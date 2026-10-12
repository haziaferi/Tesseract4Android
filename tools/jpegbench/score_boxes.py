"""Check that a variant's word boxes, mapped back to the original image, line up with
the boxes Tesseract finds on the unprocessed image.

Each word of the variant is paired with the nearest unused word of the same text in the
base run of the same file. For every pair: IoU of the boxes, and the largest of the four
edge offsets in original-image pixels. Words with no same-text partner are counted apart
(they are recognition differences, not coordinate errors).

Usage: python tools/jpegbench/score_boxes.py <preprocbench-*-boxes.tsv> [<variant> ...]
"""
import statistics
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def main():
    rows = defaultdict(lambda: defaultdict(list))  # variant -> file -> [(word, box)]
    for line in open(sys.argv[1], encoding="utf-8").read().splitlines()[1:]:
        v, f, word, conf, *box = line.split("\t")
        rows[v][f].append((word.strip().lower(), tuple(float(x) for x in box)))
    variants = sys.argv[2:] or [v for v in rows if v != "base"]
    print(f"{'variant':<10}{'words':>7}{'paired':>8}{'IoU med':>9}{'IoU<0.5':>9}{'offset med':>11}{'p95':>6}{'max':>7}  px")
    for v in variants:
        ious, offs, total, paired = [], [], 0, 0
        for f, words in rows[v].items():
            pool = defaultdict(list)
            for w, b in rows["base"].get(f, []):
                pool[w].append(b)
            for w, b in words:
                total += 1
                cands = pool.get(w)
                if not cands:
                    continue
                cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                best = min(cands, key=lambda c: ((c[0] + c[2]) / 2 - cx) ** 2 + ((c[1] + c[3]) / 2 - cy) ** 2)
                cands.remove(best)
                paired += 1
                ious.append(iou(b, best))
                offs.append(max(abs(b[i] - best[i]) for i in range(4)))
        offs.sort()
        print(f"{v:<10}{total:7d}{100 * paired / max(total, 1):7.1f}%{statistics.median(ious):9.3f}"
              f"{100 * sum(x < 0.5 for x in ious) / len(ious):8.1f}%{statistics.median(offs):11.1f}"
              f"{offs[int(0.95 * (len(offs) - 1))]:6.1f}{offs[-1]:7.1f}")


if __name__ == "__main__":
    main()
