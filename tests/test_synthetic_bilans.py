"""Bilans synthétiques : formats variés (PCG, IFRS, Excel, CSV, UPPERCASE,
pièges autour des totaux)."""
import pytest

from conftest import load
from _pipeline import run_pipeline
from bilanlens.consistency import has_warnings


# ---------------------------------------------------------------------------
# PCG français — libellés classiques du Plan Comptable Général.
# ---------------------------------------------------------------------------
def test_synth_pcg_fr():
    values, ratios, checks, _ = run_pipeline(load("synth_pcg_fr.txt"))

    assert values["non_current_assets"] == 6200
    assert values["current_assets"] == 4800
    assert values["total_assets"] == 11000
    assert values["equity"] == 5700
    assert values["long_term_debt"] == 2600
    assert values["current_liabilities"] == 2700
    assert values["total_debt"] == 5300
    assert values["revenue"] == 18000
    assert values["net_income"] == 1200

    assert ratios["current_ratio"] == pytest.approx(4800 / 2700, abs=0.01)
    assert ratios["debt_to_equity"] == pytest.approx(5300 / 5700, abs=0.01)
    assert ratios["net_margin"] == pytest.approx(1200 / 18000, abs=0.001)
    assert ratios["roe"] == pytest.approx(1200 / 5700, abs=0.001)
    assert ratios["equity_ratio"] == pytest.approx(5700 / 11000, abs=0.001)

    # Contrôles de cohérence : capitaux propres + dettes = total actif, etc.
    assert not has_warnings(checks), [
        (c["name"], c["status"], c["detail"]) for c in checks
    ]


# ---------------------------------------------------------------------------
# IFRS en anglais.
# ---------------------------------------------------------------------------
def test_synth_ifrs_en():
    values, ratios, checks, _ = run_pipeline(load("synth_ifrs_en.txt"))

    assert values["non_current_assets"] == 4200
    assert values["current_assets"] == 3800
    assert values["total_assets"] == 8000
    assert values["equity"] == 3000
    assert values["long_term_debt"] == 2400
    assert values["current_liabilities"] == 2600
    assert values["revenue"] == 12000
    assert values["net_income"] == 400
    assert values["inventory"] == 1600

    assert ratios["current_ratio"] == pytest.approx(3800 / 2600, abs=0.01)
    assert ratios["debt_to_equity"] == pytest.approx(5000 / 3000, abs=0.01)
    assert ratios["net_margin"] == pytest.approx(400 / 12000, abs=0.001)
    assert ratios["roe"] == pytest.approx(400 / 3000, abs=0.001)
    assert ratios["equity_ratio"] == pytest.approx(3000 / 8000, abs=0.001)

    assert not has_warnings(checks)


# ---------------------------------------------------------------------------
# Libellés en MAJUSCULES SANS ACCENTS (variante SCF tunisien formelle).
# ---------------------------------------------------------------------------
def test_synth_uppercase_sans_accents():
    values, ratios, checks, _ = run_pipeline(
        load("synth_uppercase_sans_accents.txt")
    )

    assert values["current_assets"] == 1900
    assert values["non_current_assets"] == 2400
    assert values["total_assets"] == 4300
    assert values["equity"] == 2000
    assert values["long_term_debt"] == 1100
    assert values["current_liabilities"] == 1200
    assert values["total_debt"] == 2300
    assert values["revenue"] == 7500
    assert values["net_income"] == 300

    assert ratios["current_ratio"] == pytest.approx(1900 / 1200, abs=0.01)
    assert ratios["debt_to_equity"] == pytest.approx(2300 / 2000, abs=0.01)
    assert ratios["equity_ratio"] == pytest.approx(2000 / 4300, abs=0.01)
    assert not has_warnings(checks)


# ---------------------------------------------------------------------------
# CSV avec colonnes N / N-1 / N-2 : il faut prendre la dernière.
# ---------------------------------------------------------------------------
def test_synth_csv_bilan_latest_period():
    values, ratios, _checks, extra = run_pipeline(load("synth_csv_bilan.csv"))

    assert extra["period"] == "31/12/2025"

    # Valeurs 2025 (pas 2024 ni 2023).
    assert values["non_current_assets"] == 3800
    assert values["current_assets"] == 3000
    assert values["total_assets"] == 6800
    assert values["equity"] == 2800
    assert values["long_term_debt"] == 1900
    assert values["total_debt"] == 4000
    assert values["revenue"] == 9500
    assert values["net_income"] == 400

    assert ratios["current_ratio"] == pytest.approx(3000 / 2100, abs=0.01)
    assert ratios["debt_to_equity"] == pytest.approx(4000 / 2800, abs=0.01)


# ---------------------------------------------------------------------------
# Excel multi-feuilles (Bilan + Compte de résultat).
# ---------------------------------------------------------------------------
def test_synth_excel_multisheet():
    values, ratios, checks, extra = run_pipeline(
        load("synth_excel_multisheet.xlsx")
    )

    assert extra["period"] == "31/12/2025"
    assert values["non_current_assets"] == 4000
    assert values["current_assets"] == 3200
    assert values["total_assets"] == 7200
    assert values["equity"] == 3500
    assert values["long_term_debt"] == 1800
    assert values["current_liabilities"] == 1900
    assert values["total_debt"] == 3700
    assert values["revenue"] == 10500
    assert values["net_income"] == 600
    assert values["cost_of_goods_sold"] == 6200

    assert ratios["current_ratio"] == pytest.approx(3200 / 1900, abs=0.01)
    assert ratios["debt_to_equity"] == pytest.approx(3700 / 3500, abs=0.01)
    assert ratios["net_margin"] == pytest.approx(600 / 10500, abs=0.001)
    assert ratios["equity_ratio"] == pytest.approx(3500 / 7200, abs=0.001)

    assert not has_warnings(checks)


# ---------------------------------------------------------------------------
# Pièges : lignes « Autres ... » et « Total X et Y » placées avant les
# vrais sous-totaux. Les vrais sous-totaux doivent gagner.
# ---------------------------------------------------------------------------
def test_synth_pieges_autres_totaux():
    values, ratios, checks, _ = run_pipeline(
        load("synth_pieges_autres_total.txt")
    )

    # Les vrais totaux l'emportent sur les lignes « Autres ».
    assert values["current_assets"] == 2900  # Total des actifs courants
    assert values["non_current_assets"] == 6400  # Immobilisations nettes
    assert values["total_assets"] == 9300
    assert values["equity"] == 3500  # Total des capitaux propres, pas Capital
    assert values["long_term_debt"] == 2800
    assert values["current_liabilities"] == 3000
    assert values["total_debt"] == 5800
    assert values["revenue"] == 11500  # Chiffre d'affaires, pas Autres produits
    assert values["net_income"] == 500

    assert ratios["current_ratio"] == pytest.approx(2900 / 3000, abs=0.01)
    assert ratios["debt_to_equity"] == pytest.approx(5800 / 3500, abs=0.01)

    # Les trois contrôles de cohérence passent (bilan équilibré).
    assert not has_warnings(checks), [
        (c["name"], c["detail"]) for c in checks
    ]
