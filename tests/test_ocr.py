"""Tests OCR — PDF scannés (images) de test1 et de SOTUVER.

Marqués 'ocr' : automatiquement skip si Tesseract (binaire + données
'fra' + 'eng') n'est pas disponible, cf. tests/conftest.py.
"""
import pytest

from conftest import charger
from _pipeline import executer_pipeline


pytestmark = pytest.mark.ocr


# ---------------------------------------------------------------------------
# test1 scanné : les mêmes libellés que test1_complet_ordre_piege.txt,
# mais rendus en pixels — le pipeline doit déclencher l'OCR.
# ---------------------------------------------------------------------------
def test_test1_scanne_declenche_ocr_et_calcule_ratios_cles():
    valeurs, ratios, _controles, extra = executer_pipeline(charger("test1_scanned.pdf"))

    assert extra["ocr_utilise"] is True, (
        "L'OCR doit être déclenché sur un PDF image."
    )

    # Les postes principaux doivent être retrouvés exactement.
    assert valeurs.get("actifs_courants") == 3500
    assert valeurs.get("passifs_courants") == 2000
    assert valeurs.get("total_actif") == 8500
    assert valeurs.get("capitaux_propres") == 4000
    assert valeurs.get("chiffre_affaires") == 12000

    # Tolérances OCR : abs=0.01 pour les ratios, abs=0.1 pour les %.
    assert ratios["liquidite_generale"] == pytest.approx(1.75, abs=0.01)
    assert ratios["endettement"] == pytest.approx(1.125, abs=0.01)
    assert ratios["marge_nette"] * 100 == pytest.approx(5.83, abs=0.1)
    assert ratios["autonomie_financiere"] * 100 == pytest.approx(47.06, abs=0.1)
    assert ratios["rentabilite_capitaux_propres"] * 100 == pytest.approx(17.50, abs=0.1)


# ---------------------------------------------------------------------------
# SOTUVER scanné : pages 2-4 du PDF réel rendues en images.
# Pages 2-3 = bilan, page 4 = état de résultat.
# Tolérances resserrées : abs=0.01 pour les ratios, abs=0.1 pour les %.
# ---------------------------------------------------------------------------
def test_sotuver_scanne_declenche_ocr_et_correspond_toutes_cibles():
    _valeurs, ratios, _controles, extra = executer_pipeline(charger("sotuver_scanned.pdf"))

    assert extra["ocr_utilise"] is True

    assert ratios["liquidite_generale"] == pytest.approx(1.14, abs=0.01)
    assert ratios["endettement"] == pytest.approx(1.90, abs=0.01)
    assert ratios["autonomie_financiere"] * 100 == pytest.approx(34.53, abs=0.1)
    assert ratios["rentabilite_capitaux_propres"] * 100 == pytest.approx(11.49, abs=0.1)
    assert ratios["marge_nette"] * 100 == pytest.approx(13.79, abs=0.1)
