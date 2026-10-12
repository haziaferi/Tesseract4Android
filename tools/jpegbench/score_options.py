"""Score ways of adding the stacked preprocessing pipeline against the current state.

A  current state: no pipeline
B  opt-in library method; default behaviour unchanged
C  pipeline on by default inside the library
D  documented recipe (sample/README), no library change; it needs only the public API

Each criterion is 0..1, higher is better. "measured" criteria come from RESULTS.md;
"judgment" criteria are estimates and are labelled so. The ranking is then checked
against random weightings, so it does not hinge on one choice of weights.
"""
import math
import random

# Measured inputs (OnePlus 6T, RESULTS.md)
CER_BASE, CER_PIPE = 0.544, 0.284              # synthetic corpus, character error rate %
FILES_WORSE = 51 / 419                         # files the pipeline made worse
TIME_RATIO = math.sqrt((857 / 633) * (8.6 / 5.8))       # synthetic and book, geometric mean
MEM_RATIO = math.sqrt((300 / 110) * (113 / 65))         # 600 dpi and 300 dpi book pages
BOOK_FOUND_DELTA, BOOK_EXTRA_DELTA = -0.02, -0.14       # points of reference words

gain = (CER_BASE - CER_PIPE) / CER_BASE                 # relative error reduction when used
cost = 1 / (TIME_RATIO * MEM_RATIO)                     # 1 = free, lower = costlier
book = 0.5 + (BOOK_FOUND_DELTA - BOOK_EXTRA_DELTA) / 2  # 0.5 = neutral on real scans

CRITERIA = {
    # name: (kind, {option: value})
    "accuracy gain available":      ("measured", {"A": 0, "B": gain, "C": gain, "D": gain}),
    "effect on a real scan":        ("measured", {"A": 0.5, "B": book, "C": book, "D": book}),
    "no regressions for existing users": ("measured", {"A": 1, "B": 1, "C": 1 - FILES_WORSE - 0.5, "D": 1}),
    "speed and memory by default":  ("measured", {"A": 1, "B": 1, "C": cost, "D": 1}),
    "effort for an app to benefit": ("judgment", {"A": 0, "B": 1, "C": 1, "D": 0.5}),
    "maintenance and API surface":  ("judgment", {"A": 1, "B": 0.6, "C": 0.3, "D": 0.9}),
    "upstream acceptance":          ("judgment", {"A": 1, "B": 0.6, "C": 0.1, "D": 0.9}),
}
# C's regression score also loses 0.5 for changing word-box coordinates (2x) under
# every existing caller of hOCR, ResultIterator and the PDF renderer.

WEIGHTS = {  # the owner's stated goal is quality and accuracy
    "accuracy gain available": 3,
    "effect on a real scan": 2,
    "no regressions for existing users": 2,
    "speed and memory by default": 1.5,
    "effort for an app to benefit": 1,
    "maintenance and API surface": 1,
    "upstream acceptance": 0.5,
}
OPTIONS = "ABCD"
NAMES = {"A": "current state", "B": "opt-in library method", "C": "on by default", "D": "documented recipe"}


def score(weights):
    return {o: sum(weights[c] * v[o] for c, (_, v) in CRITERIA.items()) / sum(weights.values()) for o in OPTIONS}


def main():
    print(f"inputs: error reduction {gain:.0%}, time x{TIME_RATIO:.2f}, memory x{MEM_RATIO:.2f}, "
          f"files worse {FILES_WORSE:.0%}, real-scan score {book:.2f}\n")
    print(f"{'criterion':<36}{'kind':<10}" + "".join(f"{o:>7}" for o in OPTIONS))
    for c, (kind, v) in CRITERIA.items():
        print(f"{c:<36}{kind:<10}" + "".join(f"{v[o]:7.2f}" for o in OPTIONS))
    s = score(WEIGHTS)
    print(f"\n{'weighted score':<46}" + "".join(f"{s[o]:7.3f}" for o in OPTIONS))

    rng = random.Random(1)
    wins = dict.fromkeys(OPTIONS, 0)
    for _ in range(5000):
        w = {c: WEIGHTS[c] * rng.uniform(0.5, 2.0) for c in WEIGHTS}
        r = score(w)
        wins[max(r, key=r.get)] += 1
    print("top under 5000 weightings (each weight x0.5..x2):",
          ", ".join(f"{o} {NAMES[o]} {100 * n / 5000:.1f}%" for o, n in sorted(wins.items(), key=lambda x: -x[1])))

    # Without the judgment criteria, measured evidence only
    measured = {c: (WEIGHTS[c] if CRITERIA[c][0] == "measured" else 0) for c in WEIGHTS}
    m = score(measured)
    print("measured criteria only:", ", ".join(f"{o} {m[o]:.3f}" for o in OPTIONS))


if __name__ == "__main__":
    main()
