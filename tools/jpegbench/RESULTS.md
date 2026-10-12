# libjpeg candidates: measured on a OnePlus 6T (arm64-v8a), 2026-10-12

Built into Tesseract4Android 4.10.0 (Tesseract 5.5.3, Leptonica 1.87.0), standard flavour.
Corpus: `make_corpus.py`, 60 synthetic text pages (5 Windows fonts x 4 sizes x 3 colour
schemes, with blur / noise / uneven-lighting variants), each saved by Pillow as 7 JPEGs
(q50/q75/q90 x 4:2:0/4:4:4, plus q75 grayscale). Every candidate decodes the same JPEG bytes.
Encoder rows: Leptonica writes each lossless original at q75 and q90 (4:2:0, its default)
with the candidate library, and the same library decodes it back.

CER = Tesseract character error rate against the ground truth (whitespace normalised).
PSNR = fidelity of the decoded image to the lossless original. `score.py` reproduces the tables.

| | IJG 9f | IJG 10 | libjpeg-turbo 3.2.0 |
|---|---|---|---|
| Decode CER, 420 JPEGs | 0.545 % | 0.545 % | 0.535 % |
| Decode PSNR, mean | 33.702 dB | 33.702 dB | 33.709 dB |
| Encode CER, 120 files | 0.424 % | 0.424 % | 0.589 % |
| Encode PSNR at q90 | 35.619 dB | 35.619 dB | 35.259 dB |
| Encoded size at q90 | 53.1 KiB | 53.1 KiB | 52.7 KiB |
| Decode time, mean | 3.5 ms | 3.5 ms | 1.7 ms |

- IJG 10 is identical to 9f in every value on every file.
- turbo vs IJG, decode: OCR differs on 31 of 420 files (17 better, 14 worse; sign test
  p = 0.72), i.e. no measurable accuracy difference. PSNR is higher on 95 files and lower on
  60 (p = 0.006), but by 0.007 dB on average: better at q50/q75 4:2:0 (+0.05 / +0.09 dB),
  worse at q90 4:2:0 (-0.09 dB), identical for 4:4:4 and grayscale.
- turbo vs IJG, encode: PSNR higher on 26 files and lower on 54 (p = 0.002); IJG's q90
  output is 0.36 dB better for 0.8 % more bytes; q75 is a tie. OCR: 7 better, 13 worse
  (p = 0.26), not significant.
- turbo's Leptonica-encoded files are byte-for-byte the size of Pillow's (60/60), as
  expected: Pillow uses libjpeg-turbo too.

Limits: synthetic pages, not camera photos; one device; turbo's x86 SIMD was not built
(NDK has no NASM) and x86 was not measured.

`turbo-wrapper/` is the CMake used for the turbo build (ExternalProject, static library
linked whole into libjpeg.so). `bench.sh` is the runner (expects the corpus in `_work/`).

## Preprocessing before OCR (IJG 9f decoder), 2026-10-12

`PreprocBenchTest` on the same corpus (419 JPEGs; one file's row was cut off by a crash,
see below). `score_preproc.py` reproduces this.

| Variant | CER | vs no preprocessing (files better / worse) | ms per page |
|---|---|---|---|
| none | 0.544 % | | 633 |
| background normalization | 0.554 % | 54 / 59, p = 0.71 | 640 |
| 2x upscale | 1.440 % | 124 / 56, but net worse | 924 |
| darkest channel (min R,G,B) | 0.976 % | 26 / 81, p < 1e-7 | 614 |
| all three: darkest channel, normalize, 2x | 0.284 % | 125 / 51, p = 2e-8 | 857 |
| line vote over all five | 0.242 % | | 3668 |
| most confident of all five | 0.635 % | | 3668 |
| perfect judge over all five (ceiling) | 0.088 % | | |

The stacked pipeline helps most where errors were: 13 px text 1.11 -> 0.72 %, 17 px
0.80 -> 0.21 %, red ink 0.87 -> 0.17 %, uneven lighting 1.19 -> 0.28 %. Each step alone
does not. Tesseract's mean confidence is a poor judge between variants.

On 15 text pages of a Google-digitized scanned book (grayscale, 300 and 600 dpi), Tesseract
already found 99.5 % of the reference words; normalization and 600 -> 300 dpi scaling moved
that by about 10 words of 6524. Most remaining error there is short junk read from
pictures and the margin watermark. `book_reference.py` rebuilds such a book's reference
text when its PDF has an incomplete ToUnicode map; `score_book.py` scores word-level.

Open: the first preprocessing run's process crashed after about 1700 OCR calls (many on
2x images). Re-running from that file did not crash, so it is not tied to one image;
the cause (likely memory growth over a long run) was not captured.

## Adding the stacked pipeline: options scored (score_options.py)

Stacked pipeline on the 15 book pages: words found 99.51 -> 99.49 %, junk 1.72 -> 1.58 %,
5.8 -> 8.6 s per page, native heap about 110 -> 300 MB on 600 dpi pages (65 -> 113 MB at
300 dpi). The 2x step also doubles every word-box coordinate.

| | A current | B opt-in method | C on by default | D documented recipe |
|---|---|---|---|---|
| weighted score | 0.545 | **0.723** | 0.468 | 0.719 |
| measured criteria only | 0.529 | 0.712 | 0.447 | 0.712 |
| wins under 5000 weightings | 0 % | 57 % | 0 % | 43 % |

B and D tie on the measured evidence; they differ only on judgment criteria (effort for
an app vs. API surface to maintain). C ranks below the current state.

## The two conditions, measured (2026-10-12)

**Where the gain comes from.** Darkest channel + normalization without the 2x step
("minlight") scores 0.564 % CER on the 419 synthetic JPEGs, no better than nothing
(0.544 %; 52 files better, 109 worse). The gain needs the 2x step.

**Size limit ("capped": up to 2x, at most 20 megapixels).** On the synthetic pages it is
identical to the uncapped pipeline (all 105 checked pages scaled 2x, same 0.285 % CER).
On the 15 book pages the 600 dpi scans are not upscaled and the 300 dpi ones are:

| book, 15 pages | none | uncapped | capped |
|---|---|---|---|
| words found | 99.51 % | 99.49 % | 99.60 % |
| extra (junk) | 1.72 % | 1.58 % | 1.39 % |
| seconds per page | 5.8 | 8.6 | 6.7 |
| native heap, 600 dpi page | 109 MB | 300 MB | 127 MB |
| native heap, 300 dpi page | 65 MB | 113 MB | 114 MB |

**Word boxes mapped back to the original image** (score_boxes.py, each word paired with
the same word in the unprocessed run): median edge offset 0.5 px, median IoU 0.945
(synthetic) / 0.985 (book). Boxes overlapping less than half: 3.7 % of synthetic words,
mostly at the same spot (small blurred text segmented differently after scaling, 248 of
280); 1 % on the book, nearly all a repeated word paired with another occurrence.

Re-scored (`score_options.py --capped`): A 0.545, B 0.750, C 0.618, D 0.746; B wins 57 %
and D 43 % of 5000 weightings; on measured criteria alone B and D tie at 0.748.
