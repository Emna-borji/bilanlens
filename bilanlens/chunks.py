"""Chunking du corpus BilanLens pour le RAG.

Un `Chunk` représente un morceau de texte indexable dans Chroma, avec
toutes les métadonnées nécessaires pour (a) le retrouver dans le PDF
d'origine et (b) l'identifier dans `results/*.jsonl` pour les comparaisons
B0 vs V1.

Semaine 2, étape 3 : la dataclass seule. Les fonctions d'extraction, de
détection d'en-tête et de découpage arrivent dans les étapes suivantes.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path


# Deux dates complètes sur la même ligne : « 31/12/2024 ... 31/12/2023 ».
_MOTIF_DATE_COMPLETE = re.compile(r"\d{2}/\d{2}/\d{4}")
# Deux années XXe siècle+ sur la même ligne : « ... 2024 ... 2023 ».
# `\b` évite d'attraper les suffixes dans des codes genre « A2024B ».
_MOTIF_ANNEE = re.compile(r"\b20\d{2}\b")


@dataclass(frozen=True)
class Chunk:
    """Un morceau indexable du corpus.

    Un `Chunk` correspond soit à une page physique entière, soit à un
    sous-morceau d'une page découpée (seuil de caractères dépassé). Dans
    ce second cas, `sous_numero` vaut 1, 2, 3, ... et chaque sous-morceau
    commence par le titre de la page + la ligne d'en-tête des colonnes
    (ou l'en-tête réparti sur 2 lignes consécutives), pour que son vecteur
    conserve le sens des chiffres qu'il contient.

    Métadonnées :
    - `doc` : clé stable du document (ex. `"sotuver_2024"`), identique à
      la clé utilisée dans `data/benchmark/questions.jsonl`.
    - `entreprise`, `exercice` : extraits de `data/benchmark/sources.json`.
    - `page_physique` : index 1-based de la page dans le PDF (telle que
      numérotée par pdfplumber / PyMuPDF, pas celle imprimée).
    - `page_imprimee` : numéro imprimé sur la page elle-même, en
      chaîne pour rester cohérent avec `evidence_page_printed` du
      benchmark (qui est un `str`) et pour gérer les chiffres romains
      des pages de préface (`"II"`, `"IV"`) ou les suffixes (`"A-3"`).
      Peut différer de `page_physique` à cause des pages de couverture,
      table des matières, etc. `None` quand aucun numéro n'est imprimé.
    - `sous_numero` : 0 si la page tient dans un seul chunk ; sinon
      1, 2, 3, ... pour chaque sous-morceau après découpage.
    - `texte` : contenu du chunk, en-tête incluse si c'est un sous-morceau.

    `frozen=True` : un `Chunk` sérialisé dans `data/chunks/*.jsonl` ne doit
    jamais être muté entre son écriture et sa lecture par l'indexeur
    Chroma (invariant exploité par les tests du benchmark).
    """
    doc: str
    entreprise: str
    exercice: int
    page_physique: int
    page_imprimee: str | None
    sous_numero: int
    texte: str

    def to_dict(self) -> dict:
        """Sérialisation stable pour `data/chunks/*.jsonl`.

        On passe par `asdict` plutôt que `__dict__` : il copie proprement
        et fonctionne sur les dataclasses frozen (dont `__dict__` interne
        peut inclure des attributs d'implémentation).
        """

        # La différence est simple : asdict() et __dict__ permettent tous les deux d'accéder aux données d'un objet, mais asdict() est conçu spécialement pour les dataclasses.
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Chunk":
        """Reconstruit un `Chunk` depuis sa forme JSON (une ligne de
        `data/chunks/*.jsonl`). Levée explicite si un champ manque."""
        return cls(**data)


# Seuil en caractères en dessous duquel une page est considérée vide
# (page scannée, image, texte résiduel comme un numéro de page seul).
# Déclenche le fallback OCR CIBLÉ sur cette page uniquement.
SEUIL_VIDE_CHARS = 30


def extraire_pages(
    pdf_path: str | Path,
    seuil_vide_chars: int = SEUIL_VIDE_CHARS,
) -> list[tuple[int, str]]:
    """Extrait le texte par page physique d'un PDF.

    Retourne `[(1, "texte page 1"), (2, "texte page 2"), ...]` ; chaque
    entrée alimentera au moins un `Chunk` dans l'étape suivante.

    Stratégie :
    1. pdfplumber page par page, texte reconstruit via
       `extraction._pdf_page_text` (regroupement par position des mots —
       sépare les colonnes voisines, contrairement à `page.extract_text()`
       qui les colle parfois).
    2. Une page est jugée vide si son texte stripé fait < `seuil_vide_chars`.
       Déclenche l'OCR UNIQUEMENT sur ces pages via `extraction._ocr_pages`
       (logique OCR partagée avec `_ocr_pdf_octets`), pas sur tout le PDF
       (gaspillage de minutes à 300 dpi).

    Lève `FileNotFoundError` si le PDF n'existe pas.
    """
    chemin = Path(pdf_path)
    if not chemin.exists():
        raise FileNotFoundError(chemin)

    import pdfplumber
    from bilanlens.extraction import _ocr_pages, _pdf_page_text

    pages: list[tuple[int, str]] = []
    with pdfplumber.open(chemin) as pdf:
        for numero, page in enumerate(pdf.pages, start=1):
            texte = _pdf_page_text(page).strip()
            pages.append((numero, texte))

    # Indices 1-based des pages vides (texte < seuil_vide_chars).
    indices_vides = [n for n, texte in pages if len(texte) < seuil_vide_chars]
    if not indices_vides:
        return pages

    # `avec_mots=False` : on ne consomme que le texte (le script de
    # chunking n'a pas besoin des coordonnées OCR, économie de temps).
    textes_ocr = _ocr_pages(chemin, indices_cibles=indices_vides)
    if not textes_ocr:
        # Tesseract absent ou pymupdf absent : on retourne tel quel ;
        # le script de chunking signalera les pages vides restantes.
        return pages

    resultats: list[tuple[int, str]] = []
    for (numero, texte_natif) in pages:
        if numero in textes_ocr:
            resultats.append((numero, textes_ocr[numero].strip()))
        else:
            resultats.append((numero, texte_natif))
    return resultats


def _ligne_est_entete_colonnes(ligne: str) -> bool:
    """Vrai si la ligne contient ≥ 2 dates (`31/12/2024`) OU ≥ 2 années
    (`\\b20\\d{2}\\b`). Les bilans comparatifs BVMT portent toujours
    deux exercices côte à côte, donc cette double occurrence est un
    marqueur fiable d'en-tête de colonnes."""
    return (
        len(_MOTIF_DATE_COMPLETE.findall(ligne)) >= 2
        or len(_MOTIF_ANNEE.findall(ligne)) >= 2
    )


# Nombre maximum de lignes non vides parcourues en haut de page pour
# chercher l'en-tête des colonnes. Au-delà, on est dans le corps du
# bilan et une phrase comme « Au cours de 2024, par rapport à 2023 »
# matcherait à tort le motif d'en-tête.
FENETRE_ENTETE_LIGNES = 10


def detecter_entete(lignes: list[str]) -> str:
    """Retourne le préambule à répéter en haut de chaque sous-morceau
    d'une page découpée.

    Composition du préambule :
    - **Titre de la page** = 1ʳᵉ ligne non vide (ex. « BILAN »).
    - **Ligne d'en-tête des colonnes** = 1ʳᵉ ligne qui matche
      `_ligne_est_entete_colonnes`, dans les `FENETRE_ENTETE_LIGNES`
      premières lignes non vides seulement. Au-delà, on est dans le
      corps du bilan et un commentaire comme « Au cours de 2024, par
      rapport à 2023 » matcherait à tort. Si la ligne juste au-dessus
      est non vide et distincte du titre, elle est incluse aussi
      (en-tête réparti sur 2 lignes : « Au / 31/12/2024 »).
    - **Déduplication** : si le titre est déjà le début de l'en-tête,
      on ne le répète pas.
    - **Fallback** : aucun pattern détecté → titre seul.

    Retourne `""` si toutes les lignes sont vides.
    """
    # On garde les indices originaux : la détection « 2 lignes
    # consécutives » doit tester la contiguité dans `lignes`, pas dans
    # la version filtrée.
    indices_non_vides = [i for i, l in enumerate(lignes) if l.strip()]
    if not indices_non_vides:
        return ""

    idx_titre = indices_non_vides[0]
    titre = lignes[idx_titre].strip()

    # Fenêtre : les N premières lignes non vides.
    indices_fenetre = indices_non_vides[:FENETRE_ENTETE_LIGNES]
    idx_entete = next(
        (i for i in indices_fenetre if _ligne_est_entete_colonnes(lignes[i])),
        None,
    )
    if idx_entete is None:
        return titre

    entete = lignes[idx_entete].strip()

    # En-tête sur 2 lignes consécutives : la ligne juste au-dessus
    # (dans `lignes`, PAS dans `indices_non_vides`) doit être non vide
    # et distincte du titre pour éviter de ré-insérer « BILAN ».
    if (
        idx_entete > 0
        and lignes[idx_entete - 1].strip()
        and idx_entete - 1 != idx_titre
    ):
        entete = lignes[idx_entete - 1].strip() + "\n" + entete

    # Dédup : titre déjà présent au début de l'en-tête (cas où la 1ʳᵉ
    # ligne non vide EST l'en-tête, ou où le titre est la ligne
    # supérieure de l'en-tête 2 lignes).
    if entete == titre or entete.startswith(titre + "\n"):
        return entete
    return titre + "\n" + entete


def decouper_page(
    texte_page: str,
    *,
    doc: str,
    entreprise: str,
    exercice: int,
    page_physique: int,
    page_imprimee: str | None,
    seuil_chars: int = 4000,
) -> list[Chunk]:
    """Découpe le texte d'une page physique en 1 ou plusieurs `Chunk`.

    Règles :
    - Si `len(texte_page.strip()) <= seuil_chars` : 1 `Chunk` avec
      `sous_numero=0` (page intacte, pas de découpage).
    - Sinon : découpage **uniquement aux fins de ligne**, sans
      chevauchement. Le 1er sous-morceau garde l'en-tête naturel de la
      page ; les suivants reçoivent `detecter_entete(lignes)` répété en
      tête, pour que leurs vecteurs conservent le sens des chiffres.
    - Si une ligne seule est plus longue que `seuil_chars - preambule`,
      elle est émise telle quelle dans son propre sous-morceau (la
      contrainte « aux fins de ligne » prime sur la contrainte de taille).

    Retourne `[]` si la page est vide (après strip). Lève `ValueError`
    si `seuil_chars <= 0`.
    """
    if seuil_chars <= 0:
        raise ValueError(f"seuil_chars doit etre > 0, recu {seuil_chars}")

    texte_normalise = texte_page.strip()
    if not texte_normalise:
        return []

    base = dict(
        doc=doc,
        entreprise=entreprise,
        exercice=exercice,
        page_physique=page_physique,
        page_imprimee=page_imprimee,
    )

    if len(texte_normalise) <= seuil_chars:
        return [Chunk(**base, sous_numero=0, texte=texte_normalise)]

    lignes = texte_normalise.split("\n")
    preambule = detecter_entete(lignes)
    # Budget pour les sous-morceaux 2, 3, ... où le préambule est injecté.
    # +1 pour le "\n" de séparation entre préambule et contenu.
    budget_avec_preambule = seuil_chars - len(preambule) - 1
    # Garde-fou : si le préambule mange tout le budget (page très exotique),
    # on force un budget minimal pour émettre au moins une ligne par bloc.
    if budget_avec_preambule <= 0:
        budget_avec_preambule = max(1, seuil_chars // 2)

    # Découpage greedy, aux fins de ligne. Le 1er bloc a droit à
    # `seuil_chars` entier (pas d'injection de préambule). Les suivants
    # sont bornés à `budget_avec_preambule`.
    blocs: list[list[str]] = []
    courant: list[str] = []
    taille_courante = 0
    for ligne in lignes:
        budget = seuil_chars if not blocs else budget_avec_preambule
        taille_candidate = taille_courante + len(ligne) + (1 if courant else 0)
        if courant and taille_candidate > budget:
            blocs.append(courant)
            courant = [ligne]
            taille_courante = len(ligne)
        else:
            courant.append(ligne)
            taille_courante = taille_candidate
    if courant:
        blocs.append(courant)

    chunks: list[Chunk] = []
    for i, bloc in enumerate(blocs, start=1):
        texte_bloc = "\n".join(bloc)
        if i == 1:
            # Le 1er bloc contient déjà le titre + en-tête (par construction
            # du découpage greedy depuis le début de la page).
            texte_final = texte_bloc
        else:
            texte_final = preambule + "\n" + texte_bloc if preambule else texte_bloc
        chunks.append(Chunk(**base, sous_numero=i, texte=texte_final))
    return chunks
