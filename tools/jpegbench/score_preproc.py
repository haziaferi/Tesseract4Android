"""Score PreprocBenchTest results: OCR error rate per preprocessing variant and combination.

Usage: python tools/jpegbench/score_preproc.py <corpus_dir> <preprocbench-*.tsv>
"""
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from score import levenshtein, norm, sign_test_p, unescape  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
CORPUS = Path(sys.argv[1])


def page_of(name):
    return name.split("__")[0]


def groups(name):
    stem = page_of(name).split("_")
    colour = "red" if "_red_" in name else "navy" if "navy" in name else "black"
    return {"size": stem[2] + "px", "colour": colour, "degradation": stem[-1], "font": stem[1],
            "jpeg": name.split("__")[1][:-4]}


truth_cache = {}


def truth(name):
    page = page_of(name)
    if page not in truth_cache:
        truth_cache[page] = norm((CORPUS / f"{page}.txt").read_text(encoding="utf-8"))
    return truth_cache[page]


res = defaultdict(dict)   # file -> variant -> (conf, ms, raw text)
for line in open(sys.argv[2], encoding="utf-8").read().splitlines()[1:]:
    variant, name, conf, ms, text = line.split("\t", 4)
    res[name][variant] = (int(conf), int(ms), unescape(text))
files = sorted(res)
variants = list(next(iter(res.values())))
chars = sum(len(truth(f)) for f in files)
err = {f: {v: levenshtein(norm(res[f][v][2]), truth(f)) for v in variants} for f in files}


def cer(total):
    return 100 * total / chars


print(f"{len(files)} JPEGs, {chars} truth characters\n")
print(f"{'variant':<10}{'CER %':>8}{'errors':>8}{'ms/page':>9}   vs base: fewer / more / equal, sign-test p")
for v in variants:
    e = sum(err[f][v] for f in files)
    ms = statistics.mean(res[f][v][1] for f in files)
    if v == "base":
        print(f"{v:<10}{cer(e):8.3f}{e:8d}{ms:9.0f}")
        continue
    fewer = sum(err[f][v] < err[f]["base"] for f in files)
    more = sum(err[f][v] > err[f]["base"] for f in files)
    print(f"{v:<10}{cer(e):8.3f}{e:8d}{ms:9.0f}   {fewer:4d} / {more:4d} / {len(files) - fewer - more:4d}, "
          f"p={sign_test_p(fewer, more):.2g}")

print("\nCER % by page property (base / light / up2x / minchan / all3):")
for key in ("size", "colour", "degradation", "font", "jpeg"):
    buckets = defaultdict(list)
    for f in files:
        buckets[groups(f)[key]].append(f)
    for g in sorted(buckets, key=lambda g: -sum(err[f]["base"] for f in buckets[g])):
        fs = buckets[g]
        c = sum(len(truth(f)) for f in fs)
        cells = " ".join(f"{100 * sum(err[f][v] for f in fs) / c:6.2f}" for v in variants)
        print(f"  {key:<11} {g:<9} {cells}")


def pick_conf(pool):
    return sum(err[f][max(pool, key=lambda v: (res[f][v][0], v == "base"))] for f in files)


def line_vote(pool):
    total = 0
    for f in files:
        texts = {v: [norm(l) for l in res[f][v][2].splitlines() if l.strip()] for v in pool}
        modal = Counter(len(t) for t in texts.values()).most_common(1)[0][0]
        voters = [v for v in pool if len(texts[v]) == modal]
        best = max(voters, key=lambda v: res[f][v][0])
        out = []
        for i in range(modal):
            votes = Counter(texts[v][i] for v in voters)
            top, n = votes.most_common(1)[0]
            # A strict majority wins; otherwise take the most confident variant's line.
            out.append(top if 2 * n > len(voters) else texts[best][i])
        total += levenshtein(" ".join(out), truth(f))
    return total


def oracle(pool):
    return sum(min(err[f][v] for v in pool) for f in files)


print("\nCombinations:")
pools = [["base", "light", "up2x", "minchan"], variants]
for pool in pools:
    ms = statistics.mean(sum(res[f][v][1] for v in pool) for f in files)
    print(f"  pool {'+'.join(pool)}  ({ms:.0f} ms/page for all of them)")
    for label, fn in (("most confident page", pick_conf), ("line vote", line_vote), ("perfect judge", oracle)):
        e = fn(pool)
        print(f"    {label:<20} CER {cer(e):.3f} %  ({e} errors)")
