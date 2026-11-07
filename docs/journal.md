# Journal d'apprentissage — BilanLens

Journal libre et chronologique : ce que j'ai appris, les décisions
prises et leur justification. Format : **date — ce que j'ai fait /
pourquoi / ce que j'ai appris**.

---

## 2026-10-23 — Adaptation du planning RAG à BilanLens / BVMT

### Ce que j'ai fait

Deux lots de modifications, préparés pour être commités séparément :

- **Lot A** — correction du référentiel comptable : « SCF tunisien »
  remplacé par « SCE (Système Comptable des Entreprises) » dans
  `README.md`, `bilanlens/extraction.py`, `bilanlens/mapping.py`,
  `tests/test_synthetic_bilans.py` et `docs/pr_fiabilisation.md`.
  Aucun nom de variable, aucune clé de dictionnaire, aucune valeur
  de test modifiée.
- **Lot B** — adaptation complète de `docs/planning.md` au contexte
  BilanLens / BVMT : titre, résumé, objectifs, données/sources,
  méthodologie, planning, risques, sources, ligne CV ; ajout d'une
  section « Adaptation BilanLens / BVMT » en 7 sous-sections.

### Pourquoi

Le planning avait été rédigé pour un projet RAG sur rapports SEC
(FinanceBench). Il fallait l'ancrer dans le vrai contexte : rapports
annuels de la **BVMT**, référentiel comptable **SCE / NCT**, benchmark
Q/A **maison** (30 au départ, 100-150 à terme), machine CPU-only avec
16 GB de RAM (pas de GPU CUDA).

Le terme « SCF tunisien » utilisé dans le code et la documentation
était un abus de langage : **SCF** (Système Comptable Financier)
désigne le référentiel **algérien** (loi 07-11 de 2007). Les rapports
BVMT sont régis par le **SCE** (loi tunisienne 96-112 du 30/12/1996)
et les **normes comptables tunisiennes (NCT 1 à 46)**. Preuves
textuelles extraites des PDF du corpus (SFBT p.6-7, SOTUVER p.7,
Délice Holding p.6, NCT 5 et 6 cités dans SOTUVER p.8).

### Ce que j'ai appris

- **« SCF » n'est pas tunisien.** Système Comptable Financier =
  Algérie (2007). Système Comptable des Entreprises (SCE) + normes
  comptables tunisiennes (NCT 1 à 46) = Tunisie (loi 96-112 de 1996).
- **Vérifier le référentiel dans les documents eux-mêmes** avant de
  l'affirmer dans la documentation : lire les 8 premières pages de
  chaque PDF du corpus suffit souvent.
- **Mesurer sa machine avant de choisir un modèle local.** Sur CPU
  Intel i7-1270P + 16 GB sans GPU dédié, un modèle 7-8 B tient en
  RAM mais répond à 3-6 tokens/s ; un 1,5-4 B tient confortablement
  à 10-20 tokens/s. Choix par défaut : Qwen 3 1.7B/4B ou Phi-4-mini.
- **Un benchmark trop petit est un indicateur de tendance, pas une
  mesure de performance.** 6 émetteurs + 30 questions → à documenter
  honnêtement dans tout partage du projet.
- **Les API gratuites servent surtout de point de comparaison.**
  Groq, Gemini Flash et Mistral Experiment permettent de séparer
  l'effet du pipeline RAG de l'effet de la puissance brute du LLM.
- **La 5ᵉ catégorie du benchmark (questions sans réponse) est la plus
  difficile à construire.** Il faut forger une question crédible dont
  la réponse n'est vraiment pas dans le corpus — risque de « fuite »
  si l'info est planquée dans une annexe oubliée.
- **Pytest + venv sous Windows : le piège.** `pytest.exe` du Python
  système ne voit pas les paquets installés dans `.venv`. Les tests
  marqués `ocr` sont skippés parce que `pytesseract` n'est pas
  importable, alors que le binaire Tesseract est bien là.
  Correction (non appliquée) : activer `.\.venv\Scripts\activate`
  avant `pytest`, ou appeler `.\.venv\Scripts\python.exe -m pytest`.

### Décisions prises

| Décision | Justification |
|---|---|
| Corpus initial = 6 PDF BVMT 2024 déjà présents | Validé, extrait, testé ; pas de dépendance externe |
| Corpus cible = 20-30 sociétés × 2-3 exercices | Volume raisonnable pour un portfolio ; progression graduelle |
| Benchmark 30 → 100-150 Q/A, 5 catégories | Démarrer petit et honnête ; viser une couverture représentative |
| Métriques : B0 ≠ V1+ | B0 n'a rien à retrouver — Recall@k et MRR ne s'y appliquent pas |
| LLM local par défaut = 1,7-4 B | Compatible avec 16 GB CPU-only sans dégrader l'expérience |
| V6 fine-tuning gelé jusqu'à V5 évalué | Priorité à la mesure du gain avant d'ajouter de la complexité |
| Page physique **et** page imprimée stockées séparément | Préserver la traçabilité quand le PDF a sa propre numérotation |

### Tests

- `pytest -v` complet (pytest du Python système) : **65 passed, 2
  skipped en 52,82 s**. Les 2 skipped sont les tests `ocr`, pour la
  raison identifiée ci-dessus.
- `.\.venv\Scripts\python.exe -m pytest -v` : **67 passed, 0 skipped
  en 56,41 s**. Les 2 tests OCR passent correctement dans le venv.

### Documentation et dépôt

- `README.md` et `CLAUDE.md` documentent désormais la commande
  pytest à utiliser (`.\.venv\Scripts\python.exe -m pytest -v`).
- `.gitignore` étendu pour exclure le PDF original du planning
  (`/FinSight Agent*.pdf`) et le fichier personnel `/notes` : le
  dépôt est public.

---

## 2026-10-24 — Benchmark semaine 1 : premières questions SOTUVER

### Ce que j'ai fait

- Expliqué le format **JSONL** et sa structure champ par champ.
- Fixé 3 décisions mineures : `evidence_page_printed` en chaîne (D1),
  valeurs intermédiaires + formule pour les Q de calcul (D2),
  `expected_refusal_reason` catégorisé pour les Q sans réponse (D3).
- Proposé 5 questions d'exemple sur `real_sotuver_2024.pdf`, une par
  catégorie (extraction, calcul, comparaison, texte annexes, sans
  réponse) **sans remplir les réponses**.
- J'ai annoté les 5 questions moi-même (valeurs, pages, extraits).
- Vérification indépendante par pdfplumber : zéro désaccord factuel
  sur les 4 premières questions, zéro occurrence des 5 mots-clés de
  Q5 dans les 37 pages du PDF (catégorie sans_reponse confirmée).
- Création de `data/benchmark/questions.jsonl` : 5 lignes JSON
  valides, IDs uniques, cohérence catégorie / champs vérifiée.

### Ce que j'ai appris

- **JSONL vs CSV** : un `evidence_text` contient virgules, guillemets
  et retours à la ligne — JSON les échappe proprement, CSV casse.
  Et une ligne corrompue en JSONL ne fait perdre qu'une question.
- **Pages imprimées hétérogènes** : romain `"iv"`, préfixé `"A-1"`,
  manquant → stocker en chaîne (`null` si absent) et pas en entier.
- **Deux colonnes 2023 chez SOTUVER** : une publiée, une retraitée
  (note III.3). Pour le résultat net 2023, les deux sont identiques
  à 38 191 627 TND, mais le choix doit être explicite dans l'énoncé
  car d'autres postes peuvent différer.
- **Piège Q4 détecté par moi-même** : les notes annexes (p. 9) disent
  « au plus bas du coût de production et de la valeur de réalisation
  nette », tandis que le rapport des commissaires (p. 28-29) parle
  de « coût moyen pondéré ». Deux sources, deux formulations — un
  benchmark qui ne précise pas la source est ambigu.
- **Q5 « sans réponse » bien construite** : recherche exhaustive de
  5 mots-clés sur 37 pages → zéro occurrence. Un rapport annuel ne
  publie pas de prix de vente unitaire par bouteille.

### Décisions prises

| Décision | Justification |
|---|---|
| JSONL comme format du benchmark | Diff git lisible, 1 Q = 1 ligne, pas de corruption en chaîne |
| `evidence_page_printed` en chaîne ou `null` | Numéros romains, préfixés ou absents |
| Pour les Q calcul : stocker valeurs intermédiaires + formule | Évaluer séparément l'extraction et le calcul |
| Pour les Q sans réponse : `expected_refusal_reason` typé | Catégoriser les refus (donnée non publiée / hors période / hors périmètre) |
| Reformulation Q3 : préciser la colonne 2023 publiée | Rendre la question reproductible même si une future version du rapport sépare publiée et retraitée |
| Note Q4 : documenter le piège rapport commissaires vs notes | Préparer une Q piège complémentaire future qui teste la métadonnée de section |

### Livrables

- `data/benchmark/questions.jsonl` : 5 questions SOTUVER 2024.

---

## 2026-10-24 (suite) — Benchmark : densification à 30 questions sur 6 PDFs

### Ce que j'ai fait

- Changement de méthode à la demande de l'utilisateur : je propose
  moi-même les 25 questions restantes avec leurs réponses complètes,
  l'utilisateur validera ensuite. Répartition imposée : 7 extraction,
  6 calcul, 5 comparaison, 4 texte annexes, 3 sans réponse ; ~4-5 Q
  par entreprise ; pièges spécifiques (colonnes 2023 publiée/retraitée,
  comptes consolidés, notes vs commissaires, unités SFBT décimales).
- Exploration des 6 PDFs : cartographie des pages (bilan actif/passif,
  état de résultat, notes règles comptables, commissaires), extraction
  des valeurs 2023 pour les comparaisons.
- Rédaction des 25 Q + validation automatique par pdfplumber (chaque
  extrait présent à la page indiquée, chaque mot-clé des « sans
  réponse » absent du PDF) + revérification arithmétique des calculs
  (ratios et différences, signe inclus).
- Correction en cours de route : Q16 et Q26 refondues (le piège
  « part de marché » est garanti non publié, contrairement à mes
  premières idées qui étaient en réalité présentes dans les PDFs —
  SNMVT International + Libye apparaissent p.14 et p.30 de Monoprix
  individuel, « clients étrangers » apparaît chez Ciments de Bizerte).
  Q07 : formule corrigée pour cohérence signe/direction.

### Ce que j'ai appris

- **Vérification au corps-à-corps est non négociable.** Deux de mes
  trois premières Q « sans réponse » étaient en réalité des Q
  « extraction » — leurs mots-clés étaient dans le PDF. Sans la
  recherche globale avant écriture, on aurait eu des faux refus.
- **Convention des deltas** : pour toute comparaison, formule =
  `valeur_target - valeur_base` (nouvelle - ancienne). Cela aligne
  automatiquement le signe de `value_signed` et le `direction`.
- **Lecture pdfplumber ≠ texte copié**. Les sauts de ligne, l'espace
  avant/après le signe négatif (`-44790 355`) et les apostrophes
  typographiques diffèrent du copier-coller humain. Il faut normaliser
  (accents, casse, parfois espaces) pour comparer.
- **Monoprix consolidé vs individuel** : exemple d'école de pièges
  comptables. CA individuel 732,6 M vs consolidé 754,0 M ; résultat
  net individuel 6 834 166 vs consolidé part du groupe 6 872 913 ;
  les filiales exclues (SNMVT INTERNATIONAL, UNITED DECS) apparaissent
  à la fois dans la note des titres de participation individuels et
  dans les notes de consolidation.
- **SOTUVER colonnes 2023** : le reclassement rétrospectif des moules
  (NCT 11) crée la double colonne publiée/retraitée, avec un
  basculement de 18 577 651 TND de Stocks vers Immobilisations
  corporelles. C'est le vrai exemple de l'ambiguïté dont parlait R2
  des questions précédentes.
- **SFBT décimales** : seule des 6 sociétés à publier en dinars avec
  3 décimales (ex. 1 281 772 854,965). C'est le piège unités du
  benchmark.

### Décisions prises

| Décision | Justification |
|---|---|
| Formule des comparaisons = `target - base` (nouvelle - ancienne) | Signe cohérent avec `value_signed`, sens cohérent avec `direction` |
| Q « sans réponse » : parts de marché, nombre de salariés Délice Holding, prix de vente unitaire | Vérifiées absentes dans les PDFs ciblés avec recherche de racines (effectif, salari, concurrent, part de marche…) et mots isolés |
| Pour les Q de calcul, intermediate_values garde le numérateur en premier et le dénominateur en second | Cohérent avec l'ordre de la formule |
| Pour la Q Q10 (Monoprix cons), on prend CP part du groupe (comme BilanLens) | Documenté dans la note ; alternative CP+minoritaires signalée |

### Validation finale (après correction utilisateur)

- **31 questions totales** dans `data/benchmark/questions.jsonl`.
- 31 lignes JSON valides, 31 IDs uniques, catégorie / champs cohérents.
- Répartition catégories : **9 extraction, 7 calcul, 6 comparaison,
  5 texte annexes, 4 sans réponse**.
- Répartition entreprises : SOTUVER 8, Monoprix consolidé 4,
  Monoprix individuel 4, SFBT 5, Ciments de Bizerte 5, Délice Holding 5.
- Tous les calculs vérifiés arithmétiquement (ratios et différences).
- Tous les extraits vérifiés présents à la page indiquée (après
  normalisation accents/casse).
- Toutes les Q « sans réponse » : mots-clés absents dans tout le PDF
  (recherche par racines : effectif, salari, employe, concurrent,
  marche tunisien, etc.).

### Correction post-validation utilisateur

- **Q30 (Délice Holding) requalifiée** : relecture manuelle utilisateur
  → la donnée est bien publiée (p.4 : « Dividendes et autres
  distributions B-8 (32 944 357) » ; p.11 : « Distribution des
  dividendes (0,600 dinars par action) (32 944 357) »). Q30 devient
  une Q d'extraction (32 944 357 TND, soit 0,600 DT par action).
- **Q15 (Monoprix individuel) précisée** : l'énoncé spécifie
  maintenant la ligne « Résultat net » (5 876 040 en 2023), hors
  effet des modifications comptables (3 064 889).
- **Q31 (nouvelle sans-réponse)** : nombre de salariés de Délice
  Holding — mots-clés `effectif`, `salari`, `employe` tous absents.
- **Leçon apprise** : pour les Q « sans réponse », chercher des
  racines (`distribut`, `dividende` isolé) et pas seulement des
  expressions composées (`dividende distribué`). Mes 2 premières
  Q « sans réponse » avant correction cherchaient des phrases trop
  longues qui ne correspondaient pas à la formulation du PDF.

---

## 2026-10-24 (suite 2) — Outil de validation du benchmark en pytest

### Ce que j'ai fait

- Création de `tests/test_benchmark.py` : 11 tests qui vérifient
  (1) la structure JSONL / catégorie / champs, (2) l'arithmétique
  des Q calcul et comparaison (signe inclus), (3) la présence de
  chaque `evidence_text` et de chaque `intermediate_values[*].evidence_text`
  à la page physique indiquée (marker `real`), (4) l'absence des
  `expected_absent_keywords` dans tout le PDF pour les Q sans réponse
  (marker `real`).
- Enrichissement du JSONL : ajout du champ `expected_absent_keywords`
  (racines/mots isolés) sur les 4 Q sans réponse.
- Le test m'a immédiatement remonté 5 vraies incohérences dans mes
  annotations, que j'ai corrigées :

  | Q | Problème | Correction |
  |---|---|---|
  | Q02 | Extrait omettait `(B.9)` et les colonnes 2023 publiée/retraitée | Extrait complet collé du PDF |
  | Q04 | PDF a des sauts de ligne au milieu des phrases | Normalisation whitespace : `" ".join(s.split())` dans `_normaliser` |
  | Q08 / Q25 | Apostrophe droite `'` dans annotation vs typographique `'` dans PDF | `_normaliser` remplace U+2019 → U+0027 |
  | Q23 / Q28 | `evidence_text` top-level mélangeait deux pages, mais `evidence_page_physical` pointe sur une seule | Simplification à la page concernée (l'intermédiaire sur une autre page est déjà vérifié séparément) |
  | Q05 | « prix de vente » trouvé dans le PDF (contexte générique sur l'évaluation des stocks) | Retiré de `expected_absent_keywords` ; `bouteille` + `prix unitaire` + `prix moyen` suffisent |

### Ce que j'ai appris

- **Un outil de validation révèle ce qu'une relecture humaine seule
  rate**. Les 5 corrections ci-dessus n'auraient pas été vues
  manuellement — Q02 avait l'air juste à l'oeil, Q08 et Q25 ont des
  apostrophes qu'un humain lit sans distinguer, Q23 et Q28 avaient
  des `evidence_text` plausibles mais incohérents avec la page.
- **Normalisation whitespace et apostrophes**, c'est **non négociable**
  quand on compare un texte annoté à la main avec un texte extrait
  par pdfplumber. Les apostrophes typographiques `'` (U+2019) sont
  invisibles à l'oeil mais fatales pour un `in`.
- **Convention `evidence_text` top-level** : doit tenir sur la page
  physique indiquée. Les valeurs intermédiaires qui pointent sur
  d'autres pages ont leurs propres `evidence_page_physical` et sont
  vérifiées séparément.
- **Racines plutôt que mots entiers** : « prix de vente » comme mot
  entier est généralement présent (contexte comptable). Pour prouver
  qu'une Q est sans réponse, préférer des termes discriminants
  (`prix unitaire`, `prix moyen`, nom du produit) que des mots
  comptables courants.
- **Le pipeline du test est utilisable en CI** : il tourne en 35 s
  sur mon poste et ne demande aucune ressource externe. Les markers
  `real` sont exécutés en CI (voir `.github/workflows/tests.yml`).

### Décisions prises

| Décision | Justification |
|---|---|
| `_normaliser` fait 4 opérations : NFD + suppression Mn + lowercase + apostrophes + whitespace flatten | Robustesse contre tous les pièges invisibles du PDF |
| Les Q sans réponse portent elles-mêmes leurs mots-racines (`expected_absent_keywords`) | Chaque Q est auto-descriptive ; le test est générique |
| `evidence_text` top-level ne doit référer qu'à la page `evidence_page_physical` | Simplifie la validation ; les intermédiaires d'autres pages sont dans `intermediate_values` |
| Marker `real` pour les tests qui ouvrent les PDFs | Convention existante du projet (voir `tests/test_real_bilans.py`) |

### Fichiers modifiés

- `tests/test_benchmark.py` : nouveau, 11 tests.
- `data/benchmark/questions.jsonl` : enrichi (`expected_absent_keywords`)
  et corrigé (Q02, Q23, Q28, Q05 notes).

---

## 2026-10-26 — Protocole d'évaluation + trait d'union conditionnel

### Ce que j'ai fait

- Ajouté le retrait du **trait d'union conditionnel U+00AD** à
  `_normaliser` (`tests/test_benchmark.py`), avec un test unitaire
  `test_normaliser_retire_le_trait_dunion_conditionnel`. Les 4 opérations
  précédentes agissent sur des caractères disjoints, le 5ᵉ aussi ;
  l'ordre reste commutatif.
- Vérifié que Q23 (ROA Ciments de Bizerte) et Q28 (ROE Délice Holding)
  portent bien **leurs deux opérandes** dans `intermediate_values`
  avec `evidence_page_physical` et `evidence_text` distincts
  (Q23 : résultat net p. 4 + total actif p. 2 ; Q28 : résultat net p. 3
  + capitaux propres p. 2). La simplification de l'`evidence_text`
  top-level n'a rien fait disparaître.
- **Correction Q23** : la précédente annotation du `total_actif`
  citait la ligne « Total des capitaux propres et des passifs
  388 668 436 » de la page 3. Même montant par équilibre comptable,
  mais c'est la ligne du **passif**, pas de l'actif. La bonne ligne
  est page 2 : « Total des Actifs 388 668 436 241 664 543 ». Corrigé.
- Rédigé `data/benchmark/protocole.md` : 9 sections courtes, un
  tableau par type de mesure, une section « Une preuve = une page »
  (leçon Q23/Q28), une section « Convention sur les dividendes »
  (« au titre de l'exercice » vs « payé pendant l'exercice », leçon
  Q30), une section sur les 3 pièges des Q `sans_reponse`
  (absence vraie / formulation équivalente / passage trompeur, leçon
  Q05).

### Pourquoi

Deux manques distincts :

1. **Technique** : U+00AD est invisible à l'écran, échappe à
   `split()` (il n'est pas de classe whitespace Unicode), et certains
   PDF l'injectent lors de l'export. Sans son retrait, une annotation
   `"intermédiaire"` ne matcherait pas un PDF portant
   `"inter­médiaire"` — bug silencieux.
2. **Protocole** : le benchmark seul ne dit pas **comment** on
   l'évalue. Sans tolérances écrites, sans conventions documentées
   (dividendes au titre de / payés pendant), sans règles sur les
   sans-réponse, chaque exécution de V1/V2 pourrait se juger
   différemment.

### Ce que j'ai appris

- **Un benchmark a toujours un protocole frère.** Le benchmark fixe
  les **questions et réponses attendues** ; le protocole fixe le
  **cadre d'interprétation** (tolérances, règles de refus,
  conventions sémantiques). Les deux doivent évoluer ensemble.
- **« Une preuve = une page »** est une règle structurelle qui rend
  l'annotation testable. Si une preuve top-level enjambait deux
  pages, le test ne pourrait pas la vérifier page par page. Les
  opérandes multi-pages descendent dans `intermediate_values[*]`,
  chacun sur sa page.
- **La convention « au titre de » vs « payé pendant »** vient
  directement du cours de finance d'entreprise : un dividende proposé
  par le conseil d'administration à l'AGO n'est pas un décaissement.
  Le premier est dans la note d'affectation du résultat, le second
  dans le TFT (flux de financement). Confondre les deux fait entrer
  dans le même ratio deux chiffres qui portent sur deux exercices
  différents.
- **Trois pièges des sans-réponse** : (a) donnée absente, (b)
  publiée sous un autre nom (Q30), (c) passage trompeur
  (Q05 « prix de vente nets pratiqués »). Le système doit refuser
  **en citant** le passage trompeur, pas en l'ignorant.

### Décisions prises

| Décision | Justification |
|---|---|
| `_normaliser` passe à 5 opérations (ajout U+00AD) | Pièges invisibles futurs couverts par un replace explicite |
| Protocole dans `data/benchmark/protocole.md` et non `docs/` | Il fait partie du benchmark, pas de la documentation générale |
| Récupération jugée OK si **toutes** les pages des `intermediate_values` sont dans le top-k | Un calcul n'est bon que si tous ses opérandes ont été retrouvés |
| Taux d'hallucination cible = 0 pour les `sans_reponse` | Un rapport annuel n'invente pas ; le système ne doit pas non plus |

### Fichiers modifiés

- `tests/test_benchmark.py` : ajout U+00AD + test unitaire.
- `data/benchmark/protocole.md` : nouveau, 9 sections.

---

## 2026-10-26 (suite) — Semaine 2, étape 2 EN COURS (pause)

### Où on en est

**Étape 2 du planning (couche d'abstraction LLM) : commencée, en pause
avant la contribution humaine.**

### Choix validés pour la semaine 2 (A/B/C/D du planning)

| Choix | Décision |
|---|---|
| A — LLM | Hybride : API gratuite **Gemini Flash** maintenant, Ollama (Qwen3-1.7B / 4B ou Phi-4-mini, max 4B) plus tard (semaine 7-8). Température 0. Version du modèle enregistrée dans chaque fichier de résultats pour reproductibilité. |
| B — Chunking | Par **page physique**, avec sous-découpage pour les pages trop longues qui préserve la ligne d'en-tête de colonnes (ex. « 31/12/2024 31/12/2023 »). |
| C — Embeddings | **bge-m3** (pas MiniLM : son max_seq_length de 128 tokens tronquerait nos chunks, dont le seuil est paramétrable, 4000 car. par défaut pour V1 ≈ 1200 tokens, à comparer plus tard avec 1500 car. sur le benchmark). À l'implémentation, afficher explicitement le max_seq_length du modèle chargé. |
| D — Index | **Chroma** (métadonnées natives : entreprise, exercice, page_physique). |

Note : les seuils Recall/MRR du protocole §3.1 sont des objectifs, pas
des critères de passage.

### Avancement micro-étapes de l'étape 2

| Micro-étape | État |
|---|---|
| 2a — `requirements.txt` : ajout `google-genai>=0.3` + `python-dotenv>=1.0` | ✅ fait |
| 2b — `.env.example` versionné (clé `GEMINI_API_KEY=`) ; `.env` déjà gitignoré | ✅ fait |
| 2c — `pytest.ini` : nouveau marker `network` pour les tests tapant une API externe | ✅ fait |
| 2d — `bilanlens/llm.py` : `LLMResponse` dataclass + Protocol `LLM` + classe `GeminiLLM` + `ErreurQuotaDepassee` + factory `creer_llm` + `list_models()` | ✅ fait **sauf** le corps de `_appel_avec_backoff` (TODO(human)) |
| 2e — Humain écrit le backoff (5-7 lignes dans `_appel_avec_backoff`) | ⏸️ **pause ici** |
| 2f — `tests/test_llm.py` : test de la dataclass + test du Protocol (`isinstance` grâce à `@runtime_checkable`) + test mocké du happy path + test marker `network` (appel réel) | 🕐 à faire après 2e |
| 2g — Lancer `.\.venv\Scripts\python.exe -m pytest -v` : tout vert | 🕐 à faire après 2f |

### Détails techniques fixés dans `bilanlens/llm.py`

- `GeminiLLM.DEFAULT_MODEL = "gemini-2.5-flash"`. Vérification au
  runtime via `list_models()` avant chaque run (Google a changé les
  modèles stables en avril 2026 ; `gemini-3.5-flash` GA depuis
  mai 2026 et `gemini-3.6-flash` depuis juillet 2026 sont aussi
  envisageables, à confirmer au moment d'exécuter B0).
- Classe `GeminiLLM` : import tardif de `google.genai` dans
  `__init__`, et dans `generate()` import tardif de `types`. Permet
  aux tests mockés de ne pas exiger la lib installée.
- `LLMResponse` est `@dataclass(frozen=True)` (immuable) : garantit
  que le fichier de résultats écrit en JSON ne pourra pas être muté
  après coup.
- `LLM` Protocol est `@runtime_checkable` : `isinstance(llm, LLM)`
  vérifie uniquement la présence de `generate` (duck typing). La
  garantie statique viendra d'un passage mypy/pyright en CI (à
  prévoir après la semaine 2).
- Sécurité clé API : jamais incluse dans `LLMResponse`, jamais loggée,
  jamais écrite dans `results/*.jsonl`. Rappel pour la revue avant
  chaque commit.

### Dette technique à adresser

- Logique de reprise d'un run interrompu (si le quota 429 persiste
  après N tentatives) : à écrire dans `evaluate_b0.py` à l'étape 5
  (checkpoint sur l'ID de la Q, re-lecture au démarrage du script).

### Reprise

Après la pause, retrouver le `TODO(human)` dans la méthode
`_appel_avec_backoff` de `bilanlens/llm.py`. L'énoncé Learn by Doing
est reproduit dans la conversation précédente ; les contraintes :

- jusqu'à `max_tentatives` tentatives (défaut 5) ;
- sur `errors.ClientError` avec `.code == 429` : `time.sleep(duree)`
  puis réessayer ;
- `duree` initiale 2 s, doublée à chaque reprise (2, 4, 8, 16) ;
- pas d'attente après la dernière tentative ;
- toute autre erreur se propage immédiatement ;
- épuisement du quota → lever `ErreurQuotaDepassee`.

Appel bloquant à passer dans la boucle :

```python
self._client.models.generate_content(
    model=self._model, contents=prompt, config=config
)
```

### Fichiers modifiés dans la session

- `requirements.txt` : + `google-genai>=0.3`, + `python-dotenv>=1.0`.
- `.env.example` : nouveau, versionné (clé vide).
- `pytest.ini` : + marker `network`.
- `bilanlens/llm.py` : nouveau, 1 TODO(human) restant.

---

## 2026-10-27 — Semaine 2, étape 2 TERMINÉE

### Reprise après pause

Le `TODO(human)` du backoff n'a pas été rédigé à la main : contribution
reprise par l'assistant selon les contraintes du journal.

### Micro-étapes 2e-2g faites

| Micro-étape | Résultat |
|---|---|
| 2e — Corps de `_appel_avec_backoff` écrit (backoff exponentiel [2, 4, 8, 16] s, max 5 tentatives, 429 réessayé, autres erreurs propagées, `ErreurQuotaDepassee` sur quota épuisé) | ✅ |
| 2e-bis — `DEFAULT_MODEL` : `"gemini-2.5-flash"` → `"gemini-3.5-flash"` (stable depuis mai 2026 selon la vérif WebSearch 2026-10-26) | ✅ |
| 2f — `tests/test_llm.py` : 9 tests (dataclass auto-descriptive, dataclass immuable, Protocol runtime_checkable, happy path mocké, 429 puis succès, 403 remonte immédiatement, quota épuisé lève ErreurQuotaDepassee, factory erreur sur fournisseur inconnu, appel réel marker `network`) | ✅ |
| 2g — Suite complète pytest : **88 passed** en 1 min 40 s (79 anciens + 9 nouveaux). Test réseau inclus, a réellement tapé Gemini. | ✅ |
| 2h — Vérification de fuite de clé : **5/5 OK** (clé 53 car. absente des 59 fichiers suivis par Git, du `git diff`, du `git diff --cached`, pas de `results/` encore, `.env` ignoré par `.gitignore` ligne 19) | ✅ |

### Choix d'implémentation du backoff (expliqué)

- **Exponentiel plutôt que linéaire** : avec un free tier à 10 RPM
  (1 appel/6 s), un backoff démarrant à 2 s a de bonnes chances de
  passer dès la 2ᵉ ou 3ᵉ tentative. En linéaire à 6 s partout, on
  attendrait toujours au moins 6 s même si le quota se libère à 2 s.
- **Pas d'attente après la dernière tentative** : on gagne la durée
  finale (ici 32 s de wait sauvées) et surtout `ErreurQuotaDepassee`
  arrive aussitôt que la 5ᵉ tentative échoue, ce qui laisse une marge
  au script d'évaluation de l'étape 5 pour sauver un checkpoint et
  arrêter proprement.
- **Toute erreur ≠ 429 remonte immédiatement** : réessayer sur un 403
  (clé invalide) ou 400 (prompt mal formé) n'y changerait rien ; mieux
  vaut planter vite et clairement.

### Patterns de test à retenir

- **Faux `errors.ClientError` via `__new__`** : contourne la variation
  de signature du constructeur entre versions de google-genai.
  `ClientError.__new__(ClientError)` + attributs posés à la main
  (`code`, `message`, `args`, `status`).
- **`@patch("bilanlens.llm.time.sleep")`** : patch local au module
  testé, pas global. Permet d'inspecter `call_count` et `call_args_list`
  pour tester **exactement** la progression des délais.
- **`isinstance(adapter, LLM)` avec `@runtime_checkable`** : vérifie
  uniquement la présence des méthodes du Protocol, pas leur signature.
  Pour une vérification stricte, prévoir mypy ou pyright en CI.

### Décisions prises

| Décision | Justification |
|---|---|
| `GeminiLLM.DEFAULT_MODEL = "gemini-3.5-flash"` | Stable (GA mai 2026), aliasé par `gemini-flash-latest` ; alternative plus récente `gemini-3.6-flash` (GA juillet 2026) à envisager plus tard |
| Backoff démarrant à 2 s, exponentiel, max 5 tentatives | Converge rapidement sur free tier 10 RPM ; durée totale max 30 s |
| `LLMResponse` dataclass `frozen=True` | Garantit qu'un script ne peut pas muter la réponse avant écriture dans `results/*.jsonl` |
| Marker `network` plutôt que mock systématique | Permet un test de contrat réel au cas par cas sans impacter la CI gratuite |

### Fichiers modifiés dans la session (final)

- `requirements.txt` : + `google-genai>=0.3`, + `python-dotenv>=1.0`.
- `.env.example` : nouveau, versionné (clé vide).
- `pytest.ini` : + marker `network` + `addopts = -m "not network"`
  (exclusion par défaut : le free tier a un quota de 250 appels/jour,
  tapper l'API à chaque `pytest` l'épuiserait en 2 jours de debug).
- `bilanlens/llm.py` : nouveau (~130 lignes, backoff complet).
- `tests/test_llm.py` : nouveau (9 tests). `load_dotenv()` au niveau
  module + `@pytest.mark.skipif(not GEMINI_API_KEY)` sur le test réel
  pour que la CI GitHub reste verte même sans secret configuré.

### Correction après questions de vérification (2026-10-27 soir)

Trois décisions issues des réponses de vérification :
1. `pytest -m network` ne doit pas être inclus dans la suite par
   défaut (sinon 100 lancements = 100 appels API). Ajouté
   `addopts = -m "not network"` dans `pytest.ini` ; `-m network` sur
   la ligne de commande écrase cette directive, comportement idiomatique.
2. Le fallback inline `if not GEMINI_API_KEY: load_dotenv()` dans le
   corps du test est remplacé par un `@pytest.mark.skipif` déclaratif,
   évalué à la collection. `load_dotenv()` est appelé une seule fois
   au niveau du module de tests, avant que le décorateur ne lise
   l'environnement.
3. Vérification empirique : `pytest -v` → 87 passed, 1 deselected ;
   `pytest -m network` → 1 passed, 87 deselected.

---

## 2026-10-31 — Semaine 2, étape 3 : chunking par page physique

### Ce que j'ai fait

Nouveau module `bilanlens/chunks.py` : dataclass `Chunk` (frozen,
to_dict/from_dict JSONL), `extraire_pages(pdf_path, seuil_vide_chars=30)`,
`detecter_entete(lignes)` et `decouper_page(..., seuil_chars=4000)`.
Trois refactorings pour supprimer la duplication avec `extraction.py` :

- Un helper partagé `_grouper_mots_par_ligne(page, tolerance_y)` dans
  `extraction.py`, consommé par `_pdf_page_text` (reconstruction du
  texte) et `_extraire_lignes_periodes_depuis_page_pdf` (extraction par
  coordonnées) : une seule logique de bucketing visuel.
- `_ocr_pages(pdf_source, indices_cibles, avec_mots)` déplacé dans
  `extraction.py`, `_ocr_pdf_octets` devient un wrapper trivial qui
  concatène. Une seule boucle PyMuPDF + Tesseract.
- Seuil de colonne de `_pdf_page_text` rendu relatif à la hauteur du
  mot (`facteur_colonne=1.0`) : plus de constante magique à 5 px, le
  seuil suit automatiquement la taille de police.

Côté tests, 28 nouveaux tests dans `tests/test_chunks.py` :
dataclass (5), extraction (4 dont « colonnes non collées sur SOTUVER »),
`_pdf_page_text` (1 : seuil relatif, `3 500` reste intact et colonnes
voisines séparées), détection d'en-tête (8 dont fenêtre bornée aux 10
premières lignes), découpage (9 dont pas de chevauchement et ligne
très longue émise telle quelle).

### Pourquoi

Un chunk par page physique garde l'ancrage « doc, page » du benchmark
(`evidence_page_physical` dans `questions.jsonl`). L'OCR ne tourne que
sur les pages sous seuil (30 car. par défaut) : économise ~90 % du
temps sur un PDF majoritairement natif.

Un en-tête de colonnes répété en haut de chaque sous-morceau conserve
le sens des chiffres : sans « Rubriques Notes 31/12/2024 31/12/2023 »,
un vecteur embedding d'un sous-morceau N≥2 verrait « 100 836 224
165 986 659 » sans savoir que c'est l'exercice courant vs précédent.

### Ce que j'ai appris

- **`dataclass(frozen=True)` + `asdict()`** : garantit qu'un `Chunk`
  écrit dans `data/chunks/*.jsonl` ne peut pas être muté entre
  sérialisation et relecture. L'invariant est exploité par les tests.
- **Reconstruction de texte depuis les mots** : `page.extract_text()`
  colle parfois des colonnes proches ; passer par
  `page.extract_words()` + regroupage par position (`top` ± tolérance,
  tri par `x0`) donne un contrôle fin sur les séparateurs.
- **Seuil adaptatif** : comparer un écart (en pixels) à une mesure du
  contenu (hauteur du glyphe) plutôt qu'à une constante produit un
  détecteur de colonnes qui tient sur toute la plage de tailles de
  police. Un seuil fixe à 5 px cassait dès qu'on changeait de corps.
- **Fenêtre d'en-tête bornée** : chercher le motif « 2 dates OU 2
  années » sur toute la page attrape des phrases du corps comme
  « Au cours de 2024, par rapport à 2023 ». Limiter aux 10 premières
  lignes non vides est un garde-fou simple et efficace.

### Décisions prises

| Décision | Justification |
|---|---|
| `sous_numero = 0` pour une page intacte, 1-N pour les sous-morceaux | Distingue sans ambiguïté « page tenant dans un chunk » et « page découpée » ; les tests du benchmark peuvent assertir sur l'un ou l'autre |
| `page_imprimee: str \| None` | Chiffres romains possibles (`"II"`, `"IV"`), suffixes (`"A-3"`), ou absence (page de garde) ; `str` garde la souplesse |
| `exercice: int` | Les filtres Chroma (`exercice >= 2020`) perdent silencieusement si on sérialise en str |
| Préambule = titre + en-tête de colonnes, dédup si identiques | Permet de garder « BILAN » quand l'en-tête est différent, sans doublon quand l'en-tête commence par le titre |
| Seuil 4000 car. configurable | ~1 page A4 dense de bilan tunisien ; au-delà on gagne à sous-découper |
| Qdrant → Chroma dans `planning.md` | Choix D validé : installation Python pure, pas de serveur à faire tourner |

### Fichiers modifiés dans la session

- `bilanlens/extraction.py` : + `_grouper_mots_par_ligne`,
  `_pdf_page_text` (seuil relatif), `_ocr_pages` (déplacé depuis
  chunks.py avec `avec_mots: bool`), `_ocr_pdf_octets` simplifié,
  `_extraire_lignes_periodes_depuis_page_pdf` refactorisé pour
  utiliser le helper.
- `bilanlens/chunks.py` : nouveau. `Chunk`, `extraire_pages`,
  `detecter_entete`, `decouper_page`.
- `tests/test_chunks.py` : nouveau, 28 tests.
- `docs/planning.md` : Qdrant → Chroma.

### Résultat

Suite complète : **114 passed, 1 deselected en 1 min 25 s**
(marker `network` déselectionné par défaut via `pytest.ini`).

---

## 2026-10-31 (soir) — Étape 5 : script chunk_corpus.py + colonne OCR_TENT. + test de couverture

### Ce que j'ai fait

- `scripts/chunk_corpus.py` : parcourt les 6 PDFs annotes dans
  `tests/data/real_*.pdf`, chunk-ise chacun via `extraire_pages` +
  `decouper_page`, et ecrit un `data/chunks/<doc>.jsonl` par document.
  Mapping explicite fichier -> (doc, entreprise, exercice).
- Tableau de stats a la fin : PAGES, CHUNKS, DECOUP., OCR_TENT.,
  OCR_OK, VIDES. **OCR_TENT. != OCR_OK** : une page candidate (natif
  < 30 car.) peut etre tentee mais ne rien renvoyer (page de
  separation sans contenu). Si Tesseract est absent, OCR_TENT. tombe
  a 0 partout meme si des pages sont candidates : la desactivation
  silencieuse de l'OCR saute aux yeux.
- `tests/test_chunks_couverture_benchmark.py` : 2 tests qui chargent
  `data/chunks/*.jsonl` et verifient que chaque segment >= 10 car.
  d'`evidence_text` (segments separes par « ... ») + chaque
  `intermediate_values[*].evidence_text` est present dans un chunk
  de la bonne `page_physique`. Signale distinctement « absent » vs
  « coupe entre deux sous-morceaux », sans toucher au benchmark.

### Resultats sur le corpus actuel

```
Tesseract disponible : True

DOC                        PAGES CHUNKS DECOUP. OCR_TENT. OCR_OK VIDES
----------------------------------------------------------------------
sotuver_2024                  37     38       1         0      0     0
monoprix_2024                 44     44       0         0      0     0
monoprix_consolide_2024       30     30       0         0      0     0
delice_holding_2024           25     27       2         0      0     0
ciments_bizerte_2024          65     65       0         2      0     2
sfbt_2024                     44     45       1         0      0     0
----------------------------------------------------------------------
TOTAL                        245    249       4         2      0     2

Pages encore vides apres OCR (a inspecter) :
  ciments_bizerte_2024 : [16, 65]
```

**245 pages -> 249 chunks** (quasi 1 chunk/page). Seules **4 pages**
sur 245 ont depasse le seuil 4000 car. et ete decoupees en
sous-morceaux : le seuil est bien dimensionne pour les bilans BVMT.

**Pages 16 et 65 de Ciments de Bizerte** : OCR effectivement tente,
Tesseract renvoie respectivement « NOTES AUX ETATS FINANCIERS » (26
car., page de separation) et « 63/ » (3 car., foliotage). Aucune
question du benchmark ne les cite. Benignes.

### Pourquoi ces choix

- **Mapping explicite plutot que glob** : les 6 PDFs ont des noms
  variables (`real_monoprix_consolide_2024.pdf` != individuel). Une
  table en dur dit noir sur blanc quels docs vont dans quel JSONL.
- **Colonne OCR_TENT.** : la distinction entre « OCR candidat »,
  « OCR tente » et « OCR reussi » est critique pour debugger. Si
  demain la CI change et Tesseract disparait, OCR_TENT. tombe a 0
  et le vrai probleme (OCR silencieusement off) est visible dans le
  log.
- **Normalisation tolerante aux espaces dans les nombres** :
  `pdf.extract_text()` colle parfois « -44790 355 » tandis que
  `_pdf_page_text()` ecrit « -44 790 355 ». Deux representations
  du MEME nombre. Le test de couverture collapse les espaces
  chiffre->chiffre des deux cotes pour comparer la substance (les
  chiffres) et pas la typographie. Decouvert sur Q22 et Q23 de
  Ciments de Bizerte : benchmark intact, test adapte.

### Ce que j'ai appris

- **Un bon signalement bat une correction automatique** : plutot
  que de « forcer » les 2 pages Ciments vers un etat non-vide, le
  script les annonce clairement et le test de couverture confirme
  qu'elles n'impactent aucune question. L'inspection manuelle a
  pris 2 minutes et a dissipe le doute.
- **La duplication est insidieuse quand elle traverse les modules**.
  La refacto Semaine 2.3 (helper `_grouper_mots_par_ligne` partage)
  a produit un vrai gain : si demain on change la tolerance
  verticale, un seul endroit a modifier.

### Fichiers modifies dans la session

- `scripts/chunk_corpus.py` : nouveau (~160 lignes).
- `data/chunks/*.jsonl` : 6 fichiers, 249 chunks, ~520 Ko au total.
- `tests/test_chunks_couverture_benchmark.py` : nouveau (2 tests).

---

## 2026-10-31 (fin de journée) — Une seule extraction de référence : `_pdf_page_text`

### Ce que j'ai fait

Trois changements liés, pour supprimer une divergence silencieuse
entre « ce que le benchmark voit » et « ce que les chunks écrivent » :

1. **`data/benchmark/questions.jsonl` — 3 champs corrigés** (format
   seulement, aucune valeur de réponse modifiée) :
   - `ciments_bizerte_2024_22.evidence_text`
   - `ciments_bizerte_2024_23.evidence_text`
   - `ciments_bizerte_2024_23.calculation.intermediate_values.resultat_net.evidence_text`

   Avant : `"Resultat net de l'exercice -44790 355 -34 355944"`
   Après : `"Resultat net de l'exercice -44 790 355 -34 355 944"`

   Les montants sont inchangés (`answer.value = -44790355`,
   `intermediate_values.resultat_net.value = -44790355`,
   `answer.value = -11.52` pour Q23). Seul le format d'écriture dans
   `evidence_text` est aligné sur ce que `_pdf_page_text` lit.

2. **`tests/test_chunks_couverture_benchmark.py`** : retrait de
   `_normaliser_tolerant_espaces_dans_nombres`. On revient à
   `_normaliser` strict partout. La « tolérance aux espaces entre
   chiffres » collait aussi deux colonnes voisines (ex. elle aurait
   fusionné « 100 836 224 165 986 659 » en « 100836224165986659 »),
   ce qui aurait masqué de vrais problèmes de chunking.

3. **`tests/test_benchmark.py`** : `_texte_page` et `_texte_pdf_entier`
   utilisent maintenant `_pdf_page_text` au lieu de
   `pdfplumber.extract_text()`. Une seule extraction de référence
   dans tout le projet : benchmark (annotation + validation),
   chunks (`data/chunks/*.jsonl`), appli.

### Pourquoi

`pdfplumber.extract_text()` est capricieux : sur la même page 4 de
Ciments de Bizerte, il écrit « -44 790 355 » sur la ligne 24 mais
« -44790 355 » sur la ligne 22 (ce comportement dépend de micro-écarts
horizontaux entre glyphes). Un `evidence_text` annoté à partir de cette
méthode était fragile.

`_pdf_page_text` reconstruit le texte à partir des positions des mots
(`page.extract_words()` + regroupement par ligne visuelle + tri par
`x0` + espace simple si gap petit, double espace si colonne). Sa
sortie est stable et prévisible : « -44 790 355 » partout. En en
faisant la référence unique, un `evidence_text` qui passe la
validation benchmark est garanti présent dans le chunk correspondant.

### Ce que j'ai appris

- **Une référence unique bat deux représentations équivalentes**.
  La tentation était de rendre le test tolérant pour accommoder deux
  formats. En pratique, deux formats « équivalents » dérivent toujours
  et introduisent des cas limites invisibles. Figer `_pdf_page_text`
  comme source de vérité évite la question.
- **Les corrections d'annotation ne doivent toucher qu'au format**,
  jamais aux valeurs. Si une correction change une valeur, c'est que
  l'annotation d'origine avait un bug plus grave : le signaler et le
  traiter séparément.

### Fichiers modifiés

- `data/benchmark/questions.jsonl` : 3 occurrences corrigées
  (format seulement).
- `tests/test_benchmark.py` : `_pdf_page_text` au lieu de
  `extract_text()` dans `_texte_page` et `_texte_pdf_entier`.
- `tests/test_chunks_couverture_benchmark.py` : retrait de la
  normalisation tolérante.

---

## 2026-10-31 (soir, 2) — Invariant : une page vide ne produit aucun chunk

### Ce que j'ai fait

Trois changements lies :

1. **`scripts/chunk_corpus.py`** : la boucle de chunking **saute**
   maintenant les pages dont le texte final reste sous
   `SEUIL_VIDE_CHARS` apres `extraire_pages` (donc apres OCR cible).
   Elles sont comptees dans `pages_encore_vides` mais n'alimentent
   plus `chunks`.

2. **`tests/test_chunks_couverture_benchmark.py`** : nouveau test
   parametre `test_invariant_chunks_egale_pages_moins_vides_plus_morceaux_supp`,
   marker `real`, qui pour chacun des 6 documents du corpus verifie :

       n_chunks == n_pages - n_vides + morceaux_supplementaires

   `morceaux_supp = sum(max(0, nb_chunks_de_la_page - 1))`. Un
   garde-fou complementaire assure qu'aucun chunk n'a un texte sous
   le seuil.

3. **Regenere `data/chunks/*.jsonl`** avec le nouveau comportement.
   Avant : Ciments 65 chunks (incorrect). Apres : 63 chunks (= 65
   pages - 2 vides + 0 decoupage). Total corpus : 249 -> 247 chunks.

### Pourquoi

Un chunk quasi-vide (ex. « 63/ » = 3 car.) n'a rien a vectoriser.
Son vecteur ressortirait au hasard dans une recherche RAG et
fausserait les mesures de Recall@k. Mieux vaut l'absence de chunk
que la presence d'un chunk bruite : le benchmark n'a aucune question
sur ces pages, aucune evidence a trouver.

### Ce que j'ai appris

- **Les invariants comptables simples (CHUNKS = PAGES - VIDES +
  MORCEAUX_SUPP) sont des sentinelles tres efficaces**. Ils ne
  decrivent pas une fonctionnalite, ils decrivent une regle de
  comportement global. Si demain quelqu'un modifie la logique de
  chunking et casse l'invariant, le test tombe immediatement, meme
  si tous les tests unitaires continuent de passer.
- **Decoupler le "quoi" du "comment"** : le script d'orchestration
  (`chunk_corpus.py`) decide quoi ignorer (pages vides), la fonction
  bas niveau `decouper_page` sait decouper n'importe quel texte en
  chunks. Chacune a sa responsabilite.

### Grep des `extract_text()` restants (sans modification)

Un seul appel actif identifie : `bilanlens/extraction.py:945`
dans `extraire_document`. Il alimente :
- la detection de locale (robuste au format) ;
- le chemin de repli `_extraire_lignes_periodes_depuis_texte` ;
- le dict de sortie consomme par `app.py` (secteur hors perimetre
  + extraction de valeurs etiquetees).

Migration eventuelle vers `_pdf_page_text` : benefique pour la
coherence totale, mais l'appli chapitre 1 en depend (test_real_bilans,
test_synthetic_bilans). Non modifie en attendant un feu vert explicite
et un commit dedie.

---

## 2026-10-31 (nuit) — Migration `extract_text()` → `_pdf_page_text` dans `extraire_document`

### Ce que j'ai fait

Dans `bilanlens/extraction.py:945` (chemin PDF de `extraire_document`),
remplacement du dernier appel `page.extract_text()` par
`_pdf_page_text(page)`. Après cette migration, le projet n'utilise
plus `extract_text()` nulle part comme source de vérité : benchmark,
chunks et appli consomment tous le même texte reconstruit par
position des mots.

### Protocole de validation (recommandé par le user)

Snapshot des 12 ratios sur 9 fichiers (`test1-3` + 6 bilans réels
BVMT) avant et après migration, puis `diff` strict :

```
diff ratios_avant.txt ratios_apres.txt
---IDENTIQUES---
```

**Aucune différence** sur aucun ratio pour aucun fichier. Les 122
tests de la suite complète restent verts.

### Pourquoi c'est safe

Le texte extrait sert à :
1. **Détection de locale** (`detecter_separateur_decimal`) : regarde
   des motifs de nombres (groupes de 3 chiffres, décimales), robuste
   au formatage des espaces.
2. **Chemin de repli** (`_extraire_lignes_periodes_depuis_texte`) :
   utilise `\s{2,}` comme séparateur de colonnes.
   `_pdf_page_text` insère justement des doubles espaces entre
   colonnes voisines : le repli en profite plutôt que d'en souffrir.
3. **Détection sectorielle** (`sector.py`) : casefold + split sur
   mots-racines, aucune dépendance au formatage spatial.
4. **Repli étiquette/valeur** (`extraire_valeurs_etiquetees`) :
   motifs regex sur libellé + montant, insensibles au nombre d'espaces.

De plus, le chemin principal reste `_extraire_lignes_periodes_depuis_page_pdf`
(parseur par coordonnées) : il n'a jamais utilisé `extract_text()`,
donc rien ne change pour lui.

### Ce que j'ai appris

- **Un diff identique sur un snapshot numérique vaut mille mots** :
  avant la migration, on pouvait seulement arguer qu'elle était
  safe. Après, un `diff --IDENTIQUES` prouve l'équivalence
  comportementale sur l'ensemble du corpus de test. Le snapshot
  prend 2 minutes à écrire et sécurise la décision.
- **Une référence unique partout évite une catégorie entière de
  bugs** : plus personne ne pourra annoter un `evidence_text` sur
  une représentation et l'évaluer sur une autre.

### Fichiers modifiés

- `bilanlens/extraction.py` : 1 ligne modifiée + 5 lignes de
  commentaire explicatif.

---

## 2026-10-31 (nuit, 2) — Semaine 2, étape 4 : pivot bge-m3 → API Gemini

### Décision

Pivot embeddings local (`bge-m3` + `sentence-transformers`) → **API
Gemini (`gemini-embedding-2`)**. Raison : disque et RAM trop justes
sur CPU 16 GB (poids 2,3 Go + encodage lent). L'API est gratuite dans
sa limite free tier et déporte le calcul.

**Plan de comparaison plus tard** : brancher un adapter bge-m3 sur
**Google Colab (GPU T4 gratuit)** et comparer les deux encodeurs sur
le benchmark avec les métriques du protocole : **Recall@5, MRR,
latence, coût, confidentialité**. Interface `encoder_textes` identique
pour les deux adapters, aucun changement dans `index.py` ni les
scripts d'évaluation.

### Vérifications préalables (avant toute écriture de code)

| Point | Résultat |
|---|---|
| Modèles disponibles sur la clé | `gemini-embedding-001`, `gemini-embedding-2`, `gemini-embedding-2-preview` |
| Modèle retenu | `gemini-embedding-2` (GA, dim=3072, `input_token_limit=8192`) |
| Vecteurs natifs normalisés ? | **Oui** (norme L2 = 1,000000 vérifiée) → `hnsw:space=cosine` compatible |
| `task_type` supporté ? | **Oui** : `RETRIEVAL_DOCUMENT` pour les chunks, `RETRIEVAL_QUERY` pour les questions. Stocké dans `coll.metadata["task_type_indexation"]`. |
| Dimension réduite ? | **Non**, on garde 3072 (max du modèle) |
| Tokens réels du corpus (count_tokens) | **186 031 tokens** sur 247 chunks — min 28 / max 2760 / moy 753 |
| Chunks dépassant 2048 tokens ? | 5 chunks (sfbt p11/p13/p14, ciments p17/p52) → `gemini-embedding-001` les tronquerait, `gemini-embedding-2` passe |
| Durée indexation estimée | **~7 min** (bornée par TPM 30k, pas RPM 100) |

### Correction de mon erreur initiale sur les quotas

**Mon estimation initiale « 1-2 appels suffisent » était fausse.**
L'API `embed_content` accepte jusqu'à 100 contents par appel mais la
somme des tokens doit tenir dans la fenêtre TPM. Avec 186 031 tokens
et un TPM de 30 000, il faut au minimum ~8 lots espacés d'une minute.
Correction : batching tokens-aware avec attente entre lots, pas
batching par nombre de chunks.

### Architecture retenue

- `bilanlens/embeddings.py` :
  - `EncodeurGemini` (dataclass : client + metadonnees quotas) ;
  - `EncodeurFake` (dataclass : hash-based, pour les tests sans quota) ;
  - `charger_encodeur()` ;
  - `compter_tokens(encoder, texte)` (API gratuite) ;
  - `_regrouper_en_lots_par_tpm(tokens, tpm_max, marge)` (**TODO(human)**
    sur le bin-packing) ;
  - `_appel_batch_avec_retry` (backoff exponentiel 2/4/8/16 s sur 429) ;
  - `encoder_textes(encoder, textes, task_type)` → `(ndarray, stats)`
    où `stats` contient `nb_appels_api`, `tokens_total`, `duree_s`,
    `nb_lots`.
- `bilanlens/index.py` : `indexer_chunks(coll, chunks, encoder, task_type)`
  retourne désormais `(n, stats)` et passe `task_type` à `encoder_textes`.
- `scripts/index_chunks.py` : estimation de durée affichée AVANT
  l'indexation, puis récap avec modèle, task_type, dim, tokens total,
  appels API, durée, chunks indexés, taille index, top-3 Q01 (encodée
  avec `RETRIEVAL_QUERY`).
- `tests/test_index.py` : 5 tests, 4 avec `EncodeurFake` (par défaut),
  1 avec marker `network` qui tape l'API réelle.

### Décisions prises

| Décision | Justification |
|---|---|
| `gemini-embedding-2` plutôt que `001` | 8192 tokens vs 2048 : 5 chunks du corpus auraient été tronqués par le `001` |
| Garder 3072 dim (pas de réduction) | Vecteurs restent unit-norm ; perte de précision inutile |
| `task_type=RETRIEVAL_DOCUMENT` pour l'indexation, `RETRIEVAL_QUERY` pour les requêtes | Asymétrie recommandée par Google ; stocké dans `coll.metadata` pour reproductibilité |
| Marker `network` pour les tests qui tapent l'API, pas de marker `embeddings` | Les tests d'index tournent par défaut avec `EncodeurFake` ; CI ne consomme pas de quota |
| `chromadb` dans `requirements.txt` principal, suppression de `requirements-rag.txt` | Zéro install séparée ; plus de `torch`, plus de `sentence-transformers` |
| Marge TPM 0,8 (24 000 tokens par lot) | Tolère l'écart entre `count_tokens` local et comptage effectif côté serveur |

### À faire ensuite

- Humain : écrire le corps de `_regrouper_en_lots_par_tpm` (bin-packing,
  8-10 lignes).
- Puis lancer `scripts/index_chunks.py` et montrer les mesures demandées
  (modèle, task_type, dim, tokens, appels API, durée, chunks indexés,
  taille index, top-3 Q01).
- Plus tard : adapter bge-m3 Colab + comparaison benchmark.

---

## 2026-10-31 (nuit, 3) — 8 corrections sur l'adapter Gemini

### Corrections appliquées (demandées par l'utilisateur)

1. **`EncodeurFake` déterministe sha256** : `hash()` Python varie
   avec `PYTHONHASHSEED` à chaque lancement ; remplacé par
   `hashlib.sha256(f"{task_type}|{texte}")[:8] -> seed`. Test
   `test_encodeur_fake_deterministe_entre_instances` vérifie que deux
   instances fraîches produisent le même vecteur pour le même texte.
2. **Comptage tokens unique** : `EncodeurGemini.compter_tokens` cache
   chaque texte localement (`_tokens_cache: dict[str, int]`). Le
   script `index_chunks.py` appelle `encoder.compter_tokens(texte)`
   une fois pour l'estimation, et la 2e demande (dans
   `embed_documents`) sort du cache local sans refaire d'appel. RPM
   respecté via sliding window `deque[timestamp]` : au plus 100
   appels dans la dernière minute.
3. **Backoff factorisé** : nouveau `bilanlens/_api_retry.py` expose
   `ErreurQuotaDepassee` et `appeler_avec_backoff(fn)`. `llm.py`
   et `embeddings.py` l'utilisent. `tests/test_llm.py` patche
   `bilanlens._api_retry.time.sleep` (au lieu de `bilanlens.llm.time.sleep`).
4. **Interface `Encodeur` (Protocol)** avec `embed_documents(textes) ->
   (ndarray, stats)` et `embed_query(texte) -> ndarray`. Pas de
   `isinstance` dans `index.py` ni dans les scripts : polymorphisme
   via le Protocol.
5. **Cache embeddings sur disque** : `data/cache_embeddings/<model>.jsonl`
   (gitignoré), append-only, clé = sha256(model|task_type|texte).
   Test `test_cache_embeddings_zero_appel_a_la_2e_indexation` vérifie
   avec `EncodeurFake` qu'une 2e indexation fait 0 vecteur recalculé.
6. **Collection Chroma par modèle** : `nom_collection(model)` →
   `bilans__gemini-embedding-2`. Permet de brancher bge-m3 plus tard
   sans mélanger les espaces vectoriels.
7. **Note confidentialité** dans `README.md` : le free tier Gemini
   peut utiliser les données envoyées ; acceptable ici (rapports BVMT
   publics), pas adapté aux documents confidentiels. Bascule
   recommandée : plan payant Google ou adapter `bge-m3` local.
8. **Plan 2×2 (Gemini, bge-m3) × (dense, hybride BM25)** dans
   `planning.md` section « Modèles candidats ». Métriques : Recall@5,
   MRR, latence, coût, confidentialité.

### Logique du bin-packing (`_regrouper_en_lots_par_tpm`)

> Trois lignes : (1) un lot courant accumule des indices tant que
> `tokens_courant + n` reste sous `budget = TPM_MAX * MARGE_QUOTA` ET
> que `len(lot_courant)` reste sous `max_contents_par_appel`. (2) Si
> l'une des deux conditions casse, on pousse le lot courant (s'il
> n'est pas vide) et on redémarre un nouveau lot avec le texte en
> cours. (3) Après la boucle, on flushe le dernier lot courant s'il
> est non vide.
>
> C'est un bin-packing First Fit qui préserve l'ordre d'entrée : les
> chunks sortent dans le même ordre qu'ils sont entrés, pratique pour
> l'alignement avec les IDs stables de Chroma.

### Fichiers modifiés / créés

- Créés : `bilanlens/_api_retry.py`.
- Réécrits : `bilanlens/embeddings.py`, `bilanlens/index.py`,
  `scripts/index_chunks.py`, `tests/test_index.py`.
- Édités : `bilanlens/llm.py` (import `_api_retry`), `tests/test_llm.py`
  (patch sleep déplacé), `.gitignore` (+ cache_embeddings),
  `README.md` (+ section Confidentialité), `docs/planning.md` (+ 2×2),
  `requirements.txt` (+ chromadb), `pytest.ini` (- marker embeddings).
- Supprimé : `requirements-rag.txt`.

### Correction à l'exécution : `gemini-embedding-2` ne fait pas de batch

**Première tentative d'indexation** : `np.asarray(tous_vecteurs)` lève
`ValueError: inhomogeneous shape`. Diagnostic : le cache ne contenait
que **8 entrées** (une par lot) au lieu de 247. Cause : `embed_content(
contents=[t1, t2, ...])` sur `gemini-embedding-2` renvoie **UN seul**
embedding — vraisemblablement la concaténation ou le premier content —
au lieu de N embeddings. Comportement **différent** de
`gemini-embedding-001` qui bat correctement.

Vérifié dans la session précédente (scratchpad `gemini_embed_check.py`) :

```
=== gemini-embedding-2 ===
  [0] dim = 3072, norme L2 = 1.000000      # UN SEUL vecteur !

=== gemini-embedding-001 ===
  [0] dim = 3072, norme L2 = 1.000000
  [1] dim = 3072, norme L2 = 1.000000      # DEUX vecteurs OK
```

**Correction appliquée** dans `embeddings.py:_call_embed_batch` : la
fonction fait maintenant N appels séquentiels (un par texte) au lieu
d'un seul appel batch. Le bin-packing TPM reste inchangé : chaque
"lot" vise ~24 000 tokens, on fait les N appels rapides à l'intérieur,
puis on attend 60 s pour libérer la fenêtre glissante. RPM 100/min
reste largement en dessous (max ~38 req/min dans un lot).

Cache vidé (`rm data/cache_embeddings/gemini-embedding-2.jsonl`),
indexation relancée.

### Ce que j'ai appris

- **Lire les sorties des petits scripts d'exploration vaut mieux que
  faire confiance à l'intuition.** Mon `gemini_embed_check.py` avait
  déjà montré que `gemini-embedding-2` retournait UN embedding pour
  deux contents — mais je ne l'avais pas relu attentivement, et j'ai
  codé le batch en supposant que ça marchait comme le `001`. Perdre
  10 min d'indexation + un cache à vider aurait pu être évité par
  une relecture de 10 secondes du script de check.
- **Un ndarray `np.asarray(liste_de_listes_de_tailles_differentes)`
  lève `inhomogeneous shape`**. C'est le signe qu'un indice a été
  oublié (resté à `None`) ou qu'une sous-liste a une mauvaise taille.
  Un check `assert len(vecteurs) == len(batch)` dans `_call_embed_batch`
  aurait fait tomber le bug directement sur la ligne responsable.

---

## 2026-11-01 — Durcissement cache + garde-fou N→N

### Ce que j'ai fait

Après la 1re indexation complète (Q01 au top-1), 5 points de
durcissement avant commit :

1. **Garde-fou "N textes → N vecteurs"** dans `tests/test_index.py` :
   - `test_embed_documents_fake_renvoie_N_vecteurs` : `EncodeurFake`
     avec 5 textes → shape `(5, dim)`.
   - `test_encodeur_gemini_N_textes_renvoie_N_vecteurs_3072` (marker
     `network`) : 3 textes réels → shape `(3, 3072)`, et cosinus
     hors-diagonale < 0,999 (sinon régression vers un batch qui
     renvoie un vecteur agrégé dupliqué).
   - Au passage, le test réseau existant
     `test_encodeur_gemini_vecteurs_natifs_unit_norm` passait
     silencieusement avant la correction : il attendait
     `nb_appels_embed == 1` pour 2 textes (hérité de l'ancien
     batch). Maintenant il attend `== 2`.
2. **Doc Gemini sur le batch** : la doc officielle confirme que
   `gemini-embedding-2` **agrège** une liste de contents en un
   seul vecteur. Pour N vecteurs séparés, Google renvoie vers la
   **Batch API asynchrone** (soumission d'un job, récupération
   différée). Le `batchEmbedContents` synchrone n'existe que pour
   `gemini-embedding-001`. Notre choix (N appels séquentiels dans
   un lot TPM, puis attente de 60 s) reste donc le seul mode
   synchrone correct pour `gemini-embedding-2`. Si on paye un jour,
   la Batch API offre -50 % selon des sources tierces.
3. **Persistance du cache `count_tokens` sur disque** :
   `_CacheTokens` (append-only JSONL, clé `sha256(model|texte)`)
   dans `bilanlens/embeddings.py`. Fichier :
   `data/cache_embeddings/<model>__tokens.jsonl` (gitignore). La
   clé ne contient pas le `task_type` : `count_tokens` ne dépend
   pas de la façon dont le texte sera utilisé ensuite. Objectif
   atteint : une 2e indexation du même corpus fait **0 appel
   count + 0 appel embed = 0 appel API au total**.

### Pourquoi

- **Le bug du vecteur unique n'était pas détecté par la suite** :
  seule une tentative d'indexation réelle le faisait tomber, via
  `inhomogeneous shape`. Un test rapide avec le `EncodeurFake` et
  un test réseau garde-fou verrouillent le comportement attendu.
- **Le cache tokens n'était qu'en RAM** : la 2e indexation refaisait
  les 247 `count_tokens` (gratuit mais 126 s de latence et bruit
  dans l'objectif "0 appel API"). Persister le comptage sur disque
  est trivial (même pattern que `_CacheEmbeddings`, un entier au
  lieu d'un vecteur) et nettoie l'affirmation "idempotence totale".

### Ce que j'ai appris

- **Le texte d'une doc officielle vaut mieux qu'un test empirique
  pour affirmer "ne fait pas de batch".** `gemini-embedding-2`
  n'est pas "cassé" : il est documenté pour agréger une liste en
  un vecteur unique. Le script d'exploration avait raison, mais la
  doc officielle donne le "pourquoi" (modèle multimodal avec
  agrégation inter-contenus explicite).
- **Un test de shape vaut plus qu'un test de norme.** Les deux
  tests précédents vérifiaient la norme L2 ≈ 1, mais pas la shape
  `(N, dim)` — une shape `(1, dim)` passait aussi. Le vrai garde-fou
  est sur la forme.
- **Deux caches à côté d'un même modèle, deux schémas de clé
  différents.** Embeddings : `sha256(model | task_type | texte)`
  car le vecteur dépend du task_type. Tokens : `sha256(model | texte)`
  seulement, car `count_tokens(model, contents=texte)` donne la
  même valeur quel que soit l'usage ultérieur du texte.

---

## 2026-11-01 — Étape 5 : evaluate_b0.py + distinction quota RPM vs RPD

### Ce que j'ai fait

Script `scripts/evaluate_b0.py` : évaluation du LLM seul (sans contexte
RAG) sur les 31 questions du benchmark, avec checkpoint append-only
sur `(run_id, question_id)` et prompt partagé B0/V1 (voir
`bilanlens/prompts.py`). Les 4 corrections demandées :

1. **Checkpoint sur le couple `(run_id, question_id)`** : un nouveau
   `run_id` (= nouveau prompt ou nouveau modèle) force à retraiter
   toutes les questions. Vérifié par un test dédié.
2. **Prompt partagé B0/V1** : `SYSTEM_INSTRUCTION` + templates dans
   `bilanlens/prompts.py`. Hash court `prompt_version` (16 hex de
   SHA-256) enregistré par ligne. Modifier les règles invalide
   automatiquement les anciens checkpoints.
3. **JSON strict côté API** : `response_mime_type="application/json"`
   + `response_schema` à 2 clés `{answer, confidence}`. Côté client,
   `parser_reponse` reste défensif : `parse_ok=False` sans crash si
   JSON invalide. `answer_raw` conservé dans tous les cas pour debug.
4. **Pas d'outils/grounding** : `tools=[]` explicite dans
   `GenerateContentConfig`. Test de spy sur le constructeur de
   config pour s'assurer que le kwarg est bien passé.

Deux incidents en condition réelle, chacun transformé en règle :

### Incident 1 : 503 UNAVAILABLE à la 8ᵉ question

**Symptôme** : `google.genai.errors.ServerError: 503 UNAVAILABLE.
"This model is currently experiencing high demand"`.

**Problème** : `_api_retry.py` n'attrapait que `errors.ClientError`
(4xx). Un 5xx remontait sans retry et plantait la boucle.

**Correction** : branche `except errors.ServerError` séparée, mêmes
délais `[2, 4, 8, 16]` s, re-lève l'erreur originale après N
tentatives (**pas** `ErreurQuotaDepassee` : une surcharge Google
n'est pas un épuisement de quota, le script appelant doit pouvoir
distinguer).

### Incident 2 : 429 à la 19ᵉ question — quota RPD épuisé

**Symptôme** : `429 RESOURCE_EXHAUSTED. Quota exceeded for metric:
generate_content_free_tier_requests, limit: 20, model:
gemini-3.6-flash. Please retry in 15h49m33s.`

**Découverte** : le free tier `gemini-3.6-flash` a seulement
**20 RPD** (requêtes par jour), pas 500 ou 1500 comme suggèrent
plusieurs sources tierces. L'alias `gemini-3.5-flash` que j'utilisais
résout vers `gemini-3.6-flash` côté Google (vérifié dans le
`model_version` renvoyé). La quasi-totalité du quota avait été
consommée en 2 runs successifs (débugs du 503).

**Problème conceptuel** : le backoff `[2, 4, 8, 16]` s de 5 tentatives
n'avait **aucun sens** quand Google indique `retryDelay: 56973s` —
j'ai attendu 30 s pour planter avec `ErreurQuotaDepassee` quand il
fallait planter net.

**Correction** : nouvelle exception `ErreurQuotaJournalier` (hérite
de `ErreurQuotaDepassee`), levée **immédiatement** si `retryDelay > 60 s`
dans la réponse Google. Extraction robuste via `_extract_retry_delay_s`
(trois chemins : `exc.details`, `exc.response_json`, regex fallback).
Le script `evaluate_b0.py` attrape l'exception, affiche
`"X/31 faits, relancer après HH:MM Tunis"` et sort avec le code 2
(convention locale : 1 = fatal, 2 = quota journalier).

### Résultat partiel sur 18/31 questions (run du 2026-10-31)

- **100 % de réponses `"donnée non disponible"`** (18/18).
- 0 `parse_ok=False` (le JSON schema fonctionne).
- Latence moyenne : **4,01 s** (min 1,93 / max 9,36).
- Catégories couvertes : extraction (5), calcul (4), comparaison (4),
  texte_annexes (3), sans_reponse (2).

### Ce que j'ai appris

- **Un code HTTP ne suffit pas à décider d'une stratégie.** Deux 429
  identiques peuvent être « attends 2 s, j'ai dépassé le RPM » ou
  « attends 15 h, tu as consommé ton RPD ». Le `retryDelay` du corps
  JSON est l'indicateur exploitable, pas le code.
- **Pin le nom pinné, pas l'alias.** `gemini-3.5-flash` est un
  pointeur mobile ; Google peut le promouvoir vers un nouveau modèle
  sans préavis. Enregistrer le `model_version` renvoyé dans chaque
  ligne de résultats permet de distinguer deux runs qui ont tapé
  deux modèles différents « sous le même nom ».
- **Un sous-type d'exception bien choisi évite le piège du `except`
  trop large.** `ErreurQuotaJournalier(ErreurQuotaDepassee)` :
  l'ancien code qui attrape `ErreurQuotaDepassee` continue de
  marcher, le nouveau code peut distinguer finement en attrapant
  `ErreurQuotaJournalier` AVANT. Pas de breaking change.
- **Un benchmark à 100 % d'abstention est un plancher très honnête.**
  B0 mesure zéro réponse correcte, donc tout gain mesuré par V1
  sera **attribué sans ambiguïté au RAG**, pas à la connaissance
  préalable du LLM. À l'opposé, si B0 répondait à 60 % des questions
  correctement par pure mémoire des rapports BVMT, la différence
  V1−B0 serait difficile à interpréter. **À tester plus tard** :
  variante B0 **sans la consigne d'abstention**, pour mesurer les
  hallucinations (le LLM invente-t-il des chiffres plausibles ?).

### Décisions prises

| Décision | Justification |
|---|---|
| `DEFAULT_MODEL = "gemini-3.6-flash"` (pas l'alias) | Reproductibilité : si Google promeut l'alias à un nouveau modèle, notre code reste identique |
| Seuil `retryDelay > 60 s` pour distinguer RPD de RPM | Un RPM se régénère en &lt; 60 s ; au-delà, c'est forcément un quota journalier |
| `EXIT_CODE_QUOTA_JOURNALIER = 2` | Permet à un wrapper CI de distinguer « replanifier demain » (2) d'une erreur fatale (1) |
| Message d'arrêt en fonction `message_arret_quota_journalier(maintenant=...)` injectable | Testable sans dépendance à l'horloge réelle |
| Même modèle pour B0 et V1 | La différence B0 vs V1 doit mesurer le RAG, pas un changement de modèle |

### Fichiers modifiés dans la session

- `bilanlens/prompts.py` : nouveau (SYSTEM_INSTRUCTION partagé,
  TEMPLATE_B0_USER, TEMPLATE_V1_USER, JSON_SCHEMA_REPONSE,
  prompt_version_b0, prompt_version_v1).
- `bilanlens/llm.py` : `generate()` accepte `response_schema`,
  `tools=[]` explicite, `DEFAULT_MODEL = "gemini-3.6-flash"`,
  re-export `ErreurQuotaJournalier`.
- `bilanlens/_api_retry.py` : `ErreurQuotaJournalier`,
  `_extract_retry_delay_s`, retry 5xx séparé.
- `scripts/evaluate_b0.py` : nouveau, checkpoint `(run_id, qid)`,
  `message_arret_quota_journalier` injectable, `EXIT_CODE_QUOTA_JOURNALIER`.
- `tests/test_llm.py` : +4 tests (503 ok, 503 persistant lève
  ServerError, 429 RPD lève ErreurQuotaJournalier immédiatement,
  héritage ErreurQuotaJournalier ⊂ ErreurQuotaDepassee).
- `tests/test_evaluate_b0.py` : nouveau, 16 tests (4 corrections +
  message d'arrêt + exit code).
- `results/b0.jsonl` : 18/31 lignes partielles (**non commité**,
  le sera après les 31 réponses complètes).

### Reste à faire (bloqué par quota)

- Attendre la régénération du quota RPD (~minuit Pacific = 09h Tunis).
- Relancer `evaluate_b0.py` → checkpoint reprend aux 13 restantes.
- Afficher les stats finales (31 lignes).
- Décider du modèle pour B0 et V1 d'après les quotas AI Studio
  réels (voir ci-dessous).

### Quotas Gemini free tier à vérifier dans AI Studio

Les chiffres ci-dessous proviennent de sources tierces et de
l'erreur Google reçue en condition réelle ; **à confirmer dans
AI Studio** (page connectée, section « Rate limits ») avant de
figer un choix de modèle pour les runs sérieux :

| Modèle (API ID) | RPM | RPD free | Verdict |
|---|---|---|---|
| `gemini-3.6-flash` (alias `gemini-3.5-flash`) | ~15 | **20** | ❌ celui qui m'a bloqué — insuffisant |
| `gemini-3.5-flash-lite` | ~10 | **500** | ✅ candidat sérieux pour B0+V1 (62 appels) |
| `gemini-3.1-flash-lite` | ~15 | 500 | ✅ fallback stable |

Décision reportée à la relance de demain, après vérification
AI Studio de ma clé.

---

## 2026-11-02 — Bascule Flash-Lite + variante B0-libre + mesure hallucination

### Pourquoi la bascule

**`gemini-3.6-flash` plafonne à 20 RPD sur une fenêtre glissante de
24 h**, pas sur une fenêtre calendaire. Deux conséquences :

1. Pour un benchmark de 31 questions × 2 runs (B0 + V1) = 62 appels
   LLM minimum, il faut ~75 h sur Flash seul : impraticable.
2. Le quota se libère **requête par requête** au fur et à mesure
   que les anciennes sortent de la fenêtre, pas d'un seul coup à
   minuit. Hier soir j'avais 20/31, ce matin Google m'a dit
   « retry dans 23 h » sur la 21ᵉ requête : 1 seule nouvelle
   requête avait pu passer en 10 h.

**Bascule validée** vers `gemini-3.5-flash-lite` (quotas issus de
sources tierces, **non vérifiés dans AI Studio** à cette date :
~500 RPD, ~10 RPM — à confirmer côté clé) :

- Modèle **stable et pinné** (`client.models.list()` confirme :
  pas de suffixe `preview` ni `exp`).
- Latence **4× plus rapide** que Flash (0,89 s moy vs 4,01 s).
- **Même modèle pour B0 et V1** : la différence B0 vs V1 doit
  mesurer l'effet du RAG, pas un changement de modèle. Si on
  changeait de modèle entre B0 et V1, la comparaison ne vaudrait
  plus rien.

### Résultats B0-strict Flash-Lite (31/31)

- **100 % de `"donnee non disponible"`** (plancher 0 % de réponses
  correctes, identique à Flash hier). Confirme que ce n'est pas
  un biais du modèle : c'est la consigne d'abstention stricte qui
  domine la décision quel que soit le modèle.
- 0 `parse_ok=False`, latence moy 0,89 s, 31 lignes propres sous
  `run_id = b0_gemini35flashlite_d1ef73ef27f98dd4`.
- Les 20 lignes historiques `gemini-3.6-flash` (incomplet)
  **préservées** sous l'ancien `run_id` dans le même fichier
  `results/b0.jsonl` : trois runs coexistent proprement.

### Variante B0-libre (prompt diagnostique sans abstention)

**But** : mesurer la propension du LLM à inventer sans contexte.
Prompt système séparé (`SYSTEM_INSTRUCTION_B0_LIBRE`) qui retire :

- « Au moindre doute, réponds `donnee non disponible` »
- « Pas d'approximation, pas d'intervalle, pas d'environ »
- « Pas de disclaimers »

Mais garde le format JSON `{answer, confidence}` identique.

**V1 reste sous `SYSTEM_INSTRUCTION` strict.** La variante libre
est cantonnée à cette mesure diagnostique. Nouveau `run_id`
`b0libre_gemini35flashlite_21c68d1cba543eeb` (prefix `b0libre_`
pour distinguer, prompt_version différent du strict).

### Résultats B0-libre — ce que le modèle fait sans consigne

Classification affinée après découverte que le modèle reformule
largement ses refus (« Je ne dispose pas... », « Information non
disponible dans le contexte », « n'est pas précisée ») :

| Catégorie | N / 31 | Interprétation |
|---|---|---|
| **CHIFFRÉE** | 4 (13 %) | nombre ≥ 5 chiffres ou % → potentielle hallucination |
| **ABSTENTION LARGE** | 24 (77 %) | refus explicite ou reformulé |
| **AUTRES textuels** | 3 (10 %) | phrase sans chiffre ni abstention (ex. méthode comptable) |

Note empirique sur la classification : le pattern regex
`n'(?:est|sont) pas` dans `est_abstention_large` est **trop large
en absolu** (« ce n'est pas déductible » n'est pas une abstention).
Il tient uniquement parce qu'il est **combiné en ET** avec « pas
de chiffre significatif » : les deux signaux ensemble sont fiables.
**Pour le scoring de l'étape 7, cette classification binaire ne
suffira pas** : il faudra comparer la réponse du modèle à la
réponse canonique du benchmark (tolérance numérique + similarité
sémantique pour les textuels), pas s'appuyer sur des regex locales.

### Les 4 hallucinations : signature complète

Toutes les 4 déclarent `confidence: "high"` — **le modèle ne
distingue pas entre savoir et inventer**.

| ID | Catégorie | Modèle (conf=high) | Benchmark |
|---|---|---|---|
| `sotuver_2024_03` | comparaison | « augmentation de 15 282 342 TND » | **diminution** de -24 287 937 TND (-63,6 %) |
| `monoprix_consolide_2024_11` | comparaison | « augmentation de 15 287 654 TND » | augmentation de +5 859 229 TND (+578 %) |
| `monoprix_2024_14` | calcul | « rentabilité nette = -5,86 % » | **0,93 %** |
| `sfbt_2024_20` | comparaison | « 25 000 000 TND par incorporation » | +20 625 000 TND (+8,33 %) |

**Zéro hallucination sur les 5 questions d'extraction testées** —
le modèle refuse systématiquement. Les hallucinations se
concentrent sur **comparaison et calcul**, dont le pattern
syntaxique (« augmentation de X TND », « ratio = Y % ») est
fréquent dans son training. Face à ces patterns, il génère un
chiffre « plausible financier » (dizaines de millions de TND)
par distribution a priori plutôt que par rappel factuel.

Détail troublant sur `monoprix_consolide_2024_11` : la vraie
variation est **+578 %** (très inhabituel : contexte post-perte).
Le modèle a eu la direction juste (augmentation) mais a sorti
+15,3 M TND au lieu de +5,9 M. Il calibre les hallucinations sur
des ordres de grandeur typiques et ignore les ratios atypiques.

### Les 3 autres textuels : hallucinations qualitatives

Tous les 3 déclarent `confidence: "high"` également.

| ID | Modèle | Benchmark |
|---|---|---|
| `sotuver_2024_04` | « coût moyen pondéré » | au plus bas du coût de production et de la valeur de réalisation nette |
| `sotuver_2024_08` | « reclassement des moules... destinés à être utilisés sur plusieurs exercices » | pour mieux refléter la nature durable des moules et aligner le traitement comptable (NCT 11) |
| `sfbt_2024_21` | « coût d'acquisition majoré des frais accessoires » | au coût moyen pondéré |

**2/3 faux, 1/3 proche sémantiquement** (`sotuver_2024_08` évoque
bien le reclassement NCT 11). Pas de hasard : le modèle semble
avoir une mémoire générique du reclassement moules → immobilisations.
C'est précisément le genre de connaissance *générale* qui va fuir
dans toutes les variantes B0.

### Décisions prises

| Décision | Justification |
|---|---|
| `DEFAULT_MODEL = "gemini-3.5-flash-lite"` | ~500 RPD annoncés par sources tierces (vs 20 RPD vérifié sur 3.6-flash) ; à reconfirmer dans AI Studio |
| Même modèle B0 et V1 | La différence doit mesurer le RAG, pas un changement de modèle |
| Variante B0-libre dans le même script via `--variante strict\|libre` | Évite la duplication de `evaluate_b0.py` |
| Prompt système B0-libre JAMAIS réutilisé pour V1 | V1 reste sous la consigne stricte |
| Nouveau format `run_id` = `<prefix>_<model_slug>_<prompt_version>` | Trois axes qui changent le résultat doivent être dans l'ID |
| `confidence` du JSON **inutilisable** comme garde-fou | 4/4 hallucinations + 3/3 autres faux = `conf=high`. Pour la V2, poids `high` à éviter |

### Ce que j'ai appris

- **Un quota glissant n'est pas un quota calendaire.** 20 RPD glissant
  = 1 requête toutes les ~72 min. Un benchmark de 62 appels prend
  75 h avec. Lire le `retryDelay` de Google sur un vrai échec est
  plus informatif que les blogs tiers.
- **Un prompt système sans consigne d'abstention ne produit pas
  nécessairement plus d'hallucinations qu'avec.** Flash-Lite libre
  a quand même refusé 77 % des questions (reformulations). Mais
  parmi les 23 % de « réponses », 4 sur 7 sont des inventions
  claires. Taux d'hallucination conditionnel ≈ 57 %.
- **Le modèle hallucine avec confiance maximale (`high`).** C'est
  la raison précise pour laquelle on construit un RAG : forcer
  la citation d'un extrait concret du rapport, qui ne peut pas
  venir d'un prior sur « augmentation de X TND ».
- **Les hallucinations numériques sont ciblées par forme de
  question**, pas par difficulté : les comparaisons et calculs
  déclenchent des patterns génératifs, pas les extractions pures.

### Fichiers modifiés dans la session (final)

- `bilanlens/llm.py` : `DEFAULT_MODEL = "gemini-3.5-flash-lite"`.
- `bilanlens/prompts.py` : `SYSTEM_INSTRUCTION_B0_LIBRE` +
  `prompt_version_b0_strict` + `prompt_version_b0_libre`.
- `scripts/evaluate_b0.py` : `--variante`, `--model`, `--only`,
  `slug_modele`, `run_id_defaut`, `contient_chiffre_significatif`,
  `est_abstention_large`, `_formater_vraie_reponse`,
  `afficher_stats_libre` (3 sections : extractions, chiffrées, autres).
- `tests/test_evaluate_b0.py` : +15 tests.
- `results/b0.jsonl` : 82 lignes au total, 3 runs cohabitants
  (`b0_d1ef73ef27f98dd4` historique incomplet,
  `b0_gemini35flashlite_d1ef73ef27f98dd4` 31/31,
  `b0libre_gemini35flashlite_21c68d1cba543eeb` 31/31).

---

## 2026-11-02 (soir) — Étape 6 V1 : RAG top-k, 31 Q, k=5

### Ce que j'ai fait

- Nouveau script `scripts/evaluate_v1.py` : encodage de la question
  via `charger_encodeur()` (Gemini embedding-2, task `RETRIEVAL_QUERY`),
  `collection.query(n_results=k)` sur Chroma, formatage du contexte
  `=== Extrait N : doc, page X ===` dans l'ordre du rang, appel LLM
  avec le MÊME `SYSTEM_INSTRUCTION` (strict) que B0 + template V1
  avec consigne de citation.
- Schéma JSON V1 à 3 clés : `answer`, `confidence`, `cited_extraits`
  (positions 1-based dans la liste de contexte, PAS numéros de page
  absolus car à `k=5` les extraits peuvent venir de plusieurs
  entreprises).
- `run_id = v1_<slug>_k<top_k>_<prompt_version>` : `top_k` dans l'ID
  pour qu'un futur run `--top-k 10` ne soit pas court-circuité par
  le checkpoint. Vérifié par test unitaire.
- Nouveau fichier `tests/test_evaluate_v1.py` : 15 tests, LLM/encodeur/
  collection faux, `FakeEncoder` sous `hashlib.sha256` (pas `hash()`
  builtin, qui varie entre runs). Fonctions `pages_attendues`,
  `recall_ok` couvertes.
- Recall@k mesuré par catégorie : `(doc, page_physique)`. Pour un
  calcul (`intermediate_values` présents), TOUTES les pages des
  valeurs intermédiaires doivent être dans le top-k (protocole §3.1).
- Rejoué `b0_gemini35flashlite_90b019c736aa621c` sur les 26 questions
  restantes → run B0-strict complet 31/31, cohérent avec le run V1.
- Supprimé "DEUX cles" du `SYSTEM_INSTRUCTION` : le schéma JSON
  (`response_schema` API) impose déjà les champs ; mentionner un
  nombre fixe obligerait à réécrire le prompt à chaque ajout de clé
  (`cited_extraits` en V1).

### Résultats V1 Flash-Lite k=5 sur 31 questions

| Métrique | V1 (RAG k=5) | B0 strict (plancher) |
|---|---|---|
| Chiffrées | 15/31 | 0/31 |
| « donnée non disponible » | 14/31 (45 %) | 31/31 (100 %) |
| parse_ok=False | 0 | 0 |
| citations invalides | 0 | — |
| latence moyenne | 1,05 s | 0,83 s |

**Recall@5 par catégorie — (doc, page) attendu dans le top-5 :**

| Catégorie | Recall@5 | Note |
|---|---|---|
| extraction | 8/9 | la base la plus solide |
| calcul | 5/7 | 2 calculs échouent recall car page intermédiaire manquante (ex. Q23 ROA : page 4 absente du top-5) |
| comparaison | 4/6 | |
| texte_annexes | 2/5 | **le point faible** ; les notes annexes diluent sur plusieurs pages |
| sans_reponse | n/a | 4 Q, pas de page attendue |

### Points marquants

- **Q10 (monoprix_consolide, calcul 13,03 %)** : page 3 bien
  récupérée au rang 1 (cited=[1]), mais le modèle calcule
  `49 423 396 / 299 295 661` (total passif hors capitaux propres)
  = 16,51 % au lieu de `49 423 396 / 379 260 923` = 13,03 %. **Recall
  OK, exactitude KO** — l'erreur est sémantique (lecture de « Total
  passif »), pas documentaire. Motive la mesure séparée recall /
  exactitude à l'étape 7.
- **Q23 (ciments_bizerte, ROA 2 pages)** : page 4 (résultat net)
  absente du top-5. **Recall KO** sur un calcul multi-page.
  **(Correction au 2026-11-05 — cf. entrée étape 8)** : j'avais
  écrit « abstention correcte » ci-dessous, c'est trompeur. Le
  résultat net apparaît en réalité page 52 (chunk rang 4,
  intitulé « RESULTAT COMPTABLE APRES IMPÔTS -44 790 355 »).
  Donc `valeurs_dans_contexte=True` malgré `recall@5 KO` strict,
  et la classe exacte est `abstention_a_tort_recall_ko` (pas
  `abstention_correcte`, qui est réservé aux Q `sans_reponse`).
  Le modèle avait la matière, il s'est abstenu quand même.
- **Hallucinations numériques** sans contexte (B0-libre, 4 cas,
  conf=high) → avec RAG, remplacées soit par abstention soit par
  réponse citée correcte. Le RAG réduit l'invention en forçant un
  ancrage textuel.

### Décisions prises

| Décision | Justification |
|---|---|
| `cited_extraits` positions 1-based (pas numéros de page absolus) | À k=5 sans filtre, les extraits peuvent venir de plusieurs entreprises : « page 4 » est ambigu |
| Correspondance (doc, page, chunk_id) dans `results.retrieved`, pas dans la réponse LLM | Sépare ce que le modèle a cité de la vérité technique Chroma |
| `top_k` dans le `run_id` | Deux runs k=5 vs k=10 doivent cohabiter sans collision de checkpoint |
| Stocker `retrieved` SANS les textes dans `results/v1.jsonl` | Fichier déjà 150-200 Ko à 5 chunks × 31 Q ; les textes vivent dans Chroma |
| Mesure Recall@k basée sur `calculation.intermediate_values` quand présent | Protocole §3.1 : TOUTES les pages requises doivent être retrouvées |
| Même `SYSTEM_INSTRUCTION` strict pour B0 et V1 | La différence doit mesurer l'effet du RAG, pas un changement de consigne |

### Ce que j'ai appris

- **Un bon recall ne garantit pas une bonne réponse.** Q10 est
  exemplaire : page 3 au rang 1, cité, et pourtant erreur de
  calcul sémantique (deux « totaux passifs » coexistent sur un bilan
  consolidé). V2 devra peut-être enrichir le prompt avec la
  définition pédagogique du cours.
- **Les notes annexes sont le point faible de l'embedding.** Recall
  2/5 sur `texte_annexes` : les questions comme « méthode de
  valorisation des pièces de rechange » matchent faiblement avec
  les pages d'annexes où l'info est noyée dans du texte long. Une
  stratégie : sous-découpage par note (NCT X, Note Y) plutôt que
  par page.
- **Les calculs multi-page tombent sur le recall, pas sur le LLM.**
  Q23 ROA : le modèle refuse honnêtement car il ne voit QUE page 2
  (total actif), pas page 4 (résultat net). Avec k=10, la page 4
  remonterait sans doute. Compromis à mesurer.
- **Flash-Lite est-il discipliné en V1 ?** Oui pour les extractions
  pures (8/9 reconstituées à l'identique, y compris 1 281 772 854,965
  avec 3 décimales sur SFBT), moins pour les calculs (hallucination
  numérique Q10 sous contexte correct).

### Fichiers modifiés dans la session

- `bilanlens/prompts.py` : SYSTEM_INSTRUCTION sans « DEUX cles » (B0
  strict ET libre), TEMPLATE_V1_USER avec consigne cited_extraits,
  JSON_SCHEMA_REPONSE_V1 (3 clés), `prompt_version_v1()`.
- `scripts/evaluate_v1.py` : nouveau, 440 lignes.
- `tests/test_evaluate_v1.py` : nouveau, 15 tests.
- `tests/test_evaluate_b0.py` : adaptation `test_system_instruction_b0_libre`.
- `results/b0.jsonl` : run `b0_gemini35flashlite_90b019c736aa621c` complet.
- `results/v1.jsonl` : run `v1_gemini35flashlite_k5_a3c4180afaeb900e` complet.

---

## 2026-11-05 — Étape 7 : score.py, recall séparé de l'exactitude

### Ce que j'ai fait

- Nouveau script `scripts/score.py` qui sépare strictement deux
  dimensions : (1) **recall** = les pages attendues sont-elles
  dans le top-k Chroma ? ; (2) **exactitude** = la réponse du
  modèle colle-t-elle au benchmark ?
- Classes exclusives (7) : `juste`, `fausse_recall_ok`,
  `fausse_recall_ko`, `abstention_a_tort_recall_ok`,
  `abstention_a_tort_recall_ko`, `abstention_correcte`,
  `reponse_a_tort`.
- Top-20 Chroma par question → 5 niveaux de recall (k ∈
  {1, 3, 5, 10, 20}) + MRR en une seule query par Q. **0 appel
  LLM, 0 appel API embeddings** (les 31 embeddings questions
  sont dans le cache `data/cache_embeddings/`).
- Nouvel indicateur **séparé** `valeurs_dans_contexte` : True
  ssi toutes les valeurs numériques attendues apparaissent dans
  la concaténation des 5 chunks du run V1 (après compression
  des séparateurs de milliers). `null` pour texte_annexes et
  sans_reponse.
- Annotations manuelles versionnées dans
  `data/benchmark/annotations_texte.jsonl` (champs : `statut`,
  `complete`, `elements_manquants`, `justification`). Q04 et Q08
  annotées, règle « juste = répond à ce que la question
  demande ; un complément absent n'invalide pas la réponse mais
  est noté ».
- Nouveau fichier `results/retrieval_top20.jsonl` (top-20 brut,
  ne touche PAS à `v1.jsonl`), nouveau `results/scores.jsonl`.
- En-tête `evaluate_v1.py` corrigé : la règle « toutes les
  pages attendues » vaut pour TOUTE question avec
  `intermediate_values` (calcul OU comparaison), pas juste
  « calcul ».
- 34 tests unitaires (parser numérique, direction, exactitude
  par format, recall@k, MRR, 7 classes, lecture annotations,
  intégration scorer_question).

### Résultats du scoring V1 (run `v1_gemini35flashlite_k5_a3c4180afaeb900e`)

| Classe | N / 31 |
|---|---|
| `juste` | **16** |
| `fausse_recall_ok` | 1 (Q10) |
| `fausse_recall_ko` | 0 |
| `abstention_a_tort_recall_ok` | 4 |
| `abstention_a_tort_recall_ko` | 6 |
| `abstention_correcte` | 4 |
| `reponse_a_tort` | 0 |

**Recall@k** (sur les 27 Q avec page attendue) :

| k | Recall@k |
|---|---|
| 1 | 10/27 (37 %) |
| 3 | 14/27 (52 %) |
| 5 | **19/27 (70 %)** ← conforme à l'analyse Étape 6 |
| 10 | 24/27 (89 %) |
| 20 | 25/27 (93 %) |

**MRR = 0,543.**

**Valeurs_dans_contexte** (indépendant du recall) : True=21,
False=1 (Q30), N/A=9 (5 texte_annexes + 4 sans_reponse).

**Réponses incomplètes** (annotation manuelle) : 1
- `sotuver_2024_04` : juste mais omet la clause « provision
  pour dépréciation sur les articles à rotation lente ou
  obsolètes » (présente dans le chunk p. 9 récupéré).

### Points marquants

- **Q10 reste le seul cas `fausse_recall_ok`** : page 3 récupérée
  au rang 1, mais interprétation sémantique fausse de « Total
  passif » → 16,51 % au lieu de 13,03 %.
- **4 `abstention_a_tort_recall_ok`** : calculs où la page
  principale était récupérée et le modèle refuse quand même
  (Q02, Q06, Q14, Q19). C'est le signal le plus clair pour la
  **V1.1** (variante : mêmes chunks V1, consigne modifiée dans
  `TEMPLATE_V1_USER`) : revoir la consigne stricte ou enrichir
  le prompt avec la définition des formules du cours. **Ne pas
  confondre avec V2** (planning §V2), qui est une refonte du
  retrieval en recherche hybride BM25 + vecteurs + filtrage
  par entreprise/année — V2 et V1.1 testent des leviers
  différents.
- **Q07, Q20, Q23, Q28** : recall@5 KO strict mais `valeurs_dans_
  contexte=True`. À séparer en deux : (a) **Q07, Q20 répondent
  juste** (classe `juste`) parce que les 2 valeurs de la
  comparaison sont sur la même page via plusieurs colonnes ;
  (b) **Q23, Q28 s'abstiennent** malgré la matière présente
  (Q23 : résultat net lisible page 52 au rang 4 sous
  « Résultat comptable après impôts »). **Recall@10 = 24/27
  (89 %)** le confirme pour Q23 : sa page 4 est au rang 6.
- **Pas un seul `fausse_recall_ko` et pas un seul `reponse_a_
  tort`** : quand Flash-Lite n'a pas la matière, il abstient. Le
  RAG a bien neutralisé les 4 hallucinations numériques
  identifiées en B0-libre.

### Décisions prises

| Décision | Justification |
|---|---|
| Cosinus informatif seulement, pas critère d'exactitude | Distances élevées même pour textes peu liés (Q23 page 1 à 0,18) |
| Classes exclusives : `juste` ⟂ `abstention_correcte` ⟂ `reponse_a_tort` | Lisibilité de la table de résultats |
| Tolérance absolue par défaut = 1 pour les montants | Les rapports BVMT arrondissent au dinar ; diff=1 courant (Q24) |
| `valeurs_dans_contexte` séparé du recall | Métrique indépendante : Q23 est recall KO strict mais valeurs OK |
| Annotations manuelles versionnées | `data/benchmark/annotations_texte.jsonl` : trace + justification + complétude |
| Règle « juste = répond au besoin ; complément absent toléré » | Q08 juste même sans NCT 11, car NCT 11 décrit le traitement, pas le motif |
| Mode d'annotation stocké par ligne dans scores.jsonl | `manuel` pour Q04/Q08 ; `automatique` pour tout le reste |
| top-20 écrit dans un fichier SÉPARÉ `retrieval_top20.jsonl` | Préserve `v1.jsonl` et son `run_id` |

### Ce que j'ai appris

- **La métrique Recall@k seule ne suffit pas.** Deux Q
  (Q07, Q20) ont recall@5 KO strict mais `valeurs_dans_
  contexte=True` et le modèle y répond juste : les valeurs sont
  lues sur une AUTRE page que la page attendue (Q07 : p. 2 au
  lieu de p. 9 ; Q20 : p. 17-18 au lieu de p. 3). Deux autres
  (Q23, Q28) ont le même profil mais s'abstiennent. Une
  question (Q30) a recall KO ET valeurs absentes. Trois
  comportements distincts derrière « recall@5 KO ».
- **Le passage de k=5 à k=10 ferait monter le recall de
  70 % à 89 %.** Compromis à mesurer en V2 : avec k=10, risque
  d'augmenter les hallucinations de type Q10 (contexte plus
  volumineux, modèle plus distrait).
- **Flash-Lite a un biais à l'abstention sur les calculs sous
  contexte.** 4 Q sur 7 calculs avec recall OK finissent en
  abstention. Un prompt enrichi (formule explicitée) pourrait
  débloquer ces cas sans toucher au recall.
- **Les annotations manuelles sont rentables à ce stade.** 2
  annotations suffisent à scorer sans ambiguïté les 2 réponses
  `texte_annexes` chiffrables ; plus propre qu'un seuil cosinus
  arbitraire.

---

## 2026-11-05 (soir) — Étape 8 : comparaison B0-strict / B0-libre / V1

### Ce que j'ai fait

- Nouveau mode `scripts/score.py --mode compare` qui score les
  **3 runs enregistrés** avec les mêmes règles, écrit
  `results/scores_compare.jsonl` (93 lignes = 31 × 3), produit
  un tableau et un SVG `results/comparison_B0_V1.svg`. **0
  appel LLM, 0 appel API embeddings** (cache intégralement chaud).
- Nouveau détecteur `score.est_abstention` : combine `est_
  abstention_large` (patterns `_PATTERNS_ABSTENTION_LARGE` déjà
  existants dans `evaluate_b0.py`) avec un garde-fou « pas de
  chiffre significatif ». Captures les **pseudo-abstentions**
  B0-libre (« n'est pas disponible dans le rapport », « n'est
  pas précisée ») sans reclasser à tort une réponse chiffrée
  qui contiendrait ce motif comme complément. **Vérification :
  V1 reste à 20/31** après le changement, identique à l'étape 7.
- Nouveau classifier `classer_b0` avec **5 classes exclusives**
  (`CLASSES_B0`) sans suffixe recall : `juste`, `fausse`,
  `abstention_a_tort`, `abstention_correcte`, `reponse_a_tort`.
  Cohérent avec le fait que B0 n'a pas de retrieval.
- Fichier `data/benchmark/annotations_texte.jsonl` étendu avec
  un champ `run_id` par ligne. 2 annotations V1 (Q04 juste
  incomplète, Q08 juste complète) + 3 annotations B0-libre
  (Q04 fausse — piège commissaires ; Q08 juste complète avec
  note « aucune source » ; Q21 fausse — méthode inventée).
  Q12 et Q25 B0-libre : **pas d'annotation** car détectées
  automatiquement comme pseudo-abstentions → classées
  `abstention_a_tort`.

### Résultats

**Prompt_version par run** (le hash change si `SYSTEM_INSTRUCTION`
ou `TEMPLATE_*_USER` bouge) :

| Run | prompt_version | SYSTEM_INSTRUCTION |
|---|---|---|
| B0-strict | `90b019c736aa621c` | `SYSTEM_INSTRUCTION` (strict) |
| **B0-libre** | `21c68d1cba543eeb` | **`SYSTEM_INSTRUCTION_B0_LIBRE`** (différent : pas de consigne d'abstention) |
| V1 | `a3c4180afaeb900e` | `SYSTEM_INSTRUCTION` (strict, identique à B0-strict) |

Les hash V1 et B0-strict diffèrent uniquement à cause du
`TEMPLATE_USER` (V1 ajoute contexte RAG + consigne `cited_
extraits`). Le prompt système reste byte-à-byte identique.
**B0-libre utilise un prompt système différent**, d'où l'écart
non comparable sur la consigne.

**Bons résultats par catégorie :**

| Catégorie | B0-strict | B0-libre | V1 | Total |
|---|---|---|---|---|
| extraction | 0 | 0 | **8** | 9 |
| calcul | 0 | 0 | 0 | 7 |
| comparaison | 0 | 0 | **6** | 6 |
| texte_annexes | 0 | 1 | **2** | 5 |
| sans_reponse | 4 | 4 | 4 | 4 |
| **TOTAL** | **4/31** | **5/31** | **20/31** | 31 |

**Sur les 27 questions avec réponse attendue (hors sans_reponse) :**

| Run | Justes | Fausses |
|---|---|---|
| B0-strict | 0 | 0 (tout en abstention) |
| B0-libre | 1 | 6 |
| V1 | 16 | 1 |

**Attention à la comparaison** : B0-strict et V1 partagent
exactement `SYSTEM_INSTRUCTION` (même consigne stricte, seul le
TEMPLATE_USER change) → **c'est la seule paire qui isole
rigoureusement l'effet du RAG**. B0-libre utilise un prompt
système différent (`SYSTEM_INSTRUCTION_B0_LIBRE`, sans consigne
d'abstention) : l'écart V1 vs B0-libre mélange effet du RAG ET
effet du prompt, à ne pas lire comme une mesure pure.

**V1 — Recall@k (sur 27 Q avec page attendue) et MRR** :

| k | Recall@k |
|---|---|
| 1 | 10/27 (37 %) |
| 3 | 14/27 (52 %) |
| **5** | **19/27 (70 %)** |
| 10 | 24/27 (89 %) |
| 20 | 25/27 (93 %) |
| MRR | **0,543** |

**Répartition B0-libre (ce que l'ablation du prompt libère)** :

| Classe B0-libre | N |
|---|---|
| juste | 1 (Q08) |
| fausse | 6 (4 hallucinations numériques + Q04 piège commissaires + Q21 méthode inventée) |
| abstention_correcte | 4 (sans_reponse) |
| abstention_a_tort | 20 (le modèle « sait qu'il ne sait pas » pour la majorité) |
| reponse_a_tort | 0 |

Sur les 27 Q non-sans_reponse, Flash-Lite libre répond pour
seulement 7 (1 juste + 6 fausses) et s'abstient pour 20. Le
taux d'hallucination conditionnel ≈ 86 % (6/7).

### Séparation des 11 échecs V1

Les 20 « bons » (16 justes + 4 abstentions correctes) laissent
**11 échecs** à expliquer, décomposables en 3 groupes disjoints :

**(a) Problèmes de recherche (4)** — recall@5 KO ET valeurs
absentes du top-5. À traiter en V2 côté retrieval :
`monoprix_consolide_2024_12`, `sfbt_2024_21`,
`ciments_bizerte_2024_25`, `delice_holding_2024_30`.

**(b) Abstentions avec valeurs présentes dans le top-5 (6)**
— le modèle a la matière mais refuse. **Toutes les 6 sont
des calculs** (Q02, Q06, Q14, Q19, Q23, Q28). Détail recall :
- recall@5 OK : `sotuver_2024_02`, `sotuver_2024_06`,
  `monoprix_2024_14`, `sfbt_2024_19`.
- recall@5 KO strict mais valeurs dans contexte via une
  **autre page que la page attendue** : `ciments_bizerte_
  2024_23` (résultat net aussi en p. 3 « Résultat de l'exercice »
  au rang 2, ET en p. 52 « Résultat comptable après impôts »
  au rang 4) ; `delice_holding_2024_28` (résultat net aussi
  en p. 10 au rang 3). **La cause de l'abstention reste
  inconnue** : le modèle a plusieurs instances de la valeur
  dans son contexte, sous des libellés variés. **Piste
  principale à tester en V1.1** (variante prompt, même
  retrieval) : la consigne stricte (« donnée non disponible »
  au moindre doute) ou le passage au calcul numérique bloquent
  plus que la reconnaissance de libellé — les 6 cas sont tous
  des calculs, aucun simple extraction.

**(c) Réponse fausse (1)** — `monoprix_consolide_2024_10` :
recall OK, valeurs dans contexte, mais calcul sémantique
faux (16,51 % au lieu de 13,03 %).

**Point distinct (pas un échec) : justes malgré recall@5 KO
(2)** — `sotuver_2024_07`, `sfbt_2024_20`. Les valeurs sont
lues sur une **autre page que la page attendue** : Q07 trouve
ses 2 valeurs en p. 2 (au lieu de p. 9 attendue), Q20 en
p. 17-18 (au lieu de p. 3 attendue). Important pour la
calibration : Recall@k par couple (doc, page) est un proxy
imparfait de la qualité quand la même ligne du bilan apparaît
sur plusieurs pages.

### Décisions prises

| Décision | Justification |
|---|---|
| `est_abstention` combine `est_abstention_large` + « pas de chiffre significatif » | Capture les pseudo-abstentions B0-libre sans reclasser une réponse chiffrée partiellement « non disponible » |
| 5 classes B0 (sans suffixe recall) | B0 ne fait pas de recherche ; mettre `_recall_ok` serait trompeur |
| Annotations indexées par `(run_id, question_id)` | Une même Q peut avoir des réponses différentes selon le prompt ; l'annotation aussi |
| SVG généré sans matplotlib | Pas de nouvelle dépendance ; graphique simple suffit pour l'étape 8 |
| Pin `ubuntu-24.04` en CI | `ubuntu-latest` = resolute depuis 2026-10-19 ; le PPA Tesseract ne la supporte pas encore |

### Ce que j'ai appris

- **B0-strict vs V1 à prompt système identique.** Sur les 27 Q
  avec réponse attendue : 0 juste / 0 fausse en B0-strict contre
  16 justes / 1 fausse en V1. C'est la seule paire qui isole
  rigoureusement l'effet du RAG (B0-libre a un prompt différent,
  à ne pas comparer directement). La réponse juste B0-libre
  (Q08) ne prouve aucune maîtrise du corpus : « aucune source »
  noté dans l'annotation, le modèle n'a pas consulté le rapport.
- **Le prompt système change le mode d'échec, pas la justesse.**
  B0-strict s'abstient partout (sauf sans_reponse), B0-libre
  invente 6 fois et s'abstient 20 fois.
- **Séparer recall et exactitude a de la valeur.** V1 a 11
  échecs : 4 problèmes de recherche + 6 abstentions avec
  valeurs présentes + 1 réponse fausse (Q10). Chaque groupe
  pointe vers une variante différente : les problèmes de
  recherche motivent **V2** du planning (BM25 + vecteurs +
  filtrage entreprise/année), les abstentions avec valeurs
  motivent **V1.1** (prompt revisité à chunks identiques),
  Q10 motive une revue indépendante (lecture de « Total
  passif »). Q07 et Q20 sont justes malgré recall@5 KO strict
  et ne comptent pas dans les échecs.
- **Les pseudo-abstentions sont un piège méthodologique.** Sans
  le filtre « pas de chiffre significatif », une réponse
  chiffrée qui contient aussi un pattern d'abstention en
  surplus pourrait être reclassée à tort en abstention. Le
  filtre évite cette confusion. (Q10 réelle = `16,51 %`, pas
  concernée ici — c'est l'exemple générique qui motive le
  filtre.)

### Expérience proposée pour la V1.1 (pas lancée ici)

**Clarification de nommage.** Ce que je décris ci-dessous
s'appelle **V1.1**, pas V2. La V2 du planning (cf.
`docs/planning.md` §V2) est une refonte du retrieval en
**recherche hybride BM25 + vecteurs, avec filtrage par
entreprise et année** — autre levier, autre expérience.
V1.1 ne touche pas au retrieval : mêmes chunks V1 réutilisés
tels quels.

Les 6 Q `abstention_a_tort` avec valeurs présentes sont **toutes
des calculs**. Une seule variable à manipuler, tout le reste
constant, pour tester la piste « consigne prudente bloque les
calculs » :

- **Relancer les 31 questions** avec exactement les mêmes
  chunks V1 (top-5 déjà enregistrés dans `results/v1.jsonl`).
  Reconstruction locale du contexte via `score.py --mode
  rebuild-context` : lit les textes depuis `data/chunks/*.jsonl`
  et les ordonne selon le `retrieved` V1. **Zéro appel Chroma,
  zéro appel API embeddings** (vérifié par test de
  non-régression `test_reconstruire_contexte_v1_toutes_les_
  31_q` : les 31 Q se reconstruisent avec **longueur, chunk_id
  et ordre identiques** au top-5 V1 d'origine,
  `len(ctx) == context_rendered_chars`).
- **Modifier UNE SEULE consigne**, et **dans `TEMPLATE_V1_
  USER` uniquement**, pas dans `SYSTEM_INSTRUCTION`. Raison :
  `SYSTEM_INSTRUCTION` reste byte-à-byte identique entre
  B0-strict et V1 pour que l'écart B0-strict vs V1 mesure
  rigoureusement l'effet du RAG. Toucher à `SYSTEM_
  INSTRUCTION` casserait cette propriété de comparaison.
  La consigne ajoutée s'insère dans le template utilisateur
  (déjà porteur de la consigne `cited_extraits`), de sorte
  que le bascule « prudent → calcul explicite » soit scopée
  à V1 et le nouveau run.
- **Critère principal** : évolution du score sur les **7
  calculs** (Q02, Q06, Q10, Q14, Q19, Q23, Q28). L'hypothèse
  prédit une baisse des `abstention_a_tort` et une hausse des
  `juste`. **Si la hausse va plutôt dans `fausse`**, ne pas
  conclure directement à une limite du modèle : analyser
  d'abord ces réponses fausses (quelle erreur ? quels chunks
  cités ? valeurs du contexte bien lues ? erreur d'arithmétique
  ou de lecture ?) avant de trancher.
- **Contrôle anti-invention** : les **4 sans_reponse** (Q05,
  Q16, Q26, Q31) doivent rester en `abstention_correcte`, et
  aucune autre Q ne doit basculer vers `fausse` ou
  `reponse_a_tort`. Si l'assouplissement provoque de nouvelles
  réponses fausses, la consigne révisée n'est pas acceptable
  même si elle résout les calculs.

Cette expérience distingue l'hypothèse « consigne trop prudente »
de l'hypothèse « capacité limite du modèle sur les calculs ».

---

### Étape 8 — close

Évaluation terminée. Les étapes 1 à 8 du planning sont livrées :
B0 (strict + libre), V1 (RAG k=5), métriques (recall, exactitude,
valeurs_dans_contexte, 7 classes), comparaison à prompt système
identique sur 31 Q.

Deux variantes identifiées pour la suite (aucune lancée ici) :
- **V1.1** (expérience ci-dessus) : mêmes chunks V1, UNE consigne
  modifiée dans `TEMPLATE_V1_USER`. Teste la piste « consigne
  prudente bloque les calculs ».
- **V2** du planning : recherche hybride BM25 + vecteurs + filtrage
  par entreprise/année. Teste la piste « retrieval dense seul
  rate les lignes de note » (4 Q `problemes_recherche` : Q12, Q21,
  Q25, Q30).

### Fichiers modifiés dans la session

- `.github/workflows/tests.yml` : `ubuntu-latest` → `ubuntu-24.04`.
- `scripts/score.py` : nouveau mode `--mode compare`,
  `est_abstention` basé sur abstention large + absence de chiffre,
  `classer_b0`, `scorer_question_b0`, `CLASSES_B0`, synthèse
  par catégorie, SVG sans matplotlib.
- `tests/test_score.py` : +12 tests (`est_abstention_*`,
  `classer_b0_*`, filtrage annotations par `run_id`).
- `data/benchmark/annotations_texte.jsonl` : champ `run_id` par
  ligne, +3 annotations B0-libre.
- `results/scores_compare.jsonl` : nouveau, 93 lignes.
- `results/comparison_B0_V1.svg` : nouveau, graphique groupé.
- `scripts/evaluate_v1.py` : commentaire header élargi (« calcul
  OU comparaison »).

---

## 2026-11-06 — V1.1 : mêmes chunks + consigne calcul

### Ce que j'ai fait

- Nouveau `bilanlens/prompts.py:TEMPLATE_V1_1_USER` = TEMPLATE_V1_USER
  + une consigne calcul exacte (fournie par l'utilisateur).
  `SYSTEM_INSTRUCTION` reste byte-à-byte identique à B0-strict et V1
  pour préserver la paire de comparaison. `JSON_SCHEMA_REPONSE_V1`
  inchangé : pas de nouveau champ dans la réponse.
- Nouveau `scripts/evaluate_v1_1.py` qui **relit `results/v1.jsonl`
  + les chunks depuis `data/chunks/*.jsonl`**, reconstruit le
  contexte (longueur, chunk_id et ordre identiques au top-5 V1 —
  vérifié par `test_reconstruire_contexte_v1_toutes_les_31_q`), et
  n'appelle que le LLM. **Zéro appel Chroma, zéro appel API
  embeddings.**
- Run V1.1 sous `v1_1_gemini35flashlite_k5_d2bbaa1f9adda0ab`,
  écrit dans `results/v1_1.jsonl` (31 lignes) ; `results/v1.jsonl`
  n'est pas modifié.
- Nouveau mode `scripts/score.py --mode v1-1` qui score V1.1 avec
  les mêmes règles que V1, réutilise `results/retrieval_top20.jsonl`
  + chunks locaux (pas de recall@k recalculé en ligne) et produit
  la comparaison classe-par-classe.
- Annotations manuelles Q04 et Q08 dupliquées sous
  `run_id=v1_1_...` — les réponses texte V1.1 sont **identiques
  byte-à-byte** à V1 pour les 5 Q `texte_annexes`, donc même
  verdict applicable.

### Résultats

**Par classe V1 → V1.1 :**

| Classe | V1 | V1.1 | Δ |
|---|---|---|---|
| `juste` | 16 | **18** | **+2** |
| `fausse_recall_ok` | 1 | 3 | +2 |
| `fausse_recall_ko` | 0 | 1 | +1 |
| `abstention_a_tort_recall_ok` | 4 | 1 | −3 |
| `abstention_a_tort_recall_ko` | 6 | 4 | −2 |
| `abstention_correcte` | 4 | 4 | 0 |
| `reponse_a_tort` | 0 | 0 | 0 |

**Par catégorie (juste + abstention_correcte) :**

| Catégorie | V1 | V1.1 |
|---|---|---|
| extraction | 8/9 | 8/9 |
| **calcul** | **0/7** | **3/7** |
| comparaison | 6/6 | 5/6 |
| texte_annexes | 2/5 | 2/5 |
| sans_reponse | 4/4 | 4/4 |
| **TOTAL** | **20/31** | **22/31** |

**Score secondaire** (juste strict + 1 comparaison « valeur
exacte, direction manquante » — Q07) = **23/31**. Critère
**post-hoc**, défini après avoir vu le résultat V1.1 ; à
mentionner comme tel dans tout reporting.

### Détail des 7 calculs V1 → V1.1

| qid | Benchmark | V1 | V1.1 | Verdict V1.1 |
|---|---|---|---|---|
| Q02 sotuver | 34,53 % | abstention | **52,74 %** | `fausse_recall_ok` |
| Q06 sotuver | 1,9 | abstention | abstention | **abstention inexpliquée** |
| Q10 monoprix_c | 13,03 % | 16,51 % | 16,51 % | inchangé |
| Q14 monoprix | 0,93 % | abstention | **0,93 %** | **juste** ✅ |
| Q19 sfbt | 74,43 % | abstention | **291,07 %** | `fausse_recall_ok` |
| Q23 ciments | −11,52 % | abstention | **−11,52 %** | **juste** ✅ |
| Q28 delice | 9,48 % | abstention | **9,48 %** | **juste** ✅ |

**3 nouvelles justes (Q14, Q23, Q28), 2 nouvelles fausses (Q02, Q19).**

### Correction d'analyse — Q02 et Q19 ne sont PAS des hallucinations

Q02 (52,74 %) et Q19 (291,07 %) partagent la **même erreur
sémantique** que Q10 (16,51 %) : le modèle divise les capitaux
propres par le **total des passifs (dettes)** au lieu du **total
du bilan (capitaux propres + passifs)**. Vérification
arithmétique :

- Q02 : 120 964 179 / 229 345 985 = **52,74 %** (vraie formule :
  120 964 179 / 350 310 164 = 34,53 %)
- Q10 : 49 423 396 / 299 295 661 = **16,51 %** (vraie :
  49 423 396 / 379 260 923 = 13,03 %)
- Q19 : 954 001 282 / 327 771 572 = **291,07 %** (vraie :
  954 001 282 / 1 281 772 854 = 74,43 %)

Les valeurs sont toutes lues correctement dans le contexte. Le
modèle confond **« Total passif »** (= total du bilan, convention
du cours) et **« Total des passifs »** (= dettes hors capitaux
propres, libellé du tableau). C'est une **erreur de vocabulaire
comptable, pas une invention**.

Avec la consigne V1.1 « fais le calcul exact », le modèle ne
s'abstient plus mais applique une formule sémantiquement fausse.
V1 abstenait sur ces 3 Q ; V1.1 répond, et fait l'erreur de
définition 3 fois sur 3 — pattern cohérent, pas aléatoire.

### Nouvelles fausses à analyser avant toute conclusion

**Q02, Q19** (règle « analyser avant de conclure à une limite du
modèle ») : réponses chiffrées produites par la consigne V1.1. Pas
un bug du LLM mais une ambiguïté terminologique du benchmark
lui-même (« Total passif » du cours ≠ « Total des passifs » du
bilan). Pistes :
- Préciser dans le prompt la définition de « Total passif » ?
  (ajouterait du biais spécifique BVMT).
- Reformuler la question pour lever l'ambigüité ?
- Accepter 2 formules et scorer les deux comme justes ? (non
  demandé ici, juste noté.)

### Régression Q07 (seule comparaison impactée)

| | V1 | V1.1 |
|---|---|---|
| `sotuver_2024_07` | « diminution de 18 577 651 TND entre 2023 et 2024 » | **« 18 577 651 TND »** |
| Classe | `juste` | **`fausse_recall_ko`** |

La consigne V1.1 « donne uniquement le résultat final avec son
unité » supprime le mot `diminution`. **Les 5 autres comparaisons
(Q03, Q11, Q15, Q20, Q24) conservent toutes la direction en
V1.1.** Q07 est la seule touchée.

Décision : garder le scoring strict (Q07 = fausse). Score
secondaire post-hoc (valeur absolue correcte, direction manquante)
proposé en complément, **explicitement signalé** comme défini
après avoir vu le résultat.

### Q06 : abstention inexpliquée

Q06 (endettement SOTUVER = Total dettes / Capitaux propres) reste
`donnee non disponible` en V1.1 alors que :
- Les 2 valeurs (229 345 985 et 120 964 179) sont dans le
  contexte, **au même chunk que Q02** (page 3).
- Q02 répond 52,74 % (chiffré, même paire de valeurs).
- Le calcul est trivial : 229 345 985 / 120 964 179 = 1,896.

**Mystère non résolu.** Peut-être la formulation de la question
(« endettement global... exprimé comme un multiple ») ou un
problème d'interprétation du mot « multiple », mais rien ne
l'explique proprement sur ce run.

### Contrôle anti-invention ✅

**Q05, Q16, Q26, Q31** (sans_reponse) : **4/4 abstentions
correctes**. Aucune bascule vers `fausse` ou `reponse_a_tort`.
Aucune autre Q ne gagne une réponse fausse non prévue (Q02 et Q19
étaient déjà en abstention en V1 et basculent vers `fausse_recall_ok`,
pas d'une Q juste V1 vers une Q fausse V1.1, sauf Q07 qui est un
cas spécifique de perte de direction, pas une hallucination).

### Décisions prises

| Décision | Justification |
|---|---|
| Score secondaire post-hoc pour Q07 | Classe stricte garde priorité ; critère de secours documenté comme ayant été défini après observation du résultat |
| Annotations Q04/Q08 dupliquées V1 → V1.1 | Réponses byte-à-byte identiques : même verdict applicable, pas une nouvelle annotation de jugement |
| Pas de modification du prompt pour corriger « Total passif » vs « Total des passifs » | Hors scope de V1.1 ; la V2 (retrieval hybride) est peut-être une meilleure réponse à cette ambigüité |

### Ce que j'ai appris

- **La consigne consignes/calcul débloque 3 des 6 calculs
  abstention-à-tort (Q14, Q23, Q28).** La piste « consigne trop
  prudente » n'est pas fausse : le modèle *peut* faire le calcul
  s'il est invité à le poser.
- **Mais elle convertit 2 abstentions prudentes en erreurs
  sémantiques (Q02, Q19).** Pas des hallucinations numériques :
  la même confusion « Total passif » = dettes que Q10 déjà en V1.
  Le pattern est cohérent (3/3 autonomies financières).
- **Les sans_reponse tiennent.** Le contrôle anti-invention
  passe : la consigne révisée ne provoque pas de nouvelles
  réponses sur les Q sans réponse.
- **Q07 est un dommage collatéral attendu.** « Donne uniquement
  le résultat final avec son unité » supprime la direction. Une
  V1.2 pourrait reformuler : « donne la direction et la valeur ».
  Mais c'est une 2e variation à tester, pas une correction locale.
- **Q06 reste inexpliquée.** Mêmes valeurs que Q02, question
  mécaniquement plus simple, le modèle refuse. Pas un biais de la
  consigne, pas un problème de recall.

### Fichiers de cette session

- `bilanlens/prompts.py` : `TEMPLATE_V1_1_USER`,
  `prompt_version_v1_1`.
- `scripts/evaluate_v1_1.py` : nouveau (reconstruction contexte
  depuis V1, 0 appel Chroma/embedding).
- `scripts/score.py` : `RUN_ID_V1_1`, `mode_v1_1`, champ
  `comparaison_valeur_seule_ok` dans le score, enrichissement de
  `exact_numerique` (direction_ok / valeur_ok séparés).
- `tests/test_evaluate_v1_1.py` : 7 tests.
- `data/benchmark/annotations_texte.jsonl` : +2 entrées V1.1
  (Q04, Q08).
- `results/v1_1.jsonl` : 31 lignes, run V1.1.
- `results/scores_v1_1.jsonl` : 31 lignes, scoring V1.1.


---

## 2026-11-06 (soir) — V1.2 : V1.1 + 2 règles anti-ambiguïté

### Ce que j'ai fait

- Nouveau `TEMPLATE_V1_2_USER` = `TEMPLATE_V1_1_USER` + deux règles
  issues de l'analyse post-hoc des erreurs V1.1 :
  - R1 : « Dans une formule d'autonomie financière, le total passif
    désigne le total des capitaux propres et des passifs (total
    du bilan). » → cible Q02/Q10/Q19 qui calculaient CP/dettes.
  - R2 : « Pour une variation ou une comparaison, indique aussi le
    sens (augmentation ou diminution). » → cible Q07 qui avait
    perdu la direction en V1.1.
- `SYSTEM_INSTRUCTION` reste byte-à-byte identique à V1 et B0-strict.
  Schéma JSON inchangé.
- Nouveau `scripts/evaluate_v1_2.py` : run V1.2 réutilise les chunks
  V1 (0 appel Chroma, 0 API embeddings). Écrit dans
  `results/v1_2.jsonl` sous `v1_2_gemini35flashlite_k5_
  634426d2b6bfde4e`. Les runs V1 et V1.1 ne sont pas modifiés.
- Nouveau mode `scripts/score.py --mode v1-2` qui compare V1.1 vs
  V1.2 Q par Q.
- 2 annotations texte V1.2 ajoutées (Q04 identique byte-à-byte à
  V1.1 ; Q08 formulé différemment mais même fond → `juste`,
  `complete=true` validé par l'utilisateur).

### Résultats V1.1 → V1.2

**Par classe :**

| Classe | V1.1 | V1.2 | Δ |
|---|---|---|---|
| `juste` | 18 | **20** | +2 |
| `fausse_recall_ok` | 3 | **0** | −3 |
| `fausse_recall_ko` | 1 | **0** | −1 |
| `abstention_a_tort_recall_ok` | 1 | 2 | +1 |
| `abstention_a_tort_recall_ko` | 4 | 5 | +1 |
| `abstention_correcte` | 4 | 4 | 0 |
| `reponse_a_tort` | 0 | 0 | 0 |

**Par catégorie :**

| Catégorie | V1.1 | V1.2 |
|---|---|---|
| extraction | 8/9 | 8/9 |
| **calcul** | 3/7 | **4/7** |
| **comparaison** | 5/6 | **6/6** |
| texte_annexes | 2/5 | 2/5 |
| sans_reponse | 4/4 | 4/4 |
| **TOTAL** | **22/31** | **24/31** |

**Justes parmi les réponses données (hors abstention) :**

| Run | Justes / Réponses données | % |
|---|---|---|
| V1.1 | 18 / 22 | 82 % |
| **V1.2** | **20 / 20** | **100 %** |

**Zéro nouvelle réponse fausse en V1.2.** Quand V1.2 répond, elle
a raison. Les erreurs résiduelles se traduisent en abstention,
pas en invention.

### Focus Q02, Q06, Q07, Q10, Q19 (cibles explicites des règles)

| qid | V1.1 | V1.2 | Verdict |
|---|---|---|---|
| **Q02** (34,53 %) | 52,74 % | **34,53 %** | ✅ règle R1 marche |
| Q06 (1,9) | abstention | abstention | inchangé (inexpliquée) |
| **Q07** (dim. 18,5 M) | « 18 577 651 TND » | **« diminution de 18 577 651 TND entre 2023 et 2024 »** | ✅ règle R2 marche |
| **Q10** (13,03 %) | 16,51 % | **13,03 %** | ✅ règle R1 marche |
| **Q19** (74,43 %) | 291,07 % | **74,43 %** | ✅ règle R1 marche |

### Régressions V1.1 → V1.2 à signaler

| qid | V1.1 | V1.2 |
|---|---|---|
| **Q14** monoprix (0,93 %) | « 0,93 % » ✅ | **abstention** |
| **Q23** ciments (−11,52 %) | « −11,52 % » ✅ | **abstention** |

Ces 2 Q ne sont pas des autonomies financières (R1 ne s'applique
pas) et ne sont pas des variations (R2 ne s'applique pas non plus).
Pas d'explication directe par les règles. Hypothèse (à vérifier) :
la densité de contraintes dans TEMPLATE_V1_2_USER rend le modèle
plus prudent sur tous les calculs, même ceux qui n'étaient pas
ciblés. Un test V1.3 avec les règles séparées (R1 seule vs R2
seule) trancherait, mais **ce n'est pas lancé ici** (pas de V1.3
sans accord utilisateur).

### Contrôle anti-invention ✅

- **Q05, Q16, Q26, Q31** (sans_reponse) : 4/4 abstentions correctes.
- **0 reponse_a_tort**, **0 fausse** sur tous les runs.
- La trajectoire V1 → V1.1 → V1.2 : les erreurs de type
  « fausse » disparaissent au profit d'abstentions.

### Avertissement méthodologique important

**Les deux règles de V1.2 ont été écrites APRÈS avoir vu les
erreurs de V1.1 sur ce benchmark**. Ce sont des règles fit
post-hoc, pas des règles dérivées d'un principe indépendant :
- R1 (« total passif = total du bilan ») répond à une convention
  pédagogique du cours de finance, pas à une norme comptable
  généralement vraie.
- R2 (« indiquer le sens ») corrige un artefact de la consigne
  V1.1 (« donne uniquement le résultat final »).

**Cette calibration doit être revalidée sur de nouvelles questions
de benchmark avant toute conclusion de généralisation.** À
l'échelle de 31 Q et 4 autonomies financières (Q02, Q10, Q19 +
le cas déjà juste Q19 sfbt), le pattern des règles peut être un
hasard de l'échantillon. Une version du benchmark avec au moins
10 nouvelles autonomies financières sur d'autres exercices /
d'autres entreprises est nécessaire pour trancher.

### Décisions prises

| Décision | Justification |
|---|---|
| V1.2 garde TEMPLATE_V1_1_USER + 2 règles | Préserve la cumulativité : V1.2 corrige V1.1 sans tout casser |
| Pas de V1.3 (R1 seule / R2 seule) | Pas lancé sans accord utilisateur |
| Annotation Q04/Q08 V1.2 avec texte différent pour Q08 | Fond identique, même verdict applicable |
| Journal signale explicitement le fit post-hoc | Avertissement méthodologique pour toute lecture ultérieure |

### Ce que j'ai appris

- **La règle « total passif = total du bilan » corrige 3/3
  autonomies financières.** C'est le signe qu'une ambiguïté
  terminologique du benchmark existait et que le modèle pouvait
  être guidé sans tricher. Mais il faut noter que cette
  règle est un **choix de convention** (celle du cours) ; les
  commissaires aux comptes de certains rapports utilisent l'autre
  définition (« Total passifs » = dettes).
- **R2 corrige exactement Q07.** Les 5 autres comparaisons
  conservaient déjà leur direction en V1.1 ; R2 ne les a pas
  dégradées.
- **Les régressions Q14/Q23 sont inexpliquées par les règles.**
  Elles n'étaient ni autonomie financière, ni comparaison. La
  piste « prompt trop dense » est plausible mais non vérifiée.
  Un test V1.3 avec règles séparées éclaircirait.
- **Score des réponses données : 100 % en V1.2.** Aucune réponse
  fausse sur ces 31 questions, avec un prompt réglé sur ce
  benchmark. Dans un cadre de production où une mauvaise réponse
  coûte plus cher qu'une abstention, c'est une propriété
  recherchée, à confirmer sur un benchmark neuf avant toute
  généralisation.

### Fichiers de cette session

- `bilanlens/prompts.py` : `TEMPLATE_V1_2_USER`,
  `prompt_version_v1_2()`.
- `scripts/evaluate_v1_2.py` : nouveau (0 Chroma, 0 embedding).
- `scripts/score.py` : `RUN_ID_V1_2` dynamique, `mode_v1_2`,
  focus sur Q02/Q06/Q07/Q10/Q19.
- `tests/test_evaluate_v1_2.py` : 5 tests.
- `data/benchmark/annotations_texte.jsonl` : +2 entrées V1.2.
- `results/v1_2.jsonl` (31 lignes) + `results/scores_v1_2.jsonl`
  (31 lignes).


---

## 2026-11-06 (nuit) — Test de répétabilité V1.2 + plan V2

### Test de répétabilité V1.2

Relancé V1.2 une seconde fois sur les 31 questions, mêmes
chunks reconstruits depuis V1, même `TEMPLATE_V1_2_USER`, même
`SYSTEM_INSTRUCTION`, même `temperature=0.0`, même modèle
Flash-Lite. Écrit dans `results/v1_2_repeat.jsonl` sous run_id
suffixé `_repeat`. `results/v1_2.jsonl` n'est pas modifié.

**Résultats :**

- **27 / 31 Q** : réponse strictement identique (byte-à-byte).
- **4 / 31 Q** : variations de surface sans changement de classe
  (toutes restent `juste`).

Détail des 4 divergences :

| qid | V1.2 initial | V1.2 repeat | Classe |
|---|---|---|---|
| `delice_holding_2024_27` | « 58 382 497 TND » | « 58 382 497 **dinars** » | juste (synonymes) |
| `sfbt_2024_20` | « ... entre le **31 décembre 2023 et le 31 décembre 2024** » | « ... entre **2023 et 2024** » | juste (formulation plus courte) |
| `sotuver_2024_04` | « ... sont **évalués** à ... » | « ... sont **évalues** à ... » | juste (accent perdu) |
| `sotuver_2024_08` | « La société a reclassé les moules **pour refléter plus fidèlement la nature durable des moules** et aligner... » | « La société a reclassé les moules **pour une meilleure présentation** en **reflets plus fidèlement** la nature durable... » | juste (ordre et phrasé changés) |

### Enseignements

- **La classe V1.2 est stable sur ce run répété.** Aucune
  bascule entre classes malgré 4 divergences textuelles. Le
  scoring basé sur `parser_premier_nombre` + `parser_direction`
  absorbe les variations d'unité (TND / dinars) et de
  formulation (« entre 2023 et 2024 » vs plus long).
- **Flash-Lite à `temperature=0.0` n'est PAS déterministe
  bit-à-bit.** 4 divergences sur 31 appels au même prompt avec
  les mêmes extraits. Suffixes qui bougent, perte d'accent
  (Q04 : « évalués » → « evalues »), reformulation du même
  motif (Q08). C'est un rappel que **« temperature=0 »
  n'implique pas « sortie déterministe »** : sampling top-k au
  tie-breaker, ordres de tokens quasi-équivalents, etc.
- **Les 4 extractions chiffrées cibles (Q01, Q09, Q13, Q17,
  Q18, Q22, Q27, Q29, Q30) ont toutes la même valeur et la
  même classe.** Un seul changement de surface (Q27 TND →
  dinars), zero différence numérique. Les valeurs sont
  robustes.
- **Les 2 réponses texte_annexes annotées (Q04, Q08) varient
  en formulation mais pas en fond.** Les annotations manuelles
  utilisées sont celles de V1.2 initial (`juste`,
  `complete` identique), et le scoring les applique au repeat
  par absence d'annotation spécifique au `v1_2_repeat_...` run_id.
  Dans un reporting académique, on devrait soit (a) annoter
  aussi le repeat pour vérifier que le même verdict tient,
  soit (b) se limiter au score chiffré.

### Avertissement

Ce test de répétabilité est **une seule relance**, pas une
statistique sur N relances. Pour une vraie mesure de
reproducibilité on ferait 5-10 relances et on rapporterait
`std` sur la fréquence de changement de classe.

### Fichiers de cette session

- `scripts/evaluate_v1_2.py` : argument `--output` pour écrire
  dans un chemin alternatif sans toucher à `results/v1_2.jsonl`.
- `results/v1_2_repeat.jsonl` : 31 lignes, run_id
  `v1_2_repeat_gemini35flashlite_k5_634426d2b6bfde4e`.

---

## Plan V2 (corrigé 2026-11-06 — pas de code écrit, pas de run)

**Objectif V2** (`docs/planning.md` §V2) : recherche hybride
BM25 + vecteurs, avec **filtrage par entreprise seulement**
(le filtre année est désactivé sur ce corpus, cf. §Filtres).
**Prompt V1.2 gardé tel quel** (`SYSTEM_INSTRUCTION` +
`TEMPLATE_V1_2_USER` inchangés). Seul le pipeline retrieval
change.

### Motivation

Les 4 Q `problemes_recherche` V1 (Q12, Q21, Q25, Q30) ont
`recall@5=KO`. Côté `valeurs_dans_contexte` :
- **Q30** (extraction, montant « 32 944 357 ») : `False` — la
  valeur attendue est absente du top-5.
- **Q12, Q21, Q25** (toutes `texte_annexes`) : `null` — pas
  de valeur numérique à chercher, l'indicateur est hors scope.

Dans les 4 cas l'embedding dense peine, soit sur un chiffre
isolé (Q30), soit sur du texte d'annexe dilué dans du texte long
(Q12/Q21/Q25). BM25 attrape les mots-clés exacts comme « coût
moyen pondéré » ou « 900 000 tonnes » que l'embedding lisse.

Filtrage par entreprise observé utile : à k=20 sur Q23, les
rangs 10 et 11 sont des pages `sfbt_2024` au lieu de
`ciments_bizerte_2024` — pages sémantiquement proches,
documentairement hors sujet.

### §1. Filtres (règles définies ex ante)

- **Filtre année — DÉSACTIVÉ sur ce corpus.** Les 6 rapports
  sont tous de l'exercice 2024. Une question qui cite 2023
  (ex. Q07 « stocks bruts au 31 décembre 2023 par le
  retraitement NCT 11 ») fait toujours référence à une colonne
  interne au rapport 2024, pas à un rapport 2023 séparé. **Ne
  pas filtrer sur l'année citée dans la question.**
  Si un futur benchmark introduit des exercices différents
  (2023 ou 2025), rouvrir ce filtre.
- **Filtre entreprise — avec garde-fous :**
  - Si la question mentionne sans ambigüité une seule
    entreprise (ex. « SOTUVER », « Ciments de Bizerte »,
    « Délice Holding », « SFBT ») → filtre à cette entreprise.
  - Si la question ne tranche pas entre `monoprix_2024`
    (individuel) et `monoprix_consolide_2024` → **garder les
    deux** dans le périmètre de recherche.
  - Si l'entreprise n'est pas reconnue → **pas de filtre**,
    retour à la recherche globale.
- **Note sur le benchmark actuel :** les 31 questions nomment
  toutes leur société. Le benchmark ne testera donc pas le cas
  « entreprise non reconnue ». C'est un angle mort à mesurer sur
  de nouvelles questions.

### §2. Comparaison retrieval SANS LLM (5 configurations)

Avant de lancer le moindre run LLM, mesurer sur les 31 Q la
qualité de retrieval des configurations suivantes :

| Config | Description |
|---|---|
| **dense** | Baseline V1 déjà enregistrée dans `results/retrieval_top20.jsonl`. |
| **BM25** | BM25 seul sur les chunks locaux. |
| **hybride RRF** | Fusion rangs dense + BM25 via Reciprocal Rank Fusion. |
| **dense + filtre entreprise** | Dense restreint au périmètre de l'entreprise de la Q **AVANT** la construction du top-50. |
| **hybride + filtre entreprise** | Fusion RRF sur dense-filtré + BM25-filtré (filtre appliqué AVANT la construction des 2 listes top-50). |

**Règle de filtrage (identique pour les 2 configs filtrées) :**
le filtre entreprise selon §1 réduit le périmètre des chunks
candidats *avant* le calcul des scores dense et BM25. Pour une
question à entreprise unique, on cherche dans les chunks du
seul document correspondant ; pour « Monoprix » ambigu, dans
les chunks des deux documents (individuel + consolidé). Ainsi
les listes top-50 dense et BM25 ne contiennent jamais de chunks
hors périmètre, et la fusion RRF n'a pas à les repêcher.

**Métriques pour chaque configuration :**

- Recall@1, Recall@3, Recall@5, Recall@10, Recall@20 (sur 27 Q
  avec page attendue).
- MRR (sur les mêmes 27 Q).
- **Rangs des pages attendues** par Q, pour inspecter les
  migrations (ex. page 4 ciments_bizerte passe-t-elle de rang 6
  à rang 3 avec BM25 ?).

Zéro appel LLM à ce stade. Seulement BM25 local + vecteurs
cached + fusion.

### §3. Hyperparamètres définis AVANT de coder

Tous les paramètres ci-dessous sont **figés avant toute mesure**
et versionnés dans `bilanlens/bm25.py` / `retrieval_hybride.py` :

- **Tokenisation française.**
  - Minuscules.
  - Accents retirés (NFKD + suppression des marks).
  - **Regroupement des nombres séparés par des espaces** en un
    seul token, **dans les chunks ET dans les questions** (même
    règle des deux côtés, sinon le match échoue). Exemples :
    - `100 836 224` → `100836224`
    - `1 281 772 854,965` → `1281772854,965`
    - `268.125.000` → `268125000` (points de milliers aussi
      compressés)
    - `l'exercice` → `l`, `exercice` (découpe aux apostrophes
      typographiques U+2019 et droites U+0027)
  - **Séparation aux apostrophes** : « l'exercice » → 2 tokens
    `l` + `exercice`, « d'actions » → `d` + `actions`.
  - **Pas de stemming.** On garde les formes telles quelles.
    Les variantes `provision` / `provisions` resteront 2 tokens
    distincts ; l'IDF compensera.
  - **Stop words conservés (baseline).** Les mots fréquents
    (« de », « et », « à », « la ») restent dans l'index. Le
    choix est baseline par simplicité et pour que l'IDF du
    corpus financier fasse le travail — et non parce qu'on
    veut « préserver des expressions ». Si la mesure montre
    qu'un stop-list classique améliore Recall@5, V2.1 pourra
    la tester explicitement.
  - **CORRECTIF POST-HOC (ajouté après mesure V2) :**
    l'argument « l'IDF fait le tri » est FAUX avec
    `rank_bm25 0.2.2`. `BM25Okapi` remplace tout IDF ≤ 0 par
    `eps = 0.25 × average_idf`, ce qui donne un **plancher
    d'environ 1,15** aux mots très fréquents (« de » mesuré à
    1,148 ; « resultat » à 1,221). Les stop words contribuent
    donc au score. V2.1 ajoute un filtre d'une liste publique
    de stop words français (NLTK FR, recopiée dans
    `bilanlens/bm25.py` avec sa source). Mesure : BM25 seul
    passe de 13/27 à 18/27 au Recall@5, hybride_filtre passe
    de 19/27 à 22/27. **Cette décision n'était PAS prise ex
    ante** — elle est documentée dans l'entrée journal du
    2026-11-06 (soir, 2).
  - **Ordre stable** (voir aussi plus bas) : la tokenisation
    est déterministe, pas de hash dependent-du-process.
- **BM25 — paramètres.**
  - `k1 = 1.5` (valeur standard rank_bm25).
  - `b = 0.75` (valeur standard rank_bm25).
  - Rationale : **pas d'ajustement sans donnée**. Les deux
    valeurs sont les défauts documentés de la littérature et de
    `rank_bm25`. Un seul changement = un seul axe de variance
    à discuter ; on commence par le standard.
- **RRF — paramètres.**
  - Taille des listes avant fusion : **top-50** dense ET top-50
    BM25 (donne de la marge pour que la fusion remonte des
    chunks lointains).
  - Constante k RRF : **k = 60** (valeur canonique de la
    littérature TREC).
  - Score d'un chunk : `Σ_i 1 / (k + rang_i)` sur les listes
    où il apparaît.
- **Ordre stable des résultats (reproducibilité).** À chaque
  étape où deux chunks ont le même score (BM25, dense, RRF),
  la clé de tri secondaire est **le `chunk_id` par ordre
  alphanumérique croissant** (ex. `ciments_bizerte_2024_p2_s0`
  avant `ciments_bizerte_2024_p3_s0`). Cette règle est
  appliquée dans les 3 modules (BM25, dense, RRF) et doit
  faire l'objet d'un test unitaire (deux chunks à score
  identique → ordre `chunk_id` croissant).
- **Version épinglée :** `rank_bm25 == 0.2.2` (dernière stable
  au 2026-11-06 ; à ajouter dans `requirements.txt`).

**Test de tokenisation (à écrire avec le module) :** vérifier
que `tokeniser("Revenus 100 836 224 TND de l'exercice 2024")`
produit une liste qui contient `100836224` (regroupé),
`revenus`, `tnd`, `de`, `l`, `exercice` (découpé à
l'apostrophe) et `2024`. Idem avec `1 281 772 854,965` →
`1281772854,965` et `268.125.000` → `268125000`.

### §4. Critère de choix de configuration (écrit AVANT de voir les résultats)

**La configuration retenue pour la V2 sera celle qui maximise
`Recall@5` sur les 27 Q avec page attendue, à égalité départagée
par `MRR` plus élevé.** Seuil impératif : `Recall@5 > 19/27`
(strictement supérieur au dense V1). **Si aucune configuration
ne dépasse 19/27, on garde le dense V1 et on ne lance PAS de
run LLM V2.** Une égalité à 19/27 est un match nul : pas assez
pour justifier le coût d'implémentation et l'ajout de
complexité, donc la V2 n'est pas lancée.

**Sous-contraintes de garde-fou :**

- Le filtrage entreprise doit garder une **couverture 100 % des
  31 Q** (pas de question qui se retrouve avec un périmètre
  vide à cause d'un filtre trop strict).
- Si deux configurations sont à égalité stricte sur Recall@5
  *et* MRR, préférer la plus simple (BM25 seul > hybride, pas
  de filtre > filtre).

Ce critère est écrit **ici, dans le journal, avant d'exécuter
les mesures**. Toute dérogation devra être justifiée dans le
commit qui lance la V2.

### §5. UN SEUL run LLM après choix

Une fois la configuration élue selon §4, **un seul run LLM**
avec :

- Prompt V1.2 (SYSTEM_INSTRUCTION + TEMPLATE_V1_2_USER).
- `k = 5` pour le contexte envoyé (identique V1/V1.2).
- Même modèle `gemini-3.5-flash-lite`.
- Même `temperature = 0.0`.
- Même format de ligne jsonl que `evaluate_v1_2.py`.

Écrit dans `results/v2.jsonl` sous run_id dédié `v2_
<slug>_k5_<prompt_version_v1_2>_<config_retrieval>`.

**Comparaison V2 vs V1.2** sur les mêmes règles que V1.2
(`score.py --mode v2`) :

1. Classes par catégorie (CLASSES 7).
2. `valeurs_dans_contexte` par Q.
3. Détail des 6 Q d'intérêt : **Q12, Q14, Q21, Q23, Q25, Q30**
   (les 4 problemes_recherche + les 2 régressions V1.2).
4. Les **4 sans_reponse** (Q05, Q16, Q26, Q31) : contrôle
   anti-invention.
5. **Montrer toute nouvelle réponse `texte_annexes`** avant de
   l'annoter (comme pour V1.1 et V1.2).

### §6. Structure code (à écrire)

| # | Fichier | Rôle | Tests |
|---|---|---|---|
| 1 | `bilanlens/bm25.py` | Indexation + recherche BM25 sur chunks locaux. Tokenisation définie §3. | construction + top-k sur corpus toy ; absence de normalisation chiffres |
| 2 | `scripts/build_bm25.py` | Indexe `data/chunks/*.jsonl` une fois, sauvegarde sur disque. | test idempotence |
| 3 | `bilanlens/retrieval_hybride.py` | RRF sur 2 listes top-50 → fusion. Paramètres §3. | fusion 2 rangs → score attendu ; cas liste vide |
| 4 | `bilanlens/filtre_question.py` | Détection entreprise selon §1. Table de synonymes versionnée. | 31 Q du benchmark ; cas Monoprix ambigu → périmètre à 2 |
| 5 | `scripts/benchmark_retrieval.py` | Lance les 5 configs sans LLM, écrit `results/retrieval_compare.jsonl` + stats. | test agrégation sur fake data |
| 6 | `scripts/evaluate_v2.py` | Pipeline V2 avec la config retenue. | faux BM25 + faux dense + faux LLM |
| 7 | `scripts/score.py --mode v2` | Scoring V2 selon règles V1.2. | diag V2 similaire V1.1/V1.2 |

### §7. Métriques V2 à produire au total

1. **Recall@k et MRR** des 5 configurations retrieval (§2).
2. **Taux de filtre réussi** par entreprise :
   - Nb de Q correctement filtrées à la bonne entreprise.
   - Nb de Q où le périmètre est « Monoprix individuel +
     consolidé » (ambigüité gardée).
   - Nb de Q sans filtre (entreprise non reconnue).
3. **Classes V2** (7), par catégorie, comparé à V1.2.
4. **valeurs_dans_contexte V2** vs V1.2.
5. **Évolution des 6 Q cibles** (Q12, Q14, Q21, Q23, Q25, Q30)
   et des 4 sans_reponse.
6. **Nouvelles réponses fausses** (contrôle, cf. règle V1.1/V1.2).
7. **Coût V2 vs V1.2** : LLM identique, latence totale, taille
   contexte envoyé.

### §8. Validation externe nécessaire

Le risque de **réglage sur le benchmark** porte sur trois
leviers, à distinguer :

1. **Règles du filtre entreprise (§1)** : la table de
   synonymes (« SOTUVER », « SNMVT », « SFBT », « Délice »,
   « Ciments de Bizerte », règles de désambiguation Monoprix)
   est construite à la main sur les 31 Q. **Fit benchmark.**
2. **Configuration retrieval retenue (§4)** : parmi les 5 Confs
   testées, on choisit celle qui maximise Recall@5 sur les
   27 Q. **Fit benchmark.**
3. **Prompt V1.2** : règles R1 (« total passif = total du
   bilan ») et R2 (« indique le sens ») issues de l'analyse
   post-hoc des erreurs V1.1. **Déjà fit benchmark**, déjà
   signalé dans l'entrée V1.2.

**En revanche, les hyperparamètres BM25/RRF (§3) sont fixés
avant la mesure** et ne sont pas un point de fit : `k1=1.5`,
`b=0.75`, `k_RRF=60`, listes top-50, tokenisation déterministe.
Ils sont pris aux valeurs standard de la littérature,
documentés tels dans `requirements.txt` + modules.

**Le réglage final V2 devra être validé sur un benchmark neuf :**

- Nouvelles autonomies financières (≥ 5 Q, autres entreprises /
  exercices) pour tester le prompt V1.2 et son règlage « total
  passif ».
- Nouvelles questions `texte_annexes` sur méthodes comptables
  rares pour tester si le gain BM25 généralise.
- Nouvelles Q `sans_reponse` dont l'entreprise n'est pas nommée
  pour tester le cas « pas de filtre » (non couvert par le
  benchmark actuel).

Sans cette validation, les chiffres V2 racontent uniquement ce
qui marche sur ce benchmark particulier, pas une amélioration
généralisable.

### §9. Risques listés

- **Ambigüité Monoprix** : le filtre garde les deux docs quand
  la question dit « Monoprix » sans qualifier. Peut diluer la
  sélection pour Q13 (« SNMVT-Monoprix » individuel) si le
  filtre n'extrait pas « SNMVT ». À tester explicitement.
- **BM25 et chiffres : atténué par la règle §3.** La
  tokenisation regroupe les nombres séparés par espaces en un
  seul token (`100 836 224` → `100836224`), appliquée aux
  chunks ET aux questions. Un montant devient donc un token
  unique avec un IDF très élevé (il n'apparaît que sur une ou
  deux pages du corpus). Le risque résiduel est les montants
  dont les séparateurs varient entre chunks (`1 281 772 854,965`
  vs `1281772854.965`) — à surveiller à l'inspection des rangs.
- **RRF k = 60** : canonique, mais peu interprétable sur des
  listes de 50. Vérifier que les scores ne s'écrasent pas.
- **Ties côté tokenisation** : deux chunks aux scores égaux
  pourraient apparaître dans un ordre non reproductible. Mitigé
  par la règle d'ordre stable §3 (tie-break = `chunk_id`
  alphanumérique croissant).

### §10. Décisions figées pour V2

- Prompt V1.2 inchangé.
- 6 corpus BVMT 2024, modèle Flash-Lite, k=5 pour contexte final.
- `rank_bm25 == 0.2.2`, `k1=1.5`, `b=0.75`, `k_RRF=60`,
  listes top-50 avant fusion.
- Critère §4 (Recall@5 max, MRR en départage) **écrit avant les
  mesures**.
- Aucun code V2 écrit, aucun run V2 lancé dans ce journal.


---

## 2026-11-06 (fin de journée) — V2 : code retrieval + benchmark 5 configs (sans LLM)

### Ce que j'ai fait

Appliqué le plan V2 §3 et §6 (étapes 1 à 4), sans toucher au
prompt V1.2 et sans lancer de run LLM.

Quatre modules / scripts créés :

1. **`bilanlens/bm25.py`** — tokenisation V2 + index BM25 global.
   - Tokenisation : lowercase, NFKD + retrait des accents,
     regroupement nombres séparés par UN SEUL espace, points de
     milliers compressés entre chiffres, découpe aux
     apostrophes U+2019 et U+0027, pas de stemming, stop-words
     conservés.
   - BM25Okapi (rank_bm25 0.2.2) avec `k1=1.5`, `b=0.75`.
   - Tie-break : `chunk_id` alphanumérique croissant.
   - Tests : 18 cas (y compris le cas edge « 732 595 162 684 081 159 »
     fusion de colonnes monoprix p.21 → un seul token, documenté
     mais pas d'exception spéciale).
2. **`bilanlens/filtre_question.py`** — détection entreprise.
   - Table de synonymes versionnée pour les 4 entreprises simples
     (SOTUVER, SFBT, Ciments de Bizerte, Délice Holding).
   - Désambiguation Monoprix : mots-clés `consolide|consolidee|groupe`
     → consolidé ; `snmvt|individuel|individuelle` → individuel ;
     sinon → ambigu = garde les 2 docs.
   - Entreprise non reconnue → `None` (pas de filtre).
   - Filtre année : désactivé (§1, corpus tout 2024).
   - Tests : 43 cas, dont les 31 Q du benchmark (toutes filtrées
     correctement → couverture 100 %).
3. **`bilanlens/retrieval_hybride.py`** — fusion RRF.
   - `k_RRF=60`, listes top-50 avant fusion (§3 verrouillé).
   - Tie-break : chunk_id croissant.
   - Tests : 10 cas (cas réaliste 50+50, score cumulé 2 listes,
     listes vides, tie-break, etc.).
4. **`scripts/benchmark_retrieval.py`** — les 5 configs sur 31 Q,
   zéro appel LLM, zéro appel réseau.
   - Embeddings lus directement depuis
     `data/cache_embeddings/gemini-embedding-2.jsonl` (sha256
     identique à `bilanlens.embeddings._hash_cle`). 278 entrées
     en cache couvrant 247 chunks (RETRIEVAL_DOCUMENT) + 31
     questions (RETRIEVAL_QUERY).
   - Cosine exact sur vecteurs unit-norm Gemini (produit scalaire).
   - Pour les 2 configs filtrées, le filtre entreprise est appliqué
     AVANT la construction des listes top-50 dense et BM25
     (§2, « filtre avant »). Pour BM25 filtré, l'index est
     reconstruit sur le périmètre (IDF recalculée sur le
     sous-ensemble).
   - Validation : dense recalculé vs `retrieval_top20.jsonl` →
     **les 31 Q ont exactement les mêmes 20 premiers chunk_ids**.
     Baseline V1 reproduite à l'identique.

### Résultats des 5 configurations (27 Q avec page attendue)

| Config | R@1 | R@3 | R@5 | R@10 | R@20 | MRR |
|---|---|---|---|---|---|---|
| **dense** (baseline V1) | 10 | 14 | **19** | 24 | 25 | 0.5430 |
| bm25 | 8 | 12 | 13 | 13 | 14 | 0.3676 |
| hybride_rrf | 9 | 14 | 15 | 16 | 25 | 0.4591 |
| **dense_filtre** | 11 | 15 | **20** | 25 | 26 | 0.5803 |
| hybride_filtre | 15 | 17 | 19 | 24 | 27 | 0.6721 |

Dense V1 reproduit exactement **19/27** à Recall@5 — baseline
validée.

### Rangs des pages attendues — questions d'intérêt

| qid | dense | bm25 | hybride_rrf | dense_filtre | hybride_filtre |
|---|---|---|---|---|---|
| monoprix_consolide_2024_12 | 6 | 1 | 1 | 6 | 1 |
| monoprix_2024_14 | 3 | — | 20 | 2 | 8 |
| sfbt_2024_21 | — | 1 | 15 | — | 8 |
| ciments_bizerte_2024_23 | 6,1 | —,— | 8,15 | 6,1 | 1,10 |
| ciments_bizerte_2024_25 | 9 | 1 | 2 | 9 | 1 |
| delice_holding_2024_30 | — | — | 12 | 15 | 8 |

Lecture (« a,b » = rang de chaque page attendue ;
« — » = pas dans top-20) :

- **Q12, Q25, Q21** (texte_annexes) : BM25 et hybride_filtre les
  mettent au rang 1. Le dense seul (filtré ou non) les enterre
  vers rang 6-9 (ou les rate comme Q21).
- **Q14** (calcul, SNMVT-Monoprix) : le filtre entreprise aide
  (3 → 2), mais hybride_filtre dégrade (3 → 8) : BM25 injecte
  du bruit.
- **Q23** (calcul ROA Ciments de Bizerte) : 2 pages attendues
  (bilan + état résultat). Aucune config ne les met toutes les
  deux dans le top-5 : la 2e page reste trop loin.
- **Q30** (dividendes Délice) : l'extraction est toujours hors
  top-5. `dense_filtre` et `hybride_filtre` la remontent dans
  le top-20 mais pas dans le top-5.

### Gains / pertes vs dense (sur R@5)

- **bm25** : +4 (Q07, Q12, Q21, Q25) / −10. Catastrophique sur
  les extractions / calculs classiques.
- **hybride_rrf** : +3 / −7. Le BM25 non filtré injecte des
  chunks d'autres sociétés qui flinguent dense.
- **dense_filtre** : **+1 (Q20) / −0**. Le filtre entreprise
  remonte la page de variation du capital social SFBT dans le
  top-5 sans rien perdre.
- **hybride_filtre** : +3 (Q07, Q12, Q25) / −3 (Q13, Q14, Q27).
  Égalité au R@5 mais MRR nettement supérieur (0.6721 vs 0.5803).
  BM25 déplace le bon chunk au rang 1 pour les Q d'annexes mais
  pousse hors top-5 des extractions simples.

### Couverture du filtre entreprise

- 31 / 31 Q filtrées à entreprise unique.
- 0 Q ambigüe (Monoprix désambiguation 100 % réussie sur ce
  benchmark).
- 0 Q sans filtre (toutes nomment leur société).

C'est la **couverture 100 %** garde-fou §4. Mais c'est aussi un
angle mort de ce benchmark : le cas « entreprise non reconnue »
(donc pas de filtre) n'est jamais exercé.

### Décision §4

Critère : Recall@5 **strictement** supérieur à 19/27, départagé
par MRR.

**Config retenue : `dense_filtre`** (R@5 = 20/27, MRR = 0.5803).

- `hybride_filtre` a un meilleur MRR (0.6721) mais son R@5 =
  19/27 n'est PAS strictement supérieur à 19. Le critère est
  écrit avant les mesures, donc on respecte : égalité = pas
  retenu.
- Les 3 autres configs (bm25, hybride_rrf, dense) sont
  inférieures au R@5 du dense baseline.

### Enseignements

- **La reproducibilité du dense a été le test le plus informatif
  avant d'ouvrir les métriques.** Si mon cosine manuel avait
  divergé de V1, je ne saurais pas distinguer « amélioration
  V2 » de « artefact numérique ». Le script avorte tant que les
  20 premiers chunk_ids ne sont pas identiques Q par Q.
- **Le BM25 seul perd beaucoup (R@5 = 13/27).** Les questions
  d'extraction / comparaison / calcul nomment des concepts
  comptables (« revenus », « capitaux propres », « autonomie
  financière ») sans recoupement lexical suffisant avec les
  pages du bilan qui donnent les chiffres. L'embedding
  « comprend » ce lien, pas BM25.
- **Hybride_rrf (sans filtre) est pire que dense.** Dans ce
  corpus BVMT, BM25 remonte des chunks d'autres sociétés avec
  des mots-clés communs (« capitaux propres », « stocks »). Ils
  polluent la fusion RRF. La fusion gagne seulement quand on la
  filtre d'abord par entreprise.
- **Le filtre entreprise seul (sans BM25) est l'amélioration
  gagnante.** +1 Q au R@5, 0 perte, implémentation simple.
  C'est la configuration la plus parcimonieuse qui satisfait
  le critère §4.
- **Hybride_filtre a un meilleur MRR mais paye des pertes sur
  des Q extraction simples.** 3 Q que dense remonte au rang
  2-3 tombent au rang 8 à cause du mélange BM25. La fusion
  déplace les rangs et change les perdants, pas seulement les
  gagnants. Un meilleur MRR global masque des régressions
  locales.
- **Les 4 problemes_recherche V1 (Q12, Q21, Q25, Q30) : la
  situation s'améliore mais reste mitigée.** Q12 et Q25
  passent au rang 1 côté hybride_filtre. Q21 reste KO sur
  dense (filtré ou non) et à rang 8 côté hybride_filtre. Q30
  reste hors top-5 partout.
- **Il faut 3 pages dans le top-5 pour Q23 ? Non, 2.** Aucune
  config ne les retrouve toutes les deux dans le top-5. La
  régression V1.2 sur Q23 ne peut pas être « réparée » par V2
  dense_filtre : page attendue 2 reste au rang 6.

### Fichiers créés / modifiés dans cette session

- `bilanlens/bm25.py` — module BM25 + tokenisation.
- `bilanlens/filtre_question.py` — détection entreprise.
- `bilanlens/retrieval_hybride.py` — fusion RRF.
- `scripts/benchmark_retrieval.py` — 5 configs, zéro LLM.
- `tests/test_bm25.py` — 18 tests.
- `tests/test_filtre_question.py` — 43 tests.
- `tests/test_retrieval_hybride.py` — 10 tests.
- `requirements.txt` — `rank_bm25==0.2.2` (épinglé §3).
- `results/retrieval_compare.jsonl` — 1 ligne par
  (config, question), 5 × 31 = 155 lignes.

Suite totale : **317 passed, 3 deselected** (zéro régression).

### Ce qui reste à faire (bloqué par feu vert)

- `scripts/evaluate_v2.py` : pipeline V2 avec `dense_filtre` +
  prompt V1.2 inchangé + k=5 contexte.
- `scripts/score.py --mode v2` : scoring V2 vs V1.2.
- UN run LLM V2 (après feu vert).

Ne pas coder tant que le feu vert n'est pas donné.



---

## 2026-11-06 (soir, 2) — V2.1 : stop words français ajoutés post-hoc

### Ce que j'ai fait

Après mesure V2 (bm25 seul à 13/27 au Recall@5), tracé l'IDF des
mots fréquents produit par `rank_bm25 0.2.2` sur le corpus BVMT :

- IDF plancher ≈ 1,148 pour « de » (présent dans quasi toutes les
  pages).
- IDF ≈ 1,221 pour « resultat » (très fréquent, financier).
- L'argument V2 « l'IDF fait le tri » est FAUX : `BM25Okapi`
  remplace tout IDF ≤ 0 par `eps = 0.25 × average_idf`, donc
  même les stop words contribuent ≈ 1,15 au score.

V2.1 est une variante de tokenisation, pas un changement de
pipeline retrieval :

- Seule nouveauté : filtre d'une liste publique de stop words
  français **après la tokenisation V2** (nombres regroupés,
  accents retirés, apostrophes découpées).
- **Pas d'autre changement** : `k1=1.5`, `b=0.75`, `k_RRF=60`,
  listes top-50, filtre entreprise avant top-50, tie-break
  chunk_id — tout est identique V2.
- Même tokenisation appliquée aux chunks et aux questions.
- Même critère §4 (R@5 strictement > 19/27, MRR en départage).

### Source de la liste de stop words

**NLTK 3.9, corpus `stopwords`, fichier `french`**, licence
Apache 2.0. Référence :
https://github.com/nltk/nltk_data, paquet `corpora/stopwords`,
fichier `french`.

Liste recopiée **verbatim** dans `bilanlens/bm25.py` sous
`_STOP_WORDS_FR_NLTK_VERBATIM`, puis normalisée localement
(minuscules + NFKD + retrait des accents) pour matcher les
tokens V2. La liste contient ~170 mots (articles, prépositions,
auxiliaires conjugués à toutes les personnes, lettres isolées
produites par les apostrophes françaises comme « l », « d »,
« c »). Je n'ai PAS construit la liste à partir des 31
questions.

### Décision post-hoc : traçabilité

Ce n'est pas un hyperparamètre ex ante. V2.1 a été décidée
**après** avoir vu que V2 BM25 restait à 13/27 au R@5 malgré
l'IDF supposé-trier. Le critère §4 est préservé tel quel
(`Recall@5 > 19/27` strict). Trois leviers à distinguer :

1. Hyperparamètres BM25 / RRF (§3) : fixés avant mesure,
   inchangés. Pas de fit benchmark.
2. Filtre entreprise (§1) : construit à la main, confirmé sur
   les 31 Q. Reconnu comme fit benchmark (§8).
3. Liste stop words (V2.1) : décidée après mesure V2. Reconnu
   comme fit benchmark (§8). Validation externe requise.

### Résultats V2 → V2.1 (sur 27 Q avec page attendue)

| Config | V2 R@5 | V2.1 R@5 | Δ | V2 MRR | V2.1 MRR | ΔMRR |
|---|---|---|---|---|---|---|
| dense | 19 | 19 | ± | 0.5430 | 0.5430 | ± |
| **bm25** | 13 | **18** | **+5** | 0.3676 | 0.5031 | **+0.1354** |
| **hybride_rrf** | 15 | **19** | **+4** | 0.4591 | 0.5961 | **+0.1370** |
| dense_filtre | 20 | 20 | ± | 0.5803 | 0.5803 | ± |
| **hybride_filtre** | 19 | **22** | **+3** | 0.6721 | 0.7136 | **+0.0415** |

Dense et dense_filtre sont strictement invariants (le tokenizer
ne joue que sur BM25). Toutes les configs qui font appel à BM25
gagnent au R@5. La plus grande amélioration en valeur relative
est bm25 seul (+5 sur une base de 13).

### Rangs des 6 Q d'intérêt, V2.1

| qid | dense | bm25 | hybride_rrf | dense_filtre | hybride_filtre |
|---|---|---|---|---|---|
| Q12 (monoprix_consolide, texte_annexes) | 6 | 1 | 1 | 6 | **1** |
| Q14 (monoprix_individuel, calcul) | 3 | — | 10 | **2** | **2** |
| Q21 (sfbt, texte_annexes) | — | 1 | 18 | — | 11 |
| Q23 (ciments_bizerte, calcul 2 pages) | 1,6 | —,9 | —,3 | 1,6 | 9,1 |
| Q25 (ciments_bizerte, texte_annexes) | 9 | 1 | 2 | 9 | **1** |
| Q30 (delice_holding, extraction) | — | 13 | 10 | 15 | **4** |

Notable V2.1 vs V2 :

- Q30 passe du rang 8 (V2 hybride_filtre) au rang 4 (V2.1
  hybride_filtre) → entre dans le top-5.
- Q14 passe du rang 8 (V2 hybride_filtre) au rang 2 (V2.1
  hybride_filtre) → la régression V2 est effacée.
- Q21 reste à rang 11 côté hybride_filtre V2.1 : même avec
  stop words retirés, le dense + le BM25 ne la remontent pas en
  top-5. Elle est structurellement difficile (méthode
  d'évaluation des stocks noyée dans un long texte d'annexe).

### Gains / pertes vs dense (R@5) — V2.1

- bm25 : +4 (Q07, Q12, Q21, Q25) / −5 (Q01, Q13, Q14, Q24, Q27).
  Net = −1, mais R@5 reste à 18 car Q21 est un gain net.
- hybride_rrf : +3 / −3. Net = 0, mais toutes gagnées sont des
  texte_annexes et toutes perdues sont des calculs / extractions.
- dense_filtre : +1 (Q20) / −0.
- **hybride_filtre** : +4 (Q07, Q12, Q25, Q30) / −1 (Q13).
  Net = +3.

### Décision §4 (critère INCHANGÉ)

**Config retenue : `v2.1 / hybride_filtre`** (R@5 = 22/27,
MRR = 0.7136).

**Résumé de la décision en trois points traçables :**

1. **+4 / −1 vs dense au Recall@5.** Gains sur Q07, Q12, Q25,
   Q30. Perte sur Q13 (SNMVT-Monoprix extraction qui passe
   hors top-5 à cause du mélange BM25). Net = +3.
2. **Configuration choisie parmi 10 configurations** (5 configs
   × 2 variantes de tokenisation V2 / V2.1). Les 5 configs V2
   restaient toutes soit sous 20/27 soit à 20/27 exactement ;
   seule V2.1 (post-hoc) dépasse strictement 19/27.
3. **L'IDF BM25 est recalculée sur le périmètre filtré.** Pour
   chaque question, un nouvel `IndexBM25` est construit sur le
   sous-ensemble de chunks de l'entreprise désambiguée par
   `bilanlens.filtre_question` (pas de filtration *a posteriori*
   de l'index global). C'est bien un index spécifique à
   l'entreprise, pas une restriction de rangs.

Impact sur les 4 Q `problemes_recherche` V1 :

| qid | rangs top-5 ? |
|---|---|
| Q12 monoprix_consolide (texte_annexes) | rang 1 → **DANS top-5** |
| Q21 sfbt (texte_annexes) | rang 11 → **HORS top-5** |
| Q25 ciments_bizerte (texte_annexes) | rang 1 → **DANS top-5** |
| Q30 delice_holding (extraction) | rang 4 → **DANS top-5** |

**3 des 4 Q `problemes_recherche` V1 entrent en top-5.** Q21
reste hors top-5 malgré V2.1, et devra être traitée par un
levier différent (chunking plus fin, ou passage sur PDF
corrigé, ou prompt-level — pas un correctif retrieval).

### Regroupement des nombres — comportement réel

Observation et documentation (pas de code modifié) :

- La règle V2 `(?<=\d) (?=\d)` fusionne **tous** les chiffres
  séparés par un seul espace, sans détection de groupes. Sur
  `monoprix_consolide_2024` p.21, 2 colonnes sont fusionnées à
  l'extraction PDF (OCR / pdfplumber) : exemple
  « 732 595 162 684 081 159 » devient un seul token de 18
  chiffres. Pas de règle spéciale.
- Une version plus stricte (par exemple : ne regrouper que des
  séquences de blocs 3-chiffres encadrés par un caractère
  non-chiffre) a été envisagée. Elle **ne changerait rien au
  BM25 seul** sur ce benchmark : un token de 18 chiffres a un
  IDF très élevé, certes, mais il ne match aucune question (les
  31 questions ne contiennent pas cette suite de chiffres).
  Comme la règle stricte complexifie le code sans gain mesuré,
  elle n'est pas adoptée.
- Avertissement documentation : si un futur benchmark introduit
  une question qui tape le milieu d'une colonne fusionnée (ex.
  « 162 684 081 »), le match BM25 échouera parce que le chunk
  contiendra `732595162684081159` et la question
  `162684081`. À surveiller si le PDF subit un re-extraction
  corrigée.

### Enseignements méthodologiques

- **« L'IDF du corpus fait le tri » est un argument à vérifier,
  pas une intuition.** Le plancher epsilon de `BM25Okapi`
  (0.25 × average IDF) invalide cette intuition sur un corpus
  domain-specific où presque tout document contient les mots
  les plus courants.
- **La décision post-hoc est légitime SI elle est tracée.** Ce
  qui est problématique : prétendre ex ante une décision
  réellement prise après mesure. Ce qui est propre :
  reconnaître dans le journal que la décision a été prise APRÈS
  mesure et l'ajouter à la liste de risques de fit benchmark.
  V2.1 a été décidée après mesure V2 → documenté comme tel,
  critère §4 préservé, liste stop words sourcée indépendamment
  (NLTK, pas construite depuis les 31 Q).
- **Les gains BM25 sur « texte_annexes » généralisent-ils ?**
  Validation externe requise. Sur ce benchmark, 3 des 4
  texte_annexes problématiques sont remontées en top-1 par
  BM25. Mais c'est 4 cas → c'est un signal, pas une preuve.
  Un benchmark neuf avec plus de Q d'annexes financières dirait
  si BM25 est systématiquement meilleur que l'embedding sur ce
  type de requête.
- **Un meilleur agrégat (MRR 0.5430 → 0.7136) peut masquer des
  régressions locales.** hybride_filtre V2.1 gagne +3 au R@5
  mais perd Q13 (SNMVT-Monoprix extraction) qui passe hors
  top-5. L'inspection Q par Q reste indispensable.

### Fichiers modifiés / créés

- `bilanlens/bm25.py` — ajout `STOP_WORDS_FR` (source NLTK FR,
  verbatim + normalisation locale) + `tokeniser_v2_1` + paramètre
  `tokenizer` sur `IndexBM25`.
- `scripts/benchmark_retrieval.py` — lance V2 + V2.1 (2
  variantes × 5 configs = 10 configurations), rapport comparatif,
  §4 décision sur l'ensemble.
- `tests/test_bm25.py` — +9 tests V2.1 (stop words list,
  tokeniser_v2_1, IndexBM25 avec tokenizer custom).
- `tests/test_benchmark_retrieval.py` — **25 nouveaux tests** sur
  fausses données (dense_top_k, enrichir, agreger,
  choisir_configuration, valider_dense_vs_v1, lancer_5_configs,
  ecrire_sortie, _hash_cle cohérence avec bilanlens.embeddings).
- `results/retrieval_compare.jsonl` — 2 × 5 × 31 = 310 lignes
  (champ `variante` ajouté).
- `docs/journal.md` — correction §3 Plan V2 (note post-hoc sur
  les stop words) + cette entrée.

Suite totale : **351 passed, 3 deselected** (zéro régression).

### Ce qui reste (bloqué par feu vert)

- `scripts/evaluate_v2.py` : pipeline V2 avec la config retenue
  `v2.1 / hybride_filtre` + prompt V1.2 inchangé + k=5 contexte.
- `scripts/score.py --mode v2` : scoring V2 vs V1.2.
- UN run LLM V2 (après feu vert).

Ne pas coder tant que le feu vert n'est pas donné.



---

## 2026-11-06 (soir, 3) — V2 run LLM + score V1.2 vs V2

### Ce que j'ai fait

Lancé une seule fois le pipeline V2 (`v2.1 / hybride_filtre` +
prompt V1.2 inchangé) sur les 31 Q du benchmark, Flash-Lite,
temperature = 0. Scoré le run avec `score.py --mode v2` : mêmes
règles que V1.2, comparaison classe par classe, categorie,
valeurs_dans_contexte, 8 Q cibles, 4 sans_reponse, nouvelles
fausses.

- 1 seul run LLM, 31 appels Flash-Lite.
- 3 annotations manuelles versionnées pour les texte_annexes
  avec réponse donnée (Q04, Q08, Q25), validées par l'utilisateur.

### Résultats globaux

| | V1.2 | V2 | Δ |
|---|---|---|---|
| Classes « juste » | 20 | 22 | +2 |
| Abstentions correctes | 4 | 4 | ± |
| Fausses | 0 | 1 | +1 |
| Abstentions à tort | 7 | 4 | −3 |
| **Bons résultats (juste + abst. correcte)** | **24/31** | **26/31** | **+2** |

Par catégorie (bons résultats = juste OR abstention_correcte) :

| Catégorie | V1.2 | V2 |
|---|---|---|
| extraction (9) | 8/9 | 8/9 |
| calcul (7) | 4/7 | 5/7 |
| comparaison (6) | 6/6 | 6/6 |
| texte_annexes (5) | 2/5 | 3/5 |
| sans_reponse (4) | 4/4 | 4/4 |
| **TOTAL** | **24/31** | **26/31** |

Recall@k et MRR (retrieval V2.1/hybride_filtre) :

| | V1.2 | V2 |
|---|---|---|
| Recall@1 | 10/27 | **15/27** |
| Recall@3 | 14/27 | **20/27** |
| Recall@5 | 19/27 | **22/27** |
| Recall@10 | 24/27 | **26/27** |
| Recall@20 | 25/27 | **27/27** (100 %) |
| MRR | 0.543 | **0.714** |

`valeurs_dans_contexte` (True/False/None) : V1.2 = 21/1/9 ;
V2 = 21/1/9. **Les totaux agrégés sont identiques par
coïncidence**, pas parce que le contenu des top-5 serait
inchangé : Q13 passe True → False (la page 5 attendue sort du
top-5) et Q30 passe False → True (la page 4 attendue entre
dans le top-5). Les deux migrations se compensent exactement.
Vérifier le vdc Q par Q et non à l'agrégat.

### Justes parmi les réponses données

- **V1.2 : 20 / 20 = 100 %.** Aucune fausse. Le prompt V1.2 est
  prudent : quand le modèle répond, il répond juste.
- **V2 : 22 / 23 = 95,7 %.** 1 fausse (Q13). V2.1 descend un
  chunk pertinent de Q13 hors top-5 et pousse un chunk
  trompeur au top ; le LLM répond une valeur en page 8 (total
  des produits d'exploitation) au lieu de la page 5 (revenus
  individuels).

### 5 changements de classe V1.2 → V2

| qid | cat | V1.2 | V2 | Interprétation |
|---|---|---|---|---|
| sotuver_2024_06 | calcul | abstention_a_tort_recall_**ok** | **juste** | Prompt V1.2 inchangé, retrieval V2.1 pousse la bonne page → sortie « 1,90 » (endettement global exprimé comme un multiple, pas un pourcentage). |
| monoprix_consolide_2024_12 | texte_annexes | abstention_a_tort_recall_ko | abstention_a_tort_recall_**ok** | Retrieval amélioré (page 13 passe de rang 6 à rang 1), mais LLM abstient toujours malgré que la réponse soit INTÉGRALEMENT dans le chunk rang 1. **La cause de l'abstention reste inconnue**. *Hypothèse à tester* : le prompt V1.2 est très conservateur sur les questions en « quelles X et pour quelle raison ? » quand le texte source est long et narratif ; il refuse peut-être par prudence quand la réponse n'est pas une valeur isolée. Nécessite une mesure dédiée (variante prompt, même retrieval). |
| monoprix_2024_13 | extraction | juste | **fausse_recall_ko** | Perte prévue par le benchmark. V2.1 hybride_filtre descend la page 5 hors top-5 ; le LLM lit « Revenus et autres » page 8 (746 256 912 = total produits d'exploitation). Ne pas corriger. |
| ciments_bizerte_2024_25 | texte_annexes | abstention_a_tort_recall_ko | **juste** | BM25 filtré V2.1 remonte la page 14 au rang 1 → V2 sort « 900 000 tonnes par an ». Validé juste/complete=true. |
| delice_holding_2024_30 | extraction | abstention_a_tort_recall_ko | **juste** | V2.1 remonte la page attendue dans le top-5 (rang 4) → V2 sort le bon montant « 32 944 357 dinars ». |

Net LLM : **+3 gains / −1 perte = +2**.

### Focus 8 Q demandées

| qid | V1.2 classe | V2 classe | vdc V1.2 / V2 |
|---|---|---|---|
| Q06 sotuver_2024_06 (calcul) | abstention_a_tort_recall_ok | **juste** | True / True |
| Q12 monoprix_consolide_12 (texte_annexes) | abst._a_tort_recall_ko | abst._a_tort_recall_**ok** | None / None |
| Q13 monoprix_13 (extraction) | juste | **fausse_recall_ko** | True / **False** |
| Q14 monoprix_14 (calcul) | abst._a_tort_recall_ok | abst._a_tort_recall_ok | True / True |
| Q21 sfbt_21 (texte_annexes) | abst._a_tort_recall_ko | abst._a_tort_recall_ko | None / None |
| Q23 ciments_23 (calcul) | abst._a_tort_recall_ko | abst._a_tort_recall_ko | True / True |
| Q25 ciments_25 (texte_annexes) | abst._a_tort_recall_ko | **juste** | None / None |
| Q30 delice_30 (extraction) | abst._a_tort_recall_ko | **juste** | **False** / **True** |

### Les 4 sans_reponse (contrôle anti-invention)

Toutes restent `abstention_correcte` en V2, comme en V1.2 :

- Q05 sotuver_2024_05 → abstention_correcte
- Q16 monoprix_2024_16 → abstention_correcte
- Q26 ciments_bizerte_2024_26 → abstention_correcte
- Q31 delice_holding_2024_31 → abstention_correcte

**Aucune invention V2.** Le gain retrieval ne corrompt pas le
comportement de refus.

### Nouvelles fausses V2

- **monoprix_2024_13** : juste → fausse_recall_ko. Unique
  régression. Prévue par le benchmark V2.1 (le filtre entreprise
  + BM25 descend la page 5 hors top-5). Perte reconnue, non
  corrigée (prompt V1.2 et pipeline retrieval V2.1 non touchés).

Pas d'autre nouvelle fausse. Pas de reponse_a_tort.

### Observation sur Q12 (demandée par l'utilisateur)

Q12 demande « quelles filiales ont été exclues du périmètre de
consolidation et pour quelle raison ? ». La référence : SNMVT
INTERNATIONAL et UNITED DECS, raison = fermeture magasins Libye
2015 (NCT 35 §11.b).

- **V2 retrieval : page 13 au rang 1.** Le chunk rang 1
  contient INTÉGRALEMENT la réponse (noms des filiales,
  pourcentages, année d'exclusion, raison Libye, référence
  NCT 35 §11.b).
- **V2 LLM : « donnée non disponible ».** Le modèle refuse
  malgré que toute la matière soit dans le contexte.

Q12 passe de `abstention_a_tort_recall_ko` (V1.2 : page non
récupérée) à `abstention_a_tort_recall_ok` (V2 : page récupérée,
modèle abstient). V2.1 corrige donc le retrieval. En revanche,
**la cause de l'abstention LLM reste inconnue** : plusieurs
hypothèses non arbitrées faute de mesure dédiée.

*Hypothèses candidates à tester ultérieurement (non tranchées) :*

1. Le prompt V1.2 est conservateur sur les questions texte en
   « quelles X et pour quelle raison ? » quand la réponse n'est
   pas une valeur isolée.
2. Le libellé « donnée non disponible » est privilégié quand
   une partie seulement de la question peut être répondue
   (liste de filiales *et* motif).
3. Un autre facteur contextuel (longueur du chunk,
   positionnement du chiffre vs du texte narratif,
   interférence avec d'autres chunks du top-5) joue.

Le même pattern s'observe pour **Q14** (calcul, valeurs dans le
contexte, abstention) et **Q23** (calcul, valeurs dans le
contexte via pages alternatives, abstention) : cause inconnue,
hypothèse à tester. Pas de correction V2.

### Annotations manuelles ajoutées à `annotations_texte.jsonl`

Trois annotations versionnées sous le run_id
`v2_gemini35flashlite_k5_634426d2b6bfde4e_v2_1_hybride_filtre` :

- **Q04 sotuver_2024_04** : statut=juste, complete=**false**.
  Élément manquant : provision pour dépréciation sur articles
  à rotation lente / obsolètes.
- **Q08 sotuver_2024_08** : statut=juste, complete=**true**.
  NCT 11 décrit le TRAITEMENT du changement, pas le motif :
  pas un élément manquant de la réponse au « pourquoi ».
- **Q25 ciments_bizerte_2024_25** : statut=juste,
  complete=**true**. Correspond exactement à la référence.

### Enseignements

- **La V2 a tenu la promesse du retrieval et nettoyé une
  abstention sur chaque catégorie d'erreur attendue.** Q06
  (calcul), Q25 (texte_annexes), Q30 (extraction) passent
  toutes en juste. +2 justes nettes, +3 bons résultats bruts.
- **Q13 : régression repérée APRÈS le benchmark retrieval,
  AVANT le run LLM.** Le critère §4 (R@5 strict > 19/27) ne
  portait **que sur le Recall@5 global** ; il ne traitait pas
  explicitement du trade-off au niveau des réponses LLM. En
  inspectant les gains/pertes R@5 par Q (étape de rapport, pas
  étape de décision), la perte de Q13 côté hybride_filtre
  V2.1 était visible : juste au Q13 côté dense, perdue côté
  hybride_filtre. La décision de lancer quand même le run LLM
  a été prise sachant cela — pas un trade-off *écrit ex ante
  dans §4*, mais un trade-off *connu avant le run*. En V2
  LLM, Q13 passe juste → fausse, et les « justes parmi
  réponses données » tombent de 100 % à 95,7 %.
- **Q12 : la cause de l'abstention LLM reste inconnue.** Toutes
  les conditions retrieval sont réunies (page attendue au
  rang 1, texte complet dans le contexte) et le modèle refuse
  quand même. **Hypothèse** : le prompt V1.2 bloque sur ce
  pattern. Non vérifié dans ce run. Un éventuel V1.3 devrait
  inclure une mesure prompt dédiée AVANT toute modification.
- **Aucune invention sur les 4 sans_reponse.** Le filtre
  entreprise + hybride_filtre + V2.1 n'a fait qu'améliorer le
  retrieval ; la sortie du modèle reste protégée par la
  consigne V1.2 (« réponds "donnée non disponible" seulement
  s'il manque une valeur nécessaire »). Garde-fou validé.
- **Décision V2 close.** Le pipeline retenu (`v2.1 /
  hybride_filtre`) améliore effectivement V1.2 au prix d'une
  régression unique et traçable. Pas d'autre run V2.

### Tableau final : B0-strict, B0-libre, V1, V1.1, V1.2, V2

Synthèse chiffrée des 6 runs réalisés sur le benchmark (31 Q,
27 avec page attendue), modèle Flash-Lite, temperature 0.

| Run | Bons résultats | Justes | Fausses | Justes / réponses données | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| B0-strict | **4/31** | 0 | 0 | 0/0 n/a | n/a | n/a |
| B0-libre  | **5/31** | 1 | 6 | 1/7 (14,3 %) | n/a | n/a |
| V1        | **20/31** | 16 | 1 | 16/17 (94,1 %) | 19/27 (70 %) | 0,543 |
| V1.1      | **22/31** | 18 | 4 | 18/22 (81,8 %) | 19/27 (70 %) | 0,543 |
| V1.2      | **24/31** | 20 | 0 | 20/20 (100 %) | 19/27 (70 %) | 0,543 |
| **V2**    | **26/31** | **22** | **1** | **22/23 (95,7 %)** | **22/27 (81 %)** | **0,714** |

Lectures clés :

- **Bons résultats** (juste + abstention_correcte) monotonement
  croissants : 4 → 5 → 20 → 22 → 24 → 26.
- **B0-strict vs V1** est la seule paire à prompt système
  identique (seul le template user change), donc la seule qui
  **mesure l'effet pur du RAG** : +16 bons résultats.
- **V1 → V1.1 → V1.2** : effet pur du prompt (retrieval
  identique, mêmes chunks). V1.1 fait +2 bons résultats mais
  payés par +4 fausses (consigne de calcul libère des réponses
  parfois sémantiquement fausses, cf. Q02/Q10/Q19 erreur de
  définition « total passif »). V1.2 corrige ces fausses avec
  R1 (« total passif = total du bilan »), ramène les fausses
  à 0 et pousse « justes parmi réponses données » à 100 %.
- **V1.2 → V2** : effet du retrieval (prompt V1.2 inchangé
  byte-à-byte). +2 bons résultats, Recall@5 + 3 Q (19 → 22),
  MRR +0,17. Payé par 1 régression Q13 (juste → fausse) ; la
  précision retombe à 95,7 % mais reste légèrement au-dessus de
  V1 (94,1 %), soit une question d'écart, et nettement au-dessus
  de V1.1 (81,8 %).
- **Les colonnes Recall@5 / MRR sont identiques V1, V1.1, V1.2**
  parce que ces 3 runs partagent exactement le retrieval dense
  V1. Seule la consigne du prompt change. V2 est la première
  version qui change le retrieval (hybride_filtre V2.1), d'où
  le saut aux 2 dernières colonnes.

### Fichiers créés / modifiés

- `results/v2.jsonl` — 31 lignes, run_id
  `v2_gemini35flashlite_k5_634426d2b6bfde4e_v2_1_hybride_filtre`.
- `results/scores_v2.jsonl` — 31 lignes.
- `data/benchmark/annotations_texte.jsonl` — 3 annotations
  ajoutées pour le run V2 (Q04, Q08, Q25).
- `docs/journal.md` — cette entrée.

Pas de code modifié ; suite totale toujours à **363 passed, 3
deselected**.

### Ce qui reste

- Validation externe sur un nouveau benchmark (plan V2 §8).
- Éventuel V1.3 pour cibler Q12 (prompt revu sur « quelles X
  et pour quelle raison ? ») — PAS avant feu vert explicite.



---

## 2026-11-06 (soir, 4) — Jeu de validation (Partie A) : 15 Q nouvelles

### Ce que j'ai fait

Écrit `data/benchmark/questions_validation.jsonl` : **15 questions
nouvelles** sur les 6 mêmes rapports BVMT 2024, même format que
`questions.jsonl`. Rédaction à partir des PDFs et chunks
uniquement (sans consulter aucun `results/v*.jsonl`,
`retrieval_compare.jsonl` ou `retrieval_top20.jsonl`). La date
du commit prouve que les 15 Q existent AVANT tout run LLM sur
ce jeu.

Distribution (vérifiée par test) : 4 extractions, 4 calculs
(dont 2 autonomies sur Ciments de Bizerte et Monoprix
individuel, deux sociétés non-tested dans les 31 Q), 2
comparaisons, 3 texte_annexes, 2 sans_reponse dont 1 sans
société nommée.

### Après feedback utilisateur — 3 corrections

1. **val_07 remplacée** : le taux de distribution Délice 2024
   (dividende unitaire / résultat par action) mélangeait deux
   exercices : le dividende 0,600 TND/action avait été versé en
   2024 sur le RÉSULTAT 2023 (AGO du 13/06/2024), et son produit
   par le nombre d'actions donne 32 944 357 TND = réponse de
   Q30 du benchmark principal. Remplacée par le **taux
   d'amortissement cumulé des immobilisations corporelles de
   la SFBT** (amortissements / brut, les deux valeurs sur la
   page 2 bilan actif SFBT, non utilisée par les 31 Q).
2. **val_12 remplacée** : la méthode de valorisation des
   stocks matières premières Ciments (p. 14 du PDF) partageait
   la page avec Q25 (capacité normale de production) et traitait
   du même fond que Q21 (méthode de valorisation des stocks
   SFBT). Remplacée par une question sur la **continuité
   d'exploitation Ciments de Bizerte** : depuis le 15/10/2023
   la société est en arrêt de production, à cause d'une rupture
   d'approvisionnement en coke de pétrole et brique réfractaire
   (page 15 Ciments, non utilisée par les 31 Q).
3. **val_09 remplacée** : la variation des stocks nets SOTUVER
   entre 2023 retraité et 2024 reprenait le thème de Q07
   (retraitement NCT 11 sur les stocks SOTUVER). Remplacée par
   la **variation du total des actifs SOTUVER 2023 → 2024**
   (augmentation de 73 485 721 TND, les deux valeurs sur
   page 2 bilan actif SOTUVER). Pour les actifs totaux, les
   colonnes 2023 retraitée et publiée sont identiques, donc
   l'ambiguïté NCT 11 ne se pose pas.
4. **val_10 gardée** avec note explicite : elle est proche
   de Q11 du benchmark principal (toutes deux portent sur
   l'évolution d'un résultat net consolidé Monoprix, même page
   p. 4 du rapport), mais Q11 cible la PART DU GROUPE (variation
   5 859 229) et val_10 cible l'ENSEMBLE consolidé avant
   répartition (variation 6 042 450). La proximité est
   documentée dans les notes de val_10.

### Limitations du jeu de validation documentées ex ante

- **val_14 est la seule Q « Monoprix » sans qualifier, mais elle
  est de catégorie `sans_reponse`.** Elle teste que le filtre
  V2 ne plante pas sur une Q Monoprix ambigüe (périmètre = 2
  docs), et que le modèle maintient son abstention quand la
  donnée n'existe dans aucun des deux rapports. Elle **ne teste
  PAS** le choix du modèle entre bilan individuel et bilan
  consolidé face à une Q ambigüe sur une donnée réelle. Cette
  Q manque dans le benchmark actuel et dans le jeu de
  validation ; à ajouter dans un prochain jeu étendu.
- **La couverture `sans filtre` est limitée.** val_15 (taux
  d'inflation Tunisie, sans société) est la seule Q qui
  exerce le chemin `filtre_question.entreprises_filtre →
  None`. Un seul cas, peu robuste statistiquement.
- **Pas de Q `calcul` avec valeurs inter-pages sur 2 chunks
  sans overlap textuel.** Les calculs multi-page (val_06, et
  anciennement val_07) ne testent pas le cas « valeurs sur
  2 pages totalement différentes sans aucun chevauchement
  lexical » qui serait le vrai stress du retrieval.

### Pages utilisées par le jeu de validation (post-correctifs)

Les 31 Q du benchmark principal couvrent les pages suivantes :
- sotuver_2024 : {3, 4, 9}
- monoprix_2024 : {5}
- monoprix_consolide_2024 : {3, 4, 13}
- sfbt_2024 : {3, 4, 8}
- ciments_bizerte_2024 : {2, 4, 14}
- delice_holding_2024 : {2, 3, 4, 7}

Les 15 Q du jeu de validation ajoutent les pages suivantes
(nouvelles pages, hors benchmark principal) :
- sotuver_2024 : p. 2 (val_01 immob nettes, val_09 total actifs)
- monoprix_2024 : p. 3 (val_02 total actifs, val_06 total actifs
  intermediate), p. 4 (val_06 CP intermediate)
- sfbt_2024 : p. 2 (val_07 amortissements/immob brutes), p. 6
  (val_03 participation BGI)
- ciments_bizerte_2024 : p. 3 (val_05 autonomie), p. 12
  (val_11 marge brute négative), p. 15 (val_12 continuité
  d'exploitation)
- delice_holding_2024 : p. 13 (val_04 dividendes CLC), p. 16
  (val_13 engagement SICAR AMEN)

Seules deux Q du jeu de validation réutilisent une page
benchmark : val_08 (ROA SFBT, p. 3) et val_10 (résultat net
ensemble consolidé Monoprix, p. 4). Les deux sont documentées
comme proches d'une Q benchmark.

### Fichiers créés

- `data/benchmark/questions_validation.jsonl` — 15 Q.
- `tests/test_benchmark_validation.py` — 17 tests reprenant les
  4 niveaux de `test_benchmark.py` (structure, arithmétique,
  extraits PDF, sans_reponse mots-racines) + 5 contrôles
  spécifiques (distribution, autonomies non-tested, sans
  société, Monoprix sans qualifier, pas d'overlap avec les
  31 Q).

Suite totale : **380 passed, 3 deselected** (+17 depuis V2,
zéro régression).

### Ce qui reste (Partie B, bloquée par validation utilisateur)

- Lancer V1.2 (dense) et V2 (v2.1/hybride_filtre) une seule
  fois sur le jeu de validation, sans rien modifier au pipeline.
- Ajouter un mode de score pour ce jeu.
- Comparer aux 31 Q d'origine : bons résultats, justes,
  fausses, Recall@5, MRR.
- Aucune modification du prompt, de BM25, du filtre, de RRF.



---

## 2026-11-07 — Partie B : runs LLM V1.2 + V2 sur jeu de validation (15 Q)

### Ce que j'ai fait

Lancé en une passe `scripts/evaluate_validation.py` sur les 15 Q
nouvelles du jeu de validation : **V1.2 (dense top-5) puis V2
(v2.1/hybride_filtre top-5)**, prompt V1.2 inchangé byte-à-byte
pour les deux runs, Flash-Lite, temperature = 0. Scoré avec
`score.py --mode validation`.

Zéro modification du prompt, du filtre entreprise, de BM25, de
RRF.

### Coût

- **15 appels à l'API d'embeddings Gemini** (RETRIEVAL_QUERY,
  une seule fois pour les 15 Q). Les chunks (247 vecteurs
  RETRIEVAL_DOCUMENT) sont déjà en cache depuis l'indexation
  V1. Le second run (V2) relit le cache → **0 appel API
  embeddings supplémentaire**.
- 30 appels Flash-Lite (15 V1.2 + 15 V2), temperature = 0.
- 6 annotations manuelles validées par l'utilisateur
  (val_11 × 2 runs, val_12 × 2 runs, val_13 × 2 runs).

### Résultats globaux sur le jeu de validation (15 Q)

| | V1.2 | V2 | Δ |
|---|---|---|---|
| juste | 11 | **12** | **+1** |
| fausse_recall_ok | 0 | 0 | ± |
| fausse_recall_ko | 0 | 0 | ± |
| abstention_a_tort_recall_ok | 1 | 1 | ± |
| abstention_a_tort_recall_ko | 1 | **0** | **−1** |
| abstention_correcte | 2 | 2 | ± |
| reponse_a_tort | 0 | 0 | ± |
| **Bons résultats** | **13/15** | **14/15** | **+1** |

Par catégorie (bons résultats) :

| Catégorie | V1.2 | V2 |
|---|---|---|
| extraction (4) | 3/4 | **4/4** |
| calcul (4) | 3/4 | 3/4 |
| comparaison (2) | 2/2 | 2/2 |
| texte_annexes (3) | 3/3 | 3/3 |
| sans_reponse (2) | 2/2 | 2/2 |

Retrieval (sur les 13 Q avec page attendue) :

| | V1.2 | V2 |
|---|---|---|
| Recall@1 | **7/13** | 5/13 |
| Recall@3 | 7/13 | **10/13** |
| Recall@5 | 11/13 | 11/13 |
| Recall@10 | 11/13 | 11/13 |
| Recall@20 | 11/13 | 11/13 |
| MRR | 0.629 | **0.635** |

Justes parmi les réponses données (hors abstention) :

- V1.2 : **11 / 11 = 100 %**.
- V2 : **12 / 12 = 100 %**.

**Aucune réponse fausse sur les deux runs sur le jeu de
validation.** Pas de `reponse_a_tort`, pas de `fausse_*`,
pas d'invention.

### Comparaison avec le benchmark des 31 Q

| Métrique | 31 Q V1.2 | 31 Q V2 | Validation V1.2 | Validation V2 |
|---|---|---|---|---|
| Bons résultats | 24/31 (77 %) | 26/31 (84 %) | 13/15 (87 %) | 14/15 (93 %) |
| Justes | 20 | 22 | 11 | 12 |
| Fausses | 0 | 1 | 0 | 0 |
| Justes / réponses données | 20/20 (100 %) | 22/23 (95,7 %) | 11/11 (100 %) | 12/12 (100 %) |
| Recall@5 | 19/27 (70 %) | 22/27 (81 %) | 11/13 (85 %) | 11/13 (85 %) |
| MRR | 0.543 | 0.714 | 0.629 | 0.635 |

Lectures :

- **Les 2 runs ont ZÉRO fausse sur le jeu de validation.** Sur
  31 Q, V2 avait 1 fausse (Q13, perte prévue hybride_filtre).
  Sur 15 Q, aucune réponse fausse ni invention.
- **V2 ne gagne pas de Recall@5 vs V1.2** sur validation
  (11/13 pour les deux). L'écart MRR V2 vs V1.2 (0,635 vs
  0,629) est **négligeable** (+0,006).
- **R@1 : 5/13 (V2) vs 7/13 (V1.2) ; R@3 : 10/13 (V2) vs 7/13
  (V1.2).** Les deux runs retrouvent les mêmes 11 pages au R@5,
  avec un classement interne différent dans le top-5. Je
  n'identifie pas ici une cause spécifique à BM25 ou au
  filtrage : trop peu d'observations et l'écart MRR final est
  minime.
- **Deux Q (val_02 et val_06) sont `juste` malgré un recall@5
  KO strict.** Voir la section dédiée plus bas.

### Changement de classe V1.2 → V2

Une seule Q change de classe : **val_02 (extraction, Monoprix
individuel total actifs)** passe `abstention_a_tort_recall_ko`
→ **juste**. Interprétation corrigée après inspection des
top-20 :

- **La page attendue (p. 3 de monoprix_2024, « Total des actifs
  305 449 843 ») n'est dans le top-20 d'AUCUN des deux runs.**
  Recall KO strict côté V1.2 ET côté V2.
- **V2 répond 305 449 843 TND malgré le recall KO** : le top-1
  V2 est `monoprix_2024 p. 2` (bilan actif), qui contient les
  sous-totaux « Total des actifs non courants = 168 274 357 »
  et « Total des actifs courants = 137 175 486 ». Le modèle a
  additionné les deux (168 274 357 + 137 175 486 = 305 449 843)
  et répondu la somme. Réponse juste par calcul intra-page,
  pas par lecture directe.
- **V1.2 avait aussi `monoprix_2024 p. 2` dans son top-5**
  (au rang 2) mais s'est abstenue. V1.2 avait aussi des chunks
  de `monoprix_consolide_2024` dans son top-5 (rangs 1 et 3),
  ce que V2 n'a pas (le filtre entreprise SNMVT-Monoprix restreint
  à `monoprix_2024`).
- **La cause de la différence de comportement entre V1.2 et V2
  reste une HYPOTHÈSE** : peut-être le mélange individuel +
  consolidé dans le contexte V1.2 trouble le modèle (deux
  bilans similaires avec des chiffres différents), et V2 lui
  présente un contexte purement individuel plus clair à lire
  et additionner. Non vérifié par une mesure dédiée.

Ce n'est pas le pattern des Q25/Q30 des 31 Q (où la page
attendue était RÉELLEMENT remontée dans le top-5 par V2.1).
Ici, aucune page attendue n'est remontée ; c'est un cas
« juste malgré recall KO » (cf. section dédiée).

### Note sur val_08 (SFBT ROA, abstention des deux runs)

val_08 est une Q `calcul` :
- Résultat net SFBT 2024 = 241 621 194,507 TND (p. 3 bilan passif)
- Total bilan SFBT 2024 = 1 281 772 854,965 TND (p. 3 bilan passif)
- Ratio attendu : 18,85 %

Les DEUX runs (V1.2 et V2) retournent `donnee non disponible`,
avec recall@5 = OK (page 3 bien dans le top-5) et vdc = True
(les deux valeurs sont présentes dans le contexte).

**La cause de l'abstention reste inconnue**, comme pour Q12,
Q14 et Q23 des 31 Q. Mêmes hypothèses non arbitrées :
- Prompt V1.2 conservateur sur des ratios où plusieurs lignes
  du bilan peuvent être interprétées comme « résultat net » ou
  « total actif » ;
- Possible confusion sur le choix de la ligne « Résultat net »
  parmi plusieurs options sur p. 3 (bilan passif) et p. 4
  (état de résultat) ;
- Un autre facteur contextuel non identifié.

Nécessiterait une mesure prompt dédiée (variante prompt, mêmes
chunks) pour trancher — hors scope V2.

### Note sur les Q `juste` malgré recall@5 KO strict

Deux Q de validation sont classées `juste` par le scorer mais
ont `recall@5 = False` au sens strict (pages attendues
manquantes dans le top-5) :

- **val_02 (extraction, Monoprix individuel total actifs)** :
  page attendue p. 3 absente du top-20 des deux runs. V2 répond
  juste en additionnant les deux sous-totaux du bilan actif
  (p. 2) ; V1.2 s'abstient. Détails ci-dessus.
- **val_06 (calcul, autonomie financière Monoprix individuel)** :
  pages attendues p. 3 (total actifs) + p. 4 (CP).
  - V1.2 : p. 4 au rang 3, p. 3 absente → recall KO. Le modèle
    répond juste (31,36 %) car la p. 4 (bilan passif) contient
    AUSSI la ligne « Total des capitaux propres et passifs
    305 449 843 » qui égale le total actif par construction.
    Le ratio CP (95 774 305) / total passif (305 449 843) =
    31,36 % se lit entièrement sur p. 4.
  - V2 : p. 4 au rang 1, p. 3 absente → même configuration.
    Même réponse.

Ce sont deux cas d'arithmétique intra-page et de lecture
croisée sur le bilan passif. Ils confirment que le critère
strict « toutes les pages de intermediate_values dans le
top-k » peut sous-estimer la capacité du modèle à répondre
quand la matière est présente sous une autre forme (sous-
totaux additionnables, ligne « total CP et passifs » qui égale
« total actif »). À documenter mais pas à « corriger » dans le
scoring : le critère strict reste défensif.

### Note sur val_13 (texte_annexes, engagement SICAR AMEN)

L'écart entre V1.2 (complete = false) et V2 (complete = true)
n'est PAS dû à une différence de retrieval : le chunk utile
(p. 16 de `delice_holding_2024`) est au **rang 1** dans les
deux runs. Le contexte envoyé au LLM est donc quasi identique.

L'écart vient de la **formulation du modèle** : V2 inclut la
valeur nominale unitaire de 286 dinars, V1.2 l'omet.
Variance de génération, pas de retrieval. Non attribuable à
BM25 ni au filtre.

### Notes sur la couverture du jeu de validation

1. **val_11 et val_12 portent sur le même sujet.** Toutes deux
   portent sur la crise opérationnelle 2023-2024 des Ciments de
   Bizerte, documentée dans les notes 2024 : val_11 interroge
   l'EFFET (marge brute négative → arrêt production clinker),
   val_12 interroge la CAUSE (arrêt production depuis le
   15/10/2023 → rupture d'approvisionnement coke de pétrole +
   brique réfractaire). Même topic métier, pages différentes
   (p. 12 et p. 15). Le benchmark de validation n'apporte donc
   qu'un seul angle couvrant à proprement parler pour cette
   société sur ce sujet.
2. **val_08 et val_09 reprennent des totaux déjà utilisés.**
   val_08 (ROA SFBT) utilise le total bilan SFBT 1 281 772
   854,965 qui est déjà la réponse de Q17 du benchmark
   principal. val_09 (variation total actifs SOTUVER) utilise
   350 310 164 qui est le total passif SOTUVER (= total actifs)
   déjà utilisé comme dénominateur dans Q02. Ces Q ne testent
   pas de NOUVELLES valeurs : elles testent la capacité du
   retrieval à trouver ces valeurs sous d'autres angles.
3. **Complétude des trois `texte_annexes` : contrastée.**
   - **val_11** : incomplète dans les DEUX runs
     (`complete=false`), même élément manquant (114 128 tonnes
     de clinker achetées).
   - **val_13** : incomplète SEULEMENT en V1.2
     (`complete=false`, manque la valeur nominale 286 DT) ;
     complète en V2 (`complete=true`). Le chunk p. 16 est au
     rang 1 pour les deux runs, donc l'écart vient de la
     formulation du modèle, pas du retrieval.
   - **val_12** : complète dans les DEUX runs
     (`complete=true`), tous les éléments demandés par la
     question (date + cause) sont présents.
   *Hypothèse non vérifiée* : la consigne V1.2 « donne
   uniquement le résultat final avec son unité » vise
   explicitement les CALCULS (contexte R1/R2 du prompt). Son
   effet sur les réponses `texte_annexes` n'a pas été mesuré
   séparément ; il est possible qu'elle pousse le modèle à
   abréger les réponses texte, mais ce n'est pas établi par
   une comparaison contrôlée.
4. **Le jeu de validation est peut-être plus FACILE que le
   benchmark principal.** Beaucoup de questions reposent sur
   des totaux de bilan (val_02 total actifs, val_05 et val_06
   autonomies qui utilisent total passif, val_08 ROA qui
   utilise total bilan, val_09 variation total actifs), chiffres
   qui apparaissent typiquement en toute dernière ligne du
   bilan actif / passif et sont donc faciles à récupérer par
   retrieval dense. Un benchmark plus dur contiendrait
   davantage de Q sur des sous-postes rares (val_04 dividendes
   CLC illustre ce type), des notes rarement référencées
   (val_11, val_12, val_13 vont dans ce sens) et des calculs
   multi-page sans pivot commun (seul val_07 le fait, et sur
   une page unique).
5. **15 questions donnent une TENDANCE, pas une PREUVE.**
   L'écart V2 vs V1.2 sur validation (14/15 vs 13/15, +1 Q)
   est dans la variance d'échantillon : un seul changement de
   classe (val_02). Les résultats sur 15 Q ne discriminent
   pas statistiquement les deux pipelines ; ils confortent
   l'ordre observé sur 31 Q mais ne suffisent pas à conclure.
   Combinée au point 4 (jeu plus facile), cette tendance peut
   être OPTIMISTE par rapport à ce qu'un benchmark de même
   difficulté que les 31 Q montrerait.

### Dépendance du jeu de validation aux PDFs

Les pages NOUVELLES couvertes par le jeu de validation (hors
pages des 31 Q) : SOTUVER p. 2, Monoprix individuel p. 3 et 4,
SFBT p. 2 et 6, Ciments p. 3, 12 et 15, Délice p. 10, 13 et 16.
Soit 11 pages nouvelles (pour 15 Q) + 4 Q qui réutilisent des
pages du benchmark principal (val_05 Ciments p. 3 n'est en fait
pas benchmark — p. 3 non utilisée par les 31 Q sur Ciments ;
val_06 Monoprix p. 4 non utilisée ; val_08 SFBT p. 3 utilisée
par Q17/Q18/Q19 ; val_10 Monoprix consolidé p. 4 utilisée par
Q11/Q09).

### Fichiers créés / modifiés

- `scripts/evaluate_validation.py` — orchestrateur V1.2 + V2
  avec compteur API embeddings et pré-embedding des 15 Q.
- `scripts/score.py` — ajout mode `validation` + constantes
  `V1_2_VALIDATION_PATH`, `V2_VALIDATION_PATH`,
  `RETRIEVAL_CMP_VALIDATION_PATH`, et helper
  `_charger_top20_par_variante`.
- `tests/test_evaluate_validation.py` — 11 tests sans réseau
  (constantes figées, run_id, format ligne, charger top20).
- `results/v1_2_validation.jsonl` — 15 lignes.
- `results/v2_validation.jsonl` — 15 lignes.
- `results/retrieval_compare_validation.jsonl` — 30 lignes
  (dense + hybride_filtre top-20 par Q).
- `results/scores_v1_2_validation.jsonl` — 15 lignes.
- `results/scores_v2_validation.jsonl` — 15 lignes.
- `data/benchmark/annotations_texte.jsonl` — +6 annotations
  (val_11 × 2, val_12 × 2, val_13 × 2).

Suite totale : **391 passed, 3 deselected** (+11 depuis
Partie A, zéro régression).

### Décisions

- Pas de V3. Pas de modification prompt, filtre, BM25, RRF.
- Décision V2 close. Les résultats sur 15 Q confortent le
  choix V2 vs V1.2 (+1 Q bons résultats, 0 fausses, R@3
  meilleur, MRR légèrement meilleur) mais ne constituent pas
  une preuve statistique indépendante : échantillon trop petit,
  jeu partiellement corrélé au benchmark principal (totaux
  partagés), angle sujet couvert plusieurs fois (Ciments
  val_11 + val_12).



---

## 2026-11-07 — Plan V3 (reranker) — pas de code, pas de run

### Principe V3

Pipeline :
1. Retrieval V2.1/hybride_filtre identique à V2 → **top-20
   candidats** (filtre entreprise, BM25 V2.1 IDF recalculée sur
   le périmètre, fusion RRF k=60 sur top-50 dense + top-50 BM25).
2. **Reranker** : reclasse ces 20 candidats via un cross-encoder
   multilingue → nouveau top-5.
3. LLM : top-5 reranké envoyé au prompt V1.2 inchangé.

**Rien d'autre ne change** : prompt V1.2, modèle Flash-Lite,
temperature = 0, filtre entreprise, BM25, RRF, k=5 contexte final.
Seul le reclassement final des 5 chunks envoyés au LLM change.

### §1. Modèle de reranker (figé avant toute mesure)

- **Modèle** : `BAAI/bge-reranker-v2-m3` (BAAI, 568 M paramètres).
- **Version épinglée** : commit HuggingFace figé dans le code
  via `revision="<sha>"` à la construction de l'AutoModel (sha
  à récupérer au moment du pin ; ex. `revision="ba3a7e4"` au
  2026-11-07 pour la branche `main`). Le commit est documenté
  dans `requirements.txt` et dans `bilanlens/reranker.py`.
- **Librairie** : `FlagEmbedding==1.3.4` (dernière stable
  2026-11-07) ou `transformers` direct. Ajoutée à
  `requirements.txt`. Dépend aussi de `torch` (non épinglé plus
  précisément que la compatibilité FlagEmbedding).
- **Pourquoi celui-ci :**
  - Multilingue, bon sur le français (évaluation FR dans la
    carte modèle BAAI).
  - **Contexte 8192 tokens**, donc une page de rapport BVMT
    (1500-3000 tokens max) **tient entière** sans troncation.
    Point clé pour éviter de perdre un tableau de bilan en fin
    de page.
  - Open weights, déterministe, local → **zéro appel API**,
    coût marginal nul par run (après le téléchargement initial).
    Reproductible.
- **Alternatives écartées** :
  - `cross-encoder/ms-marco-MiniLM-L6-v2` : context 512 tokens
    → oblige à fenêtre glissante, risque de perdre du contenu.
    Anglais, pas optimisé français.
  - `jinaai/jina-reranker-v2-multilingual-base` : context 1024,
    insuffisant pour une page complète.
  - Cohere Rerank API : payant + dépendance externe → écarté
    pour la reproductibilité.
- **Coût prévu** : téléchargement unique ≈ 1.1 GB. RAM runtime
  ≈ 2 GB (modèle en float32) ou ≈ 1 GB (float16 sur GPU).
- **Temps prévu par Q** (31 Q × 20 candidats = 620 paires) :
  - **CPU** (Intel i7 moderne) : ≈ 0.5-1.5 s par paire
    → **~5 à 15 min** pour le benchmark complet.
  - GPU (CUDA capable) : ≈ 50-150 ms par paire → ~1 à 2 min.
  - Le script auto-détecte le device via torch ; CPU fallback
    accepté (c'est un benchmark offline, le temps n'est pas
    critique).

### §2. Gestion des chunks longs

- **Longueur réelle des chunks du corpus** : à mesurer avant
  de coder. Les chunks font 1 page physique (source :
  `scripts/chunk_corpus.py`), avec une variance importante
  (une page de couverture ≈ 50 tokens, une page de bilan avec
  tableau dense ≈ 2000-3000 tokens, une note annexe narrative
  ≈ 500-1500 tokens).
- **Stratégie retenue** : **contexte 8192 tokens suffisant pour
  toutes nos pages**. On passe la page ENTIÈRE au reranker, sans
  troncation ni fenêtre glissante. Garde-fou dans le code :
  avant l'appel, calculer le nombre de tokens de la paire
  (question + chunk) ; si > 8000 tokens, lever une exception
  explicite (plutôt qu'une troncation silencieuse qui perd la
  fin de la page, souvent un tableau).
- **Raison d'écarter la fenêtre glissante** : elle multiplie
  les appels reranker (3-5× par chunk long), rend l'agrégation
  non triviale (max ? mean ? pooling ?), et ajoute une
  hyperparam supplémentaire (stride). Avec un contexte 8192,
  le problème n'existe pas.
- **Test sans réseau** : un chunk fabriqué de 3000 tokens doit
  passer tel quel ; un chunk de 9000 tokens doit lever
  l'exception garde-fou.

### §3. Nombre de candidats et ordre stable

- **Nombre de candidats à reclasser : 20 par question.**
- **Justification** :
  - Recall@20 de V2.1/hybride_filtre = **27/27** sur les 31 Q
    (100 %, mesuré dans `benchmark_retrieval.py`). **Toutes les
    pages attendues sont déjà dans le top-20 V2**, donc le
    reranker a accès à toute la matière pertinente.
  - 50 candidats donnerait 1550 paires au lieu de 620 → 2.5×
    plus de temps pour un gain marginal non justifié (les
    chunks rang 21-50 n'ont contribué à aucune page attendue
    dans les 31 Q du benchmark).
  - Si une future Q voit sa page attendue tomber au-delà du
    rang 20 de V2, le choix serait à réexaminer ; à ce jour
    aucun cas.
- **Ordre stable en cas d'égalité de score reranker** :
  tie-break identique à V2 → `chunk_id` alphanumérique
  croissant. Appliqué dans `bilanlens/reranker.py`. Test
  unitaire dédié (deux chunks à score reranker égal → ordre
  chunk_id croissant).

### §4. Critère de choix (écrit AVANT toute mesure)

**La configuration reranker retenue pour V3 doit avoir un
`Recall@5` strictement supérieur à 22/27 sur les 31 Q du
benchmark principal.** Départage en cas d'égalité : `MRR` plus
élevé.

**Si aucun réglage reranker ne dépasse 22/27, on garde V2
(pas de V3, pas de run LLM V3).** Une égalité à 22/27 est un
match nul : pas assez pour justifier le coût (modèle 1.1 GB
téléchargé, ~10 min de CPU par run, nouvelle dépendance
`FlagEmbedding` + `torch`) et la complexification du pipeline.

Garde-fous :
- Si la mesure montre que V3 fait +3 ou +4 Q au R@5 mais
  injecte UNE régression (R@5 KO pour une Q où V2 était OK),
  le critère strict reste **net positif seulement** : le R@5
  est un entier, un gain net de +1 min suffit, pas un gain
  brut avec pertes cachées ailleurs.
- Mesure du MRR à titre indicatif ; départage uniquement si
  deux configs reranker atteignent le même R@5 strict > 22/27.

### §5. Mesure sans LLM sur les 31 Q

Avant tout run LLM V3, produire pour les 31 Q :

- **Recall@1, Recall@3, Recall@5, Recall@10** pour la config
  reranker. (R@20 n'est pas informatif puisqu'on part des 20
  V2 : R@20 reranker = R@20 V2 = 27/27 par construction.)
- **MRR** sur les 27 Q avec page attendue.
- **Gains / pertes au R@5 par Q** vs V2 (variante v2.1 /
  hybride_filtre) :
  - gains : Q où V2 R@5 KO → reranker R@5 OK
  - pertes : Q où V2 R@5 OK → reranker R@5 KO
  - net = gains − pertes
- **Rangs des pages attendues pour 5 Q d'intérêt** (toutes
  problématiques dans V2) :
  - **Q12** monoprix_consolide_2024 (texte_annexes) : V2 rang 1,
    LLM abstient toujours ;
  - **Q13** monoprix_2024 individuel (extraction) : V2 R@5 KO
    (page 5 hors top-5), V2 LLM FAUSSE ;
  - **Q14** monoprix_2024 individuel (calcul) : V2 R@5 OK,
    LLM abstient (cause inconnue) ;
  - **Q21** sfbt_2024 (texte_annexes) : V2 R@5 KO (rang 11
    hybride_filtre), LLM abstient ;
  - **Q23** ciments_bizerte_2024 (calcul) : V2 R@5 OK partiel
    (1 page sur 2 dans top-5), LLM abstient.
- **Validation du pipeline amont** : la config
  `v2.1/hybride_filtre` recalculée dans le benchmark V3 doit
  redonner **R@5 = 22/27** et **MRR = 0.7136** sur les 31 Q
  (chiffres de `benchmark_retrieval.py`). Garde-fou ; si
  différent, le pipeline amont a bougé.

### §6. Rôle du jeu de validation

- **Le jeu de validation (15 Q) NE SERT PAS à choisir la
  configuration V3.** Toutes les décisions de §1 à §4 sont
  prises AVANT toute mesure sur ce jeu.
- **Le jeu de validation est utilisé UNE SEULE FOIS, à la
  FIN**, après le choix de la config reranker et un éventuel
  run LLM V3 sur les 31 Q. Le run LLM V3 sur les 15 Q est
  lancé uniquement si §4 est satisfait sur 31 Q.
- **Risque de surapprentissage** mitigé par cette séquence :
  les 31 Q sont utilisées pour le critère, les 15 Q comme
  mesure indépendante finale.
- Si la V3 est retenue mais que les 15 Q montrent une
  régression nette (perte > 1 Q bons résultats vs V2 sur
  validation), c'est un signal qu'il faut documenter mais
  pas « corriger » : le benchmark de choix reste les 31 Q.

### §7. Fichiers, tests sans réseau, garde-fous

#### Modules à créer

- **`bilanlens/reranker.py`** : adaptateur pour
  `BAAI/bge-reranker-v2-m3`. Interface minimale :
  - `class Reranker` avec `__init__(model_name, revision,
    device="auto")` et `score_pairs(pairs: list[tuple[str, str]])
    → list[float]`.
  - `def reranker_top_k(question, candidates_top_k_list,
    chunks_par_id, top_final, tie_break="chunk_id") → list[dict]`.
  - Garde-fou longueur : exception si question+chunk
    dépasse 8000 tokens.
  - Tie-break : `(-score, chunk_id)` croissant.
- **`scripts/build_reranker_cache.py`** (optionnel) : indexe
  les scores reranker pour les 31 Q × 20 candidats et
  sauvegarde sur disque. Permet de relancer les benchmarks
  sans retomber les ~10 min CPU. Idempotent : hash
  (model_name, revision, question, chunk_id) → score.
- **`scripts/benchmark_rerank.py`** : mesure les métriques §5
  sans appeler le LLM. Charge V2.1/hybride_filtre top-20 depuis
  `results/retrieval_compare.jsonl` (variante v2.1, config
  hybride_filtre), appelle le reranker, écrit
  `results/retrieval_compare_v3.jsonl` et imprime les métriques.
- **`scripts/evaluate_v3.py`** : pipeline V3 complet (si §4
  OK). Reprend `evaluate_v2.py` en substituant le top-5
  hybride_filtre par le top-5 reranké. Écrit `results/v3.jsonl`.
- **`scripts/score.py --mode v3`** : scoring V3 selon règles
  V1.2, comparaison V2 vs V3 par catégorie.

#### Tests sans réseau

- `tests/test_reranker.py` :
  - Mock du modèle (scores pré-calculés), vérification du
    tri par score décroissant.
  - Tie-break par `chunk_id` croissant sur scores égaux.
  - Garde-fou longueur : paire 9000 tokens → exception.
  - Interface `score_pairs` : retourne une liste de float de
    même taille que l'entrée, ordre préservé.
- `tests/test_benchmark_rerank.py` :
  - Fausse `Reranker` qui renvoie des scores mock.
  - Vérifie que le top-5 reranké utilise l'ordre du reranker,
    pas celui de l'entrée.
  - Vérifie que la validation « V2.1 R@5 = 22/27 » du pipeline
    amont fait échouer le benchmark si le top-20 d'entrée est
    modifié.
- Pas de test qui télécharge le modèle réel ni qui l'appelle ;
  tout est mocké ou passé en injection de dépendance.

#### Garde-fous d'exécution

- Reproductibilité : `torch.manual_seed(0)`, `float32` par
  défaut (float16 seulement sur GPU et noté explicitement).
- Détection déterministe du device : `torch.cuda.is_available()`
  → GPU ; sinon CPU. Device utilisé loggé dans la sortie.
- Si la version du modèle téléchargée diffère de la révision
  épinglée dans le code, le script échoue à la construction
  (sécurité anti-dérive de modèle).

### §8. Décisions figées pour V3

- **Prompt V1.2 inchangé.**
- Pipeline retrieval amont : V2.1/hybride_filtre inchangé.
- Modèle reranker : `BAAI/bge-reranker-v2-m3`, revision
  épinglée.
- Candidats à reclasser : 20 par question.
- Top final envoyé au LLM : 5 (comme V2).
- Critère §4 (R@5 strict > 22/27) écrit avant toute mesure.
- Pas de code V3 dans le journal. Pas de run V3 dans le
  journal.

### §9. Risques identifiés

- **Modèle trop lourd pour le CI GitHub.** Les CI ne peuvent
  pas télécharger 1.1 GB à chaque run. Le reranker ne tournera
  QUE localement. Les tests CI sont tous sans réseau (mocks).
  Le benchmark de choix et le run LLM se font sur ma machine.
- **Dérive du modèle HuggingFace.** `revision` épinglé dans
  le code évite ; garde-fou qui fail-fast si mismatch.
- **Cache reranker scores** : si les scores sont mis en cache
  sur disque, le hash doit inclure la révision du modèle.
  Changer de revision doit invalider le cache.
- **Risque de ne rien améliorer.** Avec R@20 V2 = 100 %, le
  reranker ne peut qu'améliorer le classement interne. S'il
  n'y a pas de marge réelle sur les 5 Q qui restent en recall
  KO au R@5 (Q13, Q21 et 2 pages de Q23 / Q27 / Q30 wait
  Q30 est R@5 OK en V2), le critère §4 ne sera pas atteint.
  Ce n'est pas un bug, c'est une mesure.

### Ce qui n'est PAS dans V3

- Pas de ré-entraînement / fine-tuning du reranker : on prend
  le modèle tel quel, c'est le seul choix traçable.
- Pas d'ensemble de rerankers (ex. cross-encoder + LLM-as-
  reranker). Ajouterait un levier de fit, pas souhaitable avant
  une mesure baseline.
- Pas de combinaison reranker + re-tokenisation des Q. V2.1 déjà
  en place.



---

## 2026-11-07 (soir) — V3 benchmark reranker (sans LLM) : **V3 NON retenue**

### Résumé

Reranker `BAAI/bge-reranker-v2-m3` (revision épinglée
`953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, licence Apache-2.0)
appliqué aux 20 candidats V2.1/hybride_filtre des 31 Q. Scoring
par lots de 2 avec libération mémoire explicite, cache
incrémental par paire. Zéro appel LLM.

**Décision §4** : R@5 reranker = 21/27 ≤ 22/27 strict →
**V3 NON retenue**. On garde V2 (v2.1/hybride_filtre). Pas de
run LLM V3.

### Garde-fou amont (V2.1 recalculée)

- R@5 = **22/27** ✓ (identique à `benchmark_retrieval.py`)
- MRR = **0.7136** ✓
→ Pipeline amont intact.

### Longueurs tokenisées (31 Q × 20 cand = 620 paires)

Mesure RÉELLE avec le tokenizer du reranker (pas estimation) :

- Minimum : **104** tokens
- Médiane : **613** tokens
- Maximum : **1434** tokens
- Aucune paire ne dépasse 8192 tokens → **aucune troncation**.

La page BVMT la plus dense (max = 1434) utilise moins de 20 % du
contexte natif (8192). Confirme l'hypothèse ex ante : un reranker
à contexte 8192 traite nos pages entières sans compromis. Un
reranker à 512 tokens aurait tronqué environ 60 % des paires
(toutes au-dessus de ~450 tokens, soit la médiane 613 et au-delà).

### Résultats retrieval V3 vs V2 (27 Q avec page attendue)

| Métrique | V2 (hybride_filtre V2.1) | V3 (reranker) | Δ |
|---|---|---|---|
| Recall@1 | 15/27 | 8/27 | −7 |
| Recall@3 | 20/27 | 17/27 | −3 |
| **Recall@5** | **22/27** | **21/27** | **−1** |
| Recall@10 | 26/27 | 24/27 | −2 |
| MRR | 0.7136 | 0.5168 | −0.1968 |

**V3 dégrade TOUTES les métriques retrieval mesurées.** Le
reranker ne reclasse pas mieux que la fusion RRF sur ce corpus
financier.

### Gains / pertes au R@5 vs V2

- **Gains (3)** :
  - `ciments_bizerte_2024_23` (ROA calcul, 2 pages attendues)
  - `monoprix_2024_13` (SNMVT CA individuel) — Q que V2 avait
    perdue vs dense ; V3 la récupère
  - `sfbt_2024_21` (méthode valorisation stocks, texte_annexes)
- **Pertes (4)** :
  - `delice_holding_2024_27` (dividendes reçus)
  - `delice_holding_2024_30` (dividendes payés)
  - `sfbt_2024_18` (revenus SFBT)
  - `sfbt_2024_19` (autonomie SFBT)

Net : −1. Trois gains (dont texte_annexes Q21 et Q13 = perte
prévue V2 récupérée) mais quatre pertes sur des extractions
numériques et calculs simples. Le reranker favorise les chunks
narratifs sur les tableaux chiffrés — pattern inverse du filtre
entreprise + BM25 V2.1.

### Rangs des 5 Q d'intérêt

| qid | V2 (rangs) | V3 reranker (rangs) |
|---|---|---|
| Q12 monoprix_consolide (texte_annexes) | 1 | **1** (idem) |
| Q13 monoprix_individuel (extraction) | 10 (hors top-5) | **3** (dans top-5) |
| Q14 monoprix_individuel (calcul) | 2 | **1** (remontée) |
| Q21 sfbt (texte_annexes) | 11 (hors top-5) | **3** (dans top-5) |
| Q23 ciments (calcul, 2 pages) | 9, 1 | **4, 1** (une page remontée) |

Le reranker remonte bien des pages de **texte_annexes / calcul
multi-page** dans le top-5 (Q13, Q21, Q23). Mais il DÉPLACE
d'autres pages (Q18, Q19, Q27, Q30) qui étaient dans le top-5
V2 vers des rangs > 5. Le score reranker, basé sur la
correspondance sémantique profonde question↔chunk, ne semble
pas discriminer assez bien entre « chunk qui contient la vraie
réponse » et « chunk thématiquement proche ».

### Temps et mémoire

- **Chargement modèle** : 24.9 s (CPU, float32).
- **Reranking 620 paires** : 2 846.6 s = **47,4 min** avec
  batch_size=2. ≈ **4.6 s / paire** en moyenne sur CPU (Intel
  moderne, pas de GPU).
- **RSS pic** : 2 936 MB (~2.9 GB). Bien en-deçà de l'OOM kill
  du premier essai avec batch=20 (qui n'avait pas été mesuré
  mais devait culminer autour de 5-7 GB).
- RSS fin de scoring redescend à 1 818 MB, preuve que la
  libération `del` + `gc.collect()` entre lots fonctionne : le
  pic ne vient que des forwards actifs, pas d'accumulation.
- Estimation vs réalité : plan V3 §1 annonçait 5-15 min CPU
  « Intel i7 moderne » pour 620 paires. **Réalité : 47 min**
  (batch=2 force 310 forwards séquentiels plus coûteux que
  les 31 forwards batch=20 initialement envisagés mais qui
  OOM-killaient). Estimation plan trop optimiste ; à corriger
  dans un futur plan.

### Interprétation

Pourquoi le reranker dégrade-t-il la baseline V2.1 ?

Trois hypothèses non testées (il faudrait des expériences
dédiées pour trancher, hors scope V3 close) :

1. **Entraînement du reranker non spécialisé sur du
   français financier.** `bge-reranker-v2-m3` est multilingue
   général (MS-MARCO, NQ, HotpotQA, etc.). Sans fine-tuning sur
   du domaine BVMT, la pertinence des chunks courts chiffrés
   (bilans) peut être sous-évaluée par rapport aux chunks
   narratifs.
2. **BM25 V2.1 local est déjà très bien calibré.** La
   tokenisation V2.1 avec regroupement des nombres
   (`100 836 224` → un seul token à IDF élevée) donne au BM25
   un avantage spécifique sur les montants. Le reranker, lui,
   tokenise différemment et perd ce signal.
3. **La fusion RRF filtre + dense + BM25 est déjà un reranker
   léger.** V2.1/hybride_filtre fait déjà une forme de
   reclassement multi-signal. Un cross-encoder « générique »
   par-dessus ne lit pas forcément mieux.

### Décision §4

Critère écrit AVANT la mesure (plan V3 §4) : **R@5 strictement
supérieur à 22/27 sur les 31 Q**, MRR en départage.

- V3 reranker R@5 = 21/27 ≤ 22/27.
- **V3 NON retenue.**
- **On garde V2** (`v2.1/hybride_filtre`) comme pipeline de
  production.
- **Pas de run LLM V3** (§4 pré-conditionne tout run LLM).

Le jeu de validation (15 Q, §6 du plan V3) n'est PAS utilisé :
il n'a pas vocation à choisir, et sans §4 OK sur 31 Q, pas
d'évaluation.

### Fichiers créés

- `bilanlens/reranker.py` : wrapper `BAAI/bge-reranker-v2-m3`,
  revision épinglée, scoring par lots avec libération mémoire
  (`_scores_par_lots` isolé pour test d'invariance).
- `tests/test_reranker.py` : 20 tests sans réseau (modèle
  simulé) incluant `test_classement_final_invariant_sous_batch_size`.
- `scripts/benchmark_rerank.py` : benchmark 31 Q sans LLM avec
  garde-fou amont V2.1 = 22/27, cache incrémental par paire
  (`results/rerank_scores_cache.jsonl`), mesure psutil du RSS
  pic.
- `requirements.txt` : ajout `torch==2.15.0+cpu`,
  `transformers==5.22.2`, `psutil==7.2.2`.
- `results/retrieval_compare_v3.jsonl` : 31 Q × top-20 reranké.
- `results/rerank_scores_cache.jsonl` : 620 paires (question_id,
  chunk_id, score_rerank, model_revision).

Suite tests : +20 tests reranker, zéro régression.

### Enseignements

- **Le reranker « générique » ne bat pas un pipeline déjà
  hybride.** Avec filtre entreprise + BM25 V2.1 + RRF, la
  fusion est déjà informée de plusieurs signaux (lexical pour
  les montants, sémantique pour les méthodes, filtre pour la
  société). Ajouter un cross-encoder par-dessus brouille ces
  signaux au lieu de les affiner.
- **Mesurer AVANT d'estimer.** Le plan V3 annonçait
  « ~5-15 min CPU ». Réalité : 47 min (batch=2 forcé par OOM).
  Les longueurs tokenisées médianes (613) montrent qu'une page
  BVMT tient largement dans un reranker à 512 tokens, mais
  les max (1434) justifient a posteriori le choix de bge-v2-m3
  à contexte 8192.
- **Critère ex ante tient.** Sans un critère strict écrit
  AVANT la mesure, il aurait été tentant de « rationaliser »
  21/27 comme « presque 22/27 » ou de pointer les 3 gains
  (Q13, Q21, Q23) comme une amélioration qualitative. Le
  critère §4 interdit cette gymnastique : 21 ≤ 22, V3 rejetée.
- **Garde-fou mémoire fonctionne.** Premier essai avec
  batch=20 → OOM kill. Second essai avec batch=2 + libération
  explicite → pic 2.9 GB, bien dans l'enveloppe 16 GB système.
  Le cache incrémental n'a pas été exercé (pas de reprise
  nécessaire) mais reste disponible.

### Ce qui reste

- V3 close. Pas de `evaluate_v3.py` écrit, pas de run LLM V3.
- **Le jeu de validation (15 Q) reste intouché par V3.** Il
  gardera son statut de « mesure indépendante finale » pour
  une éventuelle V4.
- Pour de futures itérations, pistes documentées **mais non
  retenues ici** :
  - Fine-tuning du reranker sur du français financier
    (coûteux, hors scope étudiant).
  - Reranker plus petit (`jina-reranker-v1-tiny-en`) pour
    comparer vitesse/qualité.
  - LLM-as-reranker (Flash-Lite sur des paires), mais ajouterait
    un deuxième appel LLM par Q → coût prohibitif.


