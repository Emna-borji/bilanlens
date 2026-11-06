"""Tests unitaires de scripts/score.py.

Aucun appel reseau. Fonctions pures testees :
- parser_premier_nombre / parser_direction
- exact_numerique (format montant, pourcentage, variation, ratio)
- valeurs_dans_contexte
- rangs_pages_attendues, recall_at_k, mrr
- classer (7 classes exclusives)
- Lecture du fichier d'annotations manuelles (Q04/Q08).
"""
from __future__ import annotations

import json
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. Parsing numerique
# ---------------------------------------------------------------------------
def test_parser_premier_nombre_montant_francais():
    from scripts.score import parser_premier_nombre
    assert parser_premier_nombre("100 836 224 TND") == 100836224.0
    assert parser_premier_nombre("-44 790 355 TND") == -44790355.0
    assert parser_premier_nombre("732 621 822 dinars") == 732621822.0


def test_parser_premier_nombre_virgule_decimale():
    from scripts.score import parser_premier_nombre
    assert parser_premier_nombre("34,53 %") == 34.53
    assert parser_premier_nombre("99,81 %") == 99.81
    assert parser_premier_nombre("1 281 772 854,965 TND") == 1281772854.965


def test_parser_premier_nombre_variation():
    from scripts.score import parser_premier_nombre
    # Dans une variation, on prend le PREMIER nombre significatif
    # (la valeur de la variation, pas l'annee).
    v = parser_premier_nombre(
        "diminution de 24 287 937 TND entre 2023 et 2024"
    )
    assert v == 24287937.0


def test_parser_premier_nombre_aucun():
    from scripts.score import parser_premier_nombre
    assert parser_premier_nombre("donnee non disponible") is None
    assert parser_premier_nombre("") is None
    assert parser_premier_nombre(None) is None


def test_parser_direction():
    from scripts.score import parser_direction
    assert parser_direction("augmentation de 20 625 000 TND") == "augmentation"
    assert parser_direction("diminution de 24 287 937 TND") == "diminution"
    assert parser_direction("donnee non disponible") is None
    assert parser_direction("hausse de 5 %") == "augmentation"


# ---------------------------------------------------------------------------
# 2. exact_numerique
# ---------------------------------------------------------------------------
def test_exact_numerique_montant_dans_tolerance():
    from scripts.score import exact_numerique
    q = {"answer": {"value": 100836224, "format": "montant",
                    "tolerance_absolute": 1}}
    ok, detail = exact_numerique("100 836 224 TND", q)
    assert ok is True
    assert detail["diff_absolue"] == 0.0


def test_exact_numerique_montant_off_by_one_toleree():
    """Q24 : benchmark -63 485 069, modele -63 485 068 (diff=1).
    Avec tolerance par defaut = 1, c'est juste."""
    from scripts.score import exact_numerique
    q = {"answer": {"value_absolute": 63485069, "direction": "diminution",
                    "format": "variation"}}
    ok, detail = exact_numerique(
        "diminution de 63 485 068 TND entre 2023 et 2024", q
    )
    assert ok is True
    assert detail["diff_absolue"] == 1.0


def test_exact_numerique_variation_direction_fausse():
    from scripts.score import exact_numerique
    q = {"answer": {"value_absolute": 24287937, "direction": "diminution",
                    "format": "variation"}}
    ok, _ = exact_numerique(
        "augmentation de 24 287 937 TND", q
    )
    assert ok is False


def test_exact_numerique_pourcentage_hors_tolerance_q10():
    """Q10 : benchmark 13,03 %, modele 16,51 %, tol_pp = 0,1."""
    from scripts.score import exact_numerique
    q = {"answer": {"value": 13.03, "format": "pourcentage",
                    "tolerance_absolute_pp": 0.1}}
    ok, detail = exact_numerique("16,51 %", q)
    assert ok is False
    assert abs(detail["diff_absolue_pp"] - 3.48) < 0.001


def test_exact_numerique_pourcentage_dans_tolerance():
    """Q29 : benchmark 99,81 %, modele 99,81 %."""
    from scripts.score import exact_numerique
    q = {"answer": {"value": 99.81, "format": "pourcentage",
                    "tolerance_absolute_pp": 0.1}}
    ok, _ = exact_numerique("99,81 %", q)
    assert ok is True


def test_exact_numerique_ratio():
    from scripts.score import exact_numerique
    q = {"answer": {"value": 1.9, "format": "ratio",
                    "tolerance_absolute": 0.02}}
    ok, _ = exact_numerique("1,90", q)
    assert ok is True
    ok, _ = exact_numerique("2,15", q)
    assert ok is False


def test_exact_numerique_valeur_non_parsable():
    from scripts.score import exact_numerique
    q = {"answer": {"value": 100, "format": "montant"}}
    ok, _ = exact_numerique("donnee non disponible", q)
    assert ok is False


# ---------------------------------------------------------------------------
# 3. valeurs_dans_contexte (indicateur SEPARE du recall)
# ---------------------------------------------------------------------------
def test_valeurs_dans_contexte_calcul_presentes():
    """Les 2 valeurs numeriques sont dans la concatenation des
    textes chunks (chiffres contigus apres compression)."""
    from scripts.score import valeurs_dans_contexte
    q = {
        "category": "calcul",
        "calculation": {"intermediate_values": {
            "a": {"value": 44790355},
            "b": {"value": 388668436},
        }},
    }
    textes = [
        "Total des Actifs 388 668 436 241 664 543",
        "RESULTAT COMPTABLE APRES IMPOTS -44790355.285",
    ]
    assert valeurs_dans_contexte(q, textes) is True


def test_valeurs_dans_contexte_calcul_absente():
    from scripts.score import valeurs_dans_contexte
    q = {
        "category": "calcul",
        "calculation": {"intermediate_values": {
            "a": {"value": 44790355},
            "b": {"value": 388668436},
        }},
    }
    textes = ["Total des Actifs 388 668 436 241 664 543"]
    assert valeurs_dans_contexte(q, textes) is False


def test_valeurs_dans_contexte_none_pour_texte_annexes():
    from scripts.score import valeurs_dans_contexte
    q = {"category": "texte_annexes"}
    assert valeurs_dans_contexte(q, ["texte long sans chiffres"]) is None


def test_valeurs_dans_contexte_none_pour_sans_reponse():
    from scripts.score import valeurs_dans_contexte
    q = {"category": "sans_reponse"}
    assert valeurs_dans_contexte(q, ["texte"]) is None


def test_valeurs_dans_contexte_extraction_simple():
    from scripts.score import valeurs_dans_contexte
    q = {
        "category": "extraction",
        "answer": {"value": 100836224, "format": "montant"},
    }
    textes = ["Revenus (R.1) 100 836 224 165 986 659"]
    assert valeurs_dans_contexte(q, textes) is True


# ---------------------------------------------------------------------------
# 4. Recall + MRR
# ---------------------------------------------------------------------------
def _ret(pages: list[tuple[str, int]]) -> list[dict]:
    """Helper : liste [(doc, page)] -> format retrieved."""
    return [
        {"rank": i + 1, "doc": d, "page_physique": p}
        for i, (d, p) in enumerate(pages)
    ]


def test_rangs_pages_attendues_mix_trouve_et_absent():
    from scripts.score import rangs_pages_attendues
    pages_att = {("sotuver_2024", 4), ("sotuver_2024", 9)}
    top20 = _ret([("sotuver_2024", 3), ("sotuver_2024", 9),
                  ("sotuver_2024", 7)])
    rangs = rangs_pages_attendues(pages_att, top20)
    assert rangs["sotuver_2024@p9"] == 2
    assert rangs["sotuver_2024@p4"] is None


def test_recall_at_k_toutes_pages_requises():
    from scripts.score import recall_at_k
    # 2 pages attendues.
    pages_att = {("a", 4), ("a", 2)}
    # Top-5 : page 2 presente, page 4 absente -> recall KO.
    top5 = _ret([("a", 2), ("a", 3), ("a", 1), ("a", 52), ("a", 12)])
    assert recall_at_k(pages_att, top5) is False
    # Top-20 : page 4 a rang 6 -> recall OK a k=10, pas a k=5.
    top20 = _ret([("a", 2), ("a", 3), ("a", 1), ("a", 52), ("a", 12),
                  ("a", 4)] + [("b", i) for i in range(14)])
    assert recall_at_k(pages_att, top20[:5]) is False
    assert recall_at_k(pages_att, top20[:10]) is True


def test_mrr_premier_pertinent_rang_4():
    from scripts.score import mrr
    pages_att = {("a", 52)}
    top20 = _ret([("a", 2), ("a", 3), ("a", 1), ("a", 52)])
    assert mrr(pages_att, top20) == 0.25


def test_mrr_aucun_pertinent():
    from scripts.score import mrr
    pages_att = {("a", 99)}
    top20 = _ret([("a", 2), ("a", 3)])
    assert mrr(pages_att, top20) == 0.0


def test_mrr_pas_de_page_attendue():
    from scripts.score import mrr
    assert mrr(set(), _ret([("a", 1)])) is None


# ---------------------------------------------------------------------------
# 5. classer (7 classes exclusives)
# ---------------------------------------------------------------------------
def test_classer_juste():
    from scripts.score import classer
    q = {"category": "extraction"}
    assert classer(q, "100 836 224 TND", recall_ok=True, exact_ok=True) == "juste"


def test_classer_fausse_recall_ok_q10():
    """Q10 : reponse donnee, mauvaise, recall OK (page 3 au rang 1)."""
    from scripts.score import classer
    q = {"category": "calcul"}
    assert classer(q, "16,51 %", recall_ok=True, exact_ok=False) == "fausse_recall_ok"


def test_classer_fausse_recall_ko():
    from scripts.score import classer
    q = {"category": "extraction"}
    assert classer(q, "123 TND", recall_ok=False, exact_ok=False) == "fausse_recall_ko"


def test_classer_abstention_a_tort_recall_ok():
    """Q02 par exemple : abstention, mais page 3 bien retrouvee."""
    from scripts.score import classer
    q = {"category": "calcul"}
    assert classer(
        q, "donnee non disponible", recall_ok=True, exact_ok=False,
    ) == "abstention_a_tort_recall_ok"


def test_classer_abstention_a_tort_recall_ko():
    from scripts.score import classer
    q = {"category": "extraction"}
    assert classer(
        q, "donnee non disponible", recall_ok=False, exact_ok=False,
    ) == "abstention_a_tort_recall_ko"


def test_classer_abstention_correcte_sans_reponse():
    from scripts.score import classer
    q = {"category": "sans_reponse"}
    # recall None (pas de page attendue) ; exact_ok ignore pour sans_reponse.
    assert classer(
        q, "donnee non disponible", recall_ok=None, exact_ok=True,
    ) == "abstention_correcte"


def test_classer_reponse_a_tort_sur_sans_reponse():
    """Q sans_reponse mais le modele donne une valeur -> reponse_a_tort."""
    from scripts.score import classer
    q = {"category": "sans_reponse"}
    assert classer(
        q, "15 % du marche", recall_ok=None, exact_ok=False,
    ) == "reponse_a_tort"


def test_classes_exclusives():
    """Aucune reponse ne doit pouvoir tomber dans deux classes."""
    from scripts.score import CLASSES
    assert len(set(CLASSES)) == 7


# ---------------------------------------------------------------------------
# 6. Lecture annotations manuelles (Q04/Q08 du fichier reel)
# ---------------------------------------------------------------------------
def test_charger_annotations_filtre_par_run_id():
    """Le fichier annotations_texte.jsonl supporte plusieurs runs ;
    `charger_annotations(run_id)` filtre strictement."""
    from scripts.score import (RUN_ID_B0_LIBRE, RUN_ID_V1,
                                  charger_annotations)

    ann_v1 = charger_annotations(run_id=RUN_ID_V1)
    assert "sotuver_2024_04" in ann_v1
    assert "sotuver_2024_08" in ann_v1
    q04_v1 = ann_v1["sotuver_2024_04"]
    assert q04_v1["statut"] == "juste"
    assert q04_v1["complete"] is False
    q08_v1 = ann_v1["sotuver_2024_08"]
    assert q08_v1["statut"] == "juste"
    assert q08_v1["complete"] is True

    ann_libre = charger_annotations(run_id=RUN_ID_B0_LIBRE)
    # B0-libre : Q04 = fausse, Q08 = juste complete, Q21 = fausse
    assert ann_libre["sotuver_2024_04"]["statut"] == "fausse"
    assert ann_libre["sotuver_2024_08"]["statut"] == "juste"
    assert ann_libre["sotuver_2024_08"]["complete"] is True
    assert ann_libre["sfbt_2024_21"]["statut"] == "fausse"


def test_charger_annotations_sans_run_id_retourne_toutes():
    """Sans run_id : derniere entree par question_id (comportement
    "global" pour les comptages)."""
    from scripts.score import charger_annotations
    ann = charger_annotations()
    # Au moins les Q04 et Q08 ; Q21 B0-libre.
    assert "sotuver_2024_04" in ann
    assert "sfbt_2024_21" in ann


# ---------------------------------------------------------------------------
# 6.bis. Detecteur d'abstention large (pseudo-abstention + filtrage chiffre)
# ---------------------------------------------------------------------------
def test_est_abstention_canonique():
    """Forme canonique 'donnee non disponible' (B0-strict, V1)."""
    from scripts.score import est_abstention
    assert est_abstention("donnee non disponible") is True


def test_est_abstention_reformulation_sans_chiffre():
    """Pseudo-abstention B0-libre : 'n'est pas disponible' + aucun
    chiffre significatif -> abstention."""
    from scripts.score import est_abstention
    assert est_abstention(
        "La capacite normale de production n'est pas precisee dans le rapport"
    ) is True
    assert est_abstention(
        "Les informations ne sont pas disponibles dans le rapport"
    ) is True


def test_est_abstention_rejet_si_chiffre_significatif():
    """Un refus partiel qui contient un chiffre significatif n'est
    PAS une abstention : c'est une reponse chiffree (potentiellement
    fausse, mais a scorer sur sa valeur, pas en abstention)."""
    from scripts.score import est_abstention
    assert est_abstention(
        "Le CA est de 100 836 224 TND, le detail n'est pas disponible"
    ) is False


def test_est_abstention_vide():
    from scripts.score import est_abstention
    assert est_abstention("") is True
    assert est_abstention(None) is True


# ---------------------------------------------------------------------------
# 7. Classifier B0 (5 classes exclusives, sans suffixe recall)
# ---------------------------------------------------------------------------
def test_classer_b0_juste():
    from scripts.score import classer_b0
    q = {"category": "extraction"}
    assert classer_b0(q, "100 836 224 TND", exact_ok=True) == "juste"


def test_classer_b0_fausse():
    from scripts.score import classer_b0
    q = {"category": "calcul"}
    assert classer_b0(q, "99,9 %", exact_ok=False) == "fausse"


def test_classer_b0_abstention_a_tort_sans_suffixe():
    """B0 : pas de suffixe recall."""
    from scripts.score import classer_b0
    q = {"category": "extraction"}
    assert classer_b0(
        q, "donnee non disponible", exact_ok=False,
    ) == "abstention_a_tort"


def test_classer_b0_pseudo_abstention_a_tort():
    """Une pseudo-abstention B0-libre (sans chiffre) est aussi une
    abstention_a_tort."""
    from scripts.score import classer_b0
    q = {"category": "texte_annexes"}
    assert classer_b0(
        q, "L'information n'est pas disponible dans le rapport",
        exact_ok=False,
    ) == "abstention_a_tort"


def test_classer_b0_abstention_correcte_sans_reponse():
    from scripts.score import classer_b0
    q = {"category": "sans_reponse"}
    assert classer_b0(
        q, "donnee non disponible", exact_ok=True,
    ) == "abstention_correcte"


def test_classer_b0_reponse_a_tort_sur_sans_reponse():
    from scripts.score import classer_b0
    q = {"category": "sans_reponse"}
    assert classer_b0(
        q, "15 % du marche tunisien", exact_ok=False,
    ) == "reponse_a_tort"


def test_classes_b0_exclusives():
    from scripts.score import CLASSES_B0
    assert len(set(CLASSES_B0)) == 5


# ---------------------------------------------------------------------------
# 7.bis. diagnostiquer_v1 : separation des echecs V1
# ---------------------------------------------------------------------------
def _score(qid, classe, vdc=None, recall5=None):
    """Minimal pour `diagnostiquer_v1` : juste les champs utilises."""
    return {
        "question_id": qid,
        "classe": classe,
        "valeurs_dans_contexte": vdc,
        "recall": {"recall_at_5": recall5},
    }


def test_diagnostiquer_v1_separe_recherche_et_prompt():
    """Les abstentions a tort se separent selon valeurs_dans_contexte,
    peu importe recall@5 (Q23 : recall KO + vdc True -> abstention
    avec valeurs, pas probleme de recherche)."""
    from scripts.score import diagnostiquer_v1

    scores = [
        # 4 abstentions avec vdc True (recall OK ou KO : meme bucket).
        _score("Q02", "abstention_a_tort_recall_ok", vdc=True, recall5=True),
        _score("Q06", "abstention_a_tort_recall_ok", vdc=True, recall5=True),
        _score("Q14", "abstention_a_tort_recall_ok", vdc=True, recall5=True),
        _score("Q19", "abstention_a_tort_recall_ok", vdc=True, recall5=True),
        _score("Q23", "abstention_a_tort_recall_ko", vdc=True, recall5=False),
        _score("Q28", "abstention_a_tort_recall_ko", vdc=True, recall5=False),
        # 4 problemes de recherche (abstention + vdc != True).
        _score("Q12", "abstention_a_tort_recall_ko", vdc=None, recall5=False),
        _score("Q21", "abstention_a_tort_recall_ko", vdc=None, recall5=False),
        _score("Q25", "abstention_a_tort_recall_ko", vdc=None, recall5=False),
        _score("Q30", "abstention_a_tort_recall_ko", vdc=False, recall5=False),
        # 1 fausse (Q10).
        _score("Q10", "fausse_recall_ok", vdc=True, recall5=True),
        # 2 justes malgre recall KO (Q07, Q20).
        _score("Q07", "juste", vdc=True, recall5=False),
        _score("Q20", "juste", vdc=True, recall5=False),
        # Justes "normaux" (recall OK) : ne doivent apparaitre nulle part.
        _score("Q01", "juste", vdc=True, recall5=True),
    ]

    diag = diagnostiquer_v1(scores)
    assert sorted(diag["problemes_recherche"]) == ["Q12", "Q21", "Q25", "Q30"]
    assert sorted(diag["abstentions_avec_valeurs"]) == [
        "Q02", "Q06", "Q14", "Q19", "Q23", "Q28",
    ]
    assert sorted(diag["fausses"]) == ["Q10"]
    assert sorted(diag["juste_malgre_recall_ko"]) == ["Q07", "Q20"]
    # nb_echecs = 4 recherche + 6 abstentions-valeurs + 1 fausse = 11.
    assert diag["nb_echecs"] == 11


def test_diagnostiquer_v1_juste_malgre_recall_ko_hors_echecs():
    """`juste_malgre_recall_ko` n'est PAS un echec, donc pas compte
    dans `nb_echecs`."""
    from scripts.score import diagnostiquer_v1

    scores = [
        _score("Q07", "juste", vdc=True, recall5=False),
        _score("Q20", "juste", vdc=True, recall5=False),
    ]
    diag = diagnostiquer_v1(scores)
    assert diag["juste_malgre_recall_ko"] == ["Q07", "Q20"]
    assert diag["nb_echecs"] == 0


# ---------------------------------------------------------------------------
# 7.ter. Reconstruction du contexte V1 depuis les chunk_ids
# ---------------------------------------------------------------------------
def test_charger_chunks_locaux_retourne_tous_les_chunks_connus():
    """`charger_chunks_locaux` lit tous les .jsonl de data/chunks/
    et renvoie {chunk_id: texte} avec la convention
    `<doc>_p<page>_s<sous>`."""
    from scripts.score import charger_chunks_locaux

    chunks = charger_chunks_locaux()
    # Au moins 6 corpus x ~30 pages = plusieurs centaines de chunks.
    assert len(chunks) > 100
    # Un chunk connu (la page 1 de sotuver_2024).
    assert "sotuver_2024_p1_s0" in chunks
    assert chunks["sotuver_2024_p1_s0"]  # non vide


def test_reconstruire_contexte_v1_identique_a_v1_sur_question_connue():
    """Pour une Q du run V1 enregistre, le contexte reconstruit a
    EXACTEMENT la meme longueur en caracteres que
    `context_rendered_chars` V1. Verifie aussi l'ordre des entetes."""
    import json
    from pathlib import Path

    from scripts.score import (RUN_ID_V1, charger_chunks_locaux,
                                  reconstruire_contexte_v1)

    racine = Path(__file__).resolve().parent.parent
    rec = None
    for ligne in open(racine / "results" / "v1.jsonl", encoding="utf-8"):
        r = json.loads(ligne)
        if (r.get("run_id") == RUN_ID_V1
                and r["question_id"] == "sotuver_2024_01"):
            rec = r
            break
    assert rec is not None

    chunks = charger_chunks_locaux()
    ctx = reconstruire_contexte_v1(rec, chunks)
    assert len(ctx) == rec["context_rendered_chars"]
    # Ordre des 5 extraits respecte le rang V1.
    positions = [
        ctx.index(f"=== Extrait {k} :") for k in range(1, 6)
    ]
    assert positions == sorted(positions)
    # Le header du top-1 porte doc + page du retrieved[0].
    first = rec["retrieved"][0]
    assert (f"=== Extrait 1 : {first['doc']}, "
             f"page {first['page_physique']} ===") in ctx


def test_reconstruire_contexte_v1_toutes_les_31_q():
    """Invariant global : pour les 31 Q du run V1, le contexte
    reconstruit a la meme longueur que `context_rendered_chars`
    V1. Un seul ecart = chunk manquant ou convention cassee."""
    import json
    from pathlib import Path

    from scripts.score import (RUN_ID_V1, charger_chunks_locaux,
                                  reconstruire_contexte_v1)

    racine = Path(__file__).resolve().parent.parent
    chunks = charger_chunks_locaux()
    ecarts = []
    total = 0
    for ligne in open(racine / "results" / "v1.jsonl", encoding="utf-8"):
        r = json.loads(ligne)
        if r.get("run_id") != RUN_ID_V1:
            continue
        total += 1
        ctx = reconstruire_contexte_v1(r, chunks)
        if len(ctx) != r["context_rendered_chars"]:
            ecarts.append((r["question_id"], r["context_rendered_chars"],
                            len(ctx)))
    assert total == 31
    assert ecarts == [], f"Ecarts de reconstruction : {ecarts}"


def test_reconstruire_contexte_v1_sans_chroma_ni_api(monkeypatch):
    """Garde-fou : la reconstruction ne doit PAS importer chromadb
    ni appeler charger_encodeur / produire_top20. On patche ces
    symboles pour exploser si quelqu'un les appelle."""
    import json
    from pathlib import Path

    from scripts import score as score_module

    def _boom(*a, **k):
        raise AssertionError("Chroma / API embeddings appele pendant "
                               "la reconstruction : interdit")

    monkeypatch.setattr(score_module, "ouvrir_collection", _boom,
                          raising=False)
    monkeypatch.setattr(score_module, "charger_encodeur", _boom,
                          raising=False)
    monkeypatch.setattr(score_module, "produire_top20", _boom,
                          raising=False)

    racine = Path(__file__).resolve().parent.parent
    rec = None
    for ligne in open(racine / "results" / "v1.jsonl", encoding="utf-8"):
        r = json.loads(ligne)
        if (r.get("run_id") == score_module.RUN_ID_V1
                and r["question_id"] == "sotuver_2024_01"):
            rec = r
            break
    chunks = score_module.charger_chunks_locaux()
    ctx = score_module.reconstruire_contexte_v1(rec, chunks)
    assert len(ctx) == rec["context_rendered_chars"]


def test_diagnostiquer_v1_fichier_reel():
    """Verifie que sur le run V1 enregistre, le diagnostic donne
    exactement 4+6+1 = 11 echecs + 2 juste_malgre_recall_ko."""
    import json
    from pathlib import Path

    from scripts.score import RUN_ID_V1, diagnostiquer_v1

    racine = Path(__file__).resolve().parent.parent
    scores = []
    for l in open(racine / "results" / "scores_compare.jsonl",
                   encoding="utf-8"):
        rec = json.loads(l)
        if rec.get("provenance") == "v1" and rec.get("run_id") == RUN_ID_V1:
            scores.append(rec)
    assert len(scores) == 31

    diag = diagnostiquer_v1(scores)
    assert sorted(diag["problemes_recherche"]) == sorted([
        "monoprix_consolide_2024_12", "sfbt_2024_21",
        "ciments_bizerte_2024_25", "delice_holding_2024_30",
    ])
    assert sorted(diag["abstentions_avec_valeurs"]) == sorted([
        "sotuver_2024_02", "sotuver_2024_06",
        "monoprix_2024_14", "sfbt_2024_19",
        "ciments_bizerte_2024_23", "delice_holding_2024_28",
    ])
    assert sorted(diag["fausses"]) == ["monoprix_consolide_2024_10"]
    assert sorted(diag["juste_malgre_recall_ko"]) == sorted([
        "sotuver_2024_07", "sfbt_2024_20",
    ])
    assert diag["nb_echecs"] == 11


# ---------------------------------------------------------------------------
# 7. Integration scorer_question avec annotations
# ---------------------------------------------------------------------------
def test_scorer_question_texte_annexes_annotation_juste_incomplete(tmp_path):
    """Un Q04-like : texte_annexes, reponse donnee, annotation manuelle
    'juste' + 'complete=false' -> classe = juste, exact_ok=True,
    complete=False, mode_annotation=manuel."""
    from scripts.score import scorer_question

    q = {
        "id": "qx", "category": "texte_annexes",
        "evidence_doc": "real_sotuver_2024.pdf",
        "evidence_page_physical": 9,
        "answer": {"value": "x", "format": "texte"},
    }
    record_v1 = {
        "retrieved": [
            {"rank": 1, "chunk_id": "sotuver_2024_p9_s0", "doc": "sotuver_2024",
             "page_physique": 9},
        ],
        "answer_parsed": {"answer": "reponse approximative"},
    }
    top20 = [
        {"rank": 1, "chunk_id": "sotuver_2024_p9_s0", "doc": "sotuver_2024",
         "page_physique": 9},
    ]
    annotations = {"qx": {"question_id": "qx", "statut": "juste",
                           "complete": False,
                           "elements_manquants": ["X"],
                           "justification": "ok"}}
    score = scorer_question(q, record_v1, top20, ["texte chunk 9"], annotations)
    assert score["classe"] == "juste"
    assert score["exact_ok"] is True
    assert score["complete"] is False
    assert score["mode_annotation"] == "manuel"
    assert score["recall"]["recall_at_5"] is True
    # valeurs_dans_contexte doit etre None pour texte_annexes.
    assert score["valeurs_dans_contexte"] is None


def test_scorer_question_q10_hallucinee():
    """Simule Q10 : page 3 au rang 1, modele 16,51 %, benchmark 13,03 %."""
    from scripts.score import scorer_question

    q = {
        "id": "q10", "category": "calcul",
        "evidence_doc": "real_monoprix_consolide_2024.pdf",
        "evidence_page_physical": 3,
        "answer": {"value": 13.03, "format": "pourcentage",
                   "tolerance_absolute_pp": 0.1},
        "calculation": {"intermediate_values": {
            "cp": {"value": 49423396, "evidence_page_physical": 3},
            "tot": {"value": 379260923, "evidence_page_physical": 3},
        }},
    }
    record_v1 = {
        "retrieved": [{"rank": 1, "chunk_id": "monoprix_consolide_2024_p3_s0",
                       "doc": "monoprix_consolide_2024", "page_physique": 3}],
        "answer_parsed": {"answer": "16,51 %"},
    }
    top20 = [{"rank": 1, "chunk_id": "monoprix_consolide_2024_p3_s0",
              "doc": "monoprix_consolide_2024", "page_physique": 3}]
    textes = ["TOTAL CAPITAUX PROPRES CONSOLIDES 49 423 396 ... "
              "TOTAL DE CAPITAUX PROPRES ET PASSIFS 379 260 923"]
    score = scorer_question(q, record_v1, top20, textes, {})
    assert score["classe"] == "fausse_recall_ok"
    assert score["exact_ok"] is False
    assert score["recall"]["recall_at_5"] is True
    assert score["valeurs_dans_contexte"] is True
    assert score["mode_annotation"] == "automatique"


def test_scorer_question_sans_reponse_abstention_correcte():
    from scripts.score import scorer_question
    q = {"id": "q5", "category": "sans_reponse",
         "evidence_doc": "real_sotuver_2024.pdf",
         "evidence_page_physical": None, "answer": None}
    record_v1 = {"retrieved": [], "answer_parsed": {"answer": "donnee non disponible"}}
    score = scorer_question(q, record_v1, [], [], {})
    assert score["classe"] == "abstention_correcte"
    assert score["pages_attendues"] == []
    # Recall @k : None pour sans_reponse.
    assert score["recall"]["recall_at_5"] is None
    assert score["valeurs_dans_contexte"] is None
