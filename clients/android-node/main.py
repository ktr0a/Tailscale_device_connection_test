"""Tailnet Chat — android-node entrypoint.

This is the python-for-android (p4a) webview bootstrap entry point.
It runs as the main app process on Android and serves the Tailnet Chat
FastAPI node on localhost:8000 (or $TAILNET_PORT for desktop testing).

Data directory priority:
  1. $TAILNET_DATA_DIR env var  (desktop override)
  2. $ANDROID_PRIVATE/tailnet_chat  (p4a sets this on device)
  3. ./data-android  (next to this file, fallback)

On first run (or if config.json is missing/invalid), serves a dark-themed
setup form via stdlib http.server, then hands off to uvicorn.
"""

import html
import http.server
import json
import os
import sys
import traceback
import urllib.parse


# ---------------------------------------------------------------------------
# Data directory and port resolution
# ---------------------------------------------------------------------------

def resolve_data_dir():
    if os.environ.get("TAILNET_DATA_DIR"):
        return os.environ["TAILNET_DATA_DIR"]
    android_private = os.environ.get("ANDROID_PRIVATE")
    if android_private:
        return os.path.join(android_private, "tailnet_chat")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data-android")


DATA_DIR = resolve_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)

PORT = int(os.environ.get("TAILNET_PORT", "8000"))
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config():
    """Return (device_name, api_key) or (None, None) if invalid/missing."""
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        name = (cfg.get("device_name") or "").strip()
        key = (cfg.get("api_key") or "").strip()
        if name and key and len(key) >= 8:
            return name, key
    except (OSError, json.JSONDecodeError, KeyError):
        pass
    return None, None


def write_config(device_name, api_key):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"device_name": device_name, "api_key": api_key}, f)
    os.replace(tmp, CONFIG_PATH)


# ---------------------------------------------------------------------------
# Setup form HTML
# ---------------------------------------------------------------------------

SETUP_FORM_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tailnet Chat — First-run setup</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0e1418;
    color: #e4e9ec;
    font-family: system-ui, -apple-system, sans-serif;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
  }}
  .panel {{
    background: #232e36;
    border-radius: 12px;
    padding: 2rem 1.75rem;
    max-width: 420px;
    width: 100%;
  }}
  h1 {{ font-size: 1.4rem; color: #28b487; margin-bottom: 0.4rem; }}
  .subtitle {{ font-size: 0.9rem; color: #8ca0ad; margin-bottom: 1.5rem; line-height: 1.5; }}
  label {{ display: block; font-size: 0.85rem; color: #8ca0ad; margin-bottom: 0.25rem; margin-top: 1rem; }}
  input {{
    width: 100%;
    padding: 0.65rem 0.85rem;
    background: #0e1418;
    border: 1px solid #3a4a55;
    border-radius: 7px;
    color: #e4e9ec;
    font-size: 1rem;
    outline: none;
  }}
  input:focus {{ border-color: #28b487; }}
  .error {{ color: #e05c5c; font-size: 0.88rem; margin-top: 1rem; }}
  button {{
    margin-top: 1.5rem;
    width: 100%;
    padding: 0.75rem;
    background: #28b487;
    color: #0e1418;
    font-size: 1rem;
    font-weight: 700;
    border: none;
    border-radius: 8px;
    cursor: pointer;
  }}
  button:active {{ background: #1f9a72; }}
</style>
</head>
<body>
<div class="panel">
  <h1>Tailnet Chat Node</h1>
  <p class="subtitle">
    This phone will become a <strong>full chat node</strong>: it stores its own
    copy of the chatlog and syncs directly with your other devices over Tailscale.
    Choose a device name and enter the shared key that every device uses.
  </p>
  {error_block}
  <form method="POST" action="/save">
    <label for="device_name">Device name (shown in chat)</label>
    <input id="device_name" name="device_name" maxlength="64"
           placeholder="my-phone" value="{device_name}" required>
    <label for="api_key">Shared key</label>
    <input id="api_key" name="api_key" type="text" maxlength="128"
           placeholder="Must be identical on every device (≥ 8 chars)" value="{api_key}">
    <button type="submit">Save &amp; Start node</button>
  </form>
</div>
</body>
</html>
"""

STARTING_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tailnet Chat — Starting…</title>
<style>
  body { background: #0e1418; color: #e4e9ec; font-family: system-ui, sans-serif;
          display: flex; align-items: center; justify-content: center;
          min-height: 100vh; text-align: center; }
  .msg { color: #28b487; font-size: 1.2rem; }
</style>
<script>
  (function poll() {
    fetch('/local/status').then(function(r) {
      if (r.ok) { location.href = '/'; return; }
      setTimeout(poll, 1000);
    }).catch(function() { setTimeout(poll, 1000); });
  })();
</script>
</head>
<body><p class="msg">Starting node…</p></body>
</html>
"""

ERROR_PAGE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tailnet Chat — Startup error</title>
<style>
  body {{ background: #0e1418; color: #e4e9ec; font-family: monospace;
          padding: 2rem; }}
  pre {{ background: #1a2530; padding: 1rem; border-radius: 6px;
         color: #e05c5c; white-space: pre-wrap; word-break: break-word; }}
  h1 {{ color: #e05c5c; margin-bottom: 1rem; }}
</style>
</head>
<body>
<h1>Startup error</h1>
<pre>{traceback_text}</pre>
</body>
</html>
"""


def render_setup_form(error="", device_name="", api_key=""):
    error_html = html.escape(error, quote=True) if error else ""
    error_block = f'<p class="error">{error_html}</p>' if error_html else ""
    return SETUP_FORM_HTML.format(
        error_block=error_block,
        device_name=html.escape(device_name, quote=True),
        api_key=html.escape(api_key, quote=True),
    )


# ---------------------------------------------------------------------------
# Setup HTTP handler (stdlib, loopback-only)
# ---------------------------------------------------------------------------

class SetupHandler(http.server.BaseHTTPRequestHandler):

    _shutdown_flag = False  # set by POST /save on success to trigger server shutdown

    def is_loopback(self):
        ip = self.client_address[0]
        return ip.startswith("127.") or ip == "::1"

    def send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.is_loopback():
            self.send_error(403, "node not configured yet")
            return
        # Only serve the setup form at the root path.
        # Every other path (including /local/status polled by the "Starting…"
        # page) must return 503 so the poll JS keeps retrying until the real
        # node (uvicorn) is up and can answer with 200.
        parsed_path = urllib.parse.urlparse(self.path).path
        if parsed_path != "/":
            self.send_html("Service unavailable — node not started yet.", status=503)
            return
        self.send_html(render_setup_form())

    def do_POST(self):
        if not self.is_loopback():
            self.send_error(403, "node not configured yet")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(body, keep_blank_values=True)

        device_name = params.get("device_name", [""])[0].strip()
        api_key = params.get("api_key", [""])[0].strip()

        # Validate
        errors = []
        if not device_name or len(device_name) < 1 or len(device_name) > 64:
            errors.append("Device name must be 1–64 characters.")
        if len(api_key) < 8:
            errors.append("Shared key must be at least 8 characters.")

        if errors:
            self.send_html(
                render_setup_form(" ".join(errors), device_name=device_name, api_key=api_key),
                status=400,
            )
            return

        # Write config atomically
        write_config(device_name, api_key)

        # Respond with "starting" page, then flag the server to stop.
        # The response is fully written before we set the flag, so
        # serve_forever()'s next timeout wake-up will exit cleanly.
        self.send_html(STARTING_HTML)
        SetupHandler._shutdown_flag = True

    def log_message(self, format, *args):
        pass  # suppress per-request log noise


class _ShutdownServer(http.server.HTTPServer):
    """HTTPServer that checks SetupHandler._shutdown_flag after each request."""

    # handle_request() uses self.timeout as its select() timeout, so the
    # serve_forever loop re-checks the flag at least every second even when
    # there is no incoming traffic.
    timeout = 1.0

    def serve_forever(self, poll_interval=0.3):
        while not SetupHandler._shutdown_flag:
            self.handle_request()


# ---------------------------------------------------------------------------
# Setup flow
# ---------------------------------------------------------------------------

def run_setup_server():
    """Serve setup form, block until config saved, then return."""
    SetupHandler._shutdown_flag = False
    server = _ShutdownServer(("127.0.0.1", PORT), SetupHandler)
    server.serve_forever()
    server.server_close()


# ---------------------------------------------------------------------------
# Error crash-page server
# ---------------------------------------------------------------------------

def run_error_server(tb_text):
    """Serve the crash traceback on the port (loopback-only)."""
    html = ERROR_PAGE_HTML.format(traceback_text=tb_text.replace("<", "&lt;").replace(">", "&gt;"))

    class ErrorHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            ip = self.client_address[0]
            if not (ip.startswith("127.") or ip == "::1"):
                self.send_error(403, "node not configured yet")
                return
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", PORT), ErrorHandler)
    server.serve_forever()


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def main():
    try:
        device_name, api_key = load_config()

        if not device_name or not api_key:
            # First-run: serve setup form until config saved
            run_setup_server()
            # Reload config
            device_name, api_key = load_config()
            if not device_name or not api_key:
                raise RuntimeError("Config still invalid after setup — should not happen.")

        # Export config as env vars for the node
        os.environ["API_KEY"] = api_key
        os.environ["DEVICE_NAME"] = device_name
        os.environ["DATA_DIR"] = DATA_DIR

        # Insert the bundled node into sys.path
        node_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "node")
        if node_dir not in sys.path:
            sys.path.insert(0, node_dir)

        import uvicorn
        import main as node_main  # noqa: F401 (imported for its side effects / app object)

        config = uvicorn.Config(
            node_main.app,
            host="0.0.0.0",
            port=PORT,
            loop="asyncio",
            http="h11",
            ws="none",
            log_level="info",
        )
        server = uvicorn.Server(config)
        server.run()  # blocks until shutdown

    except Exception:
        tb_text = traceback.format_exc()
        # Write crash log
        crash_log = os.path.join(DATA_DIR, "crash.log")
        try:
            with open(crash_log, "w") as f:
                f.write(tb_text)
        except OSError:
            pass
        # Serve error page so the WebView never shows a white screen
        run_error_server(tb_text)


if __name__ == "__main__":
    main()
