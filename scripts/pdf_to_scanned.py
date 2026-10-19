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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", help="PDF source")
    parser.add_argument("dst", help="PDF scanné à écrire")
    parser.add_argument(
        "--pages", default=None,
        help="Pages à inclure (ex. '1,2,3' ou '1-3'). Par défaut : toutes.",
    )
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(src)
    total = len(doc)

    if args.pages:
        indices = set()
        for chunk in args.pages.split(","):
            if "-" in chunk:
                a, b = chunk.split("-", 1)
                indices.update(range(int(a) - 1, int(b)))
            else:
                indices.add(int(chunk) - 1)
        page_range = sorted(i for i in indices if 0 <= i < total)
    else:
        page_range = list(range(total))

    images = []
    for i in page_range:
        page = doc[i]
        matrix = pymupdf.Matrix(args.dpi / 72, args.dpi / 72)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        images.append(img)

    if not images:
        print("Aucune page à exporter.", file=sys.stderr)
        return 1

    first, *rest = images
    first.save(
        dst, "PDF", resolution=args.dpi, save_all=True, append_images=rest
    )
    print(f"PDF scanné écrit : {dst} ({len(images)} page(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
