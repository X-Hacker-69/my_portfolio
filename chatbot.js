const API_BASE = "http://localhost:5000";
const OWNER_FIRST = "Anil";
const BOT_NAME    = "Anil AI";
const AVATAR_INIT = "AS";

const QUICK_CHIPS = [
  { label: "🚀 Best projects",     msg: "What are Anil's projects?" },
  { label: "💻 Tech stack",        msg: "What technologies does he know?" },
  { label: "🏆 Achievements",      msg: "What are his top achievements?" },
  { label: "🎓 Education",         msg: "Where does he study?" },
  { label: "🤖 AI experience",     msg: "What is his AI and ML experience?" },
  { label: "📄 Recruiter summary", msg: "Give me a recruiter-friendly summary." },
  { label: "📬 Contact",           msg: "How can I contact him?" },
];

// ══════════════════════════════════════════════════════
//  DOM REFS
// ══════════════════════════════════════════════════════
const orb        = document.getElementById("orb");
const panel      = document.getElementById("chat-panel");
const msgsEl     = document.getElementById("msgs");
const inputEl    = document.getElementById("user-input");
const sendBtn    = document.getElementById("send");
const notifBadge = document.getElementById("notif");

document.getElementById("bot-name").textContent    = BOT_NAME;
document.getElementById("av-initials").textContent = AVATAR_INIT;

// ══════════════════════════════════════════════════════
//  STATE
// ══════════════════════════════════════════════════════
let isOpen    = false;
let greeted   = false;
let history   = [];
let streaming = false;

// ══════════════════════════════════════════════════════
//  ORB TOGGLE
// ══════════════════════════════════════════════════════
orb.addEventListener("click", () => {
  isOpen = !isOpen;
  orb.classList.toggle("open", isOpen);
  panel.classList.toggle("open", isOpen);
  if (isOpen) {
    notifBadge.classList.remove("show");
    if (!greeted) { showGreeting(); greeted = true; }
    setTimeout(() => inputEl.focus(), 320);
  }
});

// Close on outside click
document.addEventListener("click", (e) => {
  if (isOpen && !panel.contains(e.target) && !orb.contains(e.target)) {
    isOpen = false;
    orb.classList.remove("open");
    panel.classList.remove("open");
  }
});

// Show notification badge after 3 s
setTimeout(() => { if (!isOpen) notifBadge.classList.add("show"); }, 3000);

// ══════════════════════════════════════════════════════
//  GREETING
// ══════════════════════════════════════════════════════
function showGreeting() {
  appendMsg("ai",
    `Hey! 👋 I'm **${BOT_NAME}**, ${OWNER_FIRST}'s AI assistant.\n\nAsk me anything about his projects, skills, or experience!`
  );
  setTimeout(() => {
    const div = document.createElement("div");
    div.className = "chips";
    QUICK_CHIPS.forEach((c) => {
      const btn = document.createElement("button");
      btn.className = "chip";
      btn.textContent = c.label;
      btn.onclick = () => sendMessage(c.msg);
      div.appendChild(btn);
    });
    msgsEl.appendChild(div);
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }, 300);
}

// ══════════════════════════════════════════════════════
//  MESSAGE RENDERING
// ══════════════════════════════════════════════════════
function appendMsg(role, text, latencyMs) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;

  const av = document.createElement("div");
  av.className = "msg-av";
  av.textContent = role === "ai" ? AVATAR_INIT : "You";

  const bub = document.createElement("div");
  bub.className = "bubble";
  bub.innerHTML = renderMd(text);

  if (latencyMs) {
    const lat = document.createElement("div");
    lat.className = "latency";
    lat.textContent = `${(latencyMs / 1000).toFixed(1)}s`;
    const col = document.createElement("div");
    col.appendChild(bub);
    col.appendChild(lat);
    wrap.appendChild(av);
    wrap.appendChild(col);
  } else {
    wrap.appendChild(av);
    wrap.appendChild(bub);
  }

  msgsEl.appendChild(wrap);
  msgsEl.scrollTop = msgsEl.scrollHeight;
  return bub;
}

function renderMd(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/^[-•] (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>[\s\S]*?<\/li>)(\n|$)+/g, (m) => `<ul>${m}</ul>`)
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br>")
    .replace(/^(?!<)/, "<p>")
    .replace(/(?<!>)$/, "</p>");
}

// ══════════════════════════════════════════════════════
//  TYPING INDICATOR
// ══════════════════════════════════════════════════════
function showTyping() {
  const wrap = document.createElement("div");
  wrap.className = "msg ai";
  wrap.id = "typing";
  const av  = document.createElement("div");
  av.className = "msg-av";
  av.textContent = AVATAR_INIT;
  const bub = document.createElement("div");
  bub.className = "bubble";
  bub.innerHTML = '<div class="typing-bub"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>';
  wrap.appendChild(av);
  wrap.appendChild(bub);
  msgsEl.appendChild(wrap);
  msgsEl.scrollTop = msgsEl.scrollHeight;
}
function hideTyping() { document.getElementById("typing")?.remove(); }

// ══════════════════════════════════════════════════════
//  SEND — tries streaming first, falls back to regular
// ══════════════════════════════════════════════════════
async function sendMessage(text) {
  if (streaming) return;
  text = (text || inputEl.value).trim();
  if (!text) return;

  inputEl.value = "";
  inputEl.style.height = "auto";
  sendBtn.classList.remove("active");

  appendMsg("user", text);
  history.push({ role: "user", content: text });
  showTyping();
  streaming = true;

  try {
    await sendStreaming(text);
  } catch (streamErr) {
    console.warn("Streaming failed, falling back:", streamErr.message);
    try {
      await sendRegular(text);
    } catch (regularErr) {
      hideTyping();
      showError(regularErr.message);
    }
  } finally {
    streaming = false;
  }
}

function showError(raw) {
  const isOffline = raw.includes("503") || raw.includes("still starting") || raw.includes("ECONNREFUSED");
  appendMsg("ai",
    isOffline
      ? "**AI server is warming up** ⏳\n\nThe model is still loading (this takes 30–90 seconds on first start).\n\nPlease try again in a moment!"
      : `**Something went wrong** ⚠️\n\n${raw}`
  );
}

// ── Streaming (SSE) ──────────────────────────────────
async function sendStreaming(text) {
  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ message: text, history: history.slice(-10) }),
  });

  if (!res.ok) {
    let errMsg = `HTTP ${res.status}`;
    try { const j = await res.json(); errMsg = j.error || errMsg; } catch {}
    throw new Error(errMsg);
  }

  hideTyping();

  // Create streaming bubble
  const wrap = document.createElement("div");
  wrap.className = "msg ai";
  const av  = document.createElement("div");
  av.className = "msg-av";
  av.textContent = AVATAR_INIT;
  const bub = document.createElement("div");
  bub.className = "bubble stream-cursor";
  wrap.appendChild(av);
  wrap.appendChild(bub);
  msgsEl.appendChild(wrap);

  const reader  = res.body.getReader();
  const decoder = new TextDecoder();
  let fullText  = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    for (const line of decoder.decode(value, { stream: true }).split("\n")) {
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") {
        bub.classList.remove("stream-cursor");
        bub.innerHTML = renderMd(fullText);
        history.push({ role: "assistant", content: fullText });
        if (history.length > 20) history = history.slice(-20);
        return;
      }
      try {
        const parsed = JSON.parse(payload);
        if (parsed.error) throw new Error(parsed.error);
        if (parsed.token) {
          fullText += parsed.token;
          bub.textContent = fullText;
          msgsEl.scrollTop = msgsEl.scrollHeight;
        }
      } catch (e) {
        if (e.message !== "Unexpected token" && !e.message.startsWith("JSON")) throw e;
      }
    }
  }

  bub.classList.remove("stream-cursor");
  bub.innerHTML = renderMd(fullText || "No response received.");
  history.push({ role: "assistant", content: fullText });
  if (history.length > 20) history = history.slice(-20);
}

// ── Non-streaming fallback ───────────────────────────
async function sendRegular(text) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ message: text, history: history.slice(-10) }),
  });

  const data = await res.json();
  hideTyping();

  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

  const reply = data.response || "No response received.";
  history.push({ role: "assistant", content: reply });
  if (history.length > 20) history = history.slice(-20);

  appendMsg("ai", reply, data.latency_ms);
}

// ══════════════════════════════════════════════════════
//  INPUT HANDLERS
// ══════════════════════════════════════════════════════
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + "px";
  sendBtn.classList.toggle("active", inputEl.value.trim().length > 0 && !streaming);
});

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", () => sendMessage());