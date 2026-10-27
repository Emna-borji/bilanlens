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


@dataclass(frozen=True)
class LLMResponse:
    """Réponse d'un appel LLM, auto-descriptive pour `results/*.jsonl`.

    Chaque champ est recopié tel quel dans le fichier de résultats pour
    qu'un run puisse être rejoué (ou refait côté scoring) sans relire le
    code de l'époque, dont les valeurs par défaut peuvent avoir changé.
    """
    text: str
    model: str          # version pinnée servie, ex. "gemini-2.5-flash"
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
    ) -> LLMResponse: ...


class ErreurQuotaDepassee(RuntimeError):
    """Levée quand le quota free tier est épuisé après N tentatives."""


class GeminiLLM:
    """Adapter Gemini (Google AI Studio, free tier).

    La clé API est lue dans la variable `GEMINI_API_KEY`, chargée depuis
    `.env` si présent. Elle n'est JAMAIS incluse dans `LLMResponse`,
    dans les logs ni dans `results/*.jsonl` : elle reste dans l'instance.

    Reproductibilité : `model` doit être une version pinnée (ex.
    `"gemini-2.5-flash"`), pas un alias flottant (`"gemini-flash-latest"`).
    """

    PROVIDER = "gemini"
    DEFAULT_MODEL = "gemini-3.5-flash"

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
    ) -> LLMResponse:
        from google.genai import types

        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system,
        )
        depart = time.perf_counter()
        reponse = self._appel_avec_backoff(prompt, config)
        duree = time.perf_counter() - depart

        texte = getattr(reponse, "text", None) or ""
        # L'API retourne parfois la version pinnée réellement servie
        # (ex. "gemini-2.5-flash-001"), parfois non : fallback sur le
        # modèle demandé.
        version_servie = getattr(reponse, "model_version", None) or self._model

        return LLMResponse(
            text=texte,
            model=version_servie,
            provider=self.PROVIDER,
            temperature=temperature,
            latency_s=duree,
        )

    def _appel_avec_backoff(self, prompt, config, max_tentatives: int = 5):
        """Appel Gemini avec backoff exponentiel sur erreurs de quota (429).

        Attente initiale 2 s, doublée à chaque reprise (2, 4, 8, 16 s).
        Pas d'attente après la dernière tentative. Toute erreur autre
        qu'un 429 (ex. 403 clé invalide, 400 prompt mal formé) se
        propage immédiatement.
        """
        from google.genai import errors

        attente = 2.0
        for tentative in range(max_tentatives):
            try:
                return self._client.models.generate_content(
                    model=self._model, contents=prompt, config=config,
                )
            except errors.ClientError as erreur:
                if erreur.code != 429:
                    raise
                if tentative == max_tentatives - 1:
                    raise ErreurQuotaDepassee(
                        f"Quota Gemini (429) : echec apres {max_tentatives} "
                        f"tentatives."
                    ) from erreur
                time.sleep(attente)
                attente *= 2

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
