#!/usr/bin/env bash
# Build the arm64 test APK for the current libjpeg, install it on a device, run JpegBenchTest.
# Usage: ANDROID_SERIAL=<device> bash tools/jpegbench/bench.sh <label>
# The corpus (make_corpus.py output) and the results live in _work/ at the repo root.
set -u
export MSYS_NO_PATHCONV=1
LABEL=$1
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
A="${ADB:-adb}"
PKG=cz.adaptech.tesseract4android.test
: "${ANDROID_SERIAL:?set ANDROID_SERIAL to the device to use}"
cd "$ROOT" || exit 1

./gradlew --no-daemon -Pandroid.injected.build.abi=arm64-v8a \
  :tesseract4android:assembleStandardDebugAndroidTest > "_work/bench-$LABEL-build.log" 2>&1
echo "build_exit=$?"
APK=tesseract4android/build/intermediates/apk/androidTest/standard/debug/tesseract4android-standard-debug-androidTest.apk
python -I -c "import zipfile,sys; print('abis:', sorted({n.split('/')[1] for n in zipfile.ZipFile(sys.argv[1]).namelist() if n.startswith('lib/')}))" "$APK"
"$A" install -r -t "$APK" | tail -1

DEV=/sdcard/Android/data/$PKG/files
if [ "$("$A" shell ls "$DEV/jpegbench" 2>/dev/null | grep -c '\.jpg$')" != "420" ]; then
  "$A" shell mkdir -p "$DEV/jpegbench"
  "$A" push _work/jpegbench/. "$DEV/jpegbench/" | tail -1
fi
echo "corpus on device: $("$A" shell ls "$DEV/jpegbench" | grep -c '\.jpg$') jpgs"

"$A" shell am instrument -w -e jpegbench "$LABEL" \
  -e class com.googlecode.tesseract.android.JpegBenchTest \
  $PKG/androidx.test.runner.AndroidJUnitRunner > "_work/bench-$LABEL-run.log" 2>&1
tail -3 "_work/bench-$LABEL-run.log"
"$A" pull "$DEV/jpegbench-$LABEL.tsv" "_work/" | tail -1
wc -l "_work/jpegbench-$LABEL.tsv"
