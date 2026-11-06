"""Benchmark retrieval V2 : 5 configurations SANS appel LLM.

Compare `dense`, `bm25`, `hybride_rrf`, `dense_filtre`,
`hybride_filtre` sur les 31 questions du benchmark.

Pipeline figé (plan V2 §2 et §3) :
- Embeddings chunks + questions lus depuis le cache local
  (``data/cache_embeddings/gemini-embedding-2.jsonl``). Aucun
  appel réseau tant que ces vecteurs sont déjà en cache : c'est
  ce que V1 a construit lors de l'indexation.
- Cosine exact sur vecteurs unit-norm Gemini (produit scalaire).
- BM25 via ``bilanlens.bm25.IndexBM25`` (k1=1.5, b=0.75).
- Fusion RRF (k=60) sur listes top-50.
- Filtre entreprise selon ``bilanlens.filtre_question``,
  appliqué AVANT la construction des listes top-50 (pour les
  2 configs filtrées).
- Tie-break : chunk_id alphanumérique croissant partout.

Écrit ``results/retrieval_compare.jsonl`` (une ligne par
(config, question)) et imprime à l'écran :
- Recall@1/3/5/10/20 + MRR pour chaque config.
- Rangs des pages attendues pour les 6 Q d'intérêt
  (Q12, Q14, Q21, Q23, Q25, Q30).
- Questions gagnées / perdues par chaque config vs dense.
- La configuration retenue par le critère §4 (Recall@5 strict
  > 19/27, départagé par MRR, garde-fou couverture 100 %).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bilanlens.bm25 import IndexBM25, tokeniser, tokeniser_v2_1  # noqa: E402
from bilanlens.filtre_question import entreprises_filtre  # noqa: E402
from bilanlens.retrieval_hybride import (  # noqa: E402
    K_RRF,
    TAILLE_LISTES_AVANT_FUSION,
    fusionner_rrf,
    marquer_source,
)
from scripts.evaluate_v1 import pages_attendues, pages_recuperees  # noqa: E402

MODEL = "gemini-embedding-2"
TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_QUERY = "RETRIEVAL_QUERY"

CACHE_PATH = ROOT / "data" / "cache_embeddings" / f"{MODEL}.jsonl"
CHUNKS_DIR = ROOT / "data" / "chunks"
BENCHMARK_PATH = ROOT / "data" / "benchmark" / "questions.jsonl"
TOP20_V1_PATH = ROOT / "results" / "retrieval_top20.jsonl"
SORTIE_PATH = ROOT / "results" / "retrieval_compare.jsonl"

CONFIGS = [
    "dense",
    "bm25",
    "hybride_rrf",
    "dense_filtre",
    "hybride_filtre",
]

Q_INTERET = [
    "monoprix_consolide_2024_12",
    "monoprix_2024_14",
    "sfbt_2024_21",
    "ciments_bizerte_2024_23",
    "ciments_bizerte_2024_25",
    "delice_holding_2024_30",
]

SEUIL_RECALL_5 = 19  # dense V1 (baseline). On veut STRICTEMENT >.


# ------------------------------------------------------------------
# Lecture cache embeddings
# ------------------------------------------------------------------

def _hash_cle(model: str, task_type: str, texte: str) -> str:
    """Même formule que bilanlens.embeddings : sha256(model|task|texte)."""
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"|")
    h.update(task_type.encode("utf-8"))
    h.update(b"|")
    h.update(texte.encode("utf-8"))
    return h.hexdigest()


def charger_cache_embeddings(path: Path) -> dict[str, np.ndarray]:
    """Lit le jsonl cache ``{key, vec}`` et retourne {key: vec}."""
    out: dict[str, np.ndarray] = {}
    with path.open(encoding="utf-8") as src:
        for ligne in src:
            ligne = ligne.strip()
            if not ligne:
                continue
            r = json.loads(ligne)
            out[r["key"]] = np.array(r["vec"], dtype=np.float32)
    return out


# ------------------------------------------------------------------
# Chargement chunks + questions
# ------------------------------------------------------------------

def charger_chunks(chunks_dir: Path) -> list[dict]:
    chunks: list[dict] = []
    for f in sorted(chunks_dir.glob("*.jsonl")):
        with f.open(encoding="utf-8") as src:
            for ligne in src:
                ligne = ligne.strip()
                if not ligne:
                    continue
                r = json.loads(ligne)
                cid = (f"{r['doc']}_p{r['page_physique']}"
                       f"_s{r.get('sous_numero', 0)}")
                r["chunk_id"] = cid
                chunks.append(r)
    return chunks


def charger_benchmark(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as src:
        for ligne in src:
            ligne = ligne.strip()
            if ligne:
                out.append(json.loads(ligne))
    return out


# ------------------------------------------------------------------
# Dense retrieval depuis vecteurs cache
# ------------------------------------------------------------------

def dense_top_k(
    q_vec: np.ndarray,
    chunks: list[dict],
    vecteurs_chunks: dict[str, np.ndarray],
    top_k: int,
    chunk_ids_filtre: set[str] | None = None,
) -> list[dict]:
    """Cosine sur vecteurs unit-norm (dot product).

    ``chunk_ids_filtre`` : si fourni, restreint la recherche à ces
    chunk_ids (filtre AVANT calcul des scores, cf. §2 du plan V2).
    Tie-break : chunk_id alphanumérique croissant.
    """
    scores: list[tuple[str, float]] = []
    for c in chunks:
        cid = c["chunk_id"]
        if chunk_ids_filtre is not None and cid not in chunk_ids_filtre:
            continue
        v = vecteurs_chunks.get(cid)
        if v is None:
            continue
        sim = float(np.dot(q_vec, v))
        scores.append((cid, sim))
    scores.sort(key=lambda t: (-t[1], t[0]))
    top = scores[:top_k]
    return [
        {"rank": i + 1, "chunk_id": cid, "score": sim,
         "distance": 1.0 - sim}
        for i, (cid, sim) in enumerate(top)
    ]


# ------------------------------------------------------------------
# Enrichissement résultat : ajoute doc + page_physique
# ------------------------------------------------------------------

def enrichir(
    resultats: list[dict], chunks_par_id: dict[str, dict],
) -> list[dict]:
    """Ajoute doc, page_physique, sous_numero depuis chunks_par_id."""
    out = []
    for r in resultats:
        c = chunks_par_id.get(r["chunk_id"], {})
        out.append({
            **r,
            "doc": c.get("doc"),
            "page_physique": c.get("page_physique"),
            "sous_numero": c.get("sous_numero", 0),
        })
    return out


# ------------------------------------------------------------------
# Métriques
# ------------------------------------------------------------------

def rangs_pages_attendues(
    attendues: set[tuple[str, int]], resultats: list[dict],
) -> dict[str, int]:
    rangs: dict[str, int] = {}
    for doc, page in attendues:
        cle = f"{doc}_p{page}"
        rang = None
        for r in resultats:
            if r.get("doc") == doc and int(r.get("page_physique", -1)) == page:
                rang = int(r["rank"])
                break
        rangs[cle] = rang if rang is not None else -1
    return rangs


def recall_at(attendues: set[tuple[str, int]], resultats: list[dict],
              k: int) -> bool:
    top_k = resultats[:k]
    recuperees = pages_recuperees(top_k)
    return attendues.issubset(recuperees)


def mrr_question(
    attendues: set[tuple[str, int]], resultats: list[dict],
) -> float:
    """Rang réciproque de la PREMIÈRE page attendue trouvée. 0 si
    aucune. Pour une Q sans page attendue (sans_reponse) retourne 0."""
    if not attendues:
        return 0.0
    for r in resultats:
        pair = (r.get("doc"), int(r.get("page_physique", -1)))
        if pair in attendues:
            return 1.0 / int(r["rank"])
    return 0.0


# ------------------------------------------------------------------
# Validation : dense recalculé == V1 ?
# ------------------------------------------------------------------

def valider_dense_vs_v1(
    resultats_dense_par_qid: dict[str, list[dict]],
    top20_v1_path: Path,
) -> tuple[bool, list[str]]:
    """Vérifie que les 20 premiers chunk_ids du dense recalculé
    coïncident avec ceux de retrieval_top20.jsonl pour chaque Q.
    Retourne (ok_global, erreurs par Q).
    """
    erreurs: list[str] = []
    with top20_v1_path.open(encoding="utf-8") as src:
        for ligne in src:
            ligne = ligne.strip()
            if not ligne:
                continue
            r = json.loads(ligne)
            qid = r["question_id"]
            v1 = [item["chunk_id"] for item in sorted(
                r["top20"], key=lambda x: int(x["rank"]))]
            v2 = [item["chunk_id"]
                  for item in resultats_dense_par_qid.get(qid, [])[:20]]
            if v1 != v2:
                erreurs.append(
                    f"{qid}\n  V1 : {v1}\n  NEW: {v2}"
                )
    return (not erreurs, erreurs)


# ------------------------------------------------------------------
# Pipeline : les 5 configs pour une question
# ------------------------------------------------------------------

def lancer_5_configs(
    question: dict,
    q_vec: np.ndarray,
    chunks: list[dict],
    chunks_par_id: dict[str, dict],
    vecteurs_chunks: dict[str, np.ndarray],
    bm25_global: IndexBM25,
    top_fusion: int,
    top_final: int,
    tokenizer=tokeniser,
) -> dict[str, list[dict]]:
    """Lance les 5 configs pour une question. Retourne un dict
    {nom_config : top_final résultats enrichis (doc, page)}.

    ``tokenizer`` sert uniquement à reconstruire l'index BM25
    filtré sur le sous-périmètre d'entreprise, avec les mêmes
    règles de tokenisation que ``bm25_global``.
    """
    out: dict[str, list[dict]] = {}

    # --- dense (global) ---
    dense_top50 = dense_top_k(
        q_vec, chunks, vecteurs_chunks, top_fusion,
    )
    out["dense"] = enrichir(dense_top50[:top_final], chunks_par_id)

    # --- bm25 (global) ---
    bm25_top50 = bm25_global.rechercher(question["question"], top_fusion)
    out["bm25"] = enrichir(bm25_top50[:top_final], chunks_par_id)

    # --- hybride RRF (global) ---
    fusion = fusionner_rrf(
        [marquer_source(dense_top50, "dense"),
         marquer_source(bm25_top50, "bm25")],
        top_k=top_final,
    )
    out["hybride_rrf"] = enrichir(fusion, chunks_par_id)

    # --- filtre entreprise ---
    docs_filtre = entreprises_filtre(question["question"])
    if docs_filtre is None:
        # Entreprise non reconnue → pas de filtre, on retombe sur
        # dense/bm25 globaux (par souci de clarté, on duplique).
        dense_filtre_top50 = dense_top50
        bm25_filtre_top50 = bm25_top50
    else:
        chunk_ids_perimetre = {
            c["chunk_id"] for c in chunks if c["doc"] in docs_filtre
        }
        dense_filtre_top50 = dense_top_k(
            q_vec, chunks, vecteurs_chunks, top_fusion,
            chunk_ids_filtre=chunk_ids_perimetre,
        )
        # BM25 filtré : on reconstruit un index sur le sous-ensemble
        # (IDF recalculé sur le périmètre, cf. §3). Même tokenizer
        # que l'index global.
        chunks_perimetre = [
            c for c in chunks if c["doc"] in docs_filtre
        ]
        bm25_filtre = IndexBM25(chunks_perimetre, tokenizer=tokenizer)
        bm25_filtre_top50 = bm25_filtre.rechercher(
            question["question"], top_fusion,
        )

    out["dense_filtre"] = enrichir(
        dense_filtre_top50[:top_final], chunks_par_id,
    )
    fusion_filtre = fusionner_rrf(
        [marquer_source(dense_filtre_top50, "dense"),
         marquer_source(bm25_filtre_top50, "bm25")],
        top_k=top_final,
    )
    out["hybride_filtre"] = enrichir(fusion_filtre, chunks_par_id)

    return out


# ------------------------------------------------------------------
# Agrégation métriques par config
# ------------------------------------------------------------------

def agreger(
    resultats_par_config: dict[str, dict[str, list[dict]]],
    benchmark: list[dict],
) -> dict[str, dict]:
    """Pour chaque config, calcule R@k et MRR sur les 27 Q avec
    page attendue + le nombre de Q couvertes par le filtre.
    """
    stats: dict[str, dict] = {}
    ks = [1, 3, 5, 10, 20]
    for config in CONFIGS:
        recalls = {k: 0 for k in ks}
        mrr_sum = 0.0
        n_q_avec_page = 0
        for q in benchmark:
            attendues = pages_attendues(q)
            if not attendues:
                continue
            n_q_avec_page += 1
            resultats = resultats_par_config[q["id"]][config]
            for k in ks:
                if recall_at(attendues, resultats, k):
                    recalls[k] += 1
            mrr_sum += mrr_question(attendues, resultats)
        stats[config] = {
            "recall_at": {k: recalls[k] for k in ks},
            "n_q_avec_page": n_q_avec_page,
            "mrr": mrr_sum / n_q_avec_page if n_q_avec_page else 0.0,
        }
    return stats


# ------------------------------------------------------------------
# Choix de configuration selon §4
# ------------------------------------------------------------------

def choisir_configuration(
    stats_par_variante: dict[str, dict[str, dict]],
) -> tuple[tuple[str, str] | None, str]:
    """§4 : meilleur R@5 strictement > SEUIL_RECALL_5 toutes variantes.

    Entrée : {variante: {config: {recall_at, mrr, ...}}}.
    Sortie : ((variante, config), justification) ou (None, ...).
    """
    candidats = []
    for variante, stats in stats_par_variante.items():
        for nom, s in stats.items():
            candidats.append(
                (variante, nom, s["recall_at"][5], s["mrr"])
            )
    # Tri par R@5 décroissant, MRR décroissant.
    candidats.sort(key=lambda t: (-t[2], -t[3]))
    tete = candidats[0]
    if tete[2] <= SEUIL_RECALL_5:
        return None, (
            f"Aucune config ne dépasse strictement "
            f"{SEUIL_RECALL_5}/27 au Recall@5. Meilleure : "
            f"{tete[0]}/{tete[1]} à {tete[2]}/27. "
            f"→ On garde le dense V1, pas de run LLM V2."
        )
    egaux = [
        c for c in candidats if c[2] == tete[2] and c[3] == tete[3]
    ]
    if len(egaux) > 1:
        # Départage par simplicité : préférer V2 à V2.1, puis
        # l'ordre canonique des configs.
        rang_config = {c: i for i, c in enumerate(CONFIGS)}
        rang_variante = {"v2": 0, "v2.1": 1}
        egaux.sort(
            key=lambda t: (rang_variante[t[0]], rang_config[t[1]])
        )
        v, c = egaux[0][0], egaux[0][1]
        return (v, c), (
            f"Config retenue : {v}/{c} (R@5={tete[2]}/27, "
            f"MRR={tete[3]:.4f}). Égalité départagée par simplicité "
            f"(V2 avant V2.1, config la plus simple)."
        )
    return (tete[0], tete[1]), (
        f"Config retenue : {tete[0]}/{tete[1]} "
        f"(R@5={tete[2]}/27, MRR={tete[3]:.4f})."
    )


# ------------------------------------------------------------------
# Rapport console
# ------------------------------------------------------------------

def _table_configs(stats: dict[str, dict], titre: str) -> None:
    print("=" * 72)
    print(titre)
    print("=" * 72)
    print(f"{'Config':<20} {'R@1':>5} {'R@3':>5} {'R@5':>5} "
          f"{'R@10':>5} {'R@20':>5} {'MRR':>8}")
    for config in CONFIGS:
        s = stats[config]
        print(f"{config:<20} "
              f"{s['recall_at'][1]:>5} {s['recall_at'][3]:>5} "
              f"{s['recall_at'][5]:>5} {s['recall_at'][10]:>5} "
              f"{s['recall_at'][20]:>5} {s['mrr']:>8.4f}")


def _diff_gains_pertes(
    variante: str,
    resultats_par_config: dict[str, dict[str, list[dict]]],
    benchmark: list[dict],
) -> None:
    print(f"\n[{variante}] Gains / pertes vs dense (R@5)")
    dense_ok_par_qid = {}
    for q in benchmark:
        attendues = pages_attendues(q)
        if not attendues:
            continue
        dense_ok_par_qid[q["id"]] = recall_at(
            attendues, resultats_par_config[q["id"]]["dense"], 5,
        )
    for config in CONFIGS:
        if config == "dense":
            continue
        gains, pertes = [], []
        for q in benchmark:
            attendues = pages_attendues(q)
            if not attendues:
                continue
            ok = recall_at(
                attendues, resultats_par_config[q["id"]][config], 5,
            )
            dense_ok = dense_ok_par_qid[q["id"]]
            if ok and not dense_ok:
                gains.append(q["id"])
            elif dense_ok and not ok:
                pertes.append(q["id"])
        print(f"  {config}:")
        print(f"    + gains  ({len(gains)}) : "
              f"{', '.join(gains) if gains else '(aucun)'}")
        print(f"    - pertes ({len(pertes)}) : "
              f"{', '.join(pertes) if pertes else '(aucune)'}")


def _rangs_q_interet(
    variante: str,
    resultats_par_config: dict[str, dict[str, list[dict]]],
    benchmark_par_qid: dict[str, dict],
) -> None:
    print(f"\n[{variante}] Rangs des pages attendues — 6 Q d'intérêt")
    print(f"{'qid':<32} ", end="")
    for config in CONFIGS:
        print(f"{config[:14]:>14} ", end="")
    print()
    for qid in Q_INTERET:
        q = benchmark_par_qid[qid]
        attendues = pages_attendues(q)
        print(f"{qid:<32} ", end="")
        for config in CONFIGS:
            rangs = rangs_pages_attendues(
                attendues, resultats_par_config[qid][config],
            )
            txt = ",".join(
                str(v) if v != -1 else "-" for v in rangs.values()
            ) or "(aucune)"
            print(f"{txt:>14} ", end="")
        print()


def _config_elue_entre_q_sensibles_dans_top5(
    config_elue_pair: tuple[str, str],
    resultats_par_variante: dict[str, dict[str, dict[str, list[dict]]]],
    benchmark_par_qid: dict[str, dict],
) -> None:
    """Pour la config élue, indique si Q12/Q21/Q25/Q30 passent en top-5."""
    variante, config = config_elue_pair
    print()
    print(f"  Impact sur Q12, Q21, Q25, Q30 "
          f"(les 4 problemes_recherche V1) — top-5 ?")
    qids_sensibles = [
        "monoprix_consolide_2024_12",
        "sfbt_2024_21",
        "ciments_bizerte_2024_25",
        "delice_holding_2024_30",
    ]
    for qid in qids_sensibles:
        q = benchmark_par_qid[qid]
        attendues = pages_attendues(q)
        resultats = resultats_par_variante[variante][qid][config]
        dans_top5 = recall_at(attendues, resultats, 5)
        rangs = rangs_pages_attendues(attendues, resultats)
        rangs_txt = ",".join(
            str(v) if v != -1 else "-" for v in rangs.values()
        )
        statut = "DANS top-5" if dans_top5 else "HORS top-5"
        print(f"    {qid:<32} rangs={rangs_txt:<10} {statut}")


def imprimer_rapport(
    stats_par_variante: dict[str, dict[str, dict]],
    resultats_par_variante: dict[str, dict[str, dict[str, list[dict]]]],
    benchmark: list[dict],
    filtres_par_qid: dict[str, list[str] | None],
) -> None:
    benchmark_par_qid = {q["id"]: q for q in benchmark}

    # Table V2
    _table_configs(
        stats_par_variante["v2"],
        "V2 — tokenisation stop-words CONSERVÉS (sur 27 Q avec page)",
    )
    print()
    # Table V2.1
    _table_configs(
        stats_par_variante["v2.1"],
        "V2.1 — tokenisation stop-words FILTRÉS (NLTK FR, post-hoc)",
    )
    print()

    # Diff V2.1 vs V2 au R@5
    print("=" * 72)
    print("Évolution V2 → V2.1 au R@5 (Δ = V2.1 - V2)")
    print("=" * 72)
    print(f"{'Config':<20} {'V2 R@5':>8} {'V2.1 R@5':>10} {'Δ':>6} "
          f"{'V2 MRR':>8} {'V2.1 MRR':>10} {'ΔMRR':>8}")
    for config in CONFIGS:
        v2 = stats_par_variante["v2"][config]
        v2_1 = stats_par_variante["v2.1"][config]
        diff_r5 = v2_1["recall_at"][5] - v2["recall_at"][5]
        diff_mrr = v2_1["mrr"] - v2["mrr"]
        signe = "+" if diff_r5 > 0 else ("±" if diff_r5 == 0 else "")
        print(f"{config:<20} "
              f"{v2['recall_at'][5]:>8} "
              f"{v2_1['recall_at'][5]:>10} "
              f"{signe}{diff_r5:>5} "
              f"{v2['mrr']:>8.4f} "
              f"{v2_1['mrr']:>10.4f} "
              f"{diff_mrr:>+8.4f}")
    print()

    # Rangs 6 Q d'intérêt par variante
    print("=" * 72)
    print("Rangs des pages attendues — 6 Q d'intérêt")
    print("=" * 72)
    for variante in ("v2", "v2.1"):
        _rangs_q_interet(
            variante, resultats_par_variante[variante], benchmark_par_qid,
        )
    print()

    # Gains / pertes par variante
    print("=" * 72)
    print("Gains / pertes vs dense (R@5)")
    print("=" * 72)
    for variante in ("v2", "v2.1"):
        _diff_gains_pertes(
            variante, resultats_par_variante[variante], benchmark,
        )
    print()

    # Couverture filtre
    print("=" * 72)
    print("Couverture du filtre entreprise (sur 31 Q)")
    print("=" * 72)
    filtre_mono = sum(1 for v in filtres_par_qid.values()
                      if v is not None and len(v) == 1)
    filtre_ambigu = sum(1 for v in filtres_par_qid.values()
                        if v is not None and len(v) > 1)
    sans_filtre = sum(1 for v in filtres_par_qid.values() if v is None)
    print(f"  Q à entreprise unique        : {filtre_mono}/31")
    print(f"  Q à 2 docs (Monoprix ambigu) : {filtre_ambigu}/31")
    print(f"  Q sans filtre (hors scope)   : {sans_filtre}/31")
    print()

    # §4 sur l'ensemble (V2 + V2.1)
    print("=" * 72)
    print("Décision §4 (critère INCHANGÉ : R@5 strictement > 19/27)")
    print("=" * 72)
    pair_elue, justification = choisir_configuration(stats_par_variante)
    print(f"  {justification}")
    if pair_elue:
        _config_elue_entre_q_sensibles_dans_top5(
            pair_elue, resultats_par_variante, benchmark_par_qid,
        )
        print()
        print(f"  → Feu vert pour UN run LLM V2 avec la config : "
              f"{pair_elue[0]}/{pair_elue[1]}")
    else:
        print("  → PAS de run LLM V2. On reste sur dense V1 "
              "(V1.2 figé).")
    print()


# ------------------------------------------------------------------
# Écriture jsonl
# ------------------------------------------------------------------

def ecrire_sortie(
    sortie_path: Path,
    resultats_par_variante: dict[str, dict[str, dict[str, list[dict]]]],
    filtres_par_qid: dict[str, list[str] | None],
    benchmark: list[dict],
) -> None:
    """Écrit une ligne par (variante, config, question)."""
    sortie_path.parent.mkdir(parents=True, exist_ok=True)
    with sortie_path.open("w", encoding="utf-8") as dst:
        for variante, resultats_par_config in resultats_par_variante.items():
            for q in benchmark:
                qid = q["id"]
                for config in CONFIGS:
                    record = {
                        "variante": variante,
                        "question_id": qid,
                        "config": config,
                        "filtre_entreprise": filtres_par_qid[qid],
                        "retrieved_top20": [
                            {"rank": r["rank"], "chunk_id": r["chunk_id"],
                             "doc": r["doc"],
                             "page_physique": r["page_physique"],
                             "sous_numero": r["sous_numero"]}
                            for r in resultats_par_config[qid][config]
                        ],
                    }
                    dst.write(
                        json.dumps(record, ensure_ascii=False) + "\n"
                    )


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> int:
    print("Chargement cache embeddings...")
    cache = charger_cache_embeddings(CACHE_PATH)
    print(f"  {len(cache)} entrées en cache")

    print("Chargement chunks...")
    chunks = charger_chunks(CHUNKS_DIR)
    chunks_par_id = {c["chunk_id"]: c for c in chunks}
    print(f"  {len(chunks)} chunks sur {len(set(c['doc'] for c in chunks))} docs")

    print("Chargement questions benchmark...")
    benchmark = charger_benchmark(BENCHMARK_PATH)
    print(f"  {len(benchmark)} questions")

    print("Résolution vecteurs chunks (cache RETRIEVAL_DOCUMENT)...")
    vecteurs_chunks: dict[str, np.ndarray] = {}
    absents_chunks = []
    for c in chunks:
        key = _hash_cle(MODEL, TASK_DOCUMENT, c["texte"])
        v = cache.get(key)
        if v is None:
            absents_chunks.append(c["chunk_id"])
        else:
            vecteurs_chunks[c["chunk_id"]] = v
    if absents_chunks:
        print(f"  ERREUR : {len(absents_chunks)} chunks absents du cache :")
        for cid in absents_chunks[:5]:
            print(f"    - {cid}")
        return 1
    print(f"  {len(vecteurs_chunks)} vecteurs chunks OK")

    print("Résolution vecteurs questions (cache RETRIEVAL_QUERY)...")
    vecteurs_q: dict[str, np.ndarray] = {}
    absents_q = []
    for q in benchmark:
        key = _hash_cle(MODEL, TASK_QUERY, q["question"])
        v = cache.get(key)
        if v is None:
            absents_q.append(q["id"])
        else:
            vecteurs_q[q["id"]] = v
    if absents_q:
        print(f"  ERREUR : {len(absents_q)} questions absentes du cache :")
        for qid in absents_q[:5]:
            print(f"    - {qid}")
        return 1
    print(f"  {len(vecteurs_q)} vecteurs questions OK")

    print("Construction BM25 global V2 (stop-words conservés)...")
    bm25_global_v2 = IndexBM25(chunks, tokenizer=tokeniser)
    print("Construction BM25 global V2.1 (stop-words NLTK FR filtrés)...")
    bm25_global_v2_1 = IndexBM25(chunks, tokenizer=tokeniser_v2_1)

    print("Lancement des 5 configurations × 2 variantes (zéro LLM)...")
    filtres_par_qid: dict[str, list[str] | None] = {}
    resultats_par_variante: dict[
        str, dict[str, dict[str, list[dict]]]
    ] = {"v2": {}, "v2.1": {}}
    for q in benchmark:
        qid = q["id"]
        q_vec = vecteurs_q[qid]
        filtres_par_qid[qid] = entreprises_filtre(q["question"])
        resultats_par_variante["v2"][qid] = lancer_5_configs(
            question=q, q_vec=q_vec,
            chunks=chunks, chunks_par_id=chunks_par_id,
            vecteurs_chunks=vecteurs_chunks,
            bm25_global=bm25_global_v2,
            top_fusion=TAILLE_LISTES_AVANT_FUSION,
            top_final=20,
            tokenizer=tokeniser,
        )
        resultats_par_variante["v2.1"][qid] = lancer_5_configs(
            question=q, q_vec=q_vec,
            chunks=chunks, chunks_par_id=chunks_par_id,
            vecteurs_chunks=vecteurs_chunks,
            bm25_global=bm25_global_v2_1,
            top_fusion=TAILLE_LISTES_AVANT_FUSION,
            top_final=20,
            tokenizer=tokeniser_v2_1,
        )

    print("Validation : dense recalculé == retrieval_top20.jsonl ?")
    # Le dense ne dépend pas du tokenizer, on vérifie une seule fois.
    dense_par_qid = {
        qid: r["dense"] for qid, r in resultats_par_variante["v2"].items()
    }
    ok, erreurs = valider_dense_vs_v1(dense_par_qid, TOP20_V1_PATH)
    if not ok:
        print(f"  ÉCHEC : {len(erreurs)} Q divergent du top-20 V1.")
        for e in erreurs[:5]:
            print(f"  --- divergence ---")
            print(f"  {e}")
        return 2
    print("  OK : les 31 Q ont exactement les mêmes 20 premiers "
          "chunk_ids (variante V2).")

    print("Agrégation des métriques par variante...")
    stats_par_variante = {
        "v2": agreger(resultats_par_variante["v2"], benchmark),
        "v2.1": agreger(resultats_par_variante["v2.1"], benchmark),
    }

    print("Écriture results/retrieval_compare.jsonl (V2 + V2.1)...")
    ecrire_sortie(
        SORTIE_PATH, resultats_par_variante, filtres_par_qid, benchmark,
    )

    imprimer_rapport(
        stats_par_variante, resultats_par_variante, benchmark,
        filtres_par_qid,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
