"""V2 : pipeline retrieval `v2.1 / hybride_filtre` + prompt V1.2.

Configuration retenue par le critère §4 du plan V2 (benchmark
2026-11-06) :
- Dense top-50 restreint au périmètre filtré (entreprise
  désambiguée par ``bilanlens.filtre_question``).
- BM25 top-50 : IDF **recalculée sur le périmètre filtré** (un
  nouvel ``IndexBM25`` est construit à chaque question sur le
  sous-ensemble de chunks de l'entreprise, avec le tokeniseur
  V2.1 — stop words français NLTK filtrés).
- Fusion RRF (k = 60) → top-5 envoyé au LLM.

**Prompt V1.2 inchangé byte-à-byte** : ``SYSTEM_INSTRUCTION``
+ ``TEMPLATE_V1_2_USER`` identiques à ``evaluate_v1_2.py``.

Choix de la config : parmi 10 configurations (5 configs × 2
variantes V2 / V2.1). Gains vs dense : **+4 / −1** au Recall@5
(gains Q07, Q12, Q25, Q30 ; perte Q13). Décision post-hoc sur
les stop words — tracée dans le journal 2026-11-06 (soir, 2).

Sortie : ``results/v2.jsonl`` sous run_id dédié
``v2_<slug>_k5_<prompt_version_v1_2>_v2_1_hybride_filtre``.
Les runs précédents (v1.jsonl, v1_1.jsonl, v1_2.jsonl) ne sont
PAS modifiés.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RACINE / ".env")

import numpy as np  # noqa: E402

from bilanlens.bm25 import IndexBM25, tokeniser_v2_1  # noqa: E402
from bilanlens.filtre_question import entreprises_filtre  # noqa: E402
from bilanlens.llm import (  # noqa: E402
    ErreurQuotaJournalier, GeminiLLM, creer_llm,
)
from bilanlens.prompts import (  # noqa: E402
    JSON_SCHEMA_REPONSE_V1,
    SYSTEM_INSTRUCTION,
    TEMPLATE_V1_2_USER,
    prompt_version_v1_2,
)
from bilanlens.retrieval_hybride import (  # noqa: E402
    K_RRF, TAILLE_LISTES_AVANT_FUSION,
    fusionner_rrf, marquer_source,
)
from scripts.benchmark_retrieval import (  # noqa: E402
    MODEL as MODEL_EMBEDDING,
    TASK_DOCUMENT, TASK_QUERY,
    _hash_cle, charger_cache_embeddings, charger_chunks,
    dense_top_k, enrichir,
)
from scripts.evaluate_b0 import (  # noqa: E402
    append_jsonl, charger_benchmark, lire_checkpoint,
    message_arret_quota_journalier, slug_modele,
    EXIT_CODE_QUOTA_JOURNALIER,
)
from scripts.evaluate_v1 import (  # noqa: E402
    citations_invalides, formater_contexte, parser_reponse_v1,
)

BENCH_PATH = RACINE / "data" / "benchmark" / "questions.jsonl"
CHUNKS_DIR = RACINE / "data" / "chunks"
CACHE_PATH = RACINE / "data" / "cache_embeddings" / f"{MODEL_EMBEDDING}.jsonl"
RESULTS_PATH = RACINE / "results" / "v2.jsonl"

TOP_K_FINAL = 5
CONFIG_ID = "v2_1_hybride_filtre"


def run_id_defaut_v2(model: str, prompt_version: str, top_k: int) -> str:
    """run_id : ``v2_<slug>_k<k>_<prompt_version>_v2_1_hybride_filtre``."""
    return (
        f"v2_{slug_modele(model)}_k{top_k}_{prompt_version}_"
        f"{CONFIG_ID}"
    )


# ------------------------------------------------------------------
# Pipeline retrieval V2 = v2.1 / hybride_filtre
# ------------------------------------------------------------------

def pipeline_v2_top5(
    question: dict,
    q_vec: np.ndarray,
    chunks: list[dict],
    chunks_par_id: dict[str, dict],
    vecteurs_chunks: dict[str, np.ndarray],
    top_fusion: int = TAILLE_LISTES_AVANT_FUSION,
    top_final: int = TOP_K_FINAL,
) -> tuple[list[dict], list[str] | None]:
    """Retrieval `v2.1 / hybride_filtre` pour une question.

    Étapes figées (plan V2 §2/§3 + V2.1 post-hoc) :
    1. Filtre entreprise → périmètre (1 doc ou 2 pour Monoprix
       ambigu) ou None (pas de filtre, périmètre global).
    2. Dense top-50 sur le périmètre : cosine exact sur vecteurs
       unit-norm cache (``bilanlens.embeddings``).
    3. BM25 top-50 : **nouvel ``IndexBM25`` construit sur le
       sous-ensemble filtré**, tokenizer V2.1. IDF locale au
       périmètre.
    4. RRF (k = 60) sur les 2 listes → top-5.
    5. Enrichissement : chaque résultat gagne ``doc``,
       ``page_physique``, ``sous_numero`` depuis ``chunks_par_id``.

    Retourne (top5_enrichi, docs_filtre). ``docs_filtre`` = None
    pour les Q sans entreprise reconnue (cas non vu sur le
    benchmark actuel ; à surveiller).
    """
    docs_filtre = entreprises_filtre(question["question"])
    if docs_filtre is None:
        chunks_perimetre = chunks
        chunk_ids_perimetre = None
    else:
        chunks_perimetre = [
            c for c in chunks if c["doc"] in docs_filtre
        ]
        chunk_ids_perimetre = {c["chunk_id"] for c in chunks_perimetre}

    dense_top50 = dense_top_k(
        q_vec, chunks, vecteurs_chunks, top_fusion,
        chunk_ids_filtre=chunk_ids_perimetre,
    )
    bm25_filtre = IndexBM25(chunks_perimetre, tokenizer=tokeniser_v2_1)
    bm25_top50 = bm25_filtre.rechercher(
        question["question"], top_fusion,
    )
    fusion = fusionner_rrf(
        [marquer_source(dense_top50, "dense"),
         marquer_source(bm25_top50, "bm25")],
        top_k=top_final,
        k_rrf=K_RRF,
    )
    return enrichir(fusion, chunks_par_id), docs_filtre


# ------------------------------------------------------------------
# LLM : prompt V1.2 inchangé
# ------------------------------------------------------------------

def generer_reponse_v2(llm, contexte: str, question: str):
    """Prompt V1.2 byte-à-byte identique à evaluate_v1_2.py."""
    prompt_user = TEMPLATE_V1_2_USER.format(
        context=contexte, question=question,
    )
    return llm.generate(
        prompt=prompt_user,
        system=SYSTEM_INSTRUCTION,
        temperature=0.0,
        response_schema=JSON_SCHEMA_REPONSE_V1,
    )


# ------------------------------------------------------------------
# Format d'une ligne results/v2.jsonl
# ------------------------------------------------------------------

def ligne_resultat_v2(
    *,
    question: dict,
    reponse,
    retrieved_top5: list[dict],
    contexte: str,
    answer_parsed: dict | None,
    parse_ok: bool,
    run_id: str,
    prompt_version: str,
    top_k: int,
    docs_filtre: list[str] | None,
) -> dict:
    """Produit la ligne JSON-serialisable à écrire dans v2.jsonl.

    Le champ ``retrieved`` contient le top-5 **enrichi**
    (chunk_id, rank, doc, page_physique, sous_numero,
    score_rrf, rangs_sources). Le texte n'est PAS stocké ici :
    il est reconstruit depuis ``data/chunks/*.jsonl`` au moment
    du scoring, comme pour V1.
    """
    retrieved_light = [
        {k: v for k, v in r.items() if k != "texte"}
        for r in retrieved_top5
    ]
    nb_extraits = len(retrieved_top5)
    cited = (
        (answer_parsed or {}).get("cited_extraits", []) if parse_ok else []
    )
    invalides = citations_invalides(cited, nb_extraits)
    return {
        "run_id": run_id,
        "provenance": "v2",
        "retrieval_config": CONFIG_ID,
        "retrieval_variante": "v2.1",
        "docs_filtre": docs_filtre,
        "prompt_version": prompt_version,
        "question_id": question["id"],
        "question": question["question"],
        "category": question.get("category"),
        "top_k": top_k,
        "retrieved": retrieved_light,
        "context_rendered_chars": len(contexte),
        "answer_raw": reponse.text,
        "answer_parsed": answer_parsed,
        "parse_ok": parse_ok,
        "cited_invalides": invalides,
        "model": reponse.model,
        "provider": reponse.provider,
        "temperature": reponse.temperature,
        "latency_s": round(reponse.latency_s, 3),
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(timespec="seconds"),
    }


# ------------------------------------------------------------------
# Main : run LLM 31 Q
# ------------------------------------------------------------------

def main() -> int:
    parseur = argparse.ArgumentParser(
        description="V2 : hybride_filtre V2.1 + prompt V1.2.",
    )
    parseur.add_argument("--model", default=GeminiLLM.DEFAULT_MODEL)
    parseur.add_argument("--run-id", default=None)
    parseur.add_argument("--only", default=None)
    parseur.add_argument("--interval-s", type=float, default=7.0)
    parseur.add_argument(
        "--output", default=None,
        help="Chemin alternatif pour results/v2.jsonl (ex : repeat).",
    )
    args = parseur.parse_args()

    global RESULTS_PATH
    if args.output:
        RESULTS_PATH = Path(args.output)
        if not RESULTS_PATH.is_absolute():
            RESULTS_PATH = RACINE / RESULTS_PATH

    print("Chargement benchmark...")
    questions = charger_benchmark(BENCH_PATH)
    if args.only:
        ids = {s.strip() for s in args.only.split(",") if s.strip()}
        questions = [q for q in questions if q["id"] in ids]
    print(f"  {len(questions)} questions")

    print("Chargement chunks locaux...")
    chunks = charger_chunks(CHUNKS_DIR)
    chunks_par_id = {c["chunk_id"]: c for c in chunks}
    print(f"  {len(chunks)} chunks")

    print("Chargement cache embeddings...")
    cache = charger_cache_embeddings(CACHE_PATH)
    print(f"  {len(cache)} entrées")

    print("Résolution vecteurs chunks (cache RETRIEVAL_DOCUMENT)...")
    vecteurs_chunks: dict[str, np.ndarray] = {}
    for c in chunks:
        key = _hash_cle(MODEL_EMBEDDING, TASK_DOCUMENT, c["texte"])
        v = cache.get(key)
        if v is None:
            print(f"  ERREUR : chunk absent du cache : {c['chunk_id']}")
            return 1
        vecteurs_chunks[c["chunk_id"]] = v

    print("Résolution vecteurs questions (cache RETRIEVAL_QUERY)...")
    vecteurs_q: dict[str, np.ndarray] = {}
    for q in questions:
        key = _hash_cle(MODEL_EMBEDDING, TASK_QUERY, q["question"])
        v = cache.get(key)
        if v is None:
            print(f"  ERREUR : question absente du cache : {q['id']}")
            return 1
        vecteurs_q[q["id"]] = v

    prompt_version = prompt_version_v1_2()
    model = args.model
    run_id = args.run_id or run_id_defaut_v2(
        model, prompt_version, TOP_K_FINAL,
    )

    print()
    print("=== V2 : v2.1 / hybride_filtre + prompt V1.2 ===")
    print(f"  model                : {model}")
    print(f"  top_k envoyé au LLM  : {TOP_K_FINAL}")
    print(f"  tokenisation BM25    : V2.1 (stop words NLTK FR filtrés)")
    print(f"  IDF BM25             : recalculée sur périmètre filtré")
    print(f"  run_id               : {run_id}")
    print(f"  prompt_version (V1.2): {prompt_version}")

    deja_faits = lire_checkpoint(RESULTS_PATH, run_id)
    a_faire = [q for q in questions if q["id"] not in deja_faits]
    print(f"Déjà faits : {len(deja_faits)}  |  à faire : {len(a_faire)}")
    if not a_faire:
        return 0

    llm = creer_llm(provider="gemini", model=model)

    for i, q in enumerate(a_faire, start=1):
        qid = q["id"]
        q_vec = vecteurs_q[qid]
        top5, docs_filtre = pipeline_v2_top5(
            question=q, q_vec=q_vec,
            chunks=chunks, chunks_par_id=chunks_par_id,
            vecteurs_chunks=vecteurs_chunks,
        )
        # Reconstruit le contexte (ajoute le texte depuis
        # chunks_par_id pour chaque chunk du top-5)
        retrieved_avec_texte = [
            {**r, "texte": chunks_par_id[r["chunk_id"]]["texte"]}
            for r in top5
        ]
        contexte = formater_contexte(retrieved_avec_texte)

        print(f"[{i}/{len(a_faire)}] {qid} ({q.get('category', '-')})")
        try:
            reponse = generer_reponse_v2(llm, contexte, q["question"])
        except ErreurQuotaJournalier as exc:
            print(message_arret_quota_journalier(
                nb_faits=len(deja_faits) + i - 1,
                total=len(questions),
                retry_delay_s=exc.retry_delay_s,
            ))
            return EXIT_CODE_QUOTA_JOURNALIER
        answer_parsed, parse_ok = parser_reponse_v1(reponse.text)
        rec = ligne_resultat_v2(
            question=q, reponse=reponse,
            retrieved_top5=top5, contexte=contexte,
            answer_parsed=answer_parsed, parse_ok=parse_ok,
            run_id=run_id, prompt_version=prompt_version,
            top_k=TOP_K_FINAL, docs_filtre=docs_filtre,
        )
        append_jsonl(RESULTS_PATH, rec)
        ans = (answer_parsed or {}).get("answer", "<parse_ok=False>")[:80]
        print(f"    -> {ans}  ({reponse.latency_s:.2f} s)")
        if i < len(a_faire):
            time.sleep(args.interval_s)

    print(f"\nFini : {RESULTS_PATH.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
