package com.googlecode.tesseract.android;

import static org.junit.Assert.assertTrue;
import static org.junit.Assume.assumeTrue;

import android.content.Context;
import android.os.Bundle;
import android.util.Log;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.filters.LargeTest;
import androidx.test.platform.app.InstrumentationRegistry;

import com.googlecode.leptonica.android.Pix;
import com.googlecode.leptonica.android.ReadFile;
import com.googlecode.leptonica.android.WriteFile;

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
 * Measures the bundled libjpeg on a text corpus: fidelity of each decoded JPEG to its
 * lossless original (PSNR), decode time, and Tesseract's output on it. It also encodes
 * each original through Leptonica's JPEG writer and measures the same on the result.
 * <p>
 * Runs only when the instrumentation argument {@code jpegbench} is given. The corpus
 * (tools/jpegbench/make_corpus.py) is read from, and results are written to, this test
 * app's external files dir. Character error rates are computed on the PC from the
 * results file, against the .txt ground truth.
 */
@RunWith(AndroidJUnit4.class)
@LargeTest
public class JpegBenchTest {
	private static final String TAG = "JpegBench";

	@Test
	public void bench() throws Exception {
		Bundle args = InstrumentationRegistry.getArguments();
		assumeTrue("pass -e jpegbench <label> to run", args.getString("jpegbench") != null);
		String label = args.getString("jpegbench");

		Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
		File base = context.getExternalFilesDir(null);
		File dir = new File(base, "jpegbench");
		File[] jpegs = dir.listFiles((d, name) -> name.endsWith(".jpg"));
		assertTrue("no corpus in " + dir, jpegs != null && jpegs.length > 0);
		Arrays.sort(jpegs);
		File work = new File(context.getCacheDir(), "jpegbench");
		assertTrue(work.isDirectory() || work.mkdirs());

		Assets.extractAssets(context);
		TessBaseAPI api = new TessBaseAPI();
		assertTrue(api.init(Assets.getTessDataPath(context), Assets.getLanguage()));

		File out = new File(base, "jpegbench-" + label + ".tsv");
		try (Writer w = new OutputStreamWriter(new FileOutputStream(out), StandardCharsets.UTF_8)) {
			w.write("kind\tfile\tformat\tdepth\tpsnr\tdecode_ms\tbytes\tconf\ttext\n");
			// Decoder: the same JPEG bytes for every candidate.
			for (File jpg : jpegs) {
				String name = jpg.getName();
				String page = name.substring(0, name.indexOf("__"));
				boolean gray = name.endsWith("_gray.jpg");
				File origFile = new File(dir, page + (gray ? ".orig_gray.png" : ".orig.png"));

				long t0 = System.nanoTime();
				Pix pix = ReadFile.readFile(jpg);
				long ms = (System.nanoTime() - t0) / 1_000_000;
				Pix orig = ReadFile.readFile(origFile);
				w.write(row(api, "decode", name, pix, orig, ms, jpg.length()));
				pix.recycle();
				orig.recycle();
			}
			// Encoder: Leptonica's JPEG writer on each original, decoded back by the same library.
			File[] origs = dir.listFiles((d, name) -> name.endsWith(".orig.png"));
			Arrays.sort(origs);
			for (File origFile : origs) {
				Pix orig = ReadFile.readFile(origFile);
				for (int q : new int[]{75, 90}) {
					File enc = new File(work, "enc.jpg");
					assertTrue(WriteFile.writeImpliedFormat(orig, enc, q, false));
					Pix pix = ReadFile.readFile(enc);
					String name = origFile.getName().replace(".orig.png", "__enc_q" + q + ".jpg");
					w.write(row(api, "encode", name, pix, orig, -1, enc.length()));
					pix.recycle();
				}
				orig.recycle();
			}
		} finally {
			api.recycle();
		}
		Log.i(TAG, "wrote " + out);
	}

	private static String row(TessBaseAPI api, String kind, String name, Pix pix, Pix orig,
							  long ms, long bytes) {
		api.setImage(pix);
		String text = api.getUTF8Text();
		return kind + "\t" + name + "\t" + pix.getImageFormat() + "\t" + pix.getDepth()
				+ "\t" + String.format(Locale.ROOT, "%.4f", psnr(pix, orig))
				+ "\t" + ms + "\t" + bytes + "\t" + api.meanConfidence()
				+ "\t" + text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n") + "\n";
	}

	/** PSNR over the colour samples of two Pix with the same size and depth (8 or 32 bpp). */
	private static double psnr(Pix a, Pix b) {
		if (a.getWidth() != b.getWidth() || a.getHeight() != b.getHeight() || a.getDepth() != b.getDepth()) {
			return Double.NaN;
		}
		byte[] x = a.getData();
		byte[] y = b.getData();
		boolean rgb = a.getDepth() == 32;
		double sum = 0;
		long n = 0;
		for (int i = 0; i < x.length; i++) {
			// In a 32 bpp word the alpha sample is the low byte, i.e. byte 0 of each
			// little-endian word; it carries nothing for an RGB image.
			if (rgb && (i & 3) == 0) continue;
			int d = (x[i] & 0xFF) - (y[i] & 0xFF);
			sum += d * d;
			n++;
		}
		if (sum == 0) return Double.POSITIVE_INFINITY;
		return 10 * Math.log10(255.0 * 255.0 * n / sum);
	}
}
