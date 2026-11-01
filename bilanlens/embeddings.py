"""Encodeurs d'embeddings pour BilanLens (RAG, Semaine 2 etape 4).

Interface commune `Encodeur` (Protocol) avec deux methodes :
- `embed_documents(textes)` → `(ndarray(n, dim), stats)` ; `task_type`
  = `RETRIEVAL_DOCUMENT` cote Gemini ;
- `embed_query(texte)` → `ndarray(dim,)` ; `task_type` = `RETRIEVAL_QUERY`.

Deux implementations livrees : `EncodeurGemini` (API Google) et
`EncodeurFake` (hashlib.sha256 → rng → unit-norm, deterministe entre
runs). `index.py` et les scripts ne font jamais de `isinstance` : ils
appellent directement les methodes du protocole.

**Confidentialite** : avec le free tier Google, les requetes peuvent
etre utilisees pour ameliorer les modeles. Acceptable pour BilanLens
(rapports BVMT publics) ; **ne pas** utiliser cet adapter sur des
documents confidentiels. Voir README « Confidentialite ».

**Cache sur disque** : chaque vecteur produit est persiste dans
`data/cache_embeddings/<model>.jsonl` (gitignore). Cle =
`sha256(model | task_type | texte)`. Les comptages `count_tokens`
sont **egalement** persistes dans `<model>__tokens.jsonl` (cle =
`sha256(model | texte)`, le task_type n'intervient pas dans le
comptage de tokens). Une seconde indexation du meme corpus fait
**0 appel API au total** (0 embed + 0 count).

**Rate limiting (Gemini)** : TPM = 30 000 (free tier, borne qui mord
en premier) ; RPM = 100. On regroupe les chunks en lots dont la somme
des tokens tient dans `TPM_MAX * MARGE_QUOTA`, on espace d'une minute
entre deux lots (fenetre TPM glissante), et le comptage des tokens
`count_tokens` est lui aussi RPM-limite (sliding window a 100/min).

**Backoff 429** : factorise avec `llm.py` via `_api_retry.appeler_avec_backoff`.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np

from bilanlens._api_retry import ErreurQuotaDepassee, appeler_avec_backoff  # noqa: F401

# Modele par defaut : `gemini-embedding-2`.
# - 3072 dim ;
# - input_token_limit = 8192 tokens (marge pour le max observe = 2760) ;
# - GA stable, vecteurs nativement unit-norm (norme L2 = 1,000000) ;
# - supporte task_type RETRIEVAL_DOCUMENT / RETRIEVAL_QUERY.
DEFAULT_MODEL = "gemini-embedding-2"
DEFAULT_DIM = 3072

# Quotas free tier (sources tierces convergentes au 2026-10-31).
TPM_MAX = 30_000  # tokens par minute (quota qui mord en premier)
RPM_MAX = 100     # requetes par minute
# Marge pour tolerer l'ecart entre count_tokens local et serveur.
MARGE_QUOTA = 0.8
# Limite documentee de `embed_content` : 100 contents par appel batch.
MAX_CONTENTS_PAR_APPEL = 100

TASK_RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_RETRIEVAL_QUERY = "RETRIEVAL_QUERY"

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache_embeddings"


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------
@runtime_checkable
class Encodeur(Protocol):
    """Interface commune aux adapters d'embedding."""

    model: str
    dim: int

    def embed_documents(
        self, textes: list[str], verbose: bool = False,
    ) -> tuple[np.ndarray, dict]: ...

    def embed_query(self, texte: str) -> np.ndarray: ...


# ---------------------------------------------------------------------------
# Cache + hashing deterministe
# ---------------------------------------------------------------------------
def _hash_cle(model: str, task_type: str, texte: str) -> str:
    """SHA-256 deterministe entre runs (contrairement a `hash()` qui
    varie avec PYTHONHASHSEED a chaque lancement de Python)."""
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"|")
    h.update(task_type.encode("utf-8"))
    h.update(b"|")
    h.update(texte.encode("utf-8"))
    return h.hexdigest()


def _cle_tokens(model: str, texte: str) -> str:
    """Cle du cache tokens : `sha256(model | texte)`. Pas de task_type :
    le comptage de tokens par `count_tokens` ne depend pas de la facon
    dont le texte sera ensuite utilise (RETRIEVAL_DOCUMENT vs _QUERY).
    """
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"|")
    h.update(texte.encode("utf-8"))
    return h.hexdigest()


class _CacheEmbeddings:
    """Cache append-only sur disque pour une (model) donnee.

    Un seul fichier par modele : `<cache_dir>/<model>.jsonl`. Les
    task_type cohabitent dans la cle (sha256 fait partie integrante
    de la cle), donc pas besoin d'un fichier par task_type.

    Robustesse : append apres chaque put (pas de save a la fin).
    Si le process est tue en cours d'indexation, le cache contient
    deja les vecteurs encodes.
    """

    def __init__(self, cache_dir: Path, model: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Un nom de fichier sur, sans '/' (ex. 'BAAI/bge-m3' → 'BAAI_bge-m3').
        nom = model.replace("/", "_")
        self.path = self.cache_dir / f"{nom}.jsonl"
        self._data: dict[str, list[float]] = {}
        if self.path.exists():
            with self.path.open(encoding="utf-8") as f:
                for ligne in f:
                    try:
                        rec = json.loads(ligne)
                        self._data[rec["key"]] = rec["vec"]
                    except (json.JSONDecodeError, KeyError):
                        continue

    def get(self, cle: str) -> list[float] | None:
        return self._data.get(cle)

    def put(self, cle: str, vec: list[float]) -> None:
        self._data[cle] = vec
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": cle, "vec": vec}) + "\n")

    def __contains__(self, cle: str) -> bool:
        return cle in self._data


class _CacheTokens:
    """Cache append-only sur disque pour les comptages `count_tokens`.

    Fichier : `<cache_dir>/<model>__tokens.jsonl`. Cle =
    `sha256(model | texte)` (voir `_cle_tokens`). Append apres chaque
    put : si le process est tue en cours d'indexation, le cache garde
    tous les comptages deja faits.

    Objectif : une 2e indexation du meme corpus fait 0 appel API au
    total (0 embed via `_CacheEmbeddings`, 0 count via `_CacheTokens`).
    """

    def __init__(self, cache_dir: Path, model: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        nom = model.replace("/", "_")
        self.path = self.cache_dir / f"{nom}__tokens.jsonl"
        self._data: dict[str, int] = {}
        if self.path.exists():
            with self.path.open(encoding="utf-8") as f:
                for ligne in f:
                    try:
                        rec = json.loads(ligne)
                        self._data[rec["key"]] = int(rec["n"])
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue

    def get(self, cle: str) -> int | None:
        return self._data.get(cle)

    def put(self, cle: str, n: int) -> None:
        self._data[cle] = n
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": cle, "n": n}) + "\n")

    def __contains__(self, cle: str) -> bool:
        return cle in self._data


# ---------------------------------------------------------------------------
# Bin-packing (TPM + API limit)
# ---------------------------------------------------------------------------
def _regrouper_en_lots_par_tpm(
    tokens_par_texte: list[int],
    tpm_max: int = TPM_MAX,
    marge: float = MARGE_QUOTA,
    max_contents_par_appel: int = MAX_CONTENTS_PAR_APPEL,
) -> list[list[int]]:
    """Bin-packing glouton : retourne la liste des lots d'indices.

    Chaque lot respecte :
    - somme des tokens <= `tpm_max * marge` (budget TPM) ;
    - taille du lot <= `max_contents_par_appel` (limite API batch).
    """
    budget = int(tpm_max * marge)
    lots: list[list[int]] = []
    lot_courant: list[int] = []
    tokens_courant = 0
    for i, n in enumerate(tokens_par_texte):
        deborde_budget = tokens_courant + n > budget
        lot_plein = len(lot_courant) >= max_contents_par_appel
        if deborde_budget or lot_plein:
            if lot_courant:
                lots.append(lot_courant)
            lot_courant = [i]
            tokens_courant = n
        else:
            lot_courant.append(i)
            tokens_courant += n
    if lot_courant:
        lots.append(lot_courant)
    return lots


# ---------------------------------------------------------------------------
# EncodeurGemini
# ---------------------------------------------------------------------------
@dataclass
class EncodeurGemini:
    """Adapter Gemini embedding (API `google-genai`) avec cache,
    sliding-window RPM pour `count_tokens` et bin-packing TPM pour
    `embed_content`.
    """

    client: object
    model: str = DEFAULT_MODEL
    dim: int = DEFAULT_DIM
    tpm_max: int = TPM_MAX
    rpm_max: int = RPM_MAX
    cache_dir: Path = field(default_factory=lambda: CACHE_DIR)
    cache: _CacheEmbeddings | None = None
    cache_tokens: _CacheTokens | None = None
    _timestamps_count: deque = field(default_factory=deque)
    _nb_appels_count: int = 0
    _nb_appels_embed: int = 0

    def __post_init__(self):
        if self.cache is None:
            self.cache = _CacheEmbeddings(self.cache_dir, self.model)
        if self.cache_tokens is None:
            self.cache_tokens = _CacheTokens(self.cache_dir, self.model)

    # ---- Comptage tokens (RPM-limite, en cache local) ----
    def _attendre_rpm_count(self) -> None:
        """Sliding window : au plus `rpm_max` appels count sur 60 s."""
        maintenant = time.monotonic()
        while self._timestamps_count and maintenant - self._timestamps_count[0] > 60:
            self._timestamps_count.popleft()
        if len(self._timestamps_count) >= self.rpm_max:
            attente = 60 - (maintenant - self._timestamps_count[0]) + 0.1
            if attente > 0:
                time.sleep(attente)
            # Nettoyer apres l'attente.
            maintenant = time.monotonic()
            while self._timestamps_count and maintenant - self._timestamps_count[0] > 60:
                self._timestamps_count.popleft()
        self._timestamps_count.append(time.monotonic())

    def compter_tokens(self, texte: str) -> int:
        """Nombre de tokens pour `texte`. Cache **sur disque** : un
        texte deja compte dans un run precedent n'est jamais recompte.
        Respecte le RPM via sliding window pour les comptages manquants.
        """
        cle = _cle_tokens(self.model, texte)
        cached = self.cache_tokens.get(cle)
        if cached is not None:
            return cached
        self._attendre_rpm_count()
        resp = self.client.models.count_tokens(
            model=self.model, contents=texte
        )
        n = resp.total_tokens
        self.cache_tokens.put(cle, n)
        self._nb_appels_count += 1
        return n

    # ---- Embedding ----
    def _call_embed_batch(
        self, textes: list[str], task_type: str,
    ) -> list[list[float]]:
        """Appels sequentiels `embed_content` (un par texte).

        `gemini-embedding-2` ne fait PAS de batch comme
        `gemini-embedding-001` : passer `contents=[t1, t2, ...]`
        retourne UN seul vecteur (vraisemblablement concatene) au lieu
        de N. Verifie empiriquement 2026-10-31. On fait donc N appels
        rapides, puis on attend 60 s cote appelant (`_encoder`) pour
        liberer le budget TPM glissant.
        """
        from google.genai import types

        config = types.EmbedContentConfig(task_type=task_type)
        vecteurs: list[list[float]] = []
        for t in textes:
            def _impl(t=t):
                return self.client.models.embed_content(
                    model=self.model, contents=t, config=config
                )
            resp = appeler_avec_backoff(_impl)
            self._nb_appels_embed += 1
            vecteurs.append(list(resp.embeddings[0].values))
        return vecteurs

    def _encoder(
        self, textes: list[str], task_type: str, verbose: bool,
    ) -> tuple[np.ndarray, dict]:
        """Encodage interne : check cache, batch les manquants, dump
        dans le cache. Rendu dans l'ordre original.
        """
        n = len(textes)
        tous_vecteurs: list[list[float] | None] = [None] * n
        a_encoder: list[tuple[int, str]] = []  # (indice_global, texte)
        hits = 0

        # 1) Cache hits
        for i, t in enumerate(textes):
            cle = _hash_cle(self.model, task_type, t)
            cached = self.cache.get(cle)
            if cached is not None:
                tous_vecteurs[i] = cached
                hits += 1
            else:
                a_encoder.append((i, t))

        if verbose and hits:
            print(f"  cache : {hits}/{n} vecteurs deja presents")

        # 2) Comptage des tokens pour les manquants, puis bin-packing
        tokens_a_encoder = [self.compter_tokens(t) for _, t in a_encoder]
        budget = int(self.tpm_max * MARGE_QUOTA)
        depassements = [
            (i, n_t) for (i, _), n_t in zip(a_encoder, tokens_a_encoder)
            if n_t > budget
        ]
        if depassements:
            raise ValueError(
                f"Chunks depassant le budget TPM ({budget} tokens) : "
                f"{depassements[:3]}"
            )
        lots = _regrouper_en_lots_par_tpm(tokens_a_encoder, self.tpm_max)

        # 3) Encodage lot par lot avec attente TPM entre lots
        t_global = time.perf_counter()
        for idx_lot, indices_locaux in enumerate(lots):
            t_lot = time.perf_counter()
            batch = [a_encoder[j][1] for j in indices_locaux]
            tokens_lot = sum(tokens_a_encoder[j] for j in indices_locaux)
            if verbose:
                print(
                    f"  Lot {idx_lot + 1}/{len(lots)} : {len(batch)} chunks, "
                    f"{tokens_lot} tokens"
                )
            vecteurs = self._call_embed_batch(batch, task_type)
            for j, v in zip(indices_locaux, vecteurs):
                i_global = a_encoder[j][0]
                tous_vecteurs[i_global] = v
                cle = _hash_cle(self.model, task_type, a_encoder[j][1])
                self.cache.put(cle, v)
            # Fenetre TPM glissante : attendre que 60 s se soient
            # ecoulees depuis le DEBUT du lot pour liberer son budget.
            if idx_lot < len(lots) - 1:
                attente = max(0.0, 60.0 - (time.perf_counter() - t_lot))
                if verbose and attente > 0:
                    print(f"    attente {attente:.1f} s (fenetre TPM)")
                time.sleep(attente)

        duree_s = time.perf_counter() - t_global
        stats = {
            "nb_appels_count": self._nb_appels_count,
            "nb_appels_embed": self._nb_appels_embed,
            "nb_hits_cache": hits,
            "nb_a_encoder": len(a_encoder),
            "tokens_total": sum(tokens_a_encoder),
            "nb_lots": len(lots),
            "duree_s": duree_s,
        }
        return np.asarray(tous_vecteurs, dtype=np.float32), stats

    def embed_documents(
        self, textes: list[str], verbose: bool = False,
    ) -> tuple[np.ndarray, dict]:
        return self._encoder(textes, TASK_RETRIEVAL_DOCUMENT, verbose)

    def embed_query(self, texte: str) -> np.ndarray:
        v, _ = self._encoder([texte], TASK_RETRIEVAL_QUERY, verbose=False)
        return v[0]


# ---------------------------------------------------------------------------
# EncodeurFake : deterministe sha256 pour tests sans quota
# ---------------------------------------------------------------------------
@dataclass
class EncodeurFake:
    """Encodeur deterministe : `sha256(task_type|texte)` → seed → rng
    → unit-norm. Deterministe entre runs (contrairement a `hash()`
    qui varie avec PYTHONHASHSEED).

    Expose la meme interface `Encodeur` que `EncodeurGemini` et
    utilise le meme cache disque : une seconde indexation = 0 vecteur
    recalcule, pour tester le path cache de bout en bout.
    """

    model: str = "fake-embedding"
    dim: int = 8
    tpm_max: int = TPM_MAX
    rpm_max: int = RPM_MAX
    cache_dir: Path = field(default_factory=lambda: CACHE_DIR)
    cache: _CacheEmbeddings | None = None
    _nb_vecteurs_calcules: int = 0

    def __post_init__(self):
        if self.cache is None:
            self.cache = _CacheEmbeddings(self.cache_dir, self.model)

    def _vecteur_deterministe(self, task_type: str, texte: str) -> list[float]:
        h = hashlib.sha256(f"{task_type}|{texte}".encode("utf-8")).digest()
        seed = int.from_bytes(h[:8], "big")
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(self.dim).astype(np.float32)
        v = v / np.linalg.norm(v)
        return v.tolist()

    def _encoder(
        self, textes: list[str], task_type: str,
    ) -> tuple[np.ndarray, dict]:
        n = len(textes)
        vecteurs = np.empty((n, self.dim), dtype=np.float32)
        hits = 0
        for i, t in enumerate(textes):
            cle = _hash_cle(self.model, task_type, t)
            cached = self.cache.get(cle)
            if cached is not None:
                vecteurs[i] = cached
                hits += 1
            else:
                v = self._vecteur_deterministe(task_type, t)
                vecteurs[i] = v
                self.cache.put(cle, v)
                self._nb_vecteurs_calcules += 1
        stats = {
            "nb_appels_count": 0,
            "nb_appels_embed": self._nb_vecteurs_calcules,
            "nb_hits_cache": hits,
            "nb_a_encoder": n - hits,
            "tokens_total": 0,
            "nb_lots": 0,
            "duree_s": 0.0,
        }
        return vecteurs, stats

    def embed_documents(
        self, textes: list[str], verbose: bool = False,
    ) -> tuple[np.ndarray, dict]:
        return self._encoder(textes, TASK_RETRIEVAL_DOCUMENT)

    def embed_query(self, texte: str) -> np.ndarray:
        v, _ = self._encoder([texte], TASK_RETRIEVAL_QUERY)
        return v[0]


# ---------------------------------------------------------------------------
# Factory + helpers
# ---------------------------------------------------------------------------
def charger_encodeur(model: str = DEFAULT_MODEL) -> EncodeurGemini:
    """Instancie l'encodeur Gemini en lisant `GEMINI_API_KEY` dans
    l'environnement. Le script appelant doit avoir fait `load_dotenv()`
    au prealable si la cle est dans `.env`.
    """
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY absente de l'environnement. "
            "Charger .env via python-dotenv ou exporter la variable."
        )
    client = genai.Client(api_key=api_key)
    return EncodeurGemini(client=client, model=model)


def nom_collection(model: str = DEFAULT_MODEL) -> str:
    """Nom de collection Chroma par modele : evite de melanger les
    espaces vectoriels (Gemini et bge-m3 n'ont pas la meme dimension
    ni la meme semantique).
    """
    return f"bilans__{model.replace('/', '_')}"
