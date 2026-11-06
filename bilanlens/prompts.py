"""Prompts partages B0 (sans contexte) et V1 (avec contexte RAG).

Architecture :
- `SYSTEM_INSTRUCTION` : les regles communes (JSON de sortie,
  "donnee non disponible", pas de disclaimers, pas d'approximation).
  Passe en `system_instruction` cote Gemini : B0 et V1 l'utilisent
  **tel quel**.
- `TEMPLATE_B0_USER` : le prompt utilisateur B0. Pas de contexte,
  juste la question.
- `TEMPLATE_V1_USER` : le prompt utilisateur V1. Contexte RAG avant
  la question.
- `JSON_SCHEMA_REPONSE` : force `response_mime_type="application/json"`
  cote API pour minimiser les `parse_ok=False`.

`prompt_version_b0()` / `prompt_version_v1()` : hash court
(`sha256(system + "||" + user_template)[:16]`) enregistre dans chaque
ligne de `results/*.jsonl`. Toute modification des regles OU du
template utilisateur invalide le checkpoint sur les anciens runs.

Pourquoi hasher la TEMPLATE et pas le prompt rendu : la template ne
depend ni de la question ni du contexte. Deux questions differentes
sous les memes regles partagent donc le meme `prompt_version`.
"""
from __future__ import annotations

import hashlib


# Regles communes B0 (strict, default) / V1. Passe en `system_instruction`.
# "Strict" : abstention imperative au moindre doute. Produit un plancher
# conservateur (voir journal 2026-11-01 : 100 % d'abstention observee).
#
# Le texte **ne mentionne plus** le nombre de cles de sortie : le schema
# JSON (`response_schema` cote API) impose les champs. Mentionner un
# nombre fixe ici obligerait a reecrire le prompt chaque fois qu'on
# ajoute un champ (ex. `cited_extraits` en V1).
SYSTEM_INSTRUCTION = """Tu es un assistant financier. Tu reponds a UNE question sur un
rapport annuel d'une societe cotee a la BVMT (Bourse de Tunis).

Regles strictes :
- Si tu connais la valeur, reponds en une phrase courte avec la
  valeur et son unite (ex. "100 836 224 TND", "34,53 %",
  "diminution de 24 287 937 TND entre 2023 et 2024").
- Si tu ne connais pas la valeur, ou si elle n'est pas publique, ou
  si tu as un doute, reponds EXACTEMENT : "donnee non disponible".
- Ne calcule rien d'approximatif. Pas d'intervalle, pas de "environ".
- Pas de disclaimers, pas de reformulation de la question.

Sortie : un objet JSON dont la structure est imposee par le schema
de reponse. Reponds uniquement avec ce JSON, sans texte autour.""".strip()


# B0-LIBRE : variante DIAGNOSTIQUE. Pas de consigne d'abstention. Permet
# de mesurer la propension du LLM a inventer (hallucination) quand il
# n'a pas acces aux rapports.
#
# **A n'utiliser QUE pour cette variante B0-libre, JAMAIS pour V1.**
# V1 doit rester sous `SYSTEM_INSTRUCTION` (strict) pour que la
# difference B0-strict vs V1 mesure l'effet du RAG, pas un changement
# de consigne.
SYSTEM_INSTRUCTION_B0_LIBRE = """Tu es un assistant financier. Tu reponds a UNE question sur un
rapport annuel d'une societe cotee a la BVMT (Bourse de Tunis).

Donne la meilleure reponse que tu peux avec les informations a ta
disposition. Reponds en une phrase courte avec la valeur et son
unite (ex. "100 836 224 TND", "34,53 %", "diminution de 24 287 937
TND entre 2023 et 2024").

Sortie : un objet JSON dont la structure est imposee par le schema
de reponse. Reponds uniquement avec ce JSON, sans texte autour.""".strip()


# B0 : prompt utilisateur = juste la question. Pas de contexte.
# PARTAGE entre B0-strict et B0-libre : seul le prompt systeme change.
TEMPLATE_B0_USER = "Question :\n{question}"

# V1 : prompt utilisateur = contexte RAG + question + consigne de
# citation. L'ordre contexte-avant-question est delibere : le modele
# voit la matiere avant la demande, comme dans un examen. La consigne
# de citation est placee ici (template V1) et PAS dans
# `SYSTEM_INSTRUCTION`, pour que B0 reste strictement comparable
# a V1 sur `answer` + `confidence`.
TEMPLATE_V1_USER = (
    "Contexte (extraits du rapport annuel) :\n{context}"
    "\n\nQuestion :\n{question}"
    "\n\nDans le champ cited_extraits du JSON, liste les numeros "
    "d'extraits (1, 2, 3, ...) que tu as reellement utilises pour "
    "construire ta reponse. Liste vide [] si aucun extrait n'a servi."
)


# Schema de reponse B0 pour `response_mime_type="application/json"` cote
# Gemini. Les cles JSON Schema supportees par le SDK Gemini sont un
# sous-ensemble (type, properties, required, enum, propertyOrdering) :
# pas de $schema, pas de additionalProperties.
JSON_SCHEMA_REPONSE = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low", "unknown"],
        },
    },
    "required": ["answer", "confidence"],
    "propertyOrdering": ["answer", "confidence"],
}


# Schema de reponse V1 : B0 + `cited_extraits` (liste d'entiers,
# positions 1-based des extraits du contexte RAG reellement utilises
# pour construire la reponse). Pas de pages absolues (page 4 est
# ambigu quand les extraits viennent de plusieurs entreprises) : on
# cite par POSITION dans la liste de contexte ; la correspondance
# (doc, page_physique, chunk_id) vit cote results/*.jsonl via le
# champ `retrieved`.
JSON_SCHEMA_REPONSE_V1 = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low", "unknown"],
        },
        "cited_extraits": {
            "type": "array",
            "items": {"type": "integer"},
        },
    },
    "required": ["answer", "confidence", "cited_extraits"],
    "propertyOrdering": ["answer", "confidence", "cited_extraits"],
}


def hash_prompt(system: str, template_user: str) -> str:
    """SHA-256 (16 hex) de `system + "||" + template_user`. Determine
    le `prompt_version` enregistre dans chaque ligne de results/*.jsonl.
    """
    h = hashlib.sha256()
    h.update(system.encode("utf-8"))
    h.update(b"||")
    h.update(template_user.encode("utf-8"))
    return h.hexdigest()[:16]


def prompt_version_b0() -> str:
    """Hash du prompt B0-strict (regles communes + template B0).
    Alias de `prompt_version_b0_strict()` pour backward compat."""
    return hash_prompt(SYSTEM_INSTRUCTION, TEMPLATE_B0_USER)


def prompt_version_b0_strict() -> str:
    """Hash du prompt B0-strict. Explicite ; prefere a `prompt_version_b0()`
    quand on veut distinguer B0-strict de B0-libre dans le code."""
    return hash_prompt(SYSTEM_INSTRUCTION, TEMPLATE_B0_USER)


def prompt_version_b0_libre() -> str:
    """Hash du prompt B0-libre (variante diagnostique, sans abstention).
    DIFFERENT de `prompt_version_b0_strict()` : garantit que B0-strict
    et B0-libre vivent sous des run_id distincts dans results/b0.jsonl."""
    return hash_prompt(SYSTEM_INSTRUCTION_B0_LIBRE, TEMPLATE_B0_USER)


def prompt_version_v1() -> str:
    """Hash du prompt V1 (regles communes B0-strict + template V1
    avec contexte). V1 n'herite PAS de B0-libre : la variante libre
    reste cantonnee a la mesure d'hallucination."""
    return hash_prompt(SYSTEM_INSTRUCTION, TEMPLATE_V1_USER)


# V1.1 : variante de V1 qui ajoute UNE consigne au TEMPLATE USER,
# sans toucher a SYSTEM_INSTRUCTION. Cible les abstentions a tort
# sur les calculs (6 Q en V1 : Q02, Q06, Q14, Q19, Q23, Q28, toutes
# calculs). Le prompt systeme reste byte-a-byte identique a
# B0-strict pour preserver la paire de comparaison.
#
# Pas de nouveau champ dans le schema JSON (le answer contient
# juste la valeur finale + unite).
TEMPLATE_V1_1_USER = (
    "Contexte (extraits du rapport annuel) :\n{context}"
    "\n\nQuestion :\n{question}"
    "\n\nSi la question demande un calcul et que toutes les valeurs "
    "necessaires figurent dans les extraits, fais le calcul exact. "
    "Dans le champ answer, donne uniquement le resultat final avec "
    "son unite. Reponds \"donnee non disponible\" seulement s'il "
    "manque une valeur necessaire."
    "\n\nDans le champ cited_extraits du JSON, liste les numeros "
    "d'extraits (1, 2, 3, ...) que tu as reellement utilises pour "
    "construire ta reponse. Liste vide [] si aucun extrait n'a servi."
)


def prompt_version_v1_1() -> str:
    """Hash du prompt V1.1 (SYSTEM_INSTRUCTION identique a V1 +
    TEMPLATE_V1_1_USER). DIFFERENT de prompt_version_v1() : garantit
    que V1 et V1.1 vivent sous des run_id distincts et ne se
    melangent pas dans results/."""
    return hash_prompt(SYSTEM_INSTRUCTION, TEMPLATE_V1_1_USER)


# V1.2 : variante de V1.1 avec deux regles supplementaires issues de
# l'analyse post-hoc des erreurs V1.1 (Q02/Q10/Q19 confondant "Total
# passif" avec "Total des passifs" ; Q07 perdant la direction de la
# variation). Ces deux regles sont donc **adaptees au benchmark
# actuel** : leur generalisation doit etre verifiee sur un benchmark
# neuf avant toute conclusion.
#
# SYSTEM_INSTRUCTION reste byte-a-byte identique a V1 et B0-strict.
# Le schema JSON (JSON_SCHEMA_REPONSE_V1) est inchange : pas de
# nouveau champ.
TEMPLATE_V1_2_USER = (
    "Contexte (extraits du rapport annuel) :\n{context}"
    "\n\nQuestion :\n{question}"
    "\n\nSi la question demande un calcul et que toutes les valeurs "
    "necessaires figurent dans les extraits, fais le calcul exact. "
    "Dans le champ answer, donne uniquement le resultat final avec "
    "son unite. Reponds \"donnee non disponible\" seulement s'il "
    "manque une valeur necessaire."
    "\n\nDans une formule d'autonomie financiere, le total passif "
    "designe le total des capitaux propres et des passifs (total "
    "du bilan)."
    "\n\nPour une variation ou une comparaison, indique aussi le "
    "sens (augmentation ou diminution)."
    "\n\nDans le champ cited_extraits du JSON, liste les numeros "
    "d'extraits (1, 2, 3, ...) que tu as reellement utilises pour "
    "construire ta reponse. Liste vide [] si aucun extrait n'a servi."
)


def prompt_version_v1_2() -> str:
    """Hash du prompt V1.2 (SYSTEM_INSTRUCTION identique a V1 +
    TEMPLATE_V1_2_USER). Distinct des versions precedentes."""
    return hash_prompt(SYSTEM_INSTRUCTION, TEMPLATE_V1_2_USER)
