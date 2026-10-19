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

    # L'OCR est bruité : on tolère une marge plus large que pour le .txt.
    # Les postes principaux doivent être retrouvés.
    assert values.get("current_assets") == pytest.approx(3500, abs=20)
    assert values.get("current_liabilities") == pytest.approx(2000, abs=20)
    assert values.get("total_assets") == pytest.approx(8500, abs=20)
    assert values.get("equity") == pytest.approx(4000, abs=20)
    assert values.get("revenue") == pytest.approx(12000, abs=20)

    # Ratios : accepter 3 % de marge pour absorber le bruit OCR.
    assert ratios["current_ratio"] == pytest.approx(1.75, abs=0.03)
    assert ratios["debt_to_equity"] == pytest.approx(1.125, abs=0.03)
    assert ratios["net_margin"] * 100 == pytest.approx(5.83, abs=0.1)
    assert ratios["equity_ratio"] * 100 == pytest.approx(47.06, abs=0.3)


# ---------------------------------------------------------------------------
# SOTUVER scanné (bilan — pages 2-3 du PDF réel, rendues en images).
#
# Les ratios « d'orientation » qui ne dépendent que des sous-totaux
# bilan (liquidité générale, autonomie financière) doivent rester
# proches de la cible publique, même avec le bruit OCR sur 3 colonnes.
# Les ratios composés qui dépendent du compte de résultat (marge nette,
# ROE) ne sont pas calculables car le CR est sur d'autres pages.
# ---------------------------------------------------------------------------
def test_sotuver_scanned_triggers_ocr_and_matches_balance_targets():
    _values, ratios, _checks, extra = run_pipeline(load("sotuver_scanned.pdf"))

    assert extra["used_ocr"] is True

    # Liquidité : CA / CL ne dépend pas de l'extraction du CR.
    assert ratios["current_ratio"] == pytest.approx(1.14, abs=0.05)
    # Autonomie financière : CP / Total actif, idem.
    assert ratios["equity_ratio"] * 100 == pytest.approx(34.53, abs=0.5)
