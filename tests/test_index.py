"""Tests Chroma + encodeur Gemini / fake (RAG, Semaine 2 etape 4).

Par defaut : tourne avec `EncodeurFake` (sha256 deterministe). Pas de
reseau, pas de quota consomme. Les tests reels sont marker `network`.

Invariants verifies :
1. Les vecteurs sont de norme ~1 (fake sha256 + API Gemini nativement
   unit-norm).
2. `None` dans les metadonnees : la cle disparait sans faire tomber le
   upsert.
3. Idempotence : indexer 2 fois les memes chunks laisse `count()` stable.
4. **Cache embeddings** : une 2e indexation du meme corpus = 0 appel.
5. Bin-packing : les lots respectent le budget TPM.
6. SHA-256 deterministe : hash stable entre runs.
7. Collection par modele : `nom_collection(model)` → `bilans__<model>`.
"""
from __future__ import annotations

import os
import pytest


# ---------------------------------------------------------------------------
# Fixture encodeur fake isole : cache dans tmp_path pour chaque test
# ---------------------------------------------------------------------------
@pytest.fixture
def encodeur_isole(tmp_path):
    """`EncodeurFake` avec cache dans un tmp_path dedie (ne pollue
    pas `data/cache_embeddings/`)."""
    from bilanlens.embeddings import EncodeurFake

    return EncodeurFake(cache_dir=tmp_path / "cache_embeddings")


@pytest.fixture
def collection(tmp_path):
    """Collection Chroma neuve dans un tmp_path."""
    try:
        from bilanlens.index import ouvrir_collection
    except ImportError:
        pytest.skip("chromadb non installe (voir requirements.txt)")
    _, coll = ouvrir_collection(
        tmp_path / "chroma",
        nom="test_bilans",
        metadonnees_collection={"test": True, "modele": "fake-embedding"},
    )
    yield coll


def _chunk_dict(**overrides):
    base = dict(
        doc="sotuver_2024",
        entreprise="SOTUVER",
        exercice=2024,
        page_physique=4,
        page_imprimee="4",
        sous_numero=0,
        texte="Revenus (R.1) 100 836 224 165 986 659",
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Vecteurs unit-norm
# ---------------------------------------------------------------------------
def test_vecteurs_sont_normalises(encodeur_isole):
    import numpy as np

    v, _ = encodeur_isole.embed_documents(
        ["Revenus 100 836 224", "Autre texte"]
    )
    normes = np.linalg.norm(v, axis=1)
    assert all(abs(n - 1.0) < 1e-4 for n in normes), f"normes = {normes}"


def test_embed_query_vecteur_unitaire(encodeur_isole):
    import numpy as np

    v = encodeur_isole.embed_query("Resultat net 2024")
    assert v.shape == (encodeur_isole.dim,)
    assert abs(np.linalg.norm(v) - 1.0) < 1e-4


# ---------------------------------------------------------------------------
# 2. Collection : metadata, metrique, nommage par modele
# ---------------------------------------------------------------------------
def test_collection_metrique_cosine(collection):
    meta = collection.metadata or {}
    assert meta.get("hnsw:space") == "cosine"
    assert meta.get("test") is True
    assert meta.get("modele") == "fake-embedding"


def test_nom_collection_par_modele():
    """Deux modeles differents donnent deux noms de collection
    differents, pour pouvoir cohabiter sans melanger les espaces."""
    from bilanlens.embeddings import nom_collection

    assert nom_collection("gemini-embedding-2") == "bilans__gemini-embedding-2"
    assert nom_collection("BAAI/bge-m3") == "bilans__BAAI_bge-m3"
    assert (
        nom_collection("gemini-embedding-2")
        != nom_collection("BAAI/bge-m3")
    )


# ---------------------------------------------------------------------------
# 3. None dans les metadonnees
# ---------------------------------------------------------------------------
def test_metadata_omet_les_cles_none(encodeur_isole, collection):
    from bilanlens.index import indexer_chunks

    chunk_avec_none = _chunk_dict(
        page_physique=1, sous_numero=0, page_imprimee=None,
    )
    indexer_chunks(collection, [chunk_avec_none], encodeur_isole)

    res = collection.get(ids=["sotuver_2024_p1_s0"], include=["metadatas"])
    meta = res["metadatas"][0]
    assert "page_imprimee" not in meta
    assert meta["exercice"] == 2024 and isinstance(meta["exercice"], int)


# ---------------------------------------------------------------------------
# 4. Idempotence Chroma
# ---------------------------------------------------------------------------
def test_upsert_idempotent_sur_meme_chunks(encodeur_isole, collection):
    from bilanlens.index import indexer_chunks

    chunks = [
        _chunk_dict(page_physique=1, sous_numero=0),
        _chunk_dict(page_physique=2, sous_numero=0),
        _chunk_dict(page_physique=3, sous_numero=0),
        _chunk_dict(page_physique=3, sous_numero=1),
    ]
    indexer_chunks(collection, chunks, encodeur_isole)
    assert collection.count() == 4
    indexer_chunks(collection, chunks, encodeur_isole)
    assert collection.count() == 4


# ---------------------------------------------------------------------------
# 5. Cache embeddings : 2e indexation = 0 vecteur recalcule
# ---------------------------------------------------------------------------
def test_cache_embeddings_zero_appel_a_la_2e_indexation(
    encodeur_isole, collection,
):
    """Apres une 1re indexation, le compteur `_nb_vecteurs_calcules`
    de l'encodeur monte. Apres une 2e, il doit rester a sa valeur :
    tous les vecteurs sont sortis du cache disque.
    """
    from bilanlens.index import indexer_chunks

    # Textes DIFFERENTS pour avoir 5 hashes distincts.
    chunks = [
        _chunk_dict(page_physique=p, sous_numero=0, texte=f"Chunk page {p} texte unique")
        for p in range(1, 6)
    ]
    _, stats1 = indexer_chunks(collection, chunks, encodeur_isole)
    assert stats1["nb_a_encoder"] == 5
    assert stats1["nb_hits_cache"] == 0
    appels_apres_1 = encodeur_isole._nb_vecteurs_calcules
    assert appels_apres_1 == 5

    # 2e indexation : tout doit sortir du cache disque.
    _, stats2 = indexer_chunks(collection, chunks, encodeur_isole)
    assert stats2["nb_hits_cache"] == 5
    assert stats2["nb_a_encoder"] == 0
    # Le compteur n'a pas bouge : aucun vecteur recalcule.
    assert encodeur_isole._nb_vecteurs_calcules == appels_apres_1


def test_cache_persiste_entre_instances_sur_meme_disque(tmp_path):
    """Un nouvel `EncodeurFake` qui pointe sur le meme `cache_dir`
    doit retrouver les vecteurs ecrits par un ancien."""
    from bilanlens.embeddings import EncodeurFake

    cache_dir = tmp_path / "cache"
    enc1 = EncodeurFake(cache_dir=cache_dir)
    enc1.embed_documents(["un", "deux"])
    assert enc1._nb_vecteurs_calcules == 2

    enc2 = EncodeurFake(cache_dir=cache_dir)
    _, stats = enc2.embed_documents(["un", "deux"])
    assert stats["nb_hits_cache"] == 2
    assert enc2._nb_vecteurs_calcules == 0


# ---------------------------------------------------------------------------
# 6. Bin-packing : lots respectent le budget TPM
# ---------------------------------------------------------------------------
def test_regroupage_par_tpm_respecte_le_budget():
    from bilanlens.embeddings import _regrouper_en_lots_par_tpm

    tokens = [10_000, 15_000, 5_000, 20_000, 3_000]
    tpm_max, marge = 30_000, 0.8
    budget = int(tpm_max * marge)
    lots = _regrouper_en_lots_par_tpm(tokens, tpm_max, marge)

    tous_indices = [i for lot in lots for i in lot]
    assert sorted(tous_indices) == list(range(len(tokens)))
    for lot in lots:
        assert sum(tokens[i] for i in lot) <= budget


def test_regroupage_respecte_max_contents_par_appel():
    """La limite de 100 contents par appel doit etre respectee meme
    si le TPM le permettrait."""
    from bilanlens.embeddings import _regrouper_en_lots_par_tpm

    # 150 chunks a 50 tokens : largement sous TPM mais > 100 par lot
    tokens = [50] * 150
    lots = _regrouper_en_lots_par_tpm(tokens, 30_000, 0.8, max_contents_par_appel=100)
    for lot in lots:
        assert len(lot) <= 100


# ---------------------------------------------------------------------------
# 7. SHA-256 deterministe entre runs
# ---------------------------------------------------------------------------
def test_hash_cle_deterministe():
    """`_hash_cle` doit retourner la MEME valeur a chaque appel : clef
    du cache qui survit a un restart Python (contrairement a hash())."""
    from bilanlens.embeddings import _hash_cle

    h1 = _hash_cle("gemini-embedding-2", "RETRIEVAL_DOCUMENT", "test")
    h2 = _hash_cle("gemini-embedding-2", "RETRIEVAL_DOCUMENT", "test")
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex

    # Modele different → hash different
    h3 = _hash_cle("BAAI/bge-m3", "RETRIEVAL_DOCUMENT", "test")
    assert h1 != h3

    # task_type different → hash different
    h4 = _hash_cle("gemini-embedding-2", "RETRIEVAL_QUERY", "test")
    assert h1 != h4


def test_encodeur_fake_deterministe_entre_instances(tmp_path):
    """Deux `EncodeurFake` avec caches separes doivent produire LE
    MEME vecteur pour le meme texte."""
    import numpy as np
    from bilanlens.embeddings import EncodeurFake

    enc1 = EncodeurFake(cache_dir=tmp_path / "c1")
    enc2 = EncodeurFake(cache_dir=tmp_path / "c2")
    v1, _ = enc1.embed_documents(["Revenus 100 836 224"])
    v2, _ = enc2.embed_documents(["Revenus 100 836 224"])
    assert np.allclose(v1, v2)


# ---------------------------------------------------------------------------
# 8. Garde-fou "N textes → N vecteurs"
# ---------------------------------------------------------------------------
def test_embed_documents_fake_renvoie_N_vecteurs(encodeur_isole):
    """Garde-fou contre le bug "un seul vecteur pour une liste" :
    `embed_documents(N textes)` doit renvoyer un ndarray de shape
    `(N, dim)`, PAS `(1, dim)` ni `(dim,)`.

    Rappel : `gemini-embedding-2` ne batch pas comme `001` (passer
    une liste a `embed_content` renvoie un seul vecteur agrege).
    `_call_embed_batch` fait donc N appels sequentiels. Ce test
    verifie que l'empilement cote `_encoder` est correct.
    """
    textes = [
        f"Chunk unique #{i} pour test N→N shape" for i in range(5)
    ]
    v, _ = encodeur_isole.embed_documents(textes)
    assert v.shape == (len(textes), encodeur_isole.dim), (
        f"shape attendue {(len(textes), encodeur_isole.dim)}, "
        f"obtenu {v.shape}"
    )


def test_cache_tokens_persiste_entre_instances_sur_meme_disque(tmp_path):
    """`_CacheTokens` : une 2e instance sur le meme `cache_dir` relit
    bien les comptages ecrits par la 1re."""
    from bilanlens.embeddings import _CacheTokens, _cle_tokens

    cache_dir = tmp_path / "cache"
    c1 = _CacheTokens(cache_dir, "gemini-embedding-2")
    cle = _cle_tokens("gemini-embedding-2", "Revenus 100 836 224")
    c1.put(cle, 42)
    assert c1.get(cle) == 42

    c2 = _CacheTokens(cache_dir, "gemini-embedding-2")
    assert c2.get(cle) == 42
    # Modele different → pas de collision.
    c3 = _CacheTokens(cache_dir, "BAAI/bge-m3")
    cle_bge = _cle_tokens("BAAI/bge-m3", "Revenus 100 836 224")
    assert c3.get(cle_bge) is None


# ---------------------------------------------------------------------------
# 9. Marker network : API Gemini reelle
# ---------------------------------------------------------------------------
@pytest.mark.network
@pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY absente",
)
def test_encodeur_gemini_vecteurs_natifs_unit_norm(tmp_path):
    """Appel reel API Gemini : vecteurs de norme L2 = 1."""
    import numpy as np
    from dotenv import load_dotenv

    load_dotenv()
    from bilanlens.embeddings import EncodeurGemini, charger_encodeur

    base = charger_encodeur()
    # Reutilise le client, mais cache isole pour ne pas polluer disque
    encodeur = EncodeurGemini(
        client=base.client,
        model=base.model,
        cache_dir=tmp_path / "cache",
    )
    v, stats = encodeur.embed_documents(
        ["Revenus (R.1) 100 836 224", "Total actif 388 668 436"]
    )
    normes = np.linalg.norm(v, axis=1)
    assert v.shape == (2, encodeur.dim)
    assert all(abs(n - 1.0) < 1e-4 for n in normes)
    # `gemini-embedding-2` ne batch pas : N appels pour N textes.
    assert stats["nb_appels_embed"] == 2
    assert stats["tokens_total"] > 0


@pytest.mark.network
@pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY absente",
)
def test_encodeur_gemini_N_textes_renvoie_N_vecteurs_3072(tmp_path):
    """Garde-fou API reelle : 3 textes → shape (3, 3072). Protege
    contre une regression ou on reviendrait au batch (qui agrege en
    un seul vecteur) pour gemini-embedding-2.
    """
    import numpy as np
    from dotenv import load_dotenv

    load_dotenv()
    from bilanlens.embeddings import DEFAULT_DIM, EncodeurGemini, charger_encodeur

    base = charger_encodeur()
    encodeur = EncodeurGemini(
        client=base.client,
        model=base.model,
        cache_dir=tmp_path / "cache",
    )
    textes = [
        "Resultat net 2024 SOTUVER",
        "Total actif consolide SFBT 2024",
        "Capitaux propres Delice Holding 2024",
    ]
    v, _ = encodeur.embed_documents(textes)
    assert v.shape == (3, DEFAULT_DIM), f"shape = {v.shape}"
    # Les 3 vecteurs doivent etre distincts (pas un vecteur agrege
    # dupplique) : on verifie que les cosinus hors-diagonale sont < 1.
    sim = v @ v.T
    assert all(abs(sim[i, i] - 1.0) < 1e-4 for i in range(3))
    hors_diag = [sim[i, j] for i in range(3) for j in range(3) if i != j]
    assert all(s < 0.999 for s in hors_diag), (
        f"vecteurs trop proches, batch regression ? sim = {sim}"
    )
