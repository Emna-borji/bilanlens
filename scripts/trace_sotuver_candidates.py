"""Script temporaire pour tracer les candidates OCR SOTUVER."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from conftest import load  # type: ignore
from bilanlens.extraction import extract_document
from bilanlens.mapping import map_candidates


def main():
    e = extract_document(load("real_sotuver_2024.pdf"))
    cands = map_candidates(e["text"], records=e["records"])
    out = Path("scripts/_trace_out.txt")
    with out.open("w", encoding="utf-8") as f:
        f.write(f"text chars: {len(e['text'])}\n")
        f.write(f"records: {len(e['records'])}\n")
        for rec in e["records"]:
            lbl = (rec.get("label") or "").lower()
            if ("passifs" in lbl or "emprunts" in lbl) and ("total" in lbl or "non courants" in lbl):
                f.write(
                    f"RAW | {rec.get('period')} | {int(rec.get('value') or 0)} |"
                    f" {repr(rec.get('label'))[:80]} | src={repr(rec.get('source_line'))[:160]}\n"
                )
        f.write("\n--- mapped ---\n")
        for c in cands:
            k = c.get("key")
            if k in ("long_term_debt", "current_liabilities", "total_debt"):
                f.write(
                    f"{k} | {c.get('period')} | {int(c.get('value') or 0)}"
                    f" | r={c.get('rank')} | {repr(c.get('label'))[:80]}\n"
                )
    print("wrote", out)


if __name__ == "__main__":
    main()
