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


# Regles communes B0 / V1. Passe en `system_instruction`.
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

Sortie : UN seul objet JSON avec DEUX cles :
  "answer" (string) : ta reponse selon les regles ci-dessus.
  "confidence" (string) : "high", "medium", "low" ou "unknown".""".strip()


# B0 : prompt utilisateur = juste la question. Pas de contexte.
TEMPLATE_B0_USER = "Question :\n{question}"

# V1 : prompt utilisateur = contexte RAG puis question. L'ordre
# contexte-avant-question est delibere : le modele voit la matiere
# avant la demande, comme dans un examen.
TEMPLATE_V1_USER = (
    "Contexte (extraits du rapport annuel) :\n{context}"
    "\n\nQuestion :\n{question}"
)


# Schema de reponse pour `response_mime_type="application/json"` cote
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
    """Hash du prompt B0 (regles communes + template B0)."""
    return hash_prompt(SYSTEM_INSTRUCTION, TEMPLATE_B0_USER)


def prompt_version_v1() -> str:
    """Hash du prompt V1 (regles communes + template V1 avec contexte)."""
    return hash_prompt(SYSTEM_INSTRUCTION, TEMPLATE_V1_USER)
