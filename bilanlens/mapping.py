
import re
import unicodedata
from .extraction import extract_labeled_values


ALIASES = {
    # Actif
    "non_current_assets": [
        "actifs non courants", "actif non courant",
        "total des actifs non courants", "total actif non courant",
        "total actifs non courants",
        "immobilisations nettes", "immobilisation nette",
        "actif immobilisé", "total de l'actif immobilisé",
        "total actif immobilisé", "immobilisations corporelles nettes",
        "immobilisation corporelle nette", "immobilisations corporelles",
        "immobilisations incorporelles", "immobilisations financières",
        "total immobilisations",
        "total des immobilisations",
        "non-current assets", "total non-current assets",
        "property plant and equipment", "property, plant and equipment",
    ],
    "current_assets": [
        "actifs courants", "actif courant", "actifs circulants",
        "actif circulant", "total des actifs courants",
        "total actifs courants", "totale des actifs courants",
        "total de l'actif courant", "total de l'actif circulant",
        "total actif circulant",
        "total actif courant",
        "total current assets", "current assets",
        "current assets total",
    ],
    "total_assets": [
        "total actif", "total actifs", "total des actifs",
        "total de l'actif", "total général de l'actif", "total assets",
        "total du bilan", "total general du bilan",
        "total des capitaux propres et passifs",
        "total capitaux propres et passifs",
        "total des capitaux propres et des passifs",
        "total equity and liabilities",
    ],
    "inventory": [
        "stocks", "stock", "stocks nets", "stocks de marchandises",
        "stocks et en cours", "stocks et en-cours",
        "inventaires", "inventories", "inventory",
    ],
    "beginning_inventory": [
        "stock au début de l'exercice", "stock initial",
        "stocks au début de l'exercice", "stock d'ouverture",
        "stock au début", "beginning inventory", "opening inventory",
        "stocks à l'ouverture",
    ],
    "ending_inventory": [
        "stock à la fin de l'exercice", "stock final",
        "stocks à la fin de l'exercice", "stock de clôture",
        "stock à la fin", "ending inventory", "closing inventory",
        "stocks à la clôture",
    ],
    "receivables": [
        "créances clients", "clients et comptes rattachés",
        "clients et comptes rattachés nets",
        "créances commerciales", "comptes clients",
        "créances d'exploitation",
        "trade receivables", "accounts receivable",
        "trade and other receivables",
    ],
    "cash": [
        "trésorerie", "disponibilités", "liquidités",
        "liquidités et équivalents de liquidités",
        "trésorerie et équivalents de trésorerie",
        "cash", "cash and cash equivalents", "cash equivalents",
    ],

    # Capitaux propres et passif
    "equity": [
        "capitaux propres", "total capitaux propres",
        "total des capitaux propres",
        "total des capitaux propres avant affectation",
        "total des capitaux propres après affectation",
        "total capitaux propres consolidés", "fonds propres",
        "total des fonds propres", "total equity", "equity",
        "shareholders' equity", "stockholders' equity",
        "total shareholders' equity",
    ],
    "share_capital": [
        "capital social", "capital", "capital émis",
        "share capital", "issued capital",
    ],
    "reserves": [
        "réserves", "reserves", "réserves légales",
        "réserves statutaires", "autres réserves",
        "total des réserves",
    ],
    "current_liabilities": [
        "passifs courants", "passif courant", "passifs circulants",
        "passif circulant", "total des passifs courants",
        "total passifs courants", "total du passif courant",
        "dettes à court terme", "dettes court terme",
        "total des dettes à court terme", "total current liabilities",
        "current liabilities",
    ],
    "supplier_payables": [
        "dettes fournisseurs", "dettes envers les fournisseurs",
        "fournisseurs et comptes rattachés", "comptes fournisseurs",
        "trade payables", "accounts payable",
        "trade and other payables",
    ],
    "tax_social_payables": [
        "dettes fiscales et sociales", "dettes fiscales",
        "dettes sociales", "état et collectivités publiques",
        "organismes sociaux", "tax and social liabilities",
        "tax payables",
    ],
    "long_term_debt": [
        "dettes financières à long terme", "dettes à long terme",
        "dettes long terme", "emprunts bancaires à long terme",
        "emprunts à long terme", "emprunts bancaires",
        "emprunts et dettes financières",
        "emprunts et dettes assimilées",
        "passifs non courants", "total des passifs non courants",
        "total passifs non courants", "long-term debt",
        "long term debt", "non-current liabilities",
        "total non-current liabilities", "non-current borrowings",
        "borrowings",
    ],
    "total_debt": [
        "total des dettes", "total dettes", "dettes totales",
        "total des emprunts et dettes", "total debt", "total borrowings",
        "total liabilities",
    ],

    # Compte de résultat
    "revenue": [
        "chiffre d'affaires", "chiffre d'affaires net", "revenus",
        "total revenus", "produits d'exploitation",
        "ventes de marchandises", "ventes", "revenue", "revenues",
        "net sales", "sales", "turnover",
    ],
    "operating_income": [
        "résultat opérationnel", "résultat d'exploitation",
        "operating income", "operating profit",
    ],
    "net_income": [
        "résultat net", "résultat net de l'exercice",
        "résultat de l'exercice", "résultat net part du groupe",
        "bénéfice net", "perte nette", "net income", "net profit",
        "net loss", "profit for the year", "loss for the year",
        "profit for the period", "net result",
    ],
    "cost_of_goods_sold": [
        "coût des ventes", "cout des ventes",
        "coût de revient des ventes", "coût des marchandises vendues",
        "cout des marchandises vendues", "cost of goods sold",
        "cost of sales",
    ],
    "purchases_incl_vat": [
        "achats ttc", "total des achats ttc",
        "achats toutes taxes comprises", "purchases including vat",
    ],

    # Données boursières et dividendes
    "share_price": [
        "cours de l'action", "prix de l'action",
        "cours de bourse", "cours boursier",
        "cours", "share price", "stock price",
    ],
    "earnings_per_share": [
        "bénéfice par action", "bpa",
        "bénéfice net par action", "résultat par action",
        "earnings per share", "eps",
    ],
    "dividend_per_share": [
        "dividende par action", "dividendes par action",
        "dpa", "dividend per share", "dps",
    ],
}


LABELS = {
    # Actif
    "non_current_assets": "Actifs non courants",
    "current_assets": "Actifs courants",
    "total_assets": "Total actif",
    "inventory": "Stocks (bilan)",
    "beginning_inventory": "Stock au début de l'exercice",
    "ending_inventory": "Stock à la fin de l'exercice",
    "receivables": "Créances clients",
    "cash": "Trésorerie",

    # Capitaux propres et passif
    "equity": "Capitaux propres",
    "share_capital": "Capital social",
    "reserves": "Réserves",
    "current_liabilities": "Passifs courants",
    "supplier_payables": "Dettes fournisseurs",
    "tax_social_payables": "Dettes fiscales et sociales",
    "long_term_debt": "Dettes à long terme",
    "total_debt": "Total des dettes",

    # Compte de résultat
    "revenue": "Chiffre d'affaires",
    "operating_income": "Résultat opérationnel",
    "net_income": "Résultat net",
    "cost_of_goods_sold": "Coût des ventes",
    "purchases_incl_vat": "Achats TTC",

    # Informations complémentaires
    "share_price": "Cours de l'action",
    "earnings_per_share": "Bénéfice par action",
    "dividend_per_share": "Dividende par action",
}


NOTE_REF = re.compile(
    r"\(\s*(?:cf\.?\s*)?(?:notes?\s*)?[a-z]{0,3}\s*[.\-]?\s*"
    r"[0-9ivx]+(?:\.[0-9]+)*\s*\)"
    r"|\(\s*\*+\s*\)",
    flags=re.IGNORECASE,
)


# Dates de type 31/12/2025, 31-12-2025 ou 31.12.2025.
DATE_DMY = re.compile(
    r"\b\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*\d{2,4}\b"
)

# Dates ISO de type 2025-12-31.
DATE_ISO = re.compile(
    r"\b\d{4}\s*-\s*\d{1,2}\s*-\s*\d{1,2}\b"
)

# Unités courantes placées entre parenthèses.
UNIT_PARENS = re.compile(
    r"\(\s*(?:"
    r"tnd|dt|dinar(?:s)?(?:\s+tunisien(?:s|ne|nes)?)?|"
    r"eur|usd|millier(?:s)?|million(?:s)?|"
    r"en\s+tnd|en\s+dt|en\s+millier(?:s)?|en\s+million(?:s)?"
    r")\s*\)",
    flags=re.IGNORECASE,
)


def _strip_accents(s):
    """Supprime les signes diacritiques (é→e, ô→o, ç→c)."""
    normalized = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize(s):
    """
    Normalise un libellé pour faciliter sa reconnaissance.

    Opérations : mise en minuscules, suppression des accents, suppression
    des références de notes, des dates et des unités entre parenthèses.
    Préserve la correspondance exacte (identité canonique).
    """
    s = str(s).lower().replace("’", "'").replace("`", "'")

    # Retirer les références de notes comptables, par exemple (B.2).
    s = NOTE_REF.sub(" ", s)

    # Retirer les unités entre parenthèses, par exemple (TND).
    s = UNIT_PARENS.sub(" ", s)

    # Retirer une date lorsqu'elle figure dans le libellé.
    s = DATE_DMY.sub(" ", s)
    s = DATE_ISO.sub(" ", s)

    # Retirer les mentions introductives de date :
    # « au 31/12/2025 » ou « au 2025-12-31 ».
    s = re.sub(r"\bau\s+", " ", s)

    # Supprimer les accents après avoir isolé les éléments contextuels.
    s = _strip_accents(s)

    # Normaliser les caractères restants (ASCII simple après accents).
    s = re.sub(
        r"[^a-z0-9' ]+",
        " ",
        s,
    )

    return re.sub(r"\s+", " ", s).strip()


ALIAS_INDEX = {}

for _key, _aliases in ALIASES.items():
    for _alias in _aliases:
        _norm = normalize(_alias)

        if _norm in ALIAS_INDEX and ALIAS_INDEX[_norm] != _key:
            raise ValueError(f"Alias en double : « {_alias} »")

        ALIAS_INDEX[_norm] = _key


# Rangs d'alias (plus grand = préféré en cas d'ambiguïté).
# Rang 1 = sous-total officiel (ligne qui agrège plusieurs composants) ;
# rang 0 = composant élémentaire (une seule ligne du bilan).
#
# Convention automatique : tout alias commençant par « total » est rang 1.
# Les autres sous-totaux officiels (sans « total ») sont listés
# explicitement ci-dessous.
_TOTAL_PREFIXES = ("total ",)

_EXPLICIT_RANK1 = {
    # PCG : sous-totaux français qui n'utilisent pas « total ».
    "actif immobilise", "actifs immobilises",
    "actif circulant", "actifs circulants",
    "actif courant", "actifs courants",
    "actif non courant", "actifs non courants",
    "passif courant", "passifs courants",
    "passif non courant", "passifs non courants",
    "passifs circulants", "passif circulant",
    "capitaux propres",
    "fonds propres",
    "dettes a long terme", "dettes long terme",
    "dettes a court terme", "dettes court terme",
    # SCF / IFRS courants.
    "equity",
    "current assets", "non-current assets",
    "current liabilities", "non-current liabilities",
    # Postes résultat agrégés et libellés agrégés fréquents.
    "chiffre d'affaires", "chiffre d'affaires net",
    "revenus", "revenue", "revenues", "net sales", "sales", "turnover",
    "resultat net", "net income", "net profit",
    "resultat de l'exercice", "profit for the year",
    # Immobilisations nettes = sous-total consolidant les immobilisations.
    "immobilisations nettes", "immobilisation nette",
    # Reserves (bare) = sous-total de toutes les réserves.
    "reserves",
}


def alias_rank(label) -> int:
    """0 = alias de composant, 1 = alias de sous-total officiel."""
    norm = normalize(label)
    if not norm:
        return 0
    if norm.startswith(_TOTAL_PREFIXES):
        return 1
    if norm in _EXPLICIT_RANK1:
        return 1
    return 0


def identify_key(label):
    """Associe un libellé à un poste comptable par correspondance exacte."""
    return ALIAS_INDEX.get(normalize(label))


def map_candidates(text, records=None):
    """Associe les lignes extraites aux postes comptables connus."""
    items = records if records else extract_labeled_values(text)
    mapped = []

    for item in items:
        key = identify_key(item["label"])

        mapped.append({
            **item,
            "key": key,
            "rank": alias_rank(item["label"]) if key else 0,
            "canonical_label": LABELS.get(key, "À vérifier"),
            "confidence": "candidate" if key else "unmapped",
        })

    return mapped
