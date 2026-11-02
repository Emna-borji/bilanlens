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
  absente du top-5, seule page 2 (total actif) remonte → abstention
  correcte du modèle. **Recall KO** sur un calcul multi-page.
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
