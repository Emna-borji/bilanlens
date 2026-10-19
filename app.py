
from datetime import datetime
import hashlib
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from finsight.extraction import extract_document
from finsight.mapping import map_candidates, LABELS
from finsight.analysis import (
    calculate_ratios,
    format_ratio,
    interpret_ratio,
    build_diagnostic,
    complete_financial_values,
)
from finsight.sector import detect_out_of_scope_sector, SECTOR_MESSAGES
from finsight.consistency import check_balance_sheet


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="FinSight | Analyse financière",
    page_icon="📊",
    layout="wide",
)

st.title("📊 FinSight")
st.subheader("Assistant d'analyse financière")

st.write(
    "Importez un document financier, vérifiez les postes comptables "
    "détectés, puis calculez des ratios avec un diagnostic explicable."
)


# ---------------------------------------------------------------------------
# Vérifications des clés
# ---------------------------------------------------------------------------
if not isinstance(LABELS, dict):
    st.error("LABELS doit être un dictionnaire de postes financiers.")
    st.stop()

if not all(isinstance(key, str) and key for key in LABELS):
    st.error("Chaque poste financier doit posséder une clé non vide.")
    st.stop()


# ---------------------------------------------------------------------------
# Ordre des familles de ratios
# ---------------------------------------------------------------------------
RATIO_FAMILIES = [
    ("Liquidité", ["current_ratio", "quick_ratio"]),
    ("Endettement", ["debt_to_equity", "equity_ratio"]),
    ("Rentabilité", ["net_margin", "roe", "roa"]),
    (
        "Activité",
        ["inventory_turnover", "receivables_days", "supplier_days"],
    ),
    ("Marché", ["per", "dividend_yield"]),
]


def group_ratios(ratios):
    """Regroupe les ratios en conservant l'ordre défini."""
    ratios_by_key = {ratio["key"]: ratio for ratio in ratios}

    groups = []

    for family_name, keys in RATIO_FAMILIES:
        family_ratios = [
            ratios_by_key[key]
            for key in keys
            if key in ratios_by_key
        ]

        if family_ratios:
            groups.append((family_name, family_ratios))

    return groups


# ---------------------------------------------------------------------------
# Barre latérale
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Mode de test")

    use_sample = st.checkbox(
        "Utiliser l'exemple synthétique intégré",
        value=False,
    )

    st.caption(
        "Les résultats sont indicatifs. Vérifiez les valeurs extraites "
        "avant d'utiliser le diagnostic."
    )

    st.divider()

    st.markdown("**Formats pris en charge**")
    st.write("PDF, Excel, CSV, TXT, DOCX")

    st.markdown("**Limite**")
    st.write("Les PDF scannés nécessitent un moteur OCR externe.")


# ---------------------------------------------------------------------------
# Chargement du fichier
# ---------------------------------------------------------------------------
uploaded = st.file_uploader(
    "Importer un bilan ou un rapport financier",
    type=["pdf", "xlsx", "xls", "csv", "txt", "docx"],
)

document_text = ""
source_name = ""
tables = []
extracted_records = []
source_signature = "no_document"

sample_path = (
    Path(__file__).parent
    / "samples"
    / "exemple_bilan.txt"
)


# ---------------------------------------------------------------------------
# 1. Extraction
# ---------------------------------------------------------------------------
used_ocr = False
ocr_available_flag = False

if uploaded is not None:
    try:
        extracted = extract_document(uploaded)

        document_text = extracted["text"]
        tables = extracted["tables"]
        extracted_records = extracted.get("records", [])
        used_ocr = extracted.get("used_ocr", False)
        ocr_available_flag = extracted.get("ocr_available", False)
        source_name = uploaded.name

        source_signature = hashlib.sha256(
            uploaded.getvalue()
        ).hexdigest()

    except Exception as exc:
        st.error(f"Erreur de lecture : {exc}")
        st.stop()

elif use_sample:
    if not sample_path.exists():
        st.error(
            "Le fichier d'exemple est introuvable : "
            "samples/exemple_bilan.txt"
        )
        st.stop()

    document_text = sample_path.read_text(encoding="utf-8")
    source_name = sample_path.name

    source_signature = hashlib.sha256(
        sample_path.read_bytes()
    ).hexdigest()


if not document_text.strip():
    st.warning(
        "Aucun texte exploitable n'a été extrait. "
        "Le document peut être scanné ou nécessiter une vérification manuelle."
    )

    if uploaded is None and not use_sample:
        st.info(
            "Importez un document ou activez l'exemple synthétique "
            "dans la barre latérale."
        )

    st.stop()


st.caption(f"Document chargé : {source_name}")

# -----------------------------------------------------------------------
# Avertissements OCR et détection de secteur hors périmètre.
# -----------------------------------------------------------------------
if used_ocr:
    st.warning(
        "📷 Valeurs issues de l'OCR : vérifiez-les attentivement. "
        "Les erreurs de reconnaissance (O/0, l/1, espaces parasites) "
        "sont fréquentes sur les documents scannés."
    )
elif uploaded is not None and uploaded.name.lower().endswith(".pdf") and not document_text.strip() and not ocr_available_flag:
    st.info(
        "PDF scanné : installez Tesseract pour l'OCR "
        "(https://github.com/UB-Mannheim/tesseract/wiki). "
        "L'application continue de fonctionner, "
        "mais aucun texte n'a pu être extrait automatiquement."
    )

_scope_warning = detect_out_of_scope_sector(document_text)
if _scope_warning:
    st.error(
        "⚠️ Document hors périmètre détecté — secteur "
        f"« {_scope_warning['sector']} ».\n\n"
        f"{SECTOR_MESSAGES[_scope_warning['sector']]}\n\n"
        f"Indices rencontrés : {', '.join(_scope_warning['matches'][:5])}."
    )
    st.info(
        "Vous pouvez continuer, mais les ratios ne seront pas pertinents "
        "pour ce type de bilan."
    )

with st.expander("Aperçu du texte extrait"):
    st.text(
        document_text[:12000]
        + (
            "\n… (aperçu tronqué)"
            if len(document_text) > 12000
            else ""
        )
    )


# ---------------------------------------------------------------------------
# 2. Détection des postes et sélection de la période
# ---------------------------------------------------------------------------
try:
    candidates = map_candidates(
        document_text,
        records=extracted_records or None,
    )
except Exception as exc:
    st.error(f"Erreur pendant la détection des postes : {exc}")
    st.stop()

if not candidates:
    st.warning(
        "Aucune ligne financière avec valeur numérique n'a été reconnue."
    )
    st.info(
        "Vérifiez le texte extrait. Un PDF scanné peut nécessiter un OCR."
    )


def period_sort_key(period):
    """Convertit une période JJ/MM/AAAA en date triable."""
    if not period:
        return datetime.min.date()

    try:
        return datetime.strptime(period, "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return datetime.min.date()


available_periods = sorted(
    {
        candidate.get("period")
        for candidate in candidates
        if candidate.get("period")
    },
    key=period_sort_key,
)

latest_period = (
    max(available_periods, key=period_sort_key)
    if available_periods
    else None
)

if latest_period:
    analysis_candidates = [
        candidate
        for candidate in candidates
        if candidate.get("period") == latest_period
    ]

    st.info(
        f"Période utilisée par défaut pour les ratios : "
        f"**{latest_period}**. Les exercices précédents restent "
        "disponibles dans le tableau des lignes détectées."
    )
else:
    analysis_candidates = candidates


# ---------------------------------------------------------------------------
# Préparation des valeurs détectées et des doublons
# ---------------------------------------------------------------------------
defaults = {}
ambiguous_fields = {}

for candidate in analysis_candidates:
    key = candidate.get("key")

    if not key:
        continue

    if key not in LABELS:
        continue

    if key not in defaults:
        defaults[key] = candidate["value"]
        ambiguous_fields[key] = [candidate]
    else:
        ambiguous_fields[key].append(candidate)


# ---------------------------------------------------------------------------
# 3. Réinitialisation si le document ou les valeurs détectées changent
# ---------------------------------------------------------------------------
defaults_signature = hashlib.sha256(
    json.dumps(
        defaults,
        sort_keys=True,
        default=str,
    ).encode("utf-8")
).hexdigest()

full_signature = f"{source_signature}:{defaults_signature}"

if st.session_state.get("_source_signature") != full_signature:
    for state_key in list(st.session_state.keys()):
        if state_key.startswith(("val_", "has_")):
            del st.session_state[state_key]

    st.session_state["_source_signature"] = full_signature


# ---------------------------------------------------------------------------
# 4. Vérification des postes comptables
# ---------------------------------------------------------------------------
st.header("1. Vérifier les postes comptables")

st.write(
    "Les valeurs proposées viennent du document chargé. "
    "Vérifiez les montants et les correspondances avant de calculer les ratios."
)

for key, items in ambiguous_fields.items():
    if len({item["value"] for item in items}) > 1:
        st.warning(
            f"Plusieurs montants différents correspondent à "
            f"« {LABELS[key]} ». Vérifiez la valeur proposée."
        )

        st.dataframe(
            pd.DataFrame([
                {
                    "Intitulé extrait": item.get("label", ""),
                    "Montant": item.get("value"),
                    "Période": item.get("period") or "Non précisée",
                }
                for item in items
            ]),
            use_container_width=True,
            hide_index=True,
        )


# Les clés du dictionnaire LABELS sont uniques par construction.
# Chaque widget possède une clé préfixée distincte.
keys = list(LABELS.keys())
value_map = {}

with st.form("financial_inputs"):
    cols = st.columns(2)

    for idx, field_key in enumerate(keys):
        raw = defaults.get(field_key)

        with cols[idx % 2]:
            entered = st.number_input(
                LABELS[field_key],
                value=float(raw) if raw is not None else 0.0,
                step=100.0,
                format="%.2f",
                key=f"val_{field_key}",
                help=(
                    "Valeur proposée à partir du document. "
                    "Vérifiez le montant et son unité."
                ),
            )

            has_value = st.checkbox(
                f"Valeur disponible : {LABELS[field_key]}",
                value=(raw is not None),
                key=f"has_{field_key}",
                help=(
                    "Décochez cette case si la donnée est absente du document. "
                    "Une donnée absente n'est pas égale à zéro."
                ),
            )

            value_map[field_key] = (
                float(entered) if has_value else None
            )

    submitted = st.form_submit_button("Calculer les ratios")


# ---------------------------------------------------------------------------
# 5. Tableau des lignes détectées automatiquement
# ---------------------------------------------------------------------------
if candidates:
    with st.expander(
        "Table des lignes détectées automatiquement",
        expanded=False,
    ):
        df = pd.DataFrame(candidates)

        columns_to_show = [
            column
            for column in [
                "label",
                "value",
                "period",
                "canonical_label",
                "confidence",
                "source_line",
            ]
            if column in df.columns
        ]

        st.dataframe(
            df[columns_to_show],
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------------------------
# 6. Calcul et affichage des résultats
# ---------------------------------------------------------------------------
if submitted:
    entered_values = value_map.copy()

    completed_values = complete_financial_values(
        entered_values
    )

    ratios = calculate_ratios(completed_values)
    ratio_groups = group_ratios(ratios)

    ordered_ratios = [
        ratio
        for _, family_ratios in ratio_groups
        for ratio in family_ratios
    ]

    diagnostic = build_diagnostic(
        completed_values,
        ordered_ratios,
    )

    # -----------------------------------------------------------------------
    # 6.1 Postes complétés automatiquement
    # -----------------------------------------------------------------------
    st.header("2. Vérification des postes complétés")

    calculated_rows = []

    for key, label in LABELS.items():
        original = entered_values.get(key)
        completed = completed_values.get(key)

        if original is None and completed is not None:
            calculated_rows.append({
                "Poste comptable": label,
                "Montant calculé": completed,
                "Origine": "Calcul automatique à partir des composants",
            })

    if calculated_rows:
        st.success(
            "Certains postes absents ont pu être calculés "
            "à partir des valeurs renseignées."
        )

        st.dataframe(
            pd.DataFrame(calculated_rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "Aucun sous-total supplémentaire n'a été calculé. "
            "Les postes disponibles ont été conservés tels quels."
        )

    # -----------------------------------------------------------------------
    # 6.2 Postes importants encore absents
    # -----------------------------------------------------------------------
    missing_labels = [
        LABELS[key]
        for key in [
            "current_assets",
            "current_liabilities",
            "total_assets",
            "equity",
            "total_debt",
            "revenue",
            "net_income",
        ]
        if key in LABELS and completed_values.get(key) is None
    ]

    if missing_labels:
        st.warning(
            "Les postes suivants restent indisponibles : "
            + ", ".join(missing_labels)
            + ". Certains ratios ne pourront pas être calculés."
        )

    # -----------------------------------------------------------------------
    # 6.2bis Contrôles de cohérence comptable
    # -----------------------------------------------------------------------
    st.header("3. Contrôles de cohérence")

    checks = check_balance_sheet(completed_values)
    for check in checks:
        if check["status"] == "ok":
            st.success(f"✅ {check['name']} — {check['detail']}")
        elif check["status"] == "warning":
            st.warning(f"⚠️ {check['name']} — {check['detail']}")
        else:
            st.info(f"⏭️ {check['name']} — {check['detail']}")

    # -----------------------------------------------------------------------
    # 6.3 Résultats regroupés par famille
    # -----------------------------------------------------------------------
    st.header("4. Résultats")

    for family_name, family_ratios in ratio_groups:
        st.subheader(family_name)
        metric_cols = st.columns(3)

        for idx, ratio in enumerate(family_ratios):
            with metric_cols[idx % 3]:
                st.metric(
                    ratio["name"],
                    format_ratio(ratio),
                )
                st.caption(ratio["formula"])

    # -----------------------------------------------------------------------
    # 6.4 Interprétation regroupée par famille
    # -----------------------------------------------------------------------
    st.header("5. Interprétation")

    for family_name, family_ratios in ratio_groups:
        st.subheader(family_name)

        for ratio in family_ratios:
            with st.expander(
                f"{ratio['name']} : {format_ratio(ratio)}",
                expanded=True,
            ):
                st.write(f"**Formule :** {ratio['formula']}")

                st.write(
                    interpret_ratio(
                        ratio["key"],
                        ratio["value"],
                        ordered_ratios,
                    )
                )

                st.caption(ratio["note"])

    # -----------------------------------------------------------------------
    # 6.5 Diagnostic financier et conclusion globale
    # -----------------------------------------------------------------------
    st.header("6. Diagnostic financier indicatif")

    left, right = st.columns(2)

    with left:
        st.subheader("Points forts potentiels")
        for item in diagnostic["strengths"]:
            st.success(item)

    with right:
        st.subheader("Risques à examiner")
        for item in diagnostic["risks"]:
            st.warning(item)

    st.subheader("Précautions")
    for item in diagnostic["caveats"]:
        st.info(item)

    # La conclusion est toujours affichée à la fin du diagnostic.
    st.subheader("Conclusion globale")
    st.write(diagnostic["conclusion"])

    # -----------------------------------------------------------------------
    # 7. Préparer les exports dans le même ordre que l'affichage
    # -----------------------------------------------------------------------
    export = {
        "document": source_name,
        "period": latest_period,
        "values": completed_values,
        "original_entered_values": entered_values,
        "automatically_calculated_fields": calculated_rows,
        "ratio_families": [
            {
                "family": family_name,
                "ratios": [
                    {
                        **ratio,
                        "display_value": format_ratio(ratio),
                        "interpretation": interpret_ratio(
                            ratio["key"],
                            ratio["value"],
                            ordered_ratios,
                        ),
                    }
                    for ratio in family_ratios
                ],
            }
            for family_name, family_ratios in ratio_groups
        ],
        "ratios": [
            {
                **ratio,
                "display_value": format_ratio(ratio),
                "interpretation": interpret_ratio(
                    ratio["key"],
                    ratio["value"],
                    ordered_ratios,
                ),
            }
            for ratio in ordered_ratios
        ],
        "consistency_checks": checks,
        "diagnostic": diagnostic,
        "disclaimer": (
            "Analyse pédagogique indicative. Vérifier les données extraites, "
            "les formules et les normes du cours. Les sous-totaux calculés "
            "dépendent des composants renseignés et peuvent être incomplets."
        ),
    }

    json_bytes = json.dumps(
        export,
        ensure_ascii=False,
        indent=2,
        default=str,
    ).encode("utf-8")

    csv_df = pd.DataFrame([
        {
            "famille": family_name,
            "ratio": ratio["name"],
            "value": ratio["value"],
            "formatted": format_ratio(ratio),
            "formula": ratio["formula"],
            "interpretation": interpret_ratio(
                ratio["key"],
                ratio["value"],
                ordered_ratios,
            ),
        }
        for family_name, family_ratios in ratio_groups
        for ratio in family_ratios
    ])

    # -----------------------------------------------------------------------
    # 8. Exports
    # -----------------------------------------------------------------------
    st.header("7. Exporter les résultats")

    c1, c2 = st.columns(2)

    with c1:
        st.download_button(
            "Exporter les résultats en JSON",
            data=json_bytes,
            file_name="finsight_resultats.json",
            mime="application/json",
        )

    with c2:
        st.download_button(
            "Exporter les ratios en CSV",
            data=csv_df.to_csv(
                index=False,
            ).encode("utf-8-sig"),
            file_name="finsight_ratios.csv",
            mime="text/csv",
        )

else:
    st.info(
        "Vérifiez les données proposées, cochez les postes disponibles, "
        "puis cliquez sur « Calculer les ratios »."
    )
