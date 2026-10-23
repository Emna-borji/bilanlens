"""Tests unitaires sur parser_montant / detecter_separateur_decimal.

Vérifient que la locale décimale est bien gérée aux cas limites :
- Virgule unique française → décimale (SFBT « 854,965 », test1 « 3,5 »).
- Virgule unique anglaise avec 3 chiffres → séparateur de milliers
  (IFRS « 1,250 », « 12,345 »).
- Virgule unique anglaise avec autre longueur → décimale (« 1,25 »).
- Plusieurs virgules → séparateur de milliers (« 1,234,567 »).
- Mélange virgule + point → le dernier séparateur est la décimale.
- Espace de milliers → sans effet.
"""
import pytest

from bilanlens.extraction import detecter_separateur_decimal, parser_montant


# ---------------------------------------------------------------------------
# detecter_separateur_decimal — reconnaissance de la locale d'un document.
# ---------------------------------------------------------------------------
def test_detection_locale_francais_defaut():
    assert detecter_separateur_decimal("") == ","
    assert detecter_separateur_decimal("Rien de pertinent ici") == ","


def test_detection_locale_francais_espace_plus_decimale():
    texte = "Total 1 281 772 854,965"
    assert detecter_separateur_decimal(texte) == ","


def test_detection_locale_anglais_double_virgule():
    texte = "Revenue 12,345,678"
    assert detecter_separateur_decimal(texte) == "."


def test_detection_locale_anglais_virgule_plus_point_decimal():
    texte = "Revenue 1,234.56"
    assert detecter_separateur_decimal(texte) == "."


def test_detection_locale_anglais_gagne_quand_les_deux_presents():
    """Un document mixte avec plusieurs virgules milliers est anglais."""
    texte = "Revenue 12,345,678 and a stray 3,5"
    assert detecter_separateur_decimal(texte) == "."


# ---------------------------------------------------------------------------
# parser_montant — cas français (défaut).
# ---------------------------------------------------------------------------
def test_parse_francais_virgule_unique_trois_decimales():
    assert parser_montant("854,965") == pytest.approx(854.965)


def test_parse_francais_sfbt_long_montant_avec_decimale():
    assert parser_montant("1 281 772 854,965") == pytest.approx(
        1_281_772_854.965
    )


def test_parse_francais_virgule_unique_une_decimale():
    # test1 : « Bénéfice par action (TND) : 3,5 »
    assert parser_montant("3,5") == 3.5


def test_parse_francais_virgule_unique_deux_decimales():
    assert parser_montant("1 250,50") == 1250.5


def test_parse_francais_espace_seulement_milliers():
    assert parser_montant("1 250") == 1250
    assert parser_montant("1 234 567") == 1_234_567


def test_parse_francais_parentheses_sont_negatives():
    assert parser_montant("(250)") == -250
    assert parser_montant("(1 234,56)") == pytest.approx(-1234.56)


# ---------------------------------------------------------------------------
# parser_montant — cas anglais (separateur_decimal='.').
# ---------------------------------------------------------------------------
def test_parse_anglais_virgule_unique_trois_chiffres_milliers():
    # « 1,250 » dans un bilan anglais = mille deux cent cinquante.
    assert parser_montant("1,250", separateur_decimal=".") == 1250


def test_parse_anglais_virgule_unique_trois_chiffres_plus_grand():
    assert parser_montant("12,345", separateur_decimal=".") == 12345
    assert parser_montant("123,456", separateur_decimal=".") == 123_456


def test_parse_anglais_virgule_unique_deux_chiffres_decimale():
    # « 1,25 » dans un bilan anglais est une décimale « légère ».
    assert parser_montant("1,25", separateur_decimal=".") == pytest.approx(1.25)


def test_parse_anglais_plusieurs_virgules_milliers():
    assert parser_montant("1,234,567", separateur_decimal=".") == 1_234_567
    assert parser_montant("12,345,678", separateur_decimal=".") == 12_345_678


def test_parse_anglais_virgule_milliers_plus_point_decimal():
    assert parser_montant("12,345.67", separateur_decimal=".") == pytest.approx(
        12_345.67
    )


# ---------------------------------------------------------------------------
# parser_montant — règle du dernier séparateur (locale-indépendante).
# ---------------------------------------------------------------------------
def test_parse_mixte_dernier_separateur_gagne_point():
    # « 1.234,56 » → la virgule finale est décimale.
    assert parser_montant("1.234,56") == pytest.approx(1234.56)


def test_parse_mixte_dernier_separateur_gagne_virgule():
    # « 1,234.56 » → le point final est décimal.
    assert parser_montant("1,234.56") == pytest.approx(1234.56)


# ---------------------------------------------------------------------------
# parser_montant — valeurs invalides.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "valeur", ["", "nan", "N/A", "-", "—", "–", "n/a", None, "abc", "€"]
)
def test_parse_invalide_retourne_none(valeur):
    assert parser_montant(valeur) is None
