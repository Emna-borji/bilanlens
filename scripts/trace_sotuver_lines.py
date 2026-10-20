"""Trace les mots OCR autour de 'Total des actifs' sur SOTUVER scanné."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from conftest import load  # type: ignore
from bilanlens.extraction import _ocr_pdf_bytes


def main():
    raw = load("sotuver_scanned.pdf").getvalue()
    _txt, pages = _ocr_pdf_bytes(raw)
    out = Path("scripts/_lines_out.txt")
    with out.open("w", encoding="utf-8") as f:
        for i, p in enumerate(pages):
            f.write(f"\n===== page {i + 1} ({len(p)} words) =====\n")
            # Grouper par y approximatif (bucket 20 pixels)
            buckets = {}
            for w in p:
                y = int(w["top"] / 20) * 20
                buckets.setdefault(y, []).append(w)
            for y in sorted(buckets):
                row = sorted(buckets[y], key=lambda w: w["x0"])
                row_text = " ".join(w["text"] for w in row)
                if "actif" in row_text.lower() and ("total" in row_text.lower() or "courant" in row_text.lower()):
                    f.write(f"y={y}: {row_text}\n")
                    gaps = [row[j + 1]["x0"] - row[j]["x1"] for j in range(len(row) - 1)]
                    f.write(f"  gaps: {gaps}\n")
                    f.write(f"  positions: {[(w['text'], w['x0'], w['x1'], w['top']) for w in row]}\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
