"""Reciprocal Rank Fusion (RRF) sur deux listes classées (plan V2 §3).

RRF fusionne deux listes top-50 (dense + BM25) sans mixer leurs
scores : seuls les rangs comptent. Un chunk à chaque liste reçoit
``1/(k_RRF + rang)``, additionné sur les listes où il apparaît.

Hyperparamètres figés ex ante (§3) :
- Taille des listes avant fusion : 50 chunks (dense ET BM25).
- Constante RRF : k = 60 (valeur canonique TREC).
- Tie-break : ``chunk_id`` alphanumérique croissant.

Attention : le filtre entreprise (§1) DOIT être appliqué AVANT la
construction des listes top-50, pour ne jamais faire remonter un
chunk hors périmètre dans la fusion. Ce module se contente de
fusionner deux listes déjà filtrées en amont.
"""
from __future__ import annotations

from typing import Iterable

K_RRF = 60
TAILLE_LISTES_AVANT_FUSION = 50


def fusionner_rrf(
    listes: Iterable[list[dict]],
    top_k: int,
    k_rrf: int = K_RRF,
) -> list[dict]:
    """Fusionne plusieurs listes classées par Reciprocal Rank Fusion.

    Chaque entrée des listes doit avoir au minimum :
    - ``chunk_id`` : identifiant unique du chunk ;
    - ``rank`` : rang entier 1-indexed dans sa liste source.

    Retourne les top-k chunks, triés par score RRF décroissant,
    tie-break par ``chunk_id`` alphanumérique croissant (§3).
    Chaque résultat :
    ``{rank, chunk_id, score_rrf, rangs_sources: {source: rang}}``.

    Pour tracer la provenance, chaque liste peut être annotée
    d'une clé ``source`` sur chaque dict (``'dense'`` ou
    ``'bm25'``). Si absente, la clé ``source`` du dict d'entrée,
    sinon une clé générique ``'liste_i'`` est utilisée.
    """
    listes = list(listes)
    scores: dict[str, float] = {}
    rangs_sources: dict[str, dict[str, int]] = {}
    for i, liste in enumerate(listes):
        source_defaut = f"liste_{i}"
        for item in liste:
            cid = item["chunk_id"]
            rang = int(item["rank"])
            source = item.get("source", source_defaut)
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k_rrf + rang)
            rangs_sources.setdefault(cid, {})[source] = rang
    ordonne = sorted(
        scores.items(),
        key=lambda t: (-t[1], t[0]),
    )
    resultats: list[dict] = []
    for rang_final, (cid, score) in enumerate(ordonne[:top_k], start=1):
        resultats.append({
            "rank": rang_final,
            "chunk_id": cid,
            "score_rrf": score,
            "rangs_sources": rangs_sources[cid],
        })
    return resultats


def marquer_source(liste: list[dict], source: str) -> list[dict]:
    """Annote une liste de résultats avec la clé ``source``.

    Retourne une nouvelle liste (ne mute pas les dicts d'entrée).
    """
    return [{**item, "source": source} for item in liste]
