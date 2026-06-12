#!/usr/bin/env python3
"""End-to-end smoke test: runs two chat nodes on localhost and verifies
send/fanout, write-ahead saving while a peer is down, catch-up sync on
restart, divergent-history merge, and online/offline status tracking.

Usage: python3 smoke_test.py   (needs fastapi/uvicorn/httpx installed)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

NODE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT_A, PORT_B = 8101, 8102
API_KEY = "smoketestkey"
PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
failures = 0


def check(label, cond):
    global failures
    print(f"  [{PASS if cond else FAIL}] {label}")
    if not cond:
        failures += 1


def req(port, path, data=None, method=None):
    url = f"http://127.0.0.1:{port}{path}"
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, method=method or ("POST" if body else "GET"))
    r.add_header("Content-Type", "application/json")
    r.add_header("X-API-Key", API_KEY)
    with urllib.request.urlopen(r, timeout=10) as resp:
        return json.loads(resp.read())


def start_node(name, port, data_dir, log):
    env = dict(os.environ, API_KEY=API_KEY, DEVICE_NAME=name, DATA_DIR=data_dir, PING_INTERVAL="3")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=NODE_DIR, env=env, stdout=log, stderr=log,
    )
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            req(port, "/local/status")
            return proc
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.3)
    proc.kill()
    raise RuntimeError(f"node {name} on :{port} did not come up")


def stop(proc):
    proc.terminate()
    proc.wait(timeout=10)


def msgs(port):
    return req(port, "/local/messages")["messages"]


def texts(port):
    return [m["message"] for m in msgs(port)]


def wait_for(fn, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if fn():
            return True
        time.sleep(0.4)
    return fn()


def main():
    workdir = tempfile.mkdtemp(prefix="tailnet-chat-test-")
    dir_a, dir_b = os.path.join(workdir, "a"), os.path.join(workdir, "b")
    os.makedirs(dir_a), os.makedirs(dir_b)

    # point the nodes at each other
    with open(os.path.join(dir_a, "peers.json"), "w") as f:
        json.dump({"peers": [{"name": "node-b", "host": "127.0.0.1", "port": PORT_B}]}, f)
    with open(os.path.join(dir_b, "peers.json"), "w") as f:
        json.dump({"peers": [{"name": "node-a", "host": "127.0.0.1", "port": PORT_A}]}, f)

    log = open(os.path.join(workdir, "nodes.log"), "w")
    a = b = None
    try:
        print("1. Live fanout between two online nodes")
        a = start_node("node-a", PORT_A, dir_a, log)
        b = start_node("node-b", PORT_B, dir_b, log)
        req(PORT_A, "/local/send", {"message": "hello from A"})
        req(PORT_B, "/local/send", {"message": "hello from B"})
        check("B received A's message", wait_for(lambda: "hello from A" in texts(PORT_B)))
        check("A received B's message", wait_for(lambda: "hello from B" in texts(PORT_A)))
        check("both logs identical", msgs(PORT_A) == msgs(PORT_B))

        print("2. Auth: peer API rejects bad key")
        try:
            r = urllib.request.Request(f"http://127.0.0.1:{PORT_A}/api/ping", headers={"X-API-Key": "wrong"})
            urllib.request.urlopen(r, timeout=5)
            check("rejects wrong API key", False)
        except urllib.error.HTTPError as e:
            check("rejects wrong API key", e.code == 403)

        print("3. Write-ahead save while peer is down, catch-up on restart")
        stop(b)
        sent = req(PORT_A, "/local/send", {"message": "sent while B was down"})
        check("A saved its own message immediately", "sent while B was down" in texts(PORT_A))
        on_disk = json.load(open(os.path.join(dir_a, "chatlog.json")))
        check("message persisted to A's disk", any(m["id"] == sent["id"] for m in on_disk["messages"]))
        b = start_node("node-b", PORT_B, dir_b, log)
        check("B caught up after restart (startup sync)", wait_for(lambda: "sent while B was down" in texts(PORT_B)))

        print("4. Divergent histories merge to the union (1,3,5 vs 2,4 case)")
        stop(a), stop(b)
        base = time.time() - 3600

        def fake(n, t, dev_id, dev):
            return {"id": f"fakemsg{n:02d}{'0' * 8}", "device_id": dev_id, "device": dev,
                    "message": f"divergent {n}", "time": t}

        ida = json.load(open(os.path.join(dir_a, "identity.json")))["device_id"]
        idb = json.load(open(os.path.join(dir_b, "identity.json")))["device_id"]
        log_a = json.load(open(os.path.join(dir_a, "chatlog.json")))
        log_b = json.load(open(os.path.join(dir_b, "chatlog.json")))
        log_a["messages"] += [fake(1, base + 60, ida, "node-a"), fake(3, base + 180, ida, "node-a"), fake(5, base + 300, ida, "node-a")]
        log_b["messages"] += [fake(2, base + 120, idb, "node-b"), fake(4, base + 240, idb, "node-b")]
        json.dump(log_a, open(os.path.join(dir_a, "chatlog.json"), "w"))
        json.dump(log_b, open(os.path.join(dir_b, "chatlog.json"), "w"))
        a = start_node("node-a", PORT_A, dir_a, log)
        b = start_node("node-b", PORT_B, dir_b, log)
        want = [f"divergent {n}" for n in (1, 2, 3, 4, 5)]
        check("A has full union", wait_for(lambda: [t for t in texts(PORT_A) if t.startswith("divergent")] == want))
        check("B has full union", wait_for(lambda: [t for t in texts(PORT_B) if t.startswith("divergent")] == want))
        check("identical order on both nodes", msgs(PORT_A) == msgs(PORT_B))
        check("no duplicates after merge", len({m["id"] for m in msgs(PORT_A)}) == len(msgs(PORT_A)))

        print("5. Liveness: status flips offline when a peer dies")
        peer_b = lambda: req(PORT_A, "/local/status")["peers"][0]
        check("B reported online", wait_for(lambda: peer_b()["online"] is True))
        stop(b)
        b = None
        check("B reported offline after ping cycle", wait_for(lambda: peer_b()["online"] is False, timeout=15))
        check("UI message endpoint still serves", len(texts(PORT_A)) > 0)
    finally:
        for p in (a, b):
            if p and p.poll() is None:
                stop(p)
        log.close()
        shutil.rmtree(workdir, ignore_errors=True)

    print(f"\n{'ALL TESTS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
