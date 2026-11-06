"""Index BM25 local sur les chunks BilanLens (plan V2 §3).

Règles de tokenisation figées ex ante (V2) :

- Minuscules, accents retirés (NFKD + suppression des marks).
- Regroupement des nombres séparés par UN SEUL espace : par
  exemple « 100 836 224 » → « 100836224 ». Appliqué aussi aux
  questions (même règle des deux côtés). Deux espaces ou plus
  entre deux chiffres ne déclenchent pas le regroupement. La
  règle est « greedy » : TOUS les chiffres séparés par un seul
  espace sont fusionnés, même si cela traverse une frontière
  de colonnes (ex. « 732 595 162 684 081 159 » dans
  monoprix_consolide_2024 p.21 devient un seul token de 18
  chiffres). Une version plus stricte (par exemple
  « uniquement des groupes de 3 chiffres ») n'a rien changé au
  BM25 seul lors de l'expérience V2.1, donc la règle greedy
  est conservée.
- Regroupement des points de milliers entre chiffres :
  « 268.125.000 » → « 268125000 ».
- Découpage aux apostrophes typographiques (U+2019) et droites
  (U+0027) : « l'exercice » → « l », « exercice ».
- Pas de stemming (provision / provisions restent 2 tokens).

BM25 : k1 = 1.5, b = 0.75 (défauts rank_bm25).

Tokenisation V2.1 (post-hoc, ajoutée après mesure V2) : identique
V2 + filtre d'une liste publique de stop words français (cf.
`STOP_WORDS_FR` et `tokeniser_v2_1`). Exposée en tant que
tokeniseur alternatif, à passer à `IndexBM25(..., tokenizer=...)`.

Pré-condition : rank_bm25 == 0.2.2.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Callable, Iterable

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


# ---------------------------------------------------------------------------
# Stop words français — V2.1 (post-hoc)
# ---------------------------------------------------------------------------
# Source : NLTK 3.9, corpus `stopwords`, fichier `french`, licence
# Apache 2.0. Référence : https://github.com/nltk/nltk_data, paquet
# `corpora/stopwords`, fichier `french`. Liste recopiée telle quelle
# ci-dessous ; la normalisation locale (minuscules + NFKD + retrait
# des accents) est appliquée au chargement du module pour que la
# comparaison avec les tokens V2 (déjà normalisés) soit directe.
_STOP_WORDS_FR_NLTK_VERBATIM = (
    "au aux avec ce ces dans de des du elle en et eux il ils "
    "je la le les leur lui ma mais me même mes moi mon ne nos "
    "notre nous on ou par pas pour qu que qui sa se ses son "
    "sur ta te tes toi ton tu un une vos votre vous c d j l à "
    "m n s t y été étée étées étés étant étante étants étantes "
    "suis es est sommes êtes sont serai seras sera serons serez "
    "seront serais serait serions seriez seraient étais était "
    "étions étiez étaient fus fut fûmes fûtes furent sois soit "
    "soyons soyez soient fusse fusses fût fussions fussiez "
    "fussent ayant ayante ayantes ayants eu eue eues eus ai as "
    "avons avez ont aurai auras aura aurons aurez auront aurais "
    "aurait aurions auriez auraient avais avait avions aviez "
    "avaient eut eûmes eûtes eurent aie aies ait ayons ayez "
    "aient eusse eusses eût eussions eussiez eussent"
).split()


def _normaliser_mot(mot: str) -> str:
    """Minuscules + NFKD + retrait des accents (comme tokeniser)."""
    t = mot.lower()
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c))


STOP_WORDS_FR: frozenset[str] = frozenset(
    _normaliser_mot(m) for m in _STOP_WORDS_FR_NLTK_VERBATIM
)


def tokeniser_v2_1(texte: str) -> list[str]:
    """Tokenisation V2.1 : V2 + retrait des stop words français.

    Décision POST-HOC : ajoutée après observation des résultats
    V2, où `BM25Okapi` donne un IDF plancher ≈ 1,15 aux mots
    très fréquents (« de », « et », « la »), suffisant pour
    polluer le score. L'hypothèse V2 « l'IDF fait le tri » ne
    tient pas en pratique avec rank_bm25 0.2.2.
    """
    return [t for t in tokeniser(texte) if t not in STOP_WORDS_FR]


class IndexBM25:
    """Index BM25 construit une fois sur une liste de chunks.

    Un chunk = dict avec au minimum ``chunk_id`` et ``texte``. Les
    autres champs sont ignorés pour l'indexation mais peuvent être
    conservés pour la restitution.

    ``tokenizer`` : fonction ``str -> list[str]``. Par défaut la
    tokenisation V2 (`tokeniser`). Passer `tokeniser_v2_1` pour la
    variante avec filtre de stop words français.
    """

    def __init__(
        self,
        chunks: Iterable[dict],
        tokenizer: Callable[[str], list[str]] = tokeniser,
    ):
        self.chunks: list[dict] = list(chunks)
        self.chunk_ids: list[str] = [c["chunk_id"] for c in self.chunks]
        self.tokenizer = tokenizer
        corpus = [tokenizer(c.get("texte", "")) for c in self.chunks]
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
        tokens = self.tokenizer(question)
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
