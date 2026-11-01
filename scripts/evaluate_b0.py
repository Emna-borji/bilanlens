"""Baseline B0 : evaluation du LLM SEUL, sans contexte RAG.

Pipeline :
1. Charge .env -> GEMINI_API_KEY.
2. Charge le benchmark data/benchmark/questions.jsonl.
3. Lit results/b0.jsonl -> set((run_id, question_id)) deja faits
   (checkpoint sur le COUPLE : un nouveau run_id doit retraiter
   toutes les questions, meme deja presentes sous un run_id anterieur).
4. Pour chaque question non faite dans ce run :
   a. Appelle le LLM avec SYSTEM_INSTRUCTION + TEMPLATE_B0_USER + JSON schema.
   b. Parse la reponse (JSON strict cote API, mais parse_ok=False
      si invalide par securite).
   c. Append une ligne JSON a results/b0.jsonl, flush.
5. Affiche stats : nb "donnee non disponible", nb parse_ok=False,
   latence moyenne, 5 exemples (dont Q01 et une sans_reponse).

Rate limiting : RPM free tier gemini-flash ~ 10-15 selon sources.
Default --interval-s=7 (~8.5 RPM) tient a l'ancien chiffre officiel
10 RPM (marge). Le backoff 429 (bilanlens._api_retry) couvre les 429
residuels mais coute cher en latence : mieux vaut l'eviter en amont.

Usage :
    .\\.venv\\Scripts\\python.exe scripts/evaluate_b0.py
    .\\.venv\\Scripts\\python.exe scripts/evaluate_b0.py --run-id b0_test
    .\\.venv\\Scripts\\python.exe scripts/evaluate_b0.py --interval-s 5
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RACINE / ".env")

from bilanlens.llm import ErreurQuotaJournalier, creer_llm  # noqa: E402
from bilanlens.prompts import (  # noqa: E402
    JSON_SCHEMA_REPONSE,
    SYSTEM_INSTRUCTION,
    TEMPLATE_B0_USER,
    prompt_version_b0,
)

# Code de sortie dedie au quota journalier (RPD) : permet a un wrapper
# CI de distinguer "quota journalier -> relancer demain" d'une erreur
# fatale (1). Convention locale, documentee ici.
EXIT_CODE_QUOTA_JOURNALIER = 2

BENCH_PATH = RACINE / "data" / "benchmark" / "questions.jsonl"
RESULTS_DIR = RACINE / "results"
RESULTS_PATH = RESULTS_DIR / "b0.jsonl"


def charger_benchmark(path: Path) -> list[dict]:
    questions = []
    with path.open(encoding="utf-8") as f:
        for ligne in f:
            questions.append(json.loads(ligne))
    return questions


def lire_checkpoint(path: Path, run_id: str) -> set[str]:
    """Retourne l'ensemble des `question_id` deja traites DANS CE
    `run_id`. Les lignes d'autres run_id sont ignorees pour le
    checkpoint (mais conservees dans le fichier)."""
    deja_faits: set[str] = set()
    if not path.exists():
        return deja_faits
    with path.open(encoding="utf-8") as f:
        for ligne in f:
            try:
                rec = json.loads(ligne)
                if rec.get("run_id") == run_id and "question_id" in rec:
                    deja_faits.add(rec["question_id"])
            except json.JSONDecodeError:
                continue
    return deja_faits


def parser_reponse(texte_brut: str) -> tuple[dict | None, bool]:
    """Retourne (answer_parsed, parse_ok). JSON strict force cote API
    via `response_mime_type` : parse_ok=False ne devrait quasiment
    jamais arriver, mais on reste defensif."""
    try:
        parsed = json.loads(texte_brut)
    except (json.JSONDecodeError, TypeError):
        return None, False
    if not isinstance(parsed, dict):
        return None, False
    if "answer" not in parsed or "confidence" not in parsed:
        return None, False
    return parsed, True


def generer_reponse_b0(llm, question_texte: str):
    """Appelle le LLM avec le prompt B0. Retourne un `LLMResponse`."""
    prompt_user = TEMPLATE_B0_USER.format(question=question_texte)
    return llm.generate(
        prompt=prompt_user,
        system=SYSTEM_INSTRUCTION,
        temperature=0.0,
        response_schema=JSON_SCHEMA_REPONSE,
    )


def ligne_resultat(
    *,
    question: dict,
    reponse,
    answer_parsed: dict | None,
    parse_ok: bool,
    run_id: str,
    prompt_version: str,
) -> dict:
    """Construit un dict JSON-serialisable pour append dans b0.jsonl."""
    return {
        "run_id": run_id,
        "prompt_version": prompt_version,
        "question_id": question["id"],
        "question": question["question"],
        "category": question.get("category"),
        "answer_raw": reponse.text,
        "answer_parsed": answer_parsed,
        "parse_ok": parse_ok,
        "model": reponse.model,
        "provider": reponse.provider,
        "temperature": reponse.temperature,
        "latency_s": round(reponse.latency_s, 3),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def append_jsonl(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def message_arret_quota_journalier(
    nb_faits: int, total: int, retry_delay_s: float,
    maintenant: datetime | None = None,
) -> str:
    """Message a afficher quand le quota journalier (RPD) est atteint.

    Separe en fonction testable (pas de time.time() cache) : le test
    peut fixer `maintenant` et verifier le format exact. En prod,
    `maintenant=None` -> `datetime.now(timezone.utc)`.
    """
    if maintenant is None:
        maintenant = datetime.now(timezone.utc)
    heure_retry_utc = maintenant + timedelta(seconds=retry_delay_s)
    # Tunis = UTC+1 toute l'annee (pas de DST). Hardcode plutot que
    # zoneinfo pour que les tests restent deterministes et portables.
    heure_retry_tunis = heure_retry_utc + timedelta(hours=1)
    heures = int(retry_delay_s // 3600)
    minutes = int((retry_delay_s % 3600) // 60)
    return (
        f"\nQuota journalier Gemini atteint ({nb_faits}/{total} faits).\n"
        f"Google indique un retry dans {heures} h {minutes:02d} min.\n"
        f"Relancer apres : {heure_retry_tunis.strftime('%Y-%m-%d %H:%M')} "
        f"(heure Tunis).\n"
        f"Le checkpoint reprendra la ou on s'est arrete."
    )


def _formater_octets(n: int) -> str:
    for unite in ("o", "Ko", "Mo"):
        if n < 1024 or unite == "Mo":
            return f"{n:.1f} {unite}"
        n /= 1024
    return f"{n:.1f} Mo"


def afficher_stats(path: Path, run_id: str) -> None:
    """Affiche stats et 5 exemples (Q01 + une sans_reponse + 3 autres)."""
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
    nb_dnd = sum(
        1 for l in lignes
        if (l.get("answer_parsed") or {}).get("answer", "").strip().lower()
        == "donnee non disponible"
    )
    nb_parse_ko = sum(1 for l in lignes if not l.get("parse_ok"))
    latence_moy = sum(l["latency_s"] for l in lignes) / n

    print()
    print("=== Resume B0 ===")
    print(f"  run_id              : {run_id}")
    print(f"  prompt_version      : {lignes[0].get('prompt_version')}")
    print(f"  modele              : {lignes[0].get('model')}")
    print(f"  questions traitees  : {n}")
    print(f"  'donnee non disponible' : {nb_dnd} ({100*nb_dnd/n:.0f} %)")
    print(f"  parse_ok=False      : {nb_parse_ko}")
    print(f"  latence moyenne     : {latence_moy:.2f} s")
    print(f"  taille fichier      : {_formater_octets(path.stat().st_size)}")

    # 5 exemples : Q01, une sans_reponse (sotuver_2024_05), 3 autres.
    ids_mis_en_avant = {"sotuver_2024_01", "sotuver_2024_05"}
    exemples = [l for l in lignes if l["question_id"] in ids_mis_en_avant]
    autres = [l for l in lignes if l["question_id"] not in ids_mis_en_avant]
    exemples.extend(autres[: max(0, 5 - len(exemples))])

    print()
    print("=== 5 exemples ===")
    for ex in exemples[:5]:
        p = ex.get("answer_parsed") or {}
        ans = p.get("answer", "<parse_ok=False>")
        conf = p.get("confidence", "-")
        print(f"  {ex['question_id']} [{ex.get('category', '-')}, conf={conf}]")
        print(f"    Q : {ex['question'][:110]}")
        print(f"    A : {ans[:150]}")


def main() -> int:
    parseur = argparse.ArgumentParser(description="Baseline B0 (LLM seul).")
    parseur.add_argument(
        "--run-id",
        default=f"b0_{prompt_version_b0()}",
        help="Identifiant du run. Default : b0_<prompt_version>. "
             "Changer le run_id force a retraiter toutes les questions.",
    )
    parseur.add_argument(
        "--interval-s", type=float, default=7.0,
        help="Delai entre deux appels LLM (RPM free tier ~ 10 req/min).",
    )
    args = parseur.parse_args()

    run_id = args.run_id
    prompt_version = prompt_version_b0()

    print(f"=== B0 : evaluation LLM seul ===")
    print(f"  run_id         : {run_id}")
    print(f"  prompt_version : {prompt_version}")
    print(f"  interval       : {args.interval_s} s entre appels")
    print(f"  benchmark      : {BENCH_PATH.relative_to(RACINE)}")
    print(f"  resultats      : {RESULTS_PATH.relative_to(RACINE)}")
    print()

    questions = charger_benchmark(BENCH_PATH)
    print(f"Questions chargees : {len(questions)}")

    deja_faits = lire_checkpoint(RESULTS_PATH, run_id)
    a_faire = [q for q in questions if q["id"] not in deja_faits]
    print(f"Deja faits pour ce run_id : {len(deja_faits)}")
    print(f"A traiter : {len(a_faire)}")
    if not a_faire:
        print("Rien a faire. Affichage des stats du run existant.")
        afficher_stats(RESULTS_PATH, run_id)
        return 0

    duree_est = len(a_faire) * (args.interval_s + 2)  # ~2 s de latence
    print(f"Duree estimee : ~{int(duree_est // 60)} min {int(duree_est % 60)} s")
    print()

    llm = creer_llm(provider="gemini")

    # Total global (sur le benchmark complet) pour un message d'arret
    # lisible : "18/31 faits" plutot que "11/13 restantes faites".
    nb_deja_faits = len(deja_faits)
    total_benchmark = len(questions)

    for i, q in enumerate(a_faire, start=1):
        print(f"[{i}/{len(a_faire)}] {q['id']} ({q.get('category', '-')})")
        try:
            reponse = generer_reponse_b0(llm, q["question"])
        except ErreurQuotaJournalier as exc:
            # Pas de backoff : attendre 15 h en boucle n'a aucun sens.
            # Checkpoint deja a jour (append-only JSONL).
            print(message_arret_quota_journalier(
                nb_faits=nb_deja_faits + i - 1,
                total=total_benchmark,
                retry_delay_s=exc.retry_delay_s,
            ))
            return EXIT_CODE_QUOTA_JOURNALIER
        answer_parsed, parse_ok = parser_reponse(reponse.text)
        rec = ligne_resultat(
            question=q,
            reponse=reponse,
            answer_parsed=answer_parsed,
            parse_ok=parse_ok,
            run_id=run_id,
            prompt_version=prompt_version,
        )
        append_jsonl(RESULTS_PATH, rec)
        ans_court = (answer_parsed or {}).get("answer", "<parse_ok=False>")[:80]
        print(f"    -> {ans_court}  ({reponse.latency_s:.2f} s)")
        if i < len(a_faire):
            time.sleep(args.interval_s)

    afficher_stats(RESULTS_PATH, run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
