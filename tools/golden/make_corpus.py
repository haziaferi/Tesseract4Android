"""Generate the golden-output image corpus for GoldenOutputTest.

The files are committed, so this script only needs to run again if the corpus
itself is meant to change. Each image exercises one decoder path that a
libpng / libjpeg / Leptonica upgrade could change: bit depths, palettes with
transparency, compressed text and ICC chunks, JPEG subsampling and progressive
mode, and deliberately damaged files that may be accepted or rejected.

Usage: python tools/golden/make_corpus.py
"""
import io
import struct
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

OUT = Path(__file__).resolve().parents[2] / "tesseract4android/src/androidTest/assets/golden"
W, H = 360, 120
TEXT = "The quick brown fox\njumps over 1234567890"


def font(size):
    for name in ("DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def page(mode="L", bg=255, fg=0):
    im = Image.new(mode, (W, H), bg)
    ImageDraw.Draw(im).multiline_text((12, 14), TEXT, fill=fg, font=font(30), spacing=10)
    return im


def colour_page():
    im = Image.new("RGB", (W, H))
    px = im.load()
    for y in range(H):
        for x in range(W):
            px[x, y] = (x * 255 // W, y * 255 // H, (x + y) * 255 // (W + H))
    ImageDraw.Draw(im).multiline_text((12, 14), TEXT, fill=(10, 10, 10), font=font(30), spacing=10)
    return im


def save_png(im, name, **kw):
    im.save(OUT / name, "PNG", **kw)


def save_jpg(im, name, **kw):
    im.save(OUT / name, "JPEG", **kw)


def chunks(data):
    pos = 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        yield pos, length, data[pos + 4:pos + 8]
        pos += 12 + length


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # PNG bit depths and colour types
    save_png(page("L").convert("1"), "png_1bit.png")
    save_png(page("L"), "png_8bit_gray.png")
    save_png(page("I;16", 65535, 0), "png_16bit_gray.png")
    save_png(colour_page(), "png_rgb.png")
    rgba = colour_page().convert("RGBA")
    rgba.putalpha(Image.linear_gradient("L").resize((W, H)))
    save_png(rgba, "png_rgba.png")

    pal = colour_page().quantize(colors=16)
    save_png(pal, "png_palette.png")
    save_png(pal, "png_palette_trns.png", transparency=0)

    # Compressed text, international text and an ICC profile (zTXt / iTXt / iCCP)
    info = PngInfo()
    info.add_text("Comment", "zTXt chunk " * 40, zip=True)
    info.add_itxt("Title", "iTXt chunk èé", lang="it", tkey="Titolo", zip=True)
    save_png(page("L"), "png_text_chunks.png", pnginfo=info)
    from PIL import ImageCms
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    save_png(colour_page(), "png_iccp.png", icc_profile=icc)

    # Damaged PNGs: bad CRC on an ancillary chunk, truncated image data
    good = (OUT / "png_text_chunks.png").read_bytes()
    bad = bytearray(good)
    for pos, length, ctype in chunks(good):
        if ctype in (b"zTXt", b"tEXt", b"iTXt"):
            crc_at = pos + 8 + length
            bad[crc_at] ^= 0xFF
            break
    (OUT / "png_bad_crc_ancillary.png").write_bytes(bytes(bad))
    rgb = (OUT / "png_rgb.png").read_bytes()
    for pos, length, ctype in chunks(rgb):
        if ctype == b"IDAT":
            (OUT / "png_truncated_idat.png").write_bytes(rgb[:pos + 8 + length // 2])
            break

    # JPEG variants
    col = colour_page()
    save_jpg(col, "jpg_420.jpg", quality=85, subsampling=2)
    save_jpg(col, "jpg_444.jpg", quality=85, subsampling=0)
    save_jpg(page("L"), "jpg_gray.jpg", quality=85)
    save_jpg(col, "jpg_progressive.jpg", quality=85, progressive=True)
    save_jpg(col, "jpg_q30.jpg", quality=30)
    j = (OUT / "jpg_420.jpg").read_bytes()
    (OUT / "jpg_truncated.jpg").write_bytes(j[:len(j) * 2 // 3])

    for p in sorted(OUT.iterdir()):
        print(f"{p.stat().st_size:7d}  {p.name}")


if __name__ == "__main__":
    main()
