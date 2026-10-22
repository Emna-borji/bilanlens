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


TOLERANCE_DEFAUT = 0.01


def _ecart_relatif(obtenu, attendu):
    """Écart relatif |obtenu - attendu| / max(|attendu|, |obtenu|, 1)."""
    base = max(abs(attendu), abs(obtenu), 1.0)
    return abs(obtenu - attendu) / base


def _formater_montant(valeur):
    return f"{valeur:,.2f}".replace(",", " ").replace(".", ",")


def _ok(nom, detail):
    return {"nom": nom, "statut": "ok", "detail": detail, "ecart": 0.0}


def _alerte(nom, detail, ecart):
    return {
        "nom": nom,
        "statut": "alerte",
        "detail": detail,
        "ecart": ecart,
    }


def _ignore(nom, raison):
    return {
        "nom": nom,
        "statut": "ignore",
        "detail": raison,
        "ecart": None,
    }


def verifier_bilan(valeurs, tolerance=TOLERANCE_DEFAUT):
    """Retourne la liste des contrôles de cohérence sur un bilan.

    Chaque contrôle est un dict :
      {nom, statut in {ok, alerte, ignore}, detail, ecart (float ou None)}
    """
    resultats = []

    total_actif = valeurs.get("total_actif")
    capitaux_propres = valeurs.get("capitaux_propres")
    total_dettes = valeurs.get("total_dettes")
    interets_minoritaires = valeurs.get("interets_minoritaires")

    actifs_non_courants = valeurs.get("actifs_non_courants")
    actifs_courants = valeurs.get("actifs_courants")

    capital_social = valeurs.get("capital_social")
    reserves = valeurs.get("reserves")
    resultat_net = valeurs.get("resultat_net")

    # 1. Total actif = capitaux propres + total des dettes (± minoritaires)
    if (
        total_actif is not None
        and capitaux_propres is not None
        and total_dettes is not None
    ):
        attendu = capitaux_propres + total_dettes + (interets_minoritaires or 0)
        ecart = _ecart_relatif(total_actif, attendu)
        detail = (
            f"Total actif {_formater_montant(total_actif)} "
            f"vs capitaux propres + dettes "
            f"{'' if interets_minoritaires is None else '(+ minoritaires) '}"
            f"= {_formater_montant(attendu)}"
        )
        if ecart <= tolerance:
            resultats.append(
                _ok("Total actif = capitaux propres + dettes", detail)
            )
        else:
            resultats.append(
                _alerte(
                    "Total actif ≠ capitaux propres + dettes",
                    f"{detail} (écart relatif {ecart * 100:.2f} %).",
                    ecart,
                )
            )
    else:
        resultats.append(
            _ignore(
                "Total actif = capitaux propres + dettes",
                "Total actif, capitaux propres ou total des dettes manquant.",
            )
        )

    # 2. Actifs courants + non courants = total actif
    if (
        total_actif is not None
        and actifs_courants is not None
        and actifs_non_courants is not None
    ):
        attendu = actifs_courants + actifs_non_courants
        ecart = _ecart_relatif(total_actif, attendu)
        detail = (
            f"AC + ANC = {_formater_montant(attendu)} "
            f"vs total actif {_formater_montant(total_actif)}"
        )
        if ecart <= tolerance:
            resultats.append(
                _ok("Actifs courants + non courants = total actif", detail)
            )
        else:
            resultats.append(
                _alerte(
                    "Actifs courants + non courants ≠ total actif",
                    f"{detail} (écart relatif {ecart * 100:.2f} %).",
                    ecart,
                )
            )
    else:
        resultats.append(
            _ignore(
                "Actifs courants + non courants = total actif",
                "Actifs courants, actifs non courants ou total actif manquant.",
            )
        )

    # 3. Capital + réserves + résultat net ≈ capitaux propres
    if (
        capitaux_propres is not None
        and capital_social is not None
        and reserves is not None
        and resultat_net is not None
    ):
        attendu = capital_social + reserves + resultat_net
        ecart = _ecart_relatif(capitaux_propres, attendu)
        detail = (
            f"Capital + réserves + résultat = {_formater_montant(attendu)} "
            f"vs capitaux propres {_formater_montant(capitaux_propres)}"
        )
        if ecart <= tolerance:
            resultats.append(
                _ok(
                    "Capital + réserves + résultat ≈ capitaux propres",
                    detail,
                )
            )
        else:
            resultats.append(
                _alerte(
                    "Capital + réserves + résultat ≠ capitaux propres",
                    f"{detail} (écart relatif {ecart * 100:.2f} %). "
                    "Peut provenir d'autres rubriques des capitaux propres "
                    "(primes, écarts, report à nouveau).",
                    ecart,
                )
            )
    else:
        resultats.append(
            _ignore(
                "Capital + réserves + résultat ≈ capitaux propres",
                "Capital, réserves, résultat net ou capitaux propres manquant.",
            )
        )

    return resultats


def a_des_alertes(controles) -> bool:
    """True s'il y a au moins une incohérence > tolérance."""
    return any(controle["statut"] == "alerte" for controle in controles)
