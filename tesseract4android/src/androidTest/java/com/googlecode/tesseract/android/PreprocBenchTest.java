package com.googlecode.tesseract.android;

import static org.junit.Assert.assertTrue;
import static org.junit.Assume.assumeTrue;

import android.content.Context;
import android.os.Bundle;
import android.os.Debug;
import android.util.Log;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.filters.LargeTest;
import androidx.test.platform.app.InstrumentationRegistry;

import com.googlecode.leptonica.android.AdaptiveMap;
import com.googlecode.leptonica.android.Pix;
import com.googlecode.leptonica.android.ReadFile;
import com.googlecode.leptonica.android.Scale;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Locale;

/**
 * Runs Tesseract on each JPEG of the jpegbench corpus after several preprocessing
 * variants, to see which ones reduce OCR errors and whether combining them helps.
 * <ul>
 * <li>base: the decoded image as is</li>
 * <li>light: Leptonica background normalization (AdaptiveMap.backgroundNormMorph)</li>
 * <li>up2x: scaled 2x (Scale.scale)</li>
 * <li>minchan: 8 bpp image of the darkest of R, G, B per pixel, so coloured ink stays dark</li>
 * <li>all3: minchan, then light, then up2x</li>
 * <li>to300: 600 dpi scans (wider than 3000 px) scaled by 0.5; others unchanged</li>
 * <li>lightto300: light, then to300</li>
 * <li>minlight: minchan, then light (all3 without the 2x)</li>
 * <li>capped: minlight, then up to 2x but no larger than {@code capmp} megapixels (default 20)</li>
 * </ul>
 * Optional arguments: {@code dir} (default jpegbench), {@code variants} (comma-separated),
 * {@code from} (skip files whose name sorts before it, to resume a run), {@code step} (take
 * every n-th file), {@code capmp} (megapixel cap for "capped") and {@code boxes} (also write
 * every word's box, mapped back to the decoded image's coordinates).
 * Runs only with the instrumentation argument {@code preprocbench}; reads the corpus from,
 * and writes results to, this test app's external files dir. Scoring is done on the PC.
 */
@RunWith(AndroidJUnit4.class)
@LargeTest
public class PreprocBenchTest {
	private static final String TAG = "PreprocBench";
	private static float capMegapixels = 20f;
	private static final String DEFAULT_VARIANTS = "base,light,up2x,minchan,all3";

	@Test
	public void bench() throws Exception {
		Bundle args = InstrumentationRegistry.getArguments();
		assumeTrue("pass -e preprocbench <label> to run", args.getString("preprocbench") != null);
		String label = args.getString("preprocbench");

		Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
		File base = context.getExternalFilesDir(null);
		File dir = new File(base, args.getString("dir", "jpegbench"));
		String[] variants = args.getString("variants", DEFAULT_VARIANTS).split(",");
		String from = args.getString("from", "");  // resume: skip files sorting before this name
		int step = Integer.parseInt(args.getString("step", "1"));  // take every step-th file
		boolean boxes = args.getString("boxes") != null;
		capMegapixels = Float.parseFloat(args.getString("capmp", "20"));
		File[] jpegs = dir.listFiles((d, name) -> name.endsWith(".jpg"));
		assertTrue("no corpus in " + dir, jpegs != null && jpegs.length > 0);
		Arrays.sort(jpegs);

		Assets.extractAssets(context);
		TessBaseAPI api = new TessBaseAPI();
		assertTrue(api.init(Assets.getTessDataPath(context), Assets.getLanguage()));

		File out = new File(base, "preprocbench-" + label + ".tsv");
		File boxOut = new File(base, "preprocbench-" + label + "-boxes.tsv");
		try (Writer w = new OutputStreamWriter(new FileOutputStream(out), StandardCharsets.UTF_8);
			 Writer wb = new OutputStreamWriter(new FileOutputStream(boxOut), StandardCharsets.UTF_8)) {
			w.write("variant\tfile\tconf\tms\ttext\n");
			wb.write("variant\tfile\tword\tconf\tleft\ttop\tright\tbottom\n");
			int index = -1;
			for (File jpg : jpegs) {
				if (jpg.getName().compareTo(from) < 0) continue;
				if (++index % step != 0) continue;
				Log.i(TAG, "file " + jpg.getName());
				Pix decoded = ReadFile.readFile(jpg);
				for (String variant : variants) {
					long t0 = System.nanoTime();
					Pix pix = preprocess(decoded, variant);
					api.setImage(pix);
					String text = api.getUTF8Text();
					long ms = (System.nanoTime() - t0) / 1_000_000;
					// Word boxes, mapped back to the decoded image's coordinates
					double sx = (double) decoded.getWidth() / pix.getWidth();
					double sy = (double) decoded.getHeight() / pix.getHeight();
					if (boxes) {
						ResultIterator it = api.getResultIterator();
						it.begin();
						do {
							String word = it.getUTF8Text(TessBaseAPI.PageIteratorLevel.RIL_WORD);
							if (word == null) continue;
							int[] b = it.getBoundingBox(TessBaseAPI.PageIteratorLevel.RIL_WORD);
							wb.write(variant + "\t" + jpg.getName() + "\t" + word.replace("\t", " ") + "\t"
									+ it.confidence(TessBaseAPI.PageIteratorLevel.RIL_WORD)
									+ String.format(Locale.ROOT, "\t%.1f\t%.1f\t%.1f\t%.1f\n",
									b[0] * sx, b[1] * sy, b[2] * sx, b[3] * sy));
						} while (it.next(TessBaseAPI.PageIteratorLevel.RIL_WORD));
						it.delete();
					}
					Log.i(TAG, "mem " + variant + " " + jpg.getName() + " " + pix.getWidth() + "x" + pix.getHeight()
							+ "x" + pix.getDepth() + " scale=" + String.format(Locale.ROOT, "%.3f", 1 / sx)
							+ " native_heap_mb=" + Debug.getNativeHeapAllocatedSize() / (1024 * 1024));
					w.write(variant + "\t" + jpg.getName() + "\t" + api.meanConfidence() + "\t" + ms + "\t"
							+ text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n") + "\n");
					if (pix != decoded) pix.recycle();
				}
				decoded.recycle();
			}
		} finally {
			api.recycle();
		}
		Log.i(TAG, "wrote " + out);
	}

	private static Pix preprocess(Pix pix, String variant) {
		switch (variant) {
			case "light":
				return AdaptiveMap.backgroundNormMorph(pix);
			case "up2x":
				return Scale.scale(pix, 2f);
			case "minchan":
				return minChannel(pix);
			case "minlight": {
				Pix a = minChannel(pix);
				Pix b = AdaptiveMap.backgroundNormMorph(a);
				if (a != pix) a.recycle();
				return b;
			}
			case "capped": {
				// minlight, then upscale by up to 2x, but never beyond capMegapixels
				Pix b = preprocess(pix, "minlight");
				double pixels = (double) b.getWidth() * b.getHeight();
				double scale = Math.min(2.0, Math.sqrt(capMegapixels * 1e6 / pixels));
				if (scale < 1.05) return b;
				Pix c = Scale.scale(b, (float) scale);
				b.recycle();
				return c;
			}
			case "to300":
				return pix.getWidth() > 3000 ? Scale.scale(pix, 0.5f) : pix;
			case "lightto300": {
				Pix a = AdaptiveMap.backgroundNormMorph(pix);
				if (a.getWidth() <= 3000) return a;
				Pix b = Scale.scale(a, 0.5f);
				a.recycle();
				return b;
			}
			case "all3": {
				Pix a = minChannel(pix);
				Pix b = AdaptiveMap.backgroundNormMorph(a);
				Pix c = Scale.scale(b, 2f);
				if (a != pix) a.recycle();
				b.recycle();
				return c;
			}
			default:
				return pix;
		}
	}

	/** 8 bpp image whose value is min(R, G, B); grayscale input is returned unchanged. */
	private static Pix minChannel(Pix pix) {
		if (pix.getDepth() != 32) return pix;
		int w = pix.getWidth();
		int h = pix.getHeight();
		byte[] src = pix.getData();  // one little-endian word per pixel: A, B, G, R
		byte[] dst = new byte[w * h];
		for (int i = 0; i < w * h; i++) {
			int b = src[4 * i + 1] & 0xFF;
			int g = src[4 * i + 2] & 0xFF;
			int r = src[4 * i + 3] & 0xFF;
			dst[i] = (byte) Math.min(r, Math.min(g, b));
		}
		return ReadFile.readBytes8(dst, w, h);
	}
}
