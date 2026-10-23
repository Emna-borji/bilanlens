"""Génère tests/data/synth_excel_multisheet.xlsx (bilan + résultat).

Script non packagé : exécuter manuellement si on change le contenu.
"""
from pathlib import Path

import pandas as pd


REPERTOIRE_DONNEES = Path(__file__).resolve().parent.parent / "tests" / "data"
SORTIE = REPERTOIRE_DONNEES / "synth_excel_multisheet.xlsx"


def main():
    bilan = pd.DataFrame(
        [
            {
                "Poste": "Actifs non courants",
                "31/12/2025": "4 000",
                "31/12/2024": "3 800",
            },
            {
                "Poste": "Stocks",
                "31/12/2025": "1 200",
                "31/12/2024": "1 100",
            },
            {
                "Poste": "Créances clients",
                "31/12/2025": "1 500",
                "31/12/2024": "1 400",
            },
            {
                "Poste": "Trésorerie",
                "31/12/2025": "500",
                "31/12/2024": "400",
            },
            {
                "Poste": "Total des actifs courants",
                "31/12/2025": "3 200",
                "31/12/2024": "2 900",
            },
            {
                "Poste": "Total actif",
                "31/12/2025": "7 200",
                "31/12/2024": "6 700",
            },
            {
                "Poste": "Capital social",
                "31/12/2025": "2 000",
                "31/12/2024": "2 000",
            },
            {
                "Poste": "Réserves",
                "31/12/2025": "900",
                "31/12/2024": "750",
            },
            {
                "Poste": "Résultat de l'exercice",
                "31/12/2025": "600",
                "31/12/2024": "550",
            },
            {
                "Poste": "Total des capitaux propres",
                "31/12/2025": "3 500",
                "31/12/2024": "3 300",
            },
            {
                "Poste": "Emprunts bancaires à long terme",
                "31/12/2025": "1 800",
                "31/12/2024": "1 700",
            },
            {
                "Poste": "Fournisseurs et comptes rattachés",
                "31/12/2025": "1 400",
                "31/12/2024": "1 200",
            },
            {
                "Poste": "Dettes fiscales et sociales",
                "31/12/2025": "500",
                "31/12/2024": "500",
            },
            {
                "Poste": "Total des passifs courants",
                "31/12/2025": "1 900",
                "31/12/2024": "1 700",
            },
            {
                "Poste": "Total des dettes",
                "31/12/2025": "3 700",
                "31/12/2024": "3 400",
            },
        ]
    )

    compte_resultat = pd.DataFrame(
        [
            {
                "Poste": "Chiffre d'affaires",
                "31/12/2025": "10 500",
                "31/12/2024": "9 800",
            },
            {
                "Poste": "Coût des ventes",
                "31/12/2025": "6 200",
                "31/12/2024": "5 900",
            },
            {
                "Poste": "Résultat d'exploitation",
                "31/12/2025": "950",
                "31/12/2024": "800",
            },
            {
                "Poste": "Résultat net",
                "31/12/2025": "600",
                "31/12/2024": "550",
            },
        ]
    )

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(SORTIE, engine="openpyxl") as redacteur:
        bilan.to_excel(redacteur, sheet_name="Bilan", index=False)
        compte_resultat.to_excel(redacteur, sheet_name="Compte de résultat", index=False)

    print(f"Fichier généré : {SORTIE}")


if __name__ == "__main__":
    main()
