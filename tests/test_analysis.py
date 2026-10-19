from finsight.analysis import calculate_ratios, build_diagnostic

def test_example_ratios():
    values = {
        "current_assets": 3000,
        "current_liabilities": 1800,
        "total_debt": 3300,
        "equity": 3700,
        "revenue": 10000,
        "net_income": 1000,
        "total_assets": 7000,
    }
    ratios = {r["key"]: r["value"] for r in calculate_ratios(values)}
    assert round(ratios["current_ratio"], 2) == 1.67
    assert round(ratios["debt_to_equity"], 2) == 0.89
    assert round(ratios["net_margin"] * 100, 2) == 10.00
    assert round(ratios["roe"] * 100, 2) == 27.03
    assert round(ratios["equity_ratio"] * 100, 2) == 52.86

def test_missing_or_zero_denominator():
    values = {"current_assets": 300, "current_liabilities": 0}
    ratios = {r["key"]: r["value"] for r in calculate_ratios(values)}
    assert ratios["current_ratio"] is None
    assert ratios["roe"] is None

def test_diagnostic_flags_negative_income():
    values = {
        "current_assets": 500, "current_liabilities": 1000,
        "total_debt": 3000, "equity": 1000,
        "revenue": 10000, "net_income": -100, "total_assets": 4000,
    }
    ratios = calculate_ratios(values)
    diag = build_diagnostic(values, ratios)
    assert any("inférieure à 1" in x for x in diag["risks"])
    assert any("négatif" in x.lower() for x in diag["risks"])
