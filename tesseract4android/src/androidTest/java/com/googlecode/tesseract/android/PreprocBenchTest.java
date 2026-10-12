package com.googlecode.tesseract.android;

import static org.junit.Assert.assertTrue;
import static org.junit.Assume.assumeTrue;

import android.content.Context;
import android.os.Bundle;
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
 * </ul>
 * Optional arguments: {@code dir} (default jpegbench), {@code variants} (comma-separated) and
 * {@code from} (skip files whose name sorts before it, to resume a run).
 * Runs only with the instrumentation argument {@code preprocbench}; reads the corpus from,
 * and writes results to, this test app's external files dir. Scoring is done on the PC.
 */
@RunWith(AndroidJUnit4.class)
@LargeTest
public class PreprocBenchTest {
	private static final String TAG = "PreprocBench";
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
		File[] jpegs = dir.listFiles((d, name) -> name.endsWith(".jpg"));
		assertTrue("no corpus in " + dir, jpegs != null && jpegs.length > 0);
		Arrays.sort(jpegs);

		Assets.extractAssets(context);
		TessBaseAPI api = new TessBaseAPI();
		assertTrue(api.init(Assets.getTessDataPath(context), Assets.getLanguage()));

		File out = new File(base, "preprocbench-" + label + ".tsv");
		try (Writer w = new OutputStreamWriter(new FileOutputStream(out), StandardCharsets.UTF_8)) {
			w.write("variant\tfile\tconf\tms\ttext\n");
			for (File jpg : jpegs) {
				if (jpg.getName().compareTo(from) < 0) continue;
				Log.i(TAG, "file " + jpg.getName());
				Pix decoded = ReadFile.readFile(jpg);
				for (String variant : variants) {
					long t0 = System.nanoTime();
					Pix pix = preprocess(decoded, variant);
					api.setImage(pix);
					String text = api.getUTF8Text();
					long ms = (System.nanoTime() - t0) / 1_000_000;
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
