"""Détection de l'entreprise d'une question (plan V2 §1).

Table de synonymes versionnée pour les 6 docs BVMT 2024 du corpus,
plus la désambiguation Monoprix (individuel / consolidé / ambigu).

Règles figées ex ante :
- Filtre année : DÉSACTIVÉ (corpus tout 2024, cf. §1 du journal V2).
- Filtre entreprise avec garde-fou : si entreprise non reconnue
  → None, c'est-à-dire pas de filtre, recherche globale.
- Monoprix : « consolidé » / « groupe » → monoprix_consolide ;
  « SNMVT » / « individuel » → monoprix_2024 ; sans qualifier
  → ambigu, on garde les deux dans le périmètre.
"""
from __future__ import annotations

import unicodedata


def _normaliser(texte: str) -> str:
    """Minuscules + retrait des accents (NFKD). Garde la ponctuation."""
    t = texte.lower()
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c))


# Table de synonymes versionnée (§1 du plan V2).
# Ordre : dict est ordonné en Python 3.7+ ; on teste dans cet ordre
# et on prend le premier match. Les 4 entreprises simples sont
# testées AVANT Monoprix pour éviter une collision si une question
# contient les deux noms.
SYNONYMES: dict[str, list[str]] = {
    "sotuver_2024": ["sotuver"],
    "sfbt_2024": [
        "sfbt",
        "societe de fabrication des boissons de tunisie",
    ],
    "ciments_bizerte_2024": [
        "ciments de bizerte",
        "ciments bizerte",
    ],
    "delice_holding_2024": [
        "delice holding",
        "delice",
    ],
}

# Mots-clés qui qualifient une question Monoprix comme ciblant la
# consolidation ou le bilan individuel. Issus directement des 8 Q
# Monoprix du benchmark (Q09-Q16).
MOTS_CLES_CONSOLIDE = ("consolide", "consolidee", "groupe")
MOTS_CLES_INDIVIDUEL = ("snmvt", "individuel", "individuelle")


def _desambiguer_monoprix(question_normalisee: str) -> list[str]:
    """Décide le périmètre Monoprix selon les mots-clés.

    Si la question mentionne à la fois un mot « consolidé » et un
    mot « individuel », on renvoie les deux docs (ambigu) plutôt
    que de trancher arbitrairement. En pratique les Q du benchmark
    ne mélangent pas les deux signaux.
    """
    a_consolide = any(
        mot in question_normalisee for mot in MOTS_CLES_CONSOLIDE
    )
    a_individuel = any(
        mot in question_normalisee for mot in MOTS_CLES_INDIVIDUEL
    )
    if a_consolide and not a_individuel:
        return ["monoprix_consolide_2024"]
    if a_individuel and not a_consolide:
        return ["monoprix_2024"]
    # Ambigu (aucun signal, ou les deux à la fois) → périmètre à 2
    return ["monoprix_2024", "monoprix_consolide_2024"]


def entreprises_filtre(question: str) -> list[str] | None:
    """Renvoie les docs à garder, ou None pour pas de filtre.

    - Si la Q nomme sans ambigüité une des 4 entreprises simples
      (SOTUVER, SFBT, Ciments de Bizerte, Délice) → [doc].
    - Si la Q mentionne Monoprix → désambiguation
      (individuel / consolidé / ambigu à 2 docs).
    - Sinon → None (entreprise non reconnue, pas de filtre).
    """
    q = _normaliser(question)
    for doc, synonymes in SYNONYMES.items():
        for s in synonymes:
            if s in q:
                return [doc]
    if "monoprix" in q:
        return _desambiguer_monoprix(q)
    return None
