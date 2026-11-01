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

# os : permet notamment de vérifier si une clé API existe.
# MagicMock : crée un faux objet qui simule le comportement d'un client Gemini.
# patch : remplace temporairement une fonction réelle par une version simulée.

import os
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

from bilanlens.llm import (
    ErreurQuotaDepassee,
    ErreurQuotaJournalier,
    GeminiLLM,
    LLM,
    LLMResponse,
    creer_llm,
)

# Charge .env au moment de l'import du module de tests pour que les
# décorateurs @pytest.mark.skipif voient `GEMINI_API_KEY` avant la
# collection. Sur CI (pas de .env), c'est un no-op silencieux.
load_dotenv()


def _fake_client_error(code: int, retry_delay_s: int | None = None):
    """Fabrique un faux `errors.ClientError` sans passer par son
    constructeur (dont la signature peut changer entre versions).

    Si `retry_delay_s` est fourni, pose un attribut `details` au format
    Google RPC (`RetryInfo` avec `retryDelay: 'Ns'`). Permet de simuler
    un 429 RPD (quota journalier) vs un 429 RPM (quota minute)."""
    from google.genai import errors
    err = errors.ClientError.__new__(errors.ClientError)
    err.code = code
    err.message = f"Erreur simulee {code}"
    err.args = (err.message,)
    err.status = "RESOURCE_EXHAUSTED" if code == 429 else "ERREUR"
    if retry_delay_s is not None:
        err.details = [
            {"@type": "type.googleapis.com/google.rpc.Help", "links": []},
            {
                "@type": "type.googleapis.com/google.rpc.RetryInfo",
                "retryDelay": f"{retry_delay_s}s",
            },
        ]
    return err


def _fake_server_error(code: int = 503):
    """Fabrique un faux `errors.ServerError` (500/502/503/504)."""
    from google.genai import errors
    err = errors.ServerError.__new__(errors.ServerError)
    err.code = code
    err.message = f"Erreur serveur simulee {code}"
    err.args = (err.message,)
    err.status = "UNAVAILABLE" if code == 503 else "ERREUR_SERVEUR"
    return err


def _geminillm_mocke(model: str = "gemini-3.5-flash") -> GeminiLLM:
    """Instance de GeminiLLM sans passer par __init__ (pas de clé requise)."""
    # Cela crée uniquement l'objet, sans exécuter son initialisation normale (__init__).

# Pourquoi ? Parce qu'on veut éviter de configurer un véritable client Gemini. On ajoute ensuite manuellement les attributs nécessaires au test :
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
@patch("bilanlens._api_retry.time.sleep")
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


@patch("bilanlens._api_retry.time.sleep")
def test_gemini_llm_403_remonte_immediatement(mock_sleep):
    """Une erreur != 429 (ex. 403 cle invalide) remonte sans reessayer."""
    from google.genai import errors
    inst = _geminillm_mocke()
    inst._client.models.generate_content.side_effect = _fake_client_error(403)

    with pytest.raises(errors.ClientError):
        inst.generate("test")

    assert inst._client.models.generate_content.call_count == 1
    mock_sleep.assert_not_called()


@patch("bilanlens._api_retry.time.sleep")
def test_gemini_llm_backoff_503_puis_succes(mock_sleep):
    """Un 503 (surcharge Google) au 1er appel, succes au 2e. Le
    backoff doit retenter avec le meme delai initial que pour 429."""
    inst = _geminillm_mocke()
    reponse_ok = MagicMock(text="ok", model_version="gemini-3.5-flash-001")
    inst._client.models.generate_content.side_effect = [
        _fake_server_error(503),
        reponse_ok,
    ]

    result = inst.generate("test")

    assert result.text == "ok"
    assert inst._client.models.generate_content.call_count == 2
    mock_sleep.assert_called_once_with(2.0)


@patch("bilanlens._api_retry.time.sleep")
def test_gemini_llm_503_persistant_releve_server_error(mock_sleep):
    """5 x 503 → l'erreur originale `ServerError` est re-levee
    (pas `ErreurQuotaDepassee` : ce n'est pas un quota)."""
    from google.genai import errors
    inst = _geminillm_mocke()
    inst._client.models.generate_content.side_effect = [
        _fake_server_error(503) for _ in range(5)
    ]

    with pytest.raises(errors.ServerError):
        inst.generate("test")

    assert inst._client.models.generate_content.call_count == 5
    assert mock_sleep.call_count == 4
    delais = [c.args[0] for c in mock_sleep.call_args_list]
    assert delais == [2.0, 4.0, 8.0, 16.0]


@patch("bilanlens._api_retry.time.sleep")
def test_gemini_llm_quota_epuise_leve_erreur_quota_depassee(mock_sleep):
    """5 x 429 (sans retryDelay) → `ErreurQuotaDepassee` ; 4 attentes
    [2, 4, 8, 16] s (pas d'attente apres la derniere tentative)."""
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


@patch("bilanlens._api_retry.time.sleep")
def test_gemini_llm_429_rpd_leve_erreur_quota_journalier_immediatement(mock_sleep):
    """Un 429 avec `retryDelay > 60s` (quota journalier) doit lever
    `ErreurQuotaJournalier` IMMEDIATEMENT : zero retry, zero sleep.
    Attendre 15 h dans une boucle de backoff n'a aucun sens."""
    inst = _geminillm_mocke()
    inst._client.models.generate_content.side_effect = [
        _fake_client_error(429, retry_delay_s=56973),  # ~15h49
    ]

    with pytest.raises(ErreurQuotaJournalier) as excinfo:
        inst.generate("test")

    # Le delai est bien recupere depuis l'exception Google.
    assert excinfo.value.retry_delay_s == 56973.0
    # Zero retry : un seul appel API.
    assert inst._client.models.generate_content.call_count == 1
    # Zero sleep : pas d'attente du tout.
    mock_sleep.assert_not_called()


def test_erreur_quota_journalier_herite_de_quota_depassee():
    """`ErreurQuotaJournalier` doit etre un sous-type de
    `ErreurQuotaDepassee` : les `except ErreurQuotaDepassee` existants
    attrapent toujours les deux cas."""
    exc = ErreurQuotaJournalier(retry_delay_s=56973)
    assert isinstance(exc, ErreurQuotaDepassee)
    assert exc.retry_delay_s == 56973.0


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
