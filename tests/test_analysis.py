from bilanlens.analysis import calculer_ratios, construire_diagnostic


def test_exemple_ratios():
    valeurs = {
        "actifs_courants": 3000,
        "passifs_courants": 1800,
        "total_dettes": 3300,
        "capitaux_propres": 3700,
        "chiffre_affaires": 10000,
        "resultat_net": 1000,
        "total_actif": 7000,
    }
    ratios = {r["cle"]: r["valeur"] for r in calculer_ratios(valeurs)}
    assert round(ratios["liquidite_generale"], 2) == 1.67
    assert round(ratios["endettement"], 2) == 0.89
    assert round(ratios["marge_nette"] * 100, 2) == 10.00
    assert round(ratios["rentabilite_capitaux_propres"] * 100, 2) == 27.03
    assert round(ratios["autonomie_financiere"] * 100, 2) == 52.86


def test_denominateur_manquant_ou_nul():
    valeurs = {"actifs_courants": 300, "passifs_courants": 0}
    ratios = {r["cle"]: r["valeur"] for r in calculer_ratios(valeurs)}
    assert ratios["liquidite_generale"] is None
    assert ratios["rentabilite_capitaux_propres"] is None


def test_diagnostic_signale_resultat_negatif():
    valeurs = {
        "actifs_courants": 500, "passifs_courants": 1000,
        "total_dettes": 3000, "capitaux_propres": 1000,
        "chiffre_affaires": 10000, "resultat_net": -100, "total_actif": 4000,
    }
    ratios = calculer_ratios(valeurs)
    diag = construire_diagnostic(valeurs, ratios)
    assert any("inférieure à 1" in x for x in diag["risques"])
    assert any("négatif" in x.lower() for x in diag["risques"])
