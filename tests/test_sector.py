"""Détecteur hors périmètre (banques, assurances) — tests unitaires."""
from finsight.sector import detect_out_of_scope_sector


def test_industrial_text_is_in_scope():
    text = """
    Immobilisations corporelles nettes : 400 000
    Stocks : 150 000
    Créances clients : 120 000
    Chiffre d'affaires : 900 000
    Résultat net : 60 000
    """
    assert detect_out_of_scope_sector(text) is None


def test_bank_balance_sheet_detected():
    text = """
    Créances sur la clientèle                1 200 000
    Créances sur les établissements de crédit   300 000
    Dépôts de la clientèle                   1 400 000
    Produit net bancaire                       150 000
    Marge d'intérêt                             90 000
    """
    result = detect_out_of_scope_sector(text)
    assert result is not None
    assert result["sector"] == "banque"
    assert len(result["matches"]) >= 2


def test_insurance_balance_sheet_detected():
    text = """
    Provisions techniques                       1 800 000
    Primes émises                                 450 000
    Primes acquises                               420 000
    Part des réassureurs dans les provisions       80 000
    """
    result = detect_out_of_scope_sector(text)
    assert result is not None
    assert result["sector"] == "assurance"
    assert len(result["matches"]) >= 2


def test_single_match_does_not_trigger():
    """Une entreprise industrielle peut citer un terme sans être du secteur."""
    text = """
    Le groupe utilise un contrat de réassurance sur un entrepôt.
    Immobilisations corporelles : 500 000
    Stocks : 100 000
    Chiffre d'affaires : 900 000
    """
    # Un seul indicateur (« reassurance ») ne doit pas déclencher.
    assert detect_out_of_scope_sector(text) is None


def test_detection_ignores_accents_and_case():
    text = """
    PRODUIT NET BANCAIRE : 150 000
    MARGE D'INTERET : 90 000
    """
    result = detect_out_of_scope_sector(text)
    assert result is not None
    assert result["sector"] == "banque"


def test_empty_text_returns_none():
    assert detect_out_of_scope_sector("") is None
    assert detect_out_of_scope_sector(None) is None
