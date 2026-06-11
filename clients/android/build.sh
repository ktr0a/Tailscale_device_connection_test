#!/usr/bin/env bash
# Builds dist/TailnetChat-debug.apk with the plain Android command-line
# toolchain (aapt2 + javac + d8 + apksigner) — no Gradle needed.
#
# Requirements: JDK 17+, unzip, python3. If no Android SDK is found at
# $ANDROID_HOME / $ANDROID_SDK_ROOT / ~/android-sdk, the needed pieces
# (~200 MB) are downloaded automatically.
set -euo pipefail
cd "$(dirname "$0")"

BT_VER="34.0.0"
PLATFORM="android-34"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/android-sdk}}"
TOOLS_URL="https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"

# --- Ensure SDK pieces exist ---
if [ ! -x "$SDK/build-tools/$BT_VER/aapt2" ] || [ ! -f "$SDK/platforms/$PLATFORM/android.jar" ]; then
    echo ">> Android SDK pieces missing — installing into $SDK"
    SDKMANAGER="$SDK/cmdline-tools/latest/bin/sdkmanager"
    if [ ! -x "$SDKMANAGER" ]; then
        mkdir -p "$SDK/cmdline-tools"
        tmp="$(mktemp -d)"
        curl -fsSL "$TOOLS_URL" -o "$tmp/tools.zip"
        unzip -q "$tmp/tools.zip" -d "$tmp"
        rm -rf "$SDK/cmdline-tools/latest"
        mv "$tmp/cmdline-tools" "$SDK/cmdline-tools/latest"
        rm -rf "$tmp"
    fi
    yes | "$SDKMANAGER" --sdk_root="$SDK" --licenses >/dev/null || true
    "$SDKMANAGER" --sdk_root="$SDK" "platforms;$PLATFORM" "build-tools;$BT_VER" >/dev/null
fi

BT="$SDK/build-tools/$BT_VER"
JAR="$SDK/platforms/$PLATFORM/android.jar"
OUT="build"
DIST="../../dist"
rm -rf "$OUT"
mkdir -p "$OUT/classes" "$OUT/gen" "$DIST"

echo ">> Compiling resources"
"$BT/aapt2" compile --dir res -o "$OUT/res.zip"
"$BT/aapt2" link -o "$OUT/unsigned.apk" -I "$JAR" \
    --manifest AndroidManifest.xml -R "$OUT/res.zip" --auto-add-overlay \
    --min-sdk-version 24 --target-sdk-version 34 \
    --version-code 1 --version-name 0.1.0 \
    --java "$OUT/gen"

echo ">> Compiling Java"
javac --release 8 -classpath "$JAR" -d "$OUT/classes" \
    $(find src "$OUT/gen" -name '*.java') 2> >(grep -v 'source value 8' >&2 || true)

echo ">> Dexing"
"$BT/d8" --release --lib "$JAR" --min-api 24 --output "$OUT" \
    $(find "$OUT/classes" -name '*.class')

echo ">> Packaging"
python3 - "$OUT" <<'PYEOF'
import sys, zipfile
out = sys.argv[1]
with zipfile.ZipFile(f"{out}/unsigned.apk", "a", zipfile.ZIP_DEFLATED) as z:
    z.write(f"{out}/classes.dex", "classes.dex")
PYEOF
"$BT/zipalign" -f 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"

echo ">> Signing (debug key)"
KEYSTORE="$OUT/debug.keystore"
keytool -genkeypair -keystore "$KEYSTORE" -alias androiddebugkey \
    -storepass android -keypass android -keyalg RSA -validity 10000 \
    -dname "CN=Android Debug,O=Android,C=US" 2>/dev/null
"$BT/apksigner" sign --ks "$KEYSTORE" --ks-pass pass:android \
    --out "$DIST/TailnetChat-debug.apk" "$OUT/aligned.apk"
"$BT/apksigner" verify "$DIST/TailnetChat-debug.apk"

echo ">> Built: $(cd "$DIST" && pwd)/TailnetChat-debug.apk"
