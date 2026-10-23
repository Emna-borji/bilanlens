"""Vérifie qu'un bilan de banque est signalé hors périmètre."""
from conftest import charger
from _pipeline import executer_pipeline
from bilanlens.sector import detecter_secteur_hors_perimetre


def test_bilan_banque_synthetique_detecte_comme_banque():
    _valeurs, _ratios, _controles, extra = executer_pipeline(
        charger("synth_bank_hors_perimetre.txt")
    )
    perimetre = detecter_secteur_hors_perimetre(extra["texte"])
    assert perimetre is not None, "Le bilan de banque n'a pas été détecté."
    assert perimetre["secteur"] == "banque"
    # Au moins 2 indicateurs trouvés.
    assert len(perimetre["correspondances"]) >= 2


def test_bilan_industriel_synthetique_non_signale():
    """Un bilan industriel (SOTUVER synthétique PCG) reste dans le périmètre."""
    _valeurs, _ratios, _controles, extra = executer_pipeline(
        charger("synth_pcg_fr.txt")
    )
    assert detecter_secteur_hors_perimetre(extra["texte"]) is None
