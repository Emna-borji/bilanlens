"""Tests unitaires du script evaluate_b0.py.

Couvre les 4 corrections de l'etudiant + l'arret quota journalier :
1. Checkpoint sur (run_id, question_id) : nouveau run_id → toutes
   les questions retraitees.
2. Prompt partage B0/V1 : `prompt_version` enregistre par ligne.
3. JSON strict force cote API + `parse_ok=False` sans crash si invalide.
4. Pas d'outils/grounding : la config LLM ne contient pas `tools` activees.
5. Quota journalier (retryDelay > 60s) : message clair + exit code 2.

Pas de reseau : le LLM est mocke par un `FakeLLM` qui respecte le
Protocol `bilanlens.llm.LLM`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# FakeLLM : respecte le Protocol LLM, trace les kwargs d'appel.
# ---------------------------------------------------------------------------
@dataclass
class _FauxResponse:
    text: str
    model: str = "fake-model-001"
    provider: str = "fake"
    temperature: float = 0.0
    latency_s: float = 0.01


class FakeLLM:
    """Repond ce qu'on lui dit. Enregistre chaque kwarg d'appel."""

    def __init__(self, reponse_text: str = '{"answer": "ok", "confidence": "high"}'):
        self._reponse_text = reponse_text
        self.appels: list[dict] = []

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.0,
        response_schema: dict | None = None,
    ):
        self.appels.append({
            "prompt": prompt,
            "system": system,
            "temperature": temperature,
            "response_schema": response_schema,
        })
        return _FauxResponse(text=self._reponse_text)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _question(id_: str, texte: str = "Q ?", cat: str = "extraction") -> dict:
    return {"id": id_, "question": texte, "category": cat}


# ---------------------------------------------------------------------------
# 1. Checkpoint sur (run_id, question_id)
# ---------------------------------------------------------------------------
def test_checkpoint_filtre_par_run_id(tmp_path):
    """Un run_id different doit retraiter TOUTES les questions,
    meme si elles sont presentes sous un autre run_id."""
    from scripts.evaluate_b0 import append_jsonl, lire_checkpoint

    path = tmp_path / "b0.jsonl"
    # Ancien run : Q01 et Q02 deja faites sous "runA".
    append_jsonl(path, {"run_id": "runA", "question_id": "Q01"})
    append_jsonl(path, {"run_id": "runA", "question_id": "Q02"})

    deja_a = lire_checkpoint(path, "runA")
    deja_b = lire_checkpoint(path, "runB")
    assert deja_a == {"Q01", "Q02"}
    assert deja_b == set(), (
        "Changement de run_id doit faire oublier les lignes "
        "d'anciens run_id, sinon un nouveau prompt saute tout"
    )


def test_checkpoint_ignore_lignes_cassees(tmp_path):
    from scripts.evaluate_b0 import lire_checkpoint

    path = tmp_path / "b0.jsonl"
    path.write_text(
        '{"run_id": "r", "question_id": "Q01"}\n'
        'ceci-nest-pas-du-json\n'
        '{"run_id": "r", "question_id": "Q02"}\n',
        encoding="utf-8",
    )
    assert lire_checkpoint(path, "r") == {"Q01", "Q02"}


# ---------------------------------------------------------------------------
# 2. Prompt partage B0/V1 + prompt_version
# ---------------------------------------------------------------------------
def test_prompt_version_b0_v1_different_quand_template_differe():
    """B0 et V1 n'ont PAS le meme prompt_version : si une regression
    les faisait partager le meme template, ce test tombe."""
    from bilanlens.prompts import prompt_version_b0, prompt_version_v1

    assert prompt_version_b0() != prompt_version_v1()
    # Format : hash hex court.
    assert len(prompt_version_b0()) == 16
    assert all(c in "0123456789abcdef" for c in prompt_version_b0())


def test_prompt_version_change_quand_regles_changent(monkeypatch):
    """Modifier `SYSTEM_INSTRUCTION` doit changer le hash. Garde-fou
    pour qu'une re-ecriture des regles invalide le checkpoint."""
    from bilanlens import prompts

    v_initial = prompts.prompt_version_b0()
    monkeypatch.setattr(prompts, "SYSTEM_INSTRUCTION", "autres regles")
    v_modifie = prompts.prompt_version_b0()
    assert v_initial != v_modifie


def test_system_instruction_identique_pour_b0_et_v1():
    """Les deux templates partagent le MEME `SYSTEM_INSTRUCTION` :
    seul le template utilisateur differe (contexte RAG en V1)."""
    from bilanlens.prompts import SYSTEM_INSTRUCTION, TEMPLATE_B0_USER, TEMPLATE_V1_USER

    assert "{question}" in TEMPLATE_B0_USER
    assert "{question}" in TEMPLATE_V1_USER
    assert "{context}" in TEMPLATE_V1_USER
    assert "{context}" not in TEMPLATE_B0_USER
    assert "donnee non disponible" in SYSTEM_INSTRUCTION


# ---------------------------------------------------------------------------
# 3. JSON schema force + parse_ok
# ---------------------------------------------------------------------------
def test_parser_reponse_json_valide():
    from scripts.evaluate_b0 import parser_reponse

    parsed, ok = parser_reponse('{"answer": "100 TND", "confidence": "high"}')
    assert ok is True
    assert parsed == {"answer": "100 TND", "confidence": "high"}


def test_parser_reponse_json_casse_renvoie_parse_ok_false():
    from scripts.evaluate_b0 import parser_reponse

    parsed, ok = parser_reponse("ceci-nest-pas-du-json")
    assert ok is False
    assert parsed is None


def test_parser_reponse_json_sans_cle_obligatoire():
    """JSON valide mais sans 'confidence' → parse_ok=False."""
    from scripts.evaluate_b0 import parser_reponse

    parsed, ok = parser_reponse('{"answer": "ok"}')
    assert ok is False
    assert parsed is None


def test_generer_reponse_b0_passe_bien_schema_et_system(tmp_path):
    """L'appel LLM doit passer : (a) SYSTEM_INSTRUCTION en system,
    (b) JSON_SCHEMA_REPONSE en response_schema, (c) temperature=0.0."""
    from bilanlens.prompts import JSON_SCHEMA_REPONSE, SYSTEM_INSTRUCTION
    from scripts.evaluate_b0 import generer_reponse_b0

    llm = FakeLLM()
    generer_reponse_b0(llm, "Quel est le CA de SOTUVER 2024 ?")

    assert len(llm.appels) == 1
    appel = llm.appels[0]
    assert appel["system"] == SYSTEM_INSTRUCTION
    assert appel["response_schema"] == JSON_SCHEMA_REPONSE
    assert appel["temperature"] == 0.0
    assert "SOTUVER 2024" in appel["prompt"]


# ---------------------------------------------------------------------------
# 4. Pas d'outils / grounding (correction 4)
# ---------------------------------------------------------------------------
def test_gemini_llm_config_declare_tools_vide(monkeypatch):
    """GenerateContentConfig doit etre instancie avec `tools=[]`
    (liste vide explicite), pour que B0 ne mesure QUE le LLM (pas
    de grounding Google Search ni d'autres outils)."""
    import bilanlens.llm as llm_module

    # Instance sans __init__ (pas de cle requise).
    inst = llm_module.GeminiLLM.__new__(llm_module.GeminiLLM)
    inst._api_key = "cle"
    inst._model = "gemini-fake"
    inst._client = MagicMock()
    reponse_mock = MagicMock()
    reponse_mock.text = '{"answer": "ok", "confidence": "high"}'
    reponse_mock.model_version = "gemini-fake-001"
    inst._client.models.generate_content.return_value = reponse_mock

    # Spy sur GenerateContentConfig pour inspecter ses kwargs.
    kwargs_captures: list[dict] = []
    from google.genai import types

    vrai_config = types.GenerateContentConfig

    def _capturer_config(**kwargs):
        kwargs_captures.append(kwargs)
        return vrai_config(**kwargs)

    monkeypatch.setattr(types, "GenerateContentConfig", _capturer_config)

    inst.generate("test", system="rules", temperature=0.0)

    assert len(kwargs_captures) == 1
    # Le point cle : tools=[] est bien passe, meme sans response_schema.
    assert kwargs_captures[0].get("tools") == []


# ---------------------------------------------------------------------------
# 5. Format de la ligne de resultat
# ---------------------------------------------------------------------------
def test_ligne_resultat_contient_run_id_et_prompt_version():
    """Chaque ligne de b0.jsonl doit porter run_id ET prompt_version :
    sinon la reprise par (run_id, question_id) n'est pas possible."""
    from scripts.evaluate_b0 import ligne_resultat

    rep = _FauxResponse(text='{"answer": "100 TND", "confidence": "high"}')
    rec = ligne_resultat(
        question=_question("Q01", "Q ?"),
        reponse=rep,
        answer_parsed={"answer": "100 TND", "confidence": "high"},
        parse_ok=True,
        run_id="b0_run_abc",
        prompt_version="deadbeef12345678",
    )
    assert rec["run_id"] == "b0_run_abc"
    assert rec["prompt_version"] == "deadbeef12345678"
    assert rec["question_id"] == "Q01"
    assert rec["temperature"] == 0.0
    assert rec["model"] == "fake-model-001"
    assert rec["answer_parsed"] == {"answer": "100 TND", "confidence": "high"}
    assert rec["parse_ok"] is True
    assert "timestamp" in rec


def test_ligne_resultat_parse_ko_garde_answer_raw():
    """`parse_ok=False` ne doit pas perdre `answer_raw` : la trace
    exacte du modele reste dans le fichier pour debug ulterieur."""
    from scripts.evaluate_b0 import ligne_resultat

    rep = _FauxResponse(text="texte brut non-JSON")
    rec = ligne_resultat(
        question=_question("Q01"),
        reponse=rep,
        answer_parsed=None,
        parse_ok=False,
        run_id="r",
        prompt_version="v",
    )
    assert rec["answer_raw"] == "texte brut non-JSON"
    assert rec["answer_parsed"] is None
    assert rec["parse_ok"] is False


# ---------------------------------------------------------------------------
# 6. Boucle complete bout-en-bout (mocke)
# ---------------------------------------------------------------------------
def test_append_jsonl_puis_rechargeable(tmp_path):
    from scripts.evaluate_b0 import append_jsonl, lire_checkpoint

    path = tmp_path / "b0.jsonl"
    for qid in ("Q01", "Q02", "Q03"):
        append_jsonl(path, {"run_id": "r", "question_id": qid, "answer_raw": "x"})
    assert lire_checkpoint(path, "r") == {"Q01", "Q02", "Q03"}
    # Les lignes sont bien du JSON valide.
    with path.open(encoding="utf-8") as f:
        for ligne in f:
            json.loads(ligne)


# ---------------------------------------------------------------------------
# 7. Message d'arret quota journalier (RPD)
# ---------------------------------------------------------------------------
def test_message_arret_quota_journalier_format():
    """Le message d'arret doit nommer : (a) X/N faits, (b) duree en
    h/min, (c) heure Tunis de reprise. `maintenant` injecte pour que
    le test ne depende pas de l'horloge."""
    from scripts.evaluate_b0 import message_arret_quota_journalier

    # Faux "maintenant" : 2026-11-01 09:00 UTC = 10:00 Tunis.
    maintenant = datetime(2026, 11, 1, 9, 0, 0, tzinfo=timezone.utc)
    # Google indique "retry dans 56973s" (~ 15h49).
    msg = message_arret_quota_journalier(
        nb_faits=18, total=31, retry_delay_s=56973, maintenant=maintenant,
    )

    assert "18/31" in msg
    assert "15 h" in msg
    assert "49 min" in msg
    # 09:00 UTC + 56973 s (~15h49m33s) = 00:49 UTC le 2 nov.
    # +1h Tunis = 01:49 Tunis le 2 nov.
    assert "2026-11-02 01:49" in msg
    assert "Tunis" in msg
    assert "checkpoint" in msg.lower()


def test_message_arret_quota_journalier_delai_court():
    """Un retry de 90 s (anormal mais possible) : 0 h 01 min.
    Verifie l'absence de bugs de formatage sur petits delais."""
    from scripts.evaluate_b0 import message_arret_quota_journalier

    maintenant = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
    msg = message_arret_quota_journalier(
        nb_faits=5, total=31, retry_delay_s=90, maintenant=maintenant,
    )
    assert "5/31" in msg
    assert "0 h 01 min" in msg


def test_exit_code_quota_journalier_est_2():
    """Convention locale : exit code 2 pour quota journalier,
    distinct de 1 (erreur fatale) et 0 (succes). Documente ici pour
    qu'un wrapper CI puisse se baser dessus."""
    from scripts.evaluate_b0 import EXIT_CODE_QUOTA_JOURNALIER

    assert EXIT_CODE_QUOTA_JOURNALIER == 2


# ---------------------------------------------------------------------------
# 8. Slug modele + run_id default (bascule gemini-3.6-flash -> Flash-Lite)
# ---------------------------------------------------------------------------
def test_slug_modele_enleve_tirets_et_points():
    """`gemini-3.5-flash-lite` -> `gemini35flashlite`.
    Permet d'inclure le nom dans un run_id sans caracteres surprenants."""
    from scripts.evaluate_b0 import slug_modele

    assert slug_modele("gemini-3.5-flash-lite") == "gemini35flashlite"
    assert slug_modele("gemini-3.6-flash") == "gemini36flash"
    # Deja un slug : idempotent.
    assert slug_modele("gemini35flashlite") == "gemini35flashlite"


def test_run_id_defaut_inclut_le_modele():
    """Deux modeles differents sous le MEME prompt_version doivent
    produire deux run_id differents : sinon on melangerait leurs
    reponses dans le meme fichier results."""
    from scripts.evaluate_b0 import run_id_defaut

    rid_flash = run_id_defaut("gemini-3.6-flash", "abc123")
    rid_lite = run_id_defaut("gemini-3.5-flash-lite", "abc123")
    assert rid_flash != rid_lite
    assert rid_flash == "b0_gemini36flash_abc123"
    assert rid_lite == "b0_gemini35flashlite_abc123"


def test_run_id_defaut_change_quand_prompt_version_change():
    """Changement de prompt sous le MEME modele -> nouveau run_id
    (meme garantie que l'ancien default `b0_<prompt_version>`)."""
    from scripts.evaluate_b0 import run_id_defaut

    rid_v1 = run_id_defaut("gemini-3.5-flash-lite", "aaa")
    rid_v2 = run_id_defaut("gemini-3.5-flash-lite", "bbb")
    assert rid_v1 != rid_v2


# ---------------------------------------------------------------------------
# 9. Variante B0-libre (prompt diagnostique sans abstention)
# ---------------------------------------------------------------------------
def test_prompt_version_b0_strict_et_libre_different():
    """Les deux variantes DOIVENT produire des hash differents : si
    elles sont egaux, un run libre et un run strict partageraient le
    meme run_id par defaut et melangeraient leurs reponses."""
    from bilanlens.prompts import (
        prompt_version_b0_libre,
        prompt_version_b0_strict,
    )

    assert prompt_version_b0_strict() != prompt_version_b0_libre()


def test_system_instruction_b0_libre_ne_contient_pas_abstention():
    """La variante libre doit ETRE DEBARRASSEE de la consigne
    d'abstention. Si demain quelqu'un la reintroduit, ce test tombe."""
    from bilanlens.prompts import SYSTEM_INSTRUCTION_B0_LIBRE

    assert "donnee non disponible" not in SYSTEM_INSTRUCTION_B0_LIBRE
    # Mais le format JSON doit rester identique.
    assert '"answer"' in SYSTEM_INSTRUCTION_B0_LIBRE
    assert '"confidence"' in SYSTEM_INSTRUCTION_B0_LIBRE


def test_run_id_defaut_variante_libre_a_prefixe_distinct():
    """`strict` -> `b0_...`, `libre` -> `b0libre_...`. Sous le MEME
    modele et le MEME prompt_version, les deux ne doivent PAS collisionner."""
    from scripts.evaluate_b0 import run_id_defaut

    rid_strict = run_id_defaut("gemini-3.5-flash-lite", "abc", "strict")
    rid_libre = run_id_defaut("gemini-3.5-flash-lite", "abc", "libre")
    assert rid_strict.startswith("b0_")
    assert rid_libre.startswith("b0libre_")
    assert rid_strict != rid_libre


def test_est_reponse_abstentive_cas_classiques():
    """Robuste aux variantes typographiques courantes."""
    from scripts.evaluate_b0 import est_reponse_abstentive

    # Cas franchement abstentifs.
    assert est_reponse_abstentive("donnee non disponible")
    assert est_reponse_abstentive("Donnee non disponible")
    assert est_reponse_abstentive("donnée non disponible")
    assert est_reponse_abstentive('"donnee non disponible"')
    assert est_reponse_abstentive("donnee non disponible.")
    assert est_reponse_abstentive("")
    # Cas chiffres (pas abstentifs).
    assert not est_reponse_abstentive("100 836 224 TND")
    assert not est_reponse_abstentive("34,53 %")
    # Phrase contenant mais pas uniquement l'abstention.
    assert not est_reponse_abstentive(
        "La donnee non disponible dans le rapport est le CA 2024."
    )
