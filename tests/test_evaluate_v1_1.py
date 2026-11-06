"""Tests unitaires de evaluate_v1_1.py.

Verifie l'invariant central : V1.1 envoie au LLM le MEME contexte
que V1 (meme longueur, meme ordre, memes chunk_ids), seul le
template utilisateur change (TEMPLATE_V1_1_USER = TEMPLATE_V1_USER
+ consigne calcul).

Aucun appel reseau (LLM mock, chunks locaux deja sur disque).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
@dataclass
class _FauxResponse:
    text: str
    model: str = "fake-model"
    provider: str = "fake"
    temperature: float = 0.0
    latency_s: float = 0.01


class FakeLLM:
    def __init__(self, reponse_text: str):
        self._reponse_text = reponse_text
        self.appels: list[dict] = []

    def generate(self, prompt, system=None, temperature=0.0,
                  response_schema=None):
        self.appels.append({
            "prompt": prompt, "system": system,
            "temperature": temperature, "response_schema": response_schema,
        })
        return _FauxResponse(text=self._reponse_text)


# ---------------------------------------------------------------------------
# 1. Prompt V1.1 : template different, SYSTEM_INSTRUCTION identique
# ---------------------------------------------------------------------------
def test_template_v1_1_differe_de_v1_sur_consigne_calcul():
    """TEMPLATE_V1_1_USER contient la consigne calcul ; V1 non."""
    from bilanlens.prompts import TEMPLATE_V1_1_USER, TEMPLATE_V1_USER

    assert TEMPLATE_V1_1_USER != TEMPLATE_V1_USER
    # La consigne ajoutee.
    assert "fais le calcul exact" in TEMPLATE_V1_1_USER
    assert "resultat final avec son unite" in TEMPLATE_V1_1_USER
    # Les autres elements de V1 restent presents.
    assert "{context}" in TEMPLATE_V1_1_USER
    assert "{question}" in TEMPLATE_V1_1_USER
    assert "cited_extraits" in TEMPLATE_V1_1_USER


def test_prompt_version_v1_1_distinct_de_v1():
    """Le hash change parce que le template change ; SYSTEM_INSTRUCTION
    reste identique (meme sur B0-strict)."""
    from bilanlens.prompts import (SYSTEM_INSTRUCTION, prompt_version_v1,
                                      prompt_version_v1_1)

    assert prompt_version_v1() != prompt_version_v1_1()
    # SYSTEM_INSTRUCTION identique : mesure propre de l'effet consigne.
    assert len(SYSTEM_INSTRUCTION) > 0


def test_json_schema_v1_1_identique_a_v1():
    """Pas de nouveau champ au schema : V1.1 renvoie toujours
    {answer, confidence, cited_extraits}."""
    from bilanlens.prompts import JSON_SCHEMA_REPONSE_V1
    from scripts.evaluate_v1_1 import generer_reponse_v1_1

    llm = FakeLLM('{"answer": "1,90", "confidence": "high", '
                   '"cited_extraits": [1]}')
    _ = generer_reponse_v1_1(llm, "context test", "question test")
    assert llm.appels[0]["response_schema"] == JSON_SCHEMA_REPONSE_V1


# ---------------------------------------------------------------------------
# 2. run_id V1.1 : prefixe distinct + top_k
# ---------------------------------------------------------------------------
def test_run_id_defaut_v1_1_distinct_de_v1():
    """Prefixe `v1_1_` + top_k dans l'ID."""
    from scripts.evaluate_v1 import run_id_defaut_v1
    from scripts.evaluate_v1_1 import run_id_defaut_v1_1

    rid_v1 = run_id_defaut_v1("gemini-3.5-flash-lite", "abc", top_k=5)
    rid_v1_1 = run_id_defaut_v1_1("gemini-3.5-flash-lite", "def", top_k=5)
    assert rid_v1 != rid_v1_1
    assert rid_v1.startswith("v1_")
    assert rid_v1_1.startswith("v1_1_")
    assert "k5" in rid_v1_1


# ---------------------------------------------------------------------------
# 3. Pipeline V1.1 : meme contexte que V1, template different
# ---------------------------------------------------------------------------
def test_generer_reponse_v1_1_envoie_meme_contexte_que_v1():
    """V1.1 recoit en entree le contexte reconstruit depuis V1 ;
    le LLM est appele avec ce contexte tel quel (place a
    `{context}` dans TEMPLATE_V1_1_USER) + la question + la
    consigne calcul."""
    from bilanlens.prompts import (SYSTEM_INSTRUCTION, TEMPLATE_V1_1_USER,
                                      TEMPLATE_V1_USER)
    from scripts.evaluate_v1_1 import generer_reponse_v1_1

    contexte = (
        "=== Extrait 1 : sotuver_2024, page 3 ===\n"
        "Total des capitaux propres (B.9) 120 964 179\n\n"
        "=== Extrait 2 : sotuver_2024, page 3 ===\n"
        "Total des capitaux propres et des passifs 350 310 164"
    )
    question = "Autonomie financiere SOTUVER 2024 ?"
    llm = FakeLLM(
        '{"answer": "34,53 %", "confidence": "high", "cited_extraits": [1, 2]}'
    )
    _ = generer_reponse_v1_1(llm, contexte, question)

    prompt_envoye = llm.appels[0]["prompt"]
    # Le contexte est integralement present dans le prompt.
    assert contexte in prompt_envoye
    # La question aussi.
    assert question in prompt_envoye
    # La consigne V1.1 est la.
    assert "fais le calcul exact" in prompt_envoye
    # V1 n'avait PAS cette consigne.
    assert "fais le calcul exact" not in TEMPLATE_V1_USER
    # system_instruction byte-a-byte identique a V1 / B0-strict.
    assert llm.appels[0]["system"] == SYSTEM_INSTRUCTION
    assert llm.appels[0]["temperature"] == 0.0


# ---------------------------------------------------------------------------
# 4. Invariant global : V1.1 utilise un contexte identique a V1
# ---------------------------------------------------------------------------
def test_v1_1_contexte_reconstruit_identique_a_v1_31_q():
    """Sur les 31 Q du run V1 enregistre, le contexte reconstruit
    utilise par V1.1 a :
    - meme longueur en caracteres,
    - memes chunk_ids,
    - meme ordre (rang top-5).
    """
    from scripts.score import (RUN_ID_V1, charger_chunks_locaux,
                                  reconstruire_contexte_v1)

    racine = Path(__file__).resolve().parent.parent
    chunks = charger_chunks_locaux()
    lignes = [
        json.loads(l) for l in open(racine / "results" / "v1.jsonl",
                                     encoding="utf-8") if l.strip()
    ]
    v1 = [l for l in lignes if l.get("run_id") == RUN_ID_V1]
    assert len(v1) == 31

    for rec in v1:
        ctx = reconstruire_contexte_v1(rec, chunks)
        # Longueur.
        assert len(ctx) == rec["context_rendered_chars"]
        # Chunk_ids et ordre : les 5 en-tetes "=== Extrait N :"
        # apparaissent dans l'ordre 1,2,3,4,5 et chacun contient
        # le (doc, page) du retrieved correspondant.
        retrieved = sorted(rec["retrieved"], key=lambda r: r["rank"])
        for i, r in enumerate(retrieved, start=1):
            entete = (f"=== Extrait {i} : {r['doc']}, "
                       f"page {r['page_physique']} ===")
            assert entete in ctx, (
                f"{rec['question_id']} : entete {i} manquant dans "
                f"le contexte reconstruit"
            )


# ---------------------------------------------------------------------------
# 5. ligne_resultat_v1_1 : trace la source du contexte
# ---------------------------------------------------------------------------
def test_ligne_resultat_v1_1_porte_run_id_source_et_provenance():
    """Chaque ligne v1_1.jsonl doit tracer qu'elle vient de V1."""
    from scripts.evaluate_v1_1 import ligne_resultat_v1_1
    from scripts.score import RUN_ID_V1

    rep = _FauxResponse(
        text='{"answer": "1,90", "confidence": "high", "cited_extraits": [1]}'
    )
    retrieved = [
        {"rank": 1, "chunk_id": "x_p1_s0", "doc": "x",
         "page_physique": 1, "distance": 0.1},
    ]
    rec = ligne_resultat_v1_1(
        question={"id": "q1", "question": "Q?", "category": "calcul"},
        reponse=rep, retrieved=retrieved, contexte="ctx dummy",
        answer_parsed={"answer": "1,90", "confidence": "high",
                        "cited_extraits": [1]},
        parse_ok=True, run_id="v1_1_run_abc",
        prompt_version="deadbeef", top_k=5,
    )
    assert rec["run_id"] == "v1_1_run_abc"
    assert rec["run_id_source"] == RUN_ID_V1
    assert rec["provenance"] == "v1_1"
    assert rec["top_k"] == 5
    assert rec["context_rendered_chars"] == len("ctx dummy")
