# -*- coding: utf-8 -*-
import json, os, sys, subprocess
print("RAG index builder starting...", flush=True)
print("Python: " + sys.executable, flush=True)

BASE_DIR    = r"D:\portfolio\portfolio_Main\backend"
CHUNKS_FILE = os.path.join(BASE_DIR, "rag_chunks.json")
INDEX_FILE  = os.path.join(BASE_DIR, "rag_index.faiss")
META_FILE   = os.path.join(BASE_DIR, "rag_meta.json")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

print("\nFiles:", flush=True)
print("  chunks : " + ("OK" if os.path.exists(CHUNKS_FILE) else "MISSING") + " " + CHUNKS_FILE, flush=True)
print("  index  : " + ("exists - will overwrite" if os.path.exists(INDEX_FILE) else "will create") + " " + INDEX_FILE, flush=True)
print("  meta   : " + ("exists - will overwrite" if os.path.exists(META_FILE)  else "will create") + " " + META_FILE,  flush=True)

if not os.path.exists(CHUNKS_FILE):
    print("\nERROR: rag_chunks.json not found.", flush=True)
    print("Run: python generate_training_data.py\n", flush=True)
    sys.exit(1)

# Quick import tests via subprocess
print("\nTesting imports...", flush=True)
for label, stmt in [
    ("numpy",                 "import numpy; print(numpy.__version__)"),
    ("sentence-transformers", "from sentence_transformers import SentenceTransformer; print('ok')"),
    ("faiss",                 "import faiss; print('ok')"),
]:
    r = subprocess.run([sys.executable, "-c", stmt], capture_output=True, text=True,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if r.returncode == 0:
        print("  OK  " + label + " - " + r.stdout.strip(), flush=True)
    else:
        print("  FAIL " + label, flush=True)
        print("  " + r.stderr.strip()[:300], flush=True)
        sys.exit(1)

# Worker script — pure ASCII strings only to avoid cp1252 issues
worker = r"""
import sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
print("  [worker] importing numpy", flush=True)
import numpy as np
print("  [worker] importing sentence_transformers", flush=True)
from sentence_transformers import SentenceTransformer
print("  [worker] importing faiss", flush=True)
import faiss
print("  [worker] all imports ok", flush=True)

CHUNKS_FILE = r"__CHUNKS__"
INDEX_FILE  = r"__INDEX__"
META_FILE   = r"__META__"
EMBED_MODEL = "__MODEL__"

with open(CHUNKS_FILE, encoding="utf-8") as f:
    chunks = json.load(f)
texts   = [c["text"]   for c in chunks]
sources = [c["source"] for c in chunks]
print("  [worker] " + str(len(texts)) + " chunks loaded", flush=True)

print("  [worker] loading model: " + EMBED_MODEL, flush=True)
model = SentenceTransformer(EMBED_MODEL)
dim   = model.get_sentence_embedding_dimension()
print("  [worker] dim=" + str(dim), flush=True)

print("  [worker] encoding...", flush=True)
embeddings = model.encode(texts, show_progress_bar=True,
                          convert_to_numpy=True, normalize_embeddings=True, batch_size=32)
embeddings = embeddings.astype("float32")
print("  [worker] shape: " + str(embeddings.shape), flush=True)

faiss.normalize_L2(embeddings)
index = faiss.IndexFlatIP(dim)
index.add(embeddings)
print("  [worker] " + str(index.ntotal) + " vectors indexed", flush=True)

faiss.write_index(index, INDEX_FILE)
with open(META_FILE, "w", encoding="utf-8") as f:
    json.dump({"texts": texts, "sources": sources,
               "embed_model": EMBED_MODEL, "dim": dim,
               "num_chunks": len(texts)}, f, indent=2, ensure_ascii=False)

print("  [worker] index saved", flush=True)
print("  [worker] meta saved", flush=True)
print("DONE:" + str(len(texts)) + ":" + str(dim), flush=True)
"""

worker = (worker
    .replace("__CHUNKS__", CHUNKS_FILE.replace("\\", "\\\\"))
    .replace("__INDEX__",  INDEX_FILE.replace("\\", "\\\\"))
    .replace("__META__",   META_FILE.replace("\\", "\\\\"))
    .replace("__MODEL__",  EMBED_MODEL)
)

print("\nRunning embedding worker...", flush=True)
env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
result = subprocess.run(
    [sys.executable, "-c", worker],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    env=env,
)
output = result.stdout.decode("utf-8", errors="replace")

for line in output.splitlines():
    print(line, flush=True)

if result.returncode != 0:
    print("\nERROR: worker failed - see output above.", flush=True)
    sys.exit(1)

done = next((l for l in output.splitlines() if l.startswith("DONE:")), None)
if done:
    parts  = done.split(":")
    chunks = parts[1]
    dim    = parts[2]
    print("\n" + "="*50, flush=True)
    print("  RAG index built successfully!", flush=True)
    print("  Chunks : " + chunks, flush=True)
    print("  Dim    : " + dim, flush=True)
    print("  Model  : " + EMBED_MODEL, flush=True)
    print("  Index  : " + INDEX_FILE, flush=True)
    print("  Meta   : " + META_FILE, flush=True)
    print("="*50, flush=True)
    print("\nNext: python inference_server.py\n", flush=True)
else:
    print("\nWARNING: worker finished but DONE line not found.", flush=True)
    print("Check that index/meta files were written.\n", flush=True)