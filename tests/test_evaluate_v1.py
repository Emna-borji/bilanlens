"""Tests unitaires d'evaluate_v1.py.

Pas de reseau : LLM mock, encodeur mock, Chroma mock. L'objectif est
de verifier :
1. Le parsing de la reponse Chroma (ids, distances, metadatas) ;
2. Le format du contexte `=== Extrait N : doc, page X ===` ;
3. La validation des `cited_extraits` (invalides si hors [1, k]) ;
4. Le format de la ligne results/v1.jsonl ;
5. Le dispatch run_id V1 (v1_<model>_<prompt_version>).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest


# ---------------------------------------------------------------------------
# Fakes : encoder, LLM, collection Chroma.
# ---------------------------------------------------------------------------
@dataclass
class _FauxResponse:
    text: str
    model: str = "fake-model-001"
    provider: str = "fake"
    temperature: float = 0.0
    latency_s: float = 0.01


class FakeLLM:
    """Repond ce qu'on lui dit. Trace chaque kwarg d'appel."""

    def __init__(self, reponse_text: str):
        self._reponse_text = reponse_text
        self.appels: list[dict] = []

    def generate(
        self, prompt, system=None, temperature=0.0, response_schema=None,
    ):
        self.appels.append({
            "prompt": prompt,
            "system": system,
            "temperature": temperature,
            "response_schema": response_schema,
        })
        return _FauxResponse(text=self._reponse_text)


class FakeEncoder:
    """Retourne un vecteur unite deterministe par sha256(texte).

    `hashlib.sha256` et PAS `hash()` builtin : `hash()` varie avec
    `PYTHONHASHSEED` d'une execution Python a l'autre (randomise par
    defaut depuis Python 3.3), donc deux runs du MEME test
    verraient des vecteurs differents. `EncodeurFake` dans
    `bilanlens/embeddings.py` suit le meme pattern pour la meme
    raison.
    """

    def __init__(self, dim: int = 8):
        self.dim = dim
        self.model = "fake-encoder"

    def embed_query(self, texte: str):
        import hashlib

        import numpy as np

        digest = hashlib.sha256(texte.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big")
        rng = np.random.default_rng(seed)
        v = rng.normal(size=self.dim)
        return v / np.linalg.norm(v)


class FakeCollection:
    """Retourne un result Chroma precuite. Verifie que `n_results`
    est bien passe."""

    def __init__(self, result: dict):
        self._result = result
        self.appels: list[dict] = []

    def query(self, query_embeddings, n_results):
        self.appels.append({
            "query_embeddings": query_embeddings,
            "n_results": n_results,
        })
        return self._result


def _result_chroma_simule(k: int = 3) -> dict:
    """Produit un result Chroma plausible pour `k` chunks."""
    return {
        "ids": [[f"doc_a_p{i+1}_s0" for i in range(k)]],
        "distances": [[0.1 * (i + 1) for i in range(k)]],
        "documents": [[f"Texte extrait {i+1}." for i in range(k)]],
        "metadatas": [[
            {
                "doc": "doc_a" if i < k - 1 else "doc_b",
                "page_physique": i + 1,
                "sous_numero": 0,
            } for i in range(k)
        ]],
    }


# ---------------------------------------------------------------------------
# 1. Parsing du result Chroma
# ---------------------------------------------------------------------------
def test_parser_retrieved_extrait_chunk_id_doc_page_distance():
    from scripts.evaluate_v1 import parser_retrieved

    result = _result_chroma_simule(k=3)
    retrieved = parser_retrieved(result)

    assert len(retrieved) == 3
    assert retrieved[0] == {
        "rank": 1,
        "chunk_id": "doc_a_p1_s0",
        "doc": "doc_a",
        "page_physique": 1,
        "sous_numero": 0,
        "distance": 0.1,
        "texte": "Texte extrait 1.",
    }
    # Rangs croissants, derniere entree = doc_b.
    assert retrieved[1]["rank"] == 2
    assert retrieved[2]["doc"] == "doc_b"


def test_parser_retrieved_result_vide_retourne_liste_vide():
    from scripts.evaluate_v1 import parser_retrieved

    assert parser_retrieved({}) == []
    assert parser_retrieved({"ids": [[]], "distances": [[]],
                             "documents": [[]], "metadatas": [[]]}) == []


# ---------------------------------------------------------------------------
# 2. Format du contexte
# ---------------------------------------------------------------------------
def test_formater_contexte_separateurs_explicites_dans_ordre_du_rang():
    from scripts.evaluate_v1 import formater_contexte, parser_retrieved

    retrieved = parser_retrieved(_result_chroma_simule(k=3))
    ctx = formater_contexte(retrieved)

    # Rang 1 est le plus proche -> en premier.
    assert ctx.index("=== Extrait 1 :") < ctx.index("=== Extrait 2 :")
    assert ctx.index("=== Extrait 2 :") < ctx.index("=== Extrait 3 :")
    assert "doc_a, page 1" in ctx
    assert "doc_b, page 3" in ctx
    # Texte present.
    assert "Texte extrait 1." in ctx


# ---------------------------------------------------------------------------
# 3. Validation des citations
# ---------------------------------------------------------------------------
def test_citations_invalides_detecte_hors_range():
    from scripts.evaluate_v1 import citations_invalides

    # Context de 5 extraits.
    assert citations_invalides([1, 3, 5], 5) == []
    # 7 est hors range.
    assert citations_invalides([1, 7], 5) == [7]
    # 0 est hors range (positions 1-based).
    assert citations_invalides([0, 1], 5) == [0]
    # Negatif.
    assert citations_invalides([-1], 5) == [-1]
    # Liste vide : aucune invalide.
    assert citations_invalides([], 5) == []


# ---------------------------------------------------------------------------
# 4. Parse de la reponse V1 (3 cles obligatoires)
# ---------------------------------------------------------------------------
def test_parser_reponse_v1_valide():
    from scripts.evaluate_v1 import parser_reponse_v1

    parsed, ok = parser_reponse_v1(
        '{"answer": "100 TND", "confidence": "high", "cited_extraits": [1, 3]}'
    )
    assert ok is True
    assert parsed["cited_extraits"] == [1, 3]


def test_parser_reponse_v1_sans_cited_extraits_retourne_parse_ok_false():
    """Le schema V1 impose les 3 cles ; sans cited_extraits ->
    parse_ok=False (meme comportement defensif que B0)."""
    from scripts.evaluate_v1 import parser_reponse_v1

    parsed, ok = parser_reponse_v1(
        '{"answer": "100 TND", "confidence": "high"}'
    )
    assert ok is False
    assert parsed is None


def test_parser_reponse_v1_cited_extraits_mauvais_type():
    """cited_extraits doit etre une liste d'entiers."""
    from scripts.evaluate_v1 import parser_reponse_v1

    # Liste de strings.
    parsed, ok = parser_reponse_v1(
        '{"answer": "x", "confidence": "high", "cited_extraits": ["1"]}'
    )
    assert ok is False
    # Pas une liste.
    parsed, ok = parser_reponse_v1(
        '{"answer": "x", "confidence": "high", "cited_extraits": 1}'
    )
    assert ok is False


# ---------------------------------------------------------------------------
# 5. Pipeline complet : encoder + collection + LLM
# ---------------------------------------------------------------------------
def test_generer_reponse_v1_appelle_bien_llm_avec_contexte_et_schema():
    from bilanlens.prompts import JSON_SCHEMA_REPONSE_V1, SYSTEM_INSTRUCTION
    from scripts.evaluate_v1 import generer_reponse_v1

    coll = FakeCollection(_result_chroma_simule(k=3))
    enc = FakeEncoder()
    llm = FakeLLM(
        '{"answer": "100 TND", "confidence": "high", "cited_extraits": [1]}'
    )

    reponse, retrieved, contexte = generer_reponse_v1(
        llm, enc, coll, "Quel est le CA ?", top_k=3,
    )

    # Chroma a bien ete appele avec n_results=3.
    assert coll.appels[0]["n_results"] == 3
    # Le LLM a recu le schema V1 + SYSTEM_INSTRUCTION strict (meme que B0).
    assert llm.appels[0]["response_schema"] == JSON_SCHEMA_REPONSE_V1
    assert llm.appels[0]["system"] == SYSTEM_INSTRUCTION
    assert llm.appels[0]["temperature"] == 0.0
    # Le prompt utilisateur contient la question ET le contexte formate.
    assert "Quel est le CA ?" in llm.appels[0]["prompt"]
    assert "=== Extrait 1 :" in llm.appels[0]["prompt"]
    # retrieved et contexte retournes aussi.
    assert len(retrieved) == 3
    assert contexte.startswith("=== Extrait 1 :")


# ---------------------------------------------------------------------------
# 6. Format ligne results/v1.jsonl
# ---------------------------------------------------------------------------
def test_ligne_resultat_v1_structure_et_citations_invalides():
    from scripts.evaluate_v1 import (
        ligne_resultat_v1, parser_retrieved,
    )

    retrieved = parser_retrieved(_result_chroma_simule(k=3))
    rep = _FauxResponse(
        text='{"answer": "x", "confidence": "high", "cited_extraits": [1, 7]}'
    )
    # cited=[1, 7], k=3 -> 7 est invalide.
    rec = ligne_resultat_v1(
        question={"id": "q1", "question": "Q ?", "category": "extraction"},
        reponse=rep,
        retrieved=retrieved,
        contexte="dummy context",
        answer_parsed={"answer": "x", "confidence": "high",
                       "cited_extraits": [1, 7]},
        parse_ok=True,
        run_id="v1_run_abc",
        prompt_version="deadbeef",
        top_k=3,
    )

    assert rec["run_id"] == "v1_run_abc"
    assert rec["top_k"] == 3
    assert rec["cited_invalides"] == [7]
    # retrieved stocke SANS les textes (trop volumineux).
    assert "texte" not in rec["retrieved"][0]
    assert rec["retrieved"][0]["chunk_id"] == "doc_a_p1_s0"
    assert rec["context_rendered_chars"] == len("dummy context")


# ---------------------------------------------------------------------------
# 7. Dispatch run_id V1
# ---------------------------------------------------------------------------
def test_run_id_defaut_v1_distinct_de_b0_et_inclut_top_k():
    """Trois axes dans le run_id V1 : prefixe `v1_`, modele, top_k.

    `top_k` est OBLIGATOIRE : sans lui, `lire_checkpoint` ferait
    sauter 31 Q deja faites a k=5 lors d'un futur run a k=10. Chaque
    axe qui change le resultat doit vivre dans l'ID.
    """
    from scripts.evaluate_b0 import run_id_defaut as run_id_defaut_b0
    from scripts.evaluate_v1 import run_id_defaut_v1

    rid_b0 = run_id_defaut_b0("gemini-3.5-flash-lite", "abc")
    rid_v1_k5 = run_id_defaut_v1("gemini-3.5-flash-lite", "abc", top_k=5)
    rid_v1_k10 = run_id_defaut_v1("gemini-3.5-flash-lite", "abc", top_k=10)

    assert rid_b0 != rid_v1_k5
    assert rid_b0.startswith("b0_")
    assert rid_v1_k5.startswith("v1_")
    # top_k doit changer l'ID.
    assert rid_v1_k5 != rid_v1_k10
    assert "k5" in rid_v1_k5
    assert "k10" in rid_v1_k10


def test_pages_attendues_calcul_multi_page():
    """Pour un calcul (intermediate_values), toutes les pages des
    valeurs intermediaires doivent etre dans l'ensemble des pages
    attendues. Pas uniquement `evidence_page_physical`."""
    from scripts.evaluate_v1 import pages_attendues

    q = {
        "evidence_doc": "real_ciments_bizerte_2024.pdf",
        "evidence_page_physical": 4,
        "calculation": {
            "intermediate_values": {
                "resultat_net": {"evidence_page_physical": 4},
                "total_actif": {"evidence_page_physical": 2},
            }
        },
    }
    pages = pages_attendues(q)
    assert pages == {("ciments_bizerte_2024", 4),
                     ("ciments_bizerte_2024", 2)}


def test_pages_attendues_extraction_simple():
    """Sans `intermediate_values`, la page attendue est
    `evidence_page_physical`."""
    from scripts.evaluate_v1 import pages_attendues

    q = {
        "evidence_doc": "real_sotuver_2024.pdf",
        "evidence_page_physical": 4,
    }
    assert pages_attendues(q) == {("sotuver_2024", 4)}


def test_pages_attendues_sans_reponse_vide():
    """Question `sans_reponse` : pas de page attendue -> set vide."""
    from scripts.evaluate_v1 import pages_attendues

    q = {
        "category": "sans_reponse",
        "evidence_doc": "real_sotuver_2024.pdf",
        "evidence_page_physical": None,
    }
    assert pages_attendues(q) == set()


def test_pages_attendues_sans_reponse_meme_avec_page_renseignee():
    """Defense en profondeur : meme si le benchmark renseigne par
    erreur un `evidence_page_physical` pour une Q `sans_reponse`, le
    court-circuit par categorie doit l'emporter et renvoyer un
    ensemble vide. Une Q sans_reponse n'entre JAMAIS dans le calcul
    du recall : la bonne reponse est l'abstention, pas une page."""
    from scripts.evaluate_v1 import pages_attendues

    q = {
        "category": "sans_reponse",
        "evidence_doc": "real_sotuver_2024.pdf",
        "evidence_page_physical": 4,  # ne doit PAS etre pris en compte
    }
    assert pages_attendues(q) == set()


def test_recall_ok_calcul_multi_page_une_page_manquante_ko():
    """Un calcul avec 2 pages attendues et seulement 1 retrouvee ->
    recall KO (protocole §3.1 : TOUTES les pages requises)."""
    from scripts.evaluate_v1 import recall_ok

    q = {
        "evidence_doc": "real_ciments_bizerte_2024.pdf",
        "calculation": {
            "intermediate_values": {
                "a": {"evidence_page_physical": 4},
                "b": {"evidence_page_physical": 2},
            }
        },
    }
    # Seule la page 2 est retrouvee ; la 4 manque.
    retrieved = [{"doc": "ciments_bizerte_2024", "page_physique": 2}]
    assert recall_ok(q, retrieved) is False
    # Les deux pages retrouvees -> OK.
    retrieved2 = [
        {"doc": "ciments_bizerte_2024", "page_physique": 2},
        {"doc": "ciments_bizerte_2024", "page_physique": 4},
    ]
    assert recall_ok(q, retrieved2) is True


def test_recall_ok_sans_reponse_renvoie_none():
    """Les questions `sans_reponse` sont hors metrique recall."""
    from scripts.evaluate_v1 import recall_ok

    q = {"evidence_doc": "real_sotuver_2024.pdf",
         "evidence_page_physical": None}
    assert recall_ok(q, [{"doc": "sotuver_2024", "page_physique": 1}]) is None
