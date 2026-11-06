"""Validation automatique de ``data/benchmark/questions_validation.jsonl``.

Reprend les 4 niveaux de vérification de ``test_benchmark.py``
(structure, arithmétique, extraits PDF, sans_reponse mots-racines)
et y ajoute 3 contrôles spécifiques au jeu de validation :

- **Distribution** : 4 extractions / 4 calculs / 2 comparaisons /
  3 texte_annexes / 2 sans_reponse (total 15, règle du plan).
- **Deux autonomies financières** doivent cibler des sociétés
  non testées dans le benchmark principal (Ciments de Bizerte,
  Délice Holding ou Monoprix individuel).
- **Au moins une Q « sans société »** (``evidence_doc = null``)
  parmi les sans_reponse, et au moins une Q qui mentionne
  « Monoprix » sans qualifier (ni consolidé, ni groupe, ni SNMVT,
  ni individuel).
- **Pas d'overlap** avec les questions de ``questions.jsonl`` :
  les textes de question doivent être distincts (comparaison
  insensible aux accents et à la casse).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from tests.test_benchmark import (
    _normaliser,
    _texte_page,
    _texte_pdf_entier,
    cache_pages,
    cache_pdfs_entiers,
    CATEGORIES_VALIDES,
    CHAMPS_REQUIS,
)

RACINE = Path(__file__).parent.parent
VALIDATION_PATH = RACINE / "data" / "benchmark" / "questions_validation.jsonl"
BENCH_PRINCIPAL_PATH = RACINE / "data" / "benchmark" / "questions.jsonl"


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
def questions_validation():
    with VALIDATION_PATH.open(encoding="utf-8") as src:
        return [json.loads(l) for l in src if l.strip()]


@pytest.fixture(scope="module")
def questions_principales():
    with BENCH_PRINCIPAL_PATH.open(encoding="utf-8") as src:
        return [json.loads(l) for l in src if l.strip()]


# ------------------------------------------------------------------
# 1. Structure — reprise de test_benchmark.py
# ------------------------------------------------------------------

def test_validation_fichier_existe():
    assert VALIDATION_PATH.exists(), (
        f"Jeu de validation introuvable : {VALIDATION_PATH}"
    )


def test_validation_toutes_lignes_sont_du_json_valide():
    with VALIDATION_PATH.open(encoding="utf-8") as src:
        for i, ligne in enumerate(src.read().splitlines(), start=1):
            if ligne.strip():
                try:
                    json.loads(ligne)
                except json.JSONDecodeError as erreur:
                    pytest.fail(f"Ligne {i} invalide : {erreur}")


def test_validation_ids_uniques(questions_validation):
    ids = [q["id"] for q in questions_validation]
    doublons = [x for x, c in Counter(ids).items() if c > 1]
    assert not doublons, f"IDs en double : {doublons}"


def test_validation_champs_obligatoires(questions_validation):
    for q in questions_validation:
        # Les sans_reponse « sans société » peuvent avoir
        # evidence_doc = null : on allège le champ obligatoire.
        champs_mini = CHAMPS_REQUIS - {"evidence_doc"}
        manquants = champs_mini - set(q.keys())
        assert not manquants, (
            f"{q.get('id', '?')} : champs manquants {manquants}"
        )
        assert q["category"] in CATEGORIES_VALIDES, (
            f"{q['id']} : catégorie '{q['category']}' inconnue"
        )


def test_validation_coherence_categorie_answer(questions_validation):
    for q in questions_validation:
        if q["category"] == "sans_reponse":
            assert q["answer"] is None, (
                f"{q['id']} : answer doit être null"
            )
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


def test_validation_sans_reponse_evidence_page_physical_null(
    questions_validation,
):
    for q in questions_validation:
        if q["category"] == "sans_reponse":
            assert q.get("evidence_page_physical") is None, (
                f"{q['id']} : sans_reponse mais evidence_page_physical "
                f"= {q.get('evidence_page_physical')!r} (doit être null)"
            )


def test_validation_calcul_et_comparaison_ont_formule(questions_validation):
    for q in questions_validation:
        if q["category"] in ("calcul", "comparaison"):
            assert "calculation" in q, (
                f"{q['id']} : calculation manquant"
            )
            calcul = q["calculation"]
            assert "formula" in calcul
            assert "intermediate_values" in calcul
            assert len(calcul["intermediate_values"]) >= 2, (
                f"{q['id']} : au moins 2 valeurs intermédiaires"
            )


# ------------------------------------------------------------------
# 2. Arithmétique
# ------------------------------------------------------------------

def test_validation_calcul_ratios_coherents(questions_validation):
    for q in questions_validation:
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
            f"{q['id']} : calculé={resultat:.4f}, "
            f"attendu={attendu}, tolérance={tolerance}"
        )


def test_validation_comparaison_differences_coherentes(questions_validation):
    for q in questions_validation:
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
                f"{q['id']} : value_signed > 0 mais "
                f"direction='{direction}'"
            )
        elif attendu < 0:
            assert direction == "diminution", (
                f"{q['id']} : value_signed < 0 mais "
                f"direction='{direction}'"
            )


# ------------------------------------------------------------------
# 3. Extraits présents dans les PDF
# ------------------------------------------------------------------

@pytest.mark.real
def test_validation_evidence_text_present_a_la_page(
    questions_validation, cache_pages,
):
    for q in questions_validation:
        if q["category"] == "sans_reponse":
            continue
        page_num = q["evidence_page_physical"]
        texte = _texte_page(cache_pages, q["evidence_doc"], page_num)
        for segment in q["evidence_text"].split("..."):
            segment_strip = segment.strip()
            if len(segment_strip) >= 10:
                assert _normaliser(segment_strip) in texte, (
                    f"{q['id']} : segment '{segment_strip[:80]}' "
                    f"absent de la page {page_num} de {q['evidence_doc']}"
                )


@pytest.mark.real
def test_validation_intermediate_values_evidence_present(
    questions_validation, cache_pages,
):
    for q in questions_validation:
        if q["category"] not in ("calcul", "comparaison"):
            continue
        for nom_iv, iv in q["calculation"]["intermediate_values"].items():
            page_num = iv["evidence_page_physical"]
            texte = _texte_page(cache_pages, q["evidence_doc"], page_num)
            assert _normaliser(iv["evidence_text"]) in texte, (
                f"{q['id']}.{nom_iv} : evidence "
                f"'{iv['evidence_text'][:80]}' absente de la page "
                f"{page_num} de {q['evidence_doc']}"
            )


# ------------------------------------------------------------------
# 4. Sans_reponse — mots-racines absents
# ------------------------------------------------------------------

@pytest.mark.real
def test_validation_sans_reponse_mots_racines_absents(
    questions_validation, cache_pdfs_entiers,
):
    """Même règle que test_benchmark.py, avec gestion du cas
    ``evidence_doc = null`` (Q sans société) : on vérifie alors
    l'absence sur les 6 PDFs du corpus."""
    corpus = [
        "real_sotuver_2024.pdf", "real_monoprix_2024.pdf",
        "real_monoprix_consolide_2024.pdf", "real_sfbt_2024.pdf",
        "real_ciments_bizerte_2024.pdf",
        "real_delice_holding_2024.pdf",
    ]
    for q in questions_validation:
        if q["category"] != "sans_reponse":
            continue
        docs_a_verifier = (
            [q["evidence_doc"]] if q.get("evidence_doc")
            else corpus
        )
        for doc in docs_a_verifier:
            texte = _texte_pdf_entier(cache_pdfs_entiers, doc)
            for mot_racine in q["expected_absent_keywords"]:
                mot_normalise = _normaliser(mot_racine)
                assert mot_normalise not in texte, (
                    f"{q['id']} : mot-racine '{mot_racine}' "
                    f"TROUVÉ dans {doc} — pas 'sans réponse'"
                )


# ------------------------------------------------------------------
# 5. Contraintes spécifiques au jeu de validation (plan §A)
# ------------------------------------------------------------------

def test_validation_distribution_4_4_2_3_2(questions_validation):
    """Règle §A : 4 extractions, 4 calculs, 2 comparaisons,
    3 texte_annexes, 2 sans_reponse. Total = 15."""
    assert len(questions_validation) == 15
    compte = Counter(q["category"] for q in questions_validation)
    attendu = {
        "extraction": 4, "calcul": 4, "comparaison": 2,
        "texte_annexes": 3, "sans_reponse": 2,
    }
    assert dict(compte) == attendu, (
        f"Distribution incorrecte : {dict(compte)}"
    )


def test_validation_deux_autonomies_sur_non_tested(questions_validation):
    """Règle §A : 2 autonomies financières ciblant des sociétés
    non testées dans le benchmark principal (Ciments de Bizerte,
    Délice Holding ou Monoprix individuel)."""
    docs_autonomie = []
    for q in questions_validation:
        if q["category"] != "calcul":
            continue
        q_lower = q["question"].lower()
        if "autonomie financière" in q_lower:
            docs_autonomie.append(q["evidence_doc"])
    assert len(docs_autonomie) >= 2, (
        f"Attendu >= 2 autonomies financières, trouvé "
        f"{len(docs_autonomie)}"
    )
    docs_non_tested = {
        "real_ciments_bizerte_2024.pdf",
        "real_delice_holding_2024.pdf",
        "real_monoprix_2024.pdf",
    }
    for doc in docs_autonomie:
        assert doc in docs_non_tested, (
            f"Autonomie sur doc testé (benchmark principal) : {doc}"
        )


def test_validation_au_moins_une_sans_societe(questions_validation):
    """Règle §A : au moins 1 Q sans_reponse qui ne nomme aucune
    société (evidence_doc = null)."""
    sans_societe = [
        q for q in questions_validation
        if q["category"] == "sans_reponse"
        and q.get("evidence_doc") is None
    ]
    assert sans_societe, (
        "Aucune Q sans_reponse 'sans société' (evidence_doc=null)"
    )


def test_validation_au_moins_une_monoprix_sans_qualifier(
    questions_validation,
):
    """Règle §A : au moins 1 Q mentionne 'Monoprix' sans le
    qualifier (ni 'consolidé', ni 'consolidée', ni 'groupe',
    ni 'SNMVT', ni 'individuel', ni 'individuelle')."""
    marqueurs = (
        "consolide", "consolidee", "groupe",
        "snmvt", "individuel", "individuelle",
    )
    ambigues = []
    for q in questions_validation:
        q_normalisee = _normaliser(q["question"])
        if "monoprix" not in q_normalisee:
            continue
        if any(m in q_normalisee for m in marqueurs):
            continue
        ambigues.append(q["id"])
    assert ambigues, (
        "Aucune Q 'Monoprix' sans qualifier trouvée (pour tester "
        "la désambiguation du filtre V2 côté périmètre ambigu)"
    )


def test_validation_pas_doverlap_avec_benchmark_principal(
    questions_validation, questions_principales,
):
    """Règle §A : aucune Q du jeu de validation ne doit répéter
    ou reformuler trivialement une Q du benchmark principal.

    Heuristique conservatrice : on compare les questions
    normalisées (lowercase + accents retirés + whitespace
    collapsé) ; égalité stricte = overlap. (Une paraphrase
    profonde n'est pas détectée ici ; le garde-fou vrai est la
    revue utilisateur.)
    """
    questions_31 = {
        _normaliser(q["question"]) for q in questions_principales
    }
    for q in questions_validation:
        normal = _normaliser(q["question"])
        assert normal not in questions_31, (
            f"{q['id']} : question identique à une Q du "
            f"benchmark principal : '{q['question'][:80]}'"
        )
