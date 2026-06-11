const tbody = document.querySelector("#peer-table tbody");
const noPeersEl = document.getElementById("no-peers");
const deviceNameEl = document.getElementById("device-name");
const addForm = document.getElementById("add-form");
const addError = document.getElementById("add-error");
const checkBtn = document.getElementById("check-now");

function fmtLastSeen(unix) {
  if (!unix) return "never";
  const secs = Math.round(Date.now() / 1000 - unix);
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  return new Date(unix * 1000).toLocaleString();
}

function noteText(note) {
  if (note === "self") return "⚠ this address points at this device itself";
  if (note === "name conflict") return "⚠ uses the same display name as this device";
  return "";
}

function render(data) {
  deviceNameEl.textContent = data.device;
  noPeersEl.classList.toggle("hidden", data.peers.length > 0);
  tbody.replaceChildren(...data.peers.map((p) => {
    const tr = document.createElement("tr");

    const tdDot = document.createElement("td");
    const dot = document.createElement("span");
    dot.className = "dot " + (p.online === null ? "" : p.online ? "online" : "offline");
    tdDot.append(dot);

    const tdName = document.createElement("td");
    tdName.textContent = p.name;
    if (p.note) {
      const note = document.createElement("span");
      note.className = "note";
      note.textContent = noteText(p.note);
      tdName.append(note);
    }

    const tdAddr = document.createElement("td");
    tdAddr.textContent = `${p.host}:${p.port}`;

    const tdSeen = document.createElement("td");
    tdSeen.textContent = fmtLastSeen(p.last_seen);

    const tdActions = document.createElement("td");
    const btn = document.createElement("button");
    btn.className = "remove-btn";
    btn.textContent = "Remove";
    btn.addEventListener("click", async () => {
      await fetch(`/local/peers?host=${encodeURIComponent(p.host)}&port=${p.port}`, { method: "DELETE" });
      refresh();
    });
    tdActions.append(btn);

    tr.append(tdDot, tdName, tdAddr, tdSeen, tdActions);
    return tr;
  }));
}

async function refresh() {
  try {
    const r = await fetch("/local/status");
    render(await r.json());
  } catch (e) { /* retry next poll */ }
}

addForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  addError.classList.add("hidden");
  const body = {
    name: document.getElementById("peer-name").value.trim(),
    host: document.getElementById("peer-host").value.trim(),
    port: parseInt(document.getElementById("peer-port").value, 10),
  };
  const r = await fetch("/local/peers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (r.ok) {
    addForm.reset();
    document.getElementById("peer-port").value = 8000;
    setTimeout(refresh, 500); // give the background ping a moment
  } else {
    const data = await r.json().catch(() => ({}));
    addError.textContent = typeof data.detail === "string" ? data.detail : "Could not add device.";
    addError.classList.remove("hidden");
  }
  refresh();
});

checkBtn.addEventListener("click", async () => {
  checkBtn.disabled = true;
  checkBtn.textContent = "Checking…";
  try {
    const r = await fetch("/local/check", { method: "POST" });
    render(await r.json());
  } finally {
    checkBtn.disabled = false;
    checkBtn.textContent = "Ping & sync all now";
  }
});

refresh();
setInterval(refresh, 10000);
