"""Tailnet Chat — Windows desktop wrapper.

Runs the full chat node in the background and shows the UI in a native
window (WebView2 via pywebview). No browser or terminal needed: this
device is a complete peer in the group chat.

Dev run:  python app.py            (uses ../../node from the repo)
Build:    build.bat                (PyInstaller one-file TailnetChat.exe)

Config and chat data live in %APPDATA%\\TailnetChat (or ~/.config/TailnetChat),
never next to the exe, so the app can run from Downloads.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request

APP_NAME = "TailnetChat"
DEFAULT_PORT = 8000


def app_data_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


CONFIG_PATH = os.path.join(app_data_dir(), "config.json")


def node_dir() -> str:
    if getattr(sys, "frozen", False):  # inside the PyInstaller bundle
        return os.path.join(sys._MEIPASS, "node")
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "node"))


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


# --- Tailscale health check ---

def find_tailscale():
    exe = shutil.which("tailscale")
    if exe:
        return exe
    candidates = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Tailscale", "tailscale.exe"),
        "/usr/bin/tailscale",
        "/usr/local/bin/tailscale",
        "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def tailscale_status() -> dict:
    """Best-effort Tailscale check; never raises."""
    exe = find_tailscale()
    if not exe:
        return {"installed": False, "running": False, "ip": None,
                "detail": "Tailscale not found — install it from tailscale.com and sign in."}
    try:
        out = subprocess.run([exe, "status", "--json"], capture_output=True, text=True, timeout=10)
        data = json.loads(out.stdout) if out.stdout.strip() else {}
        state = data.get("BackendState", "Unknown")
        running = state == "Running"
        ip = None
        if running:
            ips = data.get("Self", {}).get("TailscaleIPs") or []
            ip = next((i for i in ips if "." in i), None)
        detail = {
            "Running": f"Connected{f' — this device is {ip}' if ip else ''}",
            "Stopped": "Tailscale is stopped — open Tailscale and connect.",
            "NeedsLogin": "Tailscale needs login — open Tailscale and sign in.",
        }.get(state, f"Tailscale state: {state}")
        return {"installed": True, "running": running, "ip": ip, "detail": detail}
    except Exception as e:  # CLI hiccups must never block the launcher
        return {"installed": True, "running": False, "ip": None, "detail": f"Could not query Tailscale: {e}"}


# --- Embedded node server ---

_server_started = False


def node_already_serving(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/local/status", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def start_server(cfg: dict):
    """Start the chat node in a daemon thread.

    Returns (mode, url) where mode is "started" or "reused" (a node is
    already listening on this port, e.g. one running as a service — just
    attach to it instead of failing on a busy port).
    """
    global _server_started
    port = int(cfg["port"])
    url = f"http://127.0.0.1:{port}/"
    if _server_started:
        return ("started", url)
    if node_already_serving(port):
        return ("reused", url)

    os.environ["API_KEY"] = cfg["api_key"]
    os.environ["DEVICE_NAME"] = cfg["device_name"]
    os.environ["DATA_DIR"] = os.path.join(app_data_dir(), "data")
    sys.path.insert(0, node_dir())
    import uvicorn
    import main as node_main  # the node app; env must be set before this import

    config = uvicorn.Config(node_main.app, host="0.0.0.0", port=port,
                            loop="asyncio", http="h11", ws="none", log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 15
    while time.time() < deadline:
        if not thread.is_alive():
            raise RuntimeError(f"Node failed to start — is port {port} already used by another program?")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
            _server_started = True
            return ("started", url)
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("Node did not come up within 15 seconds")


# --- Launcher window ---

class Api:
    """Methods callable from the launcher page via window.pywebview.api."""

    def get_state(self):
        cfg = load_config() or {}
        return {
            "config": {
                "device_name": cfg.get("device_name", ""),
                "api_key": cfg.get("api_key", ""),
                "port": cfg.get("port", DEFAULT_PORT),
                "exists": bool(cfg),
            },
            "tailscale": tailscale_status(),
            "config_path": CONFIG_PATH,
        }

    def start_chat(self, device_name, api_key, port):
        device_name = (device_name or "").strip()
        api_key = (api_key or "").strip()
        try:
            port = int(port)
        except (TypeError, ValueError):
            return {"ok": False, "error": "Port must be a number."}
        if not 1 <= port <= 65535:
            return {"ok": False, "error": "Port must be between 1 and 65535."}
        if not 1 <= len(device_name) <= 64:
            return {"ok": False, "error": "Enter a device name (max 64 characters)."}
        if len(api_key) < 8:
            return {"ok": False, "error": "The shared key must be at least 8 characters — use the same one on every device."}
        cfg = {"device_name": device_name, "api_key": api_key, "port": port}
        save_config(cfg)
        try:
            mode, url = start_server(cfg)
        except RuntimeError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "url": url, "mode": mode}


LAUNCHER_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  * { box-sizing: border-box; margin: 0; font-family: system-ui, "Segoe UI", sans-serif; }
  body { background: #0e1418; color: #e4e9ec; padding: 26px 28px; font-size: 15px; }
  h1 { font-size: 21px; margin-bottom: 4px; }
  .sub { color: #8a9aa5; font-size: 13px; margin-bottom: 18px; }
  .ts { display: flex; gap: 10px; align-items: flex-start; background: #1a2228; border-radius: 10px;
        padding: 11px 13px; margin-bottom: 18px; font-size: 13.5px; }
  .ts .dot { width: 10px; height: 10px; border-radius: 50%; background: #5a6a74; margin-top: 4px; flex: none; }
  .ts.ok .dot { background: #28b487; } .ts.bad .dot { background: #c75450; }
  .ts a { color: #28b487; cursor: pointer; text-decoration: underline; margin-left: auto; flex: none; }
  label { display: block; color: #8a9aa5; font-size: 12.5px; margin: 12px 0 4px; }
  input { width: 100%; padding: 10px 12px; border-radius: 8px; border: none; background: #232e36;
          color: #e4e9ec; outline: none; font-size: 14.5px; }
  button { width: 100%; margin-top: 22px; padding: 12px; border: none; border-radius: 10px;
           background: #28b487; color: #06281c; font-size: 15.5px; font-weight: 700; cursor: pointer; }
  button:disabled { opacity: .55; cursor: default; }
  .err { color: #c75450; font-size: 13px; margin-top: 12px; min-height: 18px; }
  .path { color: #5a6a74; font-size: 11px; margin-top: 14px; word-break: break-all; }
</style></head>
<body>
  <h1>Tailnet Chat</h1>
  <div class="sub">This device becomes a full chat node on your tailnet.</div>
  <div class="ts" id="ts"><span class="dot"></span><span id="ts-text">Checking Tailscale…</span><a id="ts-refresh">recheck</a></div>
  <label>Device name (how you appear in the chat)</label>
  <input id="name" maxlength="64" placeholder="e.g. gaming-pc">
  <label>Shared key (identical on every device)</label>
  <input id="key" placeholder="openssl rand -hex 32 — paste the same value everywhere">
  <label>Port</label>
  <input id="port" value="8000">
  <button id="start">Start chat</button>
  <div class="err" id="err"></div>
  <div class="path" id="path"></div>
<script>
  const $ = (id) => document.getElementById(id);
  async function refreshState() {
    const s = await window.pywebview.api.get_state();
    $("name").value = s.config.device_name || "";
    $("key").value = s.config.api_key || "";
    $("port").value = s.config.port;
    $("path").textContent = "Config: " + s.config_path;
    renderTs(s.tailscale);
  }
  function renderTs(ts) {
    const box = $("ts");
    box.className = "ts " + (ts.running ? "ok" : "bad");
    $("ts-text").textContent = ts.detail;
  }
  $("ts-refresh").addEventListener("click", async () => {
    $("ts-text").textContent = "Checking Tailscale…";
    renderTs((await window.pywebview.api.get_state()).tailscale);
  });
  $("start").addEventListener("click", async () => {
    $("err").textContent = "";
    $("start").disabled = true;
    $("start").textContent = "Starting…";
    const r = await window.pywebview.api.start_chat($("name").value, $("key").value, $("port").value);
    if (r.ok) {
      window.location.href = r.url;
    } else {
      $("err").textContent = r.error;
      $("start").disabled = false;
      $("start").textContent = "Start chat";
    }
  });
  window.addEventListener("pywebviewready", refreshState);
</script>
</body></html>
"""


def main():
    import webview  # imported late so server logic stays usable headless

    webview.create_window("Tailnet Chat", html=LAUNCHER_HTML, js_api=Api(),
                          width=480, height=680, min_size=(390, 540))
    webview.start()


if __name__ == "__main__":
    main()
