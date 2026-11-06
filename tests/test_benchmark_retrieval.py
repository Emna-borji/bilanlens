"""Tests de scripts/benchmark_retrieval.py sur fausses données.

Exerce les fonctions pures du pipeline retrieval V2 / V2.1 sans
toucher aux vrais fichiers ``results/``, ``data/`` ou cache. Les
vecteurs, chunks, questions et top-20 V1 sont fabriqués pour
reproduire des cas canoniques (tri par cosine, tie-break, filtre
entreprise, §4 décisionnel).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from bilanlens.bm25 import IndexBM25, tokeniser, tokeniser_v2_1
from scripts.benchmark_retrieval import (
    SEUIL_RECALL_5,
    _hash_cle,
    agreger,
    charger_cache_embeddings,
    charger_chunks,
    choisir_configuration,
    dense_top_k,
    ecrire_sortie,
    enrichir,
    lancer_5_configs,
    mrr_question,
    rangs_pages_attendues,
    recall_at,
    valider_dense_vs_v1,
)


# ------------------------------------------------------------------
# Fixtures : corpus toy à 4 chunks / 2 docs, vecteurs 4-D unit-norm
# ------------------------------------------------------------------

@pytest.fixture
def chunks_fake() -> list[dict]:
    return [
        {"chunk_id": "sotuver_2024_p1_s0", "doc": "sotuver_2024",
         "entreprise": "SOTUVER", "exercice": 2024,
         "page_physique": 1, "sous_numero": 0,
         "texte": "Chiffre d'affaires de SOTUVER 100 836 224 TND"},
        {"chunk_id": "sotuver_2024_p2_s0", "doc": "sotuver_2024",
         "entreprise": "SOTUVER", "exercice": 2024,
         "page_physique": 2, "sous_numero": 0,
         "texte": "Immobilisations corporelles brutes"},
        {"chunk_id": "sfbt_2024_p1_s0", "doc": "sfbt_2024",
         "entreprise": "SFBT", "exercice": 2024,
         "page_physique": 1, "sous_numero": 0,
         "texte": "Chiffre d'affaires de la SFBT 836 585 626 TND"},
        {"chunk_id": "sfbt_2024_p2_s0", "doc": "sfbt_2024",
         "entreprise": "SFBT", "exercice": 2024,
         "page_physique": 2, "sous_numero": 0,
         "texte": "Placements financiers autres actifs"},
    ]


@pytest.fixture
def vecteurs_fake() -> dict[str, np.ndarray]:
    return {
        "sotuver_2024_p1_s0": np.array(
            [1.0, 0.0, 0.0, 0.0], dtype=np.float32),
        "sotuver_2024_p2_s0": np.array(
            [0.5, 0.5, 0.5, 0.5], dtype=np.float32),
        "sfbt_2024_p1_s0": np.array(
            [0.0, 1.0, 0.0, 0.0], dtype=np.float32),
        "sfbt_2024_p2_s0": np.array(
            [0.0, 0.0, 1.0, 0.0], dtype=np.float32),
    }


# ------------------------------------------------------------------
# _hash_cle — cohérent avec bilanlens.embeddings
# ------------------------------------------------------------------

def test_hash_cle_deterministe_et_depend_des_3_champs():
    h1 = _hash_cle("gemini-embedding-2", "RETRIEVAL_QUERY", "bonjour")
    h2 = _hash_cle("gemini-embedding-2", "RETRIEVAL_QUERY", "bonjour")
    assert h1 == h2
    assert h1 != _hash_cle("autre-model", "RETRIEVAL_QUERY", "bonjour")
    assert h1 != _hash_cle(
        "gemini-embedding-2", "RETRIEVAL_DOCUMENT", "bonjour",
    )
    assert h1 != _hash_cle("gemini-embedding-2", "RETRIEVAL_QUERY", "x")


def test_hash_cle_meme_formule_que_bilanlens_embeddings():
    # Garde-fou : la formule du hash DOIT rester identique à celle
    # de bilanlens.embeddings._hash_cle, sinon le cache n'est plus
    # lisible.
    from bilanlens.embeddings import _hash_cle as hash_prod
    assert _hash_cle("m", "t", "x") == hash_prod("m", "t", "x")


# ------------------------------------------------------------------
# charger_cache_embeddings / charger_chunks
# ------------------------------------------------------------------

def test_charger_cache_embeddings_sur_jsonl_minimal(tmp_path: Path):
    cache_path = tmp_path / "fake.jsonl"
    with cache_path.open("w", encoding="utf-8") as dst:
        dst.write(json.dumps({"key": "k1", "vec": [0.1, 0.2]}) + "\n")
        dst.write("\n")  # ligne vide : à ignorer
        dst.write(json.dumps({"key": "k2", "vec": [0.3, 0.4]}) + "\n")
    cache = charger_cache_embeddings(cache_path)
    assert set(cache.keys()) == {"k1", "k2"}
    assert cache["k1"].tolist() == pytest.approx([0.1, 0.2])
    assert cache["k1"].dtype == np.float32


def test_charger_chunks_ajoute_chunk_id(tmp_path: Path):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    (chunks_dir / "a.jsonl").write_text(
        json.dumps({
            "doc": "a", "entreprise": "A", "exercice": 2024,
            "page_physique": 1, "sous_numero": 0,
            "texte": "hello",
        }) + "\n",
        encoding="utf-8",
    )
    chunks = charger_chunks(chunks_dir)
    assert len(chunks) == 1
    assert chunks[0]["chunk_id"] == "a_p1_s0"


# ------------------------------------------------------------------
# dense_top_k — cosine + tie-break
# ------------------------------------------------------------------

def test_dense_top_k_ordre_par_similarite_decroissante(
    chunks_fake, vecteurs_fake,
):
    # Vecteur question = [1, 0, 0, 0]. Sim avec :
    # sotuver_p1 (1,0,0,0) = 1.0
    # sotuver_p2 (0.5,0.5,0.5,0.5) = 0.5
    # sfbt_p1    (0,1,0,0) = 0.0
    # sfbt_p2    (0,0,1,0) = 0.0
    # Attendu : [sotuver_p1, sotuver_p2, sfbt_p1, sfbt_p2]
    # (tie-break alphanumérique : sfbt_p1 < sfbt_p2).
    q_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    res = dense_top_k(q_vec, chunks_fake, vecteurs_fake, top_k=4)
    assert [r["chunk_id"] for r in res] == [
        "sotuver_2024_p1_s0",
        "sotuver_2024_p2_s0",
        "sfbt_2024_p1_s0",
        "sfbt_2024_p2_s0",
    ]
    assert res[0]["score"] == pytest.approx(1.0)
    assert res[1]["score"] == pytest.approx(0.5)
    assert res[2]["score"] == pytest.approx(0.0)


def test_dense_top_k_avec_filtre_restreint_le_perimetre(
    chunks_fake, vecteurs_fake,
):
    q_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    filtre = {"sotuver_2024_p1_s0", "sotuver_2024_p2_s0"}
    res = dense_top_k(
        q_vec, chunks_fake, vecteurs_fake, top_k=4,
        chunk_ids_filtre=filtre,
    )
    assert len(res) == 2
    assert all(r["chunk_id"] in filtre for r in res)
    # Rangs 1 et 2 réaffectés (l'ancien rang 1 de l'ensemble global
    # garde son rang 1, puisque c'est toujours le plus proche).
    assert res[0]["rank"] == 1
    assert res[1]["rank"] == 2


def test_dense_top_k_limite_top_k(chunks_fake, vecteurs_fake):
    q_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    res = dense_top_k(q_vec, chunks_fake, vecteurs_fake, top_k=2)
    assert len(res) == 2


# ------------------------------------------------------------------
# enrichir
# ------------------------------------------------------------------

def test_enrichir_ajoute_doc_et_page(chunks_fake):
    chunks_par_id = {c["chunk_id"]: c for c in chunks_fake}
    resultats = [{"rank": 1, "chunk_id": "sotuver_2024_p1_s0",
                  "score": 0.9}]
    out = enrichir(resultats, chunks_par_id)
    assert out[0]["doc"] == "sotuver_2024"
    assert out[0]["page_physique"] == 1
    assert out[0]["sous_numero"] == 0


# ------------------------------------------------------------------
# Métriques : rangs, recall@k, MRR
# ------------------------------------------------------------------

def test_rangs_pages_attendues_trouve_par_doc_et_page():
    attendues = {("sotuver_2024", 2), ("sotuver_2024", 5)}
    resultats = [
        {"rank": 1, "doc": "sfbt_2024", "page_physique": 1},
        {"rank": 2, "doc": "sotuver_2024", "page_physique": 2},
        {"rank": 3, "doc": "sotuver_2024", "page_physique": 5},
    ]
    rangs = rangs_pages_attendues(attendues, resultats)
    assert set(rangs.values()) == {2, 3}


def test_rangs_pages_attendues_page_absente_renvoie_moins_un():
    attendues = {("sotuver_2024", 99)}
    resultats = [
        {"rank": 1, "doc": "sotuver_2024", "page_physique": 1},
    ]
    rangs = rangs_pages_attendues(attendues, resultats)
    assert list(rangs.values()) == [-1]


def test_recall_at_exige_toutes_les_pages_attendues():
    attendues = {("doc_a", 1), ("doc_a", 5)}
    # Les 2 pages dans le top-5 → OK
    resultats = [
        {"rank": 1, "doc": "doc_a", "page_physique": 1},
        {"rank": 2, "doc": "doc_a", "page_physique": 5},
    ]
    assert recall_at(attendues, resultats, 5)
    # Une seule des deux → KO
    resultats_partiel = [
        {"rank": 1, "doc": "doc_a", "page_physique": 1},
        {"rank": 2, "doc": "doc_a", "page_physique": 7},
    ]
    assert not recall_at(attendues, resultats_partiel, 5)


def test_recall_at_restreint_au_top_k():
    attendues = {("doc_a", 1)}
    resultats = [
        {"rank": 1, "doc": "doc_a", "page_physique": 9},
        {"rank": 2, "doc": "doc_a", "page_physique": 1},
    ]
    assert not recall_at(attendues, resultats, 1)
    assert recall_at(attendues, resultats, 2)


def test_mrr_question_rang_un_vaut_un():
    attendues = {("doc_a", 1)}
    resultats = [{"rank": 1, "doc": "doc_a", "page_physique": 1}]
    assert mrr_question(attendues, resultats) == 1.0


def test_mrr_question_rang_trois_vaut_un_tiers():
    attendues = {("doc_a", 1)}
    resultats = [
        {"rank": 1, "doc": "doc_b", "page_physique": 9},
        {"rank": 2, "doc": "doc_b", "page_physique": 9},
        {"rank": 3, "doc": "doc_a", "page_physique": 1},
    ]
    assert mrr_question(attendues, resultats) == pytest.approx(1 / 3)


def test_mrr_question_aucune_attendue_renvoie_zero():
    # Conforme au protocole : sans_reponse exclut du calcul MRR.
    assert mrr_question(set(), []) == 0.0


# ------------------------------------------------------------------
# agreger
# ------------------------------------------------------------------

def test_agreger_calcule_recall_at_et_mrr():
    benchmark = [
        {"id": "q1", "category": "extraction",
         "evidence_doc": "real_doc_a.pdf", "evidence_page_physical": 1},
        {"id": "q2", "category": "extraction",
         "evidence_doc": "real_doc_a.pdf", "evidence_page_physical": 2},
        {"id": "q3", "category": "sans_reponse"},
    ]
    resultats_par_qid = {
        "q1": {
            "dense": [
                {"rank": 1, "doc": "doc_a", "page_physique": 1},
                {"rank": 2, "doc": "doc_a", "page_physique": 9},
            ],
            "bm25": [
                {"rank": 1, "doc": "doc_a", "page_physique": 9},
                {"rank": 2, "doc": "doc_a", "page_physique": 1},
            ],
            "hybride_rrf": [],
            "dense_filtre": [],
            "hybride_filtre": [],
        },
        "q2": {
            "dense": [
                {"rank": 1, "doc": "doc_a", "page_physique": 2},
            ],
            "bm25": [
                {"rank": 1, "doc": "doc_a", "page_physique": 9},
            ],
            "hybride_rrf": [],
            "dense_filtre": [],
            "hybride_filtre": [],
        },
        "q3": {k: [] for k in
               ["dense", "bm25", "hybride_rrf",
                "dense_filtre", "hybride_filtre"]},
    }
    stats = agreger(resultats_par_qid, benchmark)
    # Q3 sans_reponse ignorée → 2 Q avec page.
    assert stats["dense"]["n_q_avec_page"] == 2
    # Dense : 2/2 au R@1 et MRR = (1 + 1) / 2 = 1.0
    assert stats["dense"]["recall_at"][1] == 2
    assert stats["dense"]["mrr"] == pytest.approx(1.0)
    # BM25 : 0/2 au R@1, mais 1/2 au R@2 pour q1. MRR = (1/2 + 0)/2
    assert stats["bm25"]["recall_at"][1] == 0
    assert stats["bm25"]["recall_at"][5] == 1
    assert stats["bm25"]["mrr"] == pytest.approx(0.25)


# ------------------------------------------------------------------
# choisir_configuration — §4
# ------------------------------------------------------------------

def _stats_fake(r5: int, mrr: float) -> dict:
    return {"recall_at": {1: 0, 3: 0, 5: r5, 10: 0, 20: 0},
            "mrr": mrr, "n_q_avec_page": 27}


def test_choisir_config_aucune_depasse_seuil():
    stats = {
        "v2": {
            "dense": _stats_fake(19, 0.5),
            "bm25": _stats_fake(13, 0.3),
            "hybride_rrf": _stats_fake(15, 0.4),
            "dense_filtre": _stats_fake(19, 0.6),
            "hybride_filtre": _stats_fake(18, 0.6),
        },
        "v2.1": {k: _stats_fake(0, 0) for k in
                  ["dense", "bm25", "hybride_rrf",
                   "dense_filtre", "hybride_filtre"]},
    }
    pair, justif = choisir_configuration(stats)
    assert pair is None
    assert "pas de run LLM V2" in justif


def test_choisir_config_victoire_claire():
    stats = {
        "v2": {
            "dense": _stats_fake(19, 0.5),
            "bm25": _stats_fake(10, 0.3),
            "hybride_rrf": _stats_fake(15, 0.4),
            "dense_filtre": _stats_fake(20, 0.58),
            "hybride_filtre": _stats_fake(19, 0.67),
        },
        "v2.1": {
            "dense": _stats_fake(19, 0.5),
            "bm25": _stats_fake(18, 0.5),
            "hybride_rrf": _stats_fake(19, 0.59),
            "dense_filtre": _stats_fake(20, 0.58),
            "hybride_filtre": _stats_fake(22, 0.71),
        },
    }
    pair, _ = choisir_configuration(stats)
    assert pair == ("v2.1", "hybride_filtre")


def test_choisir_config_egalite_strict_prefere_v2_et_simplicite():
    stats = {
        "v2": {
            "dense": _stats_fake(19, 0.5),
            "bm25": _stats_fake(10, 0.3),
            "hybride_rrf": _stats_fake(15, 0.4),
            "dense_filtre": _stats_fake(22, 0.7),
            "hybride_filtre": _stats_fake(22, 0.7),
        },
        "v2.1": {
            "dense": _stats_fake(19, 0.5),
            "bm25": _stats_fake(20, 0.5),
            "hybride_rrf": _stats_fake(21, 0.59),
            "dense_filtre": _stats_fake(22, 0.7),
            "hybride_filtre": _stats_fake(22, 0.7),
        },
    }
    # 4 configs à (22, 0.7) → départage : V2 avant V2.1, puis
    # dense_filtre avant hybride_filtre.
    pair, _ = choisir_configuration(stats)
    assert pair == ("v2", "dense_filtre")


def test_choisir_config_seuil_strictement_superieur():
    # R@5 = 19 exactement = pas retenu.
    stats = {
        "v2": {k: _stats_fake(19, 0.9) for k in
                ["dense", "bm25", "hybride_rrf",
                 "dense_filtre", "hybride_filtre"]},
        "v2.1": {k: _stats_fake(19, 0.9) for k in
                  ["dense", "bm25", "hybride_rrf",
                   "dense_filtre", "hybride_filtre"]},
    }
    pair, justif = choisir_configuration(stats)
    assert pair is None
    assert SEUIL_RECALL_5 == 19


# ------------------------------------------------------------------
# valider_dense_vs_v1
# ------------------------------------------------------------------

def test_valider_dense_match_exact(tmp_path: Path):
    v1_path = tmp_path / "top20_v1.jsonl"
    with v1_path.open("w", encoding="utf-8") as dst:
        dst.write(json.dumps({
            "question_id": "q1",
            "top20": [
                {"rank": 1, "chunk_id": "a_p1_s0"},
                {"rank": 2, "chunk_id": "a_p2_s0"},
            ],
        }) + "\n")
    dense_par_qid = {
        "q1": [
            {"rank": 1, "chunk_id": "a_p1_s0"},
            {"rank": 2, "chunk_id": "a_p2_s0"},
        ],
    }
    ok, erreurs = valider_dense_vs_v1(dense_par_qid, v1_path)
    assert ok is True
    assert erreurs == []


def test_valider_dense_mismatch_detecte(tmp_path: Path):
    v1_path = tmp_path / "top20_v1.jsonl"
    with v1_path.open("w", encoding="utf-8") as dst:
        dst.write(json.dumps({
            "question_id": "q1",
            "top20": [{"rank": 1, "chunk_id": "a_p1_s0"}],
        }) + "\n")
    dense_par_qid = {
        "q1": [{"rank": 1, "chunk_id": "autre_chunk"}],
    }
    ok, erreurs = valider_dense_vs_v1(dense_par_qid, v1_path)
    assert ok is False
    assert len(erreurs) == 1


# ------------------------------------------------------------------
# lancer_5_configs — bout en bout sur fausses données
# ------------------------------------------------------------------

def test_lancer_5_configs_filtre_restreint_a_sotuver(
    chunks_fake, vecteurs_fake,
):
    chunks_par_id = {c["chunk_id"]: c for c in chunks_fake}
    bm25_global = IndexBM25(chunks_fake)
    question = {"id": "q1",
                "question": "Chiffre d'affaires de SOTUVER"}
    q_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    res = lancer_5_configs(
        question=question, q_vec=q_vec,
        chunks=chunks_fake, chunks_par_id=chunks_par_id,
        vecteurs_chunks=vecteurs_fake, bm25_global=bm25_global,
        top_fusion=10, top_final=4,
    )
    # dense_filtre : seuls les chunks SOTUVER remontent.
    docs_dense_filtre = {r["doc"] for r in res["dense_filtre"]}
    assert docs_dense_filtre == {"sotuver_2024"}
    # hybride_filtre pareil.
    docs_hybride_filtre = {r["doc"] for r in res["hybride_filtre"]}
    assert docs_hybride_filtre == {"sotuver_2024"}
    # dense global contient potentiellement les 2 docs.
    docs_dense = {r["doc"] for r in res["dense"]}
    assert "sotuver_2024" in docs_dense


def test_lancer_5_configs_dense_ne_depend_pas_du_tokenizer(
    chunks_fake, vecteurs_fake,
):
    # Garde-fou : même avec V2.1, dense et dense_filtre produisent
    # EXACTEMENT les mêmes résultats que V2 (le tokenizer ne joue
    # que sur BM25).
    chunks_par_id = {c["chunk_id"]: c for c in chunks_fake}
    bm25_v2 = IndexBM25(chunks_fake, tokenizer=tokeniser)
    bm25_v2_1 = IndexBM25(chunks_fake, tokenizer=tokeniser_v2_1)
    question = {"id": "q1", "question": "SOTUVER"}
    q_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    res_v2 = lancer_5_configs(
        question=question, q_vec=q_vec,
        chunks=chunks_fake, chunks_par_id=chunks_par_id,
        vecteurs_chunks=vecteurs_fake, bm25_global=bm25_v2,
        top_fusion=10, top_final=4, tokenizer=tokeniser,
    )
    res_v2_1 = lancer_5_configs(
        question=question, q_vec=q_vec,
        chunks=chunks_fake, chunks_par_id=chunks_par_id,
        vecteurs_chunks=vecteurs_fake, bm25_global=bm25_v2_1,
        top_fusion=10, top_final=4, tokenizer=tokeniser_v2_1,
    )
    assert [r["chunk_id"] for r in res_v2["dense"]] == [
        r["chunk_id"] for r in res_v2_1["dense"]
    ]
    assert [r["chunk_id"] for r in res_v2["dense_filtre"]] == [
        r["chunk_id"] for r in res_v2_1["dense_filtre"]
    ]


# ------------------------------------------------------------------
# ecrire_sortie
# ------------------------------------------------------------------

def test_ecrire_sortie_produit_une_ligne_par_variante_config_question(
    chunks_fake, tmp_path: Path,
):
    sortie = tmp_path / "out.jsonl"
    benchmark = [{"id": "q1", "category": "extraction"}]
    chunks_par_id = {c["chunk_id"]: c for c in chunks_fake}
    # Résultats minimaux pour 2 variantes × 5 configs × 1 Q = 10.
    base = [{
        "rank": 1, "chunk_id": "sotuver_2024_p1_s0",
        "doc": "sotuver_2024", "page_physique": 1, "sous_numero": 0,
    }]
    resultats_par_variante = {
        v: {"q1": {c: base for c in ["dense", "bm25", "hybride_rrf",
                                       "dense_filtre", "hybride_filtre"]}}
        for v in ("v2", "v2.1")
    }
    ecrire_sortie(
        sortie, resultats_par_variante,
        {"q1": ["sotuver_2024"]}, benchmark,
    )
    lignes = [json.loads(l) for l in
              sortie.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lignes) == 10
    variantes_vues = {l["variante"] for l in lignes}
    configs_vues = {l["config"] for l in lignes}
    assert variantes_vues == {"v2", "v2.1"}
    assert configs_vues == {"dense", "bm25", "hybride_rrf",
                             "dense_filtre", "hybride_filtre"}
