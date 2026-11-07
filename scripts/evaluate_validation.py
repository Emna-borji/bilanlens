"""Partie B — runs LLM V1.2 (dense) et V2 (v2.1/hybride_filtre)
sur le jeu de validation (15 Q), une seule fois chacun.

**Prompt V1.2 inchangé byte-à-byte** pour les deux runs. Les deux
seules différences entre V1.2 et V2 sont :
- la méthode de retrieval (dense top-5 pour V1.2, hybride_filtre
  v2.1 top-5 pour V2) ;
- le run_id (+ fichier de sortie) distinct pour chaque.

Pipeline figé (identique au benchmark 31 Q) :
- V1.2 : dense top-5 via cosine exact sur vecteurs cache
  (``bilanlens.embeddings``).
- V2 : v2.1/hybride_filtre top-5 — dense top-50 restreint au
  périmètre entreprise, BM25 top-50 reconstruit sur le même
  périmètre (IDF locale), fusion RRF (k=60), tokenisation V2.1
  (stop words NLTK FR filtrés).

Les 15 questions sont pré-embeddées **une seule fois** (cache
local persisté dans ``data/cache_embeddings/``). Le compteur
``_nb_appels_embed`` de ``EncodeurGemini`` rapporte le nombre
réel d'appels à l'API Gemini embedding ; les Q déjà présentes
en cache ne déclenchent aucun appel.

Sortie :
- ``results/v1_2_validation.jsonl`` (15 lignes, run_id
  ``v1_2_val_<slug>_k5_<prompt_version_v1_2>``)
- ``results/v2_validation.jsonl`` (15 lignes, run_id
  ``v2_val_<slug>_k5_<prompt_version_v1_2>_v2_1_hybride_filtre``)
- ``results/retrieval_compare_validation.jsonl`` (30 lignes,
  top-20 dense + top-20 hybride_filtre_v2_1 par Q)

Aucune modification du prompt, du filtre, de BM25 ou de RRF.
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
from bilanlens.embeddings import EncodeurGemini, charger_encodeur  # noqa: E402
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
from scripts.evaluate_v2 import (  # noqa: E402
    CONFIG_ID as CONFIG_ID_V2, pipeline_v2_top5,
)


BENCH_PATH = RACINE / "data" / "benchmark" / "questions_validation.jsonl"
CHUNKS_DIR = RACINE / "data" / "chunks"
CACHE_PATH = (
    RACINE / "data" / "cache_embeddings" / f"{MODEL_EMBEDDING}.jsonl"
)
CACHE_DIR = RACINE / "data" / "cache_embeddings"
V1_2_PATH = RACINE / "results" / "v1_2_validation.jsonl"
V2_PATH = RACINE / "results" / "v2_validation.jsonl"
RETRIEVAL_CMP_PATH = (
    RACINE / "results" / "retrieval_compare_validation.jsonl"
)

TOP_K_FINAL = 5
TOP_K_SCORING = 20  # pour recall@1/3/5/10/20 au scoring


# ------------------------------------------------------------------
# Pré-embedding des 15 questions (compte les appels API)
# ------------------------------------------------------------------

def pre_embedder_questions(
    questions: list[dict], model: str,
) -> tuple[dict[str, np.ndarray], int]:
    """Pour chaque Q, récupère le vecteur RETRIEVAL_QUERY depuis
    le cache (via le ``_CacheEmbeddings`` de ``EncodeurGemini``)
    ou via un appel API Gemini. Retourne
    ({qid: vec}, n_appels_api).

    Le compteur ``_nb_appels_embed`` est incrémenté uniquement sur
    appel API réel : une Q déjà en cache coûte 0 appel.
    """
    encoder = charger_encodeur(model=model)
    vecteurs_q: dict[str, np.ndarray] = {}
    for q in questions:
        vec = encoder.embed_query(q["question"])
        vecteurs_q[q["id"]] = (
            vec if isinstance(vec, np.ndarray)
            else np.array(vec, dtype=np.float32)
        )
    return vecteurs_q, encoder._nb_appels_embed


def run_id_v1_2_val(model: str, prompt_version: str, top_k: int) -> str:
    return (
        f"v1_2_val_{slug_modele(model)}_k{top_k}_{prompt_version}"
    )


def run_id_v2_val(model: str, prompt_version: str, top_k: int) -> str:
    return (
        f"v2_val_{slug_modele(model)}_k{top_k}_{prompt_version}_"
        f"{CONFIG_ID_V2}"
    )


# ------------------------------------------------------------------
# LLM call V1.2 (prompt inchangé)
# ------------------------------------------------------------------

def generer_reponse(llm, contexte: str, question: str):
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
# Ligne résultat (format partagé V1.2/V2 validation)
# ------------------------------------------------------------------

def ligne_resultat(
    *,
    provenance: str,
    retrieval_config: str | None,
    retrieval_variante: str | None,
    docs_filtre: list[str] | None,
    question: dict,
    reponse,
    retrieved_top5: list[dict],
    contexte: str,
    answer_parsed: dict | None,
    parse_ok: bool,
    run_id: str,
    prompt_version: str,
    top_k: int,
) -> dict:
    retrieved_light = [
        {k: v for k, v in r.items() if k != "texte"}
        for r in retrieved_top5
    ]
    nb_extraits = len(retrieved_top5)
    cited = (
        (answer_parsed or {}).get("cited_extraits", []) if parse_ok else []
    )
    invalides = citations_invalides(cited, nb_extraits)
    rec = {
        "run_id": run_id,
        "provenance": provenance,
        "benchmark": "validation",
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
    if retrieval_config is not None:
        rec["retrieval_config"] = retrieval_config
    if retrieval_variante is not None:
        rec["retrieval_variante"] = retrieval_variante
    if docs_filtre is not None:
        rec["docs_filtre"] = docs_filtre
    return rec


# ------------------------------------------------------------------
# Écriture retrieval top-20 par pipeline pour scoring
# ------------------------------------------------------------------

def ecrire_retrieval_compare_validation(
    path: Path, retrieval_par_qid_v1_2: dict[str, list[dict]],
    retrieval_par_qid_v2: dict[str, list[dict]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as dst:
        for qid, items in retrieval_par_qid_v1_2.items():
            dst.write(json.dumps({
                "benchmark": "validation",
                "variante": "v1_2",
                "config": "dense",
                "question_id": qid,
                "retrieved_top20": [
                    {"rank": r["rank"], "chunk_id": r["chunk_id"],
                     "doc": r["doc"],
                     "page_physique": r["page_physique"],
                     "sous_numero": r["sous_numero"]}
                    for r in items
                ],
            }, ensure_ascii=False) + "\n")
        for qid, items in retrieval_par_qid_v2.items():
            dst.write(json.dumps({
                "benchmark": "validation",
                "variante": "v2.1",
                "config": "hybride_filtre",
                "question_id": qid,
                "retrieved_top20": [
                    {"rank": r["rank"], "chunk_id": r["chunk_id"],
                     "doc": r["doc"],
                     "page_physique": r["page_physique"],
                     "sous_numero": r["sous_numero"]}
                    for r in items
                ],
            }, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> int:
    parseur = argparse.ArgumentParser(
        description="Partie B — runs V1.2 + V2 sur le jeu de validation.",
    )
    parseur.add_argument("--model", default=GeminiLLM.DEFAULT_MODEL)
    parseur.add_argument("--interval-s", type=float, default=7.0)
    parseur.add_argument(
        "--only", default=None,
        help="Limite à ces question_ids (séparés par virgule).",
    )
    args = parseur.parse_args()

    print("=" * 72)
    print("PARTIE B — Jeu de validation (15 Q)")
    print("=" * 72)

    questions = charger_benchmark(BENCH_PATH)
    if args.only:
        ids = {s.strip() for s in args.only.split(",") if s.strip()}
        questions = [q for q in questions if q["id"] in ids]
    print(f"Questions chargées : {len(questions)}")

    print("Chargement chunks locaux...")
    chunks = charger_chunks(CHUNKS_DIR)
    chunks_par_id = {c["chunk_id"]: c for c in chunks}
    print(f"  {len(chunks)} chunks")

    print("Chargement cache embeddings (RETRIEVAL_DOCUMENT)...")
    cache = charger_cache_embeddings(CACHE_PATH)
    vecteurs_chunks: dict[str, np.ndarray] = {}
    for c in chunks:
        key = _hash_cle(MODEL_EMBEDDING, TASK_DOCUMENT, c["texte"])
        v = cache.get(key)
        if v is None:
            print(f"  ERREUR : chunk absent du cache : {c['chunk_id']}")
            return 1
        vecteurs_chunks[c["chunk_id"]] = v
    print(f"  {len(vecteurs_chunks)} vecteurs chunks OK")

    print()
    print("Pré-embedding des questions validation (RETRIEVAL_QUERY)...")
    print("  Compteur `_nb_appels_embed` = nombre d'appels API Gemini.")
    vecteurs_q, n_appels_embed = pre_embedder_questions(
        questions, MODEL_EMBEDDING,
    )
    print(f"  **{n_appels_embed} appels API embeddings** (sur "
          f"{len(questions)} Q)")

    prompt_version = prompt_version_v1_2()
    model = args.model
    run_v1_2 = run_id_v1_2_val(model, prompt_version, TOP_K_FINAL)
    run_v2 = run_id_v2_val(model, prompt_version, TOP_K_FINAL)

    print()
    print("Préparation BM25 global V2.1 (stop words NLTK FR filtrés)...")
    bm25_global_v2_1 = IndexBM25(chunks, tokenizer=tokeniser_v2_1)

    print()
    print("=== Run V1.2 (dense) ===")
    print(f"  run_id : {run_v1_2}")
    deja_faits_v1_2 = lire_checkpoint(V1_2_PATH, run_v1_2)
    a_faire_v1_2 = [q for q in questions if q["id"] not in deja_faits_v1_2]
    print(f"  déjà faits : {len(deja_faits_v1_2)}  |  "
          f"à faire : {len(a_faire_v1_2)}")

    print()
    print("=== Run V2 (v2.1/hybride_filtre) ===")
    print(f"  run_id : {run_v2}")
    deja_faits_v2 = lire_checkpoint(V2_PATH, run_v2)
    a_faire_v2 = [q for q in questions if q["id"] not in deja_faits_v2]
    print(f"  déjà faits : {len(deja_faits_v2)}  |  "
          f"à faire : {len(a_faire_v2)}")

    if not a_faire_v1_2 and not a_faire_v2:
        print("Rien à faire, exit.")
        return 0

    llm = creer_llm(provider="gemini", model=model)

    retrieval_top20_v1_2: dict[str, list[dict]] = {}
    retrieval_top20_v2: dict[str, list[dict]] = {}

    # --- V1.2 run ---
    for i, q in enumerate(a_faire_v1_2, start=1):
        qid = q["id"]
        q_vec = vecteurs_q[qid]
        dense_top20 = dense_top_k(
            q_vec, chunks, vecteurs_chunks, TOP_K_SCORING,
        )
        dense_top20_enrichi = enrichir(dense_top20, chunks_par_id)
        retrieval_top20_v1_2[qid] = dense_top20_enrichi
        top5 = dense_top20_enrichi[:TOP_K_FINAL]
        retrieved_avec_texte = [
            {**r, "texte": chunks_par_id[r["chunk_id"]]["texte"]}
            for r in top5
        ]
        contexte = formater_contexte(retrieved_avec_texte)
        print(f"[V1.2 {i}/{len(a_faire_v1_2)}] {qid} "
              f"({q.get('category', '-')})")
        try:
            reponse = generer_reponse(llm, contexte, q["question"])
        except ErreurQuotaJournalier as exc:
            print(message_arret_quota_journalier(
                nb_faits=len(deja_faits_v1_2) + i - 1,
                total=len(questions),
                retry_delay_s=exc.retry_delay_s,
            ))
            return EXIT_CODE_QUOTA_JOURNALIER
        answer_parsed, parse_ok = parser_reponse_v1(reponse.text)
        rec = ligne_resultat(
            provenance="v1_2_validation",
            retrieval_config="dense",
            retrieval_variante="v1_2",
            docs_filtre=None,
            question=q, reponse=reponse,
            retrieved_top5=top5, contexte=contexte,
            answer_parsed=answer_parsed, parse_ok=parse_ok,
            run_id=run_v1_2, prompt_version=prompt_version,
            top_k=TOP_K_FINAL,
        )
        append_jsonl(V1_2_PATH, rec)
        ans = (
            (answer_parsed or {}).get("answer", "<parse_ok=False>")[:80]
        )
        print(f"    -> {ans}  ({reponse.latency_s:.2f} s)")
        if i < len(a_faire_v1_2) or a_faire_v2:
            time.sleep(args.interval_s)

    # --- V2 run ---
    for i, q in enumerate(a_faire_v2, start=1):
        qid = q["id"]
        q_vec = vecteurs_q[qid]
        # On refait le top-20 complet pour scoring (top-5 pour LLM).
        docs_filtre = entreprises_filtre(q["question"])
        top20_pipeline, _ = pipeline_v2_top5(
            question=q, q_vec=q_vec,
            chunks=chunks, chunks_par_id=chunks_par_id,
            vecteurs_chunks=vecteurs_chunks,
            top_final=TOP_K_SCORING,
        )
        retrieval_top20_v2[qid] = top20_pipeline
        top5 = top20_pipeline[:TOP_K_FINAL]
        retrieved_avec_texte = [
            {**r, "texte": chunks_par_id[r["chunk_id"]]["texte"]}
            for r in top5
        ]
        contexte = formater_contexte(retrieved_avec_texte)
        print(f"[V2 {i}/{len(a_faire_v2)}] {qid} "
              f"({q.get('category', '-')})")
        try:
            reponse = generer_reponse(llm, contexte, q["question"])
        except ErreurQuotaJournalier as exc:
            print(message_arret_quota_journalier(
                nb_faits=len(deja_faits_v2) + i - 1,
                total=len(questions),
                retry_delay_s=exc.retry_delay_s,
            ))
            return EXIT_CODE_QUOTA_JOURNALIER
        answer_parsed, parse_ok = parser_reponse_v1(reponse.text)
        rec = ligne_resultat(
            provenance="v2_validation",
            retrieval_config=CONFIG_ID_V2,
            retrieval_variante="v2.1",
            docs_filtre=docs_filtre,
            question=q, reponse=reponse,
            retrieved_top5=top5, contexte=contexte,
            answer_parsed=answer_parsed, parse_ok=parse_ok,
            run_id=run_v2, prompt_version=prompt_version,
            top_k=TOP_K_FINAL,
        )
        append_jsonl(V2_PATH, rec)
        ans = (
            (answer_parsed or {}).get("answer", "<parse_ok=False>")[:80]
        )
        print(f"    -> {ans}  ({reponse.latency_s:.2f} s)")
        if i < len(a_faire_v2):
            time.sleep(args.interval_s)

    # Écriture retrieval compare (top-20 pour les 2 configs)
    if retrieval_top20_v1_2 or retrieval_top20_v2:
        ecrire_retrieval_compare_validation(
            RETRIEVAL_CMP_PATH, retrieval_top20_v1_2,
            retrieval_top20_v2,
        )
        print()
        print(f"Écrit : {RETRIEVAL_CMP_PATH.relative_to(RACINE)}")

    print()
    print("=" * 72)
    print(f"Total appels API embeddings : {n_appels_embed}")
    print(f"Fini V1.2 : {V1_2_PATH.relative_to(RACINE)}")
    print(f"Fini V2   : {V2_PATH.relative_to(RACINE)}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
