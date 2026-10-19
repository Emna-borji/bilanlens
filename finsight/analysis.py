def safe_ratio(numerator, denominator):
    """Calcule un ratio sans division par zéro ni donnée manquante."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def fr_number(value, decimals=2):
    """Formate un nombre avec une virgule décimale."""
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def complete_financial_values(values):
    """Calcule les sous-totaux possibles sans assimiler une absence à zéro."""
    completed = values.copy()

    def sum_if_all_present(*keys):
        amounts = [completed.get(key) for key in keys]
        if all(amount is not None for amount in amounts):
            return sum(amounts)
        return None

    if completed.get("current_assets") is None:
        calculated = sum_if_all_present("inventory", "receivables", "cash")
        if calculated is not None:
            completed["current_assets"] = calculated

    if completed.get("current_liabilities") is None:
        calculated = sum_if_all_present(
            "supplier_payables", "tax_social_payables"
        )
        if calculated is not None:
            completed["current_liabilities"] = calculated

    if completed.get("equity") is None:
        calculated = sum_if_all_present(
            "share_capital", "reserves", "net_income"
        )
        if calculated is not None:
            completed["equity"] = calculated

    if completed.get("total_assets") is None:
        calculated = sum_if_all_present(
            "current_assets", "non_current_assets"
        )
        if calculated is not None:
            completed["total_assets"] = calculated

    if completed.get("total_debt") is None:
        calculated = sum_if_all_present(
            "current_liabilities", "long_term_debt"
        )
        if calculated is not None:
            completed["total_debt"] = calculated

    beginning = completed.get("beginning_inventory")
    ending = completed.get("ending_inventory")

    if beginning is not None and ending is not None:
        completed["average_inventory"] = (beginning + ending) / 2
    else:
        completed["average_inventory"] = None

    return completed


def calculate_ratios(values):
    """Calcule les 12 ratios répartis en cinq familles."""
    current_assets = values.get("current_assets")
    current_liabilities = values.get("current_liabilities")
    total_debt = values.get("total_debt")
    equity = values.get("equity")
    revenue = values.get("revenue")
    net_income = values.get("net_income")
    total_assets = values.get("total_assets")
    inventory = values.get("inventory")
    receivables = values.get("receivables")
    average_inventory = values.get("average_inventory")
    cost_of_goods_sold = values.get("cost_of_goods_sold")
    purchases_incl_vat = values.get("purchases_incl_vat")
    supplier_payables = values.get("supplier_payables")
    share_price = values.get("share_price")
    earnings_per_share = values.get("earnings_per_share")
    dividend_per_share = values.get("dividend_per_share")

    quick_numerator = (
        current_assets - inventory
        if current_assets is not None and inventory is not None
        else None
    )

    return [
        {
            "key": "current_ratio",
            "name": "Liquidité générale",
            "value": safe_ratio(current_assets, current_liabilities),
            "formula": "Actifs courants / Passifs courants",
            "format": "multiple",
            "note": "Mesure la couverture des dettes à court terme par les actifs courants.",
        },
        {
            "key": "quick_ratio",
            "name": "Liquidité réduite",
            "value": safe_ratio(quick_numerator, current_liabilities),
            "formula": "(Actifs courants - Stocks) / Passifs courants",
            "format": "multiple",
            "note": "Évalue la couverture des passifs courants sans compter sur la vente des stocks.",
        },
        {
            "key": "debt_to_equity",
            "name": "Endettement (dettes / capitaux propres)",
            "value": safe_ratio(total_debt, equity),
            "formula": "Total des dettes / Capitaux propres",
            "format": "multiple",
            "note": "Compare les dettes aux capitaux propres. Vérifier la définition du total des dettes utilisée.",
        },
        {
            "key": "equity_ratio",
            "name": "Autonomie financière",
            "value": safe_ratio(equity, total_assets),
            "formula": "Capitaux propres / Total actif × 100",
            "format": "percent",
            "note": "Mesure la part des actifs financée par les capitaux propres.",
        },
        {
            "key": "net_margin",
            "name": "Marge nette",
            "value": safe_ratio(net_income, revenue),
            "formula": "Résultat net / Chiffre d'affaires × 100",
            "format": "percent",
            "note": "Indique la part du chiffre d'affaires conservée en résultat net.",
        },
        {
            "key": "roe",
            "name": "Rentabilité des capitaux propres (ROE)",
            "value": safe_ratio(net_income, equity),
            "formula": "Résultat net / Capitaux propres × 100",
            "format": "percent",
            "note": "Mesure la rentabilité comptable des capitaux propres.",
        },
        {
            "key": "roa",
            "name": "Rentabilité des actifs (ROA)",
            "value": safe_ratio(net_income, total_assets),
            "formula": "Résultat net / Total actif × 100",
            "format": "percent",
            "note": "Cette version utilise le résultat net. D'autres méthodes utilisent le résultat opérationnel.",
        },
        {
            "key": "inventory_turnover",
            "name": "Rotation des stocks",
            "value": safe_ratio(cost_of_goods_sold, average_inventory),
            "formula": "Coût des ventes / Stock moyen",
            "format": "multiple",
            "note": "Le stock moyen utilise le stock initial et final. Le délai estimé repose sur 365 jours.",
        },
        {
            "key": "receivables_days",
            "name": "Délai moyen de recouvrement clients",
            "value": (
                safe_ratio(receivables, revenue) * 365
                if receivables is not None and revenue not in (None, 0)
                else None
            ),
            "formula": "Créances clients / Chiffre d'affaires × 365",
            "format": "days",
            "note": "Approximation : le chiffre d'affaires peut inclure des ventes qui ne sont pas à crédit.",
        },
        {
            "key": "supplier_days",
            "name": "Délai de paiement fournisseurs estimé",
            "value": (
                safe_ratio(supplier_payables, purchases_incl_vat) * 365
                if supplier_payables is not None
                and purchases_incl_vat not in (None, 0)
                else None
            ),
            "formula": "Dettes fournisseurs / Achats TTC × 365",
            "format": "days",
            "note": "Estimation utilisant le solde fournisseurs de fin d'exercice. Une dette moyenne serait plus précise.",
        },
        {
            "key": "per",
            "name": "PER (cours / bénéfice par action)",
            "value": safe_ratio(share_price, earnings_per_share),
            "formula": "Cours de l'action / Bénéfice par action",
            "format": "multiple",
            "note": "Indique combien de fois le bénéfice par action est valorisé dans le cours. L'interprétation dépend du secteur et des perspectives.",
        },
        {
            "key": "dividend_yield",
            "name": "Rendement du dividende",
            "value": safe_ratio(dividend_per_share, share_price),
            "formula": "Dividende par action / Cours de l'action × 100",
            "format": "percent",
            "note": "Mesure le rendement du dividende par rapport au cours, hors variation du cours et fiscalité.",
        },
    ]


def format_ratio(ratio):
    """Formate les ratios en français."""
    value = ratio["value"]

    if value is None:
        return "Non calculable : donnée manquante ou dénominateur nul"

    if ratio["format"] == "percent":
        return f"{fr_number(value * 100, 2)} %"

    if ratio["format"] == "days":
        return f"{fr_number(value, 1)} jours"

    return fr_number(value, 2)


def interpret_ratio(key, value, all_ratios=None):
    """Retourne une interprétation indicative, cohérente avec les autres ratios."""
    if value is None:
        return "Données insuffisantes pour interpréter ce ratio."

    ratio_values = {
        item["key"]: item["value"]
        for item in (all_ratios or [])
    }

    if key == "current_ratio":
        if value < 1:
            return f"{fr_number(value)} : liquidité insuffisante, les actifs courants ne couvrent pas les passifs courants."
        if value <= 1.5:
            return f"{fr_number(value)} : couverture à court terme présente, mais relativement limitée."
        if value <= 2.5:
            return f"{fr_number(value)} : bonne liquidité, les dettes à court terme sont couvertes."
        return f"{fr_number(value)} : liquidité élevée ; vérifier que les stocks et les créances ne sont pas excessifs."

    if key == "quick_ratio":
        if value < 1:
            return f"{fr_number(value)} : liquidité réduite insuffisante. Hors stocks, les actifs courants ne couvrent pas les passifs courants."
        return f"{fr_number(value)} : bonne couverture à court terme sans dépendre de la vente des stocks."

    if key == "debt_to_equity":
        if value < 0:
            return "Capitaux propres négatifs : le ratio classique est difficile à interpréter et la situation doit être examinée."
        if value < 0.5:
            return f"{fr_number(value)} : endettement relativement faible par rapport aux capitaux propres."
        if value <= 1:
            return f"{fr_number(value)} : les dettes ne dépassent pas les capitaux propres."
        return f"{fr_number(value)} : les dettes dépassent les capitaux propres, signalant une dépendance plus forte à l'endettement."

    if key == "equity_ratio":
        if value < 0:
            return "Capitaux propres négatifs : signal de fragilité financière à examiner."
        if value < 0.2:
            return f"{fr_number(value * 100, 2)} % : autonomie financière faible."
        if value < 0.5:
            return f"{fr_number(value * 100, 2)} % : les capitaux propres financent moins de la moitié des actifs."
        return f"{fr_number(value * 100, 2)} % : bonne autonomie financière selon ce repère indicatif."

    if key == "net_margin":
        if value < 0:
            return f"{fr_number(value * 100, 2)} % : marge nette négative, l'entreprise enregistre une perte nette."
        if value == 0:
            return "Marge nette nulle : l'entreprise ne dégage pas de bénéfice net sur la période."
        if value < 0.05:
            return f"{fr_number(value * 100, 2)} % : marge nette faible ; comparer au secteur."
        if value < 0.15:
            return f"{fr_number(value * 100, 2)} % : marge nette positive ; comparer aux entreprises du même secteur."
        return f"{fr_number(value * 100, 2)} % : marge nette élevée selon ce repère général ; vérifier qu'elle est durable."

    if key == "roe":
        if value < 0:
            return f"{fr_number(value * 100, 2)} % : rentabilité des capitaux propres négative."
        if value < 0.08:
            return f"{fr_number(value * 100, 2)} % : rentabilité des capitaux propres relativement faible."
        if value <= 0.20:
            return f"{fr_number(value * 100, 2)} % : bonne rentabilité des capitaux propres selon ce repère indicatif."
        return f"{fr_number(value * 100, 2)} % : rentabilité élevée ; examiner aussi l'endettement et le niveau des capitaux propres."

    if key == "roa":
        if value < 0:
            return f"{fr_number(value * 100, 2)} % : rentabilité nette des actifs négative."
        if value < 0.05:
            return f"{fr_number(value * 100, 2)} % : rentabilité nette des actifs relativement faible."
        return f"{fr_number(value * 100, 2)} % : les actifs génèrent un résultat net positif ; comparer au secteur."

    if key == "inventory_turnover":
        if value <= 0:
            return "Rotation nulle ou négative : vérifiez le coût des ventes et le stock moyen."
        days = 365 / value
        category = "relativement lente" if value < 4 else "relativement rapide"
        return f"{fr_number(value)} fois, soit environ {fr_number(days, 1)} jours de stock : rotation {category} selon ce repère général."

    if key == "receivables_days":
        if value < 0:
            return "Délai négatif inhabituel : vérifiez les créances clients et le chiffre d'affaires."
        if value < 60:
            return f"{fr_number(value, 1)} jours : délai inférieur à 60 jours selon ce repère indicatif."
        return f"{fr_number(value, 1)} jours : délai relativement long, à comparer aux conditions de paiement accordées aux clients."

    if key == "supplier_days":
        if value < 0:
            return "Valeur négative inhabituelle : vérifiez les dettes fournisseurs et les achats TTC."

        customer_days = ratio_values.get("receivables_days")

        if customer_days is not None and value > customer_days:
            return (
                f"{fr_number(value, 1)} jours : l'entreprise paie ses fournisseurs "
                f"plus tard qu'elle n'encaisse ses clients ({fr_number(customer_days, 1)} jours), "
                "ce qui peut soulager sa trésorerie. Vérifiez toutefois les délais "
                "légaux et contractuels applicables."
            )

        if customer_days is not None and value < customer_days:
            return (
                f"{fr_number(value, 1)} jours : l'entreprise paie ses fournisseurs "
                f"avant d'encaisser ses clients ({fr_number(customer_days, 1)} jours), "
                "ce qui peut exercer une pression sur sa trésorerie."
            )

        if value > 60:
            return (
                f"{fr_number(value, 1)} jours : délai supérieur à 60 jours. "
                "Vérifiez les conditions de paiement et les délais légaux ou contractuels applicables."
            )

        return (
            f"{fr_number(value, 1)} jours : délai estimé à partir du solde fournisseurs "
            "de clôture ; comparez-le aux conditions contractuelles."
        )

    if key == "per":
        if value <= 0:
            return "PER nul ou négatif : interprétation classique peu pertinente, notamment si le bénéfice par action est nul ou négatif."
        category = "faible" if value < 10 else "modéré" if value <= 20 else "élevé"
        return f"{fr_number(value)} : PER {category} selon ce repère indicatif. Les seuils dépendent du secteur, du marché et des perspectives de croissance."

    if key == "dividend_yield":
        if value < 0:
            return "Rendement négatif inhabituel : vérifiez le dividende et le cours de l'action."
        if value == 0:
            return "Rendement nul : aucun dividende positif rapporté au cours de l'action sur la base des données fournies."
        category = "faible" if value < 0.02 else "correct" if value <= 0.05 else "élevé"
        return f"{fr_number(value * 100, 2)} % : rendement {category} selon ce repère indicatif. Les seuils dépendent du secteur et du marché ; ce rendement exclut la variation du cours et la fiscalité."

    return "Aucune règle d'interprétation disponible."


def build_diagnostic(values, ratios):
    """Construit un diagnostic indicatif et une conclusion globale dynamique."""
    strengths, risks, caveats = [], [], []
    by_key = {ratio["key"]: ratio["value"] for ratio in ratios}

    liq = by_key.get("current_ratio")
    quick = by_key.get("quick_ratio")
    debt = by_key.get("debt_to_equity")
    margin = by_key.get("net_margin")
    roe = by_key.get("roe")
    autonomy = by_key.get("equity_ratio")
    roa = by_key.get("roa")
    customer_days = by_key.get("receivables_days")
    supplier_days = by_key.get("supplier_days")
    inventory_turnover = by_key.get("inventory_turnover")
    per = by_key.get("per")
    dividend_yield = by_key.get("dividend_yield")

    # Liquidité
    if liq is not None:
        if liq >= 1:
            strengths.append(f"Bonne couverture générale à court terme : liquidité de {fr_number(liq)}.")
        else:
            risks.append(f"Liquidité générale de {fr_number(liq)} : les actifs courants ne couvrent pas les passifs courants.")
    else:
        caveats.append("Liquidité générale non calculée : vérifier les actifs et passifs courants.")

    if quick is not None and quick < 1:
        risks.append(f"Liquidité réduite de {fr_number(quick)} : hors stocks, la couverture des passifs courants est insuffisante.")

    # Endettement
    if values.get("equity") is not None and values["equity"] <= 0:
        risks.append("Capitaux propres nuls ou négatifs : le ratio dettes/capitaux propres est difficile à interpréter.")
    elif debt is not None:
        if debt > 1:
            risks.append(f"Les dettes dépassent les capitaux propres : ratio de {fr_number(debt)}.")
        elif debt >= 0:
            strengths.append(f"Les dettes ne dépassent pas les capitaux propres : ratio de {fr_number(debt)}.")
    else:
        caveats.append("Endettement non calculé : vérifier le total des dettes et les capitaux propres.")

    # Rentabilité
    if margin is not None:
        if margin > 0:
            strengths.append(f"Marge nette positive : {fr_number(margin * 100, 2)} %.")
        elif margin < 0:
            risks.append("Le résultat net est négatif : l'entreprise enregistre une perte nette.")
        else:
            risks.append("Le résultat net est nul : l'entreprise ne dégage pas de bénéfice net.")

    if roe is not None and roe >= 0.15:
        strengths.append(f"Rentabilité des capitaux propres élevée : ROE de {fr_number(roe * 100, 2)} %.")
    elif roe is not None and roe < 0:
        risks.append("Le ROE est négatif : examiner le résultat net et la structure des capitaux propres.")

    if autonomy is not None:
        if autonomy < 0:
            risks.append("Les capitaux propres sont négatifs par rapport au total actif.")
        elif autonomy < 0.20:
            risks.append(f"Autonomie financière faible : {fr_number(autonomy * 100, 2)} %.")
        elif autonomy < 0.50:
            risks.append(f"Autonomie financière inférieure à 50 % : {fr_number(autonomy * 100, 2)} %. Les capitaux propres financent moins de la moitié des actifs.")

    if roa is not None and roe is not None and roa > 0 and roe >= 2 * roa:
        caveats.append("Le ROE atteint au moins deux fois le ROA. Examiner l'effet de levier et le niveau des capitaux propres.")

    # Délais clients et fournisseurs
    if customer_days is not None:
        caveats.append(f"Délai de recouvrement clients estimé à {fr_number(customer_days, 1)} jours. Le calcul utilise le chiffre d'affaires total comme approximation.")

    if supplier_days is not None:
        caveats.append(f"Délai fournisseurs estimé à {fr_number(supplier_days, 1)} jours à partir du solde de clôture, et non d'une dette moyenne.")

    if customer_days is not None and supplier_days is not None:
        if supplier_days > customer_days:
            strengths.append(
                f"Décalage potentiellement favorable à la trésorerie : les clients "
                f"sont encaissés en {fr_number(customer_days, 1)} jours, contre "
                f"{fr_number(supplier_days, 1)} jours pour payer les fournisseurs. "
                "Vérifier les délais contractuels et légaux."
            )
        elif supplier_days < customer_days:
            risks.append(
                f"Décalage potentiellement défavorable à la trésorerie : les fournisseurs "
                f"sont payés en {fr_number(supplier_days, 1)} jours, avant l'encaissement "
                f"des clients estimé à {fr_number(customer_days, 1)} jours."
            )

    # Stocks
    if inventory_turnover is not None:
        if inventory_turnover > 0:
            inventory_days = 365 / inventory_turnover
            caveats.append(f"Rotation des stocks : {fr_number(inventory_turnover)} fois, soit environ {fr_number(inventory_days, 1)} jours de stock sur la base de 365 jours et du stock moyen initial-final.")
        else:
            caveats.append("Rotation des stocks nulle ou négative : vérifiez le coût des ventes et le stock moyen.")

    # Marché
    if per is not None:
        caveats.append(f"PER de {fr_number(per)} : interprétation à comparer au secteur et aux perspectives de croissance.")

    if dividend_yield is not None:
        caveats.append(f"Rendement du dividende : {fr_number(dividend_yield * 100, 2)} %, hors variation du cours et fiscalité.")

    if not strengths:
        strengths.append("Aucun point fort ne peut être établi avec certitude à partir des données disponibles.")

    if not risks:
        risks.append("Aucun signal d'alerte détecté par les règles simples ; cela ne garantit pas l'absence de risque.")

    caveats.append(
        "Diagnostic pédagogique indicatif : les seuils varient selon le secteur. "
        "Vérifier les données, les unités, les formules du cours et la comparabilité des exercices."
    )

    # Conclusion globale dynamique
    negative_equity = values.get("equity") is not None and values["equity"] <= 0
    negative_profit = values.get("net_income") is not None and values["net_income"] < 0

    fragile = (
        negative_equity
        or negative_profit
        or (liq is not None and liq < 1)
        or (debt is not None and debt > 2)
        or (autonomy is not None and autonomy < 0.20)
    )

    healthy = (
        values.get("net_income") is not None
        and values["net_income"] > 0
        and liq is not None and liq >= 1
        and quick is not None and quick >= 1
        and autonomy is not None and autonomy >= 0.50
        and debt is not None and 0 <= debt <= 1
        and not negative_equity
    )

    if fragile:
        conclusion = (
            "Conclusion : situation financière fragile selon les indicateurs "
            "disponibles. Des signaux d'alerte touchent la rentabilité, la liquidité, "
            "les capitaux propres ou le niveau d'endettement. Une analyse approfondie "
            "est nécessaire."
        )
    elif healthy:
        conclusion = (
            "Conclusion : situation financière globalement saine selon les repères "
            "utilisés, avec résultat net positif, liquidité suffisante et structure "
            "de financement relativement équilibrée. Ces indicateurs ne garantissent "
            "pas l'absence de risque."
        )
    else:
        parts = []

        if margin is not None and margin > 0:
            parts.append("rentable")
        elif margin is not None and margin < 0:
            parts.append("en perte")

        if liq is not None and liq >= 1:
            parts.append("liquide à court terme")
        elif liq is not None:
            parts.append("en tension de liquidité")

        if customer_days is not None and supplier_days is not None:
            if supplier_days > customer_days:
                parts.append("bénéficiant d'un décalage d'encaissement potentiellement favorable")
            elif supplier_days < customer_days:
                parts.append("subissant un décalage de trésorerie potentiellement défavorable")

        description = " et ".join(parts) if parts else "difficile à qualifier avec les données disponibles"
        details = []

        if debt is not None:
            details.append(f"endettement {fr_number(debt)}")
        if autonomy is not None:
            details.append(f"autonomie {fr_number(autonomy * 100, 0)} %")

        detail_text = f" ({'; '.join(details)})" if details else ""

        if debt is not None and debt > 1:
            conclusion = (
                f"Conclusion : entreprise {description}, mais dont le financement "
                f"dépend fortement de l'endettement{detail_text}. "
                "La structure financière mérite une surveillance particulière."
            )
        else:
            conclusion = (
                f"Conclusion : entreprise {description}{detail_text}. "
                "La situation paraît intermédiaire selon les repères retenus ; "
                "les résultats doivent être comparés à ceux du secteur et aux exercices précédents."
            )

    return {
        "strengths": strengths,
        "risks": risks,
        "caveats": caveats,
        "conclusion": conclusion,
    }