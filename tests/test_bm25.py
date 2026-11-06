"""Tests de bilanlens/bm25.py : tokenisation (§3 V2 et V2.1) + index BM25."""
from __future__ import annotations

from bilanlens.bm25 import (
    B,
    IndexBM25,
    K1,
    STOP_WORDS_FR,
    tokeniser,
    tokeniser_v2_1,
)


# ------------------------------------------------------------------
# Tokenisation — règles §3
# ------------------------------------------------------------------

def test_tokeniser_regroupe_nombres_separes_par_un_espace():
    tokens = tokeniser("Revenus 100 836 224 TND")
    assert "100836224" in tokens
    assert "revenus" in tokens
    assert "tnd" in tokens


def test_tokeniser_regroupe_decimal_avec_virgule():
    tokens = tokeniser("montant 1 281 772 854,965 TND")
    assert "1281772854,965" in tokens


def test_tokeniser_regroupe_points_de_milliers():
    assert tokeniser("268.125.000") == ["268125000"]


def test_tokeniser_decoupe_apostrophe_typographique():
    tokens = tokeniser("au titre de l’exercice 2024")
    assert "l" in tokens
    assert "exercice" in tokens
    assert "2024" in tokens


def test_tokeniser_decoupe_apostrophe_droite():
    assert tokeniser("d'actions") == ["d", "actions"]


def test_tokeniser_deux_formats_memes_nombre_produisent_tokens_differents():
    # Documenté §9 : 268 125 000,000 et 268125000 ne sont PAS
    # fusionnés par la tokenisation V2 (pas de normalisation des
    # décimales). C'est une limite connue.
    assert tokeniser("268 125 000,000") == ["268125000,000"]
    assert tokeniser("268125000") == ["268125000"]
    assert tokeniser("268 125 000,000") != tokeniser("268125000")


def test_tokeniser_cas_fusion_colonnes_monoprix_p21():
    # Documenté : 2 fusions de colonnes connues dans
    # monoprix_consolide_2024, page 21. La règle §3 regroupe
    # TOUS les nombres séparés par un seul espace sans détecter
    # la fusion. Résultat attendu : un token unique de 18 chiffres.
    # Pas de règle spéciale pour ce cas.
    assert tokeniser("732 595 162 684 081 159") == [
        "732595162684081159"
    ]


def test_tokeniser_ne_regroupe_pas_double_espace():
    # UN SEUL espace — avec deux espaces (ou plus) entre deux
    # chiffres, la règle ne s'applique pas.
    tokens = tokeniser("100  836  224")
    assert "100836224" not in tokens
    assert "100" in tokens
    assert "836" in tokens
    assert "224" in tokens


def test_tokeniser_retire_accents():
    assert tokeniser("evalues evalues") == ["evalues", "evalues"]
    assert tokeniser("évalués") == ["evalues"]


def test_tokeniser_pas_de_stemming():
    assert "provision" in tokeniser("provision")
    assert "provisions" in tokeniser("provisions")
    assert "provision" not in tokeniser("provisions")


def test_tokeniser_conserve_stop_words():
    # Baseline V2 : on garde les stop words. L'IDF fera le tri.
    tokens = tokeniser("la societe de")
    assert "la" in tokens
    assert "de" in tokens


def test_tokeniser_chaine_vide():
    assert tokeniser("") == []


# ------------------------------------------------------------------
# Index BM25 — construction + recherche + tie-break
# ------------------------------------------------------------------

def test_index_bm25_recherche_basique_remonte_le_bon_chunk():
    chunks = [
        {"chunk_id": "a_p1_s0",
         "texte": "Revenus de l'exercice 100 836 224 TND"},
        {"chunk_id": "a_p2_s0",
         "texte": "Immobilisations corporelles brutes"},
        {"chunk_id": "b_p1_s0",
         "texte": "stocks et provisions courantes"},
    ]
    index = IndexBM25(chunks)
    res = index.rechercher("100 836 224", top_k=3)
    assert len(res) == 3
    assert res[0]["chunk_id"] == "a_p1_s0"
    assert res[0]["rank"] == 1


def test_index_bm25_tie_break_chunk_id_croissant():
    # 3 chunks identiques → même score BM25 → ordre déterministe
    # par chunk_id alphanumérique croissant (règle §3).
    chunks = [
        {"chunk_id": "z_p1_s0", "texte": "stocks"},
        {"chunk_id": "a_p1_s0", "texte": "stocks"},
        {"chunk_id": "m_p1_s0", "texte": "stocks"},
    ]
    index = IndexBM25(chunks)
    res = index.rechercher("stocks", top_k=3)
    assert [r["chunk_id"] for r in res] == [
        "a_p1_s0", "m_p1_s0", "z_p1_s0",
    ]


def test_index_bm25_hyperparametres_figes():
    # Garde-fou : ces 2 valeurs sont les défauts rank_bm25 et
    # ne doivent pas bouger sans décision explicite (§3).
    assert K1 == 1.5
    assert B == 0.75


def test_index_bm25_question_sans_tokens_retourne_vide():
    chunks = [{"chunk_id": "a_p1_s0", "texte": "stocks"}]
    index = IndexBM25(chunks)
    assert index.rechercher("", top_k=5) == []
    assert index.rechercher("...", top_k=5) == []


def test_index_bm25_chunk_vide_ne_fait_pas_planter():
    chunks = [
        {"chunk_id": "a_p1_s0", "texte": "stocks"},
        {"chunk_id": "b_p1_s0", "texte": ""},
    ]
    index = IndexBM25(chunks)
    res = index.rechercher("stocks", top_k=2)
    assert res[0]["chunk_id"] == "a_p1_s0"


# ------------------------------------------------------------------
# V2.1 — stop words français (post-hoc)
# ------------------------------------------------------------------

def test_stop_words_fr_contient_mots_frequents():
    # Garde-fou : la liste NLTK FR versionnée doit contenir les
    # mots fréquents attendus (après normalisation accents).
    attendus = {"de", "et", "la", "le", "les", "du", "des", "a",
                "au", "aux", "en", "une", "un"}
    assert attendus.issubset(STOP_WORDS_FR)


def test_stop_words_fr_contient_mots_courts_apostrophe():
    # « l'exercice » → ["l", "exercice"] en V2. En V2.1, « l »
    # doit disparaître (c'est un stop word NLTK).
    for lettre in ["l", "d", "j", "c", "n", "s", "t", "y", "m"]:
        assert lettre in STOP_WORDS_FR, (
            f"« {lettre} » absente de STOP_WORDS_FR (issue des "
            f"apostrophes françaises)"
        )


def test_stop_words_fr_accents_retires():
    # « été » dans NLTK devient « ete » après normalisation locale
    # (même règle que la tokenisation V2).
    assert "ete" in STOP_WORDS_FR
    assert "etait" in STOP_WORDS_FR
    assert "etaient" in STOP_WORDS_FR
    assert "meme" in STOP_WORDS_FR
    assert "a" in STOP_WORDS_FR  # « à » de NLTK


def test_tokeniser_v2_1_retire_stop_words_simples():
    # « de l'exercice 2024 » : V2 → ["de", "l", "exercice", "2024"]
    # V2.1 → ["exercice", "2024"]
    tokens = tokeniser_v2_1("de l'exercice 2024")
    assert tokens == ["exercice", "2024"]


def test_tokeniser_v2_1_conserve_nombres_et_termes_domaine():
    tokens = tokeniser_v2_1(
        "Revenus de SOTUVER 100 836 224 TND de l'exercice 2024"
    )
    assert "revenus" in tokens
    assert "sotuver" in tokens
    assert "100836224" in tokens
    assert "tnd" in tokens
    assert "exercice" in tokens
    assert "2024" in tokens
    # Stop words retirés :
    for sw in ("de", "l"):
        assert sw not in tokens


def test_tokeniser_v2_1_chaine_vide():
    assert tokeniser_v2_1("") == []


def test_tokeniser_v2_1_tokens_restants_apres_filtre_decroit_ou_egal():
    # Par construction, V2.1 produit au plus autant de tokens que
    # V2 sur n'importe quelle chaîne.
    import random
    random.seed(0)
    for _ in range(50):
        n = random.randint(0, 15)
        mots = random.choices(
            ["de", "stocks", "la", "sfbt", "provision", "100",
             "836", "revenus", "l", "societe"],
            k=n,
        )
        texte = " ".join(mots)
        assert len(tokeniser_v2_1(texte)) <= len(tokeniser(texte))


def test_index_bm25_accepte_tokenizer_v2_1():
    chunks = [
        {"chunk_id": "a_p1_s0",
         "texte": "stocks de la société 100 836 224 TND"},
        {"chunk_id": "b_p1_s0",
         "texte": "immobilisations corporelles"},
    ]
    # Avec V2.1, « de » et « la » disparaissent du corpus.
    index_v2_1 = IndexBM25(chunks, tokenizer=tokeniser_v2_1)
    res = index_v2_1.rechercher("stocks 100 836 224", top_k=2)
    assert res[0]["chunk_id"] == "a_p1_s0"


def test_index_bm25_tokenizer_affecte_score():
    # Le changement de tokenizer DOIT changer le score BM25 sur un
    # corpus assez varié pour que l'IDF ne soit pas identiquement
    # nulle. On construit 6 chunks : 3 contiennent « societe »
    # avec différents stop words, 3 non. Un chunk cible contient
    # « stocks » (terme rare) + plein de stop words.
    chunks = [
        {"chunk_id": "a_p1_s0",
         "texte": "stocks de la societe sotuver financiere"},
        {"chunk_id": "b_p1_s0",
         "texte": "placements autres actifs sotuver"},
        {"chunk_id": "c_p1_s0",
         "texte": "chiffres resultats rapport sotuver exercice"},
        {"chunk_id": "d_p1_s0",
         "texte": "notes annexes amortissements immobilisations"},
        {"chunk_id": "e_p1_s0",
         "texte": "capitaux propres passif bilan"},
        {"chunk_id": "f_p1_s0",
         "texte": "produits charges exploitation activites"},
    ]
    idx_v2 = IndexBM25(chunks)
    idx_v2_1 = IndexBM25(chunks, tokenizer=tokeniser_v2_1)
    # Question : « stocks de la societe » → V2 compte 4 tokens,
    # V2.1 n'en compte que 2 (stocks, societe).
    res_v2 = idx_v2.rechercher("stocks de la societe", top_k=2)
    res_v2_1 = idx_v2_1.rechercher("stocks de la societe", top_k=2)
    # Les deux retournent a_p1_s0 en premier (il contient
    # « stocks » et « societe »).
    assert res_v2[0]["chunk_id"] == "a_p1_s0"
    assert res_v2_1[0]["chunk_id"] == "a_p1_s0"
    # Le score V2.1 doit être différent du V2 (preuve que le
    # filtre modifie effectivement le calcul BM25).
    assert res_v2[0]["score"] != res_v2_1[0]["score"]


def test_index_bm25_meme_tokenisation_pour_chunk_et_question():
    # Règle critique : la question « Revenus 100836224 TND » et
    # le chunk « Revenus 100 836 224 TND » doivent matcher, grâce
    # au regroupement des nombres appliqué des deux côtés.
    chunks = [
        {"chunk_id": "a_p1_s0",
         "texte": "Revenus 100 836 224 TND de l'exercice"},
        {"chunk_id": "a_p2_s0",
         "texte": "Immobilisations autres"},
    ]
    index = IndexBM25(chunks)
    # La même valeur écrite sans espace (comme on peut la trouver
    # côté question si l'auteur du benchmark a collé le nombre)
    res_sans_espace = index.rechercher("100836224", top_k=1)
    # Et la valeur avec espaces (format humain)
    res_avec_espace = index.rechercher("100 836 224", top_k=1)
    assert res_sans_espace[0]["chunk_id"] == "a_p1_s0"
    assert res_avec_espace[0]["chunk_id"] == "a_p1_s0"
