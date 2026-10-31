"""Verifie que chaque `evidence_text` du benchmark se retrouve dans un
chunk de la bonne `page_physique` du bon document.

Pourquoi un test separe de `test_benchmark.py` :
- `test_benchmark.py` compare chaque `evidence_text` au PDF brut (via
  `pdfplumber.extract_text()`). C'est le filet « le benchmark est bien
  annote ».
- Ici, on compare `evidence_text` au texte des CHUNKS ecrits dans
  `data/chunks/*.jsonl` par `scripts/chunk_corpus.py`. C'est le filet
  « les chunks preservent assez de texte pour que le RAG puisse
  retrouver la bonne page ». Un decoupage qui perd un morceau crucial
  passerait ici, pas dans l'autre test.

Regles reutilisees de `test_benchmark.py` :
- `_normaliser` : minuscules, accents retires, whitespace aplati, soft
  hyphens enleves, apostrophes typographiques rabaissees.
- `evidence_text` est decoupe sur « ... » et chaque segment >= 10
  caracteres doit se retrouver dans le chunk de la bonne page.
- Idem pour chaque `calculation.intermediate_values[*].evidence_text`.

Signalement vs modification du benchmark : si une preuve est coupee
entre deux sous-morceaux de la meme page (sous_numero differents), le
test echoue en LE SIGNALANT, pas en touchant au benchmark.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.test_benchmark import _normaliser


RACINE = Path(__file__).parent.parent
BENCH_PATH = RACINE / "data" / "benchmark" / "questions.jsonl"
CHUNKS_DIR = RACINE / "data" / "chunks"


def _normaliser_tolerant_espaces_dans_nombres(texte: str) -> str:
    """`_normaliser` + colmatage des espaces entre deux chiffres.

    Pourquoi : `evidence_text` du benchmark est annote a partir de
    `pdfplumber.extract_text()`, qui parfois ecrit « -44790 355 » (espace
    perdu). Les chunks sont ecrits par `_pdf_page_text()` qui preserve
    les espaces inter-mots et ecrit « -44 790 355 ». C'est le MEME
    nombre : la comparaison ne doit pas echouer sur ce formatage.

    On ne touche pas aux espaces entre lettres, ni aux espaces entre
    chiffre et lettre : seuls les espaces chiffre->chiffre sont collapses.
    """
    base = _normaliser(texte)
    # Boucle plusieurs passes pour chainer « 1 2 3 » -> « 123 ».
    for _ in range(5):
        nouveau = re.sub(r"(\d)\s(\d)", r"\1\2", base)
        if nouveau == base:
            break
        base = nouveau
    return base


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------
def _doc_depuis_evidence_doc(evidence_doc: str) -> str:
    """`real_sotuver_2024.pdf` -> `sotuver_2024`."""
    return evidence_doc.replace("real_", "").replace(".pdf", "")


@pytest.fixture(scope="module")
def chunks_par_doc_et_page() -> dict:
    """{doc: {page_physique: [chunk_normalise, ...]}} pour toutes les pages
    de tous les docs trouves dans `data/chunks/`."""
    if not CHUNKS_DIR.exists():
        pytest.skip(
            "data/chunks/ absent : lance d'abord scripts/chunk_corpus.py"
        )
    index: dict[str, dict[int, list[str]]] = {}
    for jsonl in CHUNKS_DIR.glob("*.jsonl"):
        doc = jsonl.stem
        index.setdefault(doc, {})
        with jsonl.open(encoding="utf-8") as f:
            for ligne in f:
                c = json.loads(ligne)
                page = c["page_physique"]
                index[doc].setdefault(page, []).append(
                    _normaliser_tolerant_espaces_dans_nombres(c["texte"])
                )
    if not index:
        pytest.skip(
            "data/chunks/*.jsonl vide : lance d'abord scripts/chunk_corpus.py"
        )
    return index


@pytest.fixture(scope="module")
def questions() -> list[dict]:
    with BENCH_PATH.open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


# ---------------------------------------------------------------------------
# Verification unitaire d'un segment
# ---------------------------------------------------------------------------
def _preuves_de(evidence_text: str) -> list[str]:
    """Decoupe `evidence_text` sur « ... » et garde les segments >= 10 car.
    (meme regle que `test_benchmark.py`)."""
    return [
        s.strip()
        for s in evidence_text.split("...")
        if len(s.strip()) >= 10
    ]


def _localiser_segment(segment_normalise: str, chunks_page: list[str]) -> int | None:
    """Retourne l'index du sous-morceau qui contient le segment, ou None.

    Si None : soit absent, soit coupe entre deux sous-morceaux. Le
    caller distingue en testant la concatenation.
    """
    for i, texte in enumerate(chunks_page):
        if segment_normalise in texte:
            return i
    return None


def _coupe_entre_sous_morceaux(
    segment_normalise: str, chunks_page: list[str]
) -> bool:
    """Un segment peut etre coupe entre 2 sous-morceaux consecutifs si la
    concatenation (avec un espace) le contient alors qu'aucun seul ne le
    contient. On teste au niveau des paires consecutives.

    Note : `chunks_page` contient DEJA des textes normalises
    (`_normaliser_tolerant_espaces_dans_nombres`), donc la concatenation
    reste dans la meme forme.
    """
    for a, b in zip(chunks_page, chunks_page[1:]):
        if segment_normalise in (a + " " + b):
            return True
    return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_couverture_evidence_text_par_les_chunks(
    questions, chunks_par_doc_et_page
):
    """Chaque segment >= 10 car. d'evidence_text (hors sans_reponse) doit
    etre present dans AU MOINS un chunk de la bonne page physique."""
    manquants: list[str] = []
    coupes: list[str] = []
    for q in questions:
        if q["category"] == "sans_reponse":
            continue
        doc = _doc_depuis_evidence_doc(q["evidence_doc"])
        page = q["evidence_page_physical"]
        chunks_page = chunks_par_doc_et_page.get(doc, {}).get(page, [])
        if not chunks_page:
            manquants.append(f"{q['id']} : aucun chunk pour {doc} p.{page}")
            continue
        for segment in _preuves_de(q["evidence_text"]):
            seg_n = _normaliser_tolerant_espaces_dans_nombres(segment)
            if _localiser_segment(seg_n, chunks_page) is not None:
                continue
            # Preuve introuvable dans un sous-morceau unique. Est-elle
            # coupee entre deux ? On le signale distinctement.
            if _coupe_entre_sous_morceaux(seg_n, chunks_page):
                coupes.append(
                    f"{q['id']} : segment coupe entre deux sous-morceaux de "
                    f"{doc} p.{page} : '{segment[:60]}'"
                )
            else:
                manquants.append(
                    f"{q['id']} : segment absent des chunks de {doc} p.{page} : "
                    f"'{segment[:60]}'"
                )
    rapport = manquants + coupes
    assert not rapport, "\n".join(["Couverture incomplete :"] + rapport)


def test_couverture_intermediate_values_par_les_chunks(
    questions, chunks_par_doc_et_page
):
    """Pour chaque Q calcul/comparaison, chaque intermediate_value.evidence_text
    doit etre present dans un chunk de la bonne page physique."""
    manquants: list[str] = []
    coupes: list[str] = []
    for q in questions:
        if q["category"] not in ("calcul", "comparaison"):
            continue
        for nom_iv, iv in q["calculation"]["intermediate_values"].items():
            doc = _doc_depuis_evidence_doc(q["evidence_doc"])
            page = iv["evidence_page_physical"]
            chunks_page = chunks_par_doc_et_page.get(doc, {}).get(page, [])
            if not chunks_page:
                manquants.append(
                    f"{q['id']}.{nom_iv} : aucun chunk pour {doc} p.{page}"
                )
                continue
            # L'evidence_text d'un intermediate_value est en general une
            # ligne courte (ex. « Revenus 100 836 224 »), pas de « ... ».
            seg_n = _normaliser_tolerant_espaces_dans_nombres(iv["evidence_text"])
            if _localiser_segment(seg_n, chunks_page) is not None:
                continue
            if _coupe_entre_sous_morceaux(seg_n, chunks_page):
                coupes.append(
                    f"{q['id']}.{nom_iv} : coupe entre sous-morceaux de "
                    f"{doc} p.{page} : '{iv['evidence_text'][:60]}'"
                )
            else:
                manquants.append(
                    f"{q['id']}.{nom_iv} : absent de {doc} p.{page} : "
                    f"'{iv['evidence_text'][:60]}'"
                )
    rapport = manquants + coupes
    assert not rapport, "\n".join(["Couverture incomplete :"] + rapport)
