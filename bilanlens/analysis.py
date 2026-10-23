NOTE_SEUILS_COURS = (
    "Seuils du cours : liquidité générale (idéal > 1) et endettement global "
    "(> 1 = dépendance élevée). Les autres seuils sont des repères indicatifs "
    "hors cours."
)


def ratio_securise(numerateur, denominateur):
    """Calcule un ratio sans division par zéro ni donnée manquante."""
    if numerateur is None or denominateur is None or denominateur == 0:
        return None
    return numerateur / denominateur


def nombre_fr(valeur, decimales=2):
    """Formate un nombre avec une virgule décimale."""
    return f"{valeur:,.{decimales}f}".replace(",", " ").replace(".", ",")


def completer_valeurs_financieres(valeurs):
    """Calcule les sous-totaux possibles sans assimiler une absence à zéro."""
    completees = valeurs.copy()

    def somme_si_toutes_presentes(*cles):
        montants = [completees.get(cle) for cle in cles]
        if all(montant is not None for montant in montants):
            return sum(montants)
        return None

    if completees.get("actifs_courants") is None:
        calcule = somme_si_toutes_presentes("stocks", "creances_clients", "tresorerie")
        if calcule is not None:
            completees["actifs_courants"] = calcule

    if completees.get("passifs_courants") is None:
        calcule = somme_si_toutes_presentes(
            "dettes_fournisseurs", "dettes_fiscales_sociales"
        )
        if calcule is not None:
            completees["passifs_courants"] = calcule

    if completees.get("capitaux_propres") is None:
        calcule = somme_si_toutes_presentes(
            "capital_social", "reserves", "resultat_net"
        )
        if calcule is not None:
            completees["capitaux_propres"] = calcule

    if completees.get("total_actif") is None:
        calcule = somme_si_toutes_presentes(
            "actifs_courants", "actifs_non_courants"
        )
        if calcule is not None:
            completees["total_actif"] = calcule

    if completees.get("total_dettes") is None:
        calcule = somme_si_toutes_presentes(
            "passifs_courants", "dettes_long_terme"
        )
        if calcule is not None:
            completees["total_dettes"] = calcule

    # Total passif = capitaux propres + total des dettes (équilibre du bilan).
    # Utilisé par l'autonomie financière ; se ramène au total actif à l'équilibre.
    if completees.get("total_passif") is None:
        calcule = somme_si_toutes_presentes(
            "capitaux_propres", "total_dettes"
        )
        if calcule is not None:
            completees["total_passif"] = calcule

    initial = completees.get("stock_initial")
    final = completees.get("stock_final")

    if initial is not None and final is not None:
        completees["stock_moyen"] = (initial + final) / 2
    else:
        completees["stock_moyen"] = None

    return completees


def calculer_ratios(valeurs):
    """Calcule les 12 ratios du cours répartis en cinq familles.

    Les familles et les formules suivent la fiche du cours
    (Master Data Science – Analyse Financière). Aucun autre ratio
    n'est produit.
    """
    actifs_courants = valeurs.get("actifs_courants")
    passifs_courants = valeurs.get("passifs_courants")
    total_dettes = valeurs.get("total_dettes")
    capitaux_propres = valeurs.get("capitaux_propres")
    chiffre_affaires = valeurs.get("chiffre_affaires")
    resultat_net = valeurs.get("resultat_net")
    total_actif = valeurs.get("total_actif")
    total_passif = valeurs.get("total_passif")
    stocks = valeurs.get("stocks")
    creances_clients = valeurs.get("creances_clients")
    stock_moyen = valeurs.get("stock_moyen")
    cout_des_ventes = valeurs.get("cout_des_ventes")
    achats_ttc = valeurs.get("achats_ttc")
    dettes_fournisseurs = valeurs.get("dettes_fournisseurs")
    cours_action = valeurs.get("cours_action")
    benefice_par_action = valeurs.get("benefice_par_action")
    dividende_par_action = valeurs.get("dividende_par_action")

    numerateur_liquidite_reduite = (
        actifs_courants - stocks
        if actifs_courants is not None and stocks is not None
        else None
    )

    # Autonomie financière : Capitaux propres / Total passif (fiche de cours).
    # À l'équilibre du bilan, Total passif = Total actif, donc on retombe
    # sur ce dernier lorsque le total passif n'est pas disponible.
    denominateur_autonomie = total_passif if total_passif is not None else total_actif
    if total_passif is not None:
        note_autonomie = (
            "Capitaux propres / Total passif. Mesure la part du financement "
            "assurée par les capitaux propres."
        )
    else:
        note_autonomie = (
            "Capitaux propres / Total actif, utilisé à la place du Total passif "
            "absent (équivalent par équilibre du bilan)."
        )

    return [
        {
            "cle": "liquidite_generale",
            "nom": "Liquidité générale",
            "valeur": ratio_securise(actifs_courants, passifs_courants),
            "formule": "Actifs courants / Dettes à court terme",
            "format": "multiple",
            "note": "Mesure la couverture des dettes à court terme par les actifs courants. Idéal > 1 (fiche de cours).",
        },
        {
            "cle": "liquidite_reduite",
            "nom": "Liquidité réduite (quick ratio)",
            "valeur": ratio_securise(numerateur_liquidite_reduite, passifs_courants),
            "formule": "(Actifs courants - Stocks) / Dettes à court terme",
            "format": "multiple",
            "note": "Évalue la couverture des dettes à court terme sans compter sur la vente des stocks.",
        },
        {
            "cle": "endettement",
            "nom": "Endettement global",
            "valeur": ratio_securise(total_dettes, capitaux_propres),
            "formule": "Dettes totales / Capitaux propres",
            "format": "multiple",
            "note": "Si > 1, dépendance élevée au financement externe (fiche de cours).",
        },
        {
            "cle": "autonomie_financiere",
            "nom": "Autonomie financière",
            "valeur": ratio_securise(capitaux_propres, denominateur_autonomie),
            "formule": "Capitaux propres / Total passif",
            "format": "pourcentage",
            "note": note_autonomie,
        },
        {
            "cle": "marge_nette",
            "nom": "Rentabilité nette",
            "valeur": ratio_securise(resultat_net, chiffre_affaires),
            "formule": "Résultat net / Chiffre d'affaires",
            "format": "pourcentage",
            "note": "Part du chiffre d'affaires conservée en résultat net.",
        },
        {
            "cle": "rentabilite_capitaux_propres",
            "nom": "Rentabilité des capitaux propres (ROE)",
            "valeur": ratio_securise(resultat_net, capitaux_propres),
            "formule": "Résultat net / Capitaux propres",
            "format": "pourcentage",
            "note": "Mesure la rentabilité comptable des capitaux propres.",
        },
        {
            "cle": "rentabilite_actifs",
            "nom": "Rentabilité économique (ROA)",
            "valeur": ratio_securise(resultat_net, total_actif),
            "formule": "Résultat net / Total actif",
            "format": "pourcentage",
            "note": "Mesure la rentabilité des actifs utilisés par l'entreprise.",
        },
        {
            "cle": "rotation_stocks",
            "nom": "Rotation des stocks",
            "valeur": ratio_securise(cout_des_ventes, stock_moyen),
            "formule": "Coût des ventes / Stock moyen",
            "format": "multiple",
            "note": "Le stock moyen utilise le stock initial et le stock final.",
        },
        {
            "cle": "delai_clients",
            "nom": "Délai de recouvrement clients",
            "valeur": (
                ratio_securise(creances_clients, chiffre_affaires) * 365
                if creances_clients is not None and chiffre_affaires not in (None, 0)
                else None
            ),
            "formule": "(Créances clients / Chiffre d'affaires) × 365",
            "format": "jours",
            "note": "Approximation : le chiffre d'affaires peut inclure des ventes qui ne sont pas à crédit.",
        },
        {
            "cle": "delai_fournisseurs",
            "nom": "Délai de paiement fournisseurs",
            "valeur": (
                ratio_securise(dettes_fournisseurs, achats_ttc) * 365
                if dettes_fournisseurs is not None
                and achats_ttc not in (None, 0)
                else None
            ),
            "formule": "(Dettes fournisseurs / Achats TTC) × 365",
            "format": "jours",
            "note": "Estimation à partir du solde fournisseurs de fin d'exercice ; une dette moyenne serait plus précise.",
        },
        {
            "cle": "per",
            "nom": "PER",
            "valeur": ratio_securise(cours_action, benefice_par_action),
            "formule": "Cours de l'action / Bénéfice par action",
            "format": "multiple",
            "note": "Combien de fois le bénéfice par action est valorisé dans le cours.",
        },
        {
            "cle": "rendement_dividende",
            "nom": "Dividend Yield",
            "valeur": ratio_securise(dividende_par_action, cours_action),
            "formule": "Dividende par action / Cours de l'action",
            "format": "pourcentage",
            "note": "Rendement du dividende rapporté au cours, hors variation du cours et fiscalité.",
        },
    ]


def formater_ratio(ratio):
    """Formate les ratios en français."""
    valeur = ratio["valeur"]

    if valeur is None:
        return "Non calculable : donnée manquante ou dénominateur nul"

    if ratio["format"] == "pourcentage":
        return f"{nombre_fr(valeur * 100, 2)} %"

    if ratio["format"] == "jours":
        return f"{nombre_fr(valeur, 1)} jours"

    return nombre_fr(valeur, 2)


def interpreter_ratio(cle, valeur, tous_les_ratios=None):
    """Retourne une interprétation indicative, cohérente avec les autres ratios."""
    if valeur is None:
        return "Données insuffisantes pour interpréter ce ratio."

    valeurs_ratios = {
        element["cle"]: element["valeur"]
        for element in (tous_les_ratios or [])
    }

    if cle == "liquidite_generale":
        # Seuil principal du cours : 1.
        if valeur < 1:
            return f"{nombre_fr(valeur)} : liquidité insuffisante, les actifs courants ne couvrent pas les dettes à court terme."
        if valeur <= 2.5:
            return f"{nombre_fr(valeur)} : les dettes à court terme sont couvertes."
        return f"{nombre_fr(valeur)} : liquidité élevée ; vérifier que les stocks et les créances ne sont pas excessifs."

    if cle == "liquidite_reduite":
        if valeur < 1:
            return f"{nombre_fr(valeur)} : liquidité réduite insuffisante. Hors stocks, les actifs courants ne couvrent pas les dettes à court terme."
        return f"{nombre_fr(valeur)} : couverture à court terme assurée sans dépendre de la vente des stocks."

    if cle == "endettement":
        # Seuil principal du cours : 1 → au-delà, dépendance élevée.
        if valeur < 0:
            return "Capitaux propres négatifs : le ratio classique est difficile à interpréter et la situation doit être examinée."
        if valeur <= 1:
            return f"{nombre_fr(valeur)} : endettement global ≤ 1, structure financière équilibrée."
        return f"{nombre_fr(valeur)} : endettement global > 1, dépendance élevée au financement externe."

    if cle == "autonomie_financiere":
        if valeur < 0:
            return "Capitaux propres négatifs : signal de fragilité financière à examiner."
        if valeur < 0.2:
            return f"{nombre_fr(valeur * 100, 2)} % : autonomie financière faible."
        if valeur < 0.5:
            return f"{nombre_fr(valeur * 100, 2)} % : les capitaux propres financent moins de la moitié du passif."
        return f"{nombre_fr(valeur * 100, 2)} % : bonne autonomie financière."

    if cle == "marge_nette":
        if valeur < 0:
            return f"{nombre_fr(valeur * 100, 2)} % : rentabilité nette négative, l'entreprise enregistre une perte nette."
        if valeur == 0:
            return "Rentabilité nette nulle : l'entreprise ne dégage pas de bénéfice net sur la période."
        if valeur < 0.05:
            return f"{nombre_fr(valeur * 100, 2)} % : rentabilité nette faible ; comparer au secteur."
        if valeur < 0.15:
            return f"{nombre_fr(valeur * 100, 2)} % : rentabilité nette positive ; comparer aux entreprises du même secteur."
        return f"{nombre_fr(valeur * 100, 2)} % : rentabilité nette élevée ; vérifier qu'elle est durable."

    if cle == "rentabilite_capitaux_propres":
        if valeur < 0:
            return f"{nombre_fr(valeur * 100, 2)} % : rentabilité des capitaux propres négative."
        if valeur < 0.08:
            return f"{nombre_fr(valeur * 100, 2)} % : rentabilité des capitaux propres relativement faible."
        if valeur <= 0.20:
            return f"{nombre_fr(valeur * 100, 2)} % : bonne rentabilité des capitaux propres."
        return f"{nombre_fr(valeur * 100, 2)} % : rentabilité élevée ; examiner aussi l'endettement global et le niveau des capitaux propres."

    if cle == "rentabilite_actifs":
        if valeur < 0:
            return f"{nombre_fr(valeur * 100, 2)} % : rentabilité économique négative."
        if valeur < 0.05:
            return f"{nombre_fr(valeur * 100, 2)} % : rentabilité économique relativement faible."
        return f"{nombre_fr(valeur * 100, 2)} % : les actifs génèrent un résultat net positif ; comparer au secteur."

    if cle == "rotation_stocks":
        if valeur <= 0:
            return "Rotation nulle ou négative : vérifiez le coût des ventes et le stock moyen."
        jours = 365 / valeur
        categorie = "relativement lente" if valeur < 4 else "relativement rapide"
        return f"{nombre_fr(valeur)} fois, soit environ {nombre_fr(jours, 1)} jours de stock : rotation {categorie}."

    if cle == "delai_clients":
        if valeur < 0:
            return "Délai négatif inhabituel : vérifiez les créances clients et le chiffre d'affaires."
        if valeur < 60:
            return f"{nombre_fr(valeur, 1)} jours : délai inférieur à 60 jours."
        return f"{nombre_fr(valeur, 1)} jours : délai relativement long, à comparer aux conditions de paiement accordées aux clients."

    if cle == "delai_fournisseurs":
        if valeur < 0:
            return "Valeur négative inhabituelle : vérifiez les dettes fournisseurs et les achats TTC."

        jours_clients = valeurs_ratios.get("delai_clients")

        if jours_clients is not None and valeur > jours_clients:
            return (
                f"{nombre_fr(valeur, 1)} jours : l'entreprise paie ses fournisseurs "
                f"plus tard qu'elle n'encaisse ses clients ({nombre_fr(jours_clients, 1)} jours), "
                "ce qui peut soulager sa trésorerie. "
                "Vérifiez les délais légaux et contractuels applicables."
            )

        if jours_clients is not None and valeur < jours_clients:
            return (
                f"{nombre_fr(valeur, 1)} jours : l'entreprise paie ses fournisseurs "
                f"avant d'encaisser ses clients ({nombre_fr(jours_clients, 1)} jours), "
                "ce qui peut exercer une pression sur sa trésorerie."
            )

        if valeur > 60:
            return (
                f"{nombre_fr(valeur, 1)} jours : délai supérieur à 60 jours. "
                "Vérifiez les conditions de paiement et les délais légaux ou contractuels applicables."
            )

        return (
            f"{nombre_fr(valeur, 1)} jours : délai estimé à partir du solde fournisseurs "
            "de clôture ; comparez-le aux conditions contractuelles."
        )

    if cle == "per":
        if valeur <= 0:
            return "PER nul ou négatif : interprétation classique peu pertinente, notamment si le bénéfice par action est nul ou négatif."
        categorie = "faible" if valeur < 10 else "modéré" if valeur <= 20 else "élevé"
        return f"{nombre_fr(valeur)} : PER {categorie}. Les seuils dépendent du secteur, du marché et des perspectives de croissance."

    if cle == "rendement_dividende":
        if valeur < 0:
            return "Dividend Yield négatif inhabituel : vérifiez le dividende et le cours de l'action."
        if valeur == 0:
            return "Dividend Yield nul : aucun dividende positif rapporté au cours de l'action sur la base des données fournies."
        categorie = "faible" if valeur < 0.02 else "correct" if valeur <= 0.05 else "élevé"
        return f"{nombre_fr(valeur * 100, 2)} % : Dividend Yield {categorie}. Ce rendement exclut la variation du cours et la fiscalité."

    return "Aucune règle d'interprétation disponible."


def construire_diagnostic(valeurs, ratios):
    """Construit un diagnostic indicatif et une conclusion globale dynamique."""
    points_forts, risques, precautions = [], [], []
    par_cle = {ratio["cle"]: ratio["valeur"] for ratio in ratios}

    liquidite = par_cle.get("liquidite_generale")
    liquidite_reduite = par_cle.get("liquidite_reduite")
    endettement = par_cle.get("endettement")
    marge = par_cle.get("marge_nette")
    rcp = par_cle.get("rentabilite_capitaux_propres")
    autonomie = par_cle.get("autonomie_financiere")
    roa = par_cle.get("rentabilite_actifs")
    jours_clients = par_cle.get("delai_clients")
    jours_fournisseurs = par_cle.get("delai_fournisseurs")
    rotation_stocks = par_cle.get("rotation_stocks")
    per = par_cle.get("per")
    rendement_dividende = par_cle.get("rendement_dividende")

    # Liquidité
    if liquidite is not None:
        if liquidite >= 1:
            points_forts.append(f"Bonne couverture générale à court terme : liquidité de {nombre_fr(liquidite)}.")
        else:
            risques.append(f"Liquidité générale inférieure à 1 ({nombre_fr(liquidite)}) : les actifs courants ne couvrent pas les passifs courants.")
    else:
        precautions.append("Liquidité générale non calculée : vérifier les actifs et passifs courants.")

    if liquidite_reduite is not None and liquidite_reduite < 1:
        risques.append(f"Liquidité réduite de {nombre_fr(liquidite_reduite)} : hors stocks, la couverture des passifs courants est insuffisante.")

    # Endettement global
    if valeurs.get("capitaux_propres") is not None and valeurs["capitaux_propres"] <= 0:
        risques.append("Capitaux propres nuls ou négatifs : l'endettement global est difficile à interpréter.")
    elif endettement is not None:
        if endettement > 1:
            risques.append(f"Endettement global > 1 ({nombre_fr(endettement)}) : dépendance élevée au financement externe.")
        elif endettement >= 0:
            points_forts.append(f"Endettement global ≤ 1 ({nombre_fr(endettement)}) : structure financière équilibrée.")
    else:
        precautions.append("Endettement global non calculé : vérifier le total des dettes et les capitaux propres.")

    # Rentabilité
    if marge is not None:
        if marge > 0:
            points_forts.append(f"Rentabilité nette positive : {nombre_fr(marge * 100, 2)} %.")
        elif marge < 0:
            risques.append("Le résultat net est négatif : l'entreprise enregistre une perte nette.")
        else:
            risques.append("Le résultat net est nul : l'entreprise ne dégage pas de bénéfice net.")

    if rcp is not None and rcp >= 0.15:
        points_forts.append(f"Rentabilité des capitaux propres élevée : ROE de {nombre_fr(rcp * 100, 2)} %.")
    elif rcp is not None and rcp < 0:
        risques.append("Le ROE est négatif : examiner le résultat net et la structure des capitaux propres.")

    if autonomie is not None:
        if autonomie < 0:
            risques.append("Les capitaux propres sont négatifs par rapport au total actif.")
        elif autonomie < 0.20:
            risques.append(f"Autonomie financière faible : {nombre_fr(autonomie * 100, 2)} %.")
        elif autonomie < 0.50:
            risques.append(f"Autonomie financière inférieure à 50 % : {nombre_fr(autonomie * 100, 2)} %. Les capitaux propres financent moins de la moitié des actifs.")

    if roa is not None and rcp is not None and roa > 0 and rcp >= 2 * roa:
        precautions.append("Le ROE atteint au moins deux fois le ROA. Examiner l'effet de levier et le niveau des capitaux propres.")

    # Délais clients et fournisseurs
    if jours_clients is not None:
        precautions.append(f"Délai de recouvrement clients estimé à {nombre_fr(jours_clients, 1)} jours. Le calcul utilise le chiffre d'affaires total comme approximation.")

    if jours_fournisseurs is not None:
        precautions.append(f"Délai fournisseurs estimé à {nombre_fr(jours_fournisseurs, 1)} jours à partir du solde de clôture, et non d'une dette moyenne.")

    if jours_clients is not None and jours_fournisseurs is not None:
        if jours_fournisseurs > jours_clients:
            points_forts.append(
                f"Décalage potentiellement favorable à la trésorerie : les clients "
                f"sont encaissés en {nombre_fr(jours_clients, 1)} jours, contre "
                f"{nombre_fr(jours_fournisseurs, 1)} jours pour payer les fournisseurs. "
                "Vérifier les délais contractuels et légaux."
            )
        elif jours_fournisseurs < jours_clients:
            risques.append(
                f"Décalage potentiellement défavorable à la trésorerie : les fournisseurs "
                f"sont payés en {nombre_fr(jours_fournisseurs, 1)} jours, avant l'encaissement "
                f"des clients estimé à {nombre_fr(jours_clients, 1)} jours."
            )

    # Stocks
    if rotation_stocks is not None:
        if rotation_stocks > 0:
            jours_stock = 365 / rotation_stocks
            precautions.append(f"Rotation des stocks : {nombre_fr(rotation_stocks)} fois, soit environ {nombre_fr(jours_stock, 1)} jours de stock sur la base de 365 jours et du stock moyen initial-final.")
        else:
            precautions.append("Rotation des stocks nulle ou négative : vérifiez le coût des ventes et le stock moyen.")

    # Marché
    if per is not None:
        precautions.append(f"PER de {nombre_fr(per)} : interprétation à comparer au secteur et aux perspectives de croissance.")

    if rendement_dividende is not None:
        precautions.append(f"Dividend Yield : {nombre_fr(rendement_dividende * 100, 2)} %, hors variation du cours et fiscalité.")

    if not points_forts:
        points_forts.append("Aucun point fort ne peut être établi avec certitude à partir des données disponibles.")

    if not risques:
        risques.append("Aucun signal d'alerte détecté par les règles simples ; cela ne garantit pas l'absence de risque.")

    precautions.append(NOTE_SEUILS_COURS)
    precautions.append(
        "Diagnostic pédagogique indicatif : les seuils varient selon le secteur. "
        "Vérifier les données, les unités, les formules du cours et la comparabilité des exercices."
    )

    # Conclusion globale dynamique
    capitaux_negatifs = valeurs.get("capitaux_propres") is not None and valeurs["capitaux_propres"] <= 0
    resultat_negatif = valeurs.get("resultat_net") is not None and valeurs["resultat_net"] < 0

    fragile = (
        capitaux_negatifs
        or resultat_negatif
        or (liquidite is not None and liquidite < 1)
        or (endettement is not None and endettement > 2)
        or (autonomie is not None and autonomie < 0.20)
    )

    saine = (
        valeurs.get("resultat_net") is not None
        and valeurs["resultat_net"] > 0
        and liquidite is not None and liquidite >= 1
        and liquidite_reduite is not None and liquidite_reduite >= 1
        and autonomie is not None and autonomie >= 0.50
        and endettement is not None and 0 <= endettement <= 1
        and not capitaux_negatifs
    )

    if fragile:
        conclusion = (
            "Conclusion : situation financière fragile selon les indicateurs "
            "disponibles. Des signaux d'alerte touchent la rentabilité, la liquidité, "
            "les capitaux propres ou le niveau d'endettement. Une analyse approfondie "
            "est nécessaire."
        )
    elif saine:
        conclusion = (
            "Conclusion : situation financière globalement saine selon les repères "
            "utilisés, avec résultat net positif, liquidité suffisante et structure "
            "de financement relativement équilibrée. Ces indicateurs ne garantissent "
            "pas l'absence de risque."
        )
    else:
        morceaux = []

        if marge is not None and marge > 0:
            morceaux.append("rentable")
        elif marge is not None and marge < 0:
            morceaux.append("en perte")

        if liquidite is not None and liquidite >= 1:
            morceaux.append("liquide à court terme")
        elif liquidite is not None:
            morceaux.append("en tension de liquidité")

        if jours_clients is not None and jours_fournisseurs is not None:
            if jours_fournisseurs > jours_clients:
                morceaux.append("bénéficiant d'un décalage d'encaissement potentiellement favorable")
            elif jours_fournisseurs < jours_clients:
                morceaux.append("subissant un décalage de trésorerie potentiellement défavorable")

        description = " et ".join(morceaux) if morceaux else "difficile à qualifier avec les données disponibles"
        details = []

        if endettement is not None:
            details.append(f"endettement global {nombre_fr(endettement)}")
        if autonomie is not None:
            details.append(f"autonomie {nombre_fr(autonomie * 100, 0)} %")

        texte_detail = f" ({'; '.join(details)})" if details else ""

        if endettement is not None and endettement > 1:
            conclusion = (
                f"Conclusion : entreprise {description}, mais dont le financement "
                f"dépend fortement de l'endettement{texte_detail}. "
                "La structure financière mérite une surveillance particulière."
            )
        else:
            conclusion = (
                f"Conclusion : entreprise {description}{texte_detail}. "
                "La situation paraît intermédiaire selon les repères retenus ; "
                "les résultats doivent être comparés à ceux du secteur et aux exercices précédents."
            )

    return {
        "points_forts": points_forts,
        "risques": risques,
        "precautions": precautions,
        "conclusion": conclusion,
    }
