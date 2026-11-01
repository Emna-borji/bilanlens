"""Indexation des chunks BilanLens dans Chroma via API Gemini
(RAG, Semaine 2 etape 4).

Pipeline :
1. Charge `.env` -> `GEMINI_API_KEY`.
2. Charge tous les chunks de `data/chunks/*.jsonl`.
3. Compte les tokens reels de chaque chunk via `count_tokens`
   (gratuit, cache local pour eviter deux comptages).
4. Affiche une **estimation de duree** avant indexation.
5. Instancie l'encodeur Gemini (`gemini-embedding-2`) et indexe
   avec `encoder.embed_documents(textes)` (task_type RETRIEVAL_DOCUMENT).
6. Affiche a la fin :
    - modele + task_type + dimension ;
    - nombre total de tokens ;
    - nombre d'appels API (comptage + embeddings) ;
    - duree ;
    - nombre de chunks indexes + taille de l'index sur disque ;
    - top-3 Chroma pour la question Q01 (encodee avec RETRIEVAL_QUERY).

Usage :
    .\\.venv\\Scripts\\python.exe scripts/index_chunks.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RACINE / ".env")

from bilanlens.embeddings import (  # noqa: E402
    DEFAULT_MODEL,
    DEFAULT_DIM,
    MARGE_QUOTA,
    TASK_RETRIEVAL_DOCUMENT,
    TPM_MAX,
    charger_encodeur,
    nom_collection,
)
from bilanlens.index import (  # noqa: E402
    charger_chunks,
    indexer_chunks,
    ouvrir_collection,
)

CHUNKS_DIR = RACINE / "data" / "chunks"
CHROMA_DIR = RACINE / "data" / "chroma"
BENCH_PATH = RACINE / "data" / "benchmark" / "questions.jsonl"
SEUIL_CHUNKING = 4000


def _taille_dir(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _formater_octets(n: int) -> str:
    for unite in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or unite == "Go":
            return f"{n:.1f} {unite}"
        n /= 1024
    return f"{n:.1f} Go"


def _trouver_question(bench_path: Path, q_id: str) -> dict | None:
    with bench_path.open(encoding="utf-8") as f:
        for ligne in f:
            q = json.loads(ligne)
            if q["id"] == q_id:
                return q
    return None


def main() -> int:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    coll_name = nom_collection(DEFAULT_MODEL)
    print(f"=== Encodeur : {DEFAULT_MODEL} (dim={DEFAULT_DIM}) ===")
    print(f"Task type indexation : {TASK_RETRIEVAL_DOCUMENT}")
    print(f"Collection Chroma    : {coll_name}")
    print(f"Quotas appliques     : TPM={TPM_MAX}, marge={MARGE_QUOTA}")
    print()

    encoder = charger_encodeur()

    chunks = list(charger_chunks(CHUNKS_DIR))
    print(f"Chunks a indexer : {len(chunks)} (depuis {CHUNKS_DIR.relative_to(RACINE)}/)")

    # Pre-count : estimation + mise en cache des tokens.
    print("Comptage des tokens (count_tokens, mis en cache local) ...")
    t_count = time.perf_counter()
    tokens = [encoder.compter_tokens(c["texte"]) for c in chunks]
    duree_count = time.perf_counter() - t_count
    total_tokens = sum(tokens)
    max_t = max(tokens)
    moy_t = total_tokens / len(tokens)
    print(f"  total = {total_tokens} tokens | max = {max_t} | moy = {moy_t:.0f}")
    print(f"  compte en {duree_count:.1f} s (appels API count : {encoder._nb_appels_count})")

    budget_lot = int(TPM_MAX * MARGE_QUOTA)
    nb_lots_est = (total_tokens + budget_lot - 1) // budget_lot
    duree_est_min = max(nb_lots_est - 1, 0)
    print()
    print("=== Estimation duree indexation ===")
    print(f"  budget par lot    : {budget_lot} tokens")
    print(f"  nb de lots estime : {nb_lots_est}")
    print(
        f"  duree estimee     : >= {duree_est_min} min "
        f"(attente d'une minute entre lots pour fenetre TPM)"
    )
    print()

    _, coll = ouvrir_collection(
        CHROMA_DIR,
        model=DEFAULT_MODEL,
        metadonnees_collection={
            "modele_embeddings": DEFAULT_MODEL,
            "dim_embeddings": DEFAULT_DIM,
            "task_type_indexation": TASK_RETRIEVAL_DOCUMENT,
            "seuil_chunking_chars": SEUIL_CHUNKING,
            "date_indexation": date.today().isoformat(),
        },
    )

    print(f"Indexation (hnsw:space=cosine)...")
    n, stats = indexer_chunks(coll, chunks, encoder, verbose=True)
    print(f"  {n} chunks upsert")

    taille_index = _taille_dir(CHROMA_DIR)
    print()
    print("=== Resume indexation ===")
    print(f"  modele             : {DEFAULT_MODEL}")
    print(f"  task_type          : {TASK_RETRIEVAL_DOCUMENT}")
    print(f"  dimension          : {DEFAULT_DIM}")
    print(f"  tokens total       : {stats['tokens_total']}")
    print(f"  cache hits         : {stats['nb_hits_cache']}/{n}")
    print(f"  a encoder          : {stats['nb_a_encoder']}")
    print(f"  appels count       : {stats['nb_appels_count']}")
    print(f"  appels embed       : {stats['nb_appels_embed']} (en {stats['nb_lots']} lot(s))")
    print(f"  duree encodage     : {stats['duree_s']:.1f} s")
    print(f"  chunks indexes     : {coll.count()}")
    print(
        f"  taille index       : {_formater_octets(taille_index)}  "
        f"({CHROMA_DIR.relative_to(RACINE)}/)"
    )

    # Top-3 Q01 (encodee avec RETRIEVAL_QUERY — asymetrie doc/query).
    print()
    q = _trouver_question(BENCH_PATH, "sotuver_2024_01")
    if q is None:
        print("Benchmark Q01 (sotuver_2024_01) introuvable.")
        return 0
    print(f"=== Top-3 pour {q['id']} ===")
    print(f"  Q : {q['question']}")
    vec_q = encoder.embed_query(q["question"])
    res = coll.query(
        query_embeddings=[vec_q.tolist()],
        n_results=3,
        include=["documents", "metadatas", "distances"],
    )
    for rang, (doc_t, meta, dist) in enumerate(
        zip(res["documents"][0], res["metadatas"][0], res["distances"][0]),
        start=1,
    ):
        page = meta.get("page_physique")
        sous = meta.get("sous_numero")
        sim = 1.0 - dist
        extrait = doc_t.replace("\n", " | ")[:120]
        print(f"  {rang}. {meta['doc']} p.{page} s{sous}  cos={sim:.3f}")
        print(f"     « {extrait} »")

    return 0


if __name__ == "__main__":
    sys.exit(main())
