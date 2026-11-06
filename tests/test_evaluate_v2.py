"""Tests de scripts/evaluate_v2.py : pipeline retrieval et format
de ligne de résultat, SANS appel LLM ni API embeddings.

Les tests exercent :
- ``pipeline_v2_top5`` : retrieval `v2.1 / hybride_filtre` sur
  fausses données ; filtre entreprise AVANT top-50 ; IDF BM25
  recalculée sur le périmètre.
- ``ligne_resultat_v2`` : structure complète d'une ligne de
  ``results/v2.jsonl`` à partir d'une fausse réponse LLM.
- ``run_id_defaut_v2`` : format du run_id (``v2_<slug>_k5_
  <prompt_version_v1_2>_v2_1_hybride_filtre``).
- ``CONFIG_ID`` et ``TOP_K_FINAL`` : garde-fous figés.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from scripts.evaluate_v2 import (
    CONFIG_ID,
    TOP_K_FINAL,
    ligne_resultat_v2,
    pipeline_v2_top5,
    run_id_defaut_v2,
)


# ------------------------------------------------------------------
# Fixtures : corpus toy multi-entreprises
# ------------------------------------------------------------------

@pytest.fixture
def chunks_fake() -> list[dict]:
    """4 chunks SOTUVER + 4 chunks SFBT, 4 dim vectoriel."""
    return [
        {"chunk_id": "sotuver_2024_p1_s0", "doc": "sotuver_2024",
         "entreprise": "SOTUVER", "exercice": 2024,
         "page_physique": 1, "sous_numero": 0,
         "texte": "SOTUVER chiffre d'affaires 100 836 224 TND"},
        {"chunk_id": "sotuver_2024_p2_s0", "doc": "sotuver_2024",
         "entreprise": "SOTUVER", "exercice": 2024,
         "page_physique": 2, "sous_numero": 0,
         "texte": "SOTUVER bilan capitaux propres 120 964 179"},
        {"chunk_id": "sotuver_2024_p3_s0", "doc": "sotuver_2024",
         "entreprise": "SOTUVER", "exercice": 2024,
         "page_physique": 3, "sous_numero": 0,
         "texte": "SOTUVER immobilisations corporelles stocks"},
        {"chunk_id": "sotuver_2024_p4_s0", "doc": "sotuver_2024",
         "entreprise": "SOTUVER", "exercice": 2024,
         "page_physique": 4, "sous_numero": 0,
         "texte": "SOTUVER resultat net 13 903 690 exercice 2024"},
        {"chunk_id": "sfbt_2024_p1_s0", "doc": "sfbt_2024",
         "entreprise": "SFBT", "exercice": 2024,
         "page_physique": 1, "sous_numero": 0,
         "texte": "SFBT chiffre d'affaires 836 585 626 TND"},
        {"chunk_id": "sfbt_2024_p2_s0", "doc": "sfbt_2024",
         "entreprise": "SFBT", "exercice": 2024,
         "page_physique": 2, "sous_numero": 0,
         "texte": "SFBT bilan capitaux propres passif"},
        {"chunk_id": "sfbt_2024_p3_s0", "doc": "sfbt_2024",
         "entreprise": "SFBT", "exercice": 2024,
         "page_physique": 3, "sous_numero": 0,
         "texte": "SFBT variation capital social 2023 2024"},
        {"chunk_id": "sfbt_2024_p4_s0", "doc": "sfbt_2024",
         "entreprise": "SFBT", "exercice": 2024,
         "page_physique": 4, "sous_numero": 0,
         "texte": "SFBT notes annexes methode stocks"},
    ]


@pytest.fixture
def vecteurs_fake() -> dict[str, np.ndarray]:
    """Vecteurs orthogonaux unit-norm 4-D, 2 clusters doc."""
    return {
        "sotuver_2024_p1_s0": np.array([1, 0, 0, 0], dtype=np.float32),
        "sotuver_2024_p2_s0": np.array([0.87, 0.5, 0, 0],
                                        dtype=np.float32) / np.sqrt(1.0),
        "sotuver_2024_p3_s0": np.array([0.5, 0.87, 0, 0],
                                        dtype=np.float32) / np.sqrt(1.0),
        "sotuver_2024_p4_s0": np.array([0, 1, 0, 0], dtype=np.float32),
        "sfbt_2024_p1_s0": np.array([0, 0, 1, 0], dtype=np.float32),
        "sfbt_2024_p2_s0": np.array([0, 0, 0.87, 0.5],
                                     dtype=np.float32) / np.sqrt(1.0),
        "sfbt_2024_p3_s0": np.array([0, 0, 0.5, 0.87],
                                     dtype=np.float32) / np.sqrt(1.0),
        "sfbt_2024_p4_s0": np.array([0, 0, 0, 1], dtype=np.float32),
    }


# ------------------------------------------------------------------
# pipeline_v2_top5
# ------------------------------------------------------------------

def test_pipeline_v2_top5_filtre_restreint_a_sotuver(
    chunks_fake, vecteurs_fake,
):
    """La Q mentionne SOTUVER explicitement → périmètre restreint
    aux 4 chunks SOTUVER, aucun chunk SFBT dans le top-5."""
    chunks_par_id = {c["chunk_id"]: c for c in chunks_fake}
    q = {"id": "sotuver_test",
         "question": "Chiffre d'affaires de SOTUVER 2024"}
    q_vec = np.array([1, 0, 0, 0], dtype=np.float32)
    top5, docs_filtre = pipeline_v2_top5(
        question=q, q_vec=q_vec,
        chunks=chunks_fake, chunks_par_id=chunks_par_id,
        vecteurs_chunks=vecteurs_fake,
        top_fusion=10, top_final=5,
    )
    assert docs_filtre == ["sotuver_2024"]
    assert len(top5) == 4  # Il n'y a que 4 chunks SOTUVER.
    assert all(r["doc"] == "sotuver_2024" for r in top5)


def test_pipeline_v2_top5_filtre_restreint_a_sfbt(
    chunks_fake, vecteurs_fake,
):
    chunks_par_id = {c["chunk_id"]: c for c in chunks_fake}
    q = {"id": "sfbt_test",
         "question": "Variation du capital social de la SFBT"}
    q_vec = np.array([0, 0, 1, 0], dtype=np.float32)
    top5, docs_filtre = pipeline_v2_top5(
        question=q, q_vec=q_vec,
        chunks=chunks_fake, chunks_par_id=chunks_par_id,
        vecteurs_chunks=vecteurs_fake,
        top_fusion=10, top_final=5,
    )
    assert docs_filtre == ["sfbt_2024"]
    assert len(top5) == 4
    assert all(r["doc"] == "sfbt_2024" for r in top5)


def test_pipeline_v2_top5_rangs_1_indexes_et_consecutifs(
    chunks_fake, vecteurs_fake,
):
    chunks_par_id = {c["chunk_id"]: c for c in chunks_fake}
    q = {"id": "t", "question": "SOTUVER revenus"}
    q_vec = np.array([1, 0, 0, 0], dtype=np.float32)
    top5, _ = pipeline_v2_top5(
        question=q, q_vec=q_vec,
        chunks=chunks_fake, chunks_par_id=chunks_par_id,
        vecteurs_chunks=vecteurs_fake,
        top_fusion=10, top_final=5,
    )
    assert [r["rank"] for r in top5] == list(range(1, len(top5) + 1))


def test_pipeline_v2_top5_resultats_portent_doc_et_page(
    chunks_fake, vecteurs_fake,
):
    chunks_par_id = {c["chunk_id"]: c for c in chunks_fake}
    q = {"id": "t", "question": "SOTUVER"}
    q_vec = np.array([1, 0, 0, 0], dtype=np.float32)
    top5, _ = pipeline_v2_top5(
        question=q, q_vec=q_vec,
        chunks=chunks_fake, chunks_par_id=chunks_par_id,
        vecteurs_chunks=vecteurs_fake,
        top_fusion=10, top_final=5,
    )
    for r in top5:
        assert "doc" in r
        assert "page_physique" in r
        assert r["doc"].startswith("sotuver")


def test_pipeline_v2_top5_entreprise_non_reconnue_perimetre_global(
    chunks_fake, vecteurs_fake,
):
    chunks_par_id = {c["chunk_id"]: c for c in chunks_fake}
    # Cas non couvert par le benchmark actuel, mais important :
    # si l'entreprise n'est pas reconnue, pas de filtre, recherche
    # globale.
    q = {"id": "t", "question": "Quel est le PIB de la Tunisie ?"}
    q_vec = np.array([1, 0, 0, 0], dtype=np.float32)
    top5, docs_filtre = pipeline_v2_top5(
        question=q, q_vec=q_vec,
        chunks=chunks_fake, chunks_par_id=chunks_par_id,
        vecteurs_chunks=vecteurs_fake,
        top_fusion=10, top_final=5,
    )
    assert docs_filtre is None
    # Les 5 chunks peuvent venir des 2 docs.
    docs_vus = {r["doc"] for r in top5}
    assert len(docs_vus) >= 1  # au moins un doc, souvent les 2.


# ------------------------------------------------------------------
# ligne_resultat_v2
# ------------------------------------------------------------------

def test_ligne_resultat_v2_structure_complete():
    """Vérifie les champs obligatoires d'une ligne v2.jsonl."""
    reponse = SimpleNamespace(
        text='{"answer": "100 836 224 TND", "cited_extraits": [1]}',
        model="gemini-3.5-flash-lite",
        provider="gemini",
        temperature=0.0,
        latency_s=1.234567,
    )
    question = {"id": "sotuver_2024_01",
                "question": "Quel est le CA ?",
                "category": "extraction"}
    retrieved_top5 = [
        {"rank": 1, "chunk_id": "sotuver_2024_p4_s0",
         "doc": "sotuver_2024", "page_physique": 4, "sous_numero": 0,
         "score_rrf": 0.03},
    ]
    rec = ligne_resultat_v2(
        question=question,
        reponse=reponse,
        retrieved_top5=retrieved_top5,
        contexte="xxxxxxx",
        answer_parsed={"answer": "100 836 224 TND",
                        "cited_extraits": [1]},
        parse_ok=True,
        run_id="v2_test_run",
        prompt_version="deadbeef",
        top_k=5,
        docs_filtre=["sotuver_2024"],
    )
    # Champs clés
    assert rec["run_id"] == "v2_test_run"
    assert rec["provenance"] == "v2"
    assert rec["retrieval_config"] == "v2_1_hybride_filtre"
    assert rec["retrieval_variante"] == "v2.1"
    assert rec["docs_filtre"] == ["sotuver_2024"]
    assert rec["question_id"] == "sotuver_2024_01"
    assert rec["category"] == "extraction"
    assert rec["top_k"] == 5
    assert rec["parse_ok"] is True
    assert rec["prompt_version"] == "deadbeef"
    assert rec["context_rendered_chars"] == len("xxxxxxx")
    assert rec["model"] == "gemini-3.5-flash-lite"
    assert rec["latency_s"] == 1.235  # arrondi à 3 décimales
    # retrieved ne contient PAS le texte (reconstruit au scoring)
    assert "texte" not in rec["retrieved"][0]
    # cited_invalides est une liste (vide si tout OK)
    assert isinstance(rec["cited_invalides"], list)


def test_ligne_resultat_v2_sans_annotations_parse_ko():
    reponse = SimpleNamespace(
        text="non-JSON garbage",
        model="gemini-3.5-flash-lite",
        provider="gemini",
        temperature=0.0,
        latency_s=0.5,
    )
    rec = ligne_resultat_v2(
        question={"id": "q", "question": "q", "category": "extraction"},
        reponse=reponse,
        retrieved_top5=[],
        contexte="",
        answer_parsed=None,
        parse_ok=False,
        run_id="v2_test",
        prompt_version="x",
        top_k=5,
        docs_filtre=None,
    )
    assert rec["parse_ok"] is False
    assert rec["answer_parsed"] is None
    assert rec["docs_filtre"] is None


# ------------------------------------------------------------------
# run_id_defaut_v2 + constantes figées
# ------------------------------------------------------------------

def test_run_id_defaut_v2_format():
    rid = run_id_defaut_v2(
        "gemini-3.5-flash-lite", "634426d2b6bfde4e", 5,
    )
    # Le slug exact dépend de slug_modele() ; on vérifie le pattern
    # prefixe et suffixe.
    assert rid.startswith("v2_")
    assert rid.endswith("_v2_1_hybride_filtre")
    assert "_k5_" in rid
    assert "634426d2b6bfde4e" in rid


def test_config_id_et_top_k_figes():
    # Garde-fou : ces 2 valeurs sont celles de la décision §4.
    # Un changement doit être explicite et discuté.
    assert CONFIG_ID == "v2_1_hybride_filtre"
    assert TOP_K_FINAL == 5
