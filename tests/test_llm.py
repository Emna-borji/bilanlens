"""Tests de la couche d'abstraction LLM (bilanlens/llm.py).

- Dataclass : auto-descriptive et immuable.
- Protocol : `isinstance(adapter, LLM)` grâce à `@runtime_checkable`.
- Happy path mocké : la réponse mockée est bien emballée en LLMResponse.
- Backoff : un 429 suivi d'un succès (réessayer), un 403 (remonter
  immédiatement), tous 429 (lever `ErreurQuotaDepassee`, 4 attentes
  entre 5 tentatives, délais [2, 4, 8, 16]).
- Factory : erreur sur fournisseur inconnu.
- Appel réel (marker `network`) : ignoré par défaut, lancé avec
  `pytest -m network`. Nécessite `GEMINI_API_KEY` dans `.env`.
"""
import os
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

from bilanlens.llm import (
    ErreurQuotaDepassee,
    GeminiLLM,
    LLM,
    LLMResponse,
    creer_llm,
)

# Charge .env au moment de l'import du module de tests pour que les
# décorateurs @pytest.mark.skipif voient `GEMINI_API_KEY` avant la
# collection. Sur CI (pas de .env), c'est un no-op silencieux.
load_dotenv()


def _fake_client_error(code: int):
    """Fabrique un faux `errors.ClientError` sans passer par son
    constructeur (dont la signature peut changer entre versions)."""
    from google.genai import errors
    err = errors.ClientError.__new__(errors.ClientError)
    err.code = code
    err.message = f"Erreur simulee {code}"
    err.args = (err.message,)
    err.status = "RESOURCE_EXHAUSTED" if code == 429 else "ERREUR"
    return err


def _geminillm_mocke(model: str = "gemini-3.5-flash") -> GeminiLLM:
    """Instance de GeminiLLM sans passer par __init__ (pas de clé requise)."""
    inst = GeminiLLM.__new__(GeminiLLM)
    inst._api_key = "cle-test"
    inst._model = model
    inst._client = MagicMock()
    return inst


# ---------------------------------------------------------------------------
# 1. Dataclass auto-descriptive
# ---------------------------------------------------------------------------
def test_llm_response_est_une_dataclass_auto_descriptive():
    r = LLMResponse(
        text="42",
        model="gemini-3.5-flash",
        provider="gemini",
        temperature=0.0,
        latency_s=1.23,
    )
    assert r.text == "42"
    assert r.model == "gemini-3.5-flash"
    assert r.provider == "gemini"
    assert r.temperature == 0.0
    assert r.latency_s == 1.23


def test_llm_response_est_immuable():
    """`frozen=True` empêche toute modification a posteriori."""
    r = LLMResponse(
        text="x", model="m", provider="p", temperature=0.0, latency_s=0.1,
    )
    with pytest.raises(Exception):
        r.text = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 2. Protocol runtime_checkable
# ---------------------------------------------------------------------------
def test_gemini_llm_respecte_le_protocol_llm():
    """`@runtime_checkable` autorise `isinstance(inst, LLM)` par duck
    typing (présence de la méthode `generate`)."""
    inst = _geminillm_mocke()
    assert isinstance(inst, LLM)


# ---------------------------------------------------------------------------
# 3. Happy path mocké
# ---------------------------------------------------------------------------
def test_gemini_llm_generate_construit_une_llm_response():
    inst = _geminillm_mocke()
    reponse_mockee = MagicMock()
    reponse_mockee.text = "Resultat net = 42"
    reponse_mockee.model_version = "gemini-3.5-flash-001"
    inst._client.models.generate_content.return_value = reponse_mockee

    result = inst.generate("Quel est le resultat net ?", temperature=0.0)

    assert isinstance(result, LLMResponse)
    assert result.text == "Resultat net = 42"
    # Version pinnee reellement servie par l'API (ex. -001)
    assert result.model == "gemini-3.5-flash-001"
    assert result.provider == "gemini"
    assert result.temperature == 0.0
    assert result.latency_s >= 0


# ---------------------------------------------------------------------------
# 4. Backoff
# ---------------------------------------------------------------------------
@patch("bilanlens.llm.time.sleep")
def test_gemini_llm_backoff_429_puis_succes(mock_sleep):
    """Un 429 au 1er appel, succes au 2e. L'adapter reessaie et renvoie
    la reponse ; une seule attente a 2,0 s entre les deux tentatives."""
    inst = _geminillm_mocke()
    reponse_ok = MagicMock(text="ok", model_version="gemini-3.5-flash-001")
    inst._client.models.generate_content.side_effect = [
        _fake_client_error(429),
        reponse_ok,
    ]

    result = inst.generate("test")

    assert result.text == "ok"
    assert inst._client.models.generate_content.call_count == 2
    mock_sleep.assert_called_once_with(2.0)


@patch("bilanlens.llm.time.sleep")
def test_gemini_llm_403_remonte_immediatement(mock_sleep):
    """Une erreur != 429 (ex. 403 cle invalide) remonte sans reessayer."""
    from google.genai import errors
    inst = _geminillm_mocke()
    inst._client.models.generate_content.side_effect = _fake_client_error(403)

    with pytest.raises(errors.ClientError):
        inst.generate("test")

    assert inst._client.models.generate_content.call_count == 1
    mock_sleep.assert_not_called()


@patch("bilanlens.llm.time.sleep")
def test_gemini_llm_quota_epuise_leve_erreur_quota_depassee(mock_sleep):
    """5 x 429 → `ErreurQuotaDepassee` ; 4 attentes [2, 4, 8, 16] s
    (pas d'attente apres la derniere tentative)."""
    inst = _geminillm_mocke()
    inst._client.models.generate_content.side_effect = [
        _fake_client_error(429) for _ in range(5)
    ]

    with pytest.raises(ErreurQuotaDepassee):
        inst.generate("test")

    assert inst._client.models.generate_content.call_count == 5
    assert mock_sleep.call_count == 4
    delais = [c.args[0] for c in mock_sleep.call_args_list]
    assert delais == [2.0, 4.0, 8.0, 16.0]


# ---------------------------------------------------------------------------
# 5. Factory
# ---------------------------------------------------------------------------
def test_creer_llm_leve_sur_fournisseur_inconnu():
    with pytest.raises(ValueError, match="inconnu"):
        creer_llm(provider="inexistant")


# ---------------------------------------------------------------------------
# 6. Appel reel (marker network)
# ---------------------------------------------------------------------------
@pytest.mark.network
@pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY absente (CI sans secret ou .env vide)",
)
def test_gemini_llm_appel_reel():
    """Appel reel a Gemini. Lancer avec `pytest -m network`.
    Necessite `GEMINI_API_KEY` dans `.env` ou dans l'environnement."""
    llm = GeminiLLM(model="gemini-3.5-flash")
    r = llm.generate(
        "Reponds par un unique mot : ok. Rien d'autre.",
        temperature=0.0,
    )
    assert r.text
    assert r.provider == "gemini"
    assert r.model
    assert r.temperature == 0.0
    assert r.latency_s > 0
