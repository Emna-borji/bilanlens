"""Tests de la dataclass Chunk et de extraire_pages (bilanlens/chunks.py).

Vérifie :
- `frozen=True` empêche la mutation par affectation directe ;
- round-trip `to_dict` → JSON → `from_dict` préserve les TYPES
  (notamment `exercice: int` et `page_imprimee: str | None`),
  pas seulement les valeurs. C'est le point critique : si un indexeur
  Chroma relit les JSONL et que `exercice` revient en `str`, les filtres
  numériques (`exercice >= 2020`) tomberont silencieusement à faux.
- `extraire_pages` sur un PDF natif retourne N pages non vides et
  retrouve `evidence_text` du benchmark ;
- `extraire_pages` sur un PDF scanné déclenche l'OCR (marker `ocr`).
"""
import json
from pathlib import Path

import pytest

from bilanlens.chunks import Chunk, decouper_page, detecter_entete, extraire_pages
from bilanlens.extraction import _pdf_page_text

REPERTOIRE_DONNEES = Path(__file__).parent / "data"


class _FakePage:
    """Shim de page pdfplumber pour les tests unitaires de `_pdf_page_text` :
    `extract_words()` doit retourner des dicts {text, x0, x1, top, bottom}
    aux positions choisies par le test."""

    def __init__(self, mots):
        self._mots = mots

    def extract_words(self, **_kwargs):
        return list(self._mots)


def _chunk_valide() -> Chunk:
    return Chunk(
        doc="sotuver_2024",
        entreprise="SOTUVER",
        exercice=2024,
        page_physique=3,
        page_imprimee="3",
        sous_numero=0,
        texte="Total des capitaux propres (B.9) 120 964 179 128 614 666",
    )


def test_chunk_frozen_empeche_affectation_directe():
    chunk = _chunk_valide()
    with pytest.raises(Exception):
        chunk.texte = "autre"  # type: ignore[misc]


def test_chunk_aller_retour_dict_preserve_types():
    """La valeur ET le type survivent au passage par JSON.
    Point critique : `exercice` reste `int`, `page_imprimee` reste `str`.
    """
    original = _chunk_valide()

    comme_dict = original.to_dict()
    ligne_jsonl = json.dumps(comme_dict, ensure_ascii=False)
    rechargee = Chunk.from_dict(json.loads(ligne_jsonl))

    assert rechargee == original
    assert isinstance(rechargee.exercice, int)
    assert isinstance(rechargee.page_imprimee, str)
    assert isinstance(rechargee.page_physique, int)
    assert isinstance(rechargee.sous_numero, int)


def test_chunk_page_imprimee_peut_etre_none():
    """Pages de couverture / signature : pas de numéro imprimé."""
    chunk = Chunk(
        doc="sotuver_2024",
        entreprise="SOTUVER",
        exercice=2024,
        page_physique=1,
        page_imprimee=None,
        sous_numero=0,
        texte="Page de garde",
    )
    rechargee = Chunk.from_dict(json.loads(json.dumps(chunk.to_dict())))
    assert rechargee.page_imprimee is None


def test_chunk_page_imprimee_accepte_chiffres_romains():
    """Pages de préface : « II », « IV »."""
    chunk = Chunk(
        doc="sotuver_2024",
        entreprise="SOTUVER",
        exercice=2024,
        page_physique=2,
        page_imprimee="II",
        sous_numero=0,
        texte="Preface",
    )
    assert chunk.page_imprimee == "II"
    assert isinstance(chunk.page_imprimee, str)


def test_chunk_from_dict_leve_sur_champ_manquant():
    """`from_dict({...})` propage l'erreur si un champ est absent du JSON :
    on refuse de reconstruire un chunk incomplet silencieusement."""
    incomplet = {
        "doc": "sotuver_2024",
        "entreprise": "SOTUVER",
        "exercice": 2024,
        # page_physique manquant
        "page_imprimee": None,
        "sous_numero": 0,
        "texte": "...",
    }
    with pytest.raises(TypeError):
        Chunk.from_dict(incomplet)


# ---------------------------------------------------------------------------
# extraire_pages
# ---------------------------------------------------------------------------
def test_extraire_pages_leve_si_fichier_absent(tmp_path):
    """Chemin inexistant → FileNotFoundError (pas un comportement
    silencieux : on veut un échec explicite en amont du pipeline)."""
    with pytest.raises(FileNotFoundError):
        extraire_pages(tmp_path / "inexistant.pdf")


@pytest.mark.real
def test_extraire_pages_sotuver_natif_contient_evidence_connue():
    """SOTUVER 2024 natif : page 4 doit contenir « Revenus » et le
    montant 100 836 224 (evidence_text de la question Q01)."""
    pages = extraire_pages(REPERTOIRE_DONNEES / "real_sotuver_2024.pdf")
    assert len(pages) >= 10, f"PDF trop court ? {len(pages)} page(s)"

    # Chaque page est (numero_1_based, texte)
    numeros = [n for n, _ in pages]
    assert numeros == list(range(1, len(pages) + 1)), "numérotation 1-based attendue"

    textes = [t for _, t in pages]
    assert any("100 836 224" in t for t in textes), (
        "evidence_text Q01 absente de l'extraction (régression)"
    )

    _, texte_p4 = pages[3]  # 0-indexé
    assert "100 836 224" in texte_p4, (
        f"evidence_text Q01 pas sur la page 4 : « {texte_p4[:150]} » (début)"
    )


@pytest.mark.real
def test_extraire_pages_colonnes_non_collees_sur_sotuver():
    """La reconstruction via `_pdf_page_text` doit séparer les colonnes :
    une ligne du bilan SOTUVER doit avoir ses 2 montants comparatifs
    séparés par ≥ 2 espaces, pas collés (« 100836224165986659 »)."""
    pages = extraire_pages(REPERTOIRE_DONNEES / "real_sotuver_2024.pdf")
    _, texte_p4 = pages[3]

    # Chercher la ligne qui porte le chiffre d'affaires
    lignes_revenus = [l for l in texte_p4.split("\n") if "100 836 224" in l]
    assert lignes_revenus, "ligne « Revenus » introuvable à la page 4"

    ligne = lignes_revenus[0]
    # Les 2 montants comparatifs (2024 et 2023) doivent être séparés
    # par ≥ 2 espaces (notre signal « colonne différente »).
    assert "100 836 224  " in ligne or "100 836 224   " in ligne, (
        f"colonnes collées sur la ligne « {ligne} »"
    )
    # Vérification négative : les 2 valeurs ne sont PAS adjacentes sans espace.
    assert "100836224" not in ligne, (
        f"chiffres collés (extract_text() naïf ?) : « {ligne} »"
    )


@pytest.mark.ocr
def test_extraire_pages_pdf_scanne_declenche_ocr():
    """Sur un bilan scanné (image uniquement), pdfplumber rend du vide ;
    le fallback OCR doit remplir toutes les pages non vides."""
    pages = extraire_pages(REPERTOIRE_DONNEES / "sotuver_scanned.pdf")
    assert len(pages) >= 1

    # Toutes les pages doivent avoir un texte non vide après fallback OCR.
    pages_vides = [n for n, t in pages if not t.strip()]
    assert not pages_vides, (
        f"OCR n'a pas rempli les pages {pages_vides} (fallback cassé ?)"
    )


# ---------------------------------------------------------------------------
# _pdf_page_text : seuil de colonne relatif à la hauteur du mot
# ---------------------------------------------------------------------------
def test_pdf_page_text_seuil_colonne_relatif_a_la_police():
    """Un montant comme « 3 500 » doit rester groupé (gap intra-millier
    petit → espace simple), tandis que deux colonnes voisines doivent
    être séparées (gap grand → double espace).

    Règle : nouvelle colonne si `(x0 - x1_prec) > 1.0 * (bottom - top)`.
    Un seuil fixe en pixels tombait à faux dès qu'on changeait de taille
    de police ; la hauteur du mot (quasi-proportionnelle à la taille)
    donne un seuil qui suit automatiquement.
    """
    # Hauteur du mot = 10 (bottom - top) → seuil colonne = 10.
    # « Immo    3 500   7 200 »
    #   50-80  200-207 210-230  300-307 310-330
    # Gaps : 120 (libellé→col1), 3 (3→500), 70 (col1→col2), 3 (7→200)
    # Attendu : "Immo  3 500  7 200"
    mots = [
        {"text": "Immo", "x0": 50,  "x1": 80,  "top": 100, "bottom": 110},
        {"text": "3",    "x0": 200, "x1": 207, "top": 100, "bottom": 110},
        {"text": "500",  "x0": 210, "x1": 230, "top": 100, "bottom": 110},
        {"text": "7",    "x0": 300, "x1": 307, "top": 100, "bottom": 110},
        {"text": "200",  "x0": 310, "x1": 330, "top": 100, "bottom": 110},
    ]
    texte = _pdf_page_text(_FakePage(mots))
    # (a) « 3 500 » intact : espace simple intra-millier préservé.
    assert "3 500" in texte, f"espace de milliers perdu dans : « {texte} »"
    # (b) Frontière de colonne : 2 espaces entre la 1ʳᵉ et la 2e valeur.
    assert "500  7" in texte, (
        f"colonnes voisines pas séparées par un double espace : « {texte} »"
    )
    # (c) « 7 200 » intact : la 2e valeur n'a pas été recollée.
    assert "7 200" in texte, f"espace de milliers perdu dans : « {texte} »"
    assert "7200" not in texte, (
        f"chiffres recollés par un seuil fixe trop grand : « {texte} »"
    )


# ---------------------------------------------------------------------------
# detecter_entete
# ---------------------------------------------------------------------------
def test_detecter_entete_cas_simple_titre_puis_entete_une_ligne():
    """Cas typique BVMT : BILAN / ... / Notes 31/12/2024 31/12/2023 / rubriques."""
    lignes = [
        "BILAN",
        "",
        "Rubriques                              Notes    31/12/2024    31/12/2023",
        "ACTIFS NON COURANTS",
        "Immobilisations corporelles              2    85 230 110    82 450 220",
    ]
    preambule = detecter_entete(lignes)
    assert preambule == (
        "BILAN\n"
        "Rubriques                              Notes    31/12/2024    31/12/2023"
    )


def test_detecter_entete_sur_deux_lignes_consecutives():
    """En-tête réparti : « Au\\n31/12/2024 ... 31/12/2023 »."""
    lignes = [
        "BILAN",
        "                                Au              Au",
        "                           31/12/2024      31/12/2023",
        "Immobilisations ...",
    ]
    preambule = detecter_entete(lignes)
    # Les 3 lignes du préambule doivent toutes être présentes.
    assert preambule.startswith("BILAN\n")
    assert "Au              Au" in preambule
    assert "31/12/2024      31/12/2023" in preambule


def test_detecter_entete_fallback_sans_pattern_detecte():
    """Page de notes textuelles sans en-tête tabulaire : retourne le titre seul."""
    lignes = [
        "NOTES SUR LES ÉTATS FINANCIERS",
        "",
        "La société a été constituée en 1963 sous forme de ...",
        "Son objet social est la fabrication de ...",
    ]
    assert detecter_entete(lignes) == "NOTES SUR LES ÉTATS FINANCIERS"


def test_detecter_entete_page_vide_retourne_chaine_vide():
    assert detecter_entete([]) == ""
    assert detecter_entete(["", "   ", "\t"]) == ""


def test_detecter_entete_titre_est_lentete_pas_de_doublon():
    """Page qui commence directement par la ligne d'en-tête : titre == en-tête,
    on retourne UNE seule fois cette ligne (pas de doublon)."""
    lignes = [
        "Rubriques     Notes     31/12/2024     31/12/2023",
        "Immobilisations ...",
    ]
    preambule = detecter_entete(lignes)
    assert preambule == "Rubriques     Notes     31/12/2024     31/12/2023"
    assert preambule.count("31/12/2024") == 1  # garantie dédup


def test_detecter_entete_accepte_annees_seules_sans_date_complete():
    """« ... 2024 ... 2023 » doit suffire (\\b20\\d{2}\\b 2 fois)."""
    lignes = [
        "BILAN",
        "Rubriques             2024              2023",
        "Immobilisations ...",
    ]
    preambule = detecter_entete(lignes)
    assert "2024" in preambule and "2023" in preambule
    assert preambule.startswith("BILAN\n")


def test_detecter_entete_ignore_annee_dans_mot_code():
    """`\\b20\\d{2}\\b` : « A2024B » ne doit PAS matcher. Ligne sans
    vraies années → fallback titre."""
    lignes = [
        "RAPPORT",
        "Référence A2024B Version C2023D final",
        "Contenu ...",
    ]
    preambule = detecter_entete(lignes)
    assert preambule == "RAPPORT"


def test_detecter_entete_fenetre_limitee_aux_premieres_lignes():
    """Une phrase du corps du bilan comme « Au cours de 2024, par rapport
    à 2023 » à la 15ᵉ ligne non vide ne doit PAS être prise pour un
    en-tête de colonnes. La fenêtre de détection est bornée."""
    lignes = ["NOTES SUR LES ÉTATS FINANCIERS"]
    # 14 lignes de texte neutre entre le titre et la phrase piège.
    lignes += [f"Paragraphe de contexte ligne {i} sans date." for i in range(14)]
    lignes.append("Au cours de 2024, par rapport à 2023, la société ...")
    lignes.append("suite du paragraphe ...")

    preambule = detecter_entete(lignes)
    # Doit retomber sur le titre seul (fallback), pas sur la phrase piège.
    assert preambule == "NOTES SUR LES ÉTATS FINANCIERS", (
        f"phrase du corps détectée à tort comme en-tête : « {preambule} »"
    )


# ---------------------------------------------------------------------------
# decouper_page
# ---------------------------------------------------------------------------
def _metadonnees(**overrides):
    """Métadonnées communes pour les tests decouper_page."""
    base = dict(
        doc="sotuver_2024",
        entreprise="SOTUVER",
        exercice=2024,
        page_physique=4,
        page_imprimee="4",
    )
    base.update(overrides)
    return base


def test_decouper_page_vide_retourne_liste_vide():
    assert decouper_page("", **_metadonnees()) == []
    assert decouper_page("   \n  \t\n", **_metadonnees()) == []


def test_decouper_page_sous_seuil_retourne_un_chunk_sous_numero_zero():
    """Page courte : un seul Chunk avec sous_numero=0 (= page intacte)."""
    texte = "BILAN\n\nRubriques Notes 31/12/2024 31/12/2023\nImmo 100 200"
    chunks = decouper_page(texte, **_metadonnees(), seuil_chars=4000)
    assert len(chunks) == 1
    assert chunks[0].sous_numero == 0
    assert chunks[0].texte == texte  # texte non muté (frozen + pas de .strip() interne agressif)


def test_decouper_page_au_dessus_seuil_cree_plusieurs_sous_morceaux():
    """Seuil bas → plusieurs sous-morceaux, chacun avec sous_numero >= 1."""
    lignes = ["BILAN", "Rubriques Notes 31/12/2024 31/12/2023"]
    lignes += [f"Rubrique_{i} {i*1000} {i*999}" for i in range(80)]
    texte = "\n".join(lignes)

    chunks = decouper_page(texte, **_metadonnees(), seuil_chars=500)
    assert len(chunks) >= 2
    # Numérotation 1, 2, 3, ... (pas de sous_numero=0 dans un découpage)
    assert [c.sous_numero for c in chunks] == list(range(1, len(chunks) + 1))


def test_decouper_page_preambule_repete_dans_sous_morceaux_suivants():
    """Les sous-morceaux 2+ doivent commencer par le préambule détecté
    (titre + ligne d'en-tête), pour que leurs vecteurs portent le sens."""
    lignes = ["BILAN", "Rubriques Notes 31/12/2024 31/12/2023"]
    lignes += [f"Ligne_{i} {i*1000} {i*999}" for i in range(80)]
    texte = "\n".join(lignes)

    chunks = decouper_page(texte, **_metadonnees(), seuil_chars=500)
    assert len(chunks) >= 2
    for chunk in chunks[1:]:
        assert chunk.texte.startswith("BILAN\nRubriques Notes 31/12/2024 31/12/2023\n"), (
            f"Sous-morceau {chunk.sous_numero} n'a pas le préambule attendu : "
            f"« {chunk.texte[:120]} »"
        )


def test_decouper_page_sans_chevauchement():
    """Chaque ligne « unique » apparaît dans UN et UN SEUL sous-morceau
    (hors préambule répété, qui lui est intentionnellement dupliqué)."""
    lignes = ["BILAN", "Rubriques Notes 31/12/2024 31/12/2023"]
    # Padding à 2 chiffres : évite que MARQUEUR_UNIQUE_01 matche _10, _11, ...
    marqueurs = [f"MARQUEUR_UNIQUE_{i:02d}" for i in range(60)]
    lignes += marqueurs
    texte = "\n".join(lignes)

    chunks = decouper_page(texte, **_metadonnees(), seuil_chars=600)
    textes_concatenes = " ".join(c.texte for c in chunks)
    for marqueur in marqueurs:
        assert textes_concatenes.count(marqueur) == 1, (
            f"{marqueur} apparaît {textes_concatenes.count(marqueur)} fois "
            f"(chevauchement ? perte ?)"
        )


def test_decouper_page_decoupage_uniquement_aux_fins_de_ligne():
    """Aucun sous-morceau ne doit couper au milieu d'une ligne : chaque
    ligne du texte original (hors préambule injecté) doit apparaître
    intacte dans l'un des sous-morceaux."""
    lignes = ["BILAN", "Rubriques Notes 31/12/2024 31/12/2023"]
    lignes += [f"Ligne de données numéro {i} avec montants 1 000 2 000" for i in range(40)]
    texte = "\n".join(lignes)

    chunks = decouper_page(texte, **_metadonnees(), seuil_chars=500)
    textes_concatenes = "\n".join(c.texte for c in chunks)
    for ligne in lignes:
        if ligne.strip():
            assert ligne in textes_concatenes, f"Ligne coupée : « {ligne} »"


def test_decouper_page_ligne_tres_longue_emise_telle_quelle():
    """Si une ligne seule dépasse le budget, elle est émise entière :
    la contrainte « aux fins de ligne » prime sur la contrainte de taille."""
    ligne_longue = "x" * 2000
    texte = f"BILAN\nRubriques 31/12/2024 31/12/2023\n{ligne_longue}\nfin"

    chunks = decouper_page(texte, **_metadonnees(), seuil_chars=500)
    assert any(ligne_longue in c.texte for c in chunks), (
        "ligne de 2000 chars a été perdue ou coupée"
    )


def test_decouper_page_leve_sur_seuil_invalide():
    with pytest.raises(ValueError, match="seuil_chars"):
        decouper_page("x", **_metadonnees(), seuil_chars=0)
    with pytest.raises(ValueError, match="seuil_chars"):
        decouper_page("x", **_metadonnees(), seuil_chars=-10)


def test_decouper_page_metadonnees_propagees_tel_quel_sur_tous_les_chunks():
    """Toutes les métadonnées (doc, entreprise, exercice, pages) sont
    identiques sur chaque chunk d'une même page."""
    lignes = ["BILAN", "Rubriques Notes 31/12/2024 31/12/2023"]
    lignes += [f"Ligne {i}" for i in range(100)]
    texte = "\n".join(lignes)

    chunks = decouper_page(texte, **_metadonnees(page_imprimee="II"), seuil_chars=400)
    assert len(chunks) >= 2
    for c in chunks:
        assert c.doc == "sotuver_2024"
        assert c.entreprise == "SOTUVER"
        assert c.exercice == 2024
        assert c.page_physique == 4
        assert c.page_imprimee == "II"
