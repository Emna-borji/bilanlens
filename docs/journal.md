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
