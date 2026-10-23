
from datetime import datetime
import hashlib
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from bilanlens.extraction import extraire_document
from bilanlens.mapping import associer_candidats, LIBELLES
from bilanlens.analysis import (
    calculer_ratios,
    formater_ratio,
    interpreter_ratio,
    construire_diagnostic,
    completer_valeurs_financieres,
    NOTE_SEUILS_COURS,
)
from bilanlens.sector import detecter_secteur_hors_perimetre, MESSAGES_SECTEUR
from bilanlens.consistency import verifier_bilan


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="BilanLens | Analyse financière",
    page_icon="📊",
    layout="wide",
)

st.title("📊 BilanLens")
st.subheader("Assistant d'analyse financière")

st.write(
    "Importez un document financier, vérifiez les postes comptables "
    "détectés, puis calculez des ratios avec un diagnostic explicable."
)


# ---------------------------------------------------------------------------
# Vérifications des clés
# ---------------------------------------------------------------------------
if not isinstance(LIBELLES, dict):
    st.error("LIBELLES doit être un dictionnaire de postes financiers.")
    st.stop()

if not all(isinstance(cle, str) and cle for cle in LIBELLES):
    st.error("Chaque poste financier doit posséder une clé non vide.")
    st.stop()


# ---------------------------------------------------------------------------
# Ordre des familles de ratios
# ---------------------------------------------------------------------------
FAMILLES_RATIOS = [
    ("Ratios de liquidité", ["liquidite_generale", "liquidite_reduite"]),
    (
        "Ratios d'endettement (structure financière)",
        ["endettement", "autonomie_financiere"],
    ),
    (
        "Ratios de rentabilité",
        ["marge_nette", "rentabilite_capitaux_propres", "rentabilite_actifs"],
    ),
    (
        "Ratios d'activité (efficience)",
        ["rotation_stocks", "delai_clients", "delai_fournisseurs"],
    ),
    (
        "Ratios de marché (si données boursières)",
        ["per", "rendement_dividende"],
    ),
]


def regrouper_ratios(ratios):
    """Regroupe les ratios en conservant l'ordre défini."""
    ratios_par_cle = {ratio["cle"]: ratio for ratio in ratios}

    groupes = []

    for nom_famille, cles in FAMILLES_RATIOS:
        ratios_famille = [
            ratios_par_cle[cle]
            for cle in cles
            if cle in ratios_par_cle
        ]

        if ratios_famille:
            groupes.append((nom_famille, ratios_famille))

    return groupes


# ---------------------------------------------------------------------------
# Barre latérale
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Mode de test")

    utiliser_exemple = st.checkbox(
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
charge = st.file_uploader(
    "Importer un bilan ou un rapport financier",
    type=["pdf", "xlsx", "xls", "csv", "txt", "docx"],
)

texte_document = ""
nom_source = ""
tableaux = []
enregistrements_extraits = []
signature_source = "aucun_document"

chemin_exemple = (
    Path(__file__).parent
    / "samples"
    / "exemple_bilan.txt"
)


# ---------------------------------------------------------------------------
# 1. Extraction
# ---------------------------------------------------------------------------
ocr_utilise = False
indicateur_ocr_disponible = False

if charge is not None:
    try:
        extrait = extraire_document(charge)

        texte_document = extrait["texte"]
        tableaux = extrait["tableaux"]
        enregistrements_extraits = extrait.get("enregistrements", [])
        ocr_utilise = extrait.get("ocr_utilise", False)
        indicateur_ocr_disponible = extrait.get("ocr_disponible", False)
        nom_source = charge.name

        signature_source = hashlib.sha256(
            charge.getvalue()
        ).hexdigest()

    except Exception as exc:
        st.error(f"Erreur de lecture : {exc}")
        st.stop()

elif utiliser_exemple:
    if not chemin_exemple.exists():
        st.error(
            "Le fichier d'exemple est introuvable : "
            "samples/exemple_bilan.txt"
        )
        st.stop()

    texte_document = chemin_exemple.read_text(encoding="utf-8")
    nom_source = chemin_exemple.name

    signature_source = hashlib.sha256(
        chemin_exemple.read_bytes()
    ).hexdigest()


if not texte_document.strip():
    st.warning(
        "Aucun texte exploitable n'a été extrait. "
        "Le document peut être scanné ou nécessiter une vérification manuelle."
    )

    if charge is None and not utiliser_exemple:
        st.info(
            "Importez un document ou activez l'exemple synthétique "
            "dans la barre latérale."
        )

    st.stop()


st.caption(f"Document chargé : {nom_source}")

# -----------------------------------------------------------------------
# Avertissements OCR et détection de secteur hors périmètre.
# -----------------------------------------------------------------------
if ocr_utilise:
    st.warning(
        "📷 Valeurs issues de l'OCR : vérifiez-les attentivement. "
        "Les erreurs de reconnaissance (O/0, l/1, espaces parasites) "
        "sont fréquentes sur les documents scannés."
    )
elif charge is not None and charge.name.lower().endswith(".pdf") and not texte_document.strip() and not indicateur_ocr_disponible:
    st.info(
        "PDF scanné : installez Tesseract pour l'OCR "
        "(https://github.com/UB-Mannheim/tesseract/wiki). "
        "L'application continue de fonctionner, "
        "mais aucun texte n'a pu être extrait automatiquement."
    )

_alerte_perimetre = detecter_secteur_hors_perimetre(texte_document)
if _alerte_perimetre:
    st.error(
        "⚠️ Document hors périmètre détecté — secteur "
        f"« {_alerte_perimetre['secteur']} ».\n\n"
        f"{MESSAGES_SECTEUR[_alerte_perimetre['secteur']]}\n\n"
        f"Indices rencontrés : {', '.join(_alerte_perimetre['correspondances'][:5])}."
    )
    st.info(
        "Vous pouvez continuer, mais les ratios ne seront pas pertinents "
        "pour ce type de bilan."
    )

with st.expander("Aperçu du texte extrait"):
    st.text(
        texte_document[:12000]
        + (
            "\n… (aperçu tronqué)"
            if len(texte_document) > 12000
            else ""
        )
    )


# ---------------------------------------------------------------------------
# 2. Détection des postes et sélection de la période
# ---------------------------------------------------------------------------
try:
    candidats = associer_candidats(
        texte_document,
        enregistrements=enregistrements_extraits or None,
    )
except Exception as exc:
    st.error(f"Erreur pendant la détection des postes : {exc}")
    st.stop()

if not candidats:
    st.warning(
        "Aucune ligne financière avec valeur numérique n'a été reconnue."
    )
    st.info(
        "Vérifiez le texte extrait. Un PDF scanné peut nécessiter un OCR."
    )


def cle_tri_periode(periode):
    """Convertit une période JJ/MM/AAAA en date triable."""
    if not periode:
        return datetime.min.date()

    try:
        return datetime.strptime(periode, "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return datetime.min.date()


periodes_disponibles = sorted(
    {
        candidat.get("periode")
        for candidat in candidats
        if candidat.get("periode")
    },
    key=cle_tri_periode,
)

derniere_periode = (
    max(periodes_disponibles, key=cle_tri_periode)
    if periodes_disponibles
    else None
)

if derniere_periode:
    candidats_analyse = [
        candidat
        for candidat in candidats
        if candidat.get("periode") == derniere_periode
    ]

    st.info(
        f"Période utilisée par défaut pour les ratios : "
        f"**{derniere_periode}**. Les exercices précédents restent "
        "disponibles dans le tableau des lignes détectées."
    )
else:
    candidats_analyse = candidats


# ---------------------------------------------------------------------------
# Préparation des valeurs détectées et des doublons
# ---------------------------------------------------------------------------
valeurs_defaut = {}
rangs_defaut = {}
champs_ambigus = {}

for candidat in candidats_analyse:
    cle = candidat.get("cle")

    if not cle:
        continue

    if cle not in LIBELLES:
        continue

    rang = candidat.get("rang", 0)
    if cle not in valeurs_defaut or rang > rangs_defaut.get(cle, -1):
        valeurs_defaut[cle] = candidat["valeur"]
        rangs_defaut[cle] = rang
    champs_ambigus.setdefault(cle, []).append(candidat)


# ---------------------------------------------------------------------------
# 3. Réinitialisation si le document ou les valeurs détectées changent
# ---------------------------------------------------------------------------
signature_valeurs_defaut = hashlib.sha256(
    json.dumps(
        valeurs_defaut,
        sort_keys=True,
        default=str,
    ).encode("utf-8")
).hexdigest()

signature_complete = f"{signature_source}:{signature_valeurs_defaut}"

if st.session_state.get("_signature_source") != signature_complete:
    for cle_etat in list(st.session_state.keys()):
        if cle_etat.startswith(("val_", "a_")):
            del st.session_state[cle_etat]

    st.session_state["_signature_source"] = signature_complete


# ---------------------------------------------------------------------------
# 4. Vérification des postes comptables
# ---------------------------------------------------------------------------
st.header("1. Vérifier les postes comptables")

st.write(
    "Les valeurs proposées viennent du document chargé. "
    "Vérifiez les montants et les correspondances avant de calculer les ratios."
)

for cle, elements in champs_ambigus.items():
    if len({element["valeur"] for element in elements}) > 1:
        st.warning(
            f"Plusieurs montants différents correspondent à "
            f"« {LIBELLES[cle]} ». Vérifiez la valeur proposée."
        )

        st.dataframe(
            pd.DataFrame([
                {
                    "Intitulé extrait": element.get("libelle", ""),
                    "Montant": element.get("valeur"),
                    "Période": element.get("periode") or "Non précisée",
                }
                for element in elements
            ]),
            use_container_width=True,
            hide_index=True,
        )


# Les clés du dictionnaire LIBELLES sont uniques par construction.
# Chaque widget possède une clé préfixée distincte.
cles = list(LIBELLES.keys())
table_valeurs = {}

with st.form("saisie_financiere"):
    colonnes = st.columns(2)

    for idx, cle_champ in enumerate(cles):
        brut = valeurs_defaut.get(cle_champ)

        with colonnes[idx % 2]:
            saisi = st.number_input(
                LIBELLES[cle_champ],
                value=float(brut) if brut is not None else 0.0,
                step=100.0,
                format="%.2f",
                key=f"val_{cle_champ}",
                help=(
                    "Valeur proposée à partir du document. "
                    "Vérifiez le montant et son unité."
                ),
            )

            valeur_disponible = st.checkbox(
                f"Valeur disponible : {LIBELLES[cle_champ]}",
                value=(brut is not None),
                key=f"a_{cle_champ}",
                help=(
                    "Décochez cette case si la donnée est absente du document. "
                    "Une donnée absente n'est pas égale à zéro."
                ),
            )

            table_valeurs[cle_champ] = (
                float(saisi) if valeur_disponible else None
            )

    soumis = st.form_submit_button("Calculer les ratios")


# ---------------------------------------------------------------------------
# 5. Tableau des lignes détectées automatiquement
# ---------------------------------------------------------------------------
if candidats:
    with st.expander(
        "Table des lignes détectées automatiquement",
        expanded=False,
    ):
        df = pd.DataFrame(candidats)

        colonnes_a_afficher = [
            colonne
            for colonne in [
                "libelle",
                "valeur",
                "periode",
                "libelle_canonique",
                "confiance",
                "ligne_source",
            ]
            if colonne in df.columns
        ]

        st.dataframe(
            df[colonnes_a_afficher],
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------------------------
# 6. Calcul et affichage des résultats
# ---------------------------------------------------------------------------
if soumis:
    valeurs_saisies = table_valeurs.copy()

    valeurs_completees = completer_valeurs_financieres(
        valeurs_saisies
    )

    ratios = calculer_ratios(valeurs_completees)
    groupes_ratios = regrouper_ratios(ratios)

    ratios_ordonnes = [
        ratio
        for _, ratios_famille in groupes_ratios
        for ratio in ratios_famille
    ]

    diagnostic = construire_diagnostic(
        valeurs_completees,
        ratios_ordonnes,
    )

    # -----------------------------------------------------------------------
    # 6.1 Postes complétés automatiquement
    # -----------------------------------------------------------------------
    st.header("2. Vérification des postes complétés")

    lignes_calculees = []

    for cle, libelle in LIBELLES.items():
        originale = valeurs_saisies.get(cle)
        completee = valeurs_completees.get(cle)

        if originale is None and completee is not None:
            lignes_calculees.append({
                "Poste comptable": libelle,
                "Montant calculé": completee,
                "Origine": "Calcul automatique à partir des composants",
            })

    if lignes_calculees:
        st.success(
            "Certains postes absents ont pu être calculés "
            "à partir des valeurs renseignées."
        )

        st.dataframe(
            pd.DataFrame(lignes_calculees),
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
    libelles_manquants = [
        LIBELLES[cle]
        for cle in [
            "actifs_courants",
            "passifs_courants",
            "total_actif",
            "capitaux_propres",
            "total_dettes",
            "chiffre_affaires",
            "resultat_net",
        ]
        if cle in LIBELLES and valeurs_completees.get(cle) is None
    ]

    if libelles_manquants:
        st.warning(
            "Les postes suivants restent indisponibles : "
            + ", ".join(libelles_manquants)
            + ". Certains ratios ne pourront pas être calculés."
        )

    # -----------------------------------------------------------------------
    # 6.2bis Contrôles de cohérence comptable
    # -----------------------------------------------------------------------
    st.header("3. Contrôles de cohérence")

    controles = verifier_bilan(valeurs_completees)
    for controle in controles:
        if controle["statut"] == "ok":
            st.success(f"✅ {controle['nom']} — {controle['detail']}")
        elif controle["statut"] == "alerte":
            st.warning(f"⚠️ {controle['nom']} — {controle['detail']}")
        else:
            st.info(f"⏭️ {controle['nom']} — {controle['detail']}")

    # -----------------------------------------------------------------------
    # 6.3 Résultats regroupés par famille
    # -----------------------------------------------------------------------
    st.header("4. Résultats")

    for nom_famille, ratios_famille in groupes_ratios:
        st.subheader(nom_famille)
        colonnes_metriques = st.columns(3)

        for idx, ratio in enumerate(ratios_famille):
            with colonnes_metriques[idx % 3]:
                st.metric(
                    ratio["nom"],
                    formater_ratio(ratio),
                )
                st.caption(ratio["formule"])

    # -----------------------------------------------------------------------
    # 6.4 Interprétation regroupée par famille
    # -----------------------------------------------------------------------
    st.header("5. Interprétation")

    st.info(NOTE_SEUILS_COURS)

    for nom_famille, ratios_famille in groupes_ratios:
        st.subheader(nom_famille)

        for ratio in ratios_famille:
            with st.expander(
                f"{ratio['nom']} : {formater_ratio(ratio)}",
                expanded=True,
            ):
                st.write(f"**Formule :** {ratio['formule']}")

                st.write(
                    interpreter_ratio(
                        ratio["cle"],
                        ratio["valeur"],
                        ratios_ordonnes,
                    )
                )

                st.caption(ratio["note"])

    # -----------------------------------------------------------------------
    # 6.5 Diagnostic financier et conclusion globale
    # -----------------------------------------------------------------------
    st.header("6. Diagnostic financier indicatif")

    gauche, droite = st.columns(2)

    with gauche:
        st.subheader("Points forts potentiels")
        for element in diagnostic["points_forts"]:
            st.success(element)

    with droite:
        st.subheader("Risques à examiner")
        for element in diagnostic["risques"]:
            st.warning(element)

    st.subheader("Précautions")
    for element in diagnostic["precautions"]:
        st.info(element)

    # La conclusion est toujours affichée à la fin du diagnostic.
    st.subheader("Conclusion globale")
    st.write(diagnostic["conclusion"])

    # -----------------------------------------------------------------------
    # 7. Préparer les exports dans le même ordre que l'affichage
    # -----------------------------------------------------------------------
    export = {
        "document": nom_source,
        "periode": derniere_periode,
        "note_seuils": NOTE_SEUILS_COURS,
        "valeurs": valeurs_completees,
        "valeurs_saisies_initiales": valeurs_saisies,
        "champs_calcules_automatiquement": lignes_calculees,
        "familles_ratios": [
            {
                "famille": nom_famille,
                "ratios": [
                    {
                        **ratio,
                        "valeur_affichee": formater_ratio(ratio),
                        "interpretation": interpreter_ratio(
                            ratio["cle"],
                            ratio["valeur"],
                            ratios_ordonnes,
                        ),
                    }
                    for ratio in ratios_famille
                ],
            }
            for nom_famille, ratios_famille in groupes_ratios
        ],
        "ratios": [
            {
                **ratio,
                "valeur_affichee": formater_ratio(ratio),
                "interpretation": interpreter_ratio(
                    ratio["cle"],
                    ratio["valeur"],
                    ratios_ordonnes,
                ),
            }
            for ratio in ratios_ordonnes
        ],
        "controles_coherence": controles,
        "diagnostic": diagnostic,
        "avertissement": (
            "Analyse pédagogique indicative. Vérifier les données extraites, "
            "les formules et les normes du cours. Les sous-totaux calculés "
            "dépendent des composants renseignés et peuvent être incomplets."
        ),
    }

    octets_json = json.dumps(
        export,
        ensure_ascii=False,
        indent=2,
        default=str,
    ).encode("utf-8")

    df_csv = pd.DataFrame([
        {
            "famille": nom_famille,
            "ratio": ratio["nom"],
            "valeur": ratio["valeur"],
            "valeur_formatee": formater_ratio(ratio),
            "formule": ratio["formule"],
            "interpretation": interpreter_ratio(
                ratio["cle"],
                ratio["valeur"],
                ratios_ordonnes,
            ),
        }
        for nom_famille, ratios_famille in groupes_ratios
        for ratio in ratios_famille
    ])

    # -----------------------------------------------------------------------
    # 8. Exports
    # -----------------------------------------------------------------------
    st.header("7. Exporter les résultats")

    c1, c2 = st.columns(2)

    with c1:
        st.download_button(
            "Exporter les résultats en JSON",
            data=octets_json,
            file_name="bilanlens_resultats.json",
            mime="application/json",
        )

    with c2:
        st.download_button(
            "Exporter les ratios en CSV",
            data=df_csv.to_csv(
                index=False,
            ).encode("utf-8-sig"),
            file_name="bilanlens_ratios.csv",
            mime="text/csv",
        )

else:
    st.info(
        "Vérifiez les données proposées, cochez les postes disponibles, "
        "puis cliquez sur « Calculer les ratios »."
    )
