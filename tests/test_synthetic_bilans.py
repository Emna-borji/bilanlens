"""Bilans synthétiques : formats variés (PCG, IFRS, Excel, CSV, UPPERCASE,
pièges autour des totaux)."""
import pytest

from conftest import charger
from _pipeline import executer_pipeline
from bilanlens.consistency import a_des_alertes


# ---------------------------------------------------------------------------
# PCG français — libellés classiques du Plan Comptable Général.
# ---------------------------------------------------------------------------
def test_synth_pcg_fr():
    valeurs, ratios, controles, _ = executer_pipeline(charger("synth_pcg_fr.txt"))

    assert valeurs["actifs_non_courants"] == 6200
    assert valeurs["actifs_courants"] == 4800
    assert valeurs["total_actif"] == 11000
    assert valeurs["capitaux_propres"] == 5700
    assert valeurs["dettes_long_terme"] == 2600
    assert valeurs["passifs_courants"] == 2700
    assert valeurs["total_dettes"] == 5300
    assert valeurs["chiffre_affaires"] == 18000
    assert valeurs["resultat_net"] == 1200

    assert ratios["liquidite_generale"] == pytest.approx(4800 / 2700, abs=0.01)
    assert ratios["endettement"] == pytest.approx(5300 / 5700, abs=0.01)
    assert ratios["marge_nette"] == pytest.approx(1200 / 18000, abs=0.001)
    assert ratios["rentabilite_capitaux_propres"] == pytest.approx(1200 / 5700, abs=0.001)
    assert ratios["autonomie_financiere"] == pytest.approx(5700 / 11000, abs=0.001)

    # Contrôles de cohérence : capitaux propres + dettes = total actif, etc.
    assert not a_des_alertes(controles), [
        (c["nom"], c["statut"], c["detail"]) for c in controles
    ]


# ---------------------------------------------------------------------------
# IFRS en anglais — virgule utilisée comme séparateur de milliers
# (« 1,250 » = mille deux cent cinquante, pas 1,25).
# ---------------------------------------------------------------------------
def test_synth_ifrs_en_comma_thousands():
    valeurs, ratios, controles, extra = executer_pipeline(
        charger("synth_ifrs_en_comma_thousands.txt")
    )

    assert valeurs["actifs_non_courants"] == 12_345_000
    assert valeurs["actifs_courants"] == 7_250
    assert valeurs["stocks"] == 3_250
    assert valeurs["creances_clients"] == 2_750
    assert valeurs["tresorerie"] == 1_250
    assert valeurs["total_actif"] == 19_595_000
    assert valeurs["capital_social"] == 5_000_000
    assert valeurs["reserves"] == 2_100_000
    assert valeurs["capitaux_propres"] == 7_550_000
    assert valeurs["dettes_long_terme"] == 8_000_000
    assert valeurs["passifs_courants"] == 4_045_000
    assert valeurs["total_dettes"] == 12_045_000
    assert valeurs["chiffre_affaires"] == 25_750_000
    assert valeurs["cout_des_ventes"] == 15_500_000
    assert valeurs["resultat_operationnel"] == 1_250_000
    assert valeurs["resultat_net"] == 450_000

    assert ratios["liquidite_generale"] == pytest.approx(7250 / 4_045_000, abs=0.001)
    assert ratios["endettement"] == pytest.approx(
        12_045_000 / 7_550_000, abs=0.01
    )
    assert ratios["autonomie_financiere"] == pytest.approx(
        7_550_000 / 19_595_000, abs=0.001
    )
    assert ratios["marge_nette"] == pytest.approx(450_000 / 25_750_000, abs=0.001)

    # Vérification de la locale.
    assert extra.get("periode") is None or extra.get("periode") == "31/12/2025"


# ---------------------------------------------------------------------------
# IFRS en anglais — montants avec espaces de milliers (format mixte).
# ---------------------------------------------------------------------------
def test_synth_ifrs_en():
    valeurs, ratios, controles, _ = executer_pipeline(charger("synth_ifrs_en.txt"))

    assert valeurs["actifs_non_courants"] == 4200
    assert valeurs["actifs_courants"] == 3800
    assert valeurs["total_actif"] == 8000
    assert valeurs["capitaux_propres"] == 3000
    assert valeurs["dettes_long_terme"] == 2400
    assert valeurs["passifs_courants"] == 2600
    assert valeurs["chiffre_affaires"] == 12000
    assert valeurs["resultat_net"] == 400
    assert valeurs["stocks"] == 1600

    assert ratios["liquidite_generale"] == pytest.approx(3800 / 2600, abs=0.01)
    assert ratios["endettement"] == pytest.approx(5000 / 3000, abs=0.01)
    assert ratios["marge_nette"] == pytest.approx(400 / 12000, abs=0.001)
    assert ratios["rentabilite_capitaux_propres"] == pytest.approx(400 / 3000, abs=0.001)
    assert ratios["autonomie_financiere"] == pytest.approx(3000 / 8000, abs=0.001)

    assert not a_des_alertes(controles)


# ---------------------------------------------------------------------------
# Libellés en MAJUSCULES SANS ACCENTS (variante SCF tunisien formelle).
# ---------------------------------------------------------------------------
def test_synth_uppercase_sans_accents():
    valeurs, ratios, controles, _ = executer_pipeline(
        charger("synth_uppercase_sans_accents.txt")
    )

    assert valeurs["actifs_courants"] == 1900
    assert valeurs["actifs_non_courants"] == 2400
    assert valeurs["total_actif"] == 4300
    assert valeurs["capitaux_propres"] == 2000
    assert valeurs["dettes_long_terme"] == 1100
    assert valeurs["passifs_courants"] == 1200
    assert valeurs["total_dettes"] == 2300
    assert valeurs["chiffre_affaires"] == 7500
    assert valeurs["resultat_net"] == 300

    assert ratios["liquidite_generale"] == pytest.approx(1900 / 1200, abs=0.01)
    assert ratios["endettement"] == pytest.approx(2300 / 2000, abs=0.01)
    assert ratios["autonomie_financiere"] == pytest.approx(2000 / 4300, abs=0.01)
    assert not a_des_alertes(controles)


# ---------------------------------------------------------------------------
# CSV avec colonnes N / N-1 / N-2 : il faut prendre la dernière.
# ---------------------------------------------------------------------------
def test_synth_csv_bilan_derniere_periode():
    valeurs, ratios, _controles, extra = executer_pipeline(charger("synth_csv_bilan.csv"))

    assert extra["periode"] == "31/12/2025"

    # Valeurs 2025 (pas 2024 ni 2023).
    assert valeurs["actifs_non_courants"] == 3800
    assert valeurs["actifs_courants"] == 3000
    assert valeurs["total_actif"] == 6800
    assert valeurs["capitaux_propres"] == 2800
    assert valeurs["dettes_long_terme"] == 1900
    assert valeurs["total_dettes"] == 4000
    assert valeurs["chiffre_affaires"] == 9500
    assert valeurs["resultat_net"] == 400

    assert ratios["liquidite_generale"] == pytest.approx(3000 / 2100, abs=0.01)
    assert ratios["endettement"] == pytest.approx(4000 / 2800, abs=0.01)


# ---------------------------------------------------------------------------
# Excel multi-feuilles (Bilan + Compte de résultat).
# ---------------------------------------------------------------------------
def test_synth_excel_multisheet():
    valeurs, ratios, controles, extra = executer_pipeline(
        charger("synth_excel_multisheet.xlsx")
    )

    assert extra["periode"] == "31/12/2025"
    assert valeurs["actifs_non_courants"] == 4000
    assert valeurs["actifs_courants"] == 3200
    assert valeurs["total_actif"] == 7200
    assert valeurs["capitaux_propres"] == 3500
    assert valeurs["dettes_long_terme"] == 1800
    assert valeurs["passifs_courants"] == 1900
    assert valeurs["total_dettes"] == 3700
    assert valeurs["chiffre_affaires"] == 10500
    assert valeurs["resultat_net"] == 600
    assert valeurs["cout_des_ventes"] == 6200

    assert ratios["liquidite_generale"] == pytest.approx(3200 / 1900, abs=0.01)
    assert ratios["endettement"] == pytest.approx(3700 / 3500, abs=0.01)
    assert ratios["marge_nette"] == pytest.approx(600 / 10500, abs=0.001)
    assert ratios["autonomie_financiere"] == pytest.approx(3500 / 7200, abs=0.001)

    assert not a_des_alertes(controles)


# ---------------------------------------------------------------------------
# Pièges : lignes « Autres ... » et « Total X et Y » placées avant les
# vrais sous-totaux. Les vrais sous-totaux doivent gagner.
# ---------------------------------------------------------------------------
def test_synth_pieges_autres_totaux():
    valeurs, ratios, controles, _ = executer_pipeline(
        charger("synth_pieges_autres_total.txt")
    )

    # Les vrais totaux l'emportent sur les lignes « Autres ».
    assert valeurs["actifs_courants"] == 2900  # Total des actifs courants
    assert valeurs["actifs_non_courants"] == 6400  # Immobilisations nettes
    assert valeurs["total_actif"] == 9300
    assert valeurs["capitaux_propres"] == 3500  # Total des capitaux propres, pas Capital
    assert valeurs["dettes_long_terme"] == 2800
    assert valeurs["passifs_courants"] == 3000
    assert valeurs["total_dettes"] == 5800
    assert valeurs["chiffre_affaires"] == 11500  # Chiffre d'affaires, pas Autres produits
    assert valeurs["resultat_net"] == 500

    assert ratios["liquidite_generale"] == pytest.approx(2900 / 3000, abs=0.01)
    assert ratios["endettement"] == pytest.approx(5800 / 3500, abs=0.01)

    # Les trois contrôles de cohérence passent (bilan équilibré).
    assert not a_des_alertes(controles), [
        (c["nom"], c["detail"]) for c in controles
    ]
