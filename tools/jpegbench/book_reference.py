"""Rebuild a scanned PDF page's text layer when its ToUnicode map is incomplete.

Some PDFs (here: Google-digitized scans re-saved by macOS Preview) carry Type0 fonts with
Identity-H encoding whose ToUnicode CMap covers only some glyphs. Extractors that fall back
to the raw code for the rest produce an ambiguous letter substitution ("FhRRVH" for
"choose", where "H" may be a real H or the glyph id of "e"). pdfminer instead writes an
unmapped glyph as "(cid:N)", and the embedded font still names its glyphs, so every
(cid:N) is replaced by the Unicode of glyph N's name. Only upright text is kept (the
vertical margin watermark is dropped).

Usage: python tools/jpegbench/book_reference.py <pdf> <pages_dir>
Rewrites <pages_dir>/bNNN.txt for every bNNN__page.jpg there.
"""
import io
import re
from collections import Counter
import sys
from pathlib import Path

import fitz
import pdfplumber
from fontTools.agl import toUnicode
from fontTools.ttLib import TTFont

sys.stdout.reconfigure(encoding="utf-8")


def glyph_names(doc, page_no):
    """Font name (without subset prefix) -> glyph order, for the fonts on a page."""
    out = {}
    for f in doc[page_no].get_fonts(full=True):
        buf = doc.extract_font(f[0])[3]
        if buf:
            out[f[3].split("+")[-1]] = TTFont(io.BytesIO(buf)).getGlyphOrder()
    return out


def decode(text, glyphs):
    def repl(m):
        cid = int(m.group(1))
        if glyphs is None or cid >= len(glyphs):
            return m.group(0)
        name = glyphs[cid]
        return " " if name == "space" else (toUnicode(name) or m.group(0))
    return re.sub(r"\(cid:(\d+)\)", repl, text)


def page_text(plumber_page, glyphs_by_font):
    upright = plumber_page.filter(lambda o: o.get("object_type") != "char" or o.get("upright", True))
    lines = []
    for ln in upright.extract_text_lines(return_chars=True):
        # The line text has the inferred word spaces; decode it with the line's main font.
        font = Counter(ch["fontname"].split("+")[-1] for ch in ln["chars"]).most_common(1)[0][0]
        lines.append(decode(ln["text"], glyphs_by_font.get(font)))
    return "\n".join(lines)


def main():
    doc = fitz.open(sys.argv[1])
    pages = Path(sys.argv[2])
    with pdfplumber.open(sys.argv[1]) as pdf:
        for jpg in sorted(pages.glob("b*__page.jpg")):
            n = int(jpg.name[1:4])
            text = page_text(pdf.pages[n], glyph_names(doc, n))
            jpg.with_name(f"b{n:03d}.txt").write_text(text + "\n", encoding="utf-8")
            left = len(re.findall(r"\(cid:\d+\)", text))
            print(f"b{n:03d}: {len(text)} chars, {left} glyphs left undecoded")


if __name__ == "__main__":
    main()
