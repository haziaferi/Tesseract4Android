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
