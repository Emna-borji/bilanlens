"""Rend un PDF à texte en version « scannée » (images sans couche texte).

Utile pour tester le pipeline OCR : la sortie contient uniquement des
pixels, aucune couche texte sélectionnable, exactement comme un scan.
"""
import argparse
import sys
from pathlib import Path

import pymupdf
from PIL import Image


def main():
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("src", help="PDF source")
    parseur.add_argument("dst", help="PDF scanné à écrire")
    parseur.add_argument(
        "--pages", default=None,
        help="Pages à inclure (ex. '1,2,3' ou '1-3'). Par défaut : toutes.",
    )
    parseur.add_argument("--dpi", type=int, default=200)
    args = parseur.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(src)
    total = len(doc)

    if args.pages:
        indices = set()
        for morceau in args.pages.split(","):
            if "-" in morceau:
                a, b = morceau.split("-", 1)
                indices.update(range(int(a) - 1, int(b)))
            else:
                indices.add(int(morceau) - 1)
        plage_pages = sorted(i for i in indices if 0 <= i < total)
    else:
        plage_pages = list(range(total))

    images = []
    for i in plage_pages:
        page = doc[i]
        matrice = pymupdf.Matrix(args.dpi / 72, args.dpi / 72)
        pix = page.get_pixmap(matrix=matrice, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        images.append(img)

    if not images:
        print("Aucune page à exporter.", file=sys.stderr)
        return 1

    premiere, *reste = images
    premiere.save(
        dst, "PDF", resolution=args.dpi, save_all=True, append_images=reste
    )
    print(f"PDF scanné écrit : {dst} ({len(images)} page(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
