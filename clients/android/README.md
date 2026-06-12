# Tailnet Chat — Android app

A native Android app (`.apk`) that opens the group chat full-screen — no
browser, no address bar. It connects to a chat node that is already running
on your tailnet (typically the always-on Raspberry Pi).

Before connecting, the app checks:

1. **Tailscale app installed?** If not: a "Get Tailscale" button (Play Store).
2. **VPN active?** If Tailscale is off: an "Open Tailscale" button.
3. **Node reachable?** A real request to the node's `/local/status` —
   only then does the chat open.

If anything fails you get a clear error screen with Retry / Open Tailscale /
Change node address. The node address is set on first launch and can be
changed any time via the menu (⋮ → "Change node address").

## Install

- **Download:** `dist/TailnetChat-debug.apk` from this repo, or the
  `TailnetChat-android` artifact from the latest
  [GitHub Actions run](../../../../actions).
- Transfer to the phone and open it (allow "install unknown apps" once).
- It is signed with a throwaway debug key: Play Protect will warn, and
  upgrading between APKs from different builds may require uninstalling first.

## Build

```bash
clients/android/build.sh
```

Plain command-line toolchain (aapt2 + javac + d8 + apksigner) — no Gradle,
no IDE. Needs JDK 17+; uses `$ANDROID_HOME` if present, otherwise downloads
the needed SDK pieces (~200 MB) to `~/android-sdk`. Output:
`dist/TailnetChat-debug.apk`.

## Current limitation (by design, for the MVP)

The phone is a **window into an existing node**, not a node itself — it
doesn't keep its own copy of the chatlog, and messages you send from the
phone are stored and labeled under the node device you're connected to
(e.g. `raspberry-pi`). Running a full Python node on Android is on the
roadmap; until then, connect the phone to your always-on device.

If you want the phone to be a **full peer** with its own chatlog and identity,
see [`clients/android-node/`](../android-node/) — it bundles CPython and the
complete node using python-for-android, with a first-run setup screen for the
device name and shared key.
