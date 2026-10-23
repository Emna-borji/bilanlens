"""Tests contre les valeurs de RESULTATS_ATTENDUS.txt (test1 à test3).

Chaque fichier (test1, test2, test3) est testé en deux formats : le .txt
et le .pdf. Les deux formats doivent donner les mêmes postes et ratios.
"""
import pytest

from conftest import charger
from _pipeline import executer_pipeline


def _executer(nom_fichier):
    valeurs, ratios, _controles, _extra = executer_pipeline(charger(nom_fichier))
    return valeurs, ratios


def _assert_test1(valeurs, ratios):
    """Postes et ratios attendus pour test1 (format .txt ou .pdf)."""
    # Les postes-clé doivent provenir des libellés EXACTS, pas des pièges.
    assert valeurs["actifs_courants"] == 3500
    assert valeurs["passifs_courants"] == 2000
    assert valeurs["total_actif"] == 8500
    # IMPORTANT : « Total passif et capitaux propres : 8 500 » placé avant
    # « Capitaux propres : 4 000 » ne doit PAS être mappé à capitaux_propres.
    assert valeurs["capitaux_propres"] == 4000
    assert valeurs["total_dettes"] == 4500
    assert valeurs["chiffre_affaires"] == 12000
    assert valeurs["resultat_net"] == 700
    assert valeurs["cout_des_ventes"] == 6800
    assert valeurs["dettes_fournisseurs"] == 1400
    assert valeurs["achats_ttc"] == 8330
    assert valeurs["stocks"] == 1200
    assert valeurs["creances_clients"] == 1500
    assert valeurs["stock_initial"] == 1000
    assert valeurs["stock_final"] == 1200
    assert valeurs["cours_action"] == 42
    assert valeurs["benefice_par_action"] == pytest.approx(3.5, abs=0.01)
    assert valeurs["dividende_par_action"] == pytest.approx(1.2, abs=0.01)

    assert ratios["liquidite_generale"] == pytest.approx(1.75, abs=0.01)
    assert ratios["liquidite_reduite"] == pytest.approx(1.15, abs=0.01)
    assert ratios["endettement"] == pytest.approx(1.125, abs=0.01)
    assert ratios["autonomie_financiere"] * 100 == pytest.approx(47.06, abs=0.05)
    assert ratios["marge_nette"] * 100 == pytest.approx(5.83, abs=0.05)
    assert ratios["rentabilite_capitaux_propres"] * 100 == pytest.approx(17.50, abs=0.05)
    assert ratios["rentabilite_actifs"] * 100 == pytest.approx(8.24, abs=0.05)
    assert ratios["rotation_stocks"] == pytest.approx(6.18, abs=0.02)
    assert ratios["delai_clients"] == pytest.approx(45.6, abs=0.2)
    assert ratios["delai_fournisseurs"] == pytest.approx(61.3, abs=0.2)
    assert ratios["per"] == pytest.approx(12.0, abs=0.05)
    assert ratios["rendement_dividende"] * 100 == pytest.approx(2.86, abs=0.05)


def _assert_test2(valeurs, ratios):
    """Postes et ratios attendus pour test2 (format .txt ou .pdf)."""
    # Les valeurs doivent provenir de la colonne 2025, pas 2024.
    assert valeurs["actifs_courants"] == 2400
    assert valeurs["stocks"] == 900
    assert valeurs["total_actif"] == 6000
    assert valeurs["passifs_courants"] == 2800
    assert valeurs["dettes_long_terme"] == 1700
    assert valeurs["capitaux_propres"] == 1500
    assert valeurs["chiffre_affaires"] == 8000
    assert valeurs["resultat_net"] == -250  # parenthèses = perte

    assert ratios["liquidite_generale"] == pytest.approx(0.86, abs=0.01)
    assert ratios["liquidite_reduite"] == pytest.approx(0.54, abs=0.01)
    assert ratios["endettement"] == pytest.approx(3.00, abs=0.02)
    assert ratios["autonomie_financiere"] * 100 == pytest.approx(25.0, abs=0.1)
    assert ratios["marge_nette"] * 100 == pytest.approx(-3.13, abs=0.05)
    assert ratios["rentabilite_capitaux_propres"] * 100 == pytest.approx(-16.67, abs=0.1)
    assert ratios["rentabilite_actifs"] * 100 == pytest.approx(-4.17, abs=0.1)


def _assert_test3(valeurs, ratios):
    """Postes et ratios attendus pour test3 (format .txt ou .pdf)."""
    # Les composants élémentaires doivent être lus.
    assert valeurs["stocks"] == 150000
    assert valeurs["creances_clients"] == 120000
    assert valeurs["tresorerie"] == 80000
    assert valeurs["capital_social"] == 250000
    assert valeurs["reserves"] == 90000
    assert valeurs["resultat_net"] == 60000
    assert valeurs["dettes_long_terme"] == 200000
    assert valeurs["dettes_fournisseurs"] == 110000
    assert valeurs["dettes_fiscales_sociales"] == 40000
    assert valeurs["chiffre_affaires"] == 900000
    assert valeurs["actifs_non_courants"] == 400000

    # Les sous-totaux doivent être reconstitués.
    assert valeurs["actifs_courants"] == 350000
    assert valeurs["passifs_courants"] == 150000
    assert valeurs["capitaux_propres"] == 400000
    assert valeurs["total_actif"] == 750000

    assert ratios["liquidite_generale"] == pytest.approx(2.33, abs=0.01)
    assert ratios["liquidite_reduite"] == pytest.approx(1.33, abs=0.01)
    assert ratios["endettement"] == pytest.approx(0.88, abs=0.02)
    assert ratios["autonomie_financiere"] * 100 == pytest.approx(53.33, abs=0.05)
    assert ratios["marge_nette"] * 100 == pytest.approx(6.67, abs=0.05)
    assert ratios["rentabilite_capitaux_propres"] * 100 == pytest.approx(15.0, abs=0.1)
    assert ratios["rentabilite_actifs"] * 100 == pytest.approx(8.0, abs=0.1)


# ---------------------------------------------------------------------------
# TEST 1 : .txt et .pdf doivent donner les mêmes valeurs et ratios.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "nom_fichier",
    ["test1_complet_ordre_piege.txt", "test1_complet_ordre_piege.pdf"],
)
def test_test1_valeurs_et_ratios(nom_fichier):
    valeurs, ratios = _executer(nom_fichier)
    _assert_test1(valeurs, ratios)


@pytest.mark.parametrize(
    "nom_fichier",
    ["test2_perte_colonnes_notes.txt", "test2_perte_colonnes_notes.pdf"],
)
def test_test2_valeurs_et_ratios(nom_fichier):
    valeurs, ratios = _executer(nom_fichier)
    _assert_test2(valeurs, ratios)


@pytest.mark.parametrize(
    "nom_fichier",
    ["test3_sans_totaux.txt", "test3_sans_totaux.pdf"],
)
def test_test3_valeurs_et_ratios(nom_fichier):
    valeurs, ratios = _executer(nom_fichier)
    _assert_test3(valeurs, ratios)
