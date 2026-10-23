# BilanLens — Interprétations, diagnostic et conclusion

Ce document explique **tout ce que BilanLens produit** une fois les ratios
calculés : les 12 ratios du cours, les phrases d'interprétation pour
chaque ratio (toutes les branches de décision), la construction du
diagnostic indicatif (points forts, risques, précautions) et de la
conclusion globale.

Il reflète fidèlement le code de `bilanlens/analysis.py` et sert à :

- comprendre ce que l'application dira dans chaque cas sans avoir à
  lire le code ;
- vérifier qu'une interprétation produite par l'UI correspond bien à
  la formulation attendue ;
- documenter la position de l'application par rapport aux seuils du
  cours (Master Data Science – Analyse Financière).

> **Mention centralisée affichée dans l'UI, le diagnostic et l'export JSON :**
> *« Seuils du cours : liquidité générale (idéal > 1) et endettement
> global (> 1 = dépendance élevée). Les autres seuils sont des repères
> indicatifs hors cours. »*

---

## 1. Les 12 ratios du cours

### 1.1 Ratios de liquidité

| Ratio | Formule | Clé interne | Format |
|---|---|---|---|
| Liquidité générale | Actifs courants / Dettes à court terme | `liquidite_generale` | multiple |
| Liquidité réduite (quick ratio) | (Actifs courants − Stocks) / Dettes à court terme | `liquidite_reduite` | multiple |

### 1.2 Ratios d'endettement (structure financière)

| Ratio | Formule | Clé interne | Format |
|---|---|---|---|
| Endettement global | Dettes totales / Capitaux propres | `endettement` | multiple |
| Autonomie financière | Capitaux propres / Total passif | `autonomie_financiere` | pourcentage |

**Note sur l'autonomie financière.** La fiche de cours utilise
*Capitaux propres / Total passif*. En pratique, BilanLens calcule
`total_passif = capitaux_propres + total_dettes` automatiquement
dès que les deux composants sont connus. Si le total passif ne peut
pas être reconstitué, BilanLens utilise `total_actif` à la place
(équivalent par équilibre du bilan) et la note du ratio le signale
explicitement.

### 1.3 Ratios de rentabilité

| Ratio | Formule | Clé interne | Format |
|---|---|---|---|
| Rentabilité nette | Résultat net / Chiffre d'affaires | `marge_nette` | pourcentage |
| Rentabilité des capitaux propres (ROE) | Résultat net / Capitaux propres | `rentabilite_capitaux_propres` | pourcentage |
| Rentabilité économique (ROA) | Résultat net / Total actif | `rentabilite_actifs` | pourcentage |

### 1.4 Ratios d'activité (efficience)

| Ratio | Formule | Clé interne | Format |
|---|---|---|---|
| Rotation des stocks | Coût des ventes / Stock moyen | `rotation_stocks` | multiple |
| Délai de recouvrement clients | (Créances clients / CA) × 365 | `delai_clients` | jours |
| Délai de paiement fournisseurs | (Dettes fournisseurs / Achats TTC) × 365 | `delai_fournisseurs` | jours |

**Stock moyen** = (stock_initial + stock_final) / 2. Si l'un des
deux manque, la rotation des stocks n'est pas calculée.

### 1.5 Ratios de marché (si données boursières)

| Ratio | Formule | Clé interne | Format |
|---|---|---|---|
| PER | Cours de l'action / Bénéfice par action | `per` | multiple |
| Dividend Yield | Dividende par action / Cours de l'action | `rendement_dividende` | pourcentage |

### 1.6 Donnée manquante / dénominateur nul

Pour tout ratio dont le numérateur est manquant ou le dénominateur
nul, BilanLens affiche :

> « Non calculable : donnée manquante ou dénominateur nul »

Et l'interprétation renvoie :

> « Données insuffisantes pour interpréter ce ratio. »

---

## 2. Phrases d'interprétation (toutes les branches)

Dans ce qui suit, « X » représente la valeur formatée en français
(virgule décimale, espace milliers).

### 2.1 Liquidité générale — seuil principal du cours = 1

| Condition | Phrase affichée |
|---|---|
| `< 1` | *« X : liquidité insuffisante, les actifs courants ne couvrent pas les dettes à court terme. »* |
| `1 ≤ x ≤ 2,5` | *« X : les dettes à court terme sont couvertes. »* |
| `> 2,5` | *« X : liquidité élevée ; vérifier que les stocks et les créances ne sont pas excessifs. »* |

### 2.2 Liquidité réduite (quick ratio)

| Condition | Phrase affichée |
|---|---|
| `< 1` | *« X : liquidité réduite insuffisante. Hors stocks, les actifs courants ne couvrent pas les dettes à court terme. »* |
| `≥ 1` | *« X : couverture à court terme assurée sans dépendre de la vente des stocks. »* |

### 2.3 Endettement global — seuil principal du cours = 1

| Condition | Phrase affichée |
|---|---|
| `< 0` | *« Capitaux propres négatifs : le ratio classique est difficile à interpréter et la situation doit être examinée. »* |
| `0 ≤ x ≤ 1` | *« X : endettement global ≤ 1, structure financière équilibrée. »* |
| `> 1` | *« X : endettement global > 1, dépendance élevée au financement externe. »* |

### 2.4 Autonomie financière

Pas de seuil chiffré dans la fiche de cours (voir la mention
centralisée) ; BilanLens utilise des bornes indicatives.

| Condition | Phrase affichée |
|---|---|
| `< 0` | *« Capitaux propres négatifs : signal de fragilité financière à examiner. »* |
| `< 20 %` | *« X % : autonomie financière faible. »* |
| `20 ≤ x < 50 %` | *« X % : les capitaux propres financent moins de la moitié du passif. »* |
| `≥ 50 %` | *« X % : bonne autonomie financière. »* |

### 2.5 Rentabilité nette (ex-marge nette)

| Condition | Phrase affichée |
|---|---|
| `< 0` | *« X % : rentabilité nette négative, l'entreprise enregistre une perte nette. »* |
| `= 0` | *« Rentabilité nette nulle : l'entreprise ne dégage pas de bénéfice net sur la période. »* |
| `0 < x < 5 %` | *« X % : rentabilité nette faible ; comparer au secteur. »* |
| `5 ≤ x < 15 %` | *« X % : rentabilité nette positive ; comparer aux entreprises du même secteur. »* |
| `≥ 15 %` | *« X % : rentabilité nette élevée ; vérifier qu'elle est durable. »* |

### 2.6 Rentabilité des capitaux propres (ROE)

| Condition | Phrase affichée |
|---|---|
| `< 0` | *« X % : rentabilité des capitaux propres négative. »* |
| `0 ≤ x < 8 %` | *« X % : rentabilité des capitaux propres relativement faible. »* |
| `8 ≤ x ≤ 20 %` | *« X % : bonne rentabilité des capitaux propres. »* |
| `> 20 %` | *« X % : rentabilité élevée ; examiner aussi l'endettement global et le niveau des capitaux propres. »* |

### 2.7 Rentabilité économique (ROA)

| Condition | Phrase affichée |
|---|---|
| `< 0` | *« X % : rentabilité économique négative. »* |
| `0 ≤ x < 5 %` | *« X % : rentabilité économique relativement faible. »* |
| `≥ 5 %` | *« X % : les actifs génèrent un résultat net positif ; comparer au secteur. »* |

### 2.8 Rotation des stocks

| Condition | Phrase affichée |
|---|---|
| `≤ 0` | *« Rotation nulle ou négative : vérifiez le coût des ventes et le stock moyen. »* |
| `0 < x < 4` | *« X fois, soit environ J jours de stock : rotation relativement lente. »* |
| `≥ 4` | *« X fois, soit environ J jours de stock : rotation relativement rapide. »* |

J = 365 / rotation_stocks.

### 2.9 Délai de recouvrement clients

| Condition | Phrase affichée |
|---|---|
| `< 0` | *« Délai négatif inhabituel : vérifiez les créances clients et le chiffre d'affaires. »* |
| `0 ≤ x < 60 jours` | *« X jours : délai inférieur à 60 jours. »* |
| `≥ 60 jours` | *« X jours : délai relativement long, à comparer aux conditions de paiement accordées aux clients. »* |

### 2.10 Délai de paiement fournisseurs

Les phrases dépendent aussi du délai clients lorsqu'il est connu.

| Condition | Phrase affichée |
|---|---|
| `< 0` | *« Valeur négative inhabituelle : vérifiez les dettes fournisseurs et les achats TTC. »* |
| `fournisseurs > clients` (délai clients connu) | *« X jours : l'entreprise paie ses fournisseurs plus tard qu'elle n'encaisse ses clients (C jours), ce qui peut soulager sa trésorerie. Vérifiez les délais légaux et contractuels applicables. »* |
| `fournisseurs < clients` (délai clients connu) | *« X jours : l'entreprise paie ses fournisseurs avant d'encaisser ses clients (C jours), ce qui peut exercer une pression sur sa trésorerie. »* |
| Sinon, `> 60 jours` | *« X jours : délai supérieur à 60 jours. Vérifiez les conditions de paiement et les délais légaux ou contractuels applicables. »* |
| Sinon, `≤ 60 jours` | *« X jours : délai estimé à partir du solde fournisseurs de clôture ; comparez-le aux conditions contractuelles. »* |

C = délai clients en jours (nombre formaté).

### 2.11 PER

| Condition | Phrase affichée |
|---|---|
| `≤ 0` | *« PER nul ou négatif : interprétation classique peu pertinente, notamment si le bénéfice par action est nul ou négatif. »* |
| `0 < x < 10` | *« X : PER faible. Les seuils dépendent du secteur, du marché et des perspectives de croissance. »* |
| `10 ≤ x ≤ 20` | *« X : PER modéré. Les seuils dépendent du secteur, du marché et des perspectives de croissance. »* |
| `> 20` | *« X : PER élevé. Les seuils dépendent du secteur, du marché et des perspectives de croissance. »* |

### 2.12 Dividend Yield

| Condition | Phrase affichée |
|---|---|
| `< 0` | *« Dividend Yield négatif inhabituel : vérifiez le dividende et le cours de l'action. »* |
| `= 0` | *« Dividend Yield nul : aucun dividende positif rapporté au cours de l'action sur la base des données fournies. »* |
| `0 < x < 2 %` | *« X % : Dividend Yield faible. Ce rendement exclut la variation du cours et la fiscalité. »* |
| `2 ≤ x ≤ 5 %` | *« X % : Dividend Yield correct. Ce rendement exclut la variation du cours et la fiscalité. »* |
| `> 5 %` | *« X % : Dividend Yield élevé. Ce rendement exclut la variation du cours et la fiscalité. »* |

---

## 3. Diagnostic indicatif

Pour chaque bilan, BilanLens produit trois listes et une conclusion
globale, affichées dans la section « 6. Diagnostic financier
indicatif » de l'UI.

### 3.1 Points forts (`points_forts`)

| Déclencheur | Phrase ajoutée |
|---|---|
| `liquidite_generale ≥ 1` | *« Bonne couverture générale à court terme : liquidité de X. »* |
| `endettement ≤ 1` (et capitaux propres > 0) | *« Endettement global ≤ 1 (X) : structure financière équilibrée. »* |
| `rentabilite_nette > 0` | *« Rentabilité nette positive : X %. »* |
| `ROE ≥ 15 %` | *« Rentabilité des capitaux propres élevée : ROE de X %. »* |
| `délai fournisseurs > délai clients` (les deux connus) | *« Décalage potentiellement favorable à la trésorerie : les clients sont encaissés en C jours, contre F jours pour payer les fournisseurs. Vérifier les délais contractuels et légaux. »* |
| Aucun point fort ne se déclenche | *« Aucun point fort ne peut être établi avec certitude à partir des données disponibles. »* |

### 3.2 Risques (`risques`)

| Déclencheur | Phrase ajoutée |
|---|---|
| `liquidite_generale < 1` | *« Liquidité générale inférieure à 1 (X) : les actifs courants ne couvrent pas les passifs courants. »* |
| `liquidite_reduite < 1` | *« Liquidité réduite de X : hors stocks, la couverture des passifs courants est insuffisante. »* |
| `capitaux_propres ≤ 0` | *« Capitaux propres nuls ou négatifs : l'endettement global est difficile à interpréter. »* |
| `endettement > 1` | *« Endettement global > 1 (X) : dépendance élevée au financement externe. »* |
| `résultat_net < 0` | *« Le résultat net est négatif : l'entreprise enregistre une perte nette. »* |
| `résultat_net = 0` | *« Le résultat net est nul : l'entreprise ne dégage pas de bénéfice net. »* |
| `ROE < 0` | *« Le ROE est négatif : examiner le résultat net et la structure des capitaux propres. »* |
| `autonomie < 0` | *« Les capitaux propres sont négatifs par rapport au total actif. »* |
| `autonomie < 20 %` | *« Autonomie financière faible : X %. »* |
| `20 ≤ autonomie < 50 %` | *« Autonomie financière inférieure à 50 % : X %. Les capitaux propres financent moins de la moitié des actifs. »* |
| `délai fournisseurs < délai clients` (les deux connus) | *« Décalage potentiellement défavorable à la trésorerie : les fournisseurs sont payés en F jours, avant l'encaissement des clients estimé à C jours. »* |
| Aucun risque ne se déclenche | *« Aucun signal d'alerte détecté par les règles simples ; cela ne garantit pas l'absence de risque. »* |

### 3.3 Précautions (`precautions`)

| Déclencheur | Phrase ajoutée |
|---|---|
| `liquidité_générale` non calculée | *« Liquidité générale non calculée : vérifier les actifs et passifs courants. »* |
| `endettement` non calculé | *« Endettement global non calculé : vérifier le total des dettes et les capitaux propres. »* |
| `ROA > 0` et `ROE ≥ 2 × ROA` | *« Le ROE atteint au moins deux fois le ROA. Examiner l'effet de levier et le niveau des capitaux propres. »* |
| `délai clients` connu | *« Délai de recouvrement clients estimé à X jours. Le calcul utilise le chiffre d'affaires total comme approximation. »* |
| `délai fournisseurs` connu | *« Délai fournisseurs estimé à X jours à partir du solde de clôture, et non d'une dette moyenne. »* |
| `rotation_stocks > 0` | *« Rotation des stocks : X fois, soit environ J jours de stock sur la base de 365 jours et du stock moyen initial-final. »* |
| `rotation_stocks ≤ 0` | *« Rotation des stocks nulle ou négative : vérifiez le coût des ventes et le stock moyen. »* |
| `PER` connu | *« PER de X : interprétation à comparer au secteur et aux perspectives de croissance. »* |
| `Dividend Yield` connu | *« Dividend Yield : X %, hors variation du cours et fiscalité. »* |
| Toujours (fin de liste) | *« Seuils du cours : liquidité générale (idéal > 1) et endettement global (> 1 = dépendance élevée). Les autres seuils sont des repères indicatifs hors cours. »* |
| Toujours (dernière entrée) | *« Diagnostic pédagogique indicatif : les seuils varient selon le secteur. Vérifier les données, les unités, les formules du cours et la comparabilité des exercices. »* |

---

## 4. Conclusion globale (dynamique)

Trois branches possibles, choisies en cascade.

### 4.1 Branche « fragile »

Conditions pour tomber dans cette branche (OU logique) :

- capitaux propres `≤ 0`
- résultat net `< 0`
- liquidité générale `< 1`
- endettement global `> 2`
- autonomie financière `< 20 %`

Phrase affichée :

> *« Conclusion : situation financière fragile selon les indicateurs
> disponibles. Des signaux d'alerte touchent la rentabilité, la
> liquidité, les capitaux propres ou le niveau d'endettement. Une
> analyse approfondie est nécessaire. »*

### 4.2 Branche « saine »

Conditions pour tomber dans cette branche (toutes requises) :

- résultat net `> 0`
- liquidité générale `≥ 1`
- liquidité réduite `≥ 1`
- autonomie financière `≥ 50 %`
- `0 ≤ endettement global ≤ 1`
- capitaux propres `> 0`

Phrase affichée :

> *« Conclusion : situation financière globalement saine selon les
> repères utilisés, avec résultat net positif, liquidité suffisante et
> structure de financement relativement équilibrée. Ces indicateurs ne
> garantissent pas l'absence de risque. »*

### 4.3 Branche « intermédiaire »

Si aucune des deux branches précédentes ne s'applique, BilanLens
construit une phrase dynamique composée :

1. Un **qualificatif principal** reliant jusqu'à trois éléments :
   - *rentable* (si `rentabilité_nette > 0`) ou *en perte*
     (si `rentabilité_nette < 0`) ;
   - *liquide à court terme* (si `liquidité générale ≥ 1`) ou
     *en tension de liquidité* (si `liquidité générale < 1`) ;
   - *bénéficiant d'un décalage d'encaissement potentiellement
     favorable* (si délai fournisseurs > délai clients) ou
     *subissant un décalage de trésorerie potentiellement
     défavorable* (si délai fournisseurs < délai clients).
2. Un **détail entre parenthèses** avec `endettement global X` et
   `autonomie Y %` (les deux lorsqu'ils sont disponibles).

Deux variantes selon le niveau d'endettement.

**Avec `endettement global > 1` :**

> *« Conclusion : entreprise {description}, mais dont le financement
> dépend fortement de l'endettement (endettement global X ; autonomie
> Y %). La structure financière mérite une surveillance
> particulière. »*

**Sinon :**

> *« Conclusion : entreprise {description} (endettement global X ;
> autonomie Y %). La situation paraît intermédiaire selon les repères
> retenus ; les résultats doivent être comparés à ceux du secteur et
> aux exercices précédents. »*

Si aucun des éléments de la description ne se déclenche, la phrase
tombe sur *« difficile à qualifier avec les données disponibles »*.

---

## 5. Alignement sur la fiche de cours

- Les 12 ratios, leurs familles et leurs noms suivent exactement la
  fiche *Master Data Science – Analyse Financière*.
- Les seuils du cours (liquidité générale > 1 ; endettement global > 1
  = dépendance élevée) sont utilisés **tels quels** dans les phrases
  d'interprétation et dans le diagnostic.
- Pour les ratios sans seuil chiffré dans la fiche de cours (autonomie
  financière, rentabilités, activité, marché), BilanLens affiche des
  repères indicatifs mais la mention centralisée rappelle qu'ils ne
  viennent pas du cours.
- Autonomie financière : BilanLens utilise *Capitaux propres / Total
  passif* conformément à la fiche. Si le total passif n'est pas
  disponible, il est remplacé par le total actif (équivalent par
  équilibre du bilan) et la note du ratio le signale.

---

## 6. Où retrouver chaque texte dans le code

| Ce qui est produit | Fonction / constante |
|---|---|
| Les 12 ratios et leurs notes | `calculer_ratios(valeurs)` |
| La reconstitution de `total_passif` et des sous-totaux | `completer_valeurs_financieres(valeurs)` |
| Les phrases d'interprétation par ratio | `interpreter_ratio(cle, valeur, tous_les_ratios)` |
| Les listes du diagnostic et la conclusion | `construire_diagnostic(valeurs, ratios)` |
| Le format français (virgule décimale) | `nombre_fr(valeur, decimales)` |
| Le format d'un ratio (pourcentage / multiple / jours) | `formater_ratio(ratio)` |
| La mention centralisée des seuils du cours | `NOTE_SEUILS_COURS` |

Tout est dans `bilanlens/analysis.py`.
