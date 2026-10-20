"""Tests OCR — PDF scannés (images) de test1 et de SOTUVER.

Marqués 'ocr' : automatiquement skip si Tesseract (binaire + données
'fra' + 'eng') n'est pas disponible, cf. tests/conftest.py.
"""
import pytest

from conftest import load
from _pipeline import run_pipeline


pytestmark = pytest.mark.ocr


# ---------------------------------------------------------------------------
# test1 scanné : les mêmes libellés que test1_complet_ordre_piege.txt,
# mais rendus en pixels — le pipeline doit déclencher l'OCR.
# ---------------------------------------------------------------------------
def test_test1_scanned_triggers_ocr_and_computes_core_ratios():
    values, ratios, _checks, extra = run_pipeline(load("test1_scanned.pdf"))

    assert extra["used_ocr"] is True, (
        "L'OCR doit être déclenché sur un PDF image."
    )

    # Les postes principaux doivent être retrouvés exactement.
    assert values.get("current_assets") == 3500
    assert values.get("current_liabilities") == 2000
    assert values.get("total_assets") == 8500
    assert values.get("equity") == 4000
    assert values.get("revenue") == 12000

    # Tolérances OCR : abs=0.01 pour les ratios, abs=0.1 pour les %.
    assert ratios["current_ratio"] == pytest.approx(1.75, abs=0.01)
    assert ratios["debt_to_equity"] == pytest.approx(1.125, abs=0.01)
    assert ratios["net_margin"] * 100 == pytest.approx(5.83, abs=0.1)
    assert ratios["equity_ratio"] * 100 == pytest.approx(47.06, abs=0.1)
    assert ratios["roe"] * 100 == pytest.approx(17.50, abs=0.1)


# ---------------------------------------------------------------------------
# SOTUVER scanné : pages 2-4 du PDF réel rendues en images.
# Pages 2-3 = bilan, page 4 = état de résultat.
# Tolérances resserrées : abs=0.01 pour les ratios, abs=0.1 pour les %.
# ---------------------------------------------------------------------------
def test_sotuver_scanned_triggers_ocr_and_matches_all_targets():
    _values, ratios, _checks, extra = run_pipeline(load("sotuver_scanned.pdf"))

    assert extra["used_ocr"] is True

    assert ratios["current_ratio"] == pytest.approx(1.14, abs=0.01)
    assert ratios["debt_to_equity"] == pytest.approx(1.90, abs=0.01)
    assert ratios["equity_ratio"] * 100 == pytest.approx(34.53, abs=0.1)
    assert ratios["roe"] * 100 == pytest.approx(11.49, abs=0.1)
    assert ratios["net_margin"] * 100 == pytest.approx(13.79, abs=0.1)
