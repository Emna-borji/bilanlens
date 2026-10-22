"""Détecteur hors périmètre (banques, assurances) — tests unitaires."""
from bilanlens.sector import detecter_secteur_hors_perimetre


def test_texte_industriel_dans_le_perimetre():
    texte = """
    Immobilisations corporelles nettes : 400 000
    Stocks : 150 000
    Créances clients : 120 000
    Chiffre d'affaires : 900 000
    Résultat net : 60 000
    """
    assert detecter_secteur_hors_perimetre(texte) is None


def test_bilan_bancaire_detecte():
    texte = """
    Créances sur la clientèle                1 200 000
    Créances sur les établissements de crédit   300 000
    Dépôts de la clientèle                   1 400 000
    Produit net bancaire                       150 000
    Marge d'intérêt                             90 000
    """
    resultat = detecter_secteur_hors_perimetre(texte)
    assert resultat is not None
    assert resultat["secteur"] == "banque"
    assert len(resultat["correspondances"]) >= 2


def test_bilan_assurance_detecte():
    texte = """
    Provisions techniques                       1 800 000
    Primes émises                                 450 000
    Primes acquises                               420 000
    Part des réassureurs dans les provisions       80 000
    """
    resultat = detecter_secteur_hors_perimetre(texte)
    assert resultat is not None
    assert resultat["secteur"] == "assurance"
    assert len(resultat["correspondances"]) >= 2


def test_une_seule_correspondance_ne_declenche_pas():
    """Une entreprise industrielle peut citer un terme sans être du secteur."""
    texte = """
    Le groupe utilise un contrat de réassurance sur un entrepôt.
    Immobilisations corporelles : 500 000
    Stocks : 100 000
    Chiffre d'affaires : 900 000
    """
    # Un seul indicateur (« reassurance ») ne doit pas déclencher.
    assert detecter_secteur_hors_perimetre(texte) is None


def test_detection_ignore_accents_et_casse():
    texte = """
    PRODUIT NET BANCAIRE : 150 000
    MARGE D'INTERET : 90 000
    """
    resultat = detecter_secteur_hors_perimetre(texte)
    assert resultat is not None
    assert resultat["secteur"] == "banque"


def test_texte_vide_retourne_none():
    assert detecter_secteur_hors_perimetre("") is None
    assert detecter_secteur_hors_perimetre(None) is None
