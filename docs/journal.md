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
