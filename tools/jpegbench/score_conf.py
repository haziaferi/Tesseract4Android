"""Score OCR word lists after dropping words below a confidence threshold.

Reads the -boxes.tsv written by PreprocBenchTest (one row per word with Tesseract's
word confidence) and scores each variant word-level and order-free against the
reference text, like score_book.py: found = reference words recovered, extra = OCR words
not in the reference, both in % of reference words. A word ending in "-" is joined with
the next one, as the reference joins line-end hyphenation.

Usage: python tools/jpegbench/score_conf.py <pages_dir> <run>-boxes.tsv [...]
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score_book import words  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
THRESHOLDS = [0, 20, 40, 50, 60, 70, 80, 90]


def page_words(rows, threshold):
    kept = [w for w, c in rows if c >= threshold]
    joined, i = [], 0
    while i < len(kept):
        w = kept[i]
        while w.endswith("-") and i + 1 < len(kept):
            i += 1
            w = w[:-1] + kept[i]
        joined.append(w)
        i += 1
    return words(" ".join(joined))


def main():
    pages = Path(sys.argv[1])
    for tsv in sys.argv[2:]:
        rows = defaultdict(lambda: defaultdict(list))
        for line in open(tsv, encoding="utf-8").read().splitlines()[1:]:
            v, f, word, conf, *_ = line.split("\t")
            rows[v][f].append((word, float(conf)))
        files = sorted({f for v in rows for f in rows[v]})
        refs = {f: words((pages / (f.split("__")[0] + ".txt")).read_text(encoding="utf-8")) for f in files}
        nref = sum(sum(r.values()) for r in refs.values())
        print(f"\n{Path(tsv).name}: {len(files)} pages, {nref} reference words")
        print(f"{'variant':<9}{'min conf':>9}{'found %':>9}{'extra %':>9}{'net':>8}")
        for v in rows:
            for t in THRESHOLDS:
                found = extra = 0
                for f in files:
                    ocr = page_words(rows[v].get(f, []), t)
                    hit = sum((ocr & refs[f]).values())
                    found += hit
                    extra += sum(ocr.values()) - hit
                print(f"{v:<9}{t:9d}{100 * found / nref:9.2f}{100 * extra / nref:9.2f}{100 * (found - extra) / nref:8.2f}")


if __name__ == "__main__":
    main()
