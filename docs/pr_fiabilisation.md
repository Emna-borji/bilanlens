# Fiabilisation du pipeline d'analyse financière

## Résumé

Fiabilisation de BilanLens (ex-FinSight) sur un éventail large de bilans
industriels / commerciaux : SCE tunisien (Système Comptable des
Entreprises), PCG français, IFRS anglais ;
PDF à texte, PDF scannés via OCR, XLSX multi-feuilles, CSV, TXT, DOCX.
Banques et assurances sont détectées et signalées hors périmètre.

## Changements principaux

### Extraction
- OCR optionnel pour les PDF scannés (`pytesseract` + PyMuPDF).
  Repli silencieux si Tesseract n'est pas installé ; les pages
  scannées produisent alors un message explicite dans l'interface.
- OCR par **coordonnées** (`image_to_data`) : la position de chaque mot
  est connue, les colonnes sont retrouvées par ancre (date) même quand
  le texte brut OCR colle plusieurs montants par un simple espace.
- `parse_amount` : une virgule unique est désormais toujours un
  séparateur décimal, même avec 3 chiffres de décimales (SFBT :
  « 1 281 772 854,965 »). Deux virgules = séparateur de milliers.
- Détection et suppression des numéros de note en fin de libellé
  (ex. « Revenus 29 » → « Revenus »).
- Stratégie hybride de groupement des mots numériques : seuil
  adaptatif pour les montants expansés (PDF natif), un mot = un
  montant pour les montants compacts (OCR).

### Mapping
- `normalize()` supprime désormais les accents : les libellés en
  MAJUSCULES SANS ACCENTS (variante SCE formelle) sont reconnus.
- Alias étendus pour PCG français (Actif immobilisé, Actif circulant,
  Capital, Dettes à long terme, Immobilisations corporelles nettes…) et
  IFRS anglais (Total non-current assets, Property, plant and equipment,
  Total liabilities, Trade and other receivables / payables…).
- Système de **rang** d'alias : les sous-totaux officiels
  (« Total ... », « Capitaux propres », « Actif immobilisé »,
  « Stocks nets »…) l'emportent sur les composants (« Immobilisations
  corporelles », « Autres réserves »).
- Nouveau poste `minority_interests` (Monoprix consolidé 2024).

### Hors périmètre
- Nouveau module `bilanlens/sector.py` : détection par règles des
  bilans bancaires (dépôts de clientèle, PNB, marge d'intérêt…) et
  d'assurance (provisions techniques, primes acquises…).
- Seuil : au moins 2 indicateurs du même secteur, pour éviter les
  faux positifs.

### Contrôles de cohérence
- Nouveau module `bilanlens/consistency.py` :
  - Total actif = Capitaux propres + Dettes (± intérêts minoritaires) ;
  - Actifs courants + Actifs non courants = Total actif ;
  - Capital + Réserves + Résultat ≈ Capitaux propres.
- Un écart relatif supérieur à 1 % déclenche une alerte.

### Interface
- `app.py` : branchement des avertissements OCR, du détecteur de
  secteur hors périmètre, et des contrôles de cohérence. Les
  contrôles sont également ajoutés au JSON exporté.

## Tests pytest — 38/38 verts

- **test_analysis** (3) : ratios, dénominateurs nuls, diagnostic.
- **test_fixtures_resultats** (6) : test1, test2, test3 en `.txt` ET
  en `.pdf` d'après `RESULTATS_ATTENDUS.txt` (piège d'ordre, colonnes
  2024/2025, perte parenthésée, reconstitution).
- **test_synthetic_bilans** (6) : PCG français, IFRS anglais, Excel
  multi-feuilles, CSV N/N-1/N-2, UPPERCASE sans accents, pièges
  « Autres ... » placés avant les vrais totaux.
- **test_consistency** (7) : trois contrôles bilan + tolérance 1 %.
- **test_sector** (6) + **test_bank_out_of_scope** (2) : banque et
  assurance détectées, industrielle non flaguée.
- **test_real_bilans** (6) : SOTUVER (ratios cibles exacts),
  **Monoprix consolidé** (10 postes exacts + 3-way check), **SFBT**
  (10 postes exacts, décimales dinars), **Ciments de Bizerte** (bilan
  en perte), smoke-tests Monoprix individuel + Délice Holding.
- **test_ocr** (2) — marqués `ocr`, skip automatique si Tesseract
  absent : test1 scanné (ratios complets ± marge OCR), SOTUVER scanné
  pages 2-4 (5 ratios cibles).

Workflow GitHub Actions : installation Tesseract (fra + eng) +
poppler + pytest, déclenché sur push et pull-request.

## Limites connues documentées

- PDF à mise en page très dense (Monoprix individuel, Délice Holding
  pour certains postes) : smoke-tests, non ratios exacts.
- OCR : qualité tributaire du scan ; les erreurs fréquentes dans les
  nombres (O/0, l/1, I/1, S/5, B/8) sont corrigées
  heuristiquement, mais l'affichage mentionne explicitement l'OCR.
- Diagnostic indicatif, pas un conseil d'investissement.

## Vérifications avant merge

- [x] 38 tests pytest passent (dont réels bvmt.com.tn et OCR).
- [x] Aucun secret, clé ou fichier personnel dans le dépôt.
- [x] Licence MIT ajoutée, sources `bvmt.com.tn` citées.
- [x] README à jour (installation, OCR, lancement, limites).
- [x] Workflow GitHub Actions prêt à l'emploi.
