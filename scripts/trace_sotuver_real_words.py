"""Trace les mots pdfplumber de SOTUVER réel pour les passifs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pdfplumber


def main():
    with pdfplumber.open("tests/data/real_sotuver_2024.pdf") as pdf:
        out = Path("scripts/_real_words.txt")
        with out.open("w", encoding="utf-8") as f:
            for i, page in enumerate(pdf.pages):
                words = page.extract_words(
                    x_tolerance=2,
                    y_tolerance=3,
                    keep_blank_chars=False,
                )
                buckets = {}
                for w in words:
                    y = int(w["top"] / 3) * 3
                    buckets.setdefault(y, []).append(w)
                for y in sorted(buckets):
                    row = sorted(buckets[y], key=lambda w: w["x0"])
                    text = " ".join(w["text"] for w in row)
                    if "Total des passifs" in text and "Note" not in text:
                        f.write(f"page {i + 1}, y={y}: {text}\n")
                        f.write(
                            "  positions: "
                            + str([
                                (w["text"], round(w["x0"], 1), round(w["x1"], 1))
                                for w in row
                            ])
                            + "\n"
                        )
                        gaps = [
                            row[j + 1]["x0"] - row[j]["x1"]
                            for j in range(len(row) - 1)
                        ]
                        f.write(f"  gaps: {[round(g, 1) for g in gaps]}\n")
                        f.write("\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
