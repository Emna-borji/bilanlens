# Protocole d'évaluation — benchmark BilanLens

Ce document fixe les règles d'évaluation d'une version de BilanLens
(V1, V2, …) sur `questions.jsonl`. Il complète le benchmark : il ne
le remplace pas, et ne change pas les réponses attendues.

## 1. Objectif

Mesurer trois choses, séparément :

1. **Récupération** : le système retrouve-t-il la bonne page ?
2. **Réponse** : la valeur ou le texte produit colle-t-il à la
   référence ?
3. **Honnêteté** : le système refuse-t-il quand la donnée n'est pas
   dans le PDF ?

## 2. Composition du benchmark

| Catégorie | Nombre | Ce qu'elle évalue |
|---|---|---|
| extraction | 9 | Lire un chiffre déjà publié |
| calcul | 7 | Appliquer une formule du cours sur deux chiffres extraits |
| comparaison | 6 | Comparer une valeur entre deux exercices et nommer la direction |
| texte_annexes | 5 | Récupérer un passage de prose dans les notes |
| sans_reponse | 4 | Refuser quand la donnée n'est pas publiée |
| **Total** | **31** | |

Répartition par entreprise : SOTUVER 8, Monoprix cons. 4, Monoprix
ind. 4, SFBT 5, Ciments de Bizerte 5, Délice Holding 5.

## 3. Métriques

### 3.1 Récupération (sur toutes les questions sauf `sans_reponse`)

| Métrique | Définition | Seuil cible |
|---|---|---|
| Recall@1 | la page citée est la page de référence (`evidence_page_physical`) | ≥ 0,80 |
| Recall@5 | la page de référence est dans les 5 premiers passages | ≥ 0,95 |
| MRR | moyenne de 1 / rang de la bonne page | ≥ 0,85 |

Pour les questions `calcul` et `comparaison` dont les opérandes vivent
sur plusieurs pages, la récupération est jugée réussie si **toutes** les
pages listées dans `intermediate_values[*].evidence_page_physical`
figurent dans le top-k. Voir §6.

### 3.2 Réponse

| Catégorie | Comparaison | Verdict |
|---|---|---|
| extraction, calcul | `|réponse − answer.value|` ≤ `tolerance` | correct / incorrect |
| comparaison | signe(`réponse`) == signe(`answer.value_signed`) **et** `|réponse − answer.value_signed|` ≤ `tolerance` | correct / incorrect |
| texte_annexes | distance éditoriale ou recouvrement de mots-clés sur `evidence_text` | à définir en §4 |
| sans_reponse | le système refuse et cite le motif attendu | correct / incorrect |

### 3.3 Honnêteté (sur les `sans_reponse`)

| Métrique | Définition | Seuil cible |
|---|---|---|
| Taux de refus honnête | refus / nombre de `sans_reponse` | ≥ 0,75 |
| Taux d'hallucination | fausse réponse / nombre de `sans_reponse` | 0 |

Un refus n'est **pas** honnête si la réponse ignore un extrait trompeur
qui existe réellement dans le PDF (ex. Q05 et « prix de vente nets
pratiqués » p. 9 de SOTUVER). Le système doit **justifier** le refus
en citant le passage trouvé et expliquer qu'il ne répond pas à la
question posée.

## 4. Tolérances par format de réponse

| `answer.format` | Tolérance par défaut | Champ qui prime |
|---|---|---|
| `pourcentage` | 0,10 point (0,10 pp) | `tolerance_absolute_pp` |
| `montant` (TND) | 1 unité ou 0,5 % selon précision des opérandes | `tolerance_absolute` |
| `montant_signed` (comparaison) | égalité stricte sur l'entier, direction obligatoire | `tolerance_absolute` |
| `nombre_entier` (ex. nombre d'actions) | égalité stricte | — |
| `texte` | recouvrement ≥ 0,70 avec `evidence_text` après normalisation | — |
| `refus` | motif conforme à `expected_refusal_reason` | — |

**Règle** : si la Q porte un champ `tolerance_absolute*` dans son JSON,
il prime sur la valeur par défaut.

## 5. Règles pour les questions `sans_reponse`

Trois pièges distincts :

1. **Donnée absente du PDF.** C'est le cas typique (ex. Q16 : part de
   marché de la SFBT ; Q26 : part de marché de Ciments de Bizerte).
2. **Formulation équivalente présente dans le PDF.** Piège :
   « dividende distribué » n'est jamais écrit tel quel, mais
   « Dividendes et autres distributions » (p. 4 Délice Holding) ni
   « 0,600 dinars par action » (p. 11) le sont. **Leçon Q30** : la
   donnée est publiée sous un autre nom.
3. **Passage trompeur présent dans le PDF.** Piège : « prix de vente »
   apparaît p. 9 de SOTUVER dans « fondant sur les prix de vente nets
   pratiqués » (évaluation des stocks). **Leçon Q05** : le système
   doit refuser **et** citer ce passage pour montrer qu'il ne répond
   pas à la question.

Pour fabriquer les `expected_absent_keywords` :

- utiliser des **racines** et des **mots isolés** (`distribut`,
  `dividende`, `effectif`), jamais des **expressions composées**
  (`dividende distribué`) qui peuvent être formulées autrement ;
- vérifier automatiquement avec le test `pytest -m real` ;
- si un mot-racine est trouvé, remonter manuellement au contexte et
  décider : vraie absence (retirer le mot) ou vraie Q non-sans-réponse
  (la reclasser).

## 6. Une preuve = une page

`evidence_text` et `evidence_page_physical` au niveau top-level
désignent **le passage principal** de la question : le lecteur du JSONL
sait où aller en premier.

Quand un calcul a plusieurs opérandes sur plusieurs pages (ex. Q23
ROA Ciments de Bizerte : résultat net p. 4, total actif p. 3), chaque
opérande vit dans `calculation.intermediate_values[*]` avec sa propre
`evidence_page_physical` et son propre `evidence_text`. Le top-level
pointe la page du résultat (ou de la variable la plus caractéristique),
pas une concaténation inter-pages.

Le test `test_benchmark_intermediate_values_evidence_present` vérifie
chaque opérande à sa page. Le test `test_benchmark_evidence_text_present_a_la_page`
vérifie le top-level à sa page.

## 7. Convention sur les dividendes

Un rapport annuel publie typiquement **deux** chiffres de dividendes.
Ils ne se confondent jamais :

| Expression | Sens | Où le trouver |
|---|---|---|
| **dividende au titre de l'exercice N** | montant proposé par le conseil d'administration à l'AGO N+1, qui sera (ou non) voté puis versé plus tard | résolutions de l'AGO, note d'affectation du résultat, communication financière |
| **dividende payé pendant l'exercice N** | montant effectivement décaissé pendant l'année civile N, qui correspond au dividende voté par l'AGO au titre de l'exercice N−1 | tableau des flux de trésorerie, ligne « dividendes versés aux actionnaires » |

**Règle de la question** : si l'énoncé mentionne « au titre de
l'exercice », la réponse attendue est le dividende **proposé** ou
**voté** sur ce résultat (Q30 : 32 944 357 TND et 0,600 DT par action
pour Délice Holding sur l'exercice 2024). Si l'énoncé mentionne
« payé pendant » ou « décaissé pendant », la réponse attendue est le
**flux de trésorerie** de l'année (qui correspond au résultat de
l'année précédente).

Le système doit distinguer les deux lignes dans sa recherche.

## 8. Normalisation du texte

Toutes les comparaisons texte (évidence, mots-racines, réponse
`texte_annexes`) passent par la fonction `_normaliser` du test
`tests/test_benchmark.py` :

1. décomposition NFD ;
2. suppression des accents (catégorie Unicode `Mn`) et passage en
   minuscules ;
3. apostrophes typographiques U+2019 ’ et U+2018 ‘ → apostrophe
   droite U+0027 ' ;
4. retrait du trait d'union conditionnel U+00AD (invisible, parfois
   injecté par pdfplumber) ;
5. tout whitespace Unicode (espace, saut de ligne, tabulation, U+00A0
   insécable) collapsé en un espace unique.

Les 4 ensembles de caractères touchés sont **disjoints** : l'ordre
des opérations ne change pas le résultat. L'important est d'appliquer
la **même** normalisation aux deux côtés de la comparaison.

## 9. Validation automatique du benchmark

Le benchmark lui-même est validé par pytest :

| Test | Vérifie | Sans PDF |
|---|---|---|
| `test_benchmark_toutes_lignes_sont_du_json_valide` | chaque ligne est un JSON valide | oui |
| `test_benchmark_ids_uniques` | pas de doublons d'ID | oui |
| `test_benchmark_champs_obligatoires` | `id`, `question`, `category`, `evidence_doc` présents | oui |
| `test_benchmark_coherence_categorie_answer` | sans-réponse ↔ `answer=null`, autre ↔ `answer` non null | oui |
| `test_benchmark_calcul_et_comparaison_ont_formule` | `calculation.formula` + ≥ 2 `intermediate_values` | oui |
| `test_benchmark_calcul_ratios_coherents` | num / den (* 100) ≈ `answer.value` | oui |
| `test_benchmark_comparaison_differences_coherentes` | target − base = `value_signed`, direction cohérente | oui |
| `test_benchmark_evidence_text_present_a_la_page` | top-level `evidence_text` présent à sa page | marker `real` |
| `test_benchmark_intermediate_values_evidence_present` | chaque opérande présent à sa page | marker `real` |
| `test_benchmark_sans_reponse_mots_racines_absents` | mots-racines absents du PDF entier | marker `real` |

Commande (depuis la racine, Windows) :
`.\.venv\Scripts\python.exe -m pytest -v`

Ajouter `-m real` pour ne lancer que les tests qui lisent les PDF.
