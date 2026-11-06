"""Tests de bilanlens/filtre_question.py (§1 du plan V2).

Doit :
- extraire la bonne entreprise sur les 31 Q du benchmark ;
- garder les 2 docs Monoprix pour une question ambigüe ;
- renvoyer None pour une entreprise non reconnue.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bilanlens.filtre_question import (
    MOTS_CLES_CONSOLIDE,
    MOTS_CLES_INDIVIDUEL,
    entreprises_filtre,
)

ROOT = Path(__file__).resolve().parent.parent
BENCHMARK = ROOT / "data" / "benchmark" / "questions.jsonl"


ATTENDU_PAR_QID: dict[str, list[str]] = {
    # SOTUVER : Q01-Q08
    **{f"sotuver_2024_{i:02d}": ["sotuver_2024"] for i in range(1, 9)},
    # Monoprix consolidé : Q09-Q12
    **{f"monoprix_consolide_2024_{i:02d}": ["monoprix_consolide_2024"]
       for i in (9, 10, 11, 12)},
    # Monoprix individuel : Q13-Q16
    **{f"monoprix_2024_{i:02d}": ["monoprix_2024"]
       for i in (13, 14, 15, 16)},
    # SFBT : Q17-Q21
    **{f"sfbt_2024_{i:02d}": ["sfbt_2024"] for i in range(17, 22)},
    # Ciments de Bizerte : Q22-Q26
    **{f"ciments_bizerte_2024_{i:02d}": ["ciments_bizerte_2024"]
       for i in range(22, 27)},
    # Délice Holding : Q27-Q31
    **{f"delice_holding_2024_{i:02d}": ["delice_holding_2024"]
       for i in range(27, 32)},
}


def _charger_benchmark() -> list[dict]:
    out = []
    with BENCHMARK.open(encoding="utf-8") as src:
        for ligne in src:
            ligne = ligne.strip()
            if ligne:
                out.append(json.loads(ligne))
    return out


BENCHMARK_QS = _charger_benchmark()


@pytest.mark.parametrize("q", BENCHMARK_QS, ids=lambda q: q["id"])
def test_filtre_sur_31_questions_benchmark(q):
    attendu = ATTENDU_PAR_QID[q["id"]]
    obtenu = entreprises_filtre(q["question"])
    assert obtenu == attendu, (
        f"{q['id']} attendu={attendu} obtenu={obtenu}"
    )


def test_filtre_sotuver_simple():
    assert entreprises_filtre("Chiffre d'affaires de SOTUVER") == [
        "sotuver_2024"
    ]


def test_filtre_sfbt_simple():
    assert entreprises_filtre("Autonomie financière de la SFBT") == [
        "sfbt_2024"
    ]


def test_filtre_delice_holding_simple():
    assert entreprises_filtre(
        "ROE de Delice Holding au 31 décembre 2024"
    ) == ["delice_holding_2024"]


def test_filtre_ciments_de_bizerte_simple():
    assert entreprises_filtre(
        "Résultat net des Ciments de Bizerte"
    ) == ["ciments_bizerte_2024"]


def test_filtre_monoprix_consolide_mot_cle_groupe():
    assert entreprises_filtre(
        "Chiffre d'affaires consolidé du groupe Monoprix"
    ) == ["monoprix_consolide_2024"]


def test_filtre_monoprix_consolide_mot_cle_consolide():
    assert entreprises_filtre(
        "Bilan consolidé 2024 de Monoprix"
    ) == ["monoprix_consolide_2024"]


def test_filtre_monoprix_individuel_mot_cle_snmvt():
    assert entreprises_filtre(
        "Part de marché de la SNMVT-Monoprix"
    ) == ["monoprix_2024"]


def test_filtre_monoprix_individuel_mot_cle_individuel():
    assert entreprises_filtre(
        "Résultat net individuel de Monoprix 2024"
    ) == ["monoprix_2024"]


def test_filtre_monoprix_ambigu_sans_qualifier():
    # « Monoprix » tout seul = ambigu → périmètre à 2 docs (§1).
    assert entreprises_filtre("Monoprix 2024") == [
        "monoprix_2024", "monoprix_consolide_2024",
    ]


def test_filtre_monoprix_ambigu_avec_les_deux_signaux():
    # Signal consolidé ET individuel ensemble → on refuse de
    # trancher, on garde les 2 docs.
    assert entreprises_filtre(
        "Bilan consolidé et individuel de Monoprix"
    ) == ["monoprix_2024", "monoprix_consolide_2024"]


def test_filtre_entreprise_non_reconnue_renvoie_none():
    # Garde-fou : pas de filtre si on ne reconnaît pas l'entreprise.
    assert entreprises_filtre("Quel est le PIB de la Tunisie ?") is None


def test_mots_cles_desambiguation_sont_figes():
    # Garde-fou : la liste des mots-clés est versionnée dans le
    # module ; changer le contenu doit casser ce test.
    assert MOTS_CLES_CONSOLIDE == ("consolide", "consolidee", "groupe")
    assert MOTS_CLES_INDIVIDUEL == (
        "snmvt", "individuel", "individuelle",
    )
