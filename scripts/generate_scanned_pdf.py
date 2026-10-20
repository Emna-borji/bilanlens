"""Génère des PDF « scannés » à partir d'un .txt pour tester l'OCR.

Rend le texte dans une image puis l'intègre dans un PDF — simule donc
un scan sans couche texte. Préserve les accents (Unicode) via Pillow.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


DEFAULT_FONT_PATHS = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Library/Fonts/Arial.ttf",
]


def _pick_font(size):
    for candidate in DEFAULT_FONT_PATHS:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _render_pages(text: str, font_size: int = 22):
    width, height = 1700, 2200
    margin = 80
    line_spacing = 10
    font = _pick_font(font_size)

    lines = text.splitlines() or [""]
    images = []
    current = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(current)
    y = margin

    for line in lines:
        bbox = draw.textbbox((0, 0), line or " ", font=font)
        line_height = bbox[3] - bbox[1]
        if y + line_height > height - margin:
            images.append(current)
            current = Image.new("RGB", (width, height), "white")
            draw = ImageDraw.Draw(current)
            y = margin
        draw.text((margin, y), line, fill="black", font=font)
        y += line_height + line_spacing

    images.append(current)
    return images


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", help="Fichier texte source (.txt)")
    parser.add_argument("dst", help="PDF scanné à écrire")
    parser.add_argument("--font-size", type=int, default=22)
    args = parser.parse_args()

    src_path = Path(args.src)
    dst_path = Path(args.dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    text = src_path.read_text(encoding="utf-8")
    pages = _render_pages(text, args.font_size)
    first, *rest = pages
    first.save(
        dst_path,
        "PDF",
        resolution=300,
        save_all=True,
        append_images=rest,
    )
    print(f"PDF scanné écrit : {dst_path} ({len(pages)} page(s))")


if __name__ == "__main__":
    sys.exit(main())
