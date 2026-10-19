"""Tests contre les valeurs de RESULTATS_ATTENDUS.txt (test1 à test3)."""
import pytest

from conftest import load
from _pipeline import run_pipeline


def _run(file_name):
    values, ratios, _checks, _extra = run_pipeline(load(file_name))
    return values, ratios


# ---------------------------------------------------------------------------
# TEST 1 : « Autres ... » et « Total passif et capitaux propres » placés avant
# les vrais totaux (piège d'ordre).
# ---------------------------------------------------------------------------
def test_test1_txt_values_and_ratios():
    values, ratios = _run("test1_complet_ordre_piege.txt")

    # Les postes-clé doivent provenir des libellés EXACTS, pas des pièges.
    assert values["current_assets"] == 3500
    assert values["current_liabilities"] == 2000
    assert values["total_assets"] == 8500
    # IMPORTANT : « Total passif et capitaux propres : 8 500 » placé avant
    # « Capitaux propres : 4 000 » ne doit PAS être mappé à equity.
    assert values["equity"] == 4000
    assert values["total_debt"] == 4500
    assert values["revenue"] == 12000
    assert values["net_income"] == 700
    assert values["cost_of_goods_sold"] == 6800
    assert values["supplier_payables"] == 1400
    assert values["purchases_incl_vat"] == 8330
    assert values["inventory"] == 1200
    assert values["receivables"] == 1500
    assert values["beginning_inventory"] == 1000
    assert values["ending_inventory"] == 1200
    assert values["share_price"] == 42
    assert values["earnings_per_share"] == pytest.approx(3.5, abs=0.01)
    assert values["dividend_per_share"] == pytest.approx(1.2, abs=0.01)

    assert ratios["current_ratio"] == pytest.approx(1.75, abs=0.01)
    assert ratios["quick_ratio"] == pytest.approx(1.15, abs=0.01)
    assert ratios["debt_to_equity"] == pytest.approx(1.125, abs=0.01)
    assert ratios["equity_ratio"] * 100 == pytest.approx(47.06, abs=0.05)
    assert ratios["net_margin"] * 100 == pytest.approx(5.83, abs=0.05)
    assert ratios["roe"] * 100 == pytest.approx(17.50, abs=0.05)
    assert ratios["roa"] * 100 == pytest.approx(8.24, abs=0.05)
    assert ratios["inventory_turnover"] == pytest.approx(6.18, abs=0.02)
    assert ratios["receivables_days"] == pytest.approx(45.6, abs=0.2)
    assert ratios["supplier_days"] == pytest.approx(61.3, abs=0.2)
    assert ratios["per"] == pytest.approx(12.0, abs=0.05)
    assert ratios["dividend_yield"] * 100 == pytest.approx(2.86, abs=0.05)


# ---------------------------------------------------------------------------
# TEST 2 : 2 colonnes (2024/2025), notes (B.1), perte entre parenthèses.
# ---------------------------------------------------------------------------
def test_test2_txt_values_and_ratios():
    values, ratios = _run("test2_perte_colonnes_notes.txt")

    # Les valeurs doivent provenir de la colonne 2025, pas 2024.
    assert values["current_assets"] == 2400
    assert values["inventory"] == 900
    assert values["total_assets"] == 6000
    assert values["current_liabilities"] == 2800
    assert values["long_term_debt"] == 1700
    assert values["equity"] == 1500
    assert values["revenue"] == 8000
    assert values["net_income"] == -250  # parenthèses = perte

    assert ratios["current_ratio"] == pytest.approx(0.86, abs=0.01)
    assert ratios["quick_ratio"] == pytest.approx(0.54, abs=0.01)
    assert ratios["debt_to_equity"] == pytest.approx(3.00, abs=0.02)
    assert ratios["equity_ratio"] * 100 == pytest.approx(25.0, abs=0.1)
    assert ratios["net_margin"] * 100 == pytest.approx(-3.13, abs=0.05)
    assert ratios["roe"] * 100 == pytest.approx(-16.67, abs=0.1)
    assert ratios["roa"] * 100 == pytest.approx(-4.17, abs=0.1)


# ---------------------------------------------------------------------------
# TEST 3 : aucun sous-total, l'app doit RECONSTITUER.
# ---------------------------------------------------------------------------
def test_test3_txt_values_and_ratios():
    values, ratios = _run("test3_sans_totaux.txt")

    # Les composants élémentaires doivent être lus.
    assert values["inventory"] == 150000
    assert values["receivables"] == 120000
    assert values["cash"] == 80000
    assert values["share_capital"] == 250000
    assert values["reserves"] == 90000
    assert values["net_income"] == 60000
    assert values["long_term_debt"] == 200000
    assert values["supplier_payables"] == 110000
    assert values["tax_social_payables"] == 40000
    assert values["revenue"] == 900000
    assert values["non_current_assets"] == 400000

    # Les sous-totaux doivent être reconstitués.
    assert values["current_assets"] == 350000
    assert values["current_liabilities"] == 150000
    assert values["equity"] == 400000
    assert values["total_assets"] == 750000

    assert ratios["current_ratio"] == pytest.approx(2.33, abs=0.01)
    assert ratios["quick_ratio"] == pytest.approx(1.33, abs=0.01)
    assert ratios["debt_to_equity"] == pytest.approx(0.88, abs=0.02)
    assert ratios["equity_ratio"] * 100 == pytest.approx(53.33, abs=0.05)
    assert ratios["net_margin"] * 100 == pytest.approx(6.67, abs=0.05)
    assert ratios["roe"] * 100 == pytest.approx(15.0, abs=0.1)
    assert ratios["roa"] * 100 == pytest.approx(8.0, abs=0.1)
