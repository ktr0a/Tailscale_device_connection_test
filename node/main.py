"""Tailnet Chat node.

Every device on the tailnet runs this same app. There is no central
server: each node keeps its own full copy of the chatlog and reconciles
with its peers.

Endpoint groups:
  /api/*    peer-to-peer traffic between nodes, protected by the shared
            API key (X-API-Key header).
  /local/*  backing endpoints for this node's own web UI. Unauthenticated
            by design — access is limited to the tailnet (bind/firewall).
  /         the chat UI;  /settings  the device management UI.
"""

import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.responses import FileResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from storage import Store

API_KEY = os.environ["API_KEY"]
DEVICE_NAME = os.environ["DEVICE_NAME"]
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
PING_INTERVAL = int(os.environ.get("PING_INTERVAL", "180"))
PEER_TIMEOUT = 10
MAX_MESSAGE_LEN = 4000

store = Store(DATA_DIR)
AUTH_HEADERS = {"X-API-Key": API_KEY}
api_key_header = APIKeyHeader(name="X-API-Key")


def auth(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


# --- Pydantic v1/v2 compat ---

def model_to_dict(m):
    """pydantic v1/v2 compatibility."""
    return m.model_dump() if hasattr(m, "model_dump") else m.dict()


# --- Models ---

class ChatMessage(BaseModel):
    id: str = Field(min_length=8, max_length=64)
    device_id: str = Field(min_length=8, max_length=64)
    device: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LEN)
    time: float


class SyncRequest(BaseModel):
    device_id: str
    device: str
    messages: list[ChatMessage]


class SendRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LEN)


class PeerIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=8000, ge=1, le=65535)


# --- Peer liveness tracking (in-memory; rebuilt by pings after restart) ---

peer_status: dict[str, dict] = {}


def peer_key(peer: dict) -> str:
    return f"{peer['host']}:{peer['port']}"


def peer_url(peer: dict) -> str:
    return f"http://{peer['host']}:{peer['port']}"


def get_status(peer: dict) -> dict:
    return peer_status.setdefault(
        peer_key(peer), {"online": None, "last_seen": None, "device_id": None, "note": None}
    )


def touch_device(device_id: str) -> None:
    """A node we heard from directly is evidently online."""
    for st in peer_status.values():
        if st["device_id"] == device_id:
            st["online"] = True
            st["last_seen"] = time.time()


async def ping_peer(client: httpx.AsyncClient, peer: dict) -> bool:
    st = get_status(peer)
    try:
        resp = await client.get(f"{peer_url(peer)}/api/ping", headers=AUTH_HEADERS, timeout=PEER_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        st["online"] = True
        st["last_seen"] = time.time()
        st["device_id"] = data.get("device_id")
        if st["device_id"] == store.device_id:
            st["note"] = "self"
        elif data.get("device") == DEVICE_NAME:
            st["note"] = "name conflict"
        else:
            st["note"] = None
        return True
    except (httpx.HTTPError, ValueError):
        st["online"] = False
        return False


async def sync_with_peer(client: httpx.AsyncClient, peer: dict) -> None:
    """Two-way reconciliation: send our full log, merge what comes back."""
    payload = {"device_id": store.device_id, "device": DEVICE_NAME, "messages": store.all_messages()}
    resp = await client.post(f"{peer_url(peer)}/api/sync", json=payload, headers=AUTH_HEADERS, timeout=PEER_TIMEOUT * 3)
    resp.raise_for_status()
    incoming = [model_to_dict(ChatMessage(**m)) for m in resp.json().get("messages", [])]
    store.add_messages(incoming)


async def check_peer(client: httpx.AsyncClient, peer: dict) -> None:
    if not await ping_peer(client, peer):
        return
    if get_status(peer)["note"] == "self":
        return  # never sync with ourselves
    try:
        await sync_with_peer(client, peer)
    except (httpx.HTTPError, ValueError):
        pass  # next cycle will retry


async def check_all_peers() -> None:
    peers = store.get_peers()
    # drop status entries for peers that were removed in settings
    known = {peer_key(p) for p in peers}
    for key in list(peer_status):
        if key not in known:
            del peer_status[key]
    if not peers:
        return
    async with httpx.AsyncClient() as client:
        await asyncio.gather(*(check_peer(client, p) for p in peers), return_exceptions=True)


async def monitor_loop() -> None:
    # first pass runs immediately: this is the "device came up" full sync
    while True:
        await check_all_peers()
        await asyncio.sleep(PING_INTERVAL)


async def deliver(client: httpx.AsyncClient, peer: dict, msg: dict) -> None:
    st = get_status(peer)
    if st["note"] == "self":
        return
    try:
        resp = await client.post(f"{peer_url(peer)}/api/messages", json=msg, headers=AUTH_HEADERS, timeout=PEER_TIMEOUT)
        resp.raise_for_status()
        st["online"] = True
        st["last_seen"] = time.time()
    except httpx.HTTPError:
        st["online"] = False  # offline peers catch up via sync later


async def fanout(msg: dict) -> None:
    peers = store.get_peers()
    if not peers:
        return
    async with httpx.AsyncClient() as client:
        await asyncio.gather(*(deliver(client, p, msg) for p in peers), return_exceptions=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(monitor_loop())
    yield
    task.cancel()


app = FastAPI(title=f"Tailnet Chat — {DEVICE_NAME}", lifespan=lifespan)


# --- Peer-to-peer API (authenticated) ---

@app.get("/api/ping", tags=["Peer API"], dependencies=[Depends(auth)])
async def api_ping():
    return {"device_id": store.device_id, "device": DEVICE_NAME, "time": time.time()}


@app.post("/api/messages", tags=["Peer API"], dependencies=[Depends(auth)])
async def api_receive_message(msg: ChatMessage):
    added = store.add_messages([model_to_dict(msg)])
    touch_device(msg.device_id)
    return {"status": "ok", "new": len(added)}


@app.post("/api/sync", tags=["Peer API"], dependencies=[Depends(auth)])
async def api_sync(req: SyncRequest):
    store.add_messages([model_to_dict(m) for m in req.messages])
    caller_has = {m.id for m in req.messages}
    missing = [m for m in store.all_messages() if m["id"] not in caller_has]
    touch_device(req.device_id)
    return {"device_id": store.device_id, "device": DEVICE_NAME, "messages": missing}


# --- Local API (backs the web UI) ---

@app.get("/local/messages", tags=["Local"])
async def local_messages():
    return {"device": DEVICE_NAME, "device_id": store.device_id, "messages": store.all_messages()}


@app.post("/local/send", tags=["Local"])
async def local_send(req: SendRequest):
    text = req.message.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Message is empty")
    msg = {
        "id": uuid.uuid4().hex,
        "device_id": store.device_id,
        "device": DEVICE_NAME,
        "message": text,
        "time": time.time(),
    }
    store.add_messages([msg])  # save locally before any delivery attempt
    asyncio.create_task(fanout(msg))
    return msg


@app.get("/local/status", tags=["Local"])
async def local_status():
    peers = []
    for p in store.get_peers():
        st = peer_status.get(peer_key(p), {})
        peers.append({
            **p,
            "online": st.get("online"),
            "last_seen": st.get("last_seen"),
            "note": st.get("note"),
        })
    return {"device": DEVICE_NAME, "device_id": store.device_id, "ping_interval": PING_INTERVAL, "peers": peers}


@app.post("/local/check", tags=["Local"])
async def local_check():
    """Ping + sync every peer right now (the UI's refresh button)."""
    await check_all_peers()
    return await local_status()


@app.get("/local/peers", tags=["Local"])
async def local_list_peers():
    return {"peers": store.get_peers()}


@app.post("/local/peers", tags=["Local"])
async def local_add_peer(peer: PeerIn):
    try:
        store.add_peer(model_to_dict(peer))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    asyncio.create_task(check_all_peers())
    return {"status": "added", "peer": model_to_dict(peer)}


@app.delete("/local/peers", tags=["Local"])
async def local_remove_peer(host: str, port: int):
    if not store.remove_peer(host, port):
        raise HTTPException(status_code=404, detail="No such device")
    peer_status.pop(f"{host}:{port}", None)
    return {"status": "removed"}


# --- Web UI ---

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def ui_chat():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/settings", include_in_schema=False)
async def ui_settings():
    return FileResponse(os.path.join(STATIC_DIR, "settings.html"))
