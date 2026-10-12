"""Score JpegBenchTest results: OCR character error rate and fidelity per libjpeg build.

Usage: python tools/jpegbench/score.py <corpus_dir> <results.tsv> [<results.tsv> ...]
The first results file is the reference that the others are compared with, file by file.
"""
import math
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def levenshtein(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def unescape(s):
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", "\\": "\\"}[m.group(1)], s)


def load(path, corpus):
    rows = {}
    for line in open(path, encoding="utf-8").read().splitlines()[1:]:
        kind, name, fmt, depth, psnr, ms, size, conf, text = line.split("\t", 8)
        page = name.split("__")[0]
        truth = norm((corpus / f"{page}.txt").read_text(encoding="utf-8"))
        ocr = norm(unescape(text))
        rows[(kind, name)] = dict(
            variant=name.split("__")[1][:-4], fmt=int(fmt), depth=int(depth),
            psnr=float(psnr), ms=int(ms), size=int(size), conf=int(conf),
            errors=levenshtein(ocr, truth), chars=len(truth))
    return rows


def sign_test_p(wins, losses):
    """Two-sided exact sign test, ties dropped."""
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def main():
    corpus = Path(sys.argv[1])
    runs = {Path(p).stem.replace("jpegbench-", ""): load(p, corpus) for p in sys.argv[2:]}
    labels = list(runs)
    ref = labels[0]

    for kind in ("decode", "encode"):
        print(f"\n=== {kind} ===")
        variants = sorted({r["variant"] for k, r in runs[ref].items() if k[0] == kind})
        print(f"{'variant':<12}" + "".join(f"{l:>28}" for l in labels))
        print(f"{'':<12}" + "".join(f"{'CER%   PSNR  ms':>28}" for _ in labels))
        for v in variants + ["ALL"]:
            cells = []
            for l in labels:
                rs = [r for k, r in runs[l].items() if k[0] == kind and (v == "ALL" or r["variant"] == v)]
                cer = 100 * sum(r["errors"] for r in rs) / sum(r["chars"] for r in rs)
                ps = statistics.mean(r["psnr"] for r in rs if math.isfinite(r["psnr"]))
                ms = statistics.median(r["ms"] for r in rs) if kind == "decode" else float("nan")
                cells.append(f"{cer:7.3f} {ps:7.3f} {ms:5.0f}")
            print(f"{v:<12}" + "".join(f"{c:>28}" for c in cells))
        if kind == "encode":
            for l in labels:
                rs = [r for k, r in runs[l].items() if k[0] == kind]
                print(f"  {l}: mean encoded size {statistics.mean(r['size'] for r in rs) / 1024:.1f} KiB")

        for l in labels[1:]:
            keys = [k for k in runs[ref] if k[0] == kind and k in runs[l]]
            d_err = [runs[l][k]["errors"] - runs[ref][k]["errors"] for k in keys]
            d_psnr = [runs[l][k]["psnr"] - runs[ref][k]["psnr"] for k in keys]
            better = sum(d < 0 for d in d_err)
            worse = sum(d > 0 for d in d_err)
            p_better = sum(d > 0 for d in d_psnr)
            p_worse = sum(d < 0 for d in d_psnr)
            fallback = sum(1 for k in keys if runs[l][k]["fmt"] != runs[ref][k]["fmt"])
            print(f"\n  {l} vs {ref} ({len(keys)} files):")
            print(f"    OCR errors: {better} files fewer, {worse} more, {len(keys) - better - worse} equal;"
                  f" net {sum(d_err):+d} chars; sign test p={sign_test_p(better, worse):.3g}")
            print(f"    PSNR: {p_better} higher, {p_worse} lower, mean {statistics.mean(d_psnr):+.4f} dB;"
                  f" sign test p={sign_test_p(p_better, p_worse):.3g}")
            if fallback:
                print(f"    {fallback} files changed decoder path (native vs fallback)")


if __name__ == "__main__":
    main()
