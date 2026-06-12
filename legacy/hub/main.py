import os
import sqlite3
import datetime
import httpx
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

API_KEY = os.environ["API_KEY"]
api_key_header = APIKeyHeader(name="X-API-Key")

app = FastAPI(
    title="Tailnet Control Plane",
    description="Manual control panel. Use /docs to trigger commands from any browser.",
    version="1.0.0"
)

DB_PATH = "registry.db"

# --- Database ---

@contextmanager
def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def init_db():
    with get_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                name TEXT PRIMARY KEY,
                ip TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)

init_db()

# --- Auth ---

def auth(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

# --- Models ---

class Registration(BaseModel):
    device_name: str
    ip: str

class CommandRequest(BaseModel):
    receiver: str
    command: str

# --- Routes ---

@app.get("/status", tags=["Management"])
async def get_status():
    """Public health check — no auth required."""
    return {"status": "online", "timestamp": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)}

@app.post("/register", tags=["Management"], dependencies=[Depends(auth)])
async def register_device(reg: Registration):
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat()
    with get_db() as con:
        con.execute(
            "INSERT INTO devices (name, ip, last_seen) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET ip=excluded.ip, last_seen=excluded.last_seen",
            (reg.device_name, reg.ip, now)
        )
    return {"status": "registered", "device": reg.device_name}

@app.get("/devices", tags=["Orchestration"], dependencies=[Depends(auth)])
async def list_active_devices():
    """List all agents that checked in within the last 2 minutes."""
    cutoff = (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(minutes=2)).isoformat()
    with get_db() as con:
        rows = con.execute(
            "SELECT name, ip, last_seen FROM devices WHERE last_seen > ?", (cutoff,)
        ).fetchall()
    return [dict(r) for r in rows]

@app.post("/send", tags=["Orchestration"], dependencies=[Depends(auth)])
async def send_command(req: CommandRequest):
    """Send a shell command to a registered agent node."""
    cutoff = (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(minutes=2)).isoformat()
    with get_db() as con:
        row = con.execute(
            "SELECT ip FROM devices WHERE name=? AND last_seen > ?",
            (req.receiver, cutoff)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"'{req.receiver}' is offline or not registered")

    target_url = f"http://{row['ip']}:8001/execute"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                target_url,
                json={"command": req.command, "sender": "hub"},
                headers={"X-API-Key": API_KEY},
                timeout=10
            )
        return {"status": "delivered", "agent_response": resp.json()}
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Agent unreachable: {e}")
