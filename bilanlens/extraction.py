from pathlib import Path
from datetime import datetime
import io
import re
import shutil

import pandas as pd

SUPPORTED = {".pdf", ".xlsx", ".xls", ".csv", ".txt", ".docx"}

DATE_PATTERN = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")

# Seuil de caractères par page en dessous duquel on considère la page
# comme un scan (image). On déclenche alors l'OCR si disponible.
OCR_MIN_CHARS_PER_PAGE = 40


_TESSERACT_FALLBACK_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    "/opt/homebrew/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/usr/bin/tesseract",
]


def _find_tesseract_binary():
    """Localise tesseract via PATH, puis via les chemins standards."""
    found = shutil.which("tesseract")
    if found:
        return found
    for candidate in _TESSERACT_FALLBACK_PATHS:
        if Path(candidate).exists():
            return candidate
    return None


def ocr_available() -> bool:
    """Retourne True si Tesseract et pytesseract sont disponibles."""
    if _find_tesseract_binary() is None:
        return False
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return True


def _configure_pytesseract(module):
    """Pointe pytesseract vers le binaire Tesseract trouvé."""
    binary = _find_tesseract_binary()
    if not binary:
        return
    # pytesseract expose tesseract_cmd soit sur le module lui-même,
    # soit sur un attribut interne `pytesseract` selon la version.
    inner = getattr(module, "pytesseract", module)
    inner.tesseract_cmd = binary


_OCR_NUMBER_FIXES = str.maketrans({
    # Fautes OCR fréquentes dans les nombres. On ne corrige que les
    # chaînes qui ressemblent déjà à un nombre (voir _fix_ocr_number_token).
    "O": "0",
    "o": "0",
    "l": "1",
    "I": "1",
    "S": "5",
    "B": "8",
})


_NUMBER_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-zÀ-ÿ])"
    r"(?:\(\s*)?"
    r"[-+]?[0-9OolISB][0-9OolISB.,\s  ]*"
    r"(?:\s*\))?"
    r"(?![A-Za-zÀ-ÿ])"
)


def _fix_ocr_number_token(token: str) -> str:
    """Corrige O/l/I/S/B dans un token qui ressemble à un nombre OCR.

    N'altère rien si le token ne contient aucun chiffre : on évite de
    transformer un vrai mot (« Oui », « Lot »...) en nombre.
    """
    digits_present = any(ch.isdigit() for ch in token)
    letters_present = any(ch.isalpha() for ch in token)
    if not digits_present or not letters_present:
        return token
    return token.translate(_OCR_NUMBER_FIXES)


def clean_ocr_text(text: str) -> str:
    """Corrige les erreurs OCR fréquentes dans les nombres.

    Ne modifie pas les libellés ni n'invente de valeurs : seuls les
    tokens numériques comportant une lettre confusable (O, l, I, S, B)
    sont corrigés.
    """
    if not text:
        return text

    def _replace(match):
        return _fix_ocr_number_token(match.group(0))

    cleaned = _NUMBER_TOKEN_PATTERN.sub(_replace, text)
    # Supprimer les espaces insécables parasites qui gênent le découpage
    # en colonnes (on garde les espaces normaux).
    cleaned = cleaned.replace(" ", " ").replace(" ", " ")
    return cleaned


def _ocr_pdf_bytes(raw: bytes, languages: str = "fra+eng"):
    """OCR complet d'un PDF via PyMuPDF + Tesseract.

    Retourne (texte_concaténé, pages_de_mots). `pages_de_mots` est une
    liste par page de dicts {text, x0, x1, top} compatibles avec
    `_extract_period_records_from_pdf_page` : ça permet de retrouver les
    colonnes grâce aux coordonnées même quand les montants OCR sont
    collés par un simple espace dans le texte brut.

    Retourne ("", []) si Tesseract n'est pas disponible ou si l'OCR échoue.
    """
    empty = ("", [])
    if not ocr_available():
        return empty

    try:
        import pymupdf  # type: ignore
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore
        except ImportError:
            return empty

    try:
        import pytesseract
        from pytesseract import Output
        from PIL import Image
    except ImportError:
        return empty

    _configure_pytesseract(pytesseract)

    pages_text = []
    pages_words = []
    try:
        with pymupdf.open(stream=raw, filetype="pdf") as doc:
            for page in doc:
                # 300 dpi pour un bon compromis vitesse / fiabilité OCR.
                matrix = pymupdf.Matrix(300 / 72, 300 / 72)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                img = Image.frombytes(
                    "RGB", (pix.width, pix.height), pix.samples
                )
                try:
                    page_text = pytesseract.image_to_string(
                        img, lang=languages
                    )
                    data = pytesseract.image_to_data(
                        img, lang=languages, output_type=Output.DICT
                    )
                except pytesseract.TesseractError:
                    page_text = pytesseract.image_to_string(img, lang="eng")
                    data = pytesseract.image_to_data(
                        img, lang="eng", output_type=Output.DICT
                    )
                pages_text.append(page_text)
                words = []
                for text, left, width, top in zip(
                    data["text"],
                    data["left"],
                    data["width"],
                    data["top"],
                ):
                    cleaned = (text or "").strip()
                    if not cleaned:
                        continue
                    words.append({
                        "text": cleaned,
                        "x0": float(left),
                        "x1": float(left) + float(width),
                        "top": float(top),
                    })
                pages_words.append(words)
    except Exception:
        return empty

    return ("\n".join(pages_text), pages_words)


class _OCRPage:
    """Imite une page pdfplumber pour `_extract_period_records_from_pdf_page`.

    Ne gère que `extract_words(...)` ; les tableaux structurés n'existent
    pas dans un scan.
    """

    def __init__(self, words):
        self._words = words

    def extract_words(self, **_kwargs):
        return list(self._words)


def _make_dataframe(rows):
    """Create a DataFrame safely from extracted rows."""
    if not rows:
        return pd.DataFrame()

    width = max(len(row) for row in rows)
    normalized_rows = [
        list(row) + [None] * (width - len(row))
        for row in rows
    ]

    headers = []
    for index, value in enumerate(normalized_rows[0]):
        name = str(value).strip() if value is not None else ""
        headers.append(name or f"Colonne_{index + 1}")

    seen = {}
    unique_headers = []
    for name in headers:
        seen[name] = seen.get(name, 0) + 1
        unique_headers.append(
            name if seen[name] == 1 else f"{name}_{seen[name]}"
        )

    return pd.DataFrame(normalized_rows[1:], columns=unique_headers)


def parse_amount(value):
    """Parse common French and English financial number formats."""
    if value is None:
        return None

    s = str(value).strip()

    if not s or s.lower() in {
        "nan", "none", "n/a", "na", "-", "—", "–"
    }:
        return None

    negative = s.startswith("(") and s.endswith(")")

    s = (
        s.replace("\u202f", "")
        .replace("\xa0", "")
        .replace(" ", "")
    )

    s = re.sub(
        r"(?i)(TND|DT|EUR|USD|MAD|GBP|CHF|€|\$)",
        "",
        s,
    )

    s = s.replace("%", "").replace("(", "").replace(")", "")

    sign = -1 if s.startswith("-") else 1
    if s.startswith(("-", "+")):
        s = s[1:]

    if not s or not re.fullmatch(r"\d[\d.,]*", s):
        return None

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")

    elif "," in s:
        parts = s.split(",")
        # Une seule virgule : c'est un séparateur décimal (format français
        # ou SCF tunisien, ex. « 1 281 772 854,965 » = 1 281 772 854.965).
        # Plusieurs virgules : séparateur de milliers.
        if len(parts) == 2:
            s = parts[0] + "." + parts[-1]
        else:
            s = "".join(parts)

    elif s.count(".") > 1:
        parts = s.split(".")
        s = "".join(parts[:-1]) + "." + parts[-1]

    elif "." in s:
        left, right = s.split(".", 1)
        if len(right) == 3 and left.isdigit() and right.isdigit():
            s = left + right

    try:
        result = float(s)
        return -result if negative else sign * result
    except ValueError:
        return None


def _parse_date(value):
    """Convert a supported date string to a date object."""
    match = DATE_PATTERN.search(str(value))
    if not match:
        return None

    try:
        return datetime.strptime(match.group(), "%d/%m/%Y").date()
    except ValueError:
        return None


# Regex d'un montant financier à la française :
# - entier avec groupes de 3 chiffres séparés par espace / espace fine /
#   insécable, optionnellement signé, optionnellement entre parenthèses,
# - partie décimale avec virgule ou point.
_FRENCH_AMOUNT_RE = re.compile(
    r"-?\(?-?\d{1,3}(?:[\s \xa0]\d{3})+(?:[.,]\d+)?\)?"
    r"|-?\(?-?\d+(?:[.,]\d+)?\)?"
)


def _split_amounts_in_line(line, n_periods):
    """Essaie d'identifier les n_periods derniers montants d'une ligne
    dont les colonnes sont séparées par un simple espace.

    Retourne la liste des chaînes montants (ordre d'apparition) ou None
    si la ligne ne se prête pas à cette interprétation.
    """
    if n_periods < 2:
        return None
    matches = list(_FRENCH_AMOUNT_RE.finditer(line))
    if len(matches) < n_periods:
        return None
    # Si la fin de la ligne n'est pas un montant (ex. phrase explicative),
    # ce découpage est risqué : on l'évite.
    tail = line[matches[-1].end():].strip()
    if tail and re.search(r"[A-Za-zÀ-ÿ]", tail):
        return None
    # Prendre les N derniers montants : ce sont les colonnes de période.
    period_matches = matches[-n_periods:]
    # Vérifier que les montants « colonnes » sont consécutifs : entre
    # chaque, il n'y a que des espaces (pas de texte intermédiaire).
    for a, b in zip(period_matches, period_matches[1:]):
        between = line[a.end():b.start()]
        if between.strip():
            return None
    return [m.group(0) for m in period_matches]


def _extract_period_records_from_text(text):
    """
    Extract rows containing multiple financial periods.

    Example:
    Total des actifs courants    2 400    2 500

    when the preceding header contains 31/12/2025 and 31/12/2024.
    """
    records = []
    current_periods = []

    for original_line in text.splitlines():
        line = original_line.strip()

        if not line:
            continue

        dates = DATE_PATTERN.findall(line)

        # A header containing multiple dates defines the column periods.
        if len(dates) >= 2:
            current_periods = dates
            continue

        if not current_periods:
            continue

        # PDF text often separates table columns with multiple spaces.
        # A single space inside "3 600" is preserved as a thousands separator.
        parts = [
            part.strip()
            for part in re.split(r"\s{2,}", line)
            if part.strip()
        ]

        label = None
        amount_cells = None

        if len(parts) >= len(current_periods) + 1:
            # Chemin standard : au moins N+1 parties « bien séparées ».
            label = parts[0].strip(" •-\t")
            amount_cells = parts[-len(current_periods):]
        else:
            # Chemin de repli : colonnes collées par un simple espace
            # (fréquent avec pdfplumber sur certains PDF réels).
            trailing = _split_amounts_in_line(line, len(current_periods))
            if trailing is None:
                continue
            # Le libellé est le texte avant le premier montant de queue.
            first_trail_match = next(
                m for m in _FRENCH_AMOUNT_RE.finditer(line)
                if m.group(0) == trailing[0]
                and m.start() >= line.rfind(trailing[-1]) - 500
            )
            label_text = line[:first_trail_match.start()].strip(" •-\t ")
            # Retirer un éventuel numéro de note isolé en fin de libellé
            # (ex. « Revenus 29 ... » → « Revenus »).
            label_text = re.sub(
                r"[\s ]+-?\(?\d{1,3}\)?[\s ]*$",
                "",
                label_text,
            ).strip()
            if not label_text:
                continue
            label = label_text
            amount_cells = trailing

        if not label:
            continue
        if not re.search(r"[A-Za-zÀ-ÿ]", label):
            continue

        for period, amount_cell in zip(current_periods, amount_cells):
            value = parse_amount(amount_cell)

            if value is None:
                continue

            records.append({
                "label": label,
                "value": value,
                "period": period,
                "source_line": line,
            })

    return records


def _extract_period_records_from_tables(tables):
    """Extract records directly from DataFrames with date columns."""
    records = []

    for df in tables:
        if df is None or df.empty:
            continue

        period_columns = []

        for column in df.columns:
            period_match = DATE_PATTERN.search(str(column))
            if period_match:
                period_columns.append(
                    (column, period_match.group())
                )

        if len(period_columns) < 2:
            continue

        for _, row in df.iterrows():
            # Usually the first column contains the accounting label.
            label = str(row.iloc[0]).strip() if len(row) else ""

            if not label or label.lower() in {"nan", "none"}:
                continue

            if not re.search(r"[A-Za-zÀ-ÿ]", label):
                continue

            for column, period in period_columns:
                value = parse_amount(row[column])

                if value is None:
                    continue

                records.append({
                    "label": label,
                    "value": value,
                    "period": period,
                    "source_line": f"{label} | {period}",
                })

    return records


def _extract_period_records_from_pdf_page(page, y_tolerance=3):
    """Extract financial rows using word coordinates and date-column anchors.

    `y_tolerance` : tolérance verticale pour regrouper les mots d'une
    même ligne. Les PDF natifs ont des glyphes alignés précisément (2-3
    pixels) ; une page OCR scannée à 300 dpi a besoin de bien plus
    (textbaselines légèrement décalés, 15-30 pixels).
    """
    try:
        words = page.extract_words(
            x_tolerance=2,
            y_tolerance=y_tolerance,
            keep_blank_chars=False,
        )
    except TypeError:
        # Les shims de test (ex. _OCRPage) ignorent les kwargs.
        words = page.extract_words()

    if not words:
        return []

    # Regrouper les mots par ligne visuelle.
    lines = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        target = None

        for line in reversed(lines[-3:]):
            if abs(line["top"] - word["top"]) <= y_tolerance:
                target = line
                break

        if target is None:
            lines.append({"top": word["top"], "words": [word]})
        else:
            target["words"].append(word)

    lines.sort(key=lambda line: line["top"])

    records = []
    periods = []
    anchors = []

    date_re = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
    number_re = re.compile(
        r"^\(?[-+]?\d[\d.,]*\)?%?$"
    )

    for line in lines:
        row_words = sorted(line["words"], key=lambda w: w["x0"])

        # Détecter les dates et leur position horizontale.
        date_words = [
            word for word in row_words
            if date_re.fullmatch(word["text"])
            and _parse_date(word["text"]) is not None
        ]

        if len(date_words) >= 2:
            date_words.sort(key=lambda w: w["x0"])
            periods = [word["text"] for word in date_words]
            anchors = [
                (word["x0"] + word["x1"]) / 2
                for word in date_words
            ]
            continue

        if len(periods) < 2 or len(anchors) < 2:
            continue

        numeric_words = [
            word for word in row_words
            if number_re.fullmatch(word["text"])
        ]
        if not numeric_words:
            continue

        # Construire les groupes numériques. Deux stratégies selon la
        # densité des mots :
        #  (a) montants expansés (PDF natif qui livre « 148 », « 273 »,
        #      « 413 » séparément : nombreux mots, petits gaps à
        #      l'intérieur d'un montant, grands gaps entre colonnes) ;
        #  (b) montants compacts (OCR qui concatène « 148273413 » en un
        #      seul token : un mot = une colonne).
        # On distingue avec le nombre de mots par rapport au nombre de
        # colonnes attendues.
        gaps = [
            numeric_words[i + 1]["x0"] - numeric_words[i]["x1"]
            for i in range(len(numeric_words) - 1)
        ]

        if len(numeric_words) > len(periods) and gaps:
            # Stratégie (a) : seuil adaptatif gap > 2.5 × médiane,
            # avec minimum à 6 pixels pour les PDF natifs très serrés.
            sorted_gaps = sorted(gaps)
            median_gap = sorted_gaps[len(sorted_gaps) // 2]
            gap_threshold = max(6.0, median_gap * 2.5)

            numeric_groups = []
            current_group = []
            for word in numeric_words:
                if current_group:
                    gap = word["x0"] - current_group[-1]["x1"]
                    if gap > gap_threshold:
                        numeric_groups.append(current_group)
                        current_group = []
                current_group.append(word)
            if current_group:
                numeric_groups.append(current_group)
        else:
            # Stratégie (b) : chaque mot numérique est un groupe
            # autonome (OCR qui regroupe déjà les chiffres par montant).
            numeric_groups = [[word] for word in numeric_words]

        # Il faut une valeur identifiable pour chaque période.
        if len(numeric_groups) < len(periods):
            continue

        # Associer chaque groupe numérique à la date la plus proche en
        # partant de la DROITE : la colonne la plus à droite correspond
        # toujours à la période la plus à droite. Cela empêche qu'une
        # référence de note (petit nombre dans une colonne « Notes »
        # placée à GAUCHE des montants) soit assignée à une période par
        # proximité, ce qui écraserait la vraie valeur.
        assigned = {}
        assigned_group_ids = set()
        for anchor_index in sorted(range(len(anchors)), reverse=True):
            best_group = None
            best_distance = None
            for idx, group in enumerate(numeric_groups):
                if idx in assigned_group_ids:
                    continue
                center = (group[0]["x0"] + group[-1]["x1"]) / 2
                distance = abs(center - anchors[anchor_index])
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best_group = (idx, group)
            if best_group is not None:
                idx, group = best_group
                assigned[anchor_index] = group
                assigned_group_ids.add(idx)

        if len(assigned) < len(periods):
            continue

        first_value_x = min(
            group[0]["x0"] for group in assigned.values()
        )

        label_words = [
            word["text"] for word in row_words
            if word["x1"] <= first_value_x
        ]

        label = " ".join(label_words).strip(" :-•\t")
        label = re.sub(
            r"\([A-Za-z]\.?\d+(?:\.\d+)*\)",
            "",
            label,
        ).strip()
        # Retirer un numéro de note isolé en fin de libellé
        # (ex. « Revenus 29 » → « Revenus », « Stocks 10 » → « Stocks »).
        label = re.sub(
            r"[\s ]+-?\(?\d{1,3}\)?[\s ]*$",
            "",
            label,
        ).strip()

        if not label or not re.search(r"[A-Za-zÀ-ÿ]", label):
            continue

        for index, period in enumerate(periods):
            group = assigned.get(index)
            if not group:
                continue

            amount_text = "".join(word["text"] for word in group)
            value = parse_amount(amount_text)

            if value is None:
                continue

            records.append({
                "label": label,
                "value": value,
                "period": period,
                "source_line": " ".join(
                    word["text"] for word in row_words
                ),
            })

    return records



def _deduplicate_records(records):
    """Remove duplicates without merging different periods."""
    result = []
    seen = set()

    for record in records:
        signature = (
            re.sub(r"\s+", " ", record["label"]).strip().casefold(),
            record["value"],
            record.get("period"),
        )

        if signature in seen:
            continue

        seen.add(signature)
        result.append(record)

    return result


def extract_document(uploaded_file):
    """Extract text, tables and period-aware financial records."""
    pdf_records = []
    suffix = Path(uploaded_file.name).suffix.lower()

    if suffix not in SUPPORTED:
        raise ValueError(f"Format non pris en charge : {suffix}")

    raw = uploaded_file.getvalue()
    buffer = io.BytesIO(raw)

    text = ""
    tables = []
    used_ocr = False

    if suffix == ".txt":
        text = raw.decode("utf-8-sig", errors="replace")

    elif suffix == ".csv":
        try:
            df = pd.read_csv(
                buffer,
                sep=None,
                engine="python",
                dtype=str,
                keep_default_na=False,
            )
        except Exception:
            buffer.seek(0)
            df = pd.read_csv(
                buffer,
                dtype=str,
                keep_default_na=False,
            )

        if not df.empty:
            tables.append(df)
            text = df.to_string(index=False)

    elif suffix in {".xlsx", ".xls"}:
        sheets = pd.read_excel(
            buffer,
            sheet_name=None,
            dtype=str,
        )

        text_parts = []

        for sheet_name, df in sheets.items():
            if not df.empty:
                tables.append(df)
                text_parts.append(
                    f"\nFeuille : {sheet_name}\n{df.to_string(index=False)}"
                )

        text = "\n".join(text_parts)

    
    elif suffix == ".pdf":
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                page_texts = []

                for page_number, page in enumerate(pdf.pages, start=1):
                    page_texts.append(
                        f"\n--- Page {page_number} ---\n"
                        f"{page.extract_text() or ''}"
                    )

                    # Extraction des tableaux structurés.
                    for extracted_table in page.extract_tables() or []:
                        df = _make_dataframe(extracted_table)
                        if not df.empty:
                            tables.append(df)

                    # Extraction indépendante grâce aux coordonnées.
                    pdf_records.extend(
                        _extract_period_records_from_pdf_page(page)
                    )

                text = "\n".join(page_texts)

        except Exception as exc:
            raise ValueError(
                f"Impossible de lire ce PDF : {exc}"
            ) from exc

        # OCR en repli si pdfplumber n'a rien renvoyé d'exploitable.
        # Déclencheur : trop peu de caractères par page ET aucun record
        # extrait des tableaux structurés ou des coordonnées.
        try:
            import pdfplumber  # noqa: F401
            with pdfplumber.open(io.BytesIO(raw)) as _pdf:
                page_count = max(1, len(_pdf.pages))
        except Exception:
            page_count = 1

        text_density = len(text.strip()) / page_count

        if (
            text_density < OCR_MIN_CHARS_PER_PAGE
            and not pdf_records
            and not tables
        ):
            if ocr_available():
                ocr_text, ocr_pages_words = _ocr_pdf_bytes(raw)
                if ocr_text:
                    text = clean_ocr_text(ocr_text)
                    used_ocr = True
                    # Rejouer l'extraction par coordonnées sur les mots
                    # retournés par l'OCR : on retrouve ainsi les colonnes
                    # grâce aux positions x, y des mots, exactement comme
                    # pour un PDF à couche texte. Pages scannées à 300 dpi
                    # → y_tolerance plus permissif (lignes légèrement
                    # obliques, textbaselines imprécises).
                    for words in ocr_pages_words:
                        pdf_records.extend(
                            _extract_period_records_from_pdf_page(
                                _OCRPage(words), y_tolerance=30
                            )
                        )


    elif suffix == ".docx":
        try:
            from docx import Document

            doc = Document(io.BytesIO(raw))

            text_parts = [
                paragraph.text
                for paragraph in doc.paragraphs
                if paragraph.text.strip()
            ]

            for extracted_table in doc.tables:
                rows = [
                    [cell.text.strip() for cell in row.cells]
                    for row in extracted_table.rows
                ]

                df = _make_dataframe(rows)
                if not df.empty:
                    tables.append(df)

            text = "\n".join(text_parts)

        except Exception as exc:
            raise ValueError(
                f"Impossible de lire ce document Word : {exc}"
            ) from exc

    # Prefer structured table records, then use the extracted PDF/text layout.
    # Duplicate label/value/period records are removed.

    table_records = _extract_period_records_from_tables(tables)

    if suffix == ".pdf":
        # Priorité aux tableaux structurés et aux coordonnées.
        # Le texte sert de repli si aucune extraction structurée n'a réussi.
        if table_records or pdf_records:
            records = _deduplicate_records(table_records + pdf_records)
        else:
            records = _deduplicate_records(
                _extract_period_records_from_text(text)
            )
    else:
        text_records = _extract_period_records_from_text(text)
        records = _deduplicate_records(table_records + text_records)


    if used_ocr:
        for record in records:
            record["ocr"] = True

    return {
        "text": text,
        "tables": tables,
        "records": records,
        "suffix": suffix,
        "used_ocr": used_ocr,
        "ocr_available": ocr_available(),
    }


def extract_labeled_values(text):
    """Extract label/value pairs, preserving periods when detected."""
    period_records = _extract_period_records_from_text(text)

    if period_records:
        return _deduplicate_records(period_records)

    results = []
    seen = set()

    currency = r"(?:TND|DT|EUR|USD|MAD|GBP|CHF|€|\$)"

    patterns = [
        re.compile(r"^(.*?)\s*:\s*(.*?)\s*$"),
        re.compile(
            r"^(.*?)\s+"
            r"([-+]?\(?\d[\d\s.,]*\)?)"
            rf"\s*{currency}?\s*$",
            re.IGNORECASE,
        ),
    ]

    for original_line in text.splitlines():
        line = original_line.strip()

        if not line or len(line) > 500:
            continue

        label = ""
        amount = None

        colon_match = patterns[0].match(line)

        if colon_match:
            possible_label = colon_match.group(1).strip(" •-\t")
            possible_value = colon_match.group(2).strip()
            parsed = parse_amount(possible_value)

            if possible_label and parsed is not None:
                label = possible_label
                amount = parsed

        if amount is None:
            match = patterns[1].match(line)

            if match:
                possible_label = match.group(1).strip(" •-\t")
                possible_value = match.group(2).strip()
                parsed = parse_amount(possible_value)

                if (
                    possible_label
                    and re.search(r"[A-Za-zÀ-ÿ]", possible_label)
                    and parsed is not None
                ):
                    label = possible_label
                    amount = parsed

        if amount is None or not label:
            continue

        signature = (label.casefold(), amount)

        if signature not in seen:
            seen.add(signature)
            results.append({
                "label": label,
                "value": amount,
                "period": None,
                "source_line": line,
            })

    return results