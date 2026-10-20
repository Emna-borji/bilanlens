"""Tests sur des bilans réels publics (bvmt.com.tn).

Sociétés industrielles / commerciales tunisiennes 2024.
Chaque test vérifie les valeurs comptables lues directement dans le
PDF ainsi que les contrôles de cohérence (bilan équilibré).
"""
import pytest

from conftest import load
from _pipeline import run_pipeline
from bilanlens.consistency import has_warnings
from bilanlens.sector import detect_out_of_scope_sector


pytestmark = pytest.mark.real


def _assert_structural_balance_ok(checks, file_name):
    """Les deux contrôles de bilan structurels doivent passer.

    La décomposition « Capital + Réserves + Résultat ≈ CP » peut
    légitimement échouer (primes, report à nouveau...) et n'est pas
    testée ici.
    """
    for check in checks:
        name = check["name"]
        if (
            name.startswith("Total actif")
            or name.startswith("Actifs courants")
        ) and check["status"] == "warning":
            pytest.fail(f"{file_name} : {check['detail']}")


# ---------------------------------------------------------------------------
# SOTUVER 2024 (états financiers annuels individuels).
# Valeurs cibles fournies par l'utilisateur.
# ---------------------------------------------------------------------------
def test_sotuver_2024_ratios_match_expected():
    values, ratios, checks, extra = run_pipeline(load("real_sotuver_2024.pdf"))

    assert extra["period"] == "31/12/2024"
    assert detect_out_of_scope_sector(extra["text"]) is None

    assert ratios["current_ratio"] == pytest.approx(1.14, abs=0.01)
    assert ratios["debt_to_equity"] == pytest.approx(1.90, abs=0.02)
    assert ratios["net_margin"] * 100 == pytest.approx(13.79, abs=0.05)
    assert ratios["roe"] * 100 == pytest.approx(11.49, abs=0.05)
    assert ratios["equity_ratio"] * 100 == pytest.approx(34.53, abs=0.05)

    _assert_structural_balance_ok(checks, "real_sotuver_2024.pdf")


# ---------------------------------------------------------------------------
# Monoprix 2024 — bilan consolidé.
# Source : bvmt.com.tn, états financiers consolidés 31/12/2024.
# Valeurs cibles fournies par l'utilisateur (en dinars).
# Vérification : CP(49 423 396) + Minoritaires(30 541 866) +
# Total passifs(299 295 661) = Total actif(379 260 923).
# ---------------------------------------------------------------------------
def test_monoprix_consolide_2024_exact_values():
    values, ratios, checks, extra = run_pipeline(
        load("real_monoprix_consolide_2024.pdf")
    )

    assert extra["period"] == "31/12/2024"
    assert detect_out_of_scope_sector(extra["text"]) is None

    assert values["current_assets"] == 195_591_986
    assert values["current_liabilities"] == 261_958_403
    assert values["total_assets"] == 379_260_923
    assert values["equity"] == 49_423_396
    assert values["total_debt"] == 299_295_661
    assert values["long_term_debt"] == 37_337_258
    assert values["revenue"] == 753_997_490
    assert values["net_income"] == 6_872_913
    assert values["inventory"] == 83_323_402  # Stocks nets (rang 1)
    assert values["minority_interests"] == 30_541_866

    # Vérification arithmétique explicite.
    assert (
        values["equity"]
        + values["minority_interests"]
        + values["total_debt"]
        == values["total_assets"]
    )

    _assert_structural_balance_ok(checks, "real_monoprix_consolide_2024.pdf")


# ---------------------------------------------------------------------------
# SFBT 2024 — bilan individuel.
# Valeurs lues directement dans le PDF, en dinars (3 décimales).
# ---------------------------------------------------------------------------
def test_sfbt_2024_exact_values():
    values, ratios, checks, extra = run_pipeline(load("real_sfbt_2024.pdf"))

    assert extra["period"] == "31/12/2024"
    assert detect_out_of_scope_sector(extra["text"]) is None

    assert values["total_assets"] == pytest.approx(1_281_772_854.965, abs=1)
    assert values["equity"] == pytest.approx(954_001_282.196, abs=1)
    assert values["current_assets"] == pytest.approx(725_268_211.109, abs=1)
    assert values["non_current_assets"] == pytest.approx(556_504_643.856, abs=1)
    assert values["current_liabilities"] == pytest.approx(211_358_188.371, abs=1)
    assert values["long_term_debt"] == pytest.approx(116_413_384.398, abs=1)
    assert values["total_debt"] == pytest.approx(327_771_572.769, abs=1)
    assert values["revenue"] == pytest.approx(836_585_626.332, abs=1)
    assert values["net_income"] == pytest.approx(252_152_023.507, abs=1)
    assert values["operating_income"] == pytest.approx(202_748_424.667, abs=1)

    _assert_structural_balance_ok(checks, "real_sfbt_2024.pdf")


# ---------------------------------------------------------------------------
# Ciments de Bizerte 2024 — société en difficulté, résultat négatif.
# Valeurs lues directement dans le PDF.
# ---------------------------------------------------------------------------
def test_ciments_bizerte_2024_exact_values():
    values, ratios, checks, extra = run_pipeline(
        load("real_ciments_bizerte_2024.pdf")
    )

    assert extra["period"] == "31/12/2024"
    assert detect_out_of_scope_sector(extra["text"]) is None

    assert values["total_assets"] == 388_668_436
    assert values["equity"] == 143_302_286
    assert values["long_term_debt"] == 67_959_717
    assert values["current_liabilities"] == 177_406_433
    assert values["total_debt"] == 245_366_150
    assert values["net_income"] == -44_790_355
    assert values["share_capital"] == 44_047_290
    assert values["reserves"] == 100_809_614
    assert values["revenue"] == 27_838_606

    # Contrôle arithmétique : CP + Dettes = Total actif
    assert values["equity"] + values["total_debt"] == values["total_assets"]

    _assert_structural_balance_ok(checks, "real_ciments_bizerte_2024.pdf")


# ---------------------------------------------------------------------------
# Délice Holding 2024 — holding : certains ratios ne sont pas
# calculables (pas de chiffre d'affaires classique). Smoke-test.
# ---------------------------------------------------------------------------
def test_delice_holding_2024_pipeline_runs():
    values, _ratios, checks, extra = run_pipeline(
        load("real_delice_holding_2024.pdf")
    )

    assert extra["period"] == "31/12/2024"
    assert detect_out_of_scope_sector(extra["text"]) is None

    # Les postes essentiels d'un bilan de holding sont lus.
    assert values.get("total_assets") is not None
    assert values.get("equity") is not None

    _assert_structural_balance_ok(checks, "real_delice_holding_2024.pdf")


# ---------------------------------------------------------------------------
# Monoprix 2024 bilan individuel (ancien) — smoke-test additionnel.
# ---------------------------------------------------------------------------
def test_monoprix_individuel_2024_pipeline_runs():
    values, _ratios, checks, extra = run_pipeline(
        load("real_monoprix_2024.pdf")
    )

    assert extra["period"] == "31/12/2024"
    assert detect_out_of_scope_sector(extra["text"]) is None

    _assert_structural_balance_ok(checks, "real_monoprix_2024.pdf")
