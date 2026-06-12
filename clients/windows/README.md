# Tailnet Chat — Windows app

A single `TailnetChat.exe` that runs the **full chat node** on this PC and
shows the chat in a native window. No browser, no terminal — this device is
a complete peer: it stores its own copy of the chatlog, syncs, and appears
in everyone's device list.

## Get it

- **Download:** grab `TailnetChat.exe` from the latest
  [GitHub Actions run](../../../../actions) ("Build native clients" →
  `TailnetChat-windows` artifact), or
- **Build it yourself** on Windows (Python 3.10+ installed):

  ```bat
  cd clients\windows
  build.bat
  ```

  The exe lands in `clients\windows\dist\` and is copied to the repo's `dist\`.

## First run

1. Make sure Tailscale is installed and connected (the launcher checks this
   and tells you if it isn't — with a *recheck* link).
2. Enter a device name, the shared key (same on all devices), and a port
   (default 8000), then **Start chat**.
3. Windows Firewall will ask once — click **Allow** so other devices can
   reach you. For tighter rules, restrict the port to the Tailscale
   interface in Windows Defender Firewall.
4. Add your other devices under **Devices ⚙** (top right of the chat).

Settings and chat data live in `%APPDATA%\TailnetChat\` — the exe itself can
sit anywhere (Downloads, Desktop, USB stick).

If a node is already running on the chosen port (e.g. installed as a
service), the app detects it and attaches to it instead of starting a
second one.

## Notes

- Needs the WebView2 runtime, which is preinstalled on Windows 10/11.
- The launcher's Tailscale check uses `tailscale status --json`; the app
  still lets you start without Tailscale (e.g. for LAN testing), it just
  warns you.
