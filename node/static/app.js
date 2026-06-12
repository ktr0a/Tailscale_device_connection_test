const messagesEl = document.getElementById("messages");
const chipsEl = document.getElementById("peer-chips");
const bannerEl = document.getElementById("banner");
const deviceNameEl = document.getElementById("device-name");
const form = document.getElementById("send-form");
const input = document.getElementById("msg-input");

let myDeviceId = null;
let renderedCount = -1;

function fmtTime(unix) {
  const d = new Date(unix * 1000);
  const today = new Date().toDateString() === d.toDateString();
  const hm = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return today ? hm : `${d.toLocaleDateString([], { day: "2-digit", month: "short" })} ${hm}`;
}

function nearBottom() {
  return messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 80;
}

function renderMessages(msgs) {
  if (msgs.length === renderedCount) return;
  const stick = nearBottom() || renderedCount === -1;
  renderedCount = msgs.length;
  messagesEl.replaceChildren(...msgs.map((m) => {
    const div = document.createElement("div");
    div.className = "msg" + (m.device_id === myDeviceId ? " mine" : "");
    const meta = document.createElement("div");
    meta.className = "meta";
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = m.device;
    const when = document.createElement("span");
    when.textContent = fmtTime(m.time);
    meta.append(who, when);
    const body = document.createElement("div");
    body.textContent = m.message;
    div.append(meta, body);
    return div;
  }));
  if (stick) messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function pollMessages() {
  try {
    const r = await fetch("/local/messages");
    const data = await r.json();
    myDeviceId = data.device_id;
    deviceNameEl.textContent = data.device;
    renderMessages(data.messages);
  } catch (e) { /* node briefly unreachable; retry next poll */ }
}

function renderStatus(data) {
  chipsEl.replaceChildren(...data.peers.map((p) => {
    const chip = document.createElement("span");
    const state = p.online === null ? "" : p.online ? "online" : "offline";
    chip.className = `chip ${state}` + (p.note ? " warn" : "");
    const dot = document.createElement("span");
    dot.className = "dot";
    chip.append(dot, document.createTextNode(p.name));
    chip.title = `${p.host}:${p.port}` + (p.note ? ` — ${p.note}` : "");
    return chip;
  }));
  const offline = data.peers.filter((p) => p.online === false).map((p) => p.name);
  if (offline.length) {
    bannerEl.textContent = `Offline: ${offline.join(", ")} — they'll catch up automatically when back.`;
    bannerEl.classList.remove("hidden");
  } else {
    bannerEl.classList.add("hidden");
  }
}

async function pollStatus() {
  try {
    const r = await fetch("/local/status");
    renderStatus(await r.json());
  } catch (e) { /* retry next poll */ }
}

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  try {
    await fetch("/local/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    await pollMessages();
  } catch (e) {
    input.value = text; // give the user their text back to retry
  }
});

pollMessages();
pollStatus();
setInterval(pollMessages, 2000);
setInterval(pollStatus, 10000);
