"""Index BM25 local sur les chunks BilanLens (plan V2 §3).

Règles de tokenisation figées ex ante dans le journal V2
(2026-11-06) :

- Minuscules, accents retirés (NFKD + suppression des marks).
- Regroupement des nombres séparés par UN SEUL espace : par
  exemple « 100 836 224 » → « 100836224 ». Appliqué aussi aux
  questions (même règle des deux côtés). Deux espaces ou plus
  entre deux chiffres ne déclenchent pas le regroupement.
- Regroupement des points de milliers entre chiffres : « 268.125.000 »
  → « 268125000 ».
- Découpage aux apostrophes typographiques (U+2019) et droites
  (U+0027) : « l'exercice » → « l », « exercice ».
- Pas de stemming (provision / provisions restent 2 tokens).
- Stop-words conservés : l'IDF fait le tri.
- Ordre stable : tie-break par chunk_id alphanumérique croissant.

BM25 : k1 = 1.5, b = 0.75 (défauts rank_bm25).

Pré-condition : rank_bm25 == 0.2.2.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from rank_bm25 import BM25Okapi

K1 = 1.5
B = 0.75

_RE_POINT_MILLIER = re.compile(r"(?<=\d)\.(?=\d)")
_RE_ESPACE_MILLIER = re.compile(r"(?<=\d) (?=\d)")
_RE_TOKEN = re.compile(r"[a-z0-9]+(?:,[0-9]+)?")


def tokeniser(texte: str) -> list[str]:
    """Tokenise un texte selon les règles V2 (§3).

    Appliquer la MÊME fonction aux chunks ET aux questions : si
    la question contient « 100 836 224 » et le chunk aussi, les
    deux doivent produire le même token « 100836224 » sinon le
    match BM25 échoue.
    """
    if not texte:
        return []
    t = texte.lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = _RE_POINT_MILLIER.sub("", t)
    t = _RE_ESPACE_MILLIER.sub("", t)
    t = t.replace("’", " ").replace("'", " ")
    return _RE_TOKEN.findall(t)


class IndexBM25:
    """Index BM25 construit une fois sur une liste de chunks.

    Un chunk = dict avec au minimum ``chunk_id`` et ``texte``. Les
    autres champs sont ignorés pour l'indexation mais peuvent être
    conservés pour la restitution.
    """

    def __init__(self, chunks: Iterable[dict]):
        self.chunks: list[dict] = list(chunks)
        self.chunk_ids: list[str] = [c["chunk_id"] for c in self.chunks]
        corpus = [tokeniser(c.get("texte", "")) for c in self.chunks]
        # rank_bm25 exige des docs non-vides pour l'IDF. On insère
        # un placeholder dans les chunks vides pour ne pas planter
        # la construction ; leur score restera très bas.
        corpus = [doc if doc else ["__vide__"] for doc in corpus]
        self.bm25 = BM25Okapi(corpus, k1=K1, b=B)

    def rechercher(self, question: str, top_k: int) -> list[dict]:
        """Top-k chunks par score BM25 décroissant.

        Tie-break par chunk_id alphanumérique croissant (§3 règle
        d'ordre stable). Retourne une liste de dicts
        ``{rank, chunk_id, score}``.
        """
        tokens = tokeniser(question)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        indexes = sorted(
            range(len(scores)),
            key=lambda i: (-float(scores[i]), self.chunk_ids[i]),
        )
        resultats: list[dict] = []
        for rang, i in enumerate(indexes[:top_k], start=1):
            resultats.append({
                "rank": rang,
                "chunk_id": self.chunk_ids[i],
                "score": float(scores[i]),
            })
        return resultats
