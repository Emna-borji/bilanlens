"""Retry partage entre adapters (llm.py, embeddings.py).

Un seul endroit pour :
- `ErreurQuotaDepassee` : 429 RPM (par minute) epuise apres N tentatives.
- `ErreurQuotaJournalier` : 429 RPD (par jour) detecte sur `retryDelay > 60 s`
  dans la reponse Google. **Pas de backoff** : inutile d'attendre 15 h
  dans une boucle. Le script appelant doit stopper proprement, sauver
  le checkpoint, et dire a l'utilisateur quand relancer.
- `appeler_avec_backoff(fn)` : backoff exponentiel sur :
    * `errors.ClientError` 429 RPM (quota minute) ;
    * `errors.ServerError` 5xx (surcharge Google transitoire).
  Delais `[2, 4, 8, 16]` s pour 5 tentatives. Pas d'attente apres
  la derniere tentative.

Issues finales :
- 429 avec `retryDelay > SEUIL_QUOTA_JOURNALIER_S` -> `ErreurQuotaJournalier`
  levee IMMEDIATEMENT (0 retry, 0 sleep).
- 429 RPM persistant -> `ErreurQuotaDepassee` apres N tentatives.
- 5xx persistant -> re-leve l'erreur `ServerError` originale.
- Autre code (403, 400, ...) -> propage immediatement.
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


# Seuil (secondes) au-dela duquel on considere que le quota est
# journalier (RPD) plutot que par minute (RPM) : inutile de reessayer.
SEUIL_QUOTA_JOURNALIER_S = 60.0


class ErreurQuotaDepassee(RuntimeError):
    """Levee quand le quota 429 RPM est epuise apres N tentatives."""


class ErreurQuotaJournalier(ErreurQuotaDepassee):
    """Levee IMMEDIATEMENT sur un 429 avec `retryDelay > 60 s`.

    Porte `retry_delay_s` : le delai (en secondes) annonce par Google.
    Le script appelant peut l'afficher a l'utilisateur et exit avec
    un code dedie (ex. 2 : quota journalier) pour qu'un wrapper CI
    puisse replanifier la relance.

    Herite de `ErreurQuotaDepassee` : les `except ErreurQuotaDepassee`
    existants attrapent toujours les deux cas. Pour distinguer :
    `except ErreurQuotaJournalier` AVANT `except ErreurQuotaDepassee`.
    """

    def __init__(self, retry_delay_s: float, message: str | None = None):
        self.retry_delay_s = float(retry_delay_s)
        super().__init__(
            message
            or f"Quota journalier atteint (retry dans {int(retry_delay_s)} s)."
        )


def _parse_duree_rpc(duree: Any) -> float | None:
    """`'56973s'` -> `56973.0`. Format `google.rpc` : secondes + `s`."""
    if isinstance(duree, (int, float)):
        return float(duree)
    if isinstance(duree, str):
        m = re.match(r"^(\d+(?:\.\d+)?)s?$", duree.strip())
        if m:
            return float(m.group(1))
    return None


def _extract_retry_delay_s(exc: Any) -> float | None:
    """Cherche `retryDelay` dans un `ClientError` 429 de google.genai.

    Format Google RPC :
        details = [..., {'@type': '.../RetryInfo', 'retryDelay': '56973s'}]

    Retourne la duree en secondes ou `None` si introuvable. Robuste a
    plusieurs emplacements possibles selon la version du SDK.
    """
    # 1. Attribut `details` structurel (SDK recent).
    details = getattr(exc, "details", None)
    if isinstance(details, list):
        for item in details:
            if isinstance(item, dict) and "retryDelay" in item:
                return _parse_duree_rpc(item["retryDelay"])

    # 2. `response_json["error"]["details"]` (SDK plus ancien).
    for attr in ("response_json", "_response_json"):
        rj = getattr(exc, attr, None)
        if isinstance(rj, dict):
            det = rj.get("error", {}).get("details", [])
            for item in det:
                if isinstance(item, dict) and "retryDelay" in item:
                    return _parse_duree_rpc(item["retryDelay"])

    # 3. Regex sur le texte de l'exception (fallback de derniere chance).
    m = re.search(r"['\"]retryDelay['\"]\s*:\s*['\"](\d+(?:\.\d+)?)s?['\"]", str(exc))
    if m:
        return float(m.group(1))

    return None


def appeler_avec_backoff(
    fn: Callable[[], T],
    max_tentatives: int = 5,
    delai_initial: float = 2.0,
) -> T:
    """Appelle `fn()`, retente sur 429 RPM et 5xx (voir docstring module)."""
    from google.genai import errors

    delai = delai_initial
    for tentative in range(max_tentatives):
        try:
            return fn()
        except errors.ClientError as exc:
            if getattr(exc, "code", None) != 429:
                raise
            # Quota journalier : stop immediat, pas de retry.
            retry_s = _extract_retry_delay_s(exc)
            if retry_s is not None and retry_s > SEUIL_QUOTA_JOURNALIER_S:
                raise ErreurQuotaJournalier(retry_delay_s=retry_s) from exc
            if tentative == max_tentatives - 1:
                raise ErreurQuotaDepassee(
                    f"Quota Gemini (429) : echec apres {max_tentatives} "
                    f"tentatives."
                ) from exc
            time.sleep(delai)
            delai *= 2
        except errors.ServerError:
            # 5xx : surcharge Google transitoire, pas un quota.
            if tentative == max_tentatives - 1:
                raise
            time.sleep(delai)
            delai *= 2
    # Jamais atteint sauf max_tentatives == 0.
    raise ErreurQuotaDepassee(f"max_tentatives={max_tentatives} atteint.")
