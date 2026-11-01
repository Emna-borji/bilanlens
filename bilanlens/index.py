"""Index vectoriel Chroma pour BilanLens (RAG, Semaine 2 etape 4).

Design :
- **Une collection par modele d'embedding** : nom =
  `bilans__<model>` (voir `bilanlens.embeddings.nom_collection`).
  Permet de brancher un adapter bge-m3 (Colab) plus tard sans
  melanger les espaces vectoriels dans la meme collection.
- Metrique : `hnsw:space=cosine`. Les vecteurs Gemini sont nativement
  unit-norm (norme L2=1), donc le produit scalaire egale deja le
  cosinus ; `cosine` cote Chroma est pose pour la clarte semantique,
  pas pour corriger une echelle.
- IDs stables : `<doc>_p<page_physique>_s<sous_numero>`. Permet un
  `upsert` idempotent : re-indexer ne cree jamais de doublons.
- `None` dans les metadonnees : Chroma refuse. On OMET les cles dont
  la valeur est None (`page_imprimee` pour les pages de garde), plutot
  que de les remplacer par "" ou 0 et inventer une valeur.
- Pas de `isinstance` : `indexer_chunks` appelle `encoder.embed_documents`
  via le Protocol `Encodeur`.
"""
from __future__ import annotations

import json
from pathlib import Path


def chunk_id(c: dict) -> str:
    """ID stable : `<doc>_p<page_physique>_s<sous_numero>`."""
    return f"{c['doc']}_p{c['page_physique']}_s{c['sous_numero']}"


def _nettoyer_metadata(meta: dict) -> dict:
    """Omet les cles None (Chroma les refuse)."""
    return {k: v for k, v in meta.items() if v is not None}


def _metadonnees_chunk(c: dict) -> dict:
    """Metadonnees Chroma pour un chunk (dict JSON du JSONL)."""
    return _nettoyer_metadata({
        "doc": c["doc"],
        "entreprise": c["entreprise"],
        "exercice": c["exercice"],
        "page_physique": c["page_physique"],
        "page_imprimee": c.get("page_imprimee"),
        "sous_numero": c["sous_numero"],
    })


def ouvrir_collection(
    persist_path: Path | str,
    nom: str | None = None,
    model: str | None = None,
    metadonnees_collection: dict | None = None,
):
    """Ouvre (ou cree) la collection Chroma persistante.

    `nom` : si fourni, utilise tel quel. Sinon derive du `model` via
    `nom_collection(model)`. Les deux restent exclusifs : si aucun
    n'est fourni, erreur.

    `metadonnees_collection` : infos de reproductibilite stockees
    directement sur la collection — modele, dim, task_type, seuil
    de chunking, date d'indexation. `hnsw:space=cosine` est impose
    ici, non surchargeable.
    """
    import chromadb

    from bilanlens.embeddings import nom_collection

    if nom is None:
        if model is None:
            raise ValueError("ouvrir_collection : fournir `nom` ou `model`")
        nom = nom_collection(model)

    client = chromadb.PersistentClient(path=str(persist_path))
    meta = {"hnsw:space": "cosine"}
    if metadonnees_collection:
        meta.update(metadonnees_collection)
        meta["hnsw:space"] = "cosine"
    coll = client.get_or_create_collection(name=nom, metadata=meta)
    return client, coll


def charger_chunks(chunks_dir: Path | str):
    """Itere sur tous les chunks de `data/chunks/*.jsonl`."""
    for jsonl in sorted(Path(chunks_dir).glob("*.jsonl")):
        with jsonl.open(encoding="utf-8") as f:
            for ligne in f:
                yield json.loads(ligne)


def indexer_chunks(
    coll, chunks: list[dict], encoder, verbose: bool = False,
) -> tuple[int, dict]:
    """Upsert tous les `chunks` dans la collection.

    `encoder` : n'importe quelle instance respectant le Protocol
    `bilanlens.embeddings.Encodeur` (methodes `embed_documents` et
    `embed_query`). Pas de `isinstance` ici.

    Retourne `(n_chunks, stats)` ou `stats` provient de
    `encoder.embed_documents` : nombre d'appels API count + embed,
    hits cache, tokens total, nombre de lots, duree.

    Idempotent grace a `chunk_id` deterministe + cache embeddings
    disque : une 2e indexation = 0 appel API.
    """
    ids = [chunk_id(c) for c in chunks]
    textes = [c["texte"] for c in chunks]
    metas = [_metadonnees_chunk(c) for c in chunks]

    vecteurs, stats = encoder.embed_documents(textes, verbose=verbose)
    if hasattr(vecteurs, "tolist"):
        vecteurs = vecteurs.tolist()

    coll.upsert(
        ids=ids,
        embeddings=vecteurs,
        documents=textes,
        metadatas=metas,
    )
    return len(ids), stats
