import io
import shutil
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"


class FakeUpload:
    """Imite un fichier chargé par Streamlit (name + getvalue)."""

    def __init__(self, path: Path):
        self._path = Path(path)
        self._bytes = self._path.read_bytes()
        self.name = self._path.name

    def getvalue(self) -> bytes:
        return self._bytes


def load(path):
    """Retourne un FakeUpload pour le fichier indiqué (relatif à tests/data)."""
    full = DATA_DIR / path if not Path(path).is_absolute() else Path(path)
    return FakeUpload(full)


def _tesseract_available() -> bool:
    # On délègue au détecteur de l'application pour que les tests OCR
    # trouvent Tesseract via les chemins d'installation standards, pas
    # seulement sur le PATH du processus.
    try:
        from bilanlens.extraction import ocr_available
        return ocr_available()
    except Exception:
        return False


TESSERACT_AVAILABLE = _tesseract_available()


def pytest_collection_modifyitems(config, items):
    """Skip les tests marqués 'ocr' si Tesseract n'est pas disponible."""
    if TESSERACT_AVAILABLE:
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
