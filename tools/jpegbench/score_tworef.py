"""Score OCR word lists against two references when no ground truth exists.

found = words of the CLEAN reference (only words a stronger read was confident about)
        that the OCR also produced, in % of clean-reference words.
extra = OCR words absent from the FULL reference (not even the stronger read produced
        them: junk, misreads), in % of clean-reference words.
Optionally drops OCR words below confidence thresholds (from a -boxes.tsv).

Usage: python tools/jpegbench/score_tworef.py <clean_dir> <full_dir> <run>-boxes.tsv [...]
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score_book import words  # noqa: E402
from score_conf import THRESHOLDS, page_words  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def main():
    clean_dir, full_dir = Path(sys.argv[1]), Path(sys.argv[2])
    for tsv in sys.argv[3:]:
        rows = defaultdict(lambda: defaultdict(list))
        for line in open(tsv, encoding="utf-8").read().splitlines()[1:]:
            v, f, word, conf, *_ = line.split("\t")
            rows[v][f].append((word, float(conf)))
        files = sorted({f for v in rows for f in rows[v]})
        clean = {f: words((clean_dir / (f.split("__")[0] + ".txt")).read_text(encoding="utf-8")) for f in files}
        full = {f: words((full_dir / (f.split("__")[0] + ".txt")).read_text(encoding="utf-8")) for f in files}
        n = sum(sum(c.values()) for c in clean.values())
        print(f"\n{Path(tsv).name}: {len(files)} pages, {n} clean-reference words")
        print(f"{'variant':<9}{'min conf':>9}{'found %':>9}{'extra %':>9}{'net':>8}")
        for v in rows:
            for t in THRESHOLDS:
                found = extra = 0
                for f in files:
                    ocr = page_words(rows[v].get(f, []), t)
                    found += sum((ocr & clean[f]).values())
                    extra += sum((ocr - full[f]).values())
                print(f"{v:<9}{t:9d}{100 * found / n:9.2f}{100 * extra / n:9.2f}{100 * (found - extra) / n:8.2f}")


if __name__ == "__main__":
    main()
