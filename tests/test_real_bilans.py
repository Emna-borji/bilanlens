"""Tests sur des bilans réels publics (bvmt.com.tn).

Ces tests portent sur des sociétés industrielles ou commerciales
tunisiennes et vérifient (a) les ratios cibles connus et (b) que le
pipeline ne crashe pas, mappe les postes-clés et n'engendre pas d'écart
de bilan supérieur à la tolérance.
"""
import pytest

from conftest import load
from _pipeline import run_pipeline
from finsight.consistency import has_warnings
from finsight.sector import detect_out_of_scope_sector


pytestmark = pytest.mark.real


# ---------------------------------------------------------------------------
# SOTUVER 2024 — valeurs attendues fournies par l'utilisateur.
# Source : bvmt.com.tn (états financiers annuels individuels 31/12/2024).
# ---------------------------------------------------------------------------
def test_sotuver_2024_ratios_match_expected():
    values, ratios, checks, extra = run_pipeline(load("real_sotuver_2024.pdf"))

    assert extra["period"] == "31/12/2024"
    # Hors périmètre non déclenché (c'est une industrielle, pas une banque).
    assert detect_out_of_scope_sector(extra["text"]) is None

    assert ratios["current_ratio"] == pytest.approx(1.14, abs=0.01)
    assert ratios["debt_to_equity"] == pytest.approx(1.90, abs=0.02)
    assert ratios["net_margin"] * 100 == pytest.approx(13.79, abs=0.05)
    assert ratios["roe"] * 100 == pytest.approx(11.49, abs=0.05)
    assert ratios["equity_ratio"] * 100 == pytest.approx(34.53, abs=0.05)

    # Les deux contrôles de bilan structurels doivent passer. La
    # décomposition « Capital + Réserves + Résultat ≈ CP » peut échouer
    # sans que cela soit une anomalie : d'autres rubriques (primes
    # d'émission, report à nouveau) composent aussi les capitaux propres.
    structural = [
        c for c in checks
        if c["name"].startswith("Total actif")
        or c["name"].startswith("Actifs courants")
    ]
    for check in structural:
        assert check["status"] != "warning", (
            f"{check['name']} : {check['detail']}"
        )


# ---------------------------------------------------------------------------
# Autres bilans réels — smoke-tests : le pipeline tourne, le secteur est
# dans le périmètre, au moins quelques postes et ratios sortent, et le
# bilan structurel équilibre quand les deux totaux sont disponibles.
#
# Les bilans réels ont des formats PDF variés : certains postes peuvent
# ne pas être extraits sur un bilan donné. On accepte des trous mais on
# refuse les régressions silencieuses sur le total actif publié.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "file_name,required_posts",
    [
        ("real_sfbt_2024.pdf", {"total_assets", "equity", "revenue"}),
        (
            "real_delice_holding_2024.pdf",
            {"total_assets", "equity"},  # holding : CA pas toujours présent
        ),
        (
            "real_ciments_bizerte_2024.pdf",
            {"equity", "long_term_debt", "current_liabilities"},
        ),
        (
            "real_monoprix_2024.pdf",
            # Monoprix : format PDF particulièrement dense ; smoke-test
            # minimal, aucun poste requis strictement.
            set(),
        ),
    ],
)
def test_real_bilan_pipeline_smoke(file_name, required_posts):
    values, ratios, checks, extra = run_pipeline(load(file_name))

    # Pas de faux positif « hors périmètre » sur une industrielle ou
    # commerciale.
    assert detect_out_of_scope_sector(extra["text"]) is None, (
        f"{file_name} : secteur détecté à tort"
    )

    missing = {p for p in required_posts if values.get(p) is None}
    assert not missing, (
        f"{file_name} : postes attendus non détectés : {missing}"
    )

    # Si total actif ET capitaux propres + dettes sont tous disponibles,
    # le bilan structurel doit équilibrer.
    for check in checks:
        if (
            check["name"].startswith("Total actif")
            and check["status"] == "warning"
        ):
            pytest.fail(
                f"{file_name} : écart de bilan — {check['detail']}"
            )
