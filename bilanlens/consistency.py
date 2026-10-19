"""Contrôles de cohérence automatiques sur un bilan.

Les contrôles vérifient trois égalités comptables de base :
  1. Total actif = capitaux propres + total des dettes
     (± intérêts minoritaires si fournis).
  2. Actifs courants + actifs non courants = total actif.
  3. Capital + réserves + résultat net ≈ capitaux propres.

Chaque contrôle est appliqué uniquement si tous les postes nécessaires
sont renseignés. Un écart relatif supérieur à `tolerance` (1 % par défaut)
produit une alerte.
"""


TOLERANCE_DEFAULT = 0.01


def _relative_gap(got, expected):
    """Écart relatif |got - expected| / max(|expected|, |got|, 1)."""
    base = max(abs(expected), abs(got), 1.0)
    return abs(got - expected) / base


def _format_amount(value):
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def _ok(name, detail):
    return {"name": name, "status": "ok", "detail": detail, "gap": 0.0}


def _warn(name, detail, gap):
    return {
        "name": name,
        "status": "warning",
        "detail": detail,
        "gap": gap,
    }


def _skip(name, reason):
    return {
        "name": name,
        "status": "skipped",
        "detail": reason,
        "gap": None,
    }


def check_balance_sheet(values, tolerance=TOLERANCE_DEFAULT):
    """Retourne la liste des contrôles de cohérence sur un bilan.

    Chaque contrôle est un dict :
      {name, status in {ok, warning, skipped}, detail, gap (float ou None)}
    """
    results = []

    total_assets = values.get("total_assets")
    equity = values.get("equity")
    total_debt = values.get("total_debt")
    minority_interests = values.get("minority_interests")

    non_current_assets = values.get("non_current_assets")
    current_assets = values.get("current_assets")

    share_capital = values.get("share_capital")
    reserves = values.get("reserves")
    net_income = values.get("net_income")

    # 1. Total actif = capitaux propres + total des dettes (± minoritaires)
    if (
        total_assets is not None
        and equity is not None
        and total_debt is not None
    ):
        expected = equity + total_debt + (minority_interests or 0)
        gap = _relative_gap(total_assets, expected)
        detail = (
            f"Total actif {_format_amount(total_assets)} "
            f"vs capitaux propres + dettes "
            f"{'' if minority_interests is None else '(+ minoritaires) '}"
            f"= {_format_amount(expected)}"
        )
        if gap <= tolerance:
            results.append(
                _ok("Total actif = capitaux propres + dettes", detail)
            )
        else:
            results.append(
                _warn(
                    "Total actif ≠ capitaux propres + dettes",
                    f"{detail} (écart relatif {gap * 100:.2f} %).",
                    gap,
                )
            )
    else:
        results.append(
            _skip(
                "Total actif = capitaux propres + dettes",
                "Total actif, capitaux propres ou total des dettes manquant.",
            )
        )

    # 2. Actifs courants + non courants = total actif
    if (
        total_assets is not None
        and current_assets is not None
        and non_current_assets is not None
    ):
        expected = current_assets + non_current_assets
        gap = _relative_gap(total_assets, expected)
        detail = (
            f"AC + ANC = {_format_amount(expected)} "
            f"vs total actif {_format_amount(total_assets)}"
        )
        if gap <= tolerance:
            results.append(
                _ok("Actifs courants + non courants = total actif", detail)
            )
        else:
            results.append(
                _warn(
                    "Actifs courants + non courants ≠ total actif",
                    f"{detail} (écart relatif {gap * 100:.2f} %).",
                    gap,
                )
            )
    else:
        results.append(
            _skip(
                "Actifs courants + non courants = total actif",
                "Actifs courants, actifs non courants ou total actif manquant.",
            )
        )

    # 3. Capital + réserves + résultat net ≈ capitaux propres
    if (
        equity is not None
        and share_capital is not None
        and reserves is not None
        and net_income is not None
    ):
        expected = share_capital + reserves + net_income
        gap = _relative_gap(equity, expected)
        detail = (
            f"Capital + réserves + résultat = {_format_amount(expected)} "
            f"vs capitaux propres {_format_amount(equity)}"
        )
        if gap <= tolerance:
            results.append(
                _ok(
                    "Capital + réserves + résultat ≈ capitaux propres",
                    detail,
                )
            )
        else:
            results.append(
                _warn(
                    "Capital + réserves + résultat ≠ capitaux propres",
                    f"{detail} (écart relatif {gap * 100:.2f} %). "
                    "Peut provenir d'autres rubriques des capitaux propres "
                    "(primes, écarts, report à nouveau).",
                    gap,
                )
            )
    else:
        results.append(
            _skip(
                "Capital + réserves + résultat ≈ capitaux propres",
                "Capital, réserves, résultat net ou capitaux propres manquant.",
            )
        )

    return results


def has_warnings(checks) -> bool:
    """True s'il y a au moins une incohérence > tolérance."""
    return any(check["status"] == "warning" for check in checks)
