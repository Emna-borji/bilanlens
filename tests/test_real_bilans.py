"""Tests sur des bilans réels publics (bvmt.com.tn).

Sociétés industrielles / commerciales tunisiennes 2024.
Chaque test vérifie les valeurs comptables lues directement dans le
PDF ainsi que les contrôles de cohérence (bilan équilibré).
"""
import pytest

from conftest import charger
from _pipeline import executer_pipeline
from bilanlens.consistency import a_des_alertes
from bilanlens.sector import detecter_secteur_hors_perimetre


pytestmark = pytest.mark.real


def _assert_equilibre_structurel_ok(controles, nom_fichier):
    """Les deux contrôles de bilan structurels doivent passer.

    La décomposition « Capital + Réserves + Résultat ≈ CP » peut
    légitimement échouer (primes, report à nouveau...) et n'est pas
    testée ici.
    """
    for controle in controles:
        nom = controle["nom"]
        if (
            nom.startswith("Total actif")
            or nom.startswith("Actifs courants")
        ) and controle["statut"] == "alerte":
            pytest.fail(f"{nom_fichier} : {controle['detail']}")


# ---------------------------------------------------------------------------
# SOTUVER 2024 (états financiers annuels individuels).
# Valeurs cibles fournies par l'utilisateur.
# ---------------------------------------------------------------------------
def test_sotuver_2024_ratios_correspondent():
    valeurs, ratios, controles, extra = executer_pipeline(charger("real_sotuver_2024.pdf"))

    assert extra["periode"] == "31/12/2024"
    assert detecter_secteur_hors_perimetre(extra["texte"]) is None

    assert ratios["liquidite_generale"] == pytest.approx(1.14, abs=0.01)
    assert ratios["endettement"] == pytest.approx(1.90, abs=0.02)
    assert ratios["marge_nette"] * 100 == pytest.approx(13.79, abs=0.05)
    assert ratios["rentabilite_capitaux_propres"] * 100 == pytest.approx(11.49, abs=0.05)
    assert ratios["autonomie_financiere"] * 100 == pytest.approx(34.53, abs=0.05)

    _assert_equilibre_structurel_ok(controles, "real_sotuver_2024.pdf")


# ---------------------------------------------------------------------------
# Monoprix 2024 — bilan consolidé.
# Source : bvmt.com.tn, états financiers consolidés 31/12/2024.
# Valeurs cibles fournies par l'utilisateur (en dinars).
# Vérification : CP(49 423 396) + Minoritaires(30 541 866) +
# Total passifs(299 295 661) = Total actif(379 260 923).
# ---------------------------------------------------------------------------
def test_monoprix_consolide_2024_valeurs_exactes():
    valeurs, ratios, controles, extra = executer_pipeline(
        charger("real_monoprix_consolide_2024.pdf")
    )

    assert extra["periode"] == "31/12/2024"
    assert detecter_secteur_hors_perimetre(extra["texte"]) is None

    assert valeurs["actifs_courants"] == 195_591_986
    assert valeurs["passifs_courants"] == 261_958_403
    assert valeurs["total_actif"] == 379_260_923
    assert valeurs["capitaux_propres"] == 49_423_396
    assert valeurs["total_dettes"] == 299_295_661
    assert valeurs["dettes_long_terme"] == 37_337_258
    assert valeurs["chiffre_affaires"] == 753_997_490
    assert valeurs["resultat_net"] == 6_872_913
    assert valeurs["stocks"] == 83_323_402  # Stocks nets (rang 1)
    assert valeurs["interets_minoritaires"] == 30_541_866

    # Vérification arithmétique explicite.
    assert (
        valeurs["capitaux_propres"]
        + valeurs["interets_minoritaires"]
        + valeurs["total_dettes"]
        == valeurs["total_actif"]
    )

    _assert_equilibre_structurel_ok(controles, "real_monoprix_consolide_2024.pdf")


# ---------------------------------------------------------------------------
# SFBT 2024 — bilan individuel.
# Valeurs lues directement dans le PDF, en dinars (3 décimales).
# ---------------------------------------------------------------------------
def test_sfbt_2024_valeurs_exactes():
    valeurs, ratios, controles, extra = executer_pipeline(charger("real_sfbt_2024.pdf"))

    assert extra["periode"] == "31/12/2024"
    assert detecter_secteur_hors_perimetre(extra["texte"]) is None

    assert valeurs["total_actif"] == pytest.approx(1_281_772_854.965, abs=1)
    assert valeurs["capitaux_propres"] == pytest.approx(954_001_282.196, abs=1)
    assert valeurs["actifs_courants"] == pytest.approx(725_268_211.109, abs=1)
    assert valeurs["actifs_non_courants"] == pytest.approx(556_504_643.856, abs=1)
    assert valeurs["passifs_courants"] == pytest.approx(211_358_188.371, abs=1)
    assert valeurs["dettes_long_terme"] == pytest.approx(116_413_384.398, abs=1)
    assert valeurs["total_dettes"] == pytest.approx(327_771_572.769, abs=1)
    assert valeurs["chiffre_affaires"] == pytest.approx(836_585_626.332, abs=1)
    assert valeurs["resultat_net"] == pytest.approx(252_152_023.507, abs=1)
    assert valeurs["resultat_operationnel"] == pytest.approx(202_748_424.667, abs=1)

    _assert_equilibre_structurel_ok(controles, "real_sfbt_2024.pdf")


# ---------------------------------------------------------------------------
# Ciments de Bizerte 2024 — société en difficulté, résultat négatif.
# Valeurs lues directement dans le PDF.
# ---------------------------------------------------------------------------
def test_ciments_bizerte_2024_valeurs_exactes():
    valeurs, ratios, controles, extra = executer_pipeline(
        charger("real_ciments_bizerte_2024.pdf")
    )

    assert extra["periode"] == "31/12/2024"
    assert detecter_secteur_hors_perimetre(extra["texte"]) is None

    assert valeurs["total_actif"] == 388_668_436
    assert valeurs["capitaux_propres"] == 143_302_286
    assert valeurs["dettes_long_terme"] == 67_959_717
    assert valeurs["passifs_courants"] == 177_406_433
    assert valeurs["total_dettes"] == 245_366_150
    assert valeurs["resultat_net"] == -44_790_355
    assert valeurs["capital_social"] == 44_047_290
    assert valeurs["reserves"] == 100_809_614
    assert valeurs["chiffre_affaires"] == 27_838_606

    # Contrôle arithmétique : CP + Dettes = Total actif
    assert valeurs["capitaux_propres"] + valeurs["total_dettes"] == valeurs["total_actif"]

    _assert_equilibre_structurel_ok(controles, "real_ciments_bizerte_2024.pdf")


# ---------------------------------------------------------------------------
# Délice Holding 2024 — holding : certains ratios ne sont pas
# calculables (pas de chiffre d'affaires classique). Smoke-test.
# ---------------------------------------------------------------------------
def test_delice_holding_2024_pipeline_fonctionne():
    valeurs, _ratios, controles, extra = executer_pipeline(
        charger("real_delice_holding_2024.pdf")
    )

    assert extra["periode"] == "31/12/2024"
    assert detecter_secteur_hors_perimetre(extra["texte"]) is None

    # Les postes essentiels d'un bilan de holding sont lus.
    assert valeurs.get("total_actif") is not None
    assert valeurs.get("capitaux_propres") is not None

    _assert_equilibre_structurel_ok(controles, "real_delice_holding_2024.pdf")


# ---------------------------------------------------------------------------
# Monoprix 2024 bilan individuel (ancien) — smoke-test additionnel.
# ---------------------------------------------------------------------------
def test_monoprix_individuel_2024_pipeline_fonctionne():
    valeurs, _ratios, controles, extra = executer_pipeline(
        charger("real_monoprix_2024.pdf")
    )

    assert extra["periode"] == "31/12/2024"
    assert detecter_secteur_hors_perimetre(extra["texte"]) is None

    _assert_equilibre_structurel_ok(controles, "real_monoprix_2024.pdf")
