# BilanLens — Assistant d'analyse financière

Mini-projet pédagogique Streamlit : importer un bilan ou un rapport
financier, identifier les postes comptables, calculer des ratios et
produire un diagnostic explicable.

Pas d'IA : la reconnaissance des postes repose uniquement sur des règles
(alias exacts, normalisation, préférence des sous-totaux officiels).
Seul l'OCR (optionnel) utilise un modèle entraîné externe (Tesseract).

## Périmètre

**Dans le périmètre.** Sociétés industrielles et commerciales :
- normes comptables tunisiennes (Système Comptable des Entreprises,
  SCE), PCG français, IFRS anglais ;
- formats PDF (texte ou scanné via OCR), XLSX, CSV, TXT, DOCX ;
- bilans sur plusieurs exercices (N, N-1, N-2…) : BilanLens choisit la
  période la plus récente par défaut.

**Hors périmètre.** Les banques et les assurances ont une structure de
bilan différente (dépôts de clientèle, provisions techniques, produit
net bancaire…). BilanLens les détecte par règles et affiche un
avertissement : les ratios industriels n'y sont pas pertinents.

## Fonctionnalités

- Import PDF, Excel multi-feuilles, CSV, TXT, DOCX.
- Lecture de PDF à texte et de **PDF scannés via OCR** (fra + eng).
- Reconnaissance des libellés en français (SCE tunisien, PCG français,
  MAJUSCULES SANS ACCENTS) et en anglais (IFRS).
- Correspondance **exacte** des alias ; les sous-totaux officiels
  (« Total ... », « Capitaux propres », « Actif immobilisé »...)
  l'emportent sur les composants (« Immobilisations corporelles »,
  « Autres réserves »).
- Reconstitution automatique des sous-totaux absents (actifs courants
  depuis Stocks + Créances + Trésorerie, etc.).
- **Contrôles de cohérence** du bilan :
  - total actif = capitaux propres + dettes (± intérêts minoritaires) ;
  - actifs courants + actifs non courants = total actif ;
  - capital + réserves + résultat ≈ capitaux propres.
  Un écart > 1 % déclenche une alerte.
- Détection des bilans **bancaires et d'assurance** (hors périmètre).
- Calcul des 12 ratios de la fiche de cours (Master Data Science – Analyse
  Financière) regroupés en 5 familles : liquidité, endettement, rentabilité,
  activité, marché.
- Diagnostic explicable (points forts, risques, précautions, conclusion
  dynamique).
- Export des résultats en CSV et JSON (avec les contrôles de cohérence).

## Installation

Python 3.10+ recommandé.

```bash
python -m venv .venv

# Windows :
.venv\Scripts\activate

# macOS / Linux :
source .venv/bin/activate

pip install -r requirements.txt
```

### OCR (optionnel)

L'OCR nécessite le binaire Tesseract (langues `fra` et `eng`).

- **Windows** : installer via winget ou le MSI :
  ```powershell
  winget install UB-Mannheim.TesseractOCR
  ```
  Puis télécharger `fra.traineddata` depuis
  [github.com/tesseract-ocr/tessdata](https://github.com/tesseract-ocr/tessdata/raw/main/fra.traineddata)
  et le copier dans `C:\Program Files\Tesseract-OCR\tessdata\`.
  BilanLens détecte automatiquement le binaire aux emplacements standards.

- **macOS** : `brew install tesseract tesseract-lang`

- **Linux (Debian / Ubuntu)** :
  ```bash
  sudo apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng
  ```

Si Tesseract est absent, BilanLens continue de fonctionner : les PDF
scannés produiront un message « installez Tesseract pour l'OCR » et
les tests OCR seront automatiquement sautés.

## Lancement

```bash
streamlit run app.py
```

## Lancer les tests

**Toujours lancer pytest via le Python du venv local**, pas le
pytest global du PATH : les paquets `pytesseract`, `pymupdf` et
`pdf2image` sont installés dans `.venv` et un pytest du Python
système ne les voit pas (les tests OCR seraient alors silencieusement
sautés).

```powershell
# Windows (PowerShell)
.\.venv\Scripts\python.exe -m pytest -v
```

```bash
# macOS / Linux
.venv/bin/python -m pytest -v
```

Alternative : activer le venv d'abord (`.\.venv\Scripts\activate`
sous Windows, `source .venv/bin/activate` sous macOS/Linux), puis
lancer `pytest -v`.

- Les tests marqués `ocr` sont automatiquement sautés si Tesseract
  (binaire + langue `fra`) n'est pas disponible.
- Les tests marqués `real` utilisent des états financiers réels publiés
  sur [bvmt.com.tn](https://www.bvmt.com.tn/) et peuvent prendre
  plus de temps.

Pour n'exécuter que les tests rapides :

```powershell
.\.venv\Scripts\python.exe -m pytest -v -m "not real and not ocr"
```

## Sources des bilans de test

- Les bilans réels (`tests/data/real_*.pdf`) proviennent de la
  **Bourse de Tunis** ([bvmt.com.tn](https://www.bvmt.com.tn/)) :
  SOTUVER, Monoprix, SFBT, Délice Holding, Ciments de Bizerte,
  états financiers annuels individuels 2024.
- Les bilans synthétiques (`tests/data/synth_*`, `test1-3_*`) sont
  **fictifs** et créés uniquement pour tester BilanLens. Les montants et
  les dénominations ne correspondent à aucune société réelle.

## Structure du dépôt

```
app.py                      # Interface Streamlit
bilanlens/
  extraction.py             # Lecture des fichiers (PDF, XLSX, CSV, DOCX)
                            # + OCR en repli pour les PDF scannés.
  mapping.py                # Alias et rang des postes comptables.
  analysis.py               # Calcul des ratios et diagnostic.
  consistency.py            # Contrôles de cohérence du bilan.
  sector.py                 # Détection banque / assurance hors périmètre.
samples/
  exemple_bilan.txt         # Bilan synthétique simple de démonstration.
tests/
  conftest.py               # Helpers de test, skip OCR si Tesseract absent.
  _pipeline.py              # Pipeline commun pour les tests fixtures.
  test_analysis.py          # Tests unitaires des ratios et du diagnostic.
  test_consistency.py       # Tests unitaires des contrôles de cohérence.
  test_sector.py            # Tests unitaires de la détection sectorielle.
  test_fixtures_resultats.py# test1-3 d'après RESULTATS_ATTENDUS.txt.
  test_synthetic_bilans.py  # Bilans synthétiques PCG, IFRS, Excel, CSV…
  test_bank_out_of_scope.py # Bilan de banque = hors périmètre.
  test_real_bilans.py       # Bilans réels de bvmt.com.tn.
  test_ocr.py               # PDF scannés (test1 + SOTUVER).
  data/                     # Fichiers de test (PDF, TXT, XLSX, CSV).
scripts/
  generate_synth_excel.py   # Reconstruit synth_excel_multisheet.xlsx.
  generate_scanned_pdf.py   # Rend un .txt en PDF image (OCR).
  pdf_to_scanned.py         # Rend un PDF texte en PDF image (OCR).
.github/workflows/tests.yml # CI : installation de Tesseract + pytest.
```

## Ratios calculés

Les 12 ratios suivent exactement la fiche de cours (Master Data Science –
Analyse Financière). Aucun autre ratio n'est produit.

| Famille | Ratio | Formule |
|---------|-------|---------|
| Ratios de liquidité | Liquidité générale | Actifs courants / Dettes à court terme |
| Ratios de liquidité | Liquidité réduite (quick ratio) | (Actifs courants − Stocks) / Dettes à court terme |
| Ratios d'endettement (structure financière) | Endettement global | Dettes totales / Capitaux propres |
| Ratios d'endettement (structure financière) | Autonomie financière | Capitaux propres / Total passif |
| Ratios de rentabilité | Rentabilité nette | Résultat net / Chiffre d'affaires |
| Ratios de rentabilité | Rentabilité des capitaux propres (ROE) | Résultat net / Capitaux propres |
| Ratios de rentabilité | Rentabilité économique (ROA) | Résultat net / Total actif |
| Ratios d'activité (efficience) | Rotation des stocks | Coût des ventes / Stock moyen |
| Ratios d'activité (efficience) | Délai de recouvrement clients | (Créances clients / CA) × 365 |
| Ratios d'activité (efficience) | Délai de paiement fournisseurs | (Dettes fournisseurs / Achats TTC) × 365 |
| Ratios de marché (si données boursières) | PER | Cours de l'action / Bénéfice par action |
| Ratios de marché (si données boursières) | Dividend Yield | Dividende par action / Cours de l'action |

Seuils du cours utilisés :

- Liquidité générale : idéal > 1 ; en deçà, les actifs courants ne couvrent
  pas les dettes à court terme.
- Endettement global : > 1 signale une dépendance élevée au financement
  externe ; ≤ 1 une structure financière équilibrée.

Les autres ratios n'ont pas de seuil dans la fiche de cours ; BilanLens
affiche alors un repère **indicatif, hors cours**.

Autonomie financière : BilanLens utilise *Capitaux propres / Total passif*
(total des capitaux propres et des passifs). Si le Total passif n'est pas
disponible dans le document, il est remplacé par le Total actif, équivalent
par équilibre du bilan — ce choix est signalé dans la note du ratio.

## Limites connues

- Les PDF à mise en forme très dense (3 colonnes imbriquées, notes
  inline, montants concaténés par pdfplumber) peuvent ne pas être
  parfaitement extraits. BilanLens signale alors les postes manquants.
- L'OCR dépend de la qualité du scan : les erreurs fréquentes dans les
  nombres (O/0, l/1, I/1, S/5, B/8) sont corrigées heuristiquement,
  mais le résultat doit toujours être vérifié par l'utilisateur.
- Les sociétés **holding** peuvent n'avoir pas de chiffre d'affaires
  classique : certaines familles de ratios ne seront pas calculables.
- Le diagnostic est pédagogique et ne constitue pas un conseil
  d'investissement.

## Confidentialité des embeddings (semaine 2 étape 4)

Les embeddings sont générés via l'**API Gemini (`gemini-embedding-2`)**
sous quota free tier. Google indique dans ses CGU que les requêtes
du free tier **peuvent être utilisées pour améliorer ses modèles**.

C'est **acceptable pour BilanLens** parce que le corpus de départ est
constitué de **rapports annuels publics BVMT** déjà disponibles sur
[bvmt.com.tn](https://www.bvmt.com.tn/).

Ce n'est **pas adapté à des documents confidentiels** (plan d'affaires
interne, données clients non publiées, pièces d'audit). Pour un tel
usage, basculer sur :

- un plan **payant** Google (les requêtes payantes ne sont pas
  utilisées pour l'entraînement) ;
- ou un **adapter local** `bge-m3` (sur Google Colab pour le calcul,
  stockage des vecteurs côté machine locale). L'interface
  `bilanlens.embeddings.Encodeur` est faite pour accueillir cet
  adapter sans toucher à `index.py`.

## Benchmark RAG — B0 à V3 (évaluation étape par étape)

Après l'application Streamlit, le projet comprend une seconde partie :
évaluer un pipeline **RAG + LLM** (modèle Gemini-3.5-flash-lite) sur
**31 questions** rédigées à partir de 6 rapports annuels BVMT 2024
(SOTUVER, SFBT, Ciments de Bizerte, Délice Holding, Monoprix
individuel, Monoprix consolidé).

Les 31 questions couvrent 5 catégories : extraction, calcul,
comparaison, texte_annexes, sans_reponse. Elles sont dans
`data/benchmark/questions.jsonl` et validées automatiquement par
`tests/test_benchmark.py` (chaque réponse chiffrée vérifiée dans le
PDF source ; chaque question sans_reponse vérifiée absente du PDF).

Chaque étape est documentée dans `docs/journal.md` avec les
décisions prises, les erreurs corrigées, et les mesures.

### Résultats des 6 versions

Deux lignes B0 mesurent la base sans retrieval. Les versions V1, V1.1
et V1.2 testent **le prompt** sur un même retrieval dense top-5
(Chroma + embeddings Gemini). V2 change **le retrieval** en gardant
le prompt V1.2. V3 teste un reranker cross-encoder sur les candidats
V2.

**Chiffres sources** : `results/scores*.jsonl` (bons résultats,
justes, fausses) et `docs/journal.md` (Recall@5 et MRR).

| Version | Bons résultats | Justes | Fausses | Recall@5 | MRR |
|---|---|---|---|---|---|
| B0-strict | 4/31 | 0 | 0 | n/a | n/a |
| B0-libre | 5/31 | 1 | 6 | n/a | n/a |
| V1 | 20/31 | 16 | 1 | 19/27 | 0,543 |
| V1.1 | 22/31 | 18 | 4 | 19/27 | 0,543 |
| V1.2 | 24/31 | 20 | 0 | 19/27 | 0,543 |
| **V2** | **26/31** | **22** | **1** | **22/27** | **0,714** |
| V3 (reranker) | **non retenue** | — | — | 21/27 (retrieval) | 0,517 (retrieval) |

Lectures :

- « Bons résultats » = classes `juste` + `abstention_correcte`.
- « Fausses » = `fausse_recall_ok` + `fausse_recall_ko` + `reponse_a_tort`.
- Recall@5 et MRR sont mesurés sur les **27 questions** avec page
  attendue (hors 4 sans_reponse). B0 n'a pas de retrieval, d'où `n/a`.
- V1, V1.1 et V1.2 partagent le même retrieval → mêmes valeurs
  Recall@5 et MRR. Seul le prompt change entre les trois.
- **V3 (reranker `BAAI/bge-reranker-v2-m3`)** a été **écartée par le
  critère §4** du plan V3 (Recall@5 strictement > 22/27). Résultat
  mesuré : 21/27 ≤ 22/27, et MRR en chute (0,517 vs 0,714). Aucun
  run LLM V3 lancé ; on garde V2 (`v2.1/hybride_filtre`).

## Validation (15 questions nouvelles)

Pour tester si les gains observés sur les 31 Q d'origine se
généralisent, un jeu de validation de **15 questions nouvelles**
(`data/benchmark/questions_validation.jsonl`) a été rédigé à partir
des 6 mêmes rapports **avant tout run LLM sur ce jeu** (commit
`cb5c394`, 2026-11-06, horodatage = preuve d'ex ante).

Distribution : 4 extractions, 4 calculs (dont 2 autonomies sur
sociétés non testées), 2 comparaisons, 3 texte_annexes, 2 sans_reponse
(dont 1 sans société nommée). Au moins une Q « Monoprix » sans
qualifier individuel / consolidé.

### Résultats sur le jeu de validation

| Version | Bons résultats | Justes | Fausses | Recall@5 | MRR |
|---|---|---|---|---|---|
| V1.2 | 13/15 | 11 | 0 | 11/13 | 0,629 |
| V2 | 14/15 | 12 | 0 | 11/13 | 0,635 |

Chiffres sources : `results/scores_v1_2_validation.jsonl` et
`results/scores_v2_validation.jsonl`.

### Limites connues du jeu de validation

Documentées dans `docs/journal.md` (entrée 2026-11-06 soir 4, corrigée
2026-11-07) :

- **15 questions donnent une TENDANCE, pas une PREUVE.** L'écart V2
  vs V1.2 sur validation (+1 Q) est dans la variance d'échantillon.
- **Le jeu est peut-être plus FACILE que les 31 Q d'origine.**
  5 Q sur 15 reposent sur des totaux de bilan (dernière ligne du
  bilan actif / passif), faciles à retrouver.
- **val_02 et val_06 sont `juste` malgré un recall@5 KO strict.**
  Le modèle répond par arithmétique intra-page (addition de
  sous-totaux) ou par lecture croisée (total CP + passifs = total
  actif).
- **La seule Q « Monoprix » sans qualifier est une sans_reponse**
  (val_14). Elle teste la robustesse du filtre ambigu mais **ne
  teste pas** le choix du modèle entre bilan individuel et bilan
  consolidé sur une donnée réelle. Angle mort à combler dans un
  benchmark futur.
- **val_11 et val_12 portent sur le même sujet** (crise Ciments de
  Bizerte 2023-2024, pages différentes). Un seul topic métier
  couvert deux fois.

## Scripts du benchmark

Toutes les commandes partent du Python du venv local :
`.\.venv\Scripts\python.exe` (Windows) ou `.venv/bin/python`
(macOS / Linux). Les runs LLM nécessitent `GEMINI_API_KEY` dans
`.env`.

| Script | Rôle |
|---|---|
| `scripts/evaluate_b0.py` | Run B0 : LLM sans retrieval, prompt strict ou libre (`--variante strict\|libre`). Écrit `results/b0.jsonl`. |
| `scripts/evaluate_v1.py` | Run V1 : retrieval dense Chroma top-5 + prompt V1. Écrit `results/v1.jsonl` + `results/retrieval_top20.jsonl`. |
| `scripts/evaluate_v1_1.py` | Run V1.1 : V1 + consigne « fais le calcul exact ». Reconstruit le contexte V1 (zéro appel Chroma). |
| `scripts/evaluate_v1_2.py` | Run V1.2 : V1.1 + 2 règles anti-ambigüité (total passif, sens de variation). |
| `scripts/benchmark_retrieval.py` | Compare 10 configurations retrieval **sans LLM** (dense, BM25, hybride RRF × V2 / V2.1 tokenisation). Produit `results/retrieval_compare.jsonl`. |
| `scripts/evaluate_v2.py` | Run V2 : pipeline `v2.1/hybride_filtre` (filtre entreprise + BM25 stop-words FR + fusion RRF) + prompt V1.2. |
| `scripts/evaluate_validation.py` | Runs V1.2 + V2 sur le jeu de validation (15 Q). |
| `scripts/benchmark_rerank.py` | Benchmark V3 reranker (BAAI/bge-reranker-v2-m3) **sans LLM**. V3 écartée par le critère §4 ; aucun `evaluate_v3.py` n'a été écrit. |
| `scripts/score.py` | Scoring : `--mode {v1\|v1-1\|v1-2\|v2\|validation\|compare\|rebuild-context}`. |

### Dépendances optionnelles pour le benchmark reranker V3

V3 n'a pas été retenue, donc `torch`, `transformers` et `psutil` sont
**commentés** dans `requirements.txt`. Pour reproduire le benchmark
V3 localement :

```bash
pip install --index-url https://download.pytorch.org/whl/cpu torch==2.15.0+cpu
pip install transformers==5.22.2 psutil==7.2.2
```

Le modèle `BAAI/bge-reranker-v2-m3` (≈ 1,1 GB, Apache-2.0, revision
`953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`) est téléchargé
automatiquement dans `~/.cache/huggingface/hub/` au premier lancement.

## Licence

MIT — voir [LICENSE](LICENSE).
