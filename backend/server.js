/**
 * server.js  —  Unified Portfolio Server
 * ─────────────────────────────────────────────────────────────────────────────
 * Single command starts EVERYTHING:
 *
 *   1. 🐍  Python inference server  — spawned automatically as child process
 *   2. 🤖  Chatbot API gateway      — proxies /api/chat  →  Python (:8000)
 *   3. 🗄️   MongoDB + Contact form  — saves messages, Twilio WhatsApp alert
 *   4. 🌐  Frontend static server   — serves your portfolio HTML/CSS/JS
 *
 * Run:   npm start   (or: node server.js)
 * ─────────────────────────────────────────────────────────────────────────────
 */

"use strict";
require("dotenv").config();

const express    = require("express");
const http       = require("http");
const path       = require("path");
const cors       = require("cors");
const mongoose   = require("mongoose");
const twilio     = require("twilio");
const rateLimit  = require("express-rate-limit");
const { spawn }  = require("child_process");

const Contact = require("./models/Contact");

// ── Env config ────────────────────────────────────────────────────────────────
const PORT         = process.env.PORT         || 5000;
const PY_HOST      = process.env.PYTHON_HOST  || "localhost";
const PY_PORT      = parseInt(process.env.PYTHON_PORT || "8000");
const PY_SCRIPT    = process.env.PYTHON_SCRIPT || path.join(__dirname, "inference_server.py");  // absolute path to inference_server.py
const PY_EXEC      = process.env.PYTHON_EXEC  || (process.platform === "win32" ? path.join(__dirname, ".venv", "Scripts", "python.exe") : "python3"); // python / python3 / full venv path
const FRONTEND_DIR = process.env.FRONTEND_DIR || path.join(__dirname, "..");           // absolute path to your frontend folder

// ══════════════════════════════════════════════════════════════════════════════
//  1.  AUTO-SPAWN PYTHON INFERENCE SERVER
// ══════════════════════

let pyProcess = null;
function spawnPython() {
  if (!PY_SCRIPT) {
    console.log("⚠️  PYTHON_SCRIPT not set in .env — skipping auto-spawn.");
    console.log("   Set it to the full path of inference_server.py and restart.");
    return;
  }

  if (!require("fs").existsSync(PY_SCRIPT)) {
    console.error(`❌  PYTHON_SCRIPT not found: ${PY_SCRIPT}`);
    return;
  }

  console.log(`\n🐍 Spawning Python inference server...`);
  console.log(`   exec   : ${PY_EXEC}`);
  console.log(`   script : ${PY_SCRIPT}`);

  pyProcess = spawn(PY_EXEC, [PY_SCRIPT], {
    cwd:   path.dirname(PY_SCRIPT),
    env:   {
      ...process.env,
      PYTHONIOENCODING: "utf-8",
      PYTHON_PORT:      String(PY_PORT),
    },
    stdio: ["ignore", "pipe", "pipe"],   // capture stdout + stderr
  });

  // Stream Python output directly to Node console with a prefix
  pyProcess.stdout.on("data", (d) => {
    d.toString().split("\n").filter(Boolean)
     .forEach(line => console.log(`   [python] ${line}`));
  });
  pyProcess.stderr.on("data", (d) => {
    d.toString().split("\n").filter(Boolean)
     .forEach(line => console.error(`   [python:err] ${line}`));
  });

  pyProcess.on("exit", (code, signal) => {
    if (code !== 0 && code !== null) {
      console.error(`\n❌ Python server exited with code ${code}.`);
      console.log("   Retrying in 5 seconds...\n");
      setTimeout(spawnPython, 5000);   // auto-restart on crash
    } else {
      console.log(`\n🐍 Python server stopped (code=${code}).`);
    }
  });

  pyProcess.on("error", (err) => {
    console.error(`\n❌ Failed to spawn Python: ${err.message}`);
    console.log(`   Make sure PYTHON_EXEC="${PY_EXEC}" is correct in .env\n`);
  });
}

// Graceful shutdown — kill Python when Node exits
function shutdown() {
  console.log("\n🛑 Shutting down...");
  if (pyProcess) { pyProcess.kill("SIGTERM"); }
  process.exit(0);
}
process.on("SIGINT",  shutdown);
process.on("SIGTERM", shutdown);

// Start Python immediately
spawnPython();

// ══════════════════════════════════════════════════════════════════════════════
//  2.  MONGODB
// ══════════════════════════════════════════════════════════════════════════════
mongoose
  .connect(process.env.MONGO_URI)
  .then(() => console.log("\n🗄️  MongoDB connected"))
  .catch((err) => {
    console.error("❌ MongoDB connection failed:", err.message);
    console.warn("   Contact form disabled until MongoDB is available.");
  });

// ══════════════════════════════════════════════════════════════════════════════
//  3.  TWILIO
// ══════════════════════════════════════════════════════════════════════════════
let twilioClient = null;
if (process.env.TWILIO_SID && process.env.TWILIO_AUTH) {
  twilioClient = twilio(process.env.TWILIO_SID, process.env.TWILIO_AUTH);
  console.log("📲 Twilio ready");
} else {
  console.warn("⚠️  Twilio disabled (TWILIO_SID/TWILIO_AUTH not set)");
}

// ══════════════════════════════════════════════════════════════════════════════
//  4.  EXPRESS + MIDDLEWARE
// ══════════════════════════════════════════════════════════════════════════════
const app = express();
app.set("trust proxy", true);  // for rate-limiter behind reverse proxy

app.use(cors({
  origin: (origin, cb) => {
    const allowed = [
      `http://localhost:${PORT}`,
      `http://127.0.0.1:${PORT}`,
      process.env.FRONTEND_ORIGIN,
    ].filter(Boolean);
    if (!origin || allowed.includes(origin) || process.env.NODE_ENV !== "production") {
      return cb(null, true);
    }
    cb(new Error(`CORS blocked: ${origin}`));
  },
  methods: ["GET", "POST", "OPTIONS"],
  allowedHeaders: ["Content-Type"],
}));

app.use(express.json({ limit: "10kb" }));

// ── Serve frontend ────────────────────────────────────────────────────────────
// Priority: FRONTEND_DIR env var  →  ../frontend/public  →  ./public
const frontendDir = FRONTEND_DIR
  || path.join(__dirname, "..", "frontend", "public")
  || path.join(__dirname, "public");

if (require("fs").existsSync(frontendDir)) {
  app.use(express.static(frontendDir));
  console.log(`🌐 Serving frontend from: ${frontendDir}`);
} else {
  console.warn(`⚠️  Frontend folder not found: ${frontendDir}`);
  console.warn("   Set FRONTEND_DIR in .env to your frontend folder path.");
}

// ── Rate limiters ─────────────────────────────────────────────────────────────
const chatLimiter = rateLimit({
  windowMs: 60_000, max: 30,
  message: { error: "Too many requests — slow down." },
  standardHeaders: true, legacyHeaders: false,
});

const contactLimiter = rateLimit({
  windowMs: 10 * 60_000, max: 5,
  message: { success: false, error: "Too many submissions — try again later." },
  standardHeaders: true, legacyHeaders: false,
});

// ══════════════════════════════════════════════════════════════════════════════
//  ROUTES — HEALTH
// ══════════════════════════════════════════════════════════════════════════════
app.get("/health", (req, res) => {
  res.json({
    node:    "ok",
    mongodb: mongoose.connection.readyState === 1 ? "connected" : "disconnected",
    twilio:  twilioClient ? "enabled" : "disabled",
    python:  pyProcess && !pyProcess.killed ? "spawned" : "not running",
  });
});

app.get("/api/status", async (req, res) => {
  try {
    const data = await pyGet("/health");
    res.json({
      node:    "ok",
      mongodb: mongoose.connection.readyState === 1 ? "connected" : "disconnected",
      python:  data,
    });
  } catch {
    res.status(503).json({ node: "ok", python: "unavailable — still starting up" });
  }
});

// ══════════════════════════════════════════════════════════════════════════════
//  ROUTES — CHATBOT  (proxy → Python inference server)
// ══════════════════════════════════════════════════════════════════════════════

// ── POST /api/chat  (non-streaming) ──────────────────────────────────────────
app.post("/api/chat", chatLimiter, async (req, res) => {
  const { message, history = [] } = req.body;

  if (!message || typeof message !== "string") {
    return res.status(400).json({ error: "message field required" });
  }
  if (message.length > 1000) {
    return res.status(400).json({ error: "Message too long (max 1000 chars)" });
  }

  try {
    const result = await pyPost("/chat", {
      message: message.trim(),
      history,
      stream: false,
    });
    res.json(result);
  } catch (err) {
    console.error("Chat proxy error:", err.message);
    const offline = err.message.includes("ECONNREFUSED");
    res.status(offline ? 503 : 500).json({
      error:    offline ? "AI server is still starting up — try again in a moment." : err.message,
      response: offline ? "⚠️ I'm still warming up! Please wait a few seconds and try again." : "Something went wrong.",
    });
  }
});

// ── POST /api/chat/stream  (SSE token streaming) ─────────────────────────────
//
//  FIX: Connect to Python FIRST — only flush SSE headers once Python responds.
//  If Python is down we return a clean JSON 503 (not a 405).
//
app.post("/api/chat/stream", chatLimiter, (req, res) => {
  const { message, history = [] } = req.body;

  if (!message || typeof message !== "string") {
    return res.status(400).json({ error: "message field required" });
  }

  const body = JSON.stringify({
    message: message.trim(),
    history,
    stream: true,
  });

  // Open connection to Python BEFORE touching the browser response
  const pyReq = http.request(
    {
      hostname: PY_HOST,
      port:     PY_PORT,
      path:     "/chat/stream",
      method:   "POST",
      headers: {
        "Content-Type":   "application/json",
        "Content-Length": Buffer.byteLength(body),
      },
    },
    (pyRes) => {
      // Python responded — safe to switch browser to SSE mode now
      res.setHeader("Content-Type",  "text/event-stream");
      res.setHeader("Cache-Control", "no-cache");
      res.setHeader("Connection",    "keep-alive");
      res.flushHeaders();

      pyRes.on("data",  (chunk) => res.write(chunk));
      pyRes.on("end",   ()      => res.end());
    }
  );

  pyReq.on("error", (err) => {
    if (!res.headersSent) {
      const msg = err.message.includes("ECONNREFUSED")
        ? "AI server is still starting up. Please wait 30 seconds and try again."
        : `AI server error: ${err.message}`;
      return res.status(503).json({ error: msg });
    }
    res.write(`data: ${JSON.stringify({ error: "AI server disconnected" })}\n\n`);
    res.end();
  });

  pyReq.setTimeout(120_000, () => {
    pyReq.destroy();
    if (!res.headersSent) res.status(504).json({ error: "AI server timed out" });
  });

  pyReq.write(body);
  pyReq.end();
  req.on("close", () => pyReq.destroy());
});

// ── GET /api/portfolio  /api/summary  (passthroughs) ─────────────────────────
app.get("/api/portfolio", async (req, res) => {
  try  { res.json(await pyGet("/portfolio")); }
  catch { res.status(503).json({ error: "Python server unavailable" }); }
});

app.get("/api/summary", async (req, res) => {
  try  { res.json(await pyGet("/summary")); }
  catch { res.status(503).json({ error: "Python server unavailable" }); }
});

// ══════════════════════════════════════════════════════════════════════════════
//  ROUTES — CONTACT FORM  (MongoDB + Twilio)
// ══════════════════════════════════════════════════════════════════════════════
app.post("/send", contactLimiter, async (req, res) => {
  try {
    const { name, email, subject, message } = req.body;

    if (!name || !email || !message) {
      return res.status(400).json({ success: false, error: "name, email and message are required" });
    }

    // Save to MongoDB
    const contact = new Contact({ name, email, subject, message });
    await contact.save();
    console.log(`📩 Contact saved: ${name} <${email}>`);

    // WhatsApp alert — non-blocking
    if (twilioClient) {
      twilioClient.messages.create({
        body: `New Portfolio Message\n\nName: ${name}\nEmail: ${email}\nSubject: ${subject || "—"}\nMessage: ${message}`,
        from: process.env.TWILIO_FROM,
        to:   process.env.TO_WHATSAPP,
      })
      .then(()  => console.log("📲 WhatsApp alert sent"))
      .catch(e  => console.error("Twilio error:", e.message));
    }

    res.json({ success: true });

  } catch (err) {
    console.error("Contact error:", err.message);
    res.status(500).json({ success: false, error: "Server error — please try again." });
  }
});

// ── SPA fallback — must be LAST ───────────────────────────────────────────────
app.get("/{*path}", (req, res) => {
  const index = path.join(frontendDir, "index.html");
  if (require("fs").existsSync(index)) {
    res.sendFile(index);
  } else {
    res.status(404).send("Frontend not found. Set FRONTEND_DIR in .env");
  }
});

// ══════════════════════════════════════════════════════════════════════════════
//  PYTHON HTTP HELPERS
// ══════════════════════════════════════════════════════════════════════════════
function pyGet(apiPath) {
  return new Promise((resolve, reject) => {
    const req = http.get(`http://${PY_HOST}:${PY_PORT}${apiPath}`, (res) => {
      let data = "";
      res.on("data", (c) => (data += c));
      res.on("end",  () => {
        try  { resolve(JSON.parse(data)); }
        catch { reject(new Error("Invalid JSON from Python")); }
      });
    });
    req.on("error", reject);
    req.setTimeout(10_000, () => { req.destroy(); reject(new Error("Timeout")); });
  });
}

function pyPost(apiPath, body) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify(body);
    const req = http.request(
      {
        hostname: PY_HOST,
        port:     PY_PORT,
        path:     apiPath,
        method:   "POST",
        headers: {
          "Content-Type":   "application/json",
          "Content-Length": Buffer.byteLength(payload),
        },
      },
      (res) => {
        let data = "";
        res.on("data", (c) => (data += c));
        res.on("end",  () => {
          try  { resolve(JSON.parse(data)); }
          catch { reject(new Error("Invalid JSON from Python")); }
        });
      }
    );
    req.on("error", reject);
    req.setTimeout(120_000, () => { req.destroy(); reject(new Error("Timeout")); });
    req.write(payload);
    req.end();
  });
}

// ══════════════════════════════════════════════════════════════════════════════
//  START NODE SERVER
// ══════════════════════════════════════════════════════════════════════════════
app.listen(PORT, () => {
  console.log("\n" + "=".repeat(56));
  console.log("  Portfolio Server — All Systems Go");
  console.log("=".repeat(56));
  console.log(`  Frontend   ->  http://localhost:${PORT}`);
  console.log(`  Chat API   ->  http://localhost:${PORT}/api/chat`);
  console.log(`  AI Proxy   ->  http://${PY_HOST}:${PY_PORT}  (Python)`);
  console.log(`  MongoDB    ->  ${process.env.MONGO_URI ? "URI loaded" : "MISSING"}`);
  console.log(`  Twilio     ->  ${twilioClient ? "enabled" : "disabled"}`);
  console.log(`  Frontend   ->  ${frontendDir}`);
  console.log("=".repeat(56) + "\n");

  // Ping Python after 8 seconds (give it time to load the model)
  setTimeout(() => {
    const ping = http.get(`http://${PY_HOST}:${PY_PORT}/health`, (res) => {
      let body = "";
      res.on("data", c => (body += c));
      res.on("end",  () => {
        try {
          const info = JSON.parse(body);
          console.log(`\n  [check] Python AI server ONLINE`);
          console.log(`          model   : ${info.model || "loaded"}`);
          console.log(`          device  : ${info.device || "unknown"}`);
          console.log(`          rag     : ${info.rag_enabled ? "enabled" : "disabled"}`);
          console.log("          Chatbot is ready!\n");
        } catch {
          console.log("  [check] Python AI server is ONLINE\n");
        }
      });
    });
    ping.on("error", () => {
      console.log("  [check] Python AI server still loading — this is normal.");
      console.log("          Model loading takes 30-90 seconds on first run.\n");
    });
    ping.setTimeout(3000, () => ping.destroy());
  }, 8000);
});