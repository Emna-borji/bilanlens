# BilanLens — Analyste financier IA (RAG agentique)

*Oct 7, 2026 · @Ayman borji*

> Planning original rédigé pour un projet RAG sur rapports SEC
> (FinanceBench). Adapté à **BilanLens** avec les rapports annuels de la
> **BVMT** comme corpus principal — voir la section « Adaptation
> BilanLens / BVMT » en bas pour les écarts et les choix spécifiques.

## Résumé

**BilanLens** devient un système RAG agentique pour l'analyse financière,
conçu pour améliorer pas à pas la fiabilité des réponses sur les rapports
financiers annuels d'émetteurs cotés à la **BVMT**. Chaque composant
(recherche hybride, reranking, tableaux structurés, agent de calcul, puis
en bonus un petit LLM fine-tuné pour le text-to-SQL) n'est gardé que si
son gain est mesuré sur un **benchmark Q/A maison** de 30 questions au
départ, extensible à 100-150 à terme.

**Type** : projet personnel (portfolio)
**Durée** : 8 semaines pour le cœur + 3 semaines bonus (fine-tuning)
**Domaine** : LLM, RAG agentique, fine-tuning, finance

## Contexte et problématique

Les analystes financiers passent des heures à chercher des chiffres dans
des rapports de 100 à 300 pages. Les LLM promettent d'accélérer ce
travail, mais ils se trompent souvent sur les chiffres et les calculs.

Dans l'étude FinanceBench (Patronus AI, Contextual AI, Stanford, 2023),
GPT-4-Turbo avec un système de recherche s'est trompé ou a refusé de
répondre sur 81 % de l'échantillon testé.

**Problématique** : comment construire un système de questions-réponses
financières fiable, qui retrouve la bonne information (texte et
tableaux), calcule juste et cite ses sources ?

## Objectifs

1. Construire un pipeline d'ingestion qui extrait le texte **et les
   tableaux** des rapports PDF.
2. Développer un RAG avancé : recherche hybride, reranking et filtrage
   par entreprise et par année.
3. Ajouter un agent capable de calculer des ratios financiers avec des
   outils Python, pas avec le LLM.
4. En bonus : fine-tuner un petit LLM open-source (QLoRA) pour traduire
   les questions en requêtes SQL sur une base des chiffres extraits.
5. Mesurer chaque amélioration sur un **benchmark Q/A BVMT maison** et
   montrer le gain par rapport à une baseline RAG simple.
6. Livrer une démo web publique et un dépôt GitHub documenté.

## Données et sources

Le **corpus de départ** est constitué des rapports annuels 2024 déjà
récupérés dans `tests/data/` (SOTUVER, Monoprix individuel et consolidé,
SFBT, Ciments de Bizerte, Délice Holding), publiés par la **BVMT**. Le
**corpus cible** vise 20 à 30 émetteurs non financiers de la BVMT, sur
deux ou trois exercices quand les documents sont disponibles. Tout est
public et téléchargeable sur [bvmt.com.tn](https://www.bvmt.com.tn/).

| Source | Contenu | Usage |
|---|---|---|
| BVMT (`tests/data/real_*.pdf`) | 6 rapports annuels 2024, états financiers individuels ou consolidés avec notes annexes | Corpus initial validé |
| BVMT (bvmt.com.tn) | Rapports annuels et semestriels de tous les émetteurs cotés | Extension à 20-30 sociétés, 2-3 exercices |
| FinanceBench (GitHub / HF, arXiv 2311.11944) | 150 Q/A annotées sur rapports SEC en anglais | Référence méthodologique seulement, pas utilisé comme corpus |

Référentiel comptable des rapports BVMT : **Système Comptable des
Entreprises (SCE)**, régi par la loi 96-112 du 30/12/1996 et les
**normes comptables tunisiennes (NCT 1 à 46)**.

Les émetteurs du secteur **bancaire** et du secteur de l'**assurance**
sont **hors périmètre** (bilan structurellement différent, 12 ratios
non pertinents) et déjà détectés par règles dans `bilanlens/sector.py`.

Le **benchmark d'évaluation** est un jeu Q/A **maison**, construit à la
main à partir du corpus initial. Il compte **30 questions annotées** au
départ et vise **100 à 150 questions** à terme, réparties en cinq
catégories :

1. **Extraction** : récupérer une donnée du bilan ou de l'état de
   résultat (ex. résultat net de SOTUVER en 2024).
2. **Calcul** : calculer un ratio à partir de données vérifiées
   (ex. autonomie financière de la SFBT en 2024).
3. **Comparaison** : entre plusieurs années ou plusieurs entreprises
   (ex. croissance du CA de Monoprix 2023 vs 2024).
4. **Texte annexes** : question portant sur les notes annexes
   (ex. méthode d'amortissement des immobilisations incorporelles).
5. **Sans réponse disponible** : question dont la réponse n'est **pas**
   dans le corpus. L'agent doit **refuser de spéculer** et dire que
   la preuve n'est pas disponible.

Chaque question est annotée, lorsque c'est applicable, avec la réponse
attendue, le document source, la **page physique du PDF** (celle rendue
par pdfplumber, 1-indexée) et la **page imprimée** (celle imprimée sur
la feuille, si elle existe et peut différer de la physique), et un
extrait justificatif.

**Avertissement.** Avec 6 à 10 émetteurs et 30 questions au départ,
les mesures ont une **portée statistique faible**. Les scores
rapportés sont des **indicateurs de tendance**, pas des mesures de
performance absolue. Cette limite est à documenter explicitement
dans le README et dans tout partage du projet.

## Fonctionnalités

- **Questions en langage naturel** : « Quelle était la rentabilité
  nette de la SFBT en 2024 ? »
- **Réponses traçables** : les réponses s'appuient sur les passages ou
  tableaux retrouvés, avec le document et la page quand l'information
  est disponible.
- **Calculs fiables** : ratios, croissances et moyennes calculés par un
  outil Python, avec la formule affichée.
- **Lecture des tableaux** : les tableaux financiers (compte de résultat,
  bilan) sont extraits et interrogeables.
- **Requêtes SQL (bonus)** : pour certaines questions chiffrées, un
  modèle fine-tuné peut générer une requête SQL sur la base structurée,
  l'exécute et affiche la requête.
- **Comparaisons** : entre deux années ou deux entreprises du corpus.
- **Refus honnête** : si l'information n'est pas dans les documents,
  l'agent le dit au lieu d'inventer.
- **Tableau de bord d'évaluation** : scores de chaque version du système
  sur FinanceBench.

## Architecture et stack technique

> L'agent cherche dans l'index et calcule en Python, pas avec le LLM.
> Les rapports sont indexés une seule fois ; à chaque question, l'agent
> choisit entre chercher des passages et appeler l'outil de calcul.

**HORS LIGNE — ingestion des rapports** : Rapports PDF → Parsing texte +
tableaux → Découpage + métadonnées → Index hybride Chroma + BM25.

**EN LIGNE — question vers réponse** : Question → Agent routeur
(LangGraph) → Recherche hybride + filtres → Reranker → Réponse citée
(LLM + sources). En parallèle, l'agent peut appeler l'outil de calcul
Python (ratios) et combiner ses résultats dans la réponse.

| Brique | Outils (tous gratuits) |
|---|---|
| Parsing PDF et tableaux | Docling |
| Embeddings | bge-m3 (local) |
| Base vectorielle + BM25 | Chroma (recherche hybride) |
| Reranker | bge-reranker (local) |
| LLM | Ollama (Qwen ou Llama) |
| Agent | LangGraph, en version simple à partir de V5 |
| Évaluation | Script Python (métriques déterministes) + LLM-juge secondaire |
| Produit | FastAPI, Streamlit, Docker ; démo légère en ligne, système complet en local, vidéo |
| Bonus fine-tuning | Unsloth + QLoRA (Colab ou Kaggle), SQLite |

**Règle** : un outil n'entre dans la stack que si une mesure montre
qu'il améliore le score.

**Représentation des tableaux (V4).** Chaque ligne de tableau devient un
enregistrement structuré, pas un bloc de texte : `entreprise`,
`indicateur`, `année`, `valeur`, `unité`, `document`, `page`,
`table_id`. Ces enregistrements sont indexés pour la recherche et
serviront directement de base SQL en V6.

**Outils de l'agent (V5).** Le LLM décide, les outils exécutent :

- `retrieve_documents(question, entreprise, année)` : renvoie des
  passages et des lignes de tableaux, avec leur source.
- `calculator(expression)` : calcul exact en Python (ratios, croissances,
  moyennes).
- `query_sql(question)` (bonus V6) : requête générée par le modèle
  fine-tuné, puis exécutée.

Exemple : « Marge opérationnelle de l'entreprise X en 2022 ? » →
`retrieve_documents` (résultat opérationnel, chiffre d'affaires) →
`calculator` → réponse avec la formule, le résultat et les pages.

## Méthodologie d'évaluation

On améliore le système une étape à la fois et on mesure le gain de
chaque étape sur le **benchmark Q/A BVMT** (30 questions au départ, 100
à 150 à terme). Le projet est réussi dès V5 ; V6 est un bonus.

| Version | Ajout testé |
|---|---|
| B0 (référence) | LLM seul, sans documents : ce que le modèle sait sans nos données |
| V1 | RAG simple : découpage fixe + recherche vectorielle |
| V2 | Recherche hybride (BM25 + vecteurs) et filtrage par entreprise/année |
| V3 | + reranker |
| V4 | RAG qui exploite les tableaux structurés |
| V5 | RAG agentique + outil de calcul |
| V6 (bonus) | + outil text-to-SQL fine-tuné |

### Métriques

- **B0 (LLM seul, pas de recherche)** : évalué sur la qualité des
  réponses et le **taux d'hallucinations**. Pas de Recall@k ni de MRR
  (il n'y a rien à retrouver).
- **V1 et au-delà (recherche)** : **Recall@k** et **MRR** sur la page
  physique de l'extrait justificatif. On ajoute **nDCG** pour comparer
  le classement complet. Un passage est jugé pertinent s'il provient
  de la bonne page de la bonne entreprise sur la bonne année.
- **Exactitude numérique (toutes versions ≥ V1)** : tolérance
  configurable (par ex. 1 % pour un pourcentage, 0,1 % pour une valeur
  brute, exact pour un montant copié verbatim). Les calculs sont
  toujours vérifiés en Python, jamais produits par le LLM.
- **Qualité des citations** : la réponse cite-t-elle au moins une
  source réellement présente dans le corpus ? Mesurée **séparément**.
- **Comportement sur les questions sans réponse** (catégorie 5) :
  taux de refus honnête vs taux d'invention. Mesuré **séparément**.
- **Réponses textuelles (secondaire)** : LLM-juge, vérifié à la main
  sur un sous-échantillon.
- **Coût et latence** par question.

L'analyse d'erreurs par type de question (métier, généré, métrique) fait
partie du livrable.

**Pièce maîtresse du portfolio** : un graphique Recall@5, MRR et
exactitude numérique pour chaque version, de B0 à V5.

## Planning sur 8 semaines

> Environ 8 à 10 heures par semaine, en parallèle des cours.

1. **Semaine 1 — Benchmark et protocole.** Construire les 30 premières
   questions Q/A annotées à partir des 6 PDF BVMT déjà présents, dans
   les cinq catégories (extraction, calcul, comparaison, texte annexes,
   sans réponse). Vérifier l'extraction `extraction.py` + `mapping.py`
   sur un échantillon. Écrire le protocole d'évaluation. Livrable :
   `data/benchmark/questions.jsonl` + protocole.
2. **Semaine 2 — Baselines.** B0 (LLM seul) et V1 (RAG simple) + le
   script d'évaluation automatique. Livrable : premiers scores.
3. **Semaine 3 — Recherche.** V2 (hybride + métadonnées) et V3
   (reranker).
4. **Semaine 4 — Tableaux.** Extraction des tableaux en enregistrements
   structurés et indexation (V4).
5. **Semaine 5 — Agent.** Outils `retrieve_documents` et `calculator`,
   routage avec LangGraph (V5).
6. **Semaine 6 — Stabilisation.** Tests de bout en bout, analyse
   d'erreurs, optimisation, graphique de fiabilité par version.
7. **Semaine 7 — Produit.** API FastAPI, interface Streamlit, Docker ;
   version légère en ligne.
8. **Semaine 8 — Valorisation.** README avec architecture et résultats,
   vidéo de démo de 2 minutes du système complet, post LinkedIn.

## Phase 2 (bonus) : fine-tuning text-to-SQL (semaines 9 à 11)

Cette phase est un bonus : le projet est déjà complet à la version V5.
Le modèle fine-tuné devient un nouvel outil de l'agent : il traduit les
questions chiffrées en requêtes SQL sur une base construite à partir des
tableaux extraits en phase 1.

### Données d'entraînement

- **BIRD** et **Spider** : benchmarks publics de paires question → SQL,
  pour apprendre la tâche en général.
- **300 à 500 paires maison** sur ton propre schéma (entreprise, année,
  indicateur, valeur), générées par un LLM local puis **validées en
  exécutant le SQL**.

### Modèle et méthode

- Un petit modèle open-source de 1 à 3 milliards de paramètres, orienté
  code.
- QLoRA avec Unsloth, sur GPU gratuit (Colab ou Kaggle).

### Évaluation

- **Exactitude d'exécution** : le résultat du SQL généré est-il le bon ?
  Comparaison modèle de base vs modèle fine-tuné, sur des questions
  jamais vues.
- **Impact sur FinanceBench (V6)** : gain sur les questions de type
  métrique.

### Planning

9. **Semaine 9 — Base et données.** Construire la base SQLite des
   chiffres extraits et le jeu de paires question → SQL.
10. **Semaine 10 — Fine-tuning.** Entraînement QLoRA, comparaison
    avant/après.
11. **Semaine 11 — Intégration.** Brancher le modèle comme outil de
    l'agent, évaluer V6, mettre à jour le README.

## Livrables, ligne CV et risques

### Livrables

- [ ] Dépôt GitHub propre (code, README, schéma d'architecture,
      protocole et résultats)
- [ ] Graphique de fiabilité B0 à V5 + analyse d'erreurs
- [ ] Système complet exécutable en local (Docker)
- [ ] Démo légère en ligne
- [ ] Vidéo de démo de 2 minutes du système complet

### Ligne CV

> Conception d'un système RAG agentique pour l'analyse de rapports
> financiers d'émetteurs cotés à la BVMT (Système Comptable des
> Entreprises tunisien) : recherche hybride, reranking, extraction de
> tableaux structurés, agent de calcul en Python ; en bonus, LLM
> fine-tuné en QLoRA pour le text-to-SQL. Exactitude portée de X % à
> Y % sur un benchmark Q/A maison par rapport à une baseline RAG.
> Déploiement Docker et démo publique.

### Risques et parades

| Risque | Parade |
|---|---|
| Tableaux PDF mal extraits | `extraction.py` + `mapping.py` déjà testés sur 6 bilans BVMT ; Docling essayé seulement si V4 déçoit |
| Petit corpus initial (6 sociétés, 30 questions) | Documenter la limite statistique dans le README ; viser 20-30 sociétés et 100-150 Q/A à terme |
| Benchmark construit sur le même corpus que l'index | Marquer les questions à risque de fuite ; évaluer séparément |
| Coût des appels LLM | Modèles open-source via Ollama en local pour la mesure finale ; API gratuite (Groq, Gemini Flash) pour prototyper et comparer |
| Fine-tuning V6 long sur CPU | Phase 2 obligatoirement sur Colab/Kaggle GPU gratuit ; le projet reste complet à V5 |
| Quota GPU gratuit limité | Petit modèle (1 à 3 milliards de paramètres), QLoRA, sessions courtes sur Colab et Kaggle |

### Sources

- BVMT (bvmt.com.tn) : rapports annuels des émetteurs cotés
- Référentiel comptable : loi 96-112 du 30/12/1996 relative au
  Système Comptable des Entreprises et normes comptables tunisiennes
  (NCT 1 à 46)
- FinanceBench (GitHub, Patronus AI, arXiv 2311.11944) : référence
  méthodologique seulement
- BIRD, Spider : benchmarks text-to-SQL (phase 2 bonus)
- Unsloth (fine-tuning QLoRA)

---

## Adaptation BilanLens / BVMT

Cette section regroupe les écarts par rapport au planning original et
les choix spécifiques au contexte BilanLens / BVMT. Chaque point est
validé par observation du dépôt courant (fichiers, tests) et par
vérification matérielle de la machine de développement.

### 1. Référentiel comptable et corpus

Les rapports du corpus sont régis par le **Système Comptable des
Entreprises (SCE)** tunisien et par les **normes comptables tunisiennes
(NCT 1 à 46)**, cadre juridique : loi 96-112 du 30/12/1996 et décret
96-2459. Preuves textuelles extraites des PDF : « Système Comptable
des Entreprises » cité dans SFBT (p.6-7) et SOTUVER (p.7), « normes
comptables tunisiennes » cité dans SOTUVER (p.7) et Délice Holding
(p.6), NCT 5 et NCT 6 cités dans SOTUVER (p.8).

L'appellation « SCF tunisien » qui apparaissait dans BilanLens était
un abus de langage : **SCF** (Système Comptable Financier) désigne le
référentiel **algérien** (loi 07-11 de 2007). Le lot A corrige cette
appellation partout dans le code et la documentation sans toucher aux
alias, constantes ou valeurs de test.

Les banques et compagnies d'assurance de la BVMT sont **hors
périmètre** (bilan structurellement différent) et déjà détectées par
règles dans `bilanlens/sector.py`.

### 2. Benchmark Q/A en cinq catégories

Jeu Q/A maison, stocké dans `data/benchmark/questions.jsonl` au format
compatible FinanceBench, avec les champs :

- `question` : énoncé en français ;
- `answer` : réponse attendue (quand elle existe) ;
- `category` : extraction / calcul / comparaison / texte_annexes / sans_reponse ;
- `evidence_doc` : nom du PDF source ;
- `evidence_page_physical` : page physique rendue par pdfplumber (1-indexée) ;
- `evidence_page_printed` : page imprimée telle qu'elle figure dans le PDF (si différente) ;
- `evidence_text` : extrait justificatif copié du PDF.

Cible : **30 questions au départ**, puis **100 à 150 à terme**. La
répartition entre catégories sera décidée après examen des 6 PDF du
corpus initial, sans fixer d'avance de proportions arbitraires.

Précaution : marquer les questions dont la réponse apparaît aussi dans
les chunks utilisés pour construire le prompt (**risque de fuite**).

### 3. Métriques par étape

| Version | Métriques principales | Métriques secondaires |
|---|---|---|
| B0 (LLM seul) | Qualité des réponses (LLM-juge + revue manuelle), taux d'hallucinations | Latence par question |
| V1 à V5 | Recall@k, MRR, **nDCG**, exactitude numérique, qualité des citations, comportement sur les questions sans réponse | LLM-juge, latence, coût |

Exactitude numérique, qualité des citations et refus honnête sont
**mesurés séparément** : un bon score sur l'un ne couvre pas les deux
autres.

### 4. Modèles candidats compte tenu de la machine

Machine de développement vérifiée en session : Intel Core i7-1270P,
16 GB RAM (~3,4 GB libres à la mesure), GPU intégré Intel Iris Xe
(pas de carte NVIDIA, pas de CUDA, `nvidia-smi` absent).

| Rôle | Candidats | Taille Q4 approx. | Verdict machine |
|---|---|---|---|
| Embeddings | `bge-m3` (BAAI, multilingue, 568 M) | ~1,2 GB | ✅ |
| Reranker | `bge-reranker-v2-m3` (568 M, multilingue) | ~1,2 GB | ✅ |
| LLM local (défaut) | Qwen 3 1.7B / Qwen 3 4B-instruct, Phi-4-mini (3,8 B) | 1,0 - 2,5 GB | ✅ (10-20 tok/s CPU) |
| LLM local (optionnel) | Qwen 3 8B, Llama 3.1 8B-instruct, Mistral 7B | 4,5 - 5 GB | ⚠️ (3-6 tok/s, RAM tendue) |
| LLM local (gros) | 13 B et plus | ≥ 8 GB | ❌ RAM insuffisante |
| LLM API gratuite | Groq (GPT-OSS 20B/120B, Qwen3 27B — rate limits par modèle), Google Gemini 2.5 Flash (free tier limité ~5-10 RPM, 100-250 RPD, 1 M tokens contexte), Mistral Experiment (~1 B tokens/mois à confirmer), OpenRouter (free routing variable) | - | ✅ pour prototyper et comparer |

**Vérifier les tags disponibles au moment de l'installation.** Les
versions sur Ollama et Hugging Face évoluent vite ; les candidats
ci-dessus (Qwen 3, Phi-4-mini) sont les versions disponibles en
octobre 2026 mais peuvent être remplacés par de nouvelles releases.
Pour les API gratuites, consulter la page officielle de rate limits
de chaque fournisseur avant intégration — plusieurs ont changé leurs
quotas en 2026 (notamment Gemini au 1er avril 2026).

**Protocole d'évaluation à deux voies.** Pour chaque version du
système, mesurer avec (a) le LLM local par défaut et (b) une API
gratuite comme point de comparaison. Cela sépare l'effet du pipeline
RAG de celui de la puissance brute du LLM.

### 5. Réutilisation du code existant

- `bilanlens/extraction.py` : lecture des PDF, OCR optionnel, détection
  du séparateur décimal. **Déjà testé sur 6 PDF BVMT réels** (voir
  `tests/test_real_bilans.py`).
- `bilanlens/mapping.py` : alias et rang des postes comptables.
  **Déjà testé** (voir `tests/test_synthetic_bilans.py` et
  `tests/test_fixtures_resultats.py`).
- `bilanlens/analysis.py:calculer_ratios` : calcul des **12 ratios du
  cours**. **Déjà testé.** Devient l'outil `calculator` de l'agent
  LangGraph en V5, après ajout d'une validation des entrées, de la
  gestion des valeurs manquantes et des cas limites (division par zéro,
  dénominateurs négatifs).
- `bilanlens/consistency.py` et `bilanlens/sector.py` : garde-fous à
  conserver et à exposer dans les réponses du système (cohérence du
  bilan, détection banque/assurance hors périmètre).

### 6. Garde-fous V4 (tableaux structurés)

Chaque ligne de tableau devient un enregistrement, par exemple :

```
{
  "entreprise": "sotuver",
  "indicateur": "resultat_net",
  "annee": 2024,
  "valeur": -1234567.89,
  "unite": "TND",
  "document": "real_sotuver_2024.pdf",
  "page_physique": 12,
  "page_imprimee": "10",
  "table_id": "bilan_actif_passif"
}
```

Tests à prévoir en V4 (en plus des tests actuels) :

- nombres **négatifs** (ex. résultat net Ciments de Bizerte 2024) ;
- **séparateurs décimaux** mélangés (SFBT : « 1 281 772 854,965 ») ;
- montants exprimés en **milliers** ou en **millions** (lire la note
  d'unité en haut de la page du bilan) ;
- **comptes consolidés** vs **individuels** (Monoprix : les deux
  versions coexistent dans `tests/data/`) ;
- doublons entreprise-indicateur-année (une seule valeur par triplet).

### 7. Fine-tuning V6 : conditionnel et gelé jusqu'à V5

La phase 2 (text-to-SQL fine-tuné) **n'est pas démarrée** tant que V5
n'a pas été construit et évalué sur le benchmark. Si V5 atteint
l'objectif, V6 reste optionnel ; sinon, V6 est reporté. QLoRA +
Unsloth sur Colab/Kaggle (GPU T4 gratuit) : **impossible sur la
machine locale** (pas de GPU CUDA).

Jeu de paires question → SQL : **300 à 500 paires maison** sur le
schéma `metrique(entreprise, annee, indicateur, valeur, unite,
source_doc, source_page_physique, source_page_imprimee)`. BIRD et
Spider servent de référence méthodologique seulement ; les paires
d'entraînement sont **en français** sur des données BVMT.
