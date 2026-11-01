"""Retry partage entre adapters (llm.py, embeddings.py).

Un seul endroit pour :
- `ErreurQuotaDepassee` : type d'erreur commun aux adapters Gemini ;
- `appeler_avec_backoff(fn)` : backoff exponentiel sur 429
  (`google.genai.errors.ClientError.code == 429`), delais
  `[2, 4, 8, 16]` s, pas d'attente apres la derniere tentative ;
  toute erreur ne portant pas `code == 429` se propage.

Prendre un callable sans arguments plutot qu'un `(method, args, kwargs)`
rend le site d'appel explicite : on y voit la fonction appelee, pas une
indirection par noms positionnels.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


class ErreurQuotaDepassee(RuntimeError):
    """Levee quand le quota free tier est epuise apres N tentatives."""


def appeler_avec_backoff(
    fn: Callable[[], T],
    max_tentatives: int = 5,
    delai_initial: float = 2.0,
) -> T:
    """Appelle `fn()`, retente sur 429, propage toute autre erreur.

    Delais : `delai_initial`, puis x2 a chaque reprise (par defaut
    `[2, 4, 8, 16]` s pour 5 tentatives). Pas d'attente apres la
    derniere tentative.
    """
    from google.genai import errors

    delai = delai_initial
    for tentative in range(max_tentatives):
        try:
            return fn()
        except errors.ClientError as exc:
            if getattr(exc, "code", None) != 429:
                raise
            if tentative == max_tentatives - 1:
                raise ErreurQuotaDepassee(
                    f"Quota Gemini (429) : echec apres {max_tentatives} "
                    f"tentatives."
                ) from exc
            time.sleep(delai)
            delai *= 2
    # Jamais atteint sauf max_tentatives == 0.
    raise ErreurQuotaDepassee(f"max_tentatives={max_tentatives} atteint.")
