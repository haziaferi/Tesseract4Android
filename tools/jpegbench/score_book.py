"""Score PreprocBenchTest results on scanned book pages against a reference text layer.

Word-level and order-free, because a page's blocks (columns, captions beside pictures)
can be read in a different order without any recognition error:
  found = reference words that the OCR also produced (multiset intersection), in %
  extra = OCR words that are not in the reference (junk, misreads), in % of reference words
Words are lower-cased runs of letters and digits; a hyphen at a line end joins the halves.

Usage: python tools/jpegbench/score_book.py <pages_dir> <preprocbench-*.tsv> [...]
"""
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score import unescape  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def words(text):
    text = re.sub(r"-\s*\n\s*", "", text)
    return Counter(re.findall(r"[a-z0-9]+", text.lower()))


def main():
    pages = Path(sys.argv[1])
    for tsv in sys.argv[2:]:
        res = defaultdict(dict)
        for line in open(tsv, encoding="utf-8").read().splitlines()[1:]:
            variant, name, conf, ms, text = line.split("\t", 4)
            res[name][variant] = (int(conf), int(ms), unescape(text))
        files = sorted(res)
        variants = list(next(iter(res.values())))
        ref = {f: words((pages / (f.split("__")[0] + ".txt")).read_text(encoding="utf-8")) for f in files}
        nref = sum(sum(r.values()) for r in ref.values())
        print(f"\n{Path(tsv).name}: {len(files)} pages, {nref} reference words")
        print(f"{'variant':<12}{'found %':>9}{'extra %':>9}{'conf':>6}{'s/page':>8}")
        stats = {}
        for v in variants:
            found = extra = 0
            per_page = []
            for f in files:
                ocr = words(res[f][v][2])
                hit = sum((ocr & ref[f]).values())
                found += hit
                extra += sum(ocr.values()) - hit
                per_page.append((hit - (sum(ocr.values()) - hit)) / sum(ref[f].values()))
            stats[v] = per_page
            print(f"{v:<12}{100 * found / nref:9.2f}{100 * extra / nref:9.2f}"
                  f"{statistics.mean(res[f][v][0] for f in files):6.0f}"
                  f"{statistics.mean(res[f][v][1] for f in files) / 1000:8.1f}")
        # Most-confident pick per page among the variants
        found = extra = 0
        for f in files:
            v = max(variants, key=lambda v: res[f][v][0])
            ocr = words(res[f][v][2])
            hit = sum((ocr & ref[f]).values())
            found += hit
            extra += sum(ocr.values()) - hit
        print(f"{'pick conf':<12}{100 * found / nref:9.2f}{100 * extra / nref:9.2f}")
        print("per page, found minus extra (%), by variant:")
        for i, f in enumerate(files):
            print(f"  {f.split('__')[0]:<6}" + "".join(f"{100 * stats[v][i]:8.1f}" for v in variants))


if __name__ == "__main__":
    main()
