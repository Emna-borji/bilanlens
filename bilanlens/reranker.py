"""Reranker cross-encoder multilingue (plan V3, journal 2026-11-07).

Modèle figé : `BAAI/bge-reranker-v2-m3`.

Licence du modèle : **Apache-2.0** (cf. carte modèle HuggingFace
et `LICENSE` du dépôt BAAI/bge-reranker-v2-m3).

Revision épinglée : variable de module `MODEL_REVISION`, hash SHA
du commit HuggingFace figé (branch `main`). Le code **lève à la
construction** si :

- ``revision`` est vide ou ``None`` (refus de charger un modèle
  non figé) ;
- aucun des deux objets chargés (tokenizer et modèle) n'expose
  un commit hash résoluble (ni via ``_commit_hash``, ni via
  ``config._commit_hash``, ni via un chemin cache HuggingFace du
  type ``snapshots/<sha>/``) ;
- un commit hash est résolu et diffère de ``revision``.

Toutes ces erreurs lèvent ``RevisionMismatchError`` — jamais de
passage silencieux (fail-fast anti-dérive du modèle HF).

Contexte max : 8192 tokens (natif du modèle). On passe les pages
entières au reranker. Garde-fou : exception explicite
``LongueurExcedenteError`` si une paire dépasse ``max_length``,
plutôt qu'une troncation silencieuse qui perdrait la fin d'un
tableau de bilan.

Usage minimal ::

    from bilanlens.reranker import Reranker, reranker_top_k
    rk = Reranker()
    top5 = reranker_top_k(
        question_texte,
        candidats_top_20,          # issus de V2.1/hybride_filtre
        chunks_par_id,
        rk,                         # ou une fonction scorer (tests)
        top_final=5,
    )
"""
from __future__ import annotations

import gc
import re
from typing import Callable, Protocol


# ---------------------------------------------------------------------------
# Détection de la revision HF chargée par transformers
# ---------------------------------------------------------------------------
# Pattern pour extraire le SHA 40-hex depuis un chemin HuggingFace du cache
# local : ``.../models--X--Y/snapshots/<sha>/fichier``. C'est le format
# standard de ``huggingface_hub``, stable d'une version de transformers à
# l'autre et robuste aux séparateurs Windows (`\`) et POSIX (`/`).
_SNAPSHOT_SHA_RE = re.compile(r"snapshots[\\/]([a-f0-9]{40})")


# ---------------------------------------------------------------------------
# Identité du modèle — figés avant toute mesure
# ---------------------------------------------------------------------------
MODEL_NAME = "BAAI/bge-reranker-v2-m3"

# Revision épinglée (SHA complet du commit HuggingFace, branch main
# au 2026-11-07). Vérifiée via ``huggingface_hub.model_info`` lors
# du premier téléchargement.
MODEL_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"

# Licence du modèle (card HuggingFace au 2026-11-07).
MODEL_LICENSE = "apache-2.0"

# Contexte max natif du modèle (8192 tokens pour bge-reranker-v2-m3).
# On fixe la limite applicative à la même valeur et on vérifie
# chaque paire avant de l'envoyer au modèle.
MAX_LENGTH = 8192

# Taille de lot par défaut pour ``score_pairs``. Petits lots pour
# limiter le pic RAM pendant le forward (pages de ~2000 tokens, 2 à
# 4 paires suffisent pour tenir sur 16 GB de RAM partagée).
BATCH_SIZE_DEFAULT = 2


def _scores_par_lots(
    pairs: list[tuple[str, str]],
    batch_size: int,
    scorer_batch: Callable[[list[tuple[str, str]]], list[float]],
) -> list[float]:
    """Applique ``scorer_batch`` par lots de ``batch_size`` et
    concatène les scores dans l'ordre des paires d'entrée.

    **Invariant** : pour un ``scorer_batch`` déterministe et un
    ``batch_size`` ≥ 1, la liste de scores retournée est
    STRICTEMENT la même quelle que soit la taille des lots. Le
    test correspondant garde-foute cette propriété
    (``test_classement_final_invariant_sous_batch_size``).

    Le lot suivant commence toujours à la frontière définie par
    la coupe : pas de ré-ordonnancement, pas de chevauchement.
    """
    if batch_size < 1:
        raise ValueError(
            f"batch_size doit être >= 1 (reçu : {batch_size})"
        )
    out: list[float] = []
    for i in range(0, len(pairs), batch_size):
        lot = pairs[i:i + batch_size]
        scores = scorer_batch(lot)
        if len(scores) != len(lot):
            raise ValueError(
                f"scorer_batch a retourné {len(scores)} scores "
                f"pour un lot de {len(lot)} paires"
            )
        out.extend(scores)
    return out


class LongueurExcedenteError(RuntimeError):
    """Levée quand la longueur tokenisée d'une paire (question, chunk)
    dépasse ``MAX_LENGTH``. Signal fort : la page est trop longue
    pour tenir dans la fenêtre du reranker. Préférable à une
    troncation silencieuse qui perdrait la fin d'un tableau."""


class RevisionMismatchError(RuntimeError):
    """Levée à la construction par ``Reranker`` ou par
    ``_valider_revision_chargee`` dans trois cas :

    - **Revision vide/None** : on refuse d'instancier un reranker
      sans pin explicite (``Reranker(revision="")`` ou
      ``revision=None`` échouent ici).
    - **Commit hash non résoluble** : ni le tokenizer ni le modèle
      n'exposent un commit hash (via ``_commit_hash``, via
      ``config._commit_hash``, ou via un chemin cache
      ``snapshots/<sha>/`` dans leurs ``init_kwargs``). On préfère
      lever qu'avancer sans pouvoir valider.
    - **Commit hash différent** : le tokenizer OU le modèle
      rapporte un SHA qui ne correspond pas à la revision demandée.

    Fail-fast anti-dérive : prévient qu'un reload silencieux de
    ``main`` ou qu'une version différente en cache soient utilisés
    sans que l'appelant s'en aperçoive.
    """


# ---------------------------------------------------------------------------
# Validation de la revision HF chargée (utilitaires testables)
# ---------------------------------------------------------------------------

def _extract_commit_hash(obj) -> str | None:
    """Tente d'extraire le commit hash HuggingFace depuis un objet
    ``transformers`` (tokenizer ou modèle).

    L'API transformers n'expose pas uniformément le SHA selon les
    versions : on cherche donc dans plusieurs sources, dans l'ordre :

    1. ``obj._commit_hash`` (anciennes versions transformers).
    2. ``obj.config._commit_hash`` (modèles).
    3. ``obj.init_kwargs["vocab_file"]`` (tokenizers) : le chemin
       pointe dans le cache HuggingFace, qui contient
       ``.../snapshots/<sha>/sentencepiece.bpe.model``.

    Retourne ``None`` si aucune source ne permet d'extraire un SHA
    40-hex. ``_valider_revision_chargee`` traite ce cas comme une
    erreur (refus du passage silencieux).
    """
    direct = getattr(obj, "_commit_hash", None)
    if direct:
        return str(direct)
    cfg = getattr(obj, "config", None)
    if cfg is not None:
        cfg_hash = getattr(cfg, "_commit_hash", None)
        if cfg_hash:
            return str(cfg_hash)
    init_kwargs = getattr(obj, "init_kwargs", None) or {}
    vocab_file = init_kwargs.get("vocab_file")
    if vocab_file:
        match = _SNAPSHOT_SHA_RE.search(str(vocab_file))
        if match:
            return match.group(1)
    return None


def _valider_revision_chargee(
    revision: str, tokenizer, model,
) -> None:
    """Vérifie que la revision HuggingFace du modèle chargé
    correspond à ``revision``. Lève ``RevisionMismatchError`` dans
    les trois cas documentés par la classe d'exception.

    Au moins l'un des deux objets (tokenizer ou modèle) doit
    exposer un commit hash résoluble ; tous les hashes résolus
    doivent concorder avec ``revision``.
    """
    if not revision:
        raise RevisionMismatchError(
            "revision doit être un SHA non vide. Passer "
            "MODEL_REVISION ou un SHA explicite pour garantir un "
            "modèle figé."
        )
    tokenizer_hash = _extract_commit_hash(tokenizer)
    model_hash = _extract_commit_hash(model)
    if tokenizer_hash is None and model_hash is None:
        raise RevisionMismatchError(
            f"Aucun commit hash n'est résoluble (ni sur le "
            f"tokenizer, ni sur le modèle). Transformers n'expose "
            f"pas ``_commit_hash`` et aucun chemin cache "
            f"``snapshots/<sha>/`` n'a été trouvé. Impossible de "
            f"valider le pin à la revision {revision}. "
            f"Refus de continuer en silence (fail-fast "
            f"anti-dérive)."
        )
    for nom, h in (("tokenizer", tokenizer_hash), ("model", model_hash)):
        if h is not None and h != revision:
            raise RevisionMismatchError(
                f"Revision {nom} = {h!r} ne correspond pas à "
                f"la revision demandée {revision!r}. Fail-fast "
                f"anti-dérive du modèle HuggingFace."
            )


# ---------------------------------------------------------------------------
# Protocol pour les tests (scorer mockable)
# ---------------------------------------------------------------------------
class Scorer(Protocol):
    """Interface minimale d'un reranker : prend une liste de paires
    (question, chunk_texte), retourne une liste de scores float
    de même longueur et dans le même ordre."""

    def score_pairs(
        self, pairs: list[tuple[str, str]],
    ) -> list[float]: ...


# ---------------------------------------------------------------------------
# Reranker réel (charge le modèle HuggingFace)
# ---------------------------------------------------------------------------

class Reranker:
    """Wrapper autour de `transformers.AutoModelForSequenceClassification`
    pour `BAAI/bge-reranker-v2-m3`. ``score_pairs`` scorde une liste
    de paires (question, chunk_texte) sans troncation silencieuse.

    Paramètres
    ----------
    model_name : nom du modèle HuggingFace. Par défaut ``MODEL_NAME``.
    revision : SHA du commit HF à charger. Par défaut
        ``MODEL_REVISION``. **Doit être non vide** (sinon
        ``RevisionMismatchError`` levée avant tout chargement).
    device : "cuda", "cpu" ou "auto" (choix auto via
        ``torch.cuda.is_available``).
    max_length : seuil appliqué avant chaque forward. Par défaut
        ``MAX_LENGTH`` (8192). Toute paire plus longue lève
        ``LongueurExcedenteError``.
    batch_size : taille des lots internes de ``score_pairs``.

    Validation de la revision chargée : après le chargement du
    tokenizer et du modèle, ``_valider_revision_chargee`` compare
    le commit hash HF du tokenizer et du modèle à ``revision``.
    Si l'un diffère, ou si aucun hash n'est résoluble, une
    ``RevisionMismatchError`` est levée AVANT toute opération
    torch. Fail-fast anti-dérive.

    Injection pour tests : ``_tokenizer`` et ``_model`` permettent
    de passer des objets déjà construits (p.ex. mocks). Dans ce
    cas, ``from transformers import ...`` n'est PAS exécuté — les
    tests sans réseau peuvent couvrir la validation sans installer
    ``transformers``.

    Idempotence et déterminisme :
    - Modèle en mode ``eval`` + ``torch.inference_mode`` pendant
      ``score_pairs``.
    - Pas de ``torch.manual_seed`` nécessaire pour un modèle
      déterministe (pas de dropout en eval).
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        revision: str = MODEL_REVISION,
        device: str = "auto",
        max_length: int = MAX_LENGTH,
        batch_size: int = BATCH_SIZE_DEFAULT,
        _tokenizer=None,
        _model=None,
    ):
        # Refus précoce si revision vide — AVANT tout import lourd
        # (torch / transformers). Permet de tester sans installer
        # les dépendances.
        if not revision:
            raise RevisionMismatchError(
                "revision doit être un SHA non vide. Passer "
                "MODEL_REVISION ou un SHA explicite pour garantir "
                "un modèle figé."
            )

        self.model_name = model_name
        self.revision = revision
        self.max_length = max_length
        self.batch_size = batch_size

        if _tokenizer is not None:
            self.tokenizer = _tokenizer
        else:
            from transformers import AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name, revision=revision,
            )
        if _model is not None:
            self.model = _model
        else:
            from transformers import AutoModelForSequenceClassification
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_name, revision=revision,
            )

        # Fail-fast anti-dérive : vérifie que la revision chargée
        # correspond à ``revision``. Lève RevisionMismatchError si
        # hash absent ou différent. Avant toute opération torch.
        _valider_revision_chargee(revision, self.tokenizer, self.model)

        # Device setup (après validation : le modèle est confirmé).
        import torch
        self.model.eval()  # pas de dropout, déterministe
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        self.model.to(self.device)

    def mesurer_longueur(self, question: str, chunk_texte: str) -> int:
        """Nombre de tokens de la paire (question, chunk) sans troncation.

        Compte les tokens produits par le tokenizer du reranker, y
        compris les tokens spéciaux (CLS/SEP) ajoutés pour une paire.
        """
        ids = self.tokenizer(
            question, chunk_texte,
            truncation=False, return_tensors=None,
        )["input_ids"]
        return len(ids)

    def mesurer_longueurs_batch(
        self, pairs: list[tuple[str, str]],
    ) -> list[int]:
        """Longueurs tokenisées pour un batch de paires, sans appel au modèle."""
        return [
            self.mesurer_longueur(q, c) for q, c in pairs
        ]

    def _score_batch(
        self, pairs: list[tuple[str, str]],
    ) -> list[float]:
        """Forward d'UN petit lot déjà validé en longueur.

        Libère explicitement les tenseurs d'entrée et de sortie
        après le forward (``del`` + ``gc.collect`` + éventuel
        ``torch.cuda.empty_cache``) pour limiter le pic RAM
        pendant un benchmark long.
        """
        import torch

        if not pairs:
            return []
        with torch.inference_mode():
            inputs = self.tokenizer(
                [q for q, _ in pairs],
                [c for _, c in pairs],
                truncation=False, padding=True,
                return_tensors="pt",
            ).to(self.device)
            outputs = self.model(**inputs, return_dict=True)
            scores = outputs.logits.view(-1).float().cpu().tolist()
        # Libération explicite
        del inputs, outputs
        gc.collect()
        if str(self.device).startswith("cuda"):
            torch.cuda.empty_cache()
        return scores

    def score_pairs(
        self, pairs: list[tuple[str, str]],
        batch_size: int | None = None,
    ) -> list[float]:
        """Scorde une liste de paires (question, chunk_texte)
        par petits lots.

        Garde-fou longueur : chaque paire est tokenisée sans
        troncation AVANT scoring. Une paire dépassant
        ``max_length`` tokens lève ``LongueurExcedenteError``
        — pas de troncation silencieuse qui perdrait la fin
        d'une page (ex. ligne « Total des actifs » en bas de
        bilan).

        ``batch_size`` : si fourni, écrase ``self.batch_size``
        pour cet appel uniquement (utile pour benchmark). Les
        scores retournés ne dépendent PAS de ``batch_size``
        (invariant garanti par ``_scores_par_lots``).
        """
        if not pairs:
            return []

        # Garde-fou longueur paire par paire
        longueurs = self.mesurer_longueurs_batch(pairs)
        for i, n in enumerate(longueurs):
            if n > self.max_length:
                q, c = pairs[i]
                raise LongueurExcedenteError(
                    f"Paire {i} de longueur {n} > max_length "
                    f"{self.max_length}. Question: {q[:80]!r} ; "
                    f"chunk ({len(c)} chars) tronqué dans ce msg."
                )

        taille_lot = (
            batch_size if batch_size is not None else self.batch_size
        )
        return _scores_par_lots(
            pairs, taille_lot, self._score_batch,
        )


# ---------------------------------------------------------------------------
# API haut niveau : reranker_top_k
# ---------------------------------------------------------------------------

def reranker_top_k(
    question: str,
    candidats: list[dict],
    chunks_par_id: dict[str, dict],
    scorer: Scorer | Callable[[list[tuple[str, str]]], list[float]],
    top_final: int,
) -> list[dict]:
    """Reclasse ``candidats`` via ``scorer`` et retourne les
    ``top_final`` premiers.

    Entrée : candidats = liste de dicts {chunk_id, doc, page_physique,
    sous_numero, rank, ...}. Chaque chunk_id DOIT être présent dans
    ``chunks_par_id`` (sinon KeyError clair).

    Sortie : liste de dicts {rank, chunk_id, score_rerank, doc,
    page_physique, sous_numero}. Tri : score_rerank décroissant,
    tie-break chunk_id alphanumérique croissant (règle d'ordre
    stable commune à V2 §3).

    ``scorer`` peut être une instance ``Reranker`` ou n'importe
    quel callable prenant une liste de paires (question, chunk_texte)
    et retournant une liste de scores (utile pour tests mockés).
    """
    if not candidats:
        return []
    pairs: list[tuple[str, str]] = []
    for c in candidats:
        texte = chunks_par_id[c["chunk_id"]]["texte"]
        pairs.append((question, texte))
    if hasattr(scorer, "score_pairs"):
        scores = scorer.score_pairs(pairs)
    else:
        scores = scorer(pairs)
    if len(scores) != len(candidats):
        raise ValueError(
            f"scorer a retourné {len(scores)} scores pour "
            f"{len(candidats)} candidats"
        )
    scored = [
        {
            "chunk_id": c["chunk_id"],
            "score_rerank": float(s),
            "doc": c.get("doc"),
            "page_physique": c.get("page_physique"),
            "sous_numero": c.get("sous_numero", 0),
        }
        for c, s in zip(candidats, scores)
    ]
    scored.sort(key=lambda r: (-r["score_rerank"], r["chunk_id"]))
    return [
        {**r, "rank": rang}
        for rang, r in enumerate(scored[:top_final], start=1)
    ]
