"""V1 : evaluation du LLM avec contexte RAG (top-k chunks).

Pipeline :
1. Pour chaque question du benchmark :
   a. Encoder la question en vecteur (`EncodeurGemini.embed_query`,
      task_type=RETRIEVAL_QUERY).
   b. Query Chroma avec `n_results=top_k` (cosine distance).
   c. Formater les k chunks en contexte `=== Extrait N : doc, page X ===`.
   d. Appeler le LLM avec `SYSTEM_INSTRUCTION` (identique a B0-strict)
      + `TEMPLATE_V1_USER` (contexte + question + consigne cited_extraits).
   e. Parser le JSON {answer, confidence, cited_extraits}.
   f. Append une ligne dans results/v1.jsonl avec les chunks
      recuperes (rang, chunk_id, doc, page_physique, distance), le
      contexte rendu (nb caracteres), la reponse parsee et les
      citations invalides eventuelles.
2. Afficher les stats a la fin.

Pour l'etape 7 (score.py) :
- Une page pertinente = couple (doc, page_physique), pas la page seule
  (les 5 extraits peuvent venir de plusieurs entreprises).
- Recall@k : TOUTES les pages attendues doivent etre dans le top-k.
  Pour TOUTE question qui porte des `calculation.intermediate_values`
  (calcul OU comparaison, les deux peuvent en avoir), ce sont TOUTES
  les pages de ces valeurs intermediaires qui sont requises
  (protocole §3.1). Sans `intermediate_values`, la seule page
  `evidence_page_physical` suffit. Une seule page manquante =
  recall KO sur la question entiere.
- MRR : rang (1..k) du premier chunk pertinent.
- Les Q `sans_reponse` n'entrent pas dans le calcul du recall
  (`pages_attendues` court-circuite par categorie).

Usage :
    .\\.venv\\Scripts\\python.exe scripts/evaluate_v1.py
    .\\.venv\\Scripts\\python.exe scripts/evaluate_v1.py --top-k 3
    .\\.venv\\Scripts\\python.exe scripts/evaluate_v1.py --only sotuver_2024_01
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

from bilanlens.embeddings import charger_encodeur  # noqa: E402
from bilanlens.index import ouvrir_collection  # noqa: E402
from bilanlens.llm import ErreurQuotaJournalier, GeminiLLM, creer_llm  # noqa: E402
from bilanlens.prompts import (  # noqa: E402
    JSON_SCHEMA_REPONSE_V1,
    SYSTEM_INSTRUCTION,
    TEMPLATE_V1_USER,
    prompt_version_v1,
)
from scripts.evaluate_b0 import (  # noqa: E402
    append_jsonl,
    charger_benchmark,
    lire_checkpoint,
    message_arret_quota_journalier,
    slug_modele,
    EXIT_CODE_QUOTA_JOURNALIER,
)

BENCH_PATH = RACINE / "data" / "benchmark" / "questions.jsonl"
RESULTS_DIR = RACINE / "results"
RESULTS_PATH = RESULTS_DIR / "v1.jsonl"
CHROMA_PATH = RACINE / "data" / "chroma"

DEFAULT_TOP_K = 5


def run_id_defaut_v1(model: str, prompt_version: str, top_k: int) -> str:
    """Default `run_id` V1 : `v1_<model_slug>_k<top_k>_<prompt_version>`.

    `top_k` est INCLUS dans l'ID : le checkpoint `lire_checkpoint`
    filtre par `run_id` ; sans `k`, un futur run `--top-k 10` sauterait
    les 31 Q deja faites a `k=5` (meme run_id -> deja_faits non vide)
    et renverrait un ensemble vide, silencieusement. Chaque axe qui
    change le resultat (modele, k, prompt) doit vivre dans l'ID."""
    return f"v1_{slug_modele(model)}_k{top_k}_{prompt_version}"


def parser_retrieved(query_result: dict) -> list[dict]:
    """Transforme la reponse brute de `collection.query` en une liste
    `[{rank, chunk_id, doc, page_physique, distance, texte}, ...]`.

    Chroma retourne : `{'ids': [[...]], 'distances': [[...]],
    'documents': [[...]], 'metadatas': [[...]]}`. Les listes externes
    correspondent aux queries (une seule ici).
    """
    ids = (query_result.get("ids") or [[]])[0]
    distances = (query_result.get("distances") or [[]])[0]
    documents = (query_result.get("documents") or [[]])[0]
    metadatas = (query_result.get("metadatas") or [[]])[0]

    retrieved = []
    for i, chunk_id in enumerate(ids):
        meta = metadatas[i] if i < len(metadatas) else {}
        retrieved.append({
            "rank": i + 1,
            "chunk_id": chunk_id,
            "doc": meta.get("doc"),
            "page_physique": meta.get("page_physique"),
            "sous_numero": meta.get("sous_numero", 0),
            "distance": float(distances[i]) if i < len(distances) else None,
            "texte": documents[i] if i < len(documents) else "",
        })
    return retrieved


def formater_contexte(retrieved: list[dict]) -> str:
    """Rend les k chunks sous la forme :
        === Extrait 1 : doc, page X ===
        <texte>

        === Extrait 2 : doc, page Y ===
        <texte>
    L'ordre suit le rang Chroma (plus proche en premier).
    """
    morceaux = []
    for item in retrieved:
        entete = (
            f"=== Extrait {item['rank']} : {item['doc']}, "
            f"page {item['page_physique']} ==="
        )
        morceaux.append(f"{entete}\n{item['texte']}")
    return "\n\n".join(morceaux)


def citations_invalides(
    cited_extraits: list[int], nb_extraits: int,
) -> list[int]:
    """Numeros d'extraits cites qui n'existent PAS dans le contexte
    (1..nb_extraits). Permet de mesurer les hallucinations de
    citation (le modele cite "extrait 7" alors qu'on en a fourni 5).
    """
    return [n for n in (cited_extraits or []) if n < 1 or n > nb_extraits]


def parser_reponse_v1(texte_brut: str) -> tuple[dict | None, bool]:
    """Retourne (answer_parsed, parse_ok). JSON strict force cote API :
    verifie la presence des 3 cles obligatoires et le type de
    cited_extraits (liste d'entiers)."""
    try:
        parsed = json.loads(texte_brut)
    except (json.JSONDecodeError, TypeError):
        return None, False
    if not isinstance(parsed, dict):
        return None, False
    for cle in ("answer", "confidence", "cited_extraits"):
        if cle not in parsed:
            return None, False
    if not isinstance(parsed["cited_extraits"], list):
        return None, False
    if not all(isinstance(n, int) for n in parsed["cited_extraits"]):
        return None, False
    return parsed, True


def generer_reponse_v1(
    llm, encoder, collection, question_texte: str, top_k: int,
):
    """Pipeline RAG complet pour une question. Retourne
    (reponse_llm, retrieved, contexte)."""
    import numpy as np

    vec = encoder.embed_query(question_texte)
    if hasattr(vec, "tolist"):
        vec = vec.tolist()
    query_result = collection.query(
        query_embeddings=[vec], n_results=top_k,
    )
    retrieved = parser_retrieved(query_result)
    contexte = formater_contexte(retrieved)

    prompt_user = TEMPLATE_V1_USER.format(
        context=contexte, question=question_texte,
    )
    reponse = llm.generate(
        prompt=prompt_user,
        system=SYSTEM_INSTRUCTION,
        temperature=0.0,
        response_schema=JSON_SCHEMA_REPONSE_V1,
    )
    return reponse, retrieved, contexte


def ligne_resultat_v1(
    *,
    question: dict,
    reponse,
    retrieved: list[dict],
    contexte: str,
    answer_parsed: dict | None,
    parse_ok: bool,
    run_id: str,
    prompt_version: str,
    top_k: int,
) -> dict:
    """Construit un dict JSON-serialisable pour append dans v1.jsonl.
    `retrieved` est stocke SANS les textes (trop volumineux) ; seul
    (rank, chunk_id, doc, page_physique, distance) est conserve."""
    retrieved_light = [
        {k: v for k, v in r.items() if k != "texte"} for r in retrieved
    ]
    nb_extraits = len(retrieved)
    cited = (answer_parsed or {}).get("cited_extraits", []) if parse_ok else []
    invalides = citations_invalides(cited, nb_extraits)
    return {
        "run_id": run_id,
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
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _doc_depuis_evidence_doc(evidence_doc: str) -> str:
    """`real_sotuver_2024.pdf` -> `sotuver_2024`. Pattern reutilise
    dans tests/test_chunks_couverture_benchmark.py (meme definition
    source : scripts/chunk_corpus.py qui mappe fichier -> slug).
    """
    return evidence_doc.replace("real_", "").replace(".pdf", "")


def pages_attendues(question: dict) -> set[tuple[str, int]]:
    """Pour une question du benchmark, renvoie l'ensemble des couples
    (doc, page_physique) attendus dans le top-k.

    Protocole §3.1 : pour un calcul multi-page (presence de
    `calculation.intermediate_values`), TOUTES les pages des valeurs
    intermediaires doivent etre retrouvees. Sinon, la page principale
    `evidence_page_physical` suffit.

    Pour les questions `sans_reponse` : set vide (aucune page attendue,
    la bonne reponse est l'abstention). Le court-circuit par categorie
    fait AUTORITE sur `evidence_page_physical` meme si le benchmark
    renseigne une page par erreur : une Q sans_reponse ne doit jamais
    entrer dans le calcul du recall.
    """
    if question.get("category") == "sans_reponse":
        return set()
    evidence_doc = question.get("evidence_doc")
    if not evidence_doc:
        return set()
    doc = _doc_depuis_evidence_doc(evidence_doc)
    calc = question.get("calculation") or {}
    inter = calc.get("intermediate_values") or {}
    pages: set[tuple[str, int]] = set()
    if inter:
        # Calcul multi-page : exige TOUTES les pages des valeurs
        # intermediaires. Si une seule manque -> recall KO.
        for valeur in inter.values():
            p = valeur.get("evidence_page_physical")
            if p is not None:
                pages.add((doc, int(p)))
    else:
        p = question.get("evidence_page_physical")
        if p is not None:
            pages.add((doc, int(p)))
    return pages


def pages_recuperees(retrieved: list[dict]) -> set[tuple[str, int]]:
    """Couples (doc, page_physique) presents dans le top-k."""
    return {
        (r["doc"], int(r["page_physique"]))
        for r in retrieved
        if r.get("doc") and r.get("page_physique") is not None
    }


def recall_ok(question: dict, retrieved: list[dict]) -> bool | None:
    """`True` si toutes les pages attendues sont dans le top-k.
    `None` pour les questions sans page attendue (sans_reponse)."""
    attendues = pages_attendues(question)
    if not attendues:
        return None
    return attendues.issubset(pages_recuperees(retrieved))


def afficher_stats_v1(
    path: Path, run_id: str, benchmark: list[dict] | None = None,
) -> None:
    """Stats V1 : chiffrees, 'donnee non disponible', citations
    invalides, latence moyenne, et (si `benchmark` fourni) nombre de
    questions par categorie dont la page attendue (doc + page) est
    dans le top-k.
    """
    from scripts.evaluate_b0 import (
        contient_chiffre_significatif, est_reponse_abstentive,
    )

    if not path.exists():
        print(f"Fichier absent : {path}")
        return
    lignes = []
    with path.open(encoding="utf-8") as f:
        for ligne in f:
            try:
                rec = json.loads(ligne)
                if rec.get("run_id") == run_id:
                    lignes.append(rec)
            except json.JSONDecodeError:
                continue
    if not lignes:
        print(f"Aucune ligne pour run_id={run_id} dans {path.name}.")
        return

    n = len(lignes)
    answers = [
        (l.get("answer_parsed") or {}).get("answer", "") for l in lignes
    ]
    nb_dnd = sum(1 for a in answers if est_reponse_abstentive(a))
    nb_chiffrees = sum(1 for a in answers if contient_chiffre_significatif(a))
    nb_parse_ko = sum(1 for l in lignes if not l.get("parse_ok"))
    nb_citations_invalides = sum(1 for l in lignes if l.get("cited_invalides"))
    latence_moy = sum(l["latency_s"] for l in lignes) / n

    print()
    print("=== Resume V1 (RAG top-k) ===")
    print(f"  run_id              : {run_id}")
    print(f"  prompt_version      : {lignes[0].get('prompt_version')}")
    print(f"  modele              : {lignes[0].get('model')}")
    print(f"  top_k               : {lignes[0].get('top_k')}")
    print(f"  questions traitees  : {n}")
    print(f"  reponses chiffrees  : {nb_chiffrees}/{n}")
    print(f"  'donnee non disponible' : {nb_dnd}/{n} ({100*nb_dnd/n:.0f} %)")
    print(f"  parse_ok=False      : {nb_parse_ko}")
    print(f"  cite invalide       : {nb_citations_invalides}")
    print(f"  latence moyenne     : {latence_moy:.2f} s")

    if benchmark is None:
        return

    # Recall@k par categorie (page attendue = (doc, page_physique)).
    bench_par_id = {q["id"]: q for q in benchmark}
    par_cat_ok: dict[str, int] = {}
    par_cat_total: dict[str, int] = {}
    par_cat_na: dict[str, int] = {}
    for l in lignes:
        q = bench_par_id.get(l["question_id"])
        if q is None:
            continue
        cat = q.get("category", "-")
        ok = recall_ok(q, l.get("retrieved") or [])
        if ok is None:
            # Pas de page attendue (sans_reponse) : hors metrique recall.
            par_cat_na[cat] = par_cat_na.get(cat, 0) + 1
            continue
        par_cat_total[cat] = par_cat_total.get(cat, 0) + 1
        if ok:
            par_cat_ok[cat] = par_cat_ok.get(cat, 0) + 1

    print()
    print(f"  Recall@{lignes[0].get('top_k')} par categorie "
          f"(page attendue = doc + page_physique) :")
    for cat in sorted(par_cat_total.keys() | par_cat_na.keys()):
        total = par_cat_total.get(cat, 0)
        ok = par_cat_ok.get(cat, 0)
        na = par_cat_na.get(cat, 0)
        if total > 0:
            print(f"    {cat:<16} : {ok}/{total}"
                  + (f"  (+ {na} sans page attendue)" if na else ""))
        else:
            print(f"    {cat:<16} : {na} sans page attendue "
                  f"(categorie sans_reponse)")


def afficher_detail_v1(path: Path, run_id: str, question_ids: list[str]) -> None:
    """Pour chaque question_id : affiche les k chunks (doc, page,
    distance), la reponse, les extraits cites, les invalides. Utile
    pour inspecter 3 questions au lancement."""
    if not path.exists():
        print(f"Fichier absent : {path}")
        return
    index_par_id: dict[str, dict] = {}
    with path.open(encoding="utf-8") as f:
        for ligne in f:
            try:
                rec = json.loads(ligne)
                if rec.get("run_id") == run_id and rec["question_id"] in question_ids:
                    index_par_id[rec["question_id"]] = rec
            except json.JSONDecodeError:
                continue

    for qid in question_ids:
        rec = index_par_id.get(qid)
        if rec is None:
            print(f"  {qid} : absent du run.")
            continue
        print()
        print(f"=== {qid} [{rec.get('category')}] ===")
        print(f"Q : {rec['question'][:120]}")
        print(f"\nChunks recuperes (top {rec.get('top_k')}) :")
        for r in rec["retrieved"]:
            print(
                f"  rang {r['rank']}  {r['chunk_id']:<40}  "
                f"doc={r['doc']:<24} page={r['page_physique']:<3} "
                f"distance={r['distance']:.4f}"
            )
        p = rec.get("answer_parsed") or {}
        print(f"\nReponse modele  (conf={p.get('confidence', '-')})")
        print(f"  {p.get('answer', '<parse_ok=False>')}")
        cited = p.get("cited_extraits") or []
        print(f"  cited_extraits = {cited}")
        if rec.get("cited_invalides"):
            print(f"  CITATIONS INVALIDES : {rec['cited_invalides']}")
        print(f"  latence : {rec['latency_s']:.2f} s")


def main() -> int:
    parseur = argparse.ArgumentParser(description="V1 : RAG top-k.")
    parseur.add_argument(
        "--model", default=GeminiLLM.DEFAULT_MODEL,
        help=f"Nom pinne du modele LLM. Default : {GeminiLLM.DEFAULT_MODEL}. "
             f"Doit etre le MEME que B0 pour que la comparaison soit valide.",
    )
    parseur.add_argument(
        "--top-k", type=int, default=DEFAULT_TOP_K,
        help=f"Nombre de chunks a recuperer. Default : {DEFAULT_TOP_K}.",
    )
    parseur.add_argument(
        "--run-id", default=None,
        help="Default : v1_<model_slug>_<prompt_version_v1>.",
    )
    parseur.add_argument(
        "--only", default=None,
        help="Liste d'IDs de questions (separes par virgule).",
    )
    parseur.add_argument(
        "--interval-s", type=float, default=7.0,
        help="Delai entre deux appels LLM (RPM free tier ~ 10 req/min).",
    )
    parseur.add_argument(
        "--detail", action="store_true",
        help="Apres les stats, affiche le detail (chunks + reponse + "
             "citations) des questions traitees ce run.",
    )
    args = parseur.parse_args()

    model = args.model
    prompt_version = prompt_version_v1()
    top_k = args.top_k
    run_id = args.run_id or run_id_defaut_v1(model, prompt_version, top_k)

    print("=== V1 : evaluation RAG top-k ===")
    print(f"  model          : {model}")
    print(f"  top_k          : {top_k}")
    print(f"  run_id         : {run_id}")
    print(f"  prompt_version : {prompt_version}")
    print(f"  interval       : {args.interval_s} s entre appels")
    print(f"  benchmark      : {BENCH_PATH.relative_to(RACINE)}")
    print(f"  chroma         : {CHROMA_PATH.relative_to(RACINE)}")
    print(f"  resultats      : {RESULTS_PATH.relative_to(RACINE)}")
    if args.only:
        print(f"  --only         : {args.only}")
    print()

    benchmark = charger_benchmark(BENCH_PATH)
    print(f"Questions chargees : {len(benchmark)}")

    questions = benchmark
    if args.only:
        ids_cibles = {s.strip() for s in args.only.split(",") if s.strip()}
        ids_bench = {q["id"] for q in benchmark}
        inconnus = ids_cibles - ids_bench
        if inconnus:
            print(f"ERREUR : IDs inconnus dans --only : {sorted(inconnus)}")
            return 1
        questions = [q for q in benchmark if q["id"] in ids_cibles]
        print(f"Apres filtrage --only : {len(questions)}")

    deja_faits = lire_checkpoint(RESULTS_PATH, run_id)
    a_faire = [q for q in questions if q["id"] not in deja_faits]
    print(f"Deja faits pour ce run_id : {len(deja_faits)}")
    print(f"A traiter : {len(a_faire)}")

    if not a_faire:
        print("Rien a faire. Affichage des stats du run existant.")
        afficher_stats_v1(RESULTS_PATH, run_id, benchmark=benchmark)
        if args.detail:
            afficher_detail_v1(
                RESULTS_PATH, run_id, [q["id"] for q in questions],
            )
        return 0

    # Durée estimée : ~1 s latence LLM + interval + ~0,2 s embed query.
    duree_est = len(a_faire) * (args.interval_s + 1.2)
    print(f"Duree estimee : ~{int(duree_est // 60)} min {int(duree_est % 60)} s")
    print()

    # Encoder embeddings + collection Chroma.
    # `charger_encodeur` lit GEMINI_API_KEY depuis l'env (deja charge
    # via load_dotenv en haut de script).
    encoder = charger_encodeur()
    _, collection = ouvrir_collection(CHROMA_PATH, model=encoder.model)

    # LLM.
    llm = creer_llm(provider="gemini", model=model)

    traites_ids: list[str] = []
    for i, q in enumerate(a_faire, start=1):
        print(f"[{i}/{len(a_faire)}] {q['id']} ({q.get('category', '-')})")
        try:
            reponse, retrieved, contexte = generer_reponse_v1(
                llm, encoder, collection, q["question"], top_k,
            )
        except ErreurQuotaJournalier as exc:
            print(message_arret_quota_journalier(
                nb_faits=len(deja_faits) + i - 1,
                total=len(questions),
                retry_delay_s=exc.retry_delay_s,
            ))
            return EXIT_CODE_QUOTA_JOURNALIER
        answer_parsed, parse_ok = parser_reponse_v1(reponse.text)
        rec = ligne_resultat_v1(
            question=q,
            reponse=reponse,
            retrieved=retrieved,
            contexte=contexte,
            answer_parsed=answer_parsed,
            parse_ok=parse_ok,
            run_id=run_id,
            prompt_version=prompt_version,
            top_k=top_k,
        )
        append_jsonl(RESULTS_PATH, rec)
        ans_court = (answer_parsed or {}).get("answer", "<parse_ok=False>")[:80]
        print(f"    -> {ans_court}  ({reponse.latency_s:.2f} s)")
        traites_ids.append(q["id"])
        if i < len(a_faire):
            time.sleep(args.interval_s)

    afficher_stats_v1(RESULTS_PATH, run_id, benchmark=benchmark)
    if args.detail:
        afficher_detail_v1(RESULTS_PATH, run_id, traites_ids)
    return 0


if __name__ == "__main__":
    sys.exit(main())
