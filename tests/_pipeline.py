"""Pipeline de test commun : charge un fichier → ratios + contrôles."""
from datetime import datetime

from bilanlens.extraction import extraire_document
from bilanlens.mapping import associer_candidats
from bilanlens.analysis import completer_valeurs_financieres, calculer_ratios
from bilanlens.consistency import verifier_bilan


def _vers_date(periode):
    try:
        return datetime.strptime(periode, "%d/%m/%Y").date()
    except Exception:
        return datetime.min.date()


def executer_pipeline(fichier_charge, periode_conservee="derniere"):
    """Extraction → mapping (sensible au rang) → ratios + contrôles.

    Retourne : (valeurs, ratios, controles, extra)
      - valeurs : postes complétés
      - ratios : dict cle → float ou None
      - controles : liste de contrôles de cohérence
      - extra : dict informatif (période choisie, ocr_utilise, candidats…)
    """
    extrait = extraire_document(fichier_charge)
    candidats = associer_candidats(
        extrait["texte"],
        enregistrements=extrait.get("enregistrements") or None,
    )

    periodes = {c["periode"] for c in candidats if c.get("periode")}
    periode_choisie = None
    if periodes:
        periode_choisie = max(periodes, key=_vers_date)
        if periode_conservee == "derniere":
            candidats = [
                c for c in candidats if c.get("periode") == periode_choisie
            ]

    valeurs = {}
    meilleur_rang = {}
    for c in candidats:
        cle = c.get("cle")
        if not cle:
            continue
        rang = c.get("rang", 0)
        if cle not in valeurs or rang > meilleur_rang[cle]:
            valeurs[cle] = c["valeur"]
            meilleur_rang[cle] = rang

    completees = completer_valeurs_financieres(valeurs)
    ratios = {r["cle"]: r["valeur"] for r in calculer_ratios(completees)}
    controles = verifier_bilan(completees)

    extra = {
        "periode": periode_choisie,
        "ocr_utilise": extrait.get("ocr_utilise", False),
        "candidats": candidats,
        "texte": extrait["texte"],
    }
    return completees, ratios, controles, extra
