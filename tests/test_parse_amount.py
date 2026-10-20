"""Tests unitaires sur parse_amount / detect_decimal_separator.

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

from bilanlens.extraction import detect_decimal_separator, parse_amount


# ---------------------------------------------------------------------------
# detect_decimal_separator — reconnaissance de la locale d'un document.
# ---------------------------------------------------------------------------
def test_detect_locale_french_default():
    assert detect_decimal_separator("") == ","
    assert detect_decimal_separator("Rien de pertinent ici") == ","


def test_detect_locale_french_space_plus_decimal():
    text = "Total 1 281 772 854,965"
    assert detect_decimal_separator(text) == ","


def test_detect_locale_english_double_comma():
    text = "Revenue 12,345,678"
    assert detect_decimal_separator(text) == "."


def test_detect_locale_english_comma_plus_dot_decimal():
    text = "Revenue 1,234.56"
    assert detect_decimal_separator(text) == "."


def test_detect_locale_english_wins_over_french_when_both_present():
    """Un document mixte avec plusieurs virgules milliers est anglais."""
    text = "Revenue 12,345,678 and a stray 3,5"
    assert detect_decimal_separator(text) == "."


# ---------------------------------------------------------------------------
# parse_amount — cas français (défaut).
# ---------------------------------------------------------------------------
def test_parse_french_single_comma_three_decimals():
    assert parse_amount("854,965") == pytest.approx(854.965)


def test_parse_french_sfbt_long_amount_with_decimal():
    assert parse_amount("1 281 772 854,965") == pytest.approx(
        1_281_772_854.965
    )


def test_parse_french_single_comma_one_decimal():
    # test1 : « Bénéfice par action (TND) : 3,5 »
    assert parse_amount("3,5") == 3.5


def test_parse_french_single_comma_two_decimals():
    assert parse_amount("1 250,50") == 1250.5


def test_parse_french_space_only_thousands():
    assert parse_amount("1 250") == 1250
    assert parse_amount("1 234 567") == 1_234_567


def test_parse_french_parentheses_are_negative():
    assert parse_amount("(250)") == -250
    assert parse_amount("(1 234,56)") == pytest.approx(-1234.56)


# ---------------------------------------------------------------------------
# parse_amount — cas anglais (decimal_separator='.').
# ---------------------------------------------------------------------------
def test_parse_english_single_comma_three_digits_is_thousands():
    # « 1,250 » dans un bilan anglais = mille deux cent cinquante.
    assert parse_amount("1,250", decimal_separator=".") == 1250


def test_parse_english_single_comma_three_digits_bigger():
    assert parse_amount("12,345", decimal_separator=".") == 12345
    assert parse_amount("123,456", decimal_separator=".") == 123_456


def test_parse_english_single_comma_two_digits_is_decimal():
    # « 1,25 » dans un bilan anglais est une décimale « légère ».
    assert parse_amount("1,25", decimal_separator=".") == pytest.approx(1.25)


def test_parse_english_multiple_commas_are_thousands():
    assert parse_amount("1,234,567", decimal_separator=".") == 1_234_567
    assert parse_amount("12,345,678", decimal_separator=".") == 12_345_678


def test_parse_english_comma_thousands_plus_dot_decimal():
    assert parse_amount("12,345.67", decimal_separator=".") == pytest.approx(
        12_345.67
    )


# ---------------------------------------------------------------------------
# parse_amount — règle du dernier séparateur (locale-indépendante).
# ---------------------------------------------------------------------------
def test_parse_mixed_last_separator_wins_dot():
    # « 1.234,56 » → la virgule finale est décimale.
    assert parse_amount("1.234,56") == pytest.approx(1234.56)


def test_parse_mixed_last_separator_wins_comma():
    # « 1,234.56 » → le point final est décimal.
    assert parse_amount("1,234.56") == pytest.approx(1234.56)


# ---------------------------------------------------------------------------
# parse_amount — valeurs invalides.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value", ["", "nan", "N/A", "-", "—", "–", "n/a", None, "abc", "€"]
)
def test_parse_invalid_returns_none(value):
    assert parse_amount(value) is None
