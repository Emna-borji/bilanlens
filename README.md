# FinSight — Assistant d'analyse financière

Mini-projet académique : importer un bilan ou un rapport financier, identifier les postes comptables, calculer des ratios et produire un diagnostic explicable.

## Fonctionnalités
- Import PDF, Excel, CSV, TXT et DOCX.
- Extraction de texte PDF et lecture de tableaux Excel/CSV.
- Reconnaissance de plusieurs variantes d'intitulés français et anglais.
- Sélection manuelle des postes détectés et correction des valeurs.
- Calcul de ratios classiques : liquidité générale, endettement, marge nette, ROE et autonomie financière.
- Diagnostic à base de règles transparentes, sans prétendre remplacer un analyste financier.
- Export des résultats en CSV et JSON.
- Jeu de données synthétique pour tester l'application sans utiliser de vrais comptes.

## Installation
Python 3.10+ recommandé.

```bash
python -m venv .venv
# Windows :
.venv\Scripts\activate
# macOS/Linux :
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Utilisation
1. Importer un document financier ou utiliser l'exemple fourni.
2. Vérifier les postes détectés dans l'onglet « Données extraites ».
3. Corriger les valeurs ou sélectionner un autre poste si nécessaire.
4. Choisir les postes utilisés pour les calculs.
5. Lire les ratios, les avertissements et le diagnostic.
6. Exporter les résultats.

## Limites connues
- Les PDF scannés nécessitent un OCR externe. FinSight signale quand le texte extrait est insuffisant; il ne prétend pas effectuer de l'OCR sans moteur installé.
- Les banques, assurances et autres secteurs réglementés nécessitent des ratios sectoriels dédiés. Les ratios généraux peuvent ne pas être pertinents pour eux.
- Les formules varient selon les cours et les référentiels comptables. Les formules affichées dans l'application sont explicites et doivent être confirmées avec l'enseignant.
- Les noms de postes et les nombres extraits automatiquement doivent être vérifiés avant toute conclusion.
- Le diagnostic est pédagogique et ne constitue pas un conseil d'investissement.

## Structure
- `app.py` : interface Streamlit.
- `finsight/extraction.py` : lecture des fichiers.
- `finsight/mapping.py` : correspondance des intitulés comptables.
- `finsight/analysis.py` : calculs et interprétations.
- `samples/exemple_bilan.txt` : exemple synthétique.
- `tests/` : tests unitaires.

## Formules utilisées par défaut
- Liquidité générale = Actifs courants / Passifs courants.
- Endettement (dettes/capitaux propres) = Total des dettes / Capitaux propres.
- Marge nette = Résultat net / Chiffre d'affaires.
- ROE = Résultat net / Capitaux propres.
- Autonomie financière = Capitaux propres / Total actif.

Ces formules sont des conventions de départ, pas des vérités universelles. Les intitulés et les définitions doivent être adaptés aux consignes du cours.
