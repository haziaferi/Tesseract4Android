package com.googlecode.tesseract.android;

import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import android.content.Context;
import android.content.res.AssetManager;
import android.os.Build;
import android.util.Log;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.filters.LargeTest;
import androidx.test.platform.app.InstrumentationRegistry;

import com.googlecode.leptonica.android.Pix;
import com.googlecode.leptonica.android.ReadFile;
import com.googlecode.leptonica.android.WriteFile;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Pins the exact output of the bundled native libraries, so that an upgrade of
 * libpng, libjpeg, Leptonica or Tesseract shows every pixel, byte and word it changes.
 * <p>
 * For each image in assets/golden it records whether the native decoder accepted it
 * (a rejected file silently falls back to BitmapFactory in ReadFile.readFile), the
 * decoded size and depth, and a hash of the pixel data. It then re-encodes some of
 * them and runs OCR on ocr_sample.jpg.
 * <p>
 * The expected values live in assets/golden/expected-&lt;abi&gt;.tsv. Every run logs the
 * actual values under the tag GoldenOutput, so a new baseline is captured with
 * {@code adb logcat -s GoldenOutput:I} and reviewed before it is committed.
 */
@RunWith(AndroidJUnit4.class)
@LargeTest
public class GoldenOutputTest {
	private static final String TAG = "GoldenOutput";
	private static final String DIR = "golden";

	/** Decoded images that are written back out, and the extension that picks the encoder. */
	private static final String[][] ENCODE = {
			{"png_1bit.png", "png"},
			{"png_8bit_gray.png", "png"},
			{"png_palette_trns.png", "png"},
			{"png_rgb.png", "png"},
			{"png_rgba.png", "png"},
			{"jpg_420.jpg", "jpg"},
			{"jpg_gray.jpg", "jpg"},
	};

	@Test
	public void nativeOutputMatchesGolden() throws Exception {
		Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
		AssetManager am = context.getAssets();
		File work = new File(context.getCacheDir(), DIR);
		assertTrue(work.isDirectory() || work.mkdirs());

		Map<String, String> actual = new LinkedHashMap<>();
		Map<String, Pix> decoded = new LinkedHashMap<>();

		String[] names = am.list(DIR);
		assertTrue("no golden corpus in assets/" + DIR, names != null && names.length > 0);
		Arrays.sort(names);
		for (String name : names) {
			if (name.endsWith(".tsv")) continue;
			File file = copyAsset(am, DIR + "/" + name, new File(work, name));
			Pix pix = ReadFile.readFile(file);
			if (pix == null) {
				actual.put("decode\t" + name, "null");
				continue;
			}
			// A natively decoded Pix keeps its input format; the BitmapFactory fallback reports 0.
			actual.put("decode\t" + name, "format=" + pix.getImageFormat()
					+ "\t" + pix.getWidth() + "x" + pix.getHeight() + "x" + pix.getDepth()
					+ "\tdata=" + sha256(pix.getData()));
			decoded.put(name, pix);
		}

		for (String[] e : ENCODE) {
			Pix pix = decoded.get(e[0]);
			if (pix == null) {
				actual.put("encode\t" + e[0], "no-input");
				continue;
			}
			if (e[1].equals("jpg")) {
				for (boolean progressive : new boolean[]{false, true}) {
					File out = new File(work, "out-" + progressive + "-" + e[0]);
					boolean ok = WriteFile.writeImpliedFormat(pix, out, 85, progressive);
					actual.put("encode\t" + e[0] + (progressive ? " progressive" : " baseline") + " q85",
							ok ? "bytes=" + sha256(readAll(out)) : "failed");
				}
			} else {
				File out = new File(work, "out-" + e[0]);
				boolean ok = WriteFile.writeImpliedFormat(pix, out);
				actual.put("encode\t" + e[0], ok ? "bytes=" + sha256(readAll(out)) : "failed");
			}
		}

		Assets.extractAssets(context);
		TessBaseAPI api = new TessBaseAPI();
		assertTrue("Tesseract init failed", api.init(Assets.getTessDataPath(context), Assets.getLanguage()));
		try {
			Pix pix = decoded.get("ocr_sample.jpg");
			if (pix == null) {
				actual.put("ocr\tocr_sample.jpg", "no-input");
			} else {
				api.setImage(pix);
				String text = api.getUTF8Text();
				actual.put("ocr\tocr_sample.jpg", "conf=" + api.meanConfidence()
						+ "\ttext=" + sha256(text.getBytes(StandardCharsets.UTF_8))
						+ "\thocr=" + sha256(api.getHOCRText(0).getBytes(StandardCharsets.UTF_8))
						+ "\t" + text.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t"));
			}
			Log.i(TAG, "info\ttesseract=" + api.getVersion() + "\tabi=" + abi());
		} finally {
			api.recycle();
			for (Pix pix : decoded.values()) pix.recycle();
		}

		for (Map.Entry<String, String> line : actual.entrySet()) {
			Log.i(TAG, line.getKey() + "\t" + line.getValue());
		}

		String expectedName = DIR + "/expected-" + abi() + ".tsv";
		Map<String, String> expected = readExpected(am, expectedName);
		if (expected == null) {
			fail("No baseline at assets/" + expectedName + "; the actual values are in logcat under "
					+ TAG + ". Review them and commit them as the baseline.");
		}

		List<String> diffs = new ArrayList<>();
		for (Map.Entry<String, String> line : actual.entrySet()) {
			String want = expected.get(line.getKey());
			if (!line.getValue().equals(want)) {
				diffs.add(line.getKey() + "\n    expected: " + want + "\n    actual:   " + line.getValue());
			}
		}
		for (String key : expected.keySet()) {
			if (!actual.containsKey(key)) diffs.add(key + "\n    expected: " + expected.get(key) + "\n    actual:   (missing)");
		}
		if (!diffs.isEmpty()) {
			fail(diffs.size() + " output(s) differ from assets/" + expectedName + ":\n" + String.join("\n", diffs));
		}
	}

	private static String abi() {
		return Build.SUPPORTED_ABIS[0];
	}

	private static Map<String, String> readExpected(AssetManager am, String name) throws IOException {
		InputStream in;
		try {
			in = am.open(name);
		} catch (IOException missing) {
			return null;
		}
		Map<String, String> map = new LinkedHashMap<>();
		try (BufferedReader r = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
			String line;
			while ((line = r.readLine()) != null) {
				if (line.isEmpty() || line.startsWith("#") || line.startsWith("info\t")) continue;
				// key = kind TAB name, value = the rest
				int first = line.indexOf('\t');
				int second = first < 0 ? -1 : line.indexOf('\t', first + 1);
				if (second < 0) continue;
				map.put(line.substring(0, second), line.substring(second + 1));
			}
		}
		return map;
	}

	private static File copyAsset(AssetManager am, String asset, File out) throws IOException {
		try (InputStream in = am.open(asset); OutputStream os = new FileOutputStream(out)) {
			byte[] buf = new byte[8192];
			int n;
			while ((n = in.read(buf)) != -1) os.write(buf, 0, n);
		}
		return out;
	}

	private static byte[] readAll(File file) throws IOException {
		try (InputStream in = new FileInputStream(file)) {
			byte[] data = new byte[(int) file.length()];
			int off = 0;
			while (off < data.length) {
				int n = in.read(data, off, data.length - off);
				if (n < 0) break;
				off += n;
			}
			return data;
		}
	}

	private static String sha256(byte[] data) throws NoSuchAlgorithmException {
		if (data == null) return "null";
		StringBuilder sb = new StringBuilder();
		for (byte b : MessageDigest.getInstance("SHA-256").digest(data)) {
			sb.append(String.format("%02x", b));
		}
		return sb.substring(0, 16);
	}
}
