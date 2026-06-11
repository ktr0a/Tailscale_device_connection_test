# Setup Guide - Tailnet Orchestration Hub

Welcome to the Tailnet Orchestration Hub. This guide will walk you through setting up the hub, agents, and n8n orchestration system across your devices.

## Requirements

Before starting, ensure all modules have Tailscale installed and authenticated to your Tailnet (`tailscale up`). Also make sure Python 3.10+ is installed on the relevant devices.

> [!WARNING]
> For security reasons, do not expose the device ports (8000, 8001, 5678) to the public internet. Ensure these services are securely bound via firewall rules or tailscale interfaces.

---

## 1. Initial Setup (Shared Secret)
First, generate a shared 32-character hex secret string that will secure communication between the hub and agents.

```bash
openssl rand -hex 32
```

Save this generated key for the subsequent steps.

---

## 2. Setting Up the Hub (Raspberry Pi)

1. Open `hub/.env` and replace `your_generated_secret` with the secret you generated in step 1.
2. Install the necessary Python dependencies inside the `hub` directory:
   ```bash
   pip install fastapi uvicorn httpx pydantic
   ```
   *(We recommend using a python virtual environment)*
3. Make the start script executable:
   ```bash
   cd hub
   chmod +x start.sh
   ```
4. Start the hub using the script:
   ```bash
   ./start.sh
   ```
The Hub control plane is now available at `http://[PI-TAILSCALE-IP]:8000/docs` via devices on your Tailnet.

---

## 3. Setting up n8n Automation (Raspberry Pi)

1. Navigate to the `n8n` directory.
2. Ensure you have Docker and Docker Compose installed.
3. Start the n8n container:
   ```bash
   docker compose up -d
   ```
You can access the workflow UI at `http://[PI-TAILSCALE-IP]:5678`.

---

## 4. Setting up node Agents (Your PC / Laptop)

For the devices you want to execute commands on, you need to spin up the agent server.

1. Open `agent/.env` and configure:
   - `API_KEY` (The shared secret from step 1)
   - `HUB_URL` (Use your Raspberry Pi Tailscale IP -> `http://[PI-TAILSCALE-IP]:8000`)
   - `DEVICE_NAME` (A unique name for this device, like `workstation` or `laptop`)
2. Install agent dependencies:
   ```bash
   pip install fastapi uvicorn httpx pydantic
   ```
3. Start the agent:
   - **For Windows**: Run or double click `start.bat`
   - **For macOS/Linux**:
     ```bash
     chmod +x start.sh
     ./start.sh
     ```

The agent will automatically heartbeat to the Hub server every 60 seconds.

---

## 5. Persistence and Security setup (Optional but Recommended)

Check the underlying `readme.md` document (Phase 4 and Firewall sections) for guidance on setting up `systemd` persistence and binding Linux ports strictly to `tailscale0` via `ufw`. This ensures security and guarantees services stay running.
