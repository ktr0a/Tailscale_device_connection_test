#!/usr/bin/env bash
set -euo pipefail

# Change to the directory containing this script
cd "$(dirname "$(realpath "$0")")"

# Copy the node source into this directory (build-time bundle)
rm -rf node
mkdir node
cp ../../node/*.py node/
cp -r ../../node/static node/

# Copy the launcher icon from the existing Android client
cp ../android/res/mipmap-xxxhdpi/ic_launcher.png icon.png

# If called with --prepare, stop here (used for local desktop simulation)
if [[ "${1:-}" == "--prepare" ]]; then
    echo "Prepared source tree — stopping before buildozer (--prepare mode)."
    exit 0
fi

# Run the buildozer build
buildozer android debug

# Copy the produced APK to dist/
mkdir -p ../../dist
apk_file=$(ls bin/*.apk | head -1)
cp "$apk_file" ../../dist/TailnetChat-node-debug.apk
echo "APK written to dist/TailnetChat-node-debug.apk"
