"""Tests de ``bilanlens.reranker`` sans réseau.

Aucun test n'instancie le vrai modèle `BAAI/bge-reranker-v2-m3`
(≈ 1.1 GB). Le vrai `Reranker` est exercé uniquement dans le
benchmark local (``scripts/benchmark_rerank.py``).

Ici on vérifie :
- Les constantes figées (nom, revision, licence, max_length) ;
- L'API ``reranker_top_k`` avec un scorer mock (fonction simple
  ou classe compatible avec le Protocol ``Scorer``) ;
- Le tri par score décroissant et le tie-break ``chunk_id``
  alphanumérique croissant ;
- L'erreur claire quand un chunk_id du top-20 est absent de
  ``chunks_par_id`` (KeyError) ;
- Le garde-fou ``LongueurExcedenteError`` est exposé.
"""
from __future__ import annotations

import pytest

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from bilanlens.reranker import (
    BATCH_SIZE_DEFAULT,
    LongueurExcedenteError,
    MAX_LENGTH,
    MODEL_LICENSE,
    MODEL_NAME,
    MODEL_REVISION,
    Reranker,
    RevisionMismatchError,
    _extract_commit_hash,
    _scores_par_lots,
    _valider_revision_chargee,
    reranker_top_k,
)


# ------------------------------------------------------------------
# Constantes figées (plan V3 §1 et §8)
# ------------------------------------------------------------------

def test_model_name_est_bge_reranker_v2_m3():
    assert MODEL_NAME == "BAAI/bge-reranker-v2-m3"


def test_model_revision_est_une_revision_sha_hex_de_40_caracteres():
    assert len(MODEL_REVISION) == 40
    int(MODEL_REVISION, 16)  # doit être un entier hex valide


def test_model_revision_exact():
    """Pin la revision EXACTE du commit HF téléchargé 2026-11-07."""
    assert (
        MODEL_REVISION == "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
    )


def test_model_license_apache_2_0():
    assert MODEL_LICENSE == "apache-2.0"


def test_max_length_est_8192_contexte_natif():
    """bge-reranker-v2-m3 : contexte natif 8192 tokens. Nous
    appliquons la même limite applicative pour éviter la
    troncation silencieuse en fin de page."""
    assert MAX_LENGTH == 8192


# ------------------------------------------------------------------
# API reranker_top_k — scorer mock
# ------------------------------------------------------------------

@pytest.fixture
def chunks_fake():
    return {
        "a_p1_s0": {"texte": "stocks de la société SOTUVER"},
        "a_p2_s0": {"texte": "immobilisations corporelles brutes"},
        "b_p1_s0": {"texte": "placements et autres actifs"},
        "c_p1_s0": {"texte": "capitaux propres SFBT"},
        "d_p1_s0": {"texte": "autres chunks sans valeur"},
    }


def _scorer_depuis_dict(scores: dict[str, float]):
    """Construit une fonction scorer qui lit les scores dans un
    dict chunk_id→score. L'ordre de sortie respecte l'ordre
    d'entrée (comme le vrai Reranker.score_pairs)."""
    def _scorer(pairs):
        # Pas d'accès au chunk_id ici, on se repose sur le fait que
        # le test connaît l'ordre des pairs et retourne un score fixe
        # par position. Ce helper n'est pas utilisé si on utilise
        # un callable qui suit l'ordre des candidats ; on lit via
        # (question, chunk_texte) et on rapproche avec un dict
        # chunk_texte → score fourni.
        raise NotImplementedError
    return _scorer


def test_reranker_top_k_tri_par_score_decroissant(chunks_fake):
    # Candidats en entrée ordonnés par rank V2 (1..5)
    candidats = [
        {"rank": 1, "chunk_id": "a_p1_s0", "doc": "a",
         "page_physique": 1, "sous_numero": 0},
        {"rank": 2, "chunk_id": "b_p1_s0", "doc": "b",
         "page_physique": 1, "sous_numero": 0},
        {"rank": 3, "chunk_id": "c_p1_s0", "doc": "c",
         "page_physique": 1, "sous_numero": 0},
    ]
    # Scorer mock : renvoie des scores qui inversent l'ordre
    def scorer(pairs):
        return [0.1, 0.9, 0.5]
    out = reranker_top_k(
        "une question", candidats, chunks_fake, scorer, top_final=3,
    )
    # b (score 0.9) > c (0.5) > a (0.1)
    assert [r["chunk_id"] for r in out] == [
        "b_p1_s0", "c_p1_s0", "a_p1_s0",
    ]
    assert [r["rank"] for r in out] == [1, 2, 3]
    assert out[0]["score_rerank"] == pytest.approx(0.9)


def test_reranker_top_k_tie_break_chunk_id_croissant(chunks_fake):
    candidats = [
        {"rank": 1, "chunk_id": "c_p1_s0", "doc": "c",
         "page_physique": 1, "sous_numero": 0},
        {"rank": 2, "chunk_id": "a_p1_s0", "doc": "a",
         "page_physique": 1, "sous_numero": 0},
        {"rank": 3, "chunk_id": "b_p1_s0", "doc": "b",
         "page_physique": 1, "sous_numero": 0},
    ]
    # Tous les scores égaux → tie-break par chunk_id
    def scorer(pairs):
        return [0.5, 0.5, 0.5]
    out = reranker_top_k(
        "q", candidats, chunks_fake, scorer, top_final=3,
    )
    assert [r["chunk_id"] for r in out] == [
        "a_p1_s0", "b_p1_s0", "c_p1_s0",
    ]


def test_reranker_top_k_limite_top_final(chunks_fake):
    candidats = [
        {"rank": i, "chunk_id": f"d_p{i}_s0"
         if i == 5 else ["a_p1_s0", "b_p1_s0", "c_p1_s0",
                          "d_p1_s0"][i - 1],
         "doc": "x", "page_physique": i, "sous_numero": 0}
        for i in range(1, 5)
    ]
    candidats = [
        {"rank": 1, "chunk_id": "a_p1_s0", "doc": "a",
         "page_physique": 1, "sous_numero": 0},
        {"rank": 2, "chunk_id": "b_p1_s0", "doc": "b",
         "page_physique": 1, "sous_numero": 0},
        {"rank": 3, "chunk_id": "c_p1_s0", "doc": "c",
         "page_physique": 1, "sous_numero": 0},
        {"rank": 4, "chunk_id": "d_p1_s0", "doc": "d",
         "page_physique": 1, "sous_numero": 0},
    ]

    def scorer(pairs):
        return [0.4, 0.8, 0.6, 0.2]
    out = reranker_top_k(
        "q", candidats, chunks_fake, scorer, top_final=2,
    )
    assert len(out) == 2
    assert [r["chunk_id"] for r in out] == ["b_p1_s0", "c_p1_s0"]


def test_reranker_top_k_conserve_doc_et_page(chunks_fake):
    candidats = [
        {"rank": 1, "chunk_id": "a_p1_s0", "doc": "sotuver_2024",
         "page_physique": 4, "sous_numero": 0},
    ]
    def scorer(pairs):
        return [0.9]
    out = reranker_top_k(
        "q", candidats, chunks_fake, scorer, top_final=1,
    )
    assert out[0]["doc"] == "sotuver_2024"
    assert out[0]["page_physique"] == 4
    assert out[0]["sous_numero"] == 0


def test_reranker_top_k_accepte_un_scorer_classe_avec_score_pairs(
    chunks_fake,
):
    """Vérifie que l'API accepte aussi une instance avec
    `score_pairs` (comme le vrai `Reranker`), pas seulement un
    callable fonctionnel."""

    class ScorerMock:
        def score_pairs(self, pairs):
            return [1.0 / (i + 1) for i in range(len(pairs))]

    candidats = [
        {"rank": 1, "chunk_id": "a_p1_s0", "doc": "a",
         "page_physique": 1, "sous_numero": 0},
        {"rank": 2, "chunk_id": "b_p1_s0", "doc": "b",
         "page_physique": 1, "sous_numero": 0},
        {"rank": 3, "chunk_id": "c_p1_s0", "doc": "c",
         "page_physique": 1, "sous_numero": 0},
    ]
    out = reranker_top_k(
        "q", candidats, chunks_fake, ScorerMock(), top_final=3,
    )
    # Scores 1.0, 0.5, 0.33 → ordre original préservé.
    assert [r["chunk_id"] for r in out] == [
        "a_p1_s0", "b_p1_s0", "c_p1_s0",
    ]


def test_reranker_top_k_liste_vide():
    out = reranker_top_k(
        "q", [], {}, lambda pairs: [], top_final=5,
    )
    assert out == []


def test_reranker_top_k_erreur_si_scorer_renvoie_mauvais_nombre(
    chunks_fake,
):
    candidats = [
        {"rank": 1, "chunk_id": "a_p1_s0", "doc": "a",
         "page_physique": 1, "sous_numero": 0},
        {"rank": 2, "chunk_id": "b_p1_s0", "doc": "b",
         "page_physique": 1, "sous_numero": 0},
    ]
    def scorer_defectueux(pairs):
        return [0.9]  # devrait retourner 2 scores
    with pytest.raises(ValueError):
        reranker_top_k(
            "q", candidats, chunks_fake, scorer_defectueux,
            top_final=2,
        )


def test_reranker_top_k_erreur_si_chunk_id_absent(chunks_fake):
    candidats = [
        {"rank": 1, "chunk_id": "chunk_inexistant", "doc": "x",
         "page_physique": 1, "sous_numero": 0},
    ]
    with pytest.raises(KeyError):
        reranker_top_k(
            "q", candidats, chunks_fake, lambda p: [0.5],
            top_final=1,
        )


# ------------------------------------------------------------------
# Erreurs exposées
# ------------------------------------------------------------------

def test_longueur_excedente_error_est_une_classe():
    """Garde-fou : exporté pour permettre aux callers de
    l'attraper spécifiquement."""
    assert issubclass(LongueurExcedenteError, Exception)


# ------------------------------------------------------------------
# _extract_commit_hash — source du SHA selon l'API transformers
# ------------------------------------------------------------------

def test_extract_commit_hash_depuis_attribut_direct():
    obj = SimpleNamespace(_commit_hash=MODEL_REVISION)
    assert _extract_commit_hash(obj) == MODEL_REVISION


def test_extract_commit_hash_depuis_config():
    obj = SimpleNamespace(
        config=SimpleNamespace(_commit_hash=MODEL_REVISION),
    )
    assert _extract_commit_hash(obj) == MODEL_REVISION


def test_extract_commit_hash_depuis_vocab_file_path_windows():
    # Format réel observé dans le cache HuggingFace Windows
    path = (
        r"C:\Users\x\.cache\huggingface\hub"
        rf"\models--BAAI--bge-reranker-v2-m3\snapshots\{MODEL_REVISION}"
        r"\sentencepiece.bpe.model"
    )
    obj = SimpleNamespace(init_kwargs={"vocab_file": path})
    assert _extract_commit_hash(obj) == MODEL_REVISION


def test_extract_commit_hash_depuis_vocab_file_path_posix():
    path = (
        f"/home/x/.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3"
        f"/snapshots/{MODEL_REVISION}/sentencepiece.bpe.model"
    )
    obj = SimpleNamespace(init_kwargs={"vocab_file": path})
    assert _extract_commit_hash(obj) == MODEL_REVISION


def test_extract_commit_hash_retourne_none_si_aucune_source():
    obj = SimpleNamespace()
    assert _extract_commit_hash(obj) is None


def test_extract_commit_hash_retourne_none_si_hash_vide():
    obj = SimpleNamespace(
        _commit_hash="",
        config=SimpleNamespace(_commit_hash=None),
        init_kwargs={},
    )
    assert _extract_commit_hash(obj) is None


# ------------------------------------------------------------------
# _valider_revision_chargee — fail-fast anti-dérive
# ------------------------------------------------------------------

def test_valider_revision_leve_si_revision_vide():
    obj = SimpleNamespace(_commit_hash=MODEL_REVISION)
    with pytest.raises(RevisionMismatchError, match="SHA non vide"):
        _valider_revision_chargee("", obj, obj)
    with pytest.raises(RevisionMismatchError, match="SHA non vide"):
        _valider_revision_chargee(None, obj, obj)


def test_valider_revision_leve_si_aucun_hash_resoluble():
    """Si ni le tokenizer ni le modèle n'exposent de hash, refus
    de passer silencieusement."""
    tokenizer = SimpleNamespace()  # aucun attribut
    model = SimpleNamespace()
    with pytest.raises(
        RevisionMismatchError, match="Aucun commit hash",
    ):
        _valider_revision_chargee(MODEL_REVISION, tokenizer, model)


def test_valider_revision_leve_si_tokenizer_hash_differe():
    mauvais = "0" * 40
    tokenizer = SimpleNamespace(_commit_hash=mauvais)
    model = SimpleNamespace(_commit_hash=MODEL_REVISION)
    with pytest.raises(
        RevisionMismatchError, match="tokenizer",
    ):
        _valider_revision_chargee(MODEL_REVISION, tokenizer, model)


def test_valider_revision_leve_si_model_hash_differe():
    mauvais = "0" * 40
    tokenizer = SimpleNamespace(_commit_hash=MODEL_REVISION)
    model = SimpleNamespace(_commit_hash=mauvais)
    with pytest.raises(RevisionMismatchError, match="model"):
        _valider_revision_chargee(MODEL_REVISION, tokenizer, model)


def test_valider_revision_ok_quand_les_deux_hashes_concordent():
    tokenizer = SimpleNamespace(_commit_hash=MODEL_REVISION)
    model = SimpleNamespace(_commit_hash=MODEL_REVISION)
    # Ne doit PAS lever.
    _valider_revision_chargee(MODEL_REVISION, tokenizer, model)


def test_valider_revision_ok_si_un_seul_hash_resolu_et_concorde():
    """Au moins l'un des deux suffit pour valider."""
    tokenizer = SimpleNamespace(_commit_hash=MODEL_REVISION)
    model = SimpleNamespace()  # pas de hash sur le modèle
    _valider_revision_chargee(MODEL_REVISION, tokenizer, model)


# ------------------------------------------------------------------
# Reranker (intégration) : validation effective de la revision
# ------------------------------------------------------------------

@pytest.fixture
def torch_mock(monkeypatch):
    """Injecte un faux ``torch`` dans sys.modules pour que
    ``import torch`` dans ``Reranker.__init__`` ne nécessite pas
    torch réellement installé. ``torch.cuda.is_available()``
    retourne False, device = "cpu"."""
    mock = MagicMock()
    mock.cuda.is_available.return_value = False
    monkeypatch.setitem(sys.modules, "torch", mock)
    return mock


def test_reranker_leve_si_revision_vide_sans_dependances():
    """Refus avant tout import lourd : la validation précède
    ``from transformers import`` et ``import torch``. Donc ce
    test passe même sans torch/transformers installés."""
    with pytest.raises(
        RevisionMismatchError, match="SHA non vide",
    ):
        Reranker(revision="")
    with pytest.raises(
        RevisionMismatchError, match="SHA non vide",
    ):
        Reranker(revision=None)


def test_reranker_leve_revision_mismatch_si_hash_differe(torch_mock):
    """Fail-fast à la construction si le modèle chargé a un SHA
    différent de la revision demandée. Test via mocks, sans
    appeler HuggingFace."""
    tokenizer = MagicMock()
    tokenizer._commit_hash = MODEL_REVISION
    tokenizer.init_kwargs = {}
    tokenizer.config = SimpleNamespace(_commit_hash=MODEL_REVISION)
    model = MagicMock()
    model._commit_hash = "0" * 40  # SHA explicitement différent
    model.config = SimpleNamespace(_commit_hash="0" * 40)
    with pytest.raises(RevisionMismatchError, match="model"):
        Reranker(
            revision=MODEL_REVISION,
            _tokenizer=tokenizer, _model=model,
        )


def test_reranker_leve_si_commit_hash_absent_partout(torch_mock):
    """Pas de passage silencieux : si ni tokenizer ni modèle
    n'exposent de SHA résoluble (ex. cache manuellement édité,
    transformers qui ne remplit plus ``_commit_hash``), on lève
    plutôt que d'avancer sans vérification."""
    # On explicite les attributs à None pour désactiver le hash
    # résoluble (MagicMock auto-crée sinon des mocks truthy).
    tokenizer = MagicMock()
    tokenizer._commit_hash = None
    tokenizer.init_kwargs = {}
    tokenizer.config = SimpleNamespace(_commit_hash=None)
    model = MagicMock()
    model._commit_hash = None
    model.config = SimpleNamespace(_commit_hash=None)
    with pytest.raises(
        RevisionMismatchError, match="Aucun commit hash",
    ):
        Reranker(
            revision=MODEL_REVISION,
            _tokenizer=tokenizer, _model=model,
        )


def test_reranker_ok_quand_hash_correspond(torch_mock):
    """Pas d'exception quand tokenizer ET modèle rapportent la
    même revision que demandée. ``_setup_torch`` passe via les
    mocks (``model.eval()``, ``model.to()`` sont des MagicMock
    no-op)."""
    tokenizer = MagicMock()
    tokenizer._commit_hash = MODEL_REVISION
    tokenizer.init_kwargs = {}
    tokenizer.config = SimpleNamespace(_commit_hash=MODEL_REVISION)
    model = MagicMock()
    model._commit_hash = MODEL_REVISION
    model.config = SimpleNamespace(_commit_hash=MODEL_REVISION)
    rk = Reranker(
        revision=MODEL_REVISION,
        _tokenizer=tokenizer, _model=model,
    )
    assert rk.revision == MODEL_REVISION
    assert rk.device == "cpu"
    # Les mocks ont été configurés pour le forward (mode eval
    # appelé par __init__).
    model.eval.assert_called_once()
    model.to.assert_called_once_with("cpu")


# ------------------------------------------------------------------
# Invariance au batch_size (demande utilisateur Partie V3)
# ------------------------------------------------------------------

def test_scores_par_lots_concatene_dans_lordre_des_paires():
    pairs = [("q", f"c_{i:02d}") for i in range(10)]

    def scorer_batch(batch):
        # Score déterministe = len(texte)
        return [len(c) for q, c in batch]

    out_bs_2 = _scores_par_lots(pairs, 2, scorer_batch)
    out_bs_10 = _scores_par_lots(pairs, 10, scorer_batch)
    out_bs_1 = _scores_par_lots(pairs, 1, scorer_batch)
    # Les 3 listes doivent être STRICTEMENT identiques.
    assert out_bs_2 == out_bs_10 == out_bs_1
    # Et égales à l'appel direct sur toute la liste
    assert out_bs_2 == scorer_batch(pairs)


def test_scores_par_lots_batch_size_zero_leve():
    with pytest.raises(ValueError):
        _scores_par_lots(
            [("q", "c")], batch_size=0,
            scorer_batch=lambda b: [1.0 for _ in b],
        )


def test_scores_par_lots_scorer_qui_rend_mauvais_nombre_leve():
    pairs = [("q", "c") for _ in range(5)]
    with pytest.raises(ValueError):
        _scores_par_lots(
            pairs, batch_size=2,
            scorer_batch=lambda b: [1.0],  # faux
        )


def test_classement_final_invariant_sous_batch_size(chunks_fake):
    """Le classement final produit par ``reranker_top_k`` doit
    être identique quelle que soit la taille des lots internes
    utilisée pendant le scoring. On simule un `Reranker` dont
    le score pour la paire (q, c) est deterministe
    (hash de chunk_id), et on vérifie l'invariance.
    """
    chunks = {f"chunk_{i:02d}_p1_s0": {"texte": f"texte {i}"}
              for i in range(10)}
    candidats = [
        {"rank": i + 1, "chunk_id": f"chunk_{i:02d}_p1_s0",
         "doc": "d", "page_physique": 1, "sous_numero": 0}
        for i in range(10)
    ]

    def faire_scorer(batch_size):
        """Crée une classe scorer qui simule le batching
        interne d'un Reranker réel avec le batch_size donné."""

        class _Rk:
            def score_pairs(self, pairs):
                # Scorer déterministe : score = len de chunk_texte
                # (différent pour chaque chunk, puisque texte = "texte i")
                return _scores_par_lots(
                    pairs, batch_size,
                    lambda batch: [len(c) for q, c in batch],
                )
        return _Rk()

    top5_bs_2 = reranker_top_k(
        "q", candidats, chunks, faire_scorer(2), top_final=5,
    )
    top5_bs_4 = reranker_top_k(
        "q", candidats, chunks, faire_scorer(4), top_final=5,
    )
    top5_bs_10 = reranker_top_k(
        "q", candidats, chunks, faire_scorer(10), top_final=5,
    )
    ids_2 = [r["chunk_id"] for r in top5_bs_2]
    ids_4 = [r["chunk_id"] for r in top5_bs_4]
    ids_10 = [r["chunk_id"] for r in top5_bs_10]
    assert ids_2 == ids_4 == ids_10, (
        "Classement doit être invariant au batch_size "
        f"(bs=2: {ids_2}, bs=4: {ids_4}, bs=10: {ids_10})"
    )
    # Les scores aussi
    scores_2 = [r["score_rerank"] for r in top5_bs_2]
    scores_4 = [r["score_rerank"] for r in top5_bs_4]
    scores_10 = [r["score_rerank"] for r in top5_bs_10]
    assert scores_2 == scores_4 == scores_10


def test_batch_size_default_est_fige():
    """BATCH_SIZE_DEFAULT verrouillé à 2 pour V3 (protéger
    contre les régressions de pic RAM). Modification nécessite
    une décision explicite."""
    assert BATCH_SIZE_DEFAULT == 2
