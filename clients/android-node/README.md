# Tailnet Chat Node — Android (full node)

This APK makes your Android phone a **full peer** in the Tailnet Chat network:
the phone stores its own copy of the chatlog and identity, syncs directly with
your other devices over Tailscale, and can send and receive messages without
depending on any other always-on device.

Compare this to [`clients/android/`](../android/), which is a thin WebView
that connects to a node already running somewhere else on your tailnet.

## First-run setup

On the very first launch (before `config.json` exists in the app's private
storage) the app serves a dark-themed setup form on `http://127.0.0.1:8000/`.
The WebView opens this automatically.

You need to provide:

- **Device name** — a short label shown next to your messages in the chat
  (1–64 chars, e.g. `pixel-8`). Must be unique across your devices; the app
  warns you if there is a name collision.
- **Shared key** — the same secret you configured on every other node (`API_KEY`
  in their `.env` or `config.json`). Must be at least 8 characters. Generate
  one with `openssl rand -hex 32` and use it on every device.

After you tap **Save & Start node** the page polls until the FastAPI node is
up, then redirects to the chat.

## Adding peers

Open the **Devices** page (the gear icon inside the chat) and add each peer by
Tailscale hostname (or IP) + port 8000. Do this on every device so everyone
knows about everyone. A "Ping & sync all now" button forces an immediate sync.

## Android sleep behaviour

Android suspends backgrounded apps to save battery, so the phone node is
offline while the app is not in the foreground.

- **Messages you send** from the phone are **saved locally before delivery**
  and are never lost.
- **Messages sent by others** while the phone is asleep are caught up
  automatically the next time the app comes to the foreground (via the startup
  sync that runs immediately on launch).

A future enhancement (background foreground-service) is on the roadmap; for
now, re-opening the app triggers a full sync within seconds.

## Port

The node always listens on **port 8000** (hardcoded to match `p4a.port = 8000`
in `buildozer.spec`). Add `TAILNET_PORT=<n>` to override during local desktop
testing only.

## Getting the APK

- **CI artifact:** download `TailnetChat-node-android` from the latest
  [GitHub Actions run](../../../../actions) ("Build native clients" workflow).
- **Local build:** see below.

## Building locally (Linux only)

You need Linux, Python 3.10+, JDK 17, and a fast internet connection (first
build downloads the Android SDK + NDK via buildozer, ~3–5 GB).

```bash
# Install build tools
sudo apt-get install git zip unzip openjdk-17-jdk autoconf libtool \
    pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev

pip install 'buildozer==1.5.0' 'cython<3'

# Build
bash clients/android-node/build.sh
# → dist/TailnetChat-node-debug.apk
```

The `--prepare` flag copies the node source into place without running
buildozer (useful for local desktop simulation):

```bash
bash clients/android-node/build.sh --prepare
TAILNET_DATA_DIR=/tmp/phone-test TAILNET_PORT=8000 \
    python clients/android-node/main.py
```

## Signing

The APK is signed with a throwaway debug key. Play Protect will warn when you
sideload it. Upgrading between APKs signed by different debug keys requires
uninstalling first.
