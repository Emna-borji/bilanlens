# Règles de travail — BilanLens (mode apprentissage)

Je suis étudiant(e) en Master Data Science. Mon objectif est
d'APPRENDRE, pas seulement d'obtenir un produit fini.

## Avant de coder

- Explique d'abord le concept (ex. RAG, embeddings, LangGraph)
  simplement, avec un exemple tiré de BilanLens.
- Propose 2 ou 3 approches possibles avec leurs avantages et
  inconvénients, puis laisse-moi choisir.
- Donne un plan en petites étapes et attends mon accord.

## Pendant le code

- Une petite étape à la fois (un fichier ou une fonction), jamais
  tout d'un coup.
- Laisse-moi écrire les parties qui contiennent une décision
  importante.
- Pas de nouvelle bibliothèque sans m'expliquer pourquoi elle est
  nécessaire.

## Après chaque étape

- Résume ce qui a été fait et pourquoi, en 5 lignes maximum.
- Mets à jour docs/journal.md : ce que j'ai appris, les décisions
  prises et leur justification.
- Pose-moi 3 questions pour vérifier que j'ai compris, puis corrige
  mes réponses.
- Ne commite pas : je relis et je commite moi-même.

## Règles techniques

- Le LLM ne calcule jamais les ratios : le code les calcule.
- Tous les tests existants doivent rester verts.
- Toujours lancer les tests via le Python du venv local, pas le
  pytest global du PATH :
  `.\.venv\Scripts\python.exe -m pytest -v` (Windows)
  ou `.venv/bin/python -m pytest -v` (macOS / Linux).
  Un pytest du Python système ne voit pas `pytesseract`, `pymupdf`
  ni `pdf2image` et saute silencieusement les tests OCR.