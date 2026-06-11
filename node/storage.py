"""Persistent state for a chat node: identity, chatlog, and peer list.

All writes are atomic (write to a temp file, then rename) so a crash
mid-write can never corrupt the JSON on disk. A single lock guards the
in-memory state because FastAPI handlers and background tasks may touch
it concurrently.
"""

import json
import os
import threading
import uuid


class Store:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._chatlog_path = os.path.join(data_dir, "chatlog.json")
        self._peers_path = os.path.join(data_dir, "peers.json")
        self._identity_path = os.path.join(data_dir, "identity.json")

        self._messages: list[dict] = self._read(self._chatlog_path, {"messages": []})["messages"]
        self._messages.sort(key=lambda m: (m["time"], m["id"]))
        self._ids = {m["id"] for m in self._messages}
        self._peers: list[dict] = self._read(self._peers_path, {"peers": []})["peers"]

        identity = self._read(self._identity_path, None)
        if identity is None:
            identity = {"device_id": uuid.uuid4().hex}
            self._write(self._identity_path, identity)
        self.device_id: str = identity["device_id"]

    @staticmethod
    def _read(path: str, default):
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write(path: str, data) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    # --- Messages ---

    def add_messages(self, msgs: list[dict]) -> list[dict]:
        """Merge messages into the log, ignoring ids we already have.

        Returns the messages that were actually new. The log is kept
        sorted by (time, id) so every node converges on the same order.
        """
        added = []
        with self._lock:
            for m in msgs:
                if m["id"] in self._ids:
                    continue
                self._ids.add(m["id"])
                self._messages.append(m)
                added.append(m)
            if added:
                self._messages.sort(key=lambda m: (m["time"], m["id"]))
                self._write(self._chatlog_path, {"messages": self._messages})
        return added

    def all_messages(self) -> list[dict]:
        with self._lock:
            return [dict(m) for m in self._messages]

    def message_ids(self) -> set[str]:
        with self._lock:
            return set(self._ids)

    # --- Peers ---

    def get_peers(self) -> list[dict]:
        with self._lock:
            return [dict(p) for p in self._peers]

    def add_peer(self, peer: dict) -> None:
        with self._lock:
            for p in self._peers:
                if p["host"] == peer["host"] and p["port"] == peer["port"]:
                    raise ValueError("a device with this host and port is already configured")
            self._peers.append(peer)
            self._write(self._peers_path, {"peers": self._peers})

    def remove_peer(self, host: str, port: int) -> bool:
        with self._lock:
            remaining = [p for p in self._peers if not (p["host"] == host and p["port"] == port)]
            if len(remaining) == len(self._peers):
                return False
            self._peers = remaining
            self._write(self._peers_path, {"peers": self._peers})
            return True
