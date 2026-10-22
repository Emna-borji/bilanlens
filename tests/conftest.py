import io
import shutil
from pathlib import Path

import pytest

REPERTOIRE_DONNEES = Path(__file__).parent / "data"


class FauxFichierCharge:
    """Imite un fichier chargé par Streamlit (name + getvalue)."""

    def __init__(self, chemin: Path):
        self._chemin = Path(chemin)
        self._octets = self._chemin.read_bytes()
        self.name = self._chemin.name

    def getvalue(self) -> bytes:
        return self._octets


def charger(chemin):
    """Retourne un FauxFichierCharge pour le fichier indiqué (relatif à tests/data)."""
    complet = REPERTOIRE_DONNEES / chemin if not Path(chemin).is_absolute() else Path(chemin)
    return FauxFichierCharge(complet)


def _tesseract_disponible() -> bool:
    # On délègue au détecteur de l'application pour que les tests OCR
    # trouvent Tesseract via les chemins d'installation standards, pas
    # seulement sur le PATH du processus.
    try:
        from bilanlens.extraction import ocr_disponible
        return ocr_disponible()
    except Exception:
        return False


TESSERACT_DISPONIBLE = _tesseract_disponible()


def pytest_collection_modifyitems(config, items):
    """Skip les tests marqués 'ocr' si Tesseract n'est pas disponible."""
    if TESSERACT_DISPONIBLE:
        return
    skip_ocr = pytest.mark.skip(reason="Tesseract OCR non disponible")
    for item in items:
        if "ocr" in item.keywords:
            item.add_marker(skip_ocr)


def pytest_configure(config):
    config.addinivalue_line("markers", "ocr: test nécessitant Tesseract OCR")
    config.addinivalue_line(
        "markers",
        "real: test utilisant un bilan réel publié (bvmt.com.tn ou équivalent)",
    )
