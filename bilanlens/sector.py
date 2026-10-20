"""Détection par règles de bilans hors périmètre (banques, assurances).

Pas d'IA : repose sur des libellés caractéristiques du bilan bancaire ou
du bilan d'assurance. L'objectif n'est pas la classification sectorielle,
mais de signaler qu'un bilan a une structure incompatible avec les ratios
industriels/commerciaux usuels.
"""
import re
import unicodedata


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


# Libellés spécifiques aux bilans bancaires (très rares hors banques).
BANK_INDICATORS = [
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
INSURANCE_INDICATORS = [
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


def _normalize_haystack(text: str) -> str:
    without_accents = _strip_accents(text).lower()
    return re.sub(r"\s+", " ", without_accents)


def detect_out_of_scope_sector(text: str):
    """Retourne un dict décrivant le secteur détecté, ou None si rien.

    Résultat : {'sector': 'banque'|'assurance', 'matches': [str, ...]}
    Seuil : au moins 2 indicateurs distincts du même secteur
    (pour éviter les faux positifs sur un bilan industriel qui cite
    une ligne « reassurance » parmi ses autres produits).
    """
    if not text:
        return None

    haystack = _normalize_haystack(text)

    bank_matches = [
        indicator
        for indicator in BANK_INDICATORS
        if indicator in haystack
    ]

    insurance_matches = [
        indicator
        for indicator in INSURANCE_INDICATORS
        if indicator in haystack
    ]

    bank_score = len(bank_matches)
    insurance_score = len(insurance_matches)

    if bank_score >= 2 and bank_score >= insurance_score:
        return {"sector": "banque", "matches": bank_matches}

    if insurance_score >= 2:
        return {"sector": "assurance", "matches": insurance_matches}

    return None


SECTOR_MESSAGES = {
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
