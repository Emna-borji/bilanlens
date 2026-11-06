"""V1.2 : V1.1 + deux regles issues de l'analyse post-hoc des
erreurs V1.1 :

1. "Dans une formule d'autonomie financiere, le total passif
   designe le total des capitaux propres et des passifs (total
   du bilan)."
   → cible les 3 Q (Q02, Q10, Q19) qui calculaient CP / dettes
     au lieu de CP / total bilan.

2. "Pour une variation ou une comparaison, indique aussi le sens
   (augmentation ou diminution)."
   → cible Q07 qui a perdu "diminution de" en V1.1.

Memes chunks que V1 (reconstruction locale depuis
`results/v1.jsonl` + `data/chunks/*.jsonl`). ZERO appel Chroma,
ZERO appel API embeddings. SYSTEM_INSTRUCTION inchange ; seul le
template utilisateur change.

Sortie : `results/v1_2.jsonl` sous run_id dedie
`v1_2_<slug>_k5_<prompt_version_v1_2>`. Les runs precedents
(v1.jsonl, v1_1.jsonl) ne sont PAS modifies.
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

from bilanlens.llm import ErreurQuotaJournalier, GeminiLLM, creer_llm  # noqa: E402
from bilanlens.prompts import (  # noqa: E402
    JSON_SCHEMA_REPONSE_V1,
    SYSTEM_INSTRUCTION,
    TEMPLATE_V1_2_USER,
    prompt_version_v1_2,
)
from scripts.evaluate_b0 import (  # noqa: E402
    append_jsonl, charger_benchmark, lire_checkpoint,
    message_arret_quota_journalier, slug_modele,
    EXIT_CODE_QUOTA_JOURNALIER,
)
from scripts.evaluate_v1 import citations_invalides, parser_reponse_v1  # noqa: E402
from scripts.score import (  # noqa: E402
    RUN_ID_V1, charger_chunks_locaux, reconstruire_contexte_v1,
)

BENCH_PATH = RACINE / "data" / "benchmark" / "questions.jsonl"
V1_PATH = RACINE / "results" / "v1.jsonl"
RESULTS_PATH = RACINE / "results" / "v1_2.jsonl"


def run_id_defaut_v1_2(model: str, prompt_version: str, top_k: int) -> str:
    return f"v1_2_{slug_modele(model)}_k{top_k}_{prompt_version}"


def generer_reponse_v1_2(llm, contexte: str, question: str):
    prompt_user = TEMPLATE_V1_2_USER.format(
        context=contexte, question=question,
    )
    return llm.generate(
        prompt=prompt_user,
        system=SYSTEM_INSTRUCTION,
        temperature=0.0,
        response_schema=JSON_SCHEMA_REPONSE_V1,
    )


def ligne_resultat_v1_2(
    *, question: dict, reponse, retrieved: list[dict], contexte: str,
    answer_parsed: dict | None, parse_ok: bool,
    run_id: str, prompt_version: str, top_k: int,
) -> dict:
    retrieved_light = [
        {k: v for k, v in r.items() if k != "texte"} for r in retrieved
    ]
    nb_extraits = len(retrieved)
    cited = (answer_parsed or {}).get("cited_extraits", []) if parse_ok else []
    invalides = citations_invalides(cited, nb_extraits)
    return {
        "run_id": run_id,
        "run_id_source": RUN_ID_V1,
        "provenance": "v1_2",
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


def main() -> int:
    parseur = argparse.ArgumentParser(
        description="V1.2 : V1.1 + regles anti-ambiguite."
    )
    parseur.add_argument(
        "--model", default=GeminiLLM.DEFAULT_MODEL,
    )
    parseur.add_argument("--run-id", default=None)
    parseur.add_argument("--only", default=None)
    parseur.add_argument("--interval-s", type=float, default=7.0)
    args = parseur.parse_args()

    lignes_v1 = [
        json.loads(l) for l in open(V1_PATH, encoding="utf-8") if l.strip()
    ]
    v1_par_qid = {
        l["question_id"]: l for l in lignes_v1
        if l.get("run_id") == RUN_ID_V1
    }
    if not v1_par_qid:
        print(f"ERREUR : aucune ligne V1 run_id={RUN_ID_V1}")
        return 1

    top_k = next(iter(v1_par_qid.values())).get("top_k", 5)
    prompt_version = prompt_version_v1_2()
    model = args.model
    run_id = args.run_id or run_id_defaut_v1_2(model, prompt_version, top_k)

    print("=== V1.2 : V1.1 + 2 regles anti-ambiguite ===")
    print(f"  model             : {model}")
    print(f"  top_k (herite V1) : {top_k}")
    print(f"  run_id            : {run_id}")
    print(f"  run_id_source     : {RUN_ID_V1}")
    print(f"  prompt_version    : {prompt_version}")

    questions = charger_benchmark(BENCH_PATH)
    if args.only:
        ids = {s.strip() for s in args.only.split(",") if s.strip()}
        inconnus = ids - set(v1_par_qid)
        if inconnus:
            print(f"ERREUR : IDs inconnus : {sorted(inconnus)}")
            return 1
        questions = [q for q in questions if q["id"] in ids]

    questions = [q for q in questions if q["id"] in v1_par_qid]
    print(f"Questions a traiter : {len(questions)}")

    deja_faits = lire_checkpoint(RESULTS_PATH, run_id)
    a_faire = [q for q in questions if q["id"] not in deja_faits]
    print(f"Deja faits : {len(deja_faits)}  |  a faire : {len(a_faire)}")
    if not a_faire:
        return 0

    chunks_locaux = charger_chunks_locaux()
    print(f"Chunks locaux charges : {len(chunks_locaux)}")
    llm = creer_llm(provider="gemini", model=model)

    for i, q in enumerate(a_faire, start=1):
        qid = q["id"]
        rec_v1 = v1_par_qid[qid]
        contexte = reconstruire_contexte_v1(rec_v1, chunks_locaux)
        attendu = int(rec_v1.get("context_rendered_chars") or 0)
        if len(contexte) != attendu:
            print(f"ERREUR {qid} : len {len(contexte)} != {attendu}")
            return 1

        print(f"[{i}/{len(a_faire)}] {qid} ({q.get('category', '-')})")
        try:
            reponse = generer_reponse_v1_2(llm, contexte, q["question"])
        except ErreurQuotaJournalier as exc:
            print(message_arret_quota_journalier(
                nb_faits=len(deja_faits) + i - 1,
                total=len(questions),
                retry_delay_s=exc.retry_delay_s,
            ))
            return EXIT_CODE_QUOTA_JOURNALIER
        answer_parsed, parse_ok = parser_reponse_v1(reponse.text)
        rec = ligne_resultat_v1_2(
            question=q, reponse=reponse,
            retrieved=rec_v1.get("retrieved") or [],
            contexte=contexte,
            answer_parsed=answer_parsed, parse_ok=parse_ok,
            run_id=run_id, prompt_version=prompt_version, top_k=top_k,
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
