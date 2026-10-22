"""Génère des PDF « scannés » à partir d'un .txt pour tester l'OCR.

Rend le texte dans une image puis l'intègre dans un PDF — simule donc
un scan sans couche texte. Préserve les accents (Unicode) via Pillow.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


CHEMINS_POLICE_DEFAUT = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial.ttf",
]


def _choisir_police(taille):
    for candidat in CHEMINS_POLICE_DEFAUT:
        if Path(candidat).exists():
            try:
                return ImageFont.truetype(candidat, taille)
            except OSError:
                continue
    return ImageFont.load_default()


def _rendre_pages(texte: str, taille_police: int = 22):
    largeur, hauteur = 1700, 2200
    marge = 80
    interligne = 10
    police = _choisir_police(taille_police)

    lignes = texte.splitlines() or [""]
    images = []
    courante = Image.new("RGB", (largeur, hauteur), "white")
    stylo = ImageDraw.Draw(courante)
    y = marge

    for ligne in lignes:
        bbox = stylo.textbbox((0, 0), ligne or " ", font=police)
        hauteur_ligne = bbox[3] - bbox[1]
        if y + hauteur_ligne > hauteur - marge:
            images.append(courante)
            courante = Image.new("RGB", (largeur, hauteur), "white")
            stylo = ImageDraw.Draw(courante)
            y = marge
        stylo.text((marge, y), ligne, fill="black", font=police)
        y += hauteur_ligne + interligne

    images.append(courante)
    return images


def main():
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("src", help="Fichier texte source (.txt)")
    parseur.add_argument("dst", help="PDF scanné à écrire")
    parseur.add_argument("--font-size", type=int, default=22)
    args = parseur.parse_args()

    chemin_src = Path(args.src)
    chemin_dst = Path(args.dst)
    chemin_dst.parent.mkdir(parents=True, exist_ok=True)

    texte = chemin_src.read_text(encoding="utf-8")
    pages = _rendre_pages(texte, args.font_size)
    premiere, *reste = pages
    premiere.save(
        chemin_dst,
        "PDF",
        resolution=300,
        save_all=True,
        append_images=reste,
    )
    print(f"PDF scanné écrit : {chemin_dst} ({len(pages)} page(s))")


if __name__ == "__main__":
    sys.exit(main())
