"""Validation automatique du benchmark `data/benchmark/questions.jsonl`.

Quatre niveaux de vérification :

1. **Structure** (rapide, sans PDF) : chaque ligne JSON valide, IDs uniques,
   champs obligatoires par catégorie, cohérence catégorie / answer.
2. **Arithmétique** (rapide, sans PDF) : pour chaque Q `calcul`,
   `numerateur / denominateur (* 100)` colle à `answer.value` à la
   tolérance près. Pour chaque Q `comparaison`, `target - base` colle à
   `answer.value_signed` et à `direction`.
3. **Extraits PDF** (marker `real`) : `evidence_text` et chaque
   `intermediate_values[*].evidence_text` sont présents à la page
   physique indiquée (après normalisation accents + casse).
4. **Q sans-réponse** (marker `real`) : chaque `expected_absent_keywords`
   est absent du PDF entier (recherche de racines / mots isolés, pas
   d'expressions composées — leçon de Q30).
"""
import json
import unicodedata
from collections import Counter
from pathlib import Path

import pdfplumber
import pytest


RACINE = Path(__file__).parent.parent
BENCH_PATH = RACINE / "data" / "benchmark" / "questions.jsonl"
DATA_PATH = Path(__file__).parent / "data"


def _normaliser(texte: str) -> str:
    """Minuscules + suppression des accents + normalisation whitespace
    + normalisation des apostrophes typographiques.

    L'aplatissement du whitespace (tout saut de ligne, tabulation, série
    d'espaces) en un espace unique rend la comparaison robuste aux
    retours à la ligne insérés par pdfplumber à l'intérieur d'une phrase
    (ex. « coût de\\nproduction » dans un paragraphe).

    Les apostrophes typographiques (U+2019 ’, U+2018 ‘) sont
    rabaissées en apostrophe droite (U+0027 ') pour qu'une annotation
    tapée avec un clavier et un texte extrait d'un PDF se comparent sans
    piège invisible.
    """
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn").lower()
    texte = texte.replace("’", "'").replace("‘", "'")
    texte = " ".join(texte.split())
    return texte


@pytest.fixture(scope="module")
def questions():
    """Charge toutes les questions depuis le JSONL."""
    with open(BENCH_PATH, encoding="utf-8") as f:
        return [json.loads(ligne) for ligne in f if ligne.strip()]


@pytest.fixture(scope="module")
def cache_pages():
    """Cache (nom_pdf, page_physique) -> texte normalisé."""
    return {}


def _texte_page(cache, nom_pdf, page_num):
    cle = (nom_pdf, page_num)
    if cle not in cache:
        with pdfplumber.open(DATA_PATH / nom_pdf) as pdf:
            cache[cle] = _normaliser(pdf.pages[page_num - 1].extract_text() or "")
    return cache[cle]


@pytest.fixture(scope="module")
def cache_pdfs_entiers():
    """Cache nom_pdf -> texte normalisé de toutes les pages concaténées."""
    return {}


def _texte_pdf_entier(cache, nom_pdf):
    if nom_pdf not in cache:
        with pdfplumber.open(DATA_PATH / nom_pdf) as pdf:
            cache[nom_pdf] = _normaliser(
                "\n".join((p.extract_text() or "") for p in pdf.pages)
            )
    return cache[nom_pdf]


# ---------------------------------------------------------------------------
# 1. Structure (sans PDF).
# ---------------------------------------------------------------------------
CHAMPS_REQUIS = {"id", "question", "category", "evidence_doc"}
CATEGORIES_VALIDES = {
    "extraction", "calcul", "comparaison", "texte_annexes", "sans_reponse",
}


def test_benchmark_fichier_existe():
    assert BENCH_PATH.exists(), f"Benchmark introuvable : {BENCH_PATH}"


def test_benchmark_toutes_lignes_sont_du_json_valide():
    """Chaque ligne non vide doit être un JSON valide."""
    with open(BENCH_PATH, encoding="utf-8") as f:
        for i, ligne in enumerate(f.read().splitlines(), start=1):
            if ligne.strip():
                try:
                    json.loads(ligne)
                except json.JSONDecodeError as erreur:
                    pytest.fail(f"Ligne {i} invalide : {erreur}")


def test_benchmark_ids_uniques(questions):
    ids = [q["id"] for q in questions]
    doublons = [x for x, c in Counter(ids).items() if c > 1]
    assert not doublons, f"IDs en double : {doublons}"


def test_benchmark_champs_obligatoires(questions):
    for q in questions:
        manquants = CHAMPS_REQUIS - set(q.keys())
        assert not manquants, f"{q.get('id', '?')} : champs manquants {manquants}"
        assert q["category"] in CATEGORIES_VALIDES, (
            f"{q['id']} : catégorie '{q['category']}' inconnue"
        )


def test_benchmark_coherence_categorie_answer(questions):
    """Les Q sans_reponse ont answer=null + expected_refusal_reason +
    expected_absent_keywords ; les autres ont answer non null."""
    for q in questions:
        if q["category"] == "sans_reponse":
            assert q["answer"] is None, f"{q['id']} : answer doit être null"
            assert "expected_refusal_reason" in q, (
                f"{q['id']} : expected_refusal_reason manquant"
            )
            assert "expected_absent_keywords" in q, (
                f"{q['id']} : expected_absent_keywords manquant"
            )
            assert q["expected_absent_keywords"], (
                f"{q['id']} : liste expected_absent_keywords vide"
            )
        else:
            assert q["answer"] is not None, (
                f"{q['id']} : answer ne peut pas être null"
            )


def test_benchmark_calcul_et_comparaison_ont_formule(questions):
    for q in questions:
        if q["category"] in ("calcul", "comparaison"):
            assert "calculation" in q, f"{q['id']} : calculation manquant"
            calcul = q["calculation"]
            assert "formula" in calcul, f"{q['id']} : formula manquant"
            assert "intermediate_values" in calcul, (
                f"{q['id']} : intermediate_values manquant"
            )
            assert len(calcul["intermediate_values"]) >= 2, (
                f"{q['id']} : au moins 2 valeurs intermédiaires attendues"
            )


# ---------------------------------------------------------------------------
# 2. Arithmétique (sans PDF).
# ---------------------------------------------------------------------------
def test_benchmark_calcul_ratios_coherents(questions):
    """Pour chaque Q calcul : numerateur / denominateur (* 100) ≈ answer.value."""
    for q in questions:
        if q["category"] != "calcul":
            continue
        ivs = q["calculation"]["intermediate_values"]
        cles = list(ivs.keys())
        numerateur = ivs[cles[0]]["value"]
        denominateur = ivs[cles[1]]["value"]
        formule = q["calculation"]["formula"]
        if "* 100" in formule:
            resultat = numerateur / denominateur * 100
        else:
            resultat = numerateur / denominateur
        attendu = q["answer"]["value"]
        tolerance = (
            q["answer"].get("tolerance_absolute_pp")
            or q["answer"].get("tolerance_absolute")
            or 0.1
        )
        assert abs(resultat - attendu) <= tolerance, (
            f"{q['id']} : calculé={resultat:.4f}, attendu={attendu}, "
            f"tolérance={tolerance}"
        )


def test_benchmark_comparaison_differences_coherentes(questions):
    """Pour chaque Q comparaison : target - base = value_signed, et
    direction cohérent avec le signe."""
    for q in questions:
        if q["category"] != "comparaison":
            continue
        ivs = q["calculation"]["intermediate_values"]
        cles = list(ivs.keys())
        difference = ivs[cles[0]]["value"] - ivs[cles[1]]["value"]
        attendu = q["answer"]["value_signed"]
        assert difference == attendu, (
            f"{q['id']} : {cles[0]} - {cles[1]} = {difference}, "
            f"attendu value_signed={attendu}"
        )
        direction = q["answer"]["direction"]
        if attendu > 0:
            assert direction == "augmentation", (
                f"{q['id']} : value_signed positif mais direction='{direction}'"
            )
        elif attendu < 0:
            assert direction == "diminution", (
                f"{q['id']} : value_signed négatif mais direction='{direction}'"
            )


# ---------------------------------------------------------------------------
# 3. Extraits présents dans les PDF (marker `real`).
# ---------------------------------------------------------------------------
@pytest.mark.real
def test_benchmark_evidence_text_present_a_la_page(questions, cache_pages):
    """Chaque evidence_text (hors sans_reponse) doit être présent à la page
    physique indiquée. Les segments reliés par « ... » sont vérifiés
    séparément."""
    for q in questions:
        if q["category"] == "sans_reponse":
            continue
        page_num = q["evidence_page_physical"]
        texte = _texte_page(cache_pages, q["evidence_doc"], page_num)
        for segment in q["evidence_text"].split("..."):
            segment_strip = segment.strip()
            if len(segment_strip) >= 10:
                assert _normaliser(segment_strip) in texte, (
                    f"{q['id']} : segment '{segment_strip[:60]}' "
                    f"absent de la page {page_num} de {q['evidence_doc']}"
                )


@pytest.mark.real
def test_benchmark_intermediate_values_evidence_present(questions, cache_pages):
    """Pour chaque Q calcul/comparaison, chaque intermediate_value.evidence_text
    doit être présent à sa page physique."""
    for q in questions:
        if q["category"] not in ("calcul", "comparaison"):
            continue
        for nom_iv, iv in q["calculation"]["intermediate_values"].items():
            page_num = iv["evidence_page_physical"]
            texte = _texte_page(cache_pages, q["evidence_doc"], page_num)
            assert _normaliser(iv["evidence_text"]) in texte, (
                f"{q['id']}.{nom_iv} : evidence '{iv['evidence_text'][:60]}' "
                f"absente de la page {page_num} de {q['evidence_doc']}"
            )


# ---------------------------------------------------------------------------
# 4. Q sans-réponse : mots-racines absents du PDF entier (marker `real`).
# ---------------------------------------------------------------------------
@pytest.mark.real
def test_benchmark_sans_reponse_mots_racines_absents(questions, cache_pdfs_entiers):
    """Pour chaque Q sans_reponse : chaque mot de expected_absent_keywords
    doit être absent du texte complet du PDF (toutes pages concaténées).

    Leçon de Q30 : on cherche des **racines** et des **mots isolés**
    (ex. « distribut », « dividende »), PAS des expressions composées
    (ex. « dividende distribué ») qui peuvent être formulées autrement
    dans le PDF (« Dividendes et autres distributions »).
    """
    for q in questions:
        if q["category"] != "sans_reponse":
            continue
        texte = _texte_pdf_entier(cache_pdfs_entiers, q["evidence_doc"])
        for mot_racine in q["expected_absent_keywords"]:
            mot_normalise = _normaliser(mot_racine)
            assert mot_normalise not in texte, (
                f"{q['id']} : mot-racine '{mot_racine}' TROUVÉ dans "
                f"{q['evidence_doc']} — la Q n'est pas 'sans réponse'"
            )
