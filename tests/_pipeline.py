"""Pipeline de test commun : charge un fichier → ratios + checks."""
from datetime import datetime

from finsight.extraction import extract_document
from finsight.mapping import map_candidates
from finsight.analysis import complete_financial_values, calculate_ratios
from finsight.consistency import check_balance_sheet


def _to_date(period):
    try:
        return datetime.strptime(period, "%d/%m/%Y").date()
    except Exception:
        return datetime.min.date()


def run_pipeline(uploaded, keep_period="latest"):
    """Extraction → mapping (rank-aware) → ratios + checks.

    Retourne : (values, ratios, checks, extra)
      - values : postes complétés
      - ratios : dict key → float ou None
      - checks : liste de contrôles de cohérence
      - extra  : dict informatif (period choisie, used_ocr, candidates…)
    """
    extracted = extract_document(uploaded)
    candidates = map_candidates(
        extracted["text"],
        records=extracted.get("records") or None,
    )

    periods = {c["period"] for c in candidates if c.get("period")}
    chosen_period = None
    if periods:
        chosen_period = max(periods, key=_to_date)
        if keep_period == "latest":
            candidates = [
                c for c in candidates if c.get("period") == chosen_period
            ]

    values = {}
    best_rank = {}
    for c in candidates:
        key = c.get("key")
        if not key:
            continue
        rank = c.get("rank", 0)
        if key not in values or rank > best_rank[key]:
            values[key] = c["value"]
            best_rank[key] = rank

    completed = complete_financial_values(values)
    ratios = {r["key"]: r["value"] for r in calculate_ratios(completed)}
    checks = check_balance_sheet(completed)

    extra = {
        "period": chosen_period,
        "used_ocr": extracted.get("used_ocr", False),
        "candidates": candidates,
        "text": extracted["text"],
    }
    return completed, ratios, checks, extra
