import os
import subprocess
import threading
import time
import requests
from fastapi import FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import uvicorn

API_KEY = os.environ["API_KEY"]
HUB_URL = os.environ["HUB_URL"]
DEVICE_NAME = os.environ["DEVICE_NAME"]
HEARTBEAT_INTERVAL = 60

api_key_header = APIKeyHeader(name="X-API-Key")
app = FastAPI(title=f"Node Agent — {DEVICE_NAME}")

def auth(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

class IncomingCommand(BaseModel):
    command: str
    sender: str

@app.post("/execute", dependencies=[Security(auth)])
async def execute(cmd: IncomingCommand):
    print(f"[{DEVICE_NAME}] From {cmd.sender}: {cmd.command}")
    try:
        result = subprocess.check_output(cmd.command, shell=True, text=True, timeout=30)
        return {"status": "ok", "output": result}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "output": e.output}
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}

def get_tailscale_ip():
    try:
        return subprocess.check_output(["tailscale", "ip", "-4"], text=True).strip()
    except Exception as e:
        print(f"Could not get Tailscale IP: {e}")
        return None

def heartbeat_loop():
    while True:
        ip = get_tailscale_ip()
        if ip:
            try:
                requests.post(
                    f"{HUB_URL}/register",
                    json={"device_name": DEVICE_NAME, "ip": ip},
                    headers={"X-API-Key": API_KEY},
                    timeout=5
                )
                print(f"[{DEVICE_NAME}] Heartbeat OK (ip={ip})")
            except requests.exceptions.RequestException as e:
                print(f"[{DEVICE_NAME}] Hub unreachable: {e}")
        time.sleep(HEARTBEAT_INTERVAL)

if __name__ == "__main__":
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8001)
