#!/usr/bin/env python3
"""
inference_server.py  —  Portfolio AI (Groq primary + Local fallback)
═══════════════════════════════════════════════════════════════════════
Backend priority:
  1. GROQ_API_KEY set  → Groq (llama-3.3-70b — instant, free tier)
  2. No key / Groq down → Local fine-tuned Phi-3 model

ALL answers are grounded ONLY in portfolio.json — no internet knowledge.
Post-processing filter blocks any hallucinated project/company names.
"""

import json, os, sys, time, gc, re
from typing import Optional
from threading import Thread

print("🔄 Starting inference server...", flush=True)
print(f"   Python : {sys.version.split()[0]}", flush=True)
print(f"   CWD    : {os.getcwd()}", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PATHS
# ══════════════════════════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MERGED_DIR     = os.path.join(BASE_DIR, "portfolio-merged")
ADAPTER_DIR    = os.path.join(BASE_DIR, "portfolio-adapter")
INDEX_FILE     = os.path.join(BASE_DIR, "rag_index.faiss")
META_FILE      = os.path.join(BASE_DIR, "rag_meta.json")
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio.json")
BASE_ARCH      = "microsoft/Phi-3-mini-4k-instruct"
EMBED_MODEL    = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K          = 3
MAX_NEW_TOKENS = 250
PORT           = int(os.environ.get("PYTHON_PORT", 8000))

# ── Load .env ─────────────────────────────────────────────────────────────────
for _env in [
    os.path.join(BASE_DIR, ".env"),
    os.path.join(BASE_DIR, "node", ".env"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
]:
    if os.path.exists(_env):
        try:
            from dotenv import load_dotenv
            load_dotenv(_env)
            print(f"   Loaded .env: {_env}", flush=True)
        except ImportError:
            pass
        break

# ── Path check ────────────────────────────────────────────────────────────────
def _ok(p):
    return "✅" if (os.path.isfile(p) or (os.path.isdir(p) and bool(os.listdir(p)))) else "❌"

print(f"\n📂 BASE_DIR : {BASE_DIR}", flush=True)
print(f"   {_ok(PORTFOLIO_FILE)} portfolio.json", flush=True)
print(f"   {_ok(MERGED_DIR)}    portfolio-merged/", flush=True)
print(f"   {_ok(ADAPTER_DIR)}   portfolio-adapter/", flush=True)
print(f"   {_ok(INDEX_FILE)}    rag_index.faiss", flush=True)

if not os.path.exists(PORTFOLIO_FILE):
    print(f"\n❌  portfolio.json not found: {PORTFOLIO_FILE}\n", flush=True)
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
#  DETECT BACKEND
# ══════════════════════════════════════════════════════════════════════════════
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

has_local = (
    (os.path.exists(MERGED_DIR)  and bool(os.listdir(MERGED_DIR))) or
    (os.path.exists(ADAPTER_DIR) and bool(os.listdir(ADAPTER_DIR)))
)

if GROQ_API_KEY:
    BACKEND = "groq"
    print(f"\n🧠 Backend : GROQ  (llama-3.3-70b-versatile)", flush=True)
    print(f"   Free tier: 14,400 requests/day, responses in <1 second", flush=True)
elif has_local:
    BACKEND = "local"
    print(f"\n🧠 Backend : LOCAL  (fine-tuned Phi-3 — slow without GPU)", flush=True)
    print(f"   Tip: get a free Groq key at console.groq.com for instant responses", flush=True)
else:
    print("\n❌  No backend available.", flush=True)
    print("   Option A: add GROQ_API_KEY to .env  (free, instant)", flush=True)
    print("   Option B: run finetune.py to train local model", flush=True)
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
#  CORE IMPORTS
# ══════════════════════════════════════════════════════════════════════════════
print("\n📦 Importing dependencies...", flush=True)

import subprocess as _sp

def _test(label, stmt):
    r = _sp.run([sys.executable, "-c", stmt],
                capture_output=True, text=True,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    ok = r.returncode == 0
    print(f"   {'✅' if ok else '❌'} {label}", flush=True)
    if not ok:
        print(f"      {r.stderr.strip()[:200]}", flush=True)
    return ok

all_ok = True
all_ok &= _test("numpy",                 "import numpy")
all_ok &= _test("faiss",                 "import faiss")
all_ok &= _test("sentence-transformers", "from sentence_transformers import SentenceTransformer")
all_ok &= _test("fastapi",               "import fastapi")
all_ok &= _test("uvicorn",               "import uvicorn")
all_ok &= _test("pydantic",              "from pydantic import BaseModel")

if BACKEND == "groq":
    groq_ok = _test("groq",  "import groq")
    if not groq_ok:
        print("   Installing groq...", flush=True)
        _sp.run([sys.executable, "-m", "pip", "install", "groq", "-q"])
        groq_ok = _test("groq (retry)", "import groq")
        if not groq_ok:
            if has_local:
                print("   ⚠️  Groq install failed — falling back to local model", flush=True)
                BACKEND = "local"
            else:
                print("   ❌  pip install groq", flush=True)
                sys.exit(1)

if BACKEND == "local":
    all_ok &= _test("torch",        "import torch")
    all_ok &= _test("transformers", "import transformers")

if not all_ok:
    print("\n❌  Fix missing packages, then re-run.\n", flush=True)
    sys.exit(1)

# Real imports
import numpy as np
import faiss
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
print("   ✅ all imports ok", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PORTFOLIO — load and build allowed-facts lists
# ══════════════════════════════════════════════════════════════════════════════
print("\n📄 Loading portfolio...", flush=True)
with open(PORTFOLIO_FILE, encoding="utf-8") as f:
    portfolio = json.load(f)

OWNER_NAME  = portfolio["personal_info"]["name"]
OWNER_FIRST = OWNER_NAME.split()[0]
print(f"   ✅ {OWNER_NAME}", flush=True)

# Build whitelist from portfolio.json — used by hallucination filter
ALLOWED_PROJECTS  = [p["name"] for p in portfolio.get("projects", [])]
ALLOWED_COMPANIES = [e.get("company", "") for e in portfolio.get("experience", [])]

print(f"   🔒 Allowed projects  : {ALLOWED_PROJECTS}", flush=True)
print(f"   🔒 Allowed companies : {ALLOWED_COMPANIES}", flush=True)

# ── Convert portfolio to clean readable text ──────────────────────────────────
def _portfolio_as_text() -> str:
    lines = []
    info = portfolio.get("personal_info", {})
    lines += [
        f"NAME: {info.get('name','')}",
        f"TITLE: {info.get('title','')}",
        f"LOCATION: {info.get('location','')}",
        f"EMAIL: {info.get('email','')}",
        f"GITHUB: {info.get('github','')}",
        f"LINKEDIN: {info.get('linkedin','')}",
        f"ABOUT: {portfolio.get('about_me','')}",
        "",
    ]

    skills = portfolio.get("skills", {})
    for k, v in skills.items():
        if isinstance(v, list) and v:
            lines.append(f"SKILLS_{k.upper()}: {', '.join(str(x) for x in v)}")
    lines.append("")

    lines.append(f"PROJECTS — EXACTLY {len(ALLOWED_PROJECTS)} PROJECTS, NO OTHERS EXIST:")
    for pr in portfolio.get("projects", []):
        lines += [
            f"  PROJECT_NAME: {pr['name']}",
            f"  DESCRIPTION: {pr.get('description','')}",
            f"  TECH: {', '.join(pr.get('tech',[]))}",
            f"  HIGHLIGHTS: {'; '.join(pr.get('highlights',[]))}",
            f"  CATEGORY: {pr.get('category','')}",
            f"  GITHUB: {pr.get('github','')}",
            "",
        ]

    for edu in portfolio.get("education", []):
        lines.append(
            f"EDUCATION: {edu.get('degree','')} from "
            f"{edu.get('institution','')} ({edu.get('year','')}), "
            f"GPA {edu.get('gpa','')}, "
            f"Courses: {', '.join(edu.get('relevant_courses',[]))}"
        )
    lines.append("")

    for exp in portfolio.get("experience", []):
        lines.append(
            f"EXPERIENCE: {exp.get('role','')} at {exp.get('company','')} "
            f"({exp.get('period','')}): {exp.get('description','')}"
        )
    lines.append("")

    for a in portfolio.get("achievements", []):
        lines.append(f"ACHIEVEMENT: {a}")
    lines.append("")

    for h in portfolio.get("hackathons", []):
        lines.append(
            f"HACKATHON: {h.get('name','')} — "
            f"{h.get('result','')} — {h.get('project','')}"
        )
    lines.append("")

    contact = portfolio.get("contact", {})
    for k, v in contact.items():
        if v:
            lines.append(f"CONTACT_{k.upper()}: {v}")

    return "\n".join(lines)

PORTFOLIO_TEXT = _portfolio_as_text()

# ══════════════════════════════════════════════════════════════════════════════
#  SYSTEM PROMPT — strict, anti-hallucination
# ══════════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = f"""You are {OWNER_FIRST} AI, the portfolio assistant for {OWNER_NAME}.

STRICT RULES — follow ALL of these without exception:
1. Answer ONLY using the PORTFOLIO DATA below. Never use outside knowledge.
2. You may ONLY mention these {len(ALLOWED_PROJECTS)} project(s): {', '.join(ALLOWED_PROJECTS)}
   NEVER mention, invent, or reference any other project names.
3. You may ONLY mention these companies: {', '.join(ALLOWED_COMPANIES) or 'none'}
4. If asked about anything not in the data, respond EXACTLY:
   "I don't have that information in {OWNER_FIRST}'s portfolio."
5. Never guess, assume, or say "probably" or "might".
6. Keep answers under 150 words. Use bullet points for lists.
7. Do not add disclaimers, caveats, or meta-commentary about yourself.

PORTFOLIO DATA (this is the ONLY source you may use):
{PORTFOLIO_TEXT}"""

# ══════════════════════════════════════════════════════════════════════════════
#  HALLUCINATION FILTER
#  Scans output for project/app names not in ALLOWED_PROJECTS and removes them
# ══════════════════════════════════════════════════════════════════════════════
# Generic words that look like project names but are not
_GENERIC_TERMS = {
    "machine learning", "deep learning", "neural network", "artificial intelligence",
    "natural language", "the system", "this project", "the project", "this app",
    "the app", "the platform", "web app", "mobile app", "the tool", "the bot",
    "the dashboard", "the api", "data science", "computer vision",
}

def filter_hallucinations(text: str) -> str:
    """
    Remove sentences containing project-sounding names
    that are NOT in the portfolio.
    """
    if not text or not ALLOWED_PROJECTS:
        return text

    # Pattern: Title Case words followed by project-type nouns
    pattern = re.compile(
        r'\b([A-Z][A-Za-z0-9\s\-]{2,35}'
        r'(?:System|App|Platform|Tool|Bot|AI|Dashboard|API|'
        r'Framework|Project|Assistant|Engine|Model|Network|'
        r'Detector|Generator|Analyzer|Tracker|Manager))\b'
    )

    allowed_lower = {p.lower() for p in ALLOWED_PROJECTS}
    sentences = re.split(r'(?<=[.!?\n])\s+', text.strip())
    clean = []

    for sentence in sentences:
        hallucinated = False
        for match in pattern.finditer(sentence):
            candidate = match.group(1).strip()
            candidate_lower = candidate.lower()
            if (
                candidate_lower not in allowed_lower and
                candidate_lower not in _GENERIC_TERMS and
                len(candidate) > 4
            ):
                print(f"   🚫 Hallucination blocked: '{candidate}'", flush=True)
                hallucinated = True
                break
        if not hallucinated:
            clean.append(sentence)

    result = " ".join(clean).strip()
    if not result:
        return (
            f"{OWNER_FIRST}'s projects are: {', '.join(ALLOWED_PROJECTS)}. "
            "Ask me about any of them for details!"
        )
    return result

# ══════════════════════════════════════════════════════════════════════════════
#  RAG
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n🔍 Loading RAG embedder ({EMBED_MODEL})...", flush=True)
embedder = SentenceTransformer(EMBED_MODEL)
print("   ✅ Embedder ready", flush=True)

faiss_index = rag_meta = None
if os.path.exists(INDEX_FILE) and os.path.exists(META_FILE):
    faiss_index = faiss.read_index(INDEX_FILE)
    with open(META_FILE, encoding="utf-8") as f:
        rag_meta = json.load(f)
    print(f"   ✅ FAISS index ({faiss_index.ntotal} vectors)", flush=True)
else:
    print("   ⚠️  No FAISS index — run build_rag_index.py", flush=True)


def retrieve(query: str) -> list:
    if not faiss_index:
        return []
    vec = embedder.encode(
        [query], convert_to_numpy=True, normalize_embeddings=True
    ).astype("float32")
    faiss.normalize_L2(vec)
    scores, ids = faiss_index.search(vec, TOP_K)
    return [
        {"text":   rag_meta["texts"][i],
         "source": rag_meta["sources"][i],
         "score":  float(s)}
        for s, i in zip(scores[0], ids[0]) if i >= 0
    ]

# ══════════════════════════════════════════════════════════════════════════════
#  GROQ CLIENT
# ══════════════════════════════════════════════════════════════════════════════
groq_client = None
GROQ_MODEL  = "openai/gpt-oss-120b"   # best free Groq model

if BACKEND == "groq":
    import groq as _groq
    groq_client = _groq.Groq(api_key=GROQ_API_KEY)
    print(f"\n✅ Groq client ready  (model: {GROQ_MODEL})", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
#  LOCAL MODEL
# ══════════════════════════════════════════════════════════════════════════════
llm = tokenizer = device = None

if BACKEND == "local":
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\n🤖 Loading local model on {device.upper()}...", flush=True)
    print("   Takes 30–90 seconds on first run...", flush=True)

    _model_path = (
        MERGED_DIR  if (os.path.exists(MERGED_DIR)  and os.listdir(MERGED_DIR))
        else ADAPTER_DIR
    )
    print(f"   Source: {_model_path}", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(_model_path, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    print("   ✅ Tokenizer ready", flush=True)

    _IS_ADAPTER = (_model_path == ADAPTER_DIR)
    if _IS_ADAPTER:
        from peft import PeftModel
        _base = AutoModelForCausalLM.from_pretrained(
            BASE_ARCH,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map={"": 0} if device == "cuda" else None,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )
        llm = PeftModel.from_pretrained(_base, _model_path)
    else:
        llm = AutoModelForCausalLM.from_pretrained(
            _model_path,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map={"": 0} if device == "cuda" else None,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            attn_implementation="eager",
        )

    llm.eval()
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
        used  = torch.cuda.memory_allocated(0) / 1e9
        total = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"   ✅ Model ready ({used:.1f}/{total:.1f} GB VRAM)", flush=True)
    else:
        print("   ✅ Model ready (CPU)", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PROMPT BUILDERS
# ══════════════════════════════════════════════════════════════════════════════
def _rag_block(chunks: list) -> str:
    """Extra emphasis from top RAG chunks — reinforces the right answer."""
    if not chunks:
        return ""
    lines = [f"  [{c['source']}]: {c['text'][:350]}" for c in chunks[:2]]
    return "\n\nMOST RELEVANT EXCERPT FROM PORTFOLIO:\n" + "\n".join(lines)


def build_groq_messages(user_msg: str, chunks: list, history: list) -> list:
    """OpenAI-style message list for Groq API."""
    system = SYSTEM_PROMPT + _rag_block(chunks)
    messages = [{"role": "system", "content": system}]
    for t in history[-4:]:
        messages.append({"role": t["role"], "content": t["content"][:300]})
    messages.append({"role": "user", "content": user_msg})
    return messages


def build_local_prompt(user_msg: str, chunks: list, history: list) -> str:
    """Phi-3 <|system|>/<|user|>/<|assistant|> format."""
    system = SYSTEM_PROMPT + _rag_block(chunks)
    # Append reminder right before user turn where attention is strongest
    reminder = (
        f"\nREMINDER: ONLY use data above. "
        f"ONLY mention projects: {', '.join(ALLOWED_PROJECTS)}. "
        f"Do NOT invent anything."
    )

    hist = ""
    for t in history[-2:]:
        role = "User" if t["role"] == "user" else "Assistant"
        hist += f"\n{role}: {t['content'][:150]}"

    return (
        f"<|system|>\n{system}{reminder}<|end|>"
        f"{hist}"
        f"\n<|user|>\n{user_msg}<|end|>"
        f"\n<|assistant|>\n"
    )

# ══════════════════════════════════════════════════════════════════════════════
#  GENERATE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════
def generate_groq(user_msg: str, chunks: list, history: list) -> str:
    messages = build_groq_messages(user_msg, chunks, history)
    resp = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=300,
        temperature=0.1,      # near-zero temperature = factual, no creativity/hallucination
        top_p=0.9,
    )
    return resp.choices[0].message.content.strip()


def generate_local(user_msg: str, chunks: list, history: list) -> str:
    import torch
    prompt = build_local_prompt(user_msg, chunks, history)
    inputs = tokenizer(prompt, return_tensors="pt",
                       truncation=True, max_length=1024)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        out = llm.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            use_cache=True,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
            repetition_penalty=1.05,
        )
    new_ids  = out[0][inputs["input_ids"].shape[1]:]
    raw      = tokenizer.decode(new_ids, skip_special_tokens=True).strip()
    filtered = filter_hallucinations(raw)
    if filtered != raw:
        print(f"   🔍 Filtered: {len(raw)} → {len(filtered)} chars", flush=True)
    return filtered


def generate(user_msg: str, chunks: list, history: list) -> str:
    """Try Groq first — fall back to local if Groq fails."""
    if BACKEND == "groq":
        try:
            return generate_groq(user_msg, chunks, history)
        except Exception as e:
            err = str(e)
            print(f"   ⚠️  Groq error: {err[:100]}", flush=True)
            if "rate" in err.lower() or "429" in err:
                print("   ⚠️  Groq rate limited — waiting 5s then retrying...", flush=True)
                time.sleep(5)
                try:
                    return generate_groq(user_msg, chunks, history)
                except Exception as e2:
                    print(f"   ⚠️  Groq retry failed: {str(e2)[:80]}", flush=True)
            if has_local and llm is not None:
                print("   ↩️  Falling back to local model...", flush=True)
                return generate_local(user_msg, chunks, history)
            raise
    else:
        return generate_local(user_msg, chunks, history)

# ══════════════════════════════════════════════════════════════════════════════
#  FASTAPI
# ══════════════════════════════════════════════════════════════════════════════
app = FastAPI(title="Portfolio AI", version="4.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = []
    stream:  Optional[bool] = False

class ChatResponse(BaseModel):
    response:   str
    sources:    list
    latency_ms: int
    backend:    str


@app.get("/health")
def health():
    return {
        "status":      "ok",
        "backend":     BACKEND,
        "model":       GROQ_MODEL if BACKEND == "groq" else str(MERGED_DIR),
        "rag_enabled": faiss_index is not None,
        "owner":       OWNER_NAME,
        "projects":    ALLOWED_PROJECTS,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    t0     = time.time()
    chunks = retrieve(req.message)
    try:
        reply = generate(req.message, chunks, req.history or [])
    except Exception as e:
        reply = f"I'm having trouble answering right now. Error: {str(e)[:80]}"
    return ChatResponse(
        response=reply,
        sources=[c["source"] for c in chunks],
        latency_ms=int((time.time() - t0) * 1000),
        backend=BACKEND,
    )


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Groq: returns full answer then streams it word-by-word for smooth animation.
    Local: streams real tokens from the model.
    """
    chunks = retrieve(req.message)

    def event_gen():
        try:
            if BACKEND == "groq":
                # Get answer from Groq then stream words at 15ms/word
                reply = generate_groq(req.message, chunks, req.history or [])
                words = reply.split(" ")
                for i, word in enumerate(words):
                    token = ("" if i == 0 else " ") + word
                    yield f"data: {json.dumps({'token': token})}\n\n"
                    time.sleep(0.015)
            else:
                # Real token-by-token streaming from local model
                import torch
                from transformers import TextIteratorStreamer
                prompt  = build_local_prompt(req.message, chunks, req.history or [])
                inputs  = tokenizer(prompt, return_tensors="pt",
                                    truncation=True, max_length=1024)
                inputs  = {k: v.to(device) for k, v in inputs.items()}
                streamer = TextIteratorStreamer(
                    tokenizer, skip_prompt=True,
                    skip_special_tokens=True, timeout=60.0
                )
                Thread(target=lambda: llm.generate(
                    **inputs,
                    max_new_tokens=MAX_NEW_TOKENS,
                    do_sample=False,
                    use_cache=True,
                    pad_token_id=tokenizer.eos_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                    repetition_penalty=1.05,
                    streamer=streamer,
                ), daemon=True).start()

                buf = ""
                full = ""
                for token in streamer:
                    buf  += token
                    full += token
                    if " " in buf or "\n" in buf or len(buf) >= 6:
                        yield f"data: {json.dumps({'token': buf})}\n\n"
                        buf = ""
                if buf:
                    yield f"data: {json.dumps({'token': buf})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@app.get("/portfolio")
def get_portfolio():
    return portfolio


@app.get("/summary")
def get_summary():
    edu = portfolio.get("education", [{}])[0]
    return {
        "name":         OWNER_NAME,
        "title":        portfolio["personal_info"].get("title", ""),
        "education":    f"{edu.get('degree','')} — {edu.get('institution','')} ({edu.get('gpa','')} GPA)",
        "top_projects": [{"name": p["name"], "category": p.get("category", "")}
                         for p in portfolio.get("projects", [])[:3]],
        "achievements": portfolio.get("achievements", [])[:3],
        "contact":      portfolio.get("contact", {}),
        "backend":      BACKEND,
    }


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{'='*56}", flush=True)
    print(f"  ✅  Portfolio AI ready!", flush=True)
    print(f"  🧠  Backend  : {BACKEND.upper()}", flush=True)
    if BACKEND == "groq":
        print(f"  ⚡  Model    : {GROQ_MODEL}", flush=True)
    print(f"  🌐  API      : http://localhost:{PORT}", flush=True)
    print(f"  📖  Docs     : http://localhost:{PORT}/docs", flush=True)
    print(f"{'='*56}\n", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")