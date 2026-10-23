
import re
import unicodedata
from .extraction import extraire_valeurs_etiquetees


ALIAS = {
    # Actif
    "actifs_non_courants": [
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
    "actifs_courants": [
        "actifs courants", "actif courant", "actifs circulants",
        "actif circulant", "total des actifs courants",
        "total actifs courants", "totale des actifs courants",
        "total de l'actif courant", "total de l'actif circulant",
        "total actif circulant",
        "total actif courant",
        "total current assets", "current assets",
        "current assets total",
    ],
    "total_actif": [
        "total actif", "total actifs", "total des actifs",
        "total de l'actif", "total général de l'actif", "total assets",
        "total du bilan", "total general du bilan",
        "total des capitaux propres et passifs",
        "total capitaux propres et passifs",
        "total de capitaux propres et passifs",
        "total des capitaux propres et des passifs",
        "total equity and liabilities",
    ],
    "stocks": [
        "stocks", "stock", "stocks nets", "stocks de marchandises",
        "stocks et en cours", "stocks et en-cours",
        "inventaires", "inventories", "inventory",
    ],
    "stock_initial": [
        "stock au début de l'exercice", "stock initial",
        "stocks au début de l'exercice", "stock d'ouverture",
        "stock au début", "beginning inventory", "opening inventory",
        "stocks à l'ouverture",
    ],
    "stock_final": [
        "stock à la fin de l'exercice", "stock final",
        "stocks à la fin de l'exercice", "stock de clôture",
        "stock à la fin", "ending inventory", "closing inventory",
        "stocks à la clôture",
    ],
    "creances_clients": [
        "créances clients", "clients et comptes rattachés",
        "clients et comptes rattachés nets",
        "créances commerciales", "comptes clients",
        "créances d'exploitation",
        "trade receivables", "accounts receivable",
        "trade and other receivables",
    ],
    "tresorerie": [
        "trésorerie", "disponibilités", "liquidités",
        "liquidités et équivalents de liquidités",
        "trésorerie et équivalents de trésorerie",
        "cash", "cash and cash equivalents", "cash equivalents",
    ],

    # Capitaux propres et passif
    "capitaux_propres": [
        "capitaux propres", "total capitaux propres",
        "total des capitaux propres",
        "total des capitaux propres avant affectation",
        "total des capitaux propres après affectation",
        "total des capitaux propres (part du groupe)",
        "capitaux propres part du groupe",
        "total capitaux propres consolidés",
        "total capitaux propres consolides",
        "capitaux propres consolidés",
        "fonds propres",
        "total des fonds propres", "total equity", "equity",
        "shareholders' equity", "stockholders' equity",
        "total shareholders' equity",
    ],
    "interets_minoritaires": [
        "intérêts minoritaires", "intérêts des minoritaires",
        "total des intérêts minoritaires",
        "total des intérêts des minoritaires",
        "intérêts hors groupe", "part des minoritaires",
        "minority interests", "non-controlling interests",
        "total non-controlling interests",
    ],
    "capital_social": [
        "capital social", "capital", "capital émis",
        "share capital", "issued capital",
    ],
    "reserves": [
        "réserves", "reserves", "réserves légales",
        "réserves statutaires", "autres réserves",
        "total des réserves",
    ],
    "passifs_courants": [
        "passifs courants", "passif courant", "passifs circulants",
        "passif circulant", "total des passifs courants",
        "total passifs courants", "total du passif courant",
        "dettes à court terme", "dettes court terme",
        "total des dettes à court terme", "total current liabilities",
        "current liabilities",
    ],
    "dettes_fournisseurs": [
        "dettes fournisseurs", "dettes envers les fournisseurs",
        "fournisseurs et comptes rattachés", "comptes fournisseurs",
        "trade payables", "accounts payable",
        "trade and other payables",
    ],
    "dettes_fiscales_sociales": [
        "dettes fiscales et sociales", "dettes fiscales",
        "dettes sociales", "état et collectivités publiques",
        "organismes sociaux", "tax and social liabilities",
        "tax payables",
    ],
    "dettes_long_terme": [
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
    "total_dettes": [
        "total des dettes", "total dettes", "dettes totales",
        "total des emprunts et dettes", "total debt", "total borrowings",
        "total liabilities",
        "total des passifs", "total passifs",
    ],

    # Compte de résultat
    "chiffre_affaires": [
        "chiffre d'affaires", "chiffre d'affaires net", "revenus",
        "total revenus", "produits d'exploitation",
        "ventes de marchandises", "ventes", "revenue", "revenues",
        "net sales", "sales", "turnover",
    ],
    "resultat_operationnel": [
        "résultat opérationnel", "résultat d'exploitation",
        "operating income", "operating profit",
    ],
    "resultat_net": [
        "résultat net", "résultat net de l'exercice",
        "résultat de l'exercice", "résultat net part du groupe",
        "bénéfice net", "perte nette", "net income", "net profit",
        "net loss", "profit for the year", "loss for the year",
        "profit for the period", "net result",
    ],
    "cout_des_ventes": [
        "coût des ventes", "cout des ventes",
        "coût de revient des ventes", "coût des marchandises vendues",
        "cout des marchandises vendues", "cost of goods sold",
        "cost of sales",
    ],
    "achats_ttc": [
        "achats ttc", "total des achats ttc",
        "achats toutes taxes comprises", "purchases including vat",
    ],

    # Données boursières et dividendes
    "cours_action": [
        "cours de l'action", "prix de l'action",
        "cours de bourse", "cours boursier",
        "cours", "share price", "stock price",
    ],
    "benefice_par_action": [
        "bénéfice par action", "bpa",
        "bénéfice net par action", "résultat par action",
        "earnings per share", "eps",
    ],
    "dividende_par_action": [
        "dividende par action", "dividendes par action",
        "dpa", "dividend per share", "dps",
    ],
}


LIBELLES = {
    # Actif
    "actifs_non_courants": "Actifs non courants",
    "actifs_courants": "Actifs courants",
    "total_actif": "Total actif",
    "stocks": "Stocks (bilan)",
    "stock_initial": "Stock au début de l'exercice",
    "stock_final": "Stock à la fin de l'exercice",
    "creances_clients": "Créances clients",
    "tresorerie": "Trésorerie",

    # Capitaux propres et passif
    "capitaux_propres": "Capitaux propres",
    "interets_minoritaires": "Intérêts minoritaires",
    "capital_social": "Capital social",
    "reserves": "Réserves",
    "passifs_courants": "Passifs courants",
    "dettes_fournisseurs": "Dettes fournisseurs",
    "dettes_fiscales_sociales": "Dettes fiscales et sociales",
    "dettes_long_terme": "Dettes à long terme",
    "total_dettes": "Total des dettes",

    # Compte de résultat
    "chiffre_affaires": "Chiffre d'affaires",
    "resultat_operationnel": "Résultat opérationnel",
    "resultat_net": "Résultat net",
    "cout_des_ventes": "Coût des ventes",
    "achats_ttc": "Achats TTC",

    # Informations complémentaires
    "cours_action": "Cours de l'action",
    "benefice_par_action": "Bénéfice par action",
    "dividende_par_action": "Dividende par action",
}


REF_NOTE = re.compile(
    r"\(\s*(?:cf\.?\s*)?(?:notes?\s*)?[a-z]{0,3}\s*[.\-]?\s*"
    r"[0-9ivx]+(?:\.[0-9]+)*\s*\)"
    r"|\(\s*\*+\s*\)",
    flags=re.IGNORECASE,
)


# Dates de type 31/12/2025, 31-12-2025 ou 31.12.2025.
DATE_JMA = re.compile(
    r"\b\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*\d{2,4}\b"
)

# Dates ISO de type 2025-12-31.
DATE_ISO = re.compile(
    r"\b\d{4}\s*-\s*\d{1,2}\s*-\s*\d{1,2}\b"
)

# Unités courantes placées entre parenthèses.
UNITES_ENTRE_PARENTHESES = re.compile(
    r"\(\s*(?:"
    r"tnd|dt|dinar(?:s)?(?:\s+tunisien(?:s|ne|nes)?)?|"
    r"eur|usd|millier(?:s)?|million(?:s)?|"
    r"en\s+tnd|en\s+dt|en\s+millier(?:s)?|en\s+million(?:s)?"
    r")\s*\)",
    flags=re.IGNORECASE,
)


def _supprimer_accents(chaine):
    """Supprime les signes diacritiques (é→e, ô→o, ç→c)."""
    normalisee = unicodedata.normalize("NFKD", chaine)
    return "".join(ch for ch in normalisee if not unicodedata.combining(ch))


def normaliser(libelle):
    """
    Normalise un libellé pour faciliter sa reconnaissance.

    Opérations : mise en minuscules, suppression des accents, suppression
    des références de notes, des dates et des unités entre parenthèses.
    Préserve la correspondance exacte (identité canonique).
    """
    libelle = str(libelle).lower().replace("’", "'").replace("`", "'")

    # Retirer les références de notes comptables, par exemple (B.2).
    libelle = REF_NOTE.sub(" ", libelle)

    # Retirer les unités entre parenthèses, par exemple (TND).
    libelle = UNITES_ENTRE_PARENTHESES.sub(" ", libelle)

    # Retirer une date lorsqu'elle figure dans le libellé.
    libelle = DATE_JMA.sub(" ", libelle)
    libelle = DATE_ISO.sub(" ", libelle)

    # Retirer les mentions introductives de date :
    # « au 31/12/2025 » ou « au 2025-12-31 ».
    libelle = re.sub(r"\bau\s+", " ", libelle)

    # Supprimer les accents après avoir isolé les éléments contextuels.
    libelle = _supprimer_accents(libelle)

    # Normaliser les caractères restants (ASCII simple après accents).
    libelle = re.sub(
        r"[^a-z0-9' ]+",
        " ",
        libelle,
    )

    return re.sub(r"\s+", " ", libelle).strip()


INDEX_ALIAS = {}

for _cle, _alias in ALIAS.items():
    for _libelle_alias in _alias:
        _norm = normaliser(_libelle_alias)

        if _norm in INDEX_ALIAS and INDEX_ALIAS[_norm] != _cle:
            raise ValueError(f"Alias en double : « {_libelle_alias} »")

        INDEX_ALIAS[_norm] = _cle


# Rangs d'alias (plus grand = préféré en cas d'ambiguïté).
# Rang 1 = sous-total officiel (ligne qui agrège plusieurs composants) ;
# rang 0 = composant élémentaire (une seule ligne du bilan).
#
# Convention automatique : tout alias commençant par « total » est rang 1.
# Les autres sous-totaux officiels (sans « total ») sont listés
# explicitement ci-dessous.
_PREFIXES_TOTAL = ("total ",)

_RANG1_EXPLICITE = {
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
    # SCE / IFRS courants.
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
    # Stocks nets = stocks bruts - provisions (sous-total officiel).
    "stocks nets",
    # Clients et comptes rattachés nets = idem (après provisions).
    "clients et comptes rattaches nets",
}


def rang_alias(libelle) -> int:
    """0 = alias de composant, 1 = alias de sous-total officiel."""
    norm = normaliser(libelle)
    if not norm:
        return 0
    if norm.startswith(_PREFIXES_TOTAL):
        return 1
    if norm in _RANG1_EXPLICITE:
        return 1
    return 0


def identifier_cle(libelle):
    """Associe un libellé à un poste comptable par correspondance exacte."""
    return INDEX_ALIAS.get(normaliser(libelle))


def associer_candidats(texte, enregistrements=None):
    """Associe les lignes extraites aux postes comptables connus."""
    elements = enregistrements if enregistrements else extraire_valeurs_etiquetees(texte)
    associes = []

    for element in elements:
        cle = identifier_cle(element["libelle"])

        associes.append({
            **element,
            "cle": cle,
            "rang": rang_alias(element["libelle"]) if cle else 0,
            "libelle_canonique": LIBELLES.get(cle, "À vérifier"),
            "confiance": "candidat" if cle else "non_associe",
        })

    return associes
