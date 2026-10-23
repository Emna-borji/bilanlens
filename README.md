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

## Licence

MIT — voir [LICENSE](LICENSE).
