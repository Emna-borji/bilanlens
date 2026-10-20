"""Contrôles de cohérence du bilan — tests unitaires."""
import pytest

from bilanlens.consistency import check_balance_sheet, has_warnings


def _by_name(checks):
    return {check["name"]: check for check in checks}


def test_balanced_sheet_passes_all_checks():
    values = {
        "total_assets": 1000,
        "equity": 400,
        "total_debt": 600,
        "current_assets": 600,
        "non_current_assets": 400,
        "share_capital": 200,
        "reserves": 150,
        "net_income": 50,
    }
    checks = _by_name(check_balance_sheet(values))
    assert checks["Total actif = capitaux propres + dettes"]["status"] == "ok"
    assert (
        checks["Actifs courants + non courants = total actif"]["status"]
        == "ok"
    )
    assert (
        checks["Capital + réserves + résultat ≈ capitaux propres"]["status"]
        == "ok"
    )
    assert not has_warnings(check_balance_sheet(values))


def test_total_actif_mismatch_above_tolerance_warns():
    values = {
        "total_assets": 1000,
        "equity": 400,
        "total_debt": 580,  # 400 + 580 = 980 → écart 2 % > 1 %
    }
    checks = _by_name(check_balance_sheet(values))
    detail = checks.get("Total actif ≠ capitaux propres + dettes")
    assert detail is not None
    assert detail["status"] == "warning"
    assert detail["gap"] > 0.01


def test_total_actif_mismatch_within_tolerance_ok():
    values = {
        "total_assets": 1000,
        "equity": 400,
        "total_debt": 595,  # 400 + 595 = 995 → écart 0,5 % ≤ 1 %
    }
    checks = _by_name(check_balance_sheet(values))
    assert checks["Total actif = capitaux propres + dettes"]["status"] == "ok"


def test_minority_interests_included():
    values = {
        "total_assets": 1050,
        "equity": 400,
        "total_debt": 600,
        "minority_interests": 50,
    }
    checks = _by_name(check_balance_sheet(values))
    assert checks["Total actif = capitaux propres + dettes"]["status"] == "ok"


def test_actifs_courants_decomposition_mismatch():
    values = {
        "total_assets": 1000,
        "current_assets": 500,
        "non_current_assets": 450,  # 950 vs 1000 = 5 %
    }
    checks = _by_name(check_balance_sheet(values))
    detail = checks["Actifs courants + non courants ≠ total actif"]
    assert detail["status"] == "warning"


def test_equity_decomposition_mismatch_signals_other_components():
    values = {
        "equity": 500,
        "share_capital": 200,
        "reserves": 100,
        "net_income": 50,  # 350 vs 500 : 30 %
    }
    checks = _by_name(check_balance_sheet(values))
    detail = checks["Capital + réserves + résultat ≠ capitaux propres"]
    assert detail["status"] == "warning"
    assert "primes" in detail["detail"].lower() or "report" in detail["detail"].lower()


def test_missing_values_skip_checks_without_crash():
    values = {"total_assets": 1000}
    checks = _by_name(check_balance_sheet(values))
    for name, check in checks.items():
        assert check["status"] == "skipped"
    assert not has_warnings(checks.values())
