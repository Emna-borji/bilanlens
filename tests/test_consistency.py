"""Contrôles de cohérence du bilan — tests unitaires."""
import pytest

from bilanlens.consistency import verifier_bilan, a_des_alertes


def _par_nom(controles):
    return {controle["nom"]: controle for controle in controles}


def test_bilan_equilibre_passe_tous_les_controles():
    valeurs = {
        "total_actif": 1000,
        "capitaux_propres": 400,
        "total_dettes": 600,
        "actifs_courants": 600,
        "actifs_non_courants": 400,
        "capital_social": 200,
        "reserves": 150,
        "resultat_net": 50,
    }
    controles = _par_nom(verifier_bilan(valeurs))
    assert controles["Total actif = capitaux propres + dettes"]["statut"] == "ok"
    assert (
        controles["Actifs courants + non courants = total actif"]["statut"]
        == "ok"
    )
    assert (
        controles["Capital + réserves + résultat ≈ capitaux propres"]["statut"]
        == "ok"
    )
    assert not a_des_alertes(verifier_bilan(valeurs))


def test_ecart_total_actif_au_dessus_tolerance_alerte():
    valeurs = {
        "total_actif": 1000,
        "capitaux_propres": 400,
        "total_dettes": 580,  # 400 + 580 = 980 → écart 2 % > 1 %
    }
    controles = _par_nom(verifier_bilan(valeurs))
    detail = controles.get("Total actif ≠ capitaux propres + dettes")
    assert detail is not None
    assert detail["statut"] == "alerte"
    assert detail["ecart"] > 0.01


def test_ecart_total_actif_dans_tolerance_ok():
    valeurs = {
        "total_actif": 1000,
        "capitaux_propres": 400,
        "total_dettes": 595,  # 400 + 595 = 995 → écart 0,5 % ≤ 1 %
    }
    controles = _par_nom(verifier_bilan(valeurs))
    assert controles["Total actif = capitaux propres + dettes"]["statut"] == "ok"


def test_interets_minoritaires_inclus():
    valeurs = {
        "total_actif": 1050,
        "capitaux_propres": 400,
        "total_dettes": 600,
        "interets_minoritaires": 50,
    }
    controles = _par_nom(verifier_bilan(valeurs))
    assert controles["Total actif = capitaux propres + dettes"]["statut"] == "ok"


def test_decomposition_actifs_courants_incorrecte():
    valeurs = {
        "total_actif": 1000,
        "actifs_courants": 500,
        "actifs_non_courants": 450,  # 950 vs 1000 = 5 %
    }
    controles = _par_nom(verifier_bilan(valeurs))
    detail = controles["Actifs courants + non courants ≠ total actif"]
    assert detail["statut"] == "alerte"


def test_decomposition_capitaux_propres_signale_autres_composants():
    valeurs = {
        "capitaux_propres": 500,
        "capital_social": 200,
        "reserves": 100,
        "resultat_net": 50,  # 350 vs 500 : 30 %
    }
    controles = _par_nom(verifier_bilan(valeurs))
    detail = controles["Capital + réserves + résultat ≠ capitaux propres"]
    assert detail["statut"] == "alerte"
    assert "primes" in detail["detail"].lower() or "report" in detail["detail"].lower()


def test_valeurs_manquantes_ignorent_sans_erreur():
    valeurs = {"total_actif": 1000}
    controles = _par_nom(verifier_bilan(valeurs))
    for nom, controle in controles.items():
        assert controle["statut"] == "ignore"
    assert not a_des_alertes(controles.values())
