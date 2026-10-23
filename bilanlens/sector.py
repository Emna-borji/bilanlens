"""Détection par règles de bilans hors périmètre (banques, assurances).

Pas d'IA : repose sur des libellés caractéristiques du bilan bancaire ou
du bilan d'assurance. L'objectif n'est pas la classification sectorielle,
mais de signaler qu'un bilan a une structure incompatible avec les ratios
industriels/commerciaux usuels.
"""
import re
import unicodedata


def _supprimer_accents(texte: str) -> str:
    normalise = unicodedata.normalize("NFKD", texte)
    return "".join(ch for ch in normalise if not unicodedata.combining(ch))


# Libellés spécifiques aux bilans bancaires (très rares hors banques).
INDICATEURS_BANQUE = [
    "creances sur la clientele",
    "creances sur les etablissements de credit",
    "depots de la clientele",
    "depots et avoirs de la clientele",
    "depots des etablissements de credit",
    "operations avec la clientele",
    "operations interbancaires",
    "produit net bancaire",
    "pnb",
    "marge d'interet",
    "marge d interet",
    "commissions bancaires",
    "ratio de solvabilite",
    "ratio cooke",
    "ratio tier 1",
    "fonds propres reglementaires",
    "banque centrale",
    "portefeuille titres commercial",
    "portefeuille d'investissement",
    "coefficient d'exploitation bancaire",
    "loans to customers",
    "deposits from customers",
    "due to banks",
    "net banking income",
    "net interest margin",
    "central bank",
    "interbank operations",
]

# Libellés spécifiques aux bilans d'assurance.
INDICATEURS_ASSURANCE = [
    "provisions techniques",
    "primes emises",
    "primes acquises",
    "sinistres payes",
    "sinistres a payer",
    "reassurance",
    "cedees aux reassureurs",
    "part des reassureurs",
    "mathematical reserves",
    "insurance contracts",
    "technical provisions",
    "premiums written",
    "premiums earned",
    "claims incurred",
    "claims paid",
    "underwriting result",
    "combined ratio",
    "ratio combine",
    "solvabilite ii",
    "scr",
    "mcr",
]


def _normaliser_chaine_recherche(texte: str) -> str:
    sans_accents = _supprimer_accents(texte).lower()
    return re.sub(r"\s+", " ", sans_accents)


def detecter_secteur_hors_perimetre(texte: str):
    """Retourne un dict décrivant le secteur détecté, ou None si rien.

    Résultat : {'secteur': 'banque'|'assurance', 'correspondances': [str, ...]}
    Seuil : au moins 2 indicateurs distincts du même secteur
    (pour éviter les faux positifs sur un bilan industriel qui cite
    une ligne « reassurance » parmi ses autres produits).
    """
    if not texte:
        return None

    chaine_recherche = _normaliser_chaine_recherche(texte)

    correspondances_banque = [
        indicateur
        for indicateur in INDICATEURS_BANQUE
        if indicateur in chaine_recherche
    ]

    correspondances_assurance = [
        indicateur
        for indicateur in INDICATEURS_ASSURANCE
        if indicateur in chaine_recherche
    ]

    score_banque = len(correspondances_banque)
    score_assurance = len(correspondances_assurance)

    if score_banque >= 2 and score_banque >= score_assurance:
        return {"secteur": "banque", "correspondances": correspondances_banque}

    if score_assurance >= 2:
        return {"secteur": "assurance", "correspondances": correspondances_assurance}

    return None


MESSAGES_SECTEUR = {
    "banque": (
        "Ce document ressemble à un bilan bancaire. La structure de bilan "
        "d'une banque diffère sensiblement d'une société industrielle ou "
        "commerciale (dépôts de clientèle, créances sur la clientèle, "
        "produit net bancaire…). Les ratios proposés par BilanLens ne sont "
        "pas adaptés : utilisez des indicateurs bancaires dédiés "
        "(ratio de solvabilité, coefficient d'exploitation, marge d'intérêt…)."
    ),
    "assurance": (
        "Ce document ressemble à un bilan d'assurance. Les provisions "
        "techniques, les primes acquises et le ratio combiné ne se lisent "
        "pas comme les postes d'une société industrielle ou commerciale. "
        "Les ratios proposés par BilanLens ne sont pas adaptés."
    ),
}
