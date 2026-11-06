"""Tests V1.2 : V1.1 + deux regles anti-ambiguite.

Invariant central : V1.2 utilise le MEME contexte que V1
(reconstruit depuis V1 + chunks locaux, sans Chroma ni API
embeddings). Seul le template utilisateur change.
"""
from __future__ import annotations

from dataclasses import dataclass


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


def test_template_v1_2_contient_les_deux_regles():
    """TEMPLATE_V1_2_USER contient les 2 regles issues de l'analyse
    post-hoc de V1.1 : 'total passif = total du bilan' et
    'indique le sens' pour les variations."""
    from bilanlens.prompts import TEMPLATE_V1_2_USER

    # Regle 1 : definition du total passif.
    assert "total passif" in TEMPLATE_V1_2_USER
    assert "capitaux propres et des passifs" in TEMPLATE_V1_2_USER
    # Regle 2 : sens pour variation/comparaison.
    assert ("augmentation ou diminution" in TEMPLATE_V1_2_USER
             or "augmentation" in TEMPLATE_V1_2_USER)
    assert "variation ou une comparaison" in TEMPLATE_V1_2_USER


def test_template_v1_2_hérite_de_v1_1():
    """V1.2 contient aussi la consigne calcul de V1.1 + cited_extraits."""
    from bilanlens.prompts import TEMPLATE_V1_2_USER

    # Heritages V1.1.
    assert "fais le calcul exact" in TEMPLATE_V1_2_USER
    # Heritages V1.
    assert "{context}" in TEMPLATE_V1_2_USER
    assert "{question}" in TEMPLATE_V1_2_USER
    assert "cited_extraits" in TEMPLATE_V1_2_USER


def test_prompt_version_v1_2_distinct_des_precedents():
    """Les 3 versions coexistent sous des hash differents."""
    from bilanlens.prompts import (prompt_version_v1, prompt_version_v1_1,
                                      prompt_version_v1_2)

    pv_v1 = prompt_version_v1()
    pv_v1_1 = prompt_version_v1_1()
    pv_v1_2 = prompt_version_v1_2()
    assert len({pv_v1, pv_v1_1, pv_v1_2}) == 3


def test_generer_reponse_v1_2_envoie_les_regles_dans_prompt():
    """L'appel LLM contient le contexte, la question et les 2 regles."""
    from bilanlens.prompts import SYSTEM_INSTRUCTION
    from scripts.evaluate_v1_2 import generer_reponse_v1_2

    contexte = (
        "=== Extrait 1 : sotuver_2024, page 3 ===\n"
        "Capitaux propres 120 964 179 et Total capitaux propres "
        "et des passifs 350 310 164"
    )
    question = "Autonomie financiere ?"
    llm = FakeLLM(
        '{"answer": "34,53 %", "confidence": "high", "cited_extraits": [1]}'
    )
    _ = generer_reponse_v1_2(llm, contexte, question)

    prompt = llm.appels[0]["prompt"]
    assert contexte in prompt
    assert question in prompt
    assert "total passif" in prompt
    assert "variation ou une comparaison" in prompt
    assert llm.appels[0]["system"] == SYSTEM_INSTRUCTION


def test_run_id_defaut_v1_2_distinct_de_v1_1():
    """Prefixe `v1_2_` + top_k dans ID."""
    from scripts.evaluate_v1_1 import run_id_defaut_v1_1
    from scripts.evaluate_v1_2 import run_id_defaut_v1_2

    rid_11 = run_id_defaut_v1_1("gemini-3.5-flash-lite", "abc", top_k=5)
    rid_12 = run_id_defaut_v1_2("gemini-3.5-flash-lite", "def", top_k=5)
    assert rid_11 != rid_12
    assert rid_12.startswith("v1_2_")
    assert "k5" in rid_12
