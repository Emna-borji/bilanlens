"""Benchmark V3 : reranker cross-encoder sur les 20 candidats
V2.1/hybride_filtre des 31 Q, sans aucun appel LLM.

Pipeline figé (plan V3 §1-§5) :
1. Charge le top-20 V2.1/hybride_filtre depuis
   ``results/retrieval_compare.jsonl``.
2. **Garde-fou amont** : recalcule V2.1/hybride_filtre et exige
   R@5 = 22/27, MRR = 0,7136 sur les 31 Q. Un mismatch stoppe le
   script.
3. Instancie ``Reranker`` (BAAI/bge-reranker-v2-m3, revision
   épinglée).
4. **Mesure les longueurs** tokenisées des 31 × 20 = 620 paires
   (min / médiane / max). Aucune troncation. Lève
   ``LongueurExcedenteError`` si > 8192 tokens.
5. Score + reranke les 20 candidats par Q.
6. Calcule R@1 / 3 / 5 / 10, MRR, gains/pertes vs V2.
7. Affiche les rangs des pages attendues pour Q12, Q13, Q14,
   Q21, Q23.
8. Décision §4 : R@5 strict > 22/27 ?

Sortie : ``results/retrieval_compare_v3.jsonl`` (variante =
`v3_rerank`, config = `bge_reranker_v2_m3`). Aucun appel LLM.
"""
from __future__ import annotations

import gc
import json
import os
import statistics
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from bilanlens.reranker import (  # noqa: E402
    BATCH_SIZE_DEFAULT, MAX_LENGTH, MODEL_NAME, MODEL_REVISION,
    Reranker,
)
from scripts.benchmark_retrieval import (  # noqa: E402
    CONFIGS, charger_chunks,
)
from scripts.evaluate_v1 import pages_attendues, pages_recuperees  # noqa: E402
from scripts.score import _charger_top20_par_variante  # noqa: E402

BENCH_PATH = RACINE / "data" / "benchmark" / "questions.jsonl"
CHUNKS_DIR = RACINE / "data" / "chunks"
RETRIEVAL_CMP_PATH = RACINE / "results" / "retrieval_compare.jsonl"
SORTIE_PATH = RACINE / "results" / "retrieval_compare_v3.jsonl"
# Cache incrémental des scores : une ligne par (question_id,
# chunk_id, score_rerank, timestamp). Permet de reprendre après
# interruption (OOM kill, Ctrl+C).
CACHE_SCORES_PATH = RACINE / "results" / "rerank_scores_cache.jsonl"

BASELINE_V2_1_R5 = 22
BASELINE_V2_1_MRR = 0.7136  # mesuré dans benchmark_retrieval.py

TOP_CANDIDATS = 20
TOP_FINAL = 20  # on garde top-20 pour calculer R@1..R@10 facilement
SEUIL_R5 = 22  # critère §4 : R@5 strict > 22/27

Q_INTERET = [
    "monoprix_consolide_2024_12",  # Q12 texte_annexes
    "monoprix_2024_13",             # Q13 extraction
    "monoprix_2024_14",             # Q14 calcul
    "sfbt_2024_21",                 # Q21 texte_annexes
    "ciments_bizerte_2024_23",      # Q23 calcul (2 pages attendues)
]


# ------------------------------------------------------------------
# Chargement benchmark + V2.1 top-20
# ------------------------------------------------------------------

def charger_benchmark_31() -> list[dict]:
    out = []
    with BENCH_PATH.open(encoding="utf-8") as src:
        for ligne in src:
            ligne = ligne.strip()
            if ligne:
                out.append(json.loads(ligne))
    return out


def charger_top20_v2_1_hybride_filtre() -> dict[str, list[dict]]:
    return _charger_top20_par_variante(
        RETRIEVAL_CMP_PATH, variante="v2.1",
        config="hybride_filtre",
    )


# ------------------------------------------------------------------
# Métriques recall@k et MRR
# ------------------------------------------------------------------

def rangs_pages(
    attendues: set[tuple[str, int]], items: list[dict],
) -> dict[str, int]:
    out = {}
    for doc, page in attendues:
        cle = f"{doc}_p{page}"
        rang = -1
        for r in items:
            if (r.get("doc") == doc
                    and int(r.get("page_physique", -1)) == page):
                rang = int(r["rank"])
                break
        out[cle] = rang
    return out


def recall_at(
    attendues: set[tuple[str, int]], items: list[dict], k: int,
) -> bool:
    top_k = items[:k]
    recuperees = pages_recuperees(top_k)
    return attendues.issubset(recuperees)


def mrr_question(
    attendues: set[tuple[str, int]], items: list[dict],
) -> float:
    if not attendues:
        return 0.0
    for r in items:
        pair = (r.get("doc"), int(r.get("page_physique", -1)))
        if pair in attendues:
            return 1.0 / int(r["rank"])
    return 0.0


# ------------------------------------------------------------------
# Garde-fou amont : V2.1 doit redonner 22/27, 0.7136
# ------------------------------------------------------------------

def valider_baseline_v2_1(
    benchmark: list[dict], top20_v2_1: dict[str, list[dict]],
) -> None:
    """Vérifie que V2.1/hybride_filtre top-20 lu redonne bien
    R@5 = 22/27 et MRR = 0,7136 sur les 31 Q. Lève un
    ``RuntimeError`` sinon (pipeline amont a bougé)."""
    r5 = 0
    mrr_sum = 0.0
    n_q = 0
    for q in benchmark:
        attendues = pages_attendues(q)
        if not attendues:
            continue
        n_q += 1
        items = top20_v2_1.get(q["id"], [])
        if recall_at(attendues, items, 5):
            r5 += 1
        mrr_sum += mrr_question(attendues, items)
    mrr = mrr_sum / n_q if n_q else 0.0
    print(f"  V2.1/hybride_filtre recalculé : "
          f"R@5 = {r5}/{n_q} ; MRR = {mrr:.4f}")
    if r5 != BASELINE_V2_1_R5:
        raise RuntimeError(
            f"Garde-fou amont V2.1 : R@5 attendu = "
            f"{BASELINE_V2_1_R5}/27, obtenu = {r5}/{n_q}. "
            f"Le pipeline amont a bougé."
        )
    if abs(mrr - BASELINE_V2_1_MRR) > 0.001:
        raise RuntimeError(
            f"Garde-fou amont V2.1 : MRR attendu = "
            f"{BASELINE_V2_1_MRR}, obtenu = {mrr:.4f}. "
            f"Le pipeline amont a bougé."
        )
    print("  → Garde-fou OK, baseline V2.1 reproduite.")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> int:
    print("=" * 72)
    print("BENCHMARK V3 — Reranker cross-encoder (sans LLM)")
    print("=" * 72)
    print(f"  Modèle   : {MODEL_NAME}")
    print(f"  Revision : {MODEL_REVISION}")
    print(f"  Max tokens / paire : {MAX_LENGTH}")
    print()

    print("Chargement benchmark 31 Q...")
    benchmark = charger_benchmark_31()
    print(f"  {len(benchmark)} questions")

    print("Chargement chunks...")
    chunks = charger_chunks(CHUNKS_DIR)
    chunks_par_id = {c["chunk_id"]: c for c in chunks}
    print(f"  {len(chunks)} chunks")

    print("Chargement top-20 V2.1/hybride_filtre...")
    top20_v2_1 = charger_top20_v2_1_hybride_filtre()
    print(f"  {len(top20_v2_1)} questions couvertes")

    print()
    print("Garde-fou amont :")
    valider_baseline_v2_1(benchmark, top20_v2_1)

    print()
    print("Instanciation Reranker...")
    t0 = time.perf_counter()
    rk = Reranker()
    t_init = time.perf_counter() - t0
    print(f"  Chargé en {t_init:.1f} s sur {rk.device}")

    # Phase 1 : mesurer les longueurs
    print()
    print("Phase 1 — Mesure des longueurs de paires (31 Q × 20 cand)...")
    toutes_longueurs: list[int] = []
    for q in benchmark:
        candidats = top20_v2_1.get(q["id"], [])
        for c in candidats:
            texte = chunks_par_id[c["chunk_id"]]["texte"]
            toutes_longueurs.append(
                rk.mesurer_longueur(q["question"], texte)
            )
    longueurs = toutes_longueurs
    mini = min(longueurs)
    maxi = max(longueurs)
    median = int(statistics.median(longueurs))
    print(f"  {len(longueurs)} paires mesurées")
    print(f"  Longueur min / médiane / max : "
          f"{mini} / {median} / {maxi} tokens")
    print(f"  Aucune paire ne dépasse {MAX_LENGTH} tokens : "
          f"{all(n <= MAX_LENGTH for n in longueurs)}")
    if max(longueurs) > MAX_LENGTH:
        depassantes = sum(1 for n in longueurs if n > MAX_LENGTH)
        print(f"  ERREUR : {depassantes} paires dépassent "
              f"{MAX_LENGTH} tokens → arrêt.")
        return 2

    # Phase 2 : scorer les 20 candidats par Q, par lots de 2, avec
    # cache incrémental pour reprise si interruption.
    import psutil
    proc = psutil.Process(os.getpid())

    def rss_mb() -> float:
        return proc.memory_info().rss / (1024 ** 2)

    def charger_cache_scores() -> dict[tuple[str, str], float]:
        if not CACHE_SCORES_PATH.exists():
            return {}
        out: dict[tuple[str, str], float] = {}
        with CACHE_SCORES_PATH.open(encoding="utf-8") as src:
            for ligne in src:
                ligne = ligne.strip()
                if not ligne:
                    continue
                r = json.loads(ligne)
                if r.get("model_revision") != MODEL_REVISION:
                    continue  # scores d'une autre révision : ignorer
                out[(r["question_id"], r["chunk_id"])] = r["score_rerank"]
        return out

    def appender_scores_batch(entries: list[dict]) -> None:
        CACHE_SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CACHE_SCORES_PATH.open("a", encoding="utf-8") as dst:
            for e in entries:
                dst.write(json.dumps(e, ensure_ascii=False) + "\n")

    print()
    print(f"Phase 2 — Reranking par lots de {BATCH_SIZE_DEFAULT} "
          f"(résumable via {CACHE_SCORES_PATH.name})...")
    cache_scores = charger_cache_scores()
    if cache_scores:
        print(f"  Cache existant : {len(cache_scores)} paires "
              f"(revision {MODEL_REVISION[:8]}...)")
    print(f"  RSS avant scoring : {rss_mb():.0f} MB")

    rss_peak = rss_mb()
    scores_par_q: dict[str, dict[str, float]] = {}
    t0 = time.perf_counter()
    for i, q in enumerate(benchmark, start=1):
        qid = q["id"]
        candidats = top20_v2_1.get(qid, [])
        scores_q: dict[str, float] = {}
        a_scorer: list[tuple[int, dict]] = []
        for j, c in enumerate(candidats):
            cle = (qid, c["chunk_id"])
            if cle in cache_scores:
                scores_q[c["chunk_id"]] = cache_scores[cle]
            else:
                a_scorer.append((j, c))
        if a_scorer:
            pairs = [
                (q["question"],
                 chunks_par_id[c["chunk_id"]]["texte"])
                for _, c in a_scorer
            ]
            nouveaux_scores = rk.score_pairs(pairs)
            nouveaux_entries = []
            for (_, c), s in zip(a_scorer, nouveaux_scores):
                scores_q[c["chunk_id"]] = float(s)
                nouveaux_entries.append({
                    "model_revision": MODEL_REVISION,
                    "question_id": qid,
                    "chunk_id": c["chunk_id"],
                    "score_rerank": float(s),
                })
            appender_scores_batch(nouveaux_entries)
        scores_par_q[qid] = scores_q
        rss = rss_mb()
        if rss > rss_peak:
            rss_peak = rss
        if i % 5 == 0 or i == len(benchmark):
            dt = time.perf_counter() - t0
            print(f"  [{i}/{len(benchmark)}] scorés  "
                  f"({dt:.1f} s cumulé, RSS={rss:.0f} MB, "
                  f"peak={rss_peak:.0f} MB)")
        gc.collect()
    t_rerank = time.perf_counter() - t0
    print(f"  Temps total reranking : {t_rerank:.1f} s")
    print(f"  RSS pic : {rss_peak:.0f} MB")

    # Reconstruction des top-20 rerankés avec tie-break chunk_id
    resultats_par_q: dict[str, list[dict]] = {}
    for q in benchmark:
        qid = q["id"]
        candidats = top20_v2_1.get(qid, [])
        if not candidats:
            resultats_par_q[qid] = []
            continue
        scored = [
            {
                "chunk_id": c["chunk_id"],
                "score_rerank": scores_par_q[qid][c["chunk_id"]],
                "doc": c.get("doc"),
                "page_physique": c.get("page_physique"),
                "sous_numero": c.get("sous_numero", 0),
            }
            for c in candidats
        ]
        # Tri par score décroissant, tie-break chunk_id croissant
        scored.sort(key=lambda r: (-r["score_rerank"], r["chunk_id"]))
        resultats_par_q[qid] = [
            {**r, "rank": rang}
            for rang, r in enumerate(scored[:TOP_FINAL], start=1)
        ]

    # Phase 3 : métriques
    print()
    print("Phase 3 — Métriques retrieval (27 Q avec page attendue)...")
    recalls: dict[int, int] = {1: 0, 3: 0, 5: 0, 10: 0}
    mrr_sum = 0.0
    n_q = 0
    recall_at_5_par_qid: dict[str, bool] = {}
    for q in benchmark:
        attendues = pages_attendues(q)
        if not attendues:
            continue
        n_q += 1
        items = resultats_par_q[q["id"]]
        for k in recalls:
            if recall_at(attendues, items, k):
                recalls[k] += 1
        recall_at_5_par_qid[q["id"]] = recall_at(attendues, items, 5)
        mrr_sum += mrr_question(attendues, items)
    mrr = mrr_sum / n_q if n_q else 0.0

    # V2 recall@5 par Q, pour gains/pertes
    recall_at_5_v2_par_qid: dict[str, bool] = {}
    for q in benchmark:
        attendues = pages_attendues(q)
        if not attendues:
            continue
        items_v2 = top20_v2_1.get(q["id"], [])
        recall_at_5_v2_par_qid[q["id"]] = recall_at(attendues, items_v2, 5)

    gains = [
        qid for qid in sorted(recall_at_5_par_qid)
        if recall_at_5_par_qid[qid] and not recall_at_5_v2_par_qid[qid]
    ]
    pertes = [
        qid for qid in sorted(recall_at_5_par_qid)
        if not recall_at_5_par_qid[qid] and recall_at_5_v2_par_qid[qid]
    ]

    # Écrire sortie
    print()
    print(f"Écriture : {SORTIE_PATH.relative_to(RACINE)}")
    SORTIE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SORTIE_PATH.open("w", encoding="utf-8") as dst:
        for q in benchmark:
            items = resultats_par_q[q["id"]]
            dst.write(json.dumps({
                "variante": "v3_rerank",
                "config": "bge_reranker_v2_m3",
                "model_revision": MODEL_REVISION,
                "question_id": q["id"],
                "retrieved_top20": [
                    {"rank": r["rank"], "chunk_id": r["chunk_id"],
                     "doc": r["doc"],
                     "page_physique": r["page_physique"],
                     "sous_numero": r.get("sous_numero", 0),
                     "score_rerank": r["score_rerank"]}
                    for r in items
                ],
            }, ensure_ascii=False) + "\n")

    # Affichage des métriques
    print()
    print("=" * 72)
    print(f"RÉSULTATS V3 (reranker) sur {n_q} Q avec page attendue")
    print("=" * 72)
    print(f"  Recall@1  : {recalls[1]:>3}/{n_q}")
    print(f"  Recall@3  : {recalls[3]:>3}/{n_q}")
    print(f"  Recall@5  : {recalls[5]:>3}/{n_q}  "
          f"(V2 baseline = {BASELINE_V2_1_R5}/{n_q})")
    print(f"  Recall@10 : {recalls[10]:>3}/{n_q}")
    print(f"  MRR       : {mrr:.4f}  "
          f"(V2 baseline = {BASELINE_V2_1_MRR:.4f})")

    print()
    print("Gains / pertes vs V2 au R@5 :")
    print(f"  Gains  ({len(gains)}) : "
          f"{', '.join(gains) if gains else '(aucun)'}")
    print(f"  Pertes ({len(pertes)}) : "
          f"{', '.join(pertes) if pertes else '(aucune)'}")
    print(f"  Net    : +{len(gains) - len(pertes)}")

    print()
    print("Rangs des pages attendues — 5 Q d'intérêt :")
    print(f"{'qid':<35} {'V2 (rangs)':<22} {'V3 rerank (rangs)':<22}")
    for qid in Q_INTERET:
        q = next((x for x in benchmark if x["id"] == qid), None)
        if not q:
            continue
        attendues = pages_attendues(q)
        r_v2 = rangs_pages(attendues, top20_v2_1.get(qid, []))
        r_v3 = rangs_pages(attendues, resultats_par_q.get(qid, []))

        def fmt(r):
            return ",".join(str(v) if v != -1 else "-"
                            for v in r.values())
        print(f"{qid:<35} {fmt(r_v2):<22} {fmt(r_v3):<22}")

    print()
    print("Temps et mémoire :")
    print(f"  Chargement modèle : {t_init:.1f} s")
    print(f"  Reranking total : {t_rerank:.1f} s "
          f"(batch_size={BATCH_SIZE_DEFAULT})")
    print(f"  RSS pic : {rss_peak:.0f} MB")

    print()
    print("=" * 72)
    print(f"DÉCISION §4 (critère : Recall@5 strict > {SEUIL_R5}/27)")
    print("=" * 72)
    if recalls[5] > SEUIL_R5:
        print(f"  V3 reranker R@5 = {recalls[5]}/{n_q} > "
              f"{SEUIL_R5}/{n_q} STRICT → V3 retenue.")
        print(f"  Feu vert pour UN run LLM V3 avec le reranker.")
    else:
        print(f"  V3 reranker R@5 = {recalls[5]}/{n_q} ≤ "
              f"{SEUIL_R5}/{n_q} → **V3 NON retenue**.")
        print(f"  On garde V2 (v2.1/hybride_filtre). "
              f"PAS de run LLM V3.")

    # Longueurs écrites pour le journal
    print()
    print("Longueurs tokenisées (31 Q × 20 cand = 620 paires) :")
    print(f"  min = {mini} ; médiane = {median} ; max = {maxi}")
    print(f"  Toutes ≤ {MAX_LENGTH} tokens : "
          f"{all(n <= MAX_LENGTH for n in longueurs)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
