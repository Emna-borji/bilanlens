"""score.py — scoring du run V1 selon le protocole §4.

Separation stricte RECALL vs EXACTITUDE :
- Recall@k (k=1,3,5,10,20) + MRR : mesure si les pages attendues
  (doc, page_physique) sont dans le top-k Chroma. TOUTES les pages
  attendues doivent y etre (protocole §3.1). Calcule a partir d'un
  top-20 Chroma relance ici (0 appel LLM, 0 appel API embeddings
  si le cache est chaud).
- Exactitude : la reponse du modele V1 colle-t-elle au benchmark ?
  Methodes par format : numerique (tolerance), variation (direction
  + valeur), texte (annotation manuelle versionnee), sans_reponse
  (abstention detectee).
- Indicateur SEPARE `valeurs_dans_contexte` : pour les questions
  non-texte avec valeurs numeriques attendues, verifie si ces
  valeurs apparaissent dans les 5 chunks du run V1 (independant
  du recall strict par page). `null` pour texte_annexes et
  sans_reponse (pas de valeur numerique).

Classes exclusives (7) : cf. CLASSES.

Entrees :
- data/benchmark/questions.jsonl
- data/benchmark/annotations_texte.jsonl (annotations manuelles
  pour les Q texte_annexes qui ont recu une reponse)
- results/v1.jsonl (run V1 a scorer)
- Chroma (data/chroma/)

Sorties :
- results/scores.jsonl (une ligne par Q)
- results/retrieval_top20.jsonl (une ligne par Q, top-20 brut,
  sans modifier results/v1.jsonl)
- stdout : stats agregees
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(RACINE / ".env")

BENCH_PATH = RACINE / "data" / "benchmark" / "questions.jsonl"
ANNOTATIONS_PATH = RACINE / "data" / "benchmark" / "annotations_texte.jsonl"
V1_PATH = RACINE / "results" / "v1.jsonl"
B0_PATH = RACINE / "results" / "b0.jsonl"
SCORES_PATH = RACINE / "results" / "scores.jsonl"
SCORES_COMPARE_PATH = RACINE / "results" / "scores_compare.jsonl"
TOP20_PATH = RACINE / "results" / "retrieval_top20.jsonl"
COMPARISON_SVG = RACINE / "results" / "comparison_B0_V1.svg"
CHROMA_PATH = RACINE / "data" / "chroma"

# Run_ids cibles de la comparaison etape 8. Fixes et cohes : meme
# modele Flash-Lite pour les 3. Pour B0, il n'y a PAS de top_k dans
# l'ID (pas de retrieval).
RUN_ID_B0_STRICT = "b0_gemini35flashlite_90b019c736aa621c"
RUN_ID_B0_LIBRE = "b0libre_gemini35flashlite_21c68d1cba543eeb"
RUN_ID_V1 = "v1_gemini35flashlite_k5_a3c4180afaeb900e"

K_LIST = (1, 3, 5, 10, 20)

# 7 classes pour un run V1 (avec retrieval : recall_ok/ko distingue).
CLASSES = (
    "juste",
    "fausse_recall_ok",
    "fausse_recall_ko",
    "abstention_a_tort_recall_ok",
    "abstention_a_tort_recall_ko",
    "abstention_correcte",
    "reponse_a_tort",
)

# 5 classes pour un run B0 (sans retrieval : pas de suffixe recall).
# Un `abstention_a_tort` B0 ne veut PAS dire "recall KO" (il n'y a
# pas de recherche) : c'est "le modele n'a pas donne la reponse
# alors qu'il y en avait une a donner".
CLASSES_B0 = (
    "juste",
    "fausse",
    "abstention_a_tort",
    "abstention_correcte",
    "reponse_a_tort",
)


# ---------------------------------------------------------------------------
# I/O utilitaires
# ---------------------------------------------------------------------------
def charger_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                out.append(json.loads(ligne))
            except json.JSONDecodeError:
                continue
    return out


def charger_annotations(
    run_id: str | None = None, path: Path = ANNOTATIONS_PATH,
) -> dict[str, dict]:
    """Retourne `{question_id: annotation}` pour les annotations
    manuelles associees a `run_id`. Chaque ligne du fichier porte
    un champ `run_id` : les reponses d'un meme question_id peuvent
    differer d'un run a l'autre (B0-libre vs V1), donc l'annotation
    aussi.

    Si `run_id` est None, charge toutes les annotations sans
    filtrage (utile pour le compte dans les tests)."""
    out: dict[str, dict] = {}
    for a in charger_jsonl(path):
        if run_id is not None and a.get("run_id") != run_id:
            continue
        out[a["question_id"]] = a
    return out


# ---------------------------------------------------------------------------
# Normalisation texte
# ---------------------------------------------------------------------------
def _normaliser(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).lower().strip()


# ---------------------------------------------------------------------------
# Parsing de la reponse LLM (numerique + direction)
# ---------------------------------------------------------------------------
_RE_NOMBRE = re.compile(
    r"-?\s*\d{1,3}(?:[  \xa0]\d{3})*(?:[.,]\d+)?|-?\s*\d+(?:[.,]\d+)?"
)


def parser_premier_nombre(texte: str) -> float | None:
    """Extrait le PREMIER nombre du texte en gerant les separateurs
    francais (espace milliers, virgule decimale). Retourne un float.

    Exemples :
        "100 836 224 TND"       -> 100836224.0
        "34,53 %"               -> 34.53
        "1 281 772 854,965"     -> 1281772854.965
        "diminution de 24 287 937 TND entre 2023 et 2024"
                                -> 24287937.0 (ignore 2023, 2024 : suivent)
        "99,81 %"               -> 99.81
        "-44 790 355 TND"       -> -44790355.0
    """
    if not isinstance(texte, str):
        return None
    m = _RE_NOMBRE.search(texte)
    if not m:
        return None
    s = m.group(0)
    # Retire espaces (incluant insecables) et remplace virgule decimale.
    s_clean = re.sub(r"[  \xa0]", "", s)
    # Si virgule ET point coexistent : on suppose virgule=decimal, point=milliers.
    if "," in s_clean and "." in s_clean:
        s_clean = s_clean.replace(".", "").replace(",", ".")
    else:
        s_clean = s_clean.replace(",", ".")
    try:
        return float(s_clean)
    except ValueError:
        return None


def parser_direction(texte: str) -> str | None:
    """Pour les comparaisons : 'augmentation' | 'diminution' | None."""
    if not isinstance(texte, str):
        return None
    t = _normaliser(texte)
    if "augmentation" in t or "hausse" in t or "progression" in t:
        return "augmentation"
    if "diminution" in t or "baisse" in t or "recul" in t:
        return "diminution"
    return None


# ---------------------------------------------------------------------------
# Exactitude
# ---------------------------------------------------------------------------
def _tolerance_par_defaut(unite: str | None) -> float:
    """Pour un benchmark sans `tolerance_absolute` explicite.
    Les grands montants en TND tolerent ~1 unite d'ecart (arrondi
    au dinar dans le rapport source). Les pourcentages sans
    tolerance_absolute_pp : 0.01 point. Les ratios : 0.01."""
    return 1.0  # unite = 1 (TND/dinar/tonne). Ajuste par format.


def exact_numerique(
    answer_parsed_text: str, benchmark_q: dict,
) -> tuple[bool, dict]:
    """Verifie la justesse numerique d'une reponse LLM par rapport au
    benchmark. Retourne (ok, detail).

    `detail` contient : attendu, obtenu, diff, tolerance, format.
    """
    ans_bench = benchmark_q.get("answer") or {}
    fmt = ans_bench.get("format")

    # Direction + valeur absolue pour les comparaisons.
    if fmt == "variation":
        direction_attendue = ans_bench.get("direction")
        valeur_attendue = ans_bench.get("value_absolute")
        direction_obtenue = parser_direction(answer_parsed_text)
        valeur_obtenue = parser_premier_nombre(answer_parsed_text)
        tol = ans_bench.get("tolerance_absolute", _tolerance_par_defaut(None))
        detail = {
            "format": "variation",
            "direction_attendue": direction_attendue,
            "direction_obtenue": direction_obtenue,
            "valeur_attendue": valeur_attendue,
            "valeur_obtenue": valeur_obtenue,
            "tolerance_absolue": tol,
            "diff_absolue": (
                abs((valeur_obtenue or 0) - (valeur_attendue or 0))
                if valeur_obtenue is not None else None
            ),
        }
        if direction_obtenue != direction_attendue:
            return False, detail
        if valeur_obtenue is None:
            return False, detail
        return abs(valeur_obtenue - valeur_attendue) <= tol, detail

    # Pourcentage : tolerance_absolute_pp.
    if fmt == "pourcentage":
        valeur_attendue = ans_bench.get("value")
        valeur_obtenue = parser_premier_nombre(answer_parsed_text)
        tol = ans_bench.get("tolerance_absolute_pp", 0.01)
        detail = {
            "format": "pourcentage",
            "valeur_attendue": valeur_attendue,
            "valeur_obtenue": valeur_obtenue,
            "tolerance_pp": tol,
            "diff_absolue_pp": (
                abs(valeur_obtenue - valeur_attendue)
                if valeur_obtenue is not None else None
            ),
        }
        if valeur_obtenue is None:
            return False, detail
        return abs(valeur_obtenue - valeur_attendue) <= tol, detail

    # Ratio : tolerance_absolute.
    if fmt == "ratio":
        valeur_attendue = ans_bench.get("value")
        valeur_obtenue = parser_premier_nombre(answer_parsed_text)
        tol = ans_bench.get("tolerance_absolute", 0.01)
        detail = {
            "format": "ratio",
            "valeur_attendue": valeur_attendue,
            "valeur_obtenue": valeur_obtenue,
            "tolerance_absolue": tol,
            "diff_absolue": (
                abs(valeur_obtenue - valeur_attendue)
                if valeur_obtenue is not None else None
            ),
        }
        if valeur_obtenue is None:
            return False, detail
        return abs(valeur_obtenue - valeur_attendue) <= tol, detail

    # Montant (extractions).
    if fmt == "montant":
        valeur_attendue = ans_bench.get("value")
        valeur_obtenue = parser_premier_nombre(answer_parsed_text)
        tol = ans_bench.get("tolerance_absolute", _tolerance_par_defaut(None))
        detail = {
            "format": "montant",
            "valeur_attendue": valeur_attendue,
            "valeur_obtenue": valeur_obtenue,
            "tolerance_absolue": tol,
            "diff_absolue": (
                abs(valeur_obtenue - valeur_attendue)
                if valeur_obtenue is not None else None
            ),
        }
        if valeur_obtenue is None:
            return False, detail
        return abs(valeur_obtenue - valeur_attendue) <= tol, detail

    # Format non numerique (texte).
    return False, {"format": fmt, "raison": "format non numerique"}


# ---------------------------------------------------------------------------
# Valeurs dans contexte (indicateur separe du recall)
# ---------------------------------------------------------------------------
def valeurs_dans_contexte(
    benchmark_q: dict, textes_chunks_v1: list[str],
) -> bool | None:
    """Pour les Q avec valeur(s) numerique(s) attendue(s) : True ssi
    TOUTES ces valeurs apparaissent (sequence de chiffres) dans la
    concatenation des chunks V1. `None` pour texte_annexes,
    sans_reponse (pas de valeur numerique a chercher).

    Les espaces / virgules / points entre chiffres sont ignores
    (le PDF publie les grands montants comme '100 836 224').
    """
    cat = benchmark_q.get("category")
    if cat in ("texte_annexes", "sans_reponse"):
        return None

    # Collecter les valeurs numeriques a chercher.
    valeurs: list[float] = []
    inter = (benchmark_q.get("calculation") or {}).get("intermediate_values") or {}
    for v in inter.values():
        val = v.get("value")
        if isinstance(val, (int, float)):
            valeurs.append(val)
    if not inter:
        ans = benchmark_q.get("answer") or {}
        val_ans = ans.get("value") or ans.get("value_absolute")
        if isinstance(val_ans, (int, float)):
            valeurs.append(val_ans)

    if not valeurs:
        return None

    # Normaliser contexte : compresser tous les separateurs entre chiffres.
    texte = "\n".join(textes_chunks_v1 or [])
    texte_compresse = re.sub(r"[  \xa0.,]+(?=\d)", "", texte)

    for v in valeurs:
        motif = str(int(abs(v))) if float(v).is_integer() else None
        if motif is None:
            # Valeur non entiere : chercher la partie entiere et la partie
            # decimale separement n'est pas fiable ; on prend l'entier.
            motif = str(int(abs(v)))
        if motif not in texte_compresse:
            return False
    return True


# ---------------------------------------------------------------------------
# Recall + MRR
# ---------------------------------------------------------------------------
def rangs_pages_attendues(
    pages_attendues: set[tuple[str, int]],
    retrieved_top20: list[dict],
) -> dict[str, int | None]:
    """Pour chaque page attendue, son rang (1..20) dans le top-20 ou
    None si absente. Clefs : 'doc@page' (str) pour serialisation JSON.
    """
    rangs: dict[str, int | None] = {}
    for doc, page in pages_attendues:
        trouve: int | None = None
        for r in retrieved_top20:
            if r.get("doc") == doc and int(r.get("page_physique") or -1) == int(page):
                trouve = int(r["rank"])
                break
        rangs[f"{doc}@p{page}"] = trouve
    return rangs


def recall_at_k(
    pages_attendues: set[tuple[str, int]], retrieved_top_k: list[dict],
) -> bool:
    """`True` ssi TOUTES les pages attendues sont dans `retrieved_top_k`."""
    retrouvees = {
        (r["doc"], int(r["page_physique"]))
        for r in retrieved_top_k
        if r.get("doc") and r.get("page_physique") is not None
    }
    return pages_attendues.issubset(retrouvees)


def mrr(
    pages_attendues: set[tuple[str, int]], retrieved_top20: list[dict],
) -> float | None:
    """Rang-reciproque du premier chunk pertinent. 0.0 si aucun
    chunk pertinent dans le top-20. `None` si pas de page attendue."""
    if not pages_attendues:
        return None
    for r in retrieved_top20:
        pair = (r.get("doc"), int(r.get("page_physique") or -1))
        if pair in pages_attendues:
            return 1.0 / int(r["rank"])
    return 0.0


# ---------------------------------------------------------------------------
# Classification (7 classes exclusives)
# ---------------------------------------------------------------------------
def est_abstention(answer_text: str) -> bool:
    """`True` ssi la reponse exprime un refus de repondre ET ne
    contient PAS de chiffre significatif.

    Pourquoi la combinaison : B0-libre (prompt sans consigne
    d'abstention) reformule souvent le refus en langage libre
    ("je ne dispose pas", "n'est pas disponible dans le rapport")
    alors que B0-strict et V1 utilisent la forme canonique "donnee
    non disponible". `est_abstention_large` capte les deux, mais
    sans le garde-fou "pas de chiffre", une reponse chiffree qui
    contient l'un de ces patterns ("Le CA s'eleve a 100 M TND,
    ceci dit l'information complementaire n'est pas disponible")
    serait classee a tort comme abstention. Le filtrage par
    chiffre significatif resout ce cas.

    Garantit que V1 reste classe comme avant : les 14 abstentions
    V1 (4 abstention_correcte + 4 abstention_a_tort_recall_ok +
    6 abstention_a_tort_recall_ko) utilisent toutes la forme
    canonique "donnee non disponible" imposee par SYSTEM_INSTRUCTION,
    captee par la branche stricte de est_abstention_large, et aucune
    ne contient de chiffre significatif.
    """
    from scripts.evaluate_b0 import (
        contient_chiffre_significatif, est_abstention_large,
    )
    if not isinstance(answer_text, str) or not answer_text:
        return True  # pas de reponse = abstention
    if contient_chiffre_significatif(answer_text):
        return False
    return est_abstention_large(answer_text)


def classer(
    benchmark_q: dict,
    reponse_llm_text: str,
    recall_ok: bool | None,
    exact_ok: bool,
) -> str:
    """V1 : attribue l'une des 7 classes exclusives (CLASSES).

    `recall_ok` : True/False (page attendue dans top-k) ou None
    (categorie sans_reponse, pas de page attendue).
    `exact_ok` : True si la reponse colle au benchmark.
    """
    cat = benchmark_q.get("category")
    abstention = est_abstention(reponse_llm_text)

    if cat == "sans_reponse":
        return "abstention_correcte" if abstention else "reponse_a_tort"

    if abstention:
        if recall_ok:
            return "abstention_a_tort_recall_ok"
        return "abstention_a_tort_recall_ko"
    if exact_ok:
        return "juste"
    if recall_ok:
        return "fausse_recall_ok"
    return "fausse_recall_ko"


def classer_b0(
    benchmark_q: dict, reponse_llm_text: str, exact_ok: bool,
) -> str:
    """B0 : attribue l'une des 5 classes CLASSES_B0. Pas de suffixe
    recall, car B0 ne fait pas de recherche (abstention_a_tort veut
    dire "le modele n'a pas donne la reponse alors qu'elle existait
    dans un rapport annuel que le systeme ne consulte pas")."""
    cat = benchmark_q.get("category")
    abstention = est_abstention(reponse_llm_text)

    if cat == "sans_reponse":
        return "abstention_correcte" if abstention else "reponse_a_tort"
    if abstention:
        return "abstention_a_tort"
    return "juste" if exact_ok else "fausse"


# ---------------------------------------------------------------------------
# Scoring par question
# ---------------------------------------------------------------------------
def scorer_question(
    benchmark_q: dict,
    record_v1: dict,
    retrieved_top20: list[dict],
    textes_chunks_v1: list[str],
    annotations: dict[str, dict],
    run_id: str | None = None,
) -> dict:
    """Produit le dict JSON-serialisable pour `results/scores.jsonl`.

    Intermediaires stockes : recall@k pour chaque k, MRR, rangs des
    pages attendues, valeurs_dans_contexte, cosinus (informatif,
    None ici), detail numerique, mode d'annotation.
    """
    from scripts.evaluate_v1 import pages_attendues

    qid = benchmark_q["id"]
    cat = benchmark_q.get("category")
    attendues = pages_attendues(benchmark_q)
    attendues_json = sorted(f"{d}@p{p}" for d, p in attendues) if attendues else []

    rangs = rangs_pages_attendues(attendues, retrieved_top20) if attendues else {}

    recalls = {}
    for k in K_LIST:
        if cat == "sans_reponse":
            recalls[f"recall_at_{k}"] = None
        else:
            recalls[f"recall_at_{k}"] = recall_at_k(
                attendues, retrieved_top20[:k],
            )
    mrr_val = mrr(attendues, retrieved_top20) if attendues else None

    reponse_text = (record_v1.get("answer_parsed") or {}).get("answer", "") or ""

    # Exactitude et mode d'annotation.
    mode_annotation = None
    annotation = annotations.get(qid)
    if cat == "sans_reponse":
        exact_ok = est_abstention(reponse_text)
        detail_exact = {"format": "sans_reponse", "abstention_detectee": exact_ok}
        mode_annotation = "automatique"
    elif cat == "texte_annexes":
        if est_abstention(reponse_text):
            exact_ok = False
            detail_exact = {"format": "texte", "raison": "abstention"}
            mode_annotation = "automatique"
        elif annotation is not None:
            exact_ok = annotation.get("statut") == "juste"
            detail_exact = {
                "format": "texte",
                "statut": annotation.get("statut"),
                "complete": annotation.get("complete"),
                "elements_manquants": annotation.get("elements_manquants", []),
                "justification": annotation.get("justification"),
            }
            mode_annotation = "manuel"
        else:
            # Reponse donnee mais pas d'annotation : non scoree.
            exact_ok = False
            detail_exact = {
                "format": "texte",
                "statut": "non_annotee",
                "raison": "reponse donnee mais pas d'annotation manuelle",
            }
            mode_annotation = "manuel"
    else:
        if est_abstention(reponse_text):
            exact_ok = False
            detail_exact = {"format": (benchmark_q.get("answer") or {}).get("format"),
                            "raison": "abstention"}
        else:
            exact_ok, detail_exact = exact_numerique(reponse_text, benchmark_q)
        mode_annotation = "automatique"

    # Recall OK sur la question = recall@5 (metrique de reference).
    recall_ok_val = recalls["recall_at_5"]
    classe = classer(benchmark_q, reponse_text, recall_ok_val, exact_ok)

    # Valeurs dans contexte (indicateur separe).
    vdc = valeurs_dans_contexte(benchmark_q, textes_chunks_v1)

    # Completude (seulement pour texte_annexes avec annotation).
    complete = None
    if annotation is not None and cat == "texte_annexes":
        complete = annotation.get("complete")

    return {
        "run_id": run_id or record_v1.get("run_id"),
        "provenance": "v1",
        "question_id": qid,
        "category": cat,
        "classe": classe,
        "recall": recalls,
        "mrr": mrr_val,
        "pages_attendues": attendues_json,
        "rangs_pages_attendues": rangs,
        "valeurs_dans_contexte": vdc,
        "exact_ok": exact_ok,
        "detail_exact": detail_exact,
        "complete": complete,
        "mode_annotation": mode_annotation,
        "reponse_modele": reponse_text,
        "scored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def scorer_question_b0(
    benchmark_q: dict, record_b0: dict,
    annotations: dict[str, dict], run_id: str,
) -> dict:
    """Scoring B0 (pas de retrieval). Produit la meme structure que
    `scorer_question` mais avec `classe` dans CLASSES_B0 et sans
    recall / mrr / retrieved / valeurs_dans_contexte."""
    qid = benchmark_q["id"]
    cat = benchmark_q.get("category")
    reponse_text = (record_b0.get("answer_parsed") or {}).get("answer", "") or ""

    mode_annotation = None
    annotation = annotations.get(qid)
    if cat == "sans_reponse":
        exact_ok = est_abstention(reponse_text)
        detail_exact = {"format": "sans_reponse", "abstention_detectee": exact_ok}
        mode_annotation = "automatique"
    elif cat == "texte_annexes":
        if est_abstention(reponse_text):
            exact_ok = False
            detail_exact = {"format": "texte", "raison": "abstention"}
            mode_annotation = "automatique"
        elif annotation is not None:
            exact_ok = annotation.get("statut") == "juste"
            detail_exact = {
                "format": "texte",
                "statut": annotation.get("statut"),
                "complete": annotation.get("complete"),
                "elements_manquants": annotation.get("elements_manquants", []),
                "justification": annotation.get("justification"),
            }
            mode_annotation = "manuel"
        else:
            exact_ok = False
            detail_exact = {
                "format": "texte",
                "statut": "non_annotee",
                "raison": "reponse donnee mais pas d'annotation manuelle",
            }
            mode_annotation = "manuel"
    else:
        if est_abstention(reponse_text):
            exact_ok = False
            detail_exact = {"format": (benchmark_q.get("answer") or {}).get("format"),
                            "raison": "abstention"}
        else:
            exact_ok, detail_exact = exact_numerique(reponse_text, benchmark_q)
        mode_annotation = "automatique"

    classe = classer_b0(benchmark_q, reponse_text, exact_ok)
    complete = None
    if annotation is not None and cat == "texte_annexes":
        complete = annotation.get("complete")

    return {
        "run_id": run_id,
        "provenance": "b0",
        "question_id": qid,
        "category": cat,
        "classe": classe,
        "exact_ok": exact_ok,
        "detail_exact": detail_exact,
        "complete": complete,
        "mode_annotation": mode_annotation,
        "reponse_modele": reponse_text,
        "scored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# Top-20 Chroma (0 LLM, 0 API si cache chaud)
# ---------------------------------------------------------------------------
def produire_top20(questions: list[dict]) -> tuple[dict[str, list[dict]],
                                                     dict[str, list[str]], int]:
    """Lance une query top-20 par question et retourne :
    - `top20_par_qid` : {qid: [chunks top-20]}
    - `textes_par_qid` : {qid: [textes]} (ordre = rang)
    - `nb_appels_embeddings` : int, sur l'ensemble des 31 Q.
    """
    from bilanlens.embeddings import charger_encodeur
    from bilanlens.index import ouvrir_collection

    encoder = charger_encodeur()
    _, collection = ouvrir_collection(CHROMA_PATH, model=encoder.model)
    appels_avant = getattr(encoder, "_nb_vecteurs_calcules", 0)

    top20_par_qid: dict[str, list[dict]] = {}
    textes_par_qid: dict[str, list[str]] = {}
    for q in questions:
        vec = encoder.embed_query(q["question"])
        if hasattr(vec, "tolist"):
            vec = vec.tolist()
        result = collection.query(query_embeddings=[vec], n_results=20)
        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        top20 = []
        textes = []
        for i, cid in enumerate(ids):
            meta = metas[i] if i < len(metas) else {}
            top20.append({
                "rank": i + 1,
                "chunk_id": cid,
                "doc": meta.get("doc"),
                "page_physique": meta.get("page_physique"),
                "sous_numero": meta.get("sous_numero", 0),
                "distance": float(distances[i]) if i < len(distances) else None,
            })
            textes.append(documents[i] if i < len(documents) else "")
        top20_par_qid[q["id"]] = top20
        textes_par_qid[q["id"]] = textes

    appels_apres = getattr(encoder, "_nb_vecteurs_calcules", 0)
    return top20_par_qid, textes_par_qid, appels_apres - appels_avant


def textes_des_5_chunks_v1(
    record_v1: dict, textes_top20: list[str], top20: list[dict],
) -> list[str]:
    """Pour les 5 chunk_ids du run V1, retrouve les textes via le top-20
    (le top-5 V1 est TOUJOURS inclus dans ce top-20 avec la meme query)."""
    id_to_texte = {c["chunk_id"]: t for c, t in zip(top20, textes_top20)}
    return [id_to_texte.get(r["chunk_id"], "") for r in record_v1.get("retrieved", [])]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
def afficher_stats(scores: list[dict]) -> None:
    if not scores:
        print("Aucun score.")
        return
    print()
    print("=== Resume score V1 ===")
    print(f"  questions scorees   : {len(scores)}")

    # Repartition des classes.
    par_classe = {c: 0 for c in CLASSES}
    for s in scores:
        par_classe[s["classe"]] = par_classe.get(s["classe"], 0) + 1
    print()
    print("  Repartition des classes :")
    for c in CLASSES:
        print(f"    {c:<32} : {par_classe[c]}")

    # Synthese par categorie : nb de bons resultats par categorie,
    # ou "bon" = `juste` (Q avec reponse) OU `abstention_correcte`
    # (Q sans_reponse). Lecture directe : "sur X questions de cette
    # categorie, le systeme fait N la bonne chose".
    categories = ("extraction", "calcul", "comparaison",
                   "texte_annexes", "sans_reponse")
    bons_par_cat: dict[str, int] = {c: 0 for c in categories}
    total_par_cat: dict[str, int] = {c: 0 for c in categories}
    for s in scores:
        cat = s["category"]
        if cat not in total_par_cat:
            continue
        total_par_cat[cat] += 1
        if s["classe"] in ("juste", "abstention_correcte"):
            bons_par_cat[cat] += 1
    total_bons = sum(bons_par_cat.values())
    total_qs = sum(total_par_cat.values())
    print()
    print("  Bons resultats par categorie "
          "(juste OU abstention_correcte) :")
    for cat in categories:
        t = total_par_cat[cat]
        if t == 0:
            continue
        print(f"    {cat:<16} : {bons_par_cat[cat]}/{t}")
    print(f"    {'TOTAL':<16} : {total_bons}/{total_qs}")

    # Recall@k globaux (sur Q avec page attendue).
    print()
    print("  Recall@k (sur Q avec page attendue) et MRR :")
    with_pages = [s for s in scores if s["pages_attendues"]]
    n = len(with_pages)
    for k in K_LIST:
        ok = sum(1 for s in with_pages if s["recall"][f"recall_at_{k}"])
        print(f"    Recall@{k:<2} : {ok}/{n}  ({100*ok/n:.0f} %)")
    mrr_vals = [s["mrr"] for s in with_pages if s.get("mrr") is not None]
    if mrr_vals:
        print(f"    MRR      : {sum(mrr_vals)/len(mrr_vals):.3f}")

    # valeurs_dans_contexte.
    vdc_true = sum(1 for s in scores if s["valeurs_dans_contexte"] is True)
    vdc_false = sum(1 for s in scores if s["valeurs_dans_contexte"] is False)
    vdc_na = sum(1 for s in scores if s["valeurs_dans_contexte"] is None)
    print()
    print(f"  valeurs_dans_contexte : True={vdc_true}, False={vdc_false}, "
          f"N/A={vdc_na} (texte/sans_reponse)")

    # Reponses incompletes (annotation manuelle).
    incomplets = [s for s in scores if s.get("complete") is False]
    if incomplets:
        print()
        print(f"  reponses incompletes (annotation manuelle) : {len(incomplets)}")
        for s in incomplets:
            manquants = s["detail_exact"].get("elements_manquants", [])
            print(f"    {s['question_id']}  manquants={manquants}")


# ---------------------------------------------------------------------------
# Comparaison B0-strict / B0-libre / V1 (etape 8)
# ---------------------------------------------------------------------------
def afficher_stats_b0(scores: list[dict], label: str) -> None:
    if not scores:
        print(f"Aucun score {label}.")
        return
    print()
    print(f"=== Resume {label} ===")
    print(f"  questions scorees   : {len(scores)}")
    par_classe = {c: 0 for c in CLASSES_B0}
    for s in scores:
        par_classe[s["classe"]] = par_classe.get(s["classe"], 0) + 1
    print()
    print("  Repartition des classes :")
    for c in CLASSES_B0:
        print(f"    {c:<24} : {par_classe[c]}")

    categories = ("extraction", "calcul", "comparaison",
                   "texte_annexes", "sans_reponse")
    bons = {c: 0 for c in categories}
    tot = {c: 0 for c in categories}
    for s in scores:
        cat = s["category"]
        if cat not in tot:
            continue
        tot[cat] += 1
        if s["classe"] in ("juste", "abstention_correcte"):
            bons[cat] += 1
    print()
    print("  Bons resultats par categorie (juste OU abstention_correcte) :")
    total_bons = 0
    total_qs = 0
    for cat in categories:
        if tot[cat] == 0:
            continue
        print(f"    {cat:<16} : {bons[cat]}/{tot[cat]}")
        total_bons += bons[cat]
        total_qs += tot[cat]
    print(f"    {'TOTAL':<16} : {total_bons}/{total_qs}")


def _ecrire_svg_comparaison(
    bons_par_cat_par_run: dict[str, dict[str, int]],
    totaux_par_cat: dict[str, int],
    path: Path,
) -> None:
    """Genere un SVG simple de type bar chart groupe : une couleur
    par run (B0-strict, B0-libre, V1), un groupe par categorie.
    Pas de dependance matplotlib.
    """
    categories = ["extraction", "calcul", "comparaison",
                   "texte_annexes", "sans_reponse"]
    runs = ["B0-strict", "B0-libre", "V1"]
    couleurs = {"B0-strict": "#999999", "B0-libre": "#e67e22", "V1": "#2e86de"}

    largeur_cat = 180
    espace_barre = 50
    marge_x = 90
    marge_y_haut = 50
    marge_y_bas = 100
    h_graphique = 300
    w_total = marge_x + len(categories) * largeur_cat + marge_x
    h_total = marge_y_haut + h_graphique + marge_y_bas

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_total}" '
        f'height="{h_total}" viewBox="0 0 {w_total} {h_total}">',
        f'<rect width="{w_total}" height="{h_total}" fill="#ffffff"/>',
        '<text x="40" y="30" font-family="Arial" font-size="16" '
        'font-weight="bold">Bons resultats par categorie '
        '(juste OU abstention_correcte)</text>',
    ]

    # Axe Y simple : graduations 0, 0.5, 1 (ratio bons/total).
    axe_bas = marge_y_haut + h_graphique
    for frac, lbl in [(0.0, "0"), (0.5, "50 %"), (1.0, "100 %")]:
        y = axe_bas - int(frac * h_graphique)
        svg.append(
            f'<line x1="{marge_x - 10}" y1="{y}" x2="{w_total - marge_x}" '
            f'y2="{y}" stroke="#dddddd" stroke-width="1"/>'
        )
        svg.append(
            f'<text x="{marge_x - 15}" y="{y + 4}" font-family="Arial" '
            f'font-size="11" text-anchor="end" fill="#666">{lbl}</text>'
        )

    # Barres groupees.
    for i, cat in enumerate(categories):
        tot = totaux_par_cat.get(cat, 0) or 1
        x0 = marge_x + i * largeur_cat + 20
        for j, run in enumerate(runs):
            n = bons_par_cat_par_run.get(run, {}).get(cat, 0)
            frac = n / tot
            h = int(frac * h_graphique)
            xb = x0 + j * (espace_barre - 10)
            yb = axe_bas - h
            svg.append(
                f'<rect x="{xb}" y="{yb}" width="35" height="{h}" '
                f'fill="{couleurs[run]}" opacity="0.9"/>'
            )
            svg.append(
                f'<text x="{xb + 17}" y="{yb - 4}" font-family="Arial" '
                f'font-size="10" text-anchor="middle" fill="#333">'
                f'{n}/{tot}</text>'
            )
        # Label categorie.
        svg.append(
            f'<text x="{x0 + 55}" y="{axe_bas + 20}" font-family="Arial" '
            f'font-size="12" text-anchor="middle" fill="#333">{cat}</text>'
        )

    # Legende.
    lx = marge_x
    ly = h_total - 40
    for j, run in enumerate(runs):
        svg.append(
            f'<rect x="{lx + j * 150}" y="{ly}" width="18" height="12" '
            f'fill="{couleurs[run]}"/>'
        )
        svg.append(
            f'<text x="{lx + j * 150 + 24}" y="{ly + 10}" font-family="Arial" '
            f'font-size="12" fill="#333">{run}</text>'
        )
    svg.append("</svg>")
    path.write_text("\n".join(svg), encoding="utf-8")


def diagnostiquer_v1(scores_v1: list[dict]) -> dict:
    """Separe les echecs V1 en 3 groupes DISJOINTS + 1 observation
    distincte.

    Les 3 groupes d'echecs (leur union = nb_echecs) :
    - `problemes_recherche` : abstention_a_tort ET valeurs absentes
      du top-5 (recall KO + vdc False/None). V2 doit ameliorer le
      retrieval.
    - `abstentions_avec_valeurs` : abstention_a_tort ET valeurs
      presentes dans le top-5 (vdc=True), que recall@5 soit OK ou
      KO. Le modele a la matiere mais refuse. V2 doit ameliorer
      le prompt / la formule du cours.
    - `fausses` : reponse donnee mais mauvaise (toutes classes
      fausse_* et reponse_a_tort).

    Point distinct, HORS echecs :
    - `juste_malgre_recall_ko` : classe=juste ET recall@5=False.
      Le modele repond juste meme si la page attendue stricte n'est
      pas dans le top-5 (typique des comparaisons avec les 2 valeurs
      sur la meme page mais via plusieurs colonnes). Interessant
      pour la calibration de Recall@k comme proxy de la qualite.
    """
    pb_recherche: list[str] = []
    abstentions_valeurs: list[str] = []
    fausses: list[str] = []
    juste_malgre_recall_ko: list[str] = []

    for s in scores_v1:
        classe = s["classe"]
        qid = s["question_id"]
        vdc = s.get("valeurs_dans_contexte")
        rec5 = (s.get("recall") or {}).get("recall_at_5")

        if classe in ("abstention_a_tort_recall_ok",
                        "abstention_a_tort_recall_ko"):
            if vdc is True:
                abstentions_valeurs.append(qid)
            else:
                pb_recherche.append(qid)
        elif classe in ("fausse_recall_ok", "fausse_recall_ko",
                         "reponse_a_tort"):
            fausses.append(qid)
        elif classe == "juste" and rec5 is False:
            juste_malgre_recall_ko.append(qid)

    nb_echecs = (len(pb_recherche) + len(abstentions_valeurs)
                  + len(fausses))
    return {
        "problemes_recherche": pb_recherche,
        "abstentions_avec_valeurs": abstentions_valeurs,
        "fausses": fausses,
        "juste_malgre_recall_ko": juste_malgre_recall_ko,
        "nb_echecs": nb_echecs,
    }


def mode_compare(questions: list[dict]) -> int:
    """Score B0-strict, B0-libre et V1 sur le MEME benchmark et
    produit : results/scores_compare.jsonl + tableau + SVG."""
    lignes_b0 = charger_jsonl(B0_PATH)
    lignes_v1 = charger_jsonl(V1_PATH)
    b0_strict = {l["question_id"]: l for l in lignes_b0
                 if l.get("run_id") == RUN_ID_B0_STRICT}
    b0_libre = {l["question_id"]: l for l in lignes_b0
                if l.get("run_id") == RUN_ID_B0_LIBRE}
    v1 = {l["question_id"]: l for l in lignes_v1
          if l.get("run_id") == RUN_ID_V1}

    print(f"B0-strict : {len(b0_strict)}/31 reponses")
    print(f"B0-libre  : {len(b0_libre)}/31 reponses")
    print(f"V1        : {len(v1)}/31 reponses")

    # prompt_version par run.
    pv_b0_strict = (next(iter(b0_strict.values())) or {}).get("prompt_version")
    pv_b0_libre = (next(iter(b0_libre.values())) or {}).get("prompt_version")
    pv_v1 = (next(iter(v1.values())) or {}).get("prompt_version")
    print()
    print("prompt_version par run :")
    print(f"  B0-strict : {pv_b0_strict}")
    print(f"  B0-libre  : {pv_b0_libre}  <-- SYSTEM_INSTRUCTION different "
          "(voir prompts.py : SYSTEM_INSTRUCTION_B0_LIBRE, sans consigne "
          "d'abstention)")
    print(f"  V1        : {pv_v1}        (meme SYSTEM_INSTRUCTION que B0-strict)")

    # Top-20 pour V1 uniquement.
    print()
    print("=== Top-20 Chroma (V1 uniquement) ===")
    top20_par_qid, textes_par_qid, nb_appels = produire_top20(questions)
    print(f"Appels API embeddings : {nb_appels}")

    scores_tous: list[dict] = []
    # Score B0-strict.
    ann_strict = charger_annotations(run_id=RUN_ID_B0_STRICT)
    scores_b0_strict = []
    for q in questions:
        rec = b0_strict.get(q["id"])
        if rec is None:
            continue
        scores_b0_strict.append(
            scorer_question_b0(q, rec, ann_strict, RUN_ID_B0_STRICT)
        )
    # Score B0-libre.
    ann_libre = charger_annotations(run_id=RUN_ID_B0_LIBRE)
    scores_b0_libre = []
    for q in questions:
        rec = b0_libre.get(q["id"])
        if rec is None:
            continue
        scores_b0_libre.append(
            scorer_question_b0(q, rec, ann_libre, RUN_ID_B0_LIBRE)
        )
    # Score V1.
    ann_v1 = charger_annotations(run_id=RUN_ID_V1)
    scores_v1 = []
    for q in questions:
        rec = v1.get(q["id"])
        if rec is None:
            continue
        top20 = top20_par_qid.get(q["id"], [])
        textes_top20 = textes_par_qid.get(q["id"], [])
        textes_v1 = textes_des_5_chunks_v1(rec, textes_top20, top20)
        scores_v1.append(
            scorer_question(q, rec, top20, textes_v1, ann_v1,
                             run_id=RUN_ID_V1)
        )

    scores_tous = scores_b0_strict + scores_b0_libre + scores_v1
    with SCORES_COMPARE_PATH.open("w", encoding="utf-8") as f:
        for s in scores_tous:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"Ecrit : {SCORES_COMPARE_PATH.relative_to(RACINE)}  "
          f"({len(scores_tous)} lignes)")

    afficher_stats_b0(scores_b0_strict, "B0-strict")
    afficher_stats_b0(scores_b0_libre, "B0-libre")
    afficher_stats(scores_v1)

    # Table de synthese.
    categories = ["extraction", "calcul", "comparaison",
                   "texte_annexes", "sans_reponse"]
    bons_par_run: dict[str, dict[str, int]] = {}
    totaux = {c: 0 for c in categories}
    for run_label, scores in [("B0-strict", scores_b0_strict),
                               ("B0-libre", scores_b0_libre),
                               ("V1", scores_v1)]:
        bons = {c: 0 for c in categories}
        for s in scores:
            cat = s["category"]
            if cat in bons and s["classe"] in ("juste",
                                                 "abstention_correcte"):
                bons[cat] += 1
            if cat in totaux:
                totaux[cat] += 1
        bons_par_run[run_label] = bons
    for cat in totaux:
        totaux[cat] = totaux[cat] // 3  # on a compte 3x le meme total

    print()
    print("=== Tableau de comparaison (bons = juste OU abstention_correcte) ===")
    print(f"  {'categorie':<16}  {'B0-strict':>10}  {'B0-libre':>10}  "
          f"{'V1':>10}  {'total':>8}")
    for cat in categories:
        row = (
            f"  {cat:<16}  "
            f"{bons_par_run['B0-strict'][cat]:>10}  "
            f"{bons_par_run['B0-libre'][cat]:>10}  "
            f"{bons_par_run['V1'][cat]:>10}  "
            f"{totaux[cat]:>8}"
        )
        print(row)
    tt_b0s = sum(bons_par_run["B0-strict"].values())
    tt_b0l = sum(bons_par_run["B0-libre"].values())
    tt_v1 = sum(bons_par_run["V1"].values())
    tt_tot = sum(totaux.values())
    print(f"  {'TOTAL':<16}  {tt_b0s:>10}  {tt_b0l:>10}  "
          f"{tt_v1:>10}  {tt_tot:>8}")

    # Separation des echecs V1.
    diag = diagnostiquer_v1(scores_v1)
    print()
    print(f"=== Diagnostic V1 : {diag['nb_echecs']} echecs decomposes ===")
    print(f"  Problemes de recherche "
          f"({len(diag['problemes_recherche'])}) : recall@5 KO + "
          f"valeurs absentes du top-5")
    print(f"    {sorted(diag['problemes_recherche'])}")
    print(f"  Abstentions avec valeurs presentes "
          f"({len(diag['abstentions_avec_valeurs'])}) : le modele a "
          f"la matiere (recall OK ou vdc=True) mais s'abstient")
    print(f"    {sorted(diag['abstentions_avec_valeurs'])}")
    print(f"  Reponses fausses ({len(diag['fausses'])}) : reponse donnee, "
          f"mauvaise valeur")
    print(f"    {sorted(diag['fausses'])}")
    print()
    print(f"  (Point distinct) Justes malgre recall@5 KO strict "
          f"({len(diag['juste_malgre_recall_ko'])}) : page attendue "
          f"absente mais valeurs lues dans le top-5 sur une AUTRE "
          f"page que la page attendue")
    print(f"    {sorted(diag['juste_malgre_recall_ko'])}")

    # SVG.
    _ecrire_svg_comparaison(bons_par_run, totaux, COMPARISON_SVG)
    print()
    print(f"Ecrit : {COMPARISON_SVG.relative_to(RACINE)}")

    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parseur = argparse.ArgumentParser(description="Score du run V1.")
    parseur.add_argument(
        "--mode", choices=["v1", "compare"], default="v1",
        help="'v1' : score le dernier run V1 (default). 'compare' : "
             "compare B0-strict / B0-libre / V1 (etape 8)."
    )
    parseur.add_argument(
        "--run-id", default=None,
        help="run_id a scorer dans results/v1.jsonl. Default : le "
             "dernier run_id trouve dans v1.jsonl. Ignore en mode "
             "compare (run_ids pin par le code)."
    )
    args = parseur.parse_args()

    questions = charger_jsonl(BENCH_PATH)
    print(f"Questions chargees : {len(questions)}")

    if args.mode == "compare":
        return mode_compare(questions)

    lignes_v1 = charger_jsonl(V1_PATH)
    if not lignes_v1:
        print(f"ERREUR : {V1_PATH} vide ou absent.")
        return 1
    run_id = args.run_id or lignes_v1[-1]["run_id"]
    v1_run = [l for l in lignes_v1 if l.get("run_id") == run_id]
    v1_par_qid = {l["question_id"]: l for l in v1_run}
    print(f"Run V1 : {run_id}  ({len(v1_run)} reponses)")

    annotations = charger_annotations(run_id=run_id)
    print(f"Annotations manuelles chargees (run {run_id}) : {len(annotations)}")

    print()
    print("=== Top-20 Chroma sur les 31 questions ===")
    top20_par_qid, textes_par_qid, nb_appels = produire_top20(questions)
    print(f"Appels API embeddings sur les 31 Q : {nb_appels}")

    # Ecrire retrieval_top20.jsonl.
    with TOP20_PATH.open("w", encoding="utf-8") as f:
        for q in questions:
            qid = q["id"]
            f.write(json.dumps({
                "question_id": qid,
                "category": q.get("category"),
                "run_id_v1": run_id,
                "top20": top20_par_qid.get(qid, []),
            }, ensure_ascii=False) + "\n")
    print(f"Ecrit : {TOP20_PATH.relative_to(RACINE)}")

    # Scorer chaque question.
    scores = []
    for q in questions:
        qid = q["id"]
        rec_v1 = v1_par_qid.get(qid)
        if rec_v1 is None:
            continue
        top20 = top20_par_qid.get(qid, [])
        textes_top20 = textes_par_qid.get(qid, [])
        textes_v1 = textes_des_5_chunks_v1(rec_v1, textes_top20, top20)
        score = scorer_question(q, rec_v1, top20, textes_v1, annotations)
        scores.append(score)

    with SCORES_PATH.open("w", encoding="utf-8") as f:
        for s in scores:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"Ecrit : {SCORES_PATH.relative_to(RACINE)}  ({len(scores)} lignes)")

    afficher_stats(scores)
    return 0


if __name__ == "__main__":
    sys.exit(main())
