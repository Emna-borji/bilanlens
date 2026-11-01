"""Couche d'abstraction LLM pour BilanLens.

Interface commune `LLM` + adapter(s) pour fournisseur(s) externe(s).
Semaine 2 : adapter Gemini (API gratuite Google AI Studio).
Les scripts d'évaluation (B0, V1, ...) prennent un `LLM` en paramètre
et ne connaissent pas le fournisseur réel.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from dotenv import load_dotenv

# Reexport : ErreurQuotaDepassee et ErreurQuotaJournalier sont
# factorisees dans _api_retry pour etre partagees avec
# bilanlens.embeddings. Les anciens imports continuent de marcher.
from bilanlens._api_retry import (  # noqa: F401
    ErreurQuotaDepassee,
    ErreurQuotaJournalier,
    appeler_avec_backoff,
)


@dataclass(frozen=True)
class LLMResponse:
    """Réponse d'un appel LLM, auto-descriptive pour `results/*.jsonl`.

    Chaque champ est recopié tel quel dans le fichier de résultats pour
    qu'un run puisse être rejoué (ou refait côté scoring) sans relire le
    code de l'époque, dont les valeurs par défaut peuvent avoir changé.
    """
    text: str
    model: str          # version pinnée servie, ex. "gemini-3.6-flash"
    provider: str       # "gemini", "groq", "ollama", ...
    temperature: float  # la température RÉELLEMENT utilisée
    latency_s: float    # temps mesuré côté client


@runtime_checkable
class LLM(Protocol):
    """Interface commune à tous les adapters LLM.

    `@runtime_checkable` permet un `isinstance(adapter, LLM)` qui vérifie
    la présence de la méthode `generate` (duck typing). Pour une garantie
    forte à l'écriture, utiliser mypy ou pyright dans la CI.
    """
    def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.0,
        response_schema: dict | None = None,
    ) -> LLMResponse: ...


class GeminiLLM:
    """Adapter Gemini (Google AI Studio, free tier).

    La clé API est lue dans la variable `GEMINI_API_KEY`, chargée depuis
    `.env` si présent. Elle n'est JAMAIS incluse dans `LLMResponse`,
    dans les logs ni dans `results/*.jsonl` : elle reste dans l'instance.

    Reproductibilité : `model` doit être le nom pinné réellement
    servi (ex. `"gemini-3.6-flash"`), pas un alias flottant
    (`"gemini-flash-latest"`, `"gemini-3.5-flash"` qui est l'alias
    actuel de `gemini-3.6-flash` cote Google). Le nom pinné reste
    valide quand Google promeut le prochain Flash a l'alias.
    """

    PROVIDER = "gemini"
    # Nom pinne reellement servi par Google (verifie via `model_version`
    # dans la reponse). L'alias `gemini-3.5-flash` resout vers
    # `gemini-3.6-flash` depuis l'automne 2026, mais pinner le vrai
    # nom garantit la reproductibilite : si Google promeut
    # `gemini-3.8-flash` a l'alias demain, notre code reste identique.
    DEFAULT_MODEL = "gemini-3.6-flash"

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        load_dotenv()
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self._api_key:
            raise RuntimeError(
                "GEMINI_API_KEY introuvable. Copier .env.example en .env "
                "et y mettre une clé (https://aistudio.google.com/apikey)."
            )
        self._model = model
        # Import tardif : permet aux tests mockés de patcher le module
        # sans que google-genai soit installé.
        from google import genai
        self._client = genai.Client(api_key=self._api_key)

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.0,
        response_schema: dict | None = None,
    ) -> LLMResponse:
        """Appelle le LLM.

        `response_schema` : si fourni, force la sortie en JSON
        conforme au schema (`response_mime_type="application/json"`).
        Reduit drastiquement les reponses mal formees cote scoring.

        **Pas d'outils, pas de grounding** : la config n'active ni
        Google Search, ni code execution, ni function calling. B0
        doit mesurer le LLM SEUL (pas d'acces au web). V1 passera
        son contexte RAG dans le prompt, pas via un outil.
        """
        from google.genai import types

        kwargs: dict = {
            "temperature": temperature,
            "system_instruction": system,
            # Explicite : pas d'outils actives (voir docstring).
            "tools": [],
        }
        if response_schema is not None:
            kwargs["response_mime_type"] = "application/json"
            kwargs["response_schema"] = response_schema
        config = types.GenerateContentConfig(**kwargs)
        depart = time.perf_counter()
        reponse = self._appel_avec_backoff(prompt, config)
        duree = time.perf_counter() - depart

        texte = getattr(reponse, "text", None) or ""
        # L'API retourne la version pinnée réellement servie
        # (ex. "gemini-3.6-flash"), parfois avec suffixe (-001) ;
        # fallback sur le modèle demandé si le champ est absent.
        version_servie = getattr(reponse, "model_version", None) or self._model

        return LLMResponse(
            text=texte,
            model=version_servie,
            provider=self.PROVIDER,
            temperature=temperature,
            latency_s=duree,
        )

    def _appel_avec_backoff(self, prompt, config, max_tentatives: int = 5):
        """Appel Gemini avec backoff exponentiel sur 429.

        Delegation a `appeler_avec_backoff` (bilanlens._api_retry) :
        le meme code de reprise sert aussi pour les embeddings.
        """
        return appeler_avec_backoff(
            lambda: self._client.models.generate_content(
                model=self._model, contents=prompt, config=config,
            ),
            max_tentatives=max_tentatives,
        )

    def list_models(self) -> list[str]:
        """Liste les modèles disponibles pour cette clé.
        À appeler une fois (ex. en REPL) pour choisir une version stable
        et non "preview"."""
        return [m.name for m in self._client.models.list()]


def creer_llm(provider: str = "gemini", model: str | None = None) -> LLM:
    """Factory : retourne un adapter pour un fournisseur donné.

    Fournisseurs connus : `gemini`. Ajouter `ollama` en semaine 7-8.
    """
    if provider == "gemini":
        return GeminiLLM(model=model or GeminiLLM.DEFAULT_MODEL)
    raise ValueError(f"Fournisseur inconnu : '{provider}'")
