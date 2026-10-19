"""Vérifie qu'un bilan de banque est signalé hors périmètre."""
from conftest import load
from _pipeline import run_pipeline
from bilanlens.sector import detect_out_of_scope_sector


def test_synthetic_bank_bilan_detected_as_bank():
    _values, _ratios, _checks, extra = run_pipeline(
        load("synth_bank_hors_perimetre.txt")
    )
    scope = detect_out_of_scope_sector(extra["text"])
    assert scope is not None, "Le bilan de banque n'a pas été détecté."
    assert scope["sector"] == "banque"
    # Au moins 2 indicateurs trouvés.
    assert len(scope["matches"]) >= 2


def test_industrial_synthetic_not_flagged():
    """Un bilan industriel (SOTUVER synthétique PCG) reste dans le périmètre."""
    _values, _ratios, _checks, extra = run_pipeline(load("synth_pcg_fr.txt"))
    assert detect_out_of_scope_sector(extra["text"]) is None
