"""Chunking du corpus BilanLens vers data/chunks/*.jsonl.

Pour chaque PDF du corpus annote (`tests/data/real_*.pdf`), lance
`extraire_pages` puis `decouper_page` et ecrit un fichier JSONL par
document, une ligne par chunk, dans `data/chunks/<doc>.jsonl`.

A la fin, affiche un tableau de stats :
- nombre de chunks par document,
- combien de pages ont ete decoupees en sous-morceaux,
- combien de pages ont ete recuperees par l'OCR,
- quelles pages sont encore vides apres OCR (a verifier a la main).

Usage :
    .\\.venv\\Scripts\\python.exe scripts/chunk_corpus.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pdfplumber

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from bilanlens.chunks import (  # noqa: E402
    SEUIL_VIDE_CHARS,
    decouper_page,
    extraire_pages,
)
from bilanlens.extraction import _pdf_page_text, ocr_disponible  # noqa: E402

PDF_DIR = RACINE / "tests" / "data"
CHUNKS_DIR = RACINE / "data" / "chunks"

# Mapping explicite fichier -> metadonnees. Les cles `doc` sont
# alignees avec le prefixe des `id` dans `data/benchmark/questions.jsonl`
# (ex. `sotuver_2024_01`) pour permettre un join direct cote evaluation.
DOCUMENTS = [
    ("real_sotuver_2024.pdf",          "sotuver_2024",          "SOTUVER",             2024),
    ("real_monoprix_2024.pdf",         "monoprix_2024",         "MONOPRIX",            2024),
    ("real_monoprix_consolide_2024.pdf", "monoprix_consolide_2024", "MONOPRIX (consolide)", 2024),
    ("real_delice_holding_2024.pdf",   "delice_holding_2024",   "DELICE HOLDING",      2024),
    ("real_ciments_bizerte_2024.pdf",  "ciments_bizerte_2024",  "CIMENTS DE BIZERTE",  2024),
    ("real_sfbt_2024.pdf",             "sfbt_2024",             "SFBT",                2024),
]


def _compter_pages_vides_natives(pdf_path: Path) -> int:
    """Nombre de pages dont le texte NATIF (sans OCR) tombe sous le seuil.

    C'est le nombre de pages pour lesquelles `extraire_pages` va
    DECLENCHER l'OCR. En soustrayant les pages encore vides apres
    extraction complete, on sait combien de pages ont ete RECUPEREES
    par l'OCR.
    """
    n = 0
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            if len(_pdf_page_text(page).strip()) < SEUIL_VIDE_CHARS:
                n += 1
    return n


def chunker_document(
    pdf_path: Path, doc: str, entreprise: str, exercice: int
) -> dict:
    """Chunke un PDF et retourne un dict de stats + la liste de chunks."""
    pages = extraire_pages(pdf_path)
    chunks: list = []
    pages_decoupees: list[int] = []
    for num, texte in pages:
        morceaux = decouper_page(
            texte,
            doc=doc,
            entreprise=entreprise,
            exercice=exercice,
            page_physique=num,
            page_imprimee=None,
        )
        if len(morceaux) > 1:
            pages_decoupees.append(num)
        chunks.extend(morceaux)
    pages_encore_vides = [
        n for n, t in pages if len(t.strip()) < SEUIL_VIDE_CHARS
    ]
    return {
        "chunks": chunks,
        "n_pages": len(pages),
        "pages_decoupees": pages_decoupees,
        "pages_encore_vides": pages_encore_vides,
    }


def ecrire_jsonl(chunks: list, sortie: Path) -> None:
    with sortie.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")


def main() -> int:
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    tesseract_dispo = ocr_disponible()
    print(f"Tesseract disponible : {tesseract_dispo}")
    if not tesseract_dispo:
        print(
            "  ATTENTION : OCR_TENT. restera a 0 pour toutes les pages candidates ; "
            "une page vide ne sera donc jamais recuperee silencieusement."
        )
    print()

    # OCR_TENT. : nombre de pages candidates (natif < seuil) ET Tesseract dispo.
    #             Donne 0 si Tesseract est absent, meme si des pages sont candidates
    #             -> une desactivation silencieuse de l'OCR saute aux yeux.
    # OCR_OK    : parmi les pages tentees, celles dont le texte final a repasse
    #             le seuil (donc effectivement recuperees par l'OCR).
    entete = (
        f"{'DOC':<26} {'PAGES':>5} {'CHUNKS':>6} {'DECOUP.':>7} "
        f"{'OCR_TENT.':>9} {'OCR_OK':>6} {'VIDES':>5}"
    )
    print(entete)
    print("-" * len(entete))

    totaux = {
        "pages": 0, "chunks": 0, "decoupees": 0,
        "ocr_tente": 0, "ocr_ok": 0, "vides": 0,
    }
    details_vides: dict[str, list[int]] = {}

    for fichier, doc, entreprise, exercice in DOCUMENTS:
        pdf_path = PDF_DIR / fichier
        if not pdf_path.exists():
            print(f"  MANQUANT : {pdf_path}")
            continue

        pages_candidates = _compter_pages_vides_natives(pdf_path)
        stats = chunker_document(pdf_path, doc, entreprise, exercice)
        pages_tente = pages_candidates if tesseract_dispo else 0
        pages_ok = pages_tente - len(stats["pages_encore_vides"])

        ecrire_jsonl(stats["chunks"], CHUNKS_DIR / f"{doc}.jsonl")

        print(
            f"{doc:<26} "
            f"{stats['n_pages']:>5} "
            f"{len(stats['chunks']):>6} "
            f"{len(stats['pages_decoupees']):>7} "
            f"{pages_tente:>9} "
            f"{pages_ok:>6} "
            f"{len(stats['pages_encore_vides']):>5}"
        )
        if stats["pages_encore_vides"]:
            details_vides[doc] = stats["pages_encore_vides"]

        totaux["pages"] += stats["n_pages"]
        totaux["chunks"] += len(stats["chunks"])
        totaux["decoupees"] += len(stats["pages_decoupees"])
        totaux["ocr_tente"] += pages_tente
        totaux["ocr_ok"] += pages_ok
        totaux["vides"] += len(stats["pages_encore_vides"])

    print("-" * len(entete))
    print(
        f"{'TOTAL':<26} "
        f"{totaux['pages']:>5} "
        f"{totaux['chunks']:>6} "
        f"{totaux['decoupees']:>7} "
        f"{totaux['ocr_tente']:>9} "
        f"{totaux['ocr_ok']:>6} "
        f"{totaux['vides']:>5}"
    )
    if details_vides:
        print()
        print("Pages encore vides apres OCR (a inspecter) :")
        for doc, pages in details_vides.items():
            print(f"  {doc} : {pages}")

    print()
    print(f"Chunks ecrits dans : {CHUNKS_DIR.relative_to(RACINE)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
