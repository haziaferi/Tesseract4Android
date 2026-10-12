"""Generate the JPEG decoder benchmark corpus for JpegBenchTest.

Text pages with known ground truth are rendered losslessly (PNG), then saved as
JPEGs at several qualities and chroma subsamplings. Every candidate libjpeg build
decodes the same JPEG bytes, so differences in OCR accuracy and in fidelity to
the lossless original come from the decoder alone.

Usage: python tools/jpegbench/make_corpus.py <out_dir>
Then push <out_dir> to the test app's external files dir (see README in this folder).
"""
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = ["arial.ttf", "times.ttf", "georgia.ttf", "verdana.ttf", "cour.ttf"]
SIZES = [13, 17, 22, 30]                   # pixel size of the font
SCHEMES = [                                # (name, background, ink)
    ("black", (255, 255, 255), (0, 0, 0)),
    ("navy_on_cream", (250, 244, 214), (20, 30, 110)),
    ("red", (255, 255, 255), (190, 20, 20)),  # chroma subsampling hits coloured ink hardest
]
DEGRADE = ["clean", "blur", "noise", "light"]
JPEGS = [(q, s) for q in (50, 75, 90) for s in ("420", "444")]
WIDTH = 900                                # multiple of 4, so 8 bpp rows have no padding

WORDS = """the of and to in is that for it as was with be by on not he this are or his
from at which but have an they you were her she there been one all we their has would
when if so no what up out more about them into some could time only other new these
two may first then do any like my now over such our man me even most made after also
did many before must through back years where much your way well down should because
each just those people how too little state good very make world still own see men
work long get here between both life being under never day same another know while
last might us great old year off come since against go came right used take three
house small found number light water people paper market river letter garden window
station morning evening answer travel winter summer method account picture question
""".split()


def line_text(rng, n_words):
    words = [rng.choice(WORDS) for _ in range(n_words)]
    if rng.random() < 0.5:
        words.insert(rng.randrange(len(words)), str(rng.randrange(10, 99999)))
    words[0] = words[0].capitalize()
    return " ".join(words) + rng.choice([".", ",", ";", ":", "?", ""])


def render(font_name, size, scheme, degrade, rng):
    _, bg, ink = scheme
    font = ImageFont.truetype(font_name, size)
    lines, y_step = [], int(size * 1.6)
    draw_probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for _ in range(6):
        for n in range(12, 2, -1):
            t = line_text(rng, n)
            if draw_probe.textlength(t, font=font) <= WIDTH - 2 * 24:
                lines.append(t)
                break
    height = 2 * 24 + y_step * len(lines)
    height += (-height) % 4
    im = Image.new("RGB", (WIDTH, height), bg)
    d = ImageDraw.Draw(im)
    for i, t in enumerate(lines):
        d.text((24, 24 + i * y_step), t, fill=ink, font=font)
    if degrade == "blur":
        im = im.filter(ImageFilter.GaussianBlur(0.7))
    elif degrade == "noise":
        noise = Image.effect_noise((WIDTH, height), 18).convert("RGB")
        im = Image.blend(im, noise, 0.10)
    elif degrade == "light":  # uneven lighting, as in a phone photo of a page
        grad = Image.linear_gradient("L").rotate(90).resize((WIDTH, height))
        shade = Image.merge("RGB", [grad.point(lambda v: 255 - v // 3)] * 3)
        im = Image.composite(im, Image.new("RGB", im.size, (0, 0, 0)), shade.convert("L"))
    return im, "\n".join(lines)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261012)
    n = 0
    for fi, font in enumerate(FONTS):
        for si, size in enumerate(SIZES):
            for ci, scheme in enumerate(SCHEMES):
                degrade = DEGRADE[(fi + si + ci) % len(DEGRADE)]
                page = f"p{n:03d}_{Path(font).stem}_{size}_{scheme[0]}_{degrade}"
                im, text = render(font, size, scheme, degrade, rng)
                im.save(out / f"{page}.orig.png")
                im.convert("L").save(out / f"{page}.orig_gray.png")
                (out / f"{page}.txt").write_text(text + "\n", encoding="utf-8")
                for q, s in JPEGS:
                    im.save(out / f"{page}__q{q}_{s}.jpg", "JPEG", quality=q,
                            subsampling={"420": 2, "444": 0}[s])
                im.convert("L").save(out / f"{page}__q75_gray.jpg", "JPEG", quality=75)
                n += 1
    total = sum(p.stat().st_size for p in out.iterdir())
    print(f"{n} pages, {len(list(out.glob('*.jpg')))} JPEGs, {total / 1e6:.1f} MB in {out}")


if __name__ == "__main__":
    main()
