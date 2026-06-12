# Tailnet Orchestration Hub

A private orchestration system built over Tailscale. It provides a secure, internal-only control plane that connects devices across your Tailnet, enabling automated workflows and remote command execution without exposing any public ports.

## Architecture

The system consists of three main components communicating exclusively over the Tailnet:

| Component | Recommended Device | Port | Role |
|-----------|--------------------|------|------|
| **Hub** | Raspberry Pi | 8000 | FastAPI device registry, command router, and manual control panel (Swagger UI). |
| **Agent** | Target PC / Laptop | 8001 | Listens for and executes commands from the Hub. Reports heartbeat every 60s. |
| **n8n** | Raspberry Pi | 5678 | Workflow automation platform for smart triggers and scheduled tasks. |

```text
Phone / Browser
      │
      ├──► http://[pi]:8000/docs   (manual control — Swagger UI)
      └──► http://[pi]:5678        (automated workflows — n8n)
                │
                ▼
         [Pi Hub :8000]  ◄── agents heartbeat every 60s
                │
                ├──► POST http://[pc]:8001/execute
                └──► POST http://[laptop]:8001/execute
```

## Features
- **Zero Public Ports:** All traffic stays within the secure Tailscale network.
- **Automated Discovery:** Agents regularly heartbeat to the Hub, maintaining an up-to-date registry of online devices.
- **RESTful API:** Control devices manually via the Hub's Swagger UI or programmatically via n8n workflows.
- **Workflow Automation:** Integrate with n8n to build custom automation sequences across your Tailnet.

## Prerequisites
- Tailscale installed and authenticated (`tailscale up`) on all devices.
- Python 3.10+ installed on both the Hub and Agent machines.
- Docker and Docker Compose installed on the Hub machine (for running n8n).

## Installation

### 1. Generate a Shared Secret
Generate a single shared secret to be used for authentication between the Hub, Agents, and n8n. Run this once and save it:
```bash
openssl rand -hex 32
```

### 2. Hub Setup (Central Controller)
The Hub acts as the central device registry and command router. It is typically hosted on an always-on device like a Raspberry Pi.

1. Navigate to the `hub/` directory.
2. Create a `.env` file and set the `API_KEY`:
   ```bash
   API_KEY=your_generated_secret
   ```
3. Install dependencies: `pip install fastapi uvicorn httpx pydantic`
4. Start the Hub:
   ```bash
   ./start.sh
   # Or manually: python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

### 3. Agent Setup (Target Devices)
The Agent runs on any device that you want to control or monitor.

1. Navigate to the `agent/` directory on the target machine.
2. Create a `.env` file with the required configuration:
   ```bash
   API_KEY=your_generated_secret
   HUB_URL=http://<HUB-TAILSCALE-IP>:8000
   DEVICE_NAME=my_workstation
   ```
3. Start the Agent:
   ```bash
   ./start.sh
   # Or manually on Windows: python agent.py
   ```

### 4. n8n Setup (Workflow Automation)
n8n orchestrates workflows and can interact with the Hub.

1. Navigate to the `n8n/` directory.
2. Start the Docker container:
   ```bash
   docker compose up -d
   ```
3. Access n8n in your browser at `http://<HUB-TAILSCALE-IP>:5678`.

## Usage & Integration

### Manual Testing and Control
1. The Hub exposes a built-in Swagger UI. Visit it in your browser at `http://<HUB-TAILSCALE-IP>:8000/docs`.
2. Ensure you authenticate by entering `your_generated_secret` into the `X-API-Key` section.
3. You can use `GET /status` to check the Hub health.
4. You can use `GET /devices` to see all online Agents.
5. You can use `POST /send` to send remote commands to Agents.

### Triggering Actions with n8n
To create automated workflows that trigger actions on your nodes:

1. Create a **Webhook** node in n8n (or any trigger of your choice).
2. Connect it to an **HTTP Request** node.
3. Configure the HTTP node to interact with the Hub:
    - **Method:** POST
    - **URL:** `http://localhost:8000/send` (if n8n and Hub are on the same machine)
    - **Headers:** `X-API-Key: your_generated_secret`
    - **Body (JSON):**
      ```json
      {
        "receiver": "my_workstation",
        "command": "echo 'Triggered via n8n'"
      }
      ```
4. This node will now remotely execute the shell command on `my_workstation` over Tailscale.

## Security & Firewall
For maximum security, limit traffic explicitly to the Tailscale interface (`tailscale0`).

**Hub Device:**
```bash
sudo ufw allow in on tailscale0 to any port 8000
sudo ufw allow in on tailscale0 to any port 5678
```

**Agent Node (Linux):**
```bash
sudo ufw allow in on tailscale0 to any port 8001
```

## System Services (Persistence)

For continuous operation across device restarts, configure systemd services. 

Sample configurations can be created pointing to your clone directory:

**`tailnet-hub.service`** (Hub Node):
```ini
[Unit]
Description=Tailnet Hub
After=network.target

[Service]
WorkingDirectory=/path/to/tailnet-automation/hub
EnvironmentFile=/path/to/tailnet-automation/hub/.env
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**`tailnet-agent.service`** (Agent Nodes):
```ini
[Unit]
Description=Tailnet Node Agent
After=network.target

[Service]
WorkingDirectory=/path/to/tailnet-automation/agent
EnvironmentFile=/path/to/tailnet-automation/agent/.env
ExecStart=/usr/bin/python3 agent.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tailnet-hub tailnet-agent
```