"""Score Tesseract-on-Android candidates from GitHub data pulled 2026-10-11.

Each criterion is normalised to 0..1. The ranking is then checked against
random weightings, so the answer does not hinge on one hand-picked weight.
"""
import math
import random

# stars, commits in last 12 months (capped at 100 by the API page), contributors,
# days since last push, permissive licence, reusable as a library, engine score,
# active (not archived)
# Engine score: 1.0 = Tesseract 5.5.x (verified), 0.2 = 3.05, 0.4 = unverified.
C = {
    "adaptech-cz/Tesseract4Android":      (945, 3, 2, 248, 1, 1.0, 1.0, 1),
    "SubhamTyagi/android-ocr":            (610, 39, 70, 66, 1, 0.3, 1.0, 1),
    "ossappscollective/OSS-DocumentScanner": (2540, 100, 91, 4, 1, 0.5, 0.4, 1),
    "rmtheis/tess-two":                   (3761, 0, 13, 1304, 1, 1.0, 0.2, 0),
    "renard314/textfairy":                (826, 0, 5, 2129, 0, 0.3, 0.4, 1),
    "jonathanpalma/react-native-tesseract-ocr": (595, 0, 3, 327, 1, 0.8, 0.4, 1),
    "arrrrny/tesseract_ocr (Flutter)":    (105, 2, 4, 130, 1, 0.8, 0.4, 1),
}

def features(v):
    stars, c12, contrib, age, lic, lib, eng, alive = v
    return {
        "adoption":    math.log10(stars + 1) / math.log10(4000),
        "activity":    min(c12, 100) / 100,
        "bus_factor":  min(math.log10(contrib + 1) / 2, 1),
        "recency":     math.exp(-age / 365),
        "licence":     lic,
        "reusable":    lib,
        "engine":      eng,
        "alive":       alive,
    }

F = {k: features(v) for k, v in C.items()}
KEYS = list(next(iter(F.values())))

def rank(w):
    s = {k: sum(w[c] * f[c] for c in KEYS) for k, f in F.items()}
    return sorted(s, key=s.get, reverse=True), s

def report(goal, base):
    order, s = rank(base)
    print(f"\n== {goal} ==")
    for k in order:
        print(f"  {s[k]:.2f}  {k}")
    wins = {}
    rng = random.Random(1)
    for _ in range(5000):
        # jitter each weight by x0.5..x2 around the goal's weights
        w = {c: base[c] * rng.uniform(0.5, 2.0) for c in KEYS}
        top = rank(w)[0][0]
        wins[top] = wins.get(top, 0) + 1
    print("  top-1 under 5000 jittered weightings:",
          {k: f"{v/50:.1f}%" for k, v in sorted(wins.items(), key=lambda x: -x[1])})

# Goal A: an engine to embed in your own Kotlin app.
report("A: library to embed in an Android app", dict(
    adoption=1, activity=1, bus_factor=1, recency=1, licence=2,
    reusable=4, engine=4, alive=3))
# Goal B: an existing app to fork / with the most room to grow.
report("B: app with the most potential to fork or build on", dict(
    adoption=1.5, activity=3, bus_factor=3, recency=2, licence=1.5,
    reusable=0.5, engine=1.5, alive=3))
