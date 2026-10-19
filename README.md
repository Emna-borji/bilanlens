# FinSight — Assistant d'analyse financière

Mini-projet pédagogique Streamlit : importer un bilan ou un rapport
financier, identifier les postes comptables, calculer des ratios et
produire un diagnostic explicable.

Pas d'IA : la reconnaissance des postes repose uniquement sur des règles
(alias exacts, normalisation, préférence des sous-totaux officiels).
Seul l'OCR (optionnel) utilise un modèle entraîné externe (Tesseract).

## Périmètre

**Dans le périmètre.** Sociétés industrielles et commerciales :
- normes SCF tunisien, PCG français, IFRS anglais ;
- formats PDF (texte ou scanné via OCR), XLSX, CSV, TXT, DOCX ;
- bilans sur plusieurs exercices (N, N-1, N-2…) : FinSight choisit la
  période la plus récente par défaut.

**Hors périmètre.** Les banques et les assurances ont une structure de
bilan différente (dépôts de clientèle, provisions techniques, produit
net bancaire…). FinSight les détecte par règles et affiche un
avertissement : les ratios industriels n'y sont pas pertinents.

## Fonctionnalités

- Import PDF, Excel multi-feuilles, CSV, TXT, DOCX.
- Lecture de PDF à texte et de **PDF scannés via OCR** (fra + eng).
- Reconnaissance des libellés en français (SCF, PCG, MAJUSCULES SANS
  ACCENTS) et en anglais (IFRS).
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
- Calcul des 12 ratios regroupés en 5 familles : liquidité, endettement,
  rentabilité, activité, marché.
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
  FinSight détecte automatiquement le binaire aux emplacements standards.

- **macOS** : `brew install tesseract tesseract-lang`

- **Linux (Debian / Ubuntu)** :
  ```bash
  sudo apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng
  ```

Si Tesseract est absent, FinSight continue de fonctionner : les PDF
scannés produiront un message « installez Tesseract pour l'OCR » et
les tests OCR seront automatiquement sautés.

## Lancement

```bash
streamlit run app.py
```

## Lancer les tests

```bash
pytest -v
```

- Les tests marqués `ocr` sont automatiquement sautés si Tesseract
  (binaire + langue `fra`) n'est pas disponible.
- Les tests marqués `real` utilisent des états financiers réels publiés
  sur [bvmt.com.tn](https://www.bvmt.com.tn/) et peuvent prendre
  plus de temps.

Pour n'exécuter que les tests rapides :

```bash
pytest -v -m "not real and not ocr"
```

## Sources des bilans de test

- Les bilans réels (`tests/data/real_*.pdf`) proviennent de la
  **Bourse de Tunis** ([bvmt.com.tn](https://www.bvmt.com.tn/)) :
  SOTUVER, Monoprix, SFBT, Délice Holding, Ciments de Bizerte,
  états financiers annuels individuels 2024.
- Les bilans synthétiques (`tests/data/synth_*`, `test1-3_*`) sont
  **fictifs** et créés uniquement pour tester FinSight. Les montants et
  les dénominations ne correspondent à aucune société réelle.

## Structure du dépôt

```
app.py                      # Interface Streamlit
finsight/
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

| Famille | Ratio | Formule |
|---------|-------|---------|
| Liquidité | Liquidité générale | Actifs courants / Passifs courants |
| Liquidité | Liquidité réduite | (Actifs courants − Stocks) / Passifs courants |
| Endettement | Endettement | Total des dettes / Capitaux propres |
| Endettement | Autonomie financière | Capitaux propres / Total actif |
| Rentabilité | Marge nette | Résultat net / Chiffre d'affaires |
| Rentabilité | ROE | Résultat net / Capitaux propres |
| Rentabilité | ROA | Résultat net / Total actif |
| Activité | Rotation des stocks | Coût des ventes / Stock moyen |
| Activité | Délai clients | Créances clients / CA × 365 |
| Activité | Délai fournisseurs | Dettes fournisseurs / Achats TTC × 365 |
| Marché | PER | Cours / Bénéfice par action |
| Marché | Rendement du dividende | Dividende / Cours |

Les seuils d'interprétation sont indicatifs et varient selon le secteur.

## Limites connues

- Les PDF à mise en forme très dense (3 colonnes imbriquées, notes
  inline, montants concaténés par pdfplumber) peuvent ne pas être
  parfaitement extraits. FinSight signale alors les postes manquants.
- L'OCR dépend de la qualité du scan : les erreurs fréquentes dans les
  nombres (O/0, l/1, I/1, S/5, B/8) sont corrigées heuristiquement,
  mais le résultat doit toujours être vérifié par l'utilisateur.
- Les sociétés **holding** peuvent n'avoir pas de chiffre d'affaires
  classique : certaines familles de ratios ne seront pas calculables.
- Le diagnostic est pédagogique et ne constitue pas un conseil
  d'investissement.

## Licence

MIT — voir [LICENSE](LICENSE).
