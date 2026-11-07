"""Tests sans réseau de ``scripts/evaluate_validation.py`` et du
mode ``validation`` de ``scripts/score.py``.

Zéro appel LLM, zéro appel API embeddings, zéro Chroma. Toutes
les fonctions pures et la lecture de fichiers sont couvertes.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.evaluate_validation import (
    BENCH_PATH as VALIDATION_BENCH_PATH,
    TOP_K_FINAL,
    TOP_K_SCORING,
    ecrire_retrieval_compare_validation,
    ligne_resultat,
    run_id_v1_2_val,
    run_id_v2_val,
)
from scripts.score import _charger_top20_par_variante


# ------------------------------------------------------------------
# Constantes figées
# ------------------------------------------------------------------

def test_top_k_final_fige_a_5():
    assert TOP_K_FINAL == 5


def test_top_k_scoring_fige_a_20():
    assert TOP_K_SCORING == 20


def test_bench_path_pointe_sur_jeu_validation():
    """Garde-fou : le script ne doit pas pointer sur le benchmark
    principal par erreur."""
    assert VALIDATION_BENCH_PATH.name == "questions_validation.jsonl"


# ------------------------------------------------------------------
# run_id V1.2 et V2 validation
# ------------------------------------------------------------------

def test_run_id_v1_2_val_prefixe_distinct():
    rid = run_id_v1_2_val(
        "gemini-3.5-flash-lite", "634426d2b6bfde4e", 5,
    )
    assert rid.startswith("v1_2_val_")
    assert "_k5_" in rid
    assert "634426d2b6bfde4e" in rid


def test_run_id_v2_val_prefixe_et_suffixe_distincts():
    rid = run_id_v2_val(
        "gemini-3.5-flash-lite", "634426d2b6bfde4e", 5,
    )
    assert rid.startswith("v2_val_")
    assert rid.endswith("_v2_1_hybride_filtre")
    assert "_k5_" in rid


def test_run_ids_v1_2_et_v2_val_distincts():
    rid1 = run_id_v1_2_val("m", "p", 5)
    rid2 = run_id_v2_val("m", "p", 5)
    assert rid1 != rid2


# ------------------------------------------------------------------
# ligne_resultat : structure
# ------------------------------------------------------------------

def _reponse_fake():
    return SimpleNamespace(
        text='{"answer": "42 TND", "cited_extraits": [1]}',
        model="gemini-3.5-flash-lite",
        provider="gemini",
        temperature=0.0,
        latency_s=1.111,
    )


def test_ligne_resultat_v1_2_validation():
    rec = ligne_resultat(
        provenance="v1_2_validation",
        retrieval_config="dense",
        retrieval_variante="v1_2",
        docs_filtre=None,
        question={"id": "val_01", "question": "q?",
                   "category": "extraction"},
        reponse=_reponse_fake(),
        retrieved_top5=[{"rank": 1, "chunk_id": "a_p1_s0",
                           "doc": "a", "page_physique": 1,
                           "sous_numero": 0}],
        contexte="xxx",
        answer_parsed={"answer": "42 TND",
                        "cited_extraits": [1]},
        parse_ok=True,
        run_id="run_v1_2_val_test",
        prompt_version="abc",
        top_k=5,
    )
    assert rec["provenance"] == "v1_2_validation"
    assert rec["benchmark"] == "validation"
    assert rec["retrieval_config"] == "dense"
    assert rec["retrieval_variante"] == "v1_2"
    # docs_filtre absent pour V1.2 (pas de filtre entreprise en dense)
    assert "docs_filtre" not in rec
    assert rec["question_id"] == "val_01"
    assert rec["top_k"] == 5
    assert rec["parse_ok"] is True


def test_ligne_resultat_v2_validation_avec_filtre():
    rec = ligne_resultat(
        provenance="v2_validation",
        retrieval_config="v2_1_hybride_filtre",
        retrieval_variante="v2.1",
        docs_filtre=["sotuver_2024"],
        question={"id": "val_01", "question": "q?",
                   "category": "extraction"},
        reponse=_reponse_fake(),
        retrieved_top5=[],
        contexte="",
        answer_parsed=None,
        parse_ok=False,
        run_id="run_v2_val_test",
        prompt_version="abc",
        top_k=5,
    )
    assert rec["provenance"] == "v2_validation"
    assert rec["benchmark"] == "validation"
    assert rec["retrieval_config"] == "v2_1_hybride_filtre"
    assert rec["retrieval_variante"] == "v2.1"
    assert rec["docs_filtre"] == ["sotuver_2024"]
    assert rec["parse_ok"] is False


# ------------------------------------------------------------------
# ecrire_retrieval_compare_validation
# ------------------------------------------------------------------

def test_ecrire_retrieval_compare_validation_format(tmp_path: Path):
    sortie = tmp_path / "rc_val.jsonl"
    v1_2 = {
        "val_01": [{"rank": 1, "chunk_id": "a_p1_s0", "doc": "a",
                     "page_physique": 1, "sous_numero": 0}],
    }
    v2 = {
        "val_01": [{"rank": 1, "chunk_id": "b_p1_s0", "doc": "b",
                     "page_physique": 1, "sous_numero": 0}],
    }
    ecrire_retrieval_compare_validation(sortie, v1_2, v2)
    lignes = [json.loads(l) for l in sortie.read_text(
        encoding="utf-8").strip().splitlines()]
    assert len(lignes) == 2
    pour_variante = {l["variante"]: l for l in lignes}
    assert pour_variante["v1_2"]["config"] == "dense"
    assert pour_variante["v2.1"]["config"] == "hybride_filtre"
    for l in lignes:
        assert l["benchmark"] == "validation"


# ------------------------------------------------------------------
# _charger_top20_par_variante (lecture jsonl retrieval compare)
# ------------------------------------------------------------------

def test_charger_top20_par_variante_filtre_correctement(tmp_path: Path):
    path = tmp_path / "rc.jsonl"
    with path.open("w", encoding="utf-8") as dst:
        # Variante v1_2 config dense
        dst.write(json.dumps({
            "variante": "v1_2", "config": "dense",
            "question_id": "val_01",
            "retrieved_top20": [{"rank": 1, "chunk_id": "x"}],
        }) + "\n")
        # Variante v2.1 config hybride_filtre
        dst.write(json.dumps({
            "variante": "v2.1", "config": "hybride_filtre",
            "question_id": "val_01",
            "retrieved_top20": [{"rank": 1, "chunk_id": "y"}],
        }) + "\n")
        # Config autre (doit être ignorée)
        dst.write(json.dumps({
            "variante": "v2.1", "config": "dense",
            "question_id": "val_01",
            "retrieved_top20": [{"rank": 1, "chunk_id": "z"}],
        }) + "\n")
    out_dense = _charger_top20_par_variante(
        path, variante="v1_2", config="dense",
    )
    out_hybride = _charger_top20_par_variante(
        path, variante="v2.1", config="hybride_filtre",
    )
    assert out_dense == {"val_01": [{"rank": 1, "chunk_id": "x"}]}
    assert out_hybride == {"val_01": [{"rank": 1, "chunk_id": "y"}]}


def test_charger_top20_par_variante_ignore_lignes_vides(tmp_path: Path):
    path = tmp_path / "rc.jsonl"
    with path.open("w", encoding="utf-8") as dst:
        dst.write("\n")
        dst.write("   \n")
        dst.write(json.dumps({
            "variante": "v1_2", "config": "dense",
            "question_id": "val_01",
            "retrieved_top20": [],
        }) + "\n")
    out = _charger_top20_par_variante(
        path, variante="v1_2", config="dense",
    )
    assert out == {"val_01": []}
