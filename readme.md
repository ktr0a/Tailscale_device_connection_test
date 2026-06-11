# Tailnet Chat

A private, serverless group chat for your own devices, running entirely over
[Tailscale](https://tailscale.com). Every device (up to ~10) runs the same
small node app and joins one big group chat. No cloud, no public ports, no
single point of failure.

## How it works

There is **no central server and no single source of truth**. Each node:

- keeps its own full copy of the chatlog as JSON on disk (`node/data/chatlog.json`);
- **saves locally before sending** — a message survives even if every other
  device is offline and the sender shuts down right after;
- fans every sent message out to all configured peers immediately;
- **syncs on startup and every ping cycle**: it exchanges logs with each
  reachable peer and both end up with the union. If device A has messages
  from 1, 3 and 5pm and device B has 2, 3, 4 and 5pm, both converge to
  1–5pm automatically;
- **pings all peers every 3 minutes** (configurable) and shows offline
  devices in the chat's top bar.

```text
[laptop :8000] ◄──────► [workstation :8000]
       ▲  ▲                  ▲
       │  └───── sync ───────┤
       ▼                     ▼
        [raspberry pi :8000]      ← every node is identical
```

### Messages and identity

Each message is `{id, device_id, device, message, time}`:

- `id` — a random UUID. Merging is a *union by id*, so duplicates are
  impossible even if the same message arrives via fanout *and* sync.
- `device_id` — a permanent random ID generated on each device's first run
  (stored in `node/data/identity.json`). `device` is just a display label,
  so two devices accidentally configured with the same name **cannot**
  corrupt or mix up storage. The settings page warns you when it detects a
  name conflict, or when a configured address turns out to be the device itself.
- `time` — unix timestamp from the sender's clock. Messages are displayed
  sorted by time (ties broken by id), so all nodes show the same order.
  Tailscale devices are normally NTP-synced; heavy clock skew would only
  affect display order, never data integrity.

## Setup (repeat on every device)

Requirements: Tailscale up and authenticated, Python 3.10+.

```bash
cd node
pip install -r requirements.txt
cp .env.example .env   # then edit it
```

`.env` per device:

```bash
API_KEY=shared_secret_same_on_all_devices   # generate once: openssl rand -hex 32
DEVICE_NAME=laptop                          # unique label for this device
PORT=8000
PING_INTERVAL=180
```

Start the node:

- **Linux/macOS:** `./start.sh`
- **Windows:** double-click `start.bat`

Then open `http://<this-device-tailscale-ip>:8000` in a browser:

- **Chat page (`/`)** — the group chat. Top bar shows every configured
  device with a green/red dot; offline devices are also listed in a banner.
- **Devices page (`/settings`)** — add each other device by name +
  Tailscale IP (or MagicDNS hostname) + port. Do this on every device so
  everyone knows everyone. A "Ping & sync all now" button forces an
  immediate reconciliation.

## Security

- Node-to-node traffic (`/api/*`) requires the shared `API_KEY`
  (`X-API-Key` header).
- The web UI (`/` and `/local/*`) is unauthenticated and trusts the
  tailnet: anyone who can reach the port can read the chat. Keep the port
  off the public internet and ideally bind it to the Tailscale interface:

```bash
sudo ufw allow in on tailscale0 to any port 8000
```

## Persistence (optional)

Run the node as a systemd service so it survives reboots:

```ini
[Unit]
Description=Tailnet Chat Node
After=network.target

[Service]
WorkingDirectory=/path/to/repo/node
EnvironmentFile=/path/to/repo/node/.env
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## Development

- `node/main.py` — FastAPI app: peer API, local UI API, fanout, ping/sync loop.
- `node/storage.py` — atomic JSON persistence (chatlog, peers, identity).
- `node/static/` — the web UI (vanilla HTML/JS/CSS).
- `node/smoke_test.py` — end-to-end test that spins up two nodes locally and
  verifies fanout, offline write-ahead saving, catch-up sync after restart,
  divergent-history merge, dedup, and liveness tracking:

  ```bash
  cd node && python3 smoke_test.py
  ```

### Legacy

`legacy/` contains the original Tailnet Orchestration Hub (remote command
execution via hub/agents + n8n). It is deactivated but kept for future
development — see `legacy/README.md`.

## Roadmap ideas

- Message delivery/read indicators (per-device "has seen up to" markers)
- Push-style updates in the UI (WebSocket/SSE instead of polling)
- Auth on the web UI itself
- Image/file attachments
- Reintegrate legacy remote-command execution as chat commands
