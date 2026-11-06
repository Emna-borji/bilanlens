"""Tests de bilanlens/retrieval_hybride.py (§3 du plan V2)."""
from __future__ import annotations

import pytest

from bilanlens.retrieval_hybride import (
    K_RRF,
    TAILLE_LISTES_AVANT_FUSION,
    fusionner_rrf,
    marquer_source,
)


def test_k_rrf_fige_a_60():
    # Garde-fou : §3 verrouille k = 60, taille 50.
    assert K_RRF == 60
    assert TAILLE_LISTES_AVANT_FUSION == 50


def test_rrf_cas_minimal_chunk_rang_1_dans_une_liste():
    # Un seul chunk, rang 1 dans une seule liste : score = 1/(60+1)
    dense = [{"chunk_id": "a_p1_s0", "rank": 1, "source": "dense"}]
    res = fusionner_rrf([dense], top_k=5)
    assert len(res) == 1
    assert res[0]["chunk_id"] == "a_p1_s0"
    assert res[0]["rank"] == 1
    assert res[0]["score_rrf"] == pytest.approx(1.0 / 61)
    assert res[0]["rangs_sources"] == {"dense": 1}


def test_rrf_chunk_dans_deux_listes_cumule_les_scores():
    # Chunk rang 1 côté dense + rang 2 côté BM25
    dense = [{"chunk_id": "a_p1_s0", "rank": 1, "source": "dense"}]
    bm25 = [{"chunk_id": "a_p1_s0", "rank": 2, "source": "bm25"}]
    res = fusionner_rrf([dense, bm25], top_k=5)
    assert len(res) == 1
    attendu = 1.0 / 61 + 1.0 / 62
    assert res[0]["score_rrf"] == pytest.approx(attendu)
    assert res[0]["rangs_sources"] == {"dense": 1, "bm25": 2}


def test_rrf_tri_par_score_decroissant():
    # chunk A : rang 1 dense + rang 5 bm25
    # chunk B : rang 1 bm25
    # Score A = 1/61 + 1/65 ≈ 0.01639 + 0.01538 = 0.03178
    # Score B = 1/61 = 0.01639
    # A doit passer devant B.
    dense = [
        {"chunk_id": "a_p1_s0", "rank": 1, "source": "dense"},
    ]
    bm25 = [
        {"chunk_id": "b_p1_s0", "rank": 1, "source": "bm25"},
        {"chunk_id": "a_p1_s0", "rank": 5, "source": "bm25"},
    ]
    res = fusionner_rrf([dense, bm25], top_k=5)
    assert [r["chunk_id"] for r in res] == ["a_p1_s0", "b_p1_s0"]
    assert res[0]["rank"] == 1
    assert res[1]["rank"] == 2


def test_rrf_tie_break_chunk_id_croissant():
    # Trois chunks, tous au même rang dans leurs listes respectives
    # → même score RRF → tri par chunk_id croissant.
    dense = [
        {"chunk_id": "z_p1_s0", "rank": 3, "source": "dense"},
        {"chunk_id": "a_p1_s0", "rank": 3, "source": "dense"},
        {"chunk_id": "m_p1_s0", "rank": 3, "source": "dense"},
    ]
    res = fusionner_rrf([dense], top_k=3)
    assert [r["chunk_id"] for r in res] == [
        "a_p1_s0", "m_p1_s0", "z_p1_s0",
    ]


def test_rrf_liste_vide():
    assert fusionner_rrf([], top_k=5) == []
    assert fusionner_rrf([[], []], top_k=5) == []


def test_rrf_top_k_limite_resultats():
    dense = [
        {"chunk_id": f"a_p{i}_s0", "rank": i, "source": "dense"}
        for i in range(1, 51)
    ]
    res = fusionner_rrf([dense], top_k=5)
    assert len(res) == 5
    assert [r["rank"] for r in res] == [1, 2, 3, 4, 5]


def test_rrf_source_par_defaut_si_absente():
    # Cas robuste : si on oublie d'annoter ``source``, la fusion
    # marche quand même et utilise une source générique.
    liste_a = [{"chunk_id": "a_p1_s0", "rank": 1}]
    liste_b = [{"chunk_id": "a_p1_s0", "rank": 1}]
    res = fusionner_rrf([liste_a, liste_b], top_k=1)
    assert set(res[0]["rangs_sources"].keys()) == {"liste_0", "liste_1"}


def test_marquer_source_n_ecrase_pas_entree():
    liste = [{"chunk_id": "a_p1_s0", "rank": 1}]
    marquee = marquer_source(liste, "dense")
    assert marquee[0]["source"] == "dense"
    assert "source" not in liste[0], (
        "marquer_source ne doit pas muter la liste d'entrée"
    )


def test_rrf_cas_realiste_dense_et_bm25_de_50_elements():
    # 50 chunks dense (ids 1..50), 50 chunks bm25 (ids 1..50) ;
    # chunks 1 et 2 tombent sur mêmes rangs → ils gagnent la
    # fusion. Chunks rangs élevés : seulement dans une liste.
    dense = [
        {"chunk_id": f"c_{i:03d}", "rank": i, "source": "dense"}
        for i in range(1, 51)
    ]
    bm25 = [
        {"chunk_id": f"c_{i:03d}", "rank": i, "source": "bm25"}
        for i in range(1, 51)
    ]
    res = fusionner_rrf([dense, bm25], top_k=5)
    assert [r["chunk_id"] for r in res] == [
        "c_001", "c_002", "c_003", "c_004", "c_005",
    ]
    for r in res:
        assert set(r["rangs_sources"].keys()) == {"dense", "bm25"}
