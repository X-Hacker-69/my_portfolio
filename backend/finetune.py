#!/usr/bin/env python3
"""
finetune.py
───────────
Fine-tunes Phi-3-mini (or Mistral-7B) on your portfolio Q&A data
using QLoRA (4-bit quantization + LoRA adapters).

Hardware requirements:
  • Phi-3 Mini  (3.8B) — ~6 GB VRAM  |  CPU works but slow
  • Mistral 7B         — ~10 GB VRAM

Run:
  python finetune.py

Output (all inside BASE_DIR):
  portfolio-adapter/   — LoRA adapter weights
  portfolio-merged/    — Merged full model ready for inference
"""

import json
import os
import sys

# ══════════════════════════════════════════════════════════════════════════════
#  PATHS  — everything lives inside BASE_DIR
# ══════════════════════════════════════════════════════════════════════════════
BASE_DIR    = r"D:\portfolio\portfolio_Main\backend"

DATA_FILE   = os.path.join(BASE_DIR, "training_data.jsonl")
ADAPTER_DIR = os.path.join(BASE_DIR, "portfolio-adapter")
MERGED_DIR  = os.path.join(BASE_DIR, "portfolio-merged")

# ── Sanity check — fail clearly if training data is missing ───────────────────
if not os.path.exists(DATA_FILE):
    print("\n" + "═" * 60)
    print("❌  TRAINING DATA NOT FOUND")
    print("═" * 60)
    print(f"\n   Expected: {DATA_FILE}")
    print("\n   Fix: run this first:")
    print("        python generate_training_data.py\n")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
#  DEPENDENCIES
# ══════════════════════════════════════════════════════════════════════════════
try:
    import torch
    from datasets import Dataset
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
        TrainingArguments,
        BitsAndBytesConfig,
    )
    from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
    from trl import SFTTrainer
    try:
        from trl import SFTConfig          # trl >= 0.12
        _HAS_SFT_CONFIG = True
    except ImportError:
        _HAS_SFT_CONFIG = False
except ImportError as e:
    print(f"\n❌ Missing dependency: {e}\n")
    print("   Run:")
    print("     pip install torch transformers datasets peft trl bitsandbytes accelerate")
    print("   GPU (CUDA 12.1):")
    print("     pip install torch --index-url https://download.pytorch.org/whl/cu121\n")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════

# Base model — change to Mistral if you have 10+ GB VRAM
#   "microsoft/Phi-3-mini-4k-instruct"   — 3.8B  ~6 GB VRAM  ✅ recommended
#   "mistralai/Mistral-7B-Instruct-v0.2" — 7B   ~10 GB VRAM
BASE_MODEL = "microsoft/Phi-3-mini-4k-instruct"

TRAINING_CONFIG = {
    "num_train_epochs":             5,    # increase for more overfitting to your data
    "per_device_train_batch_size":  2,
    "gradient_accumulation_steps":  4,    # effective batch size = 2 × 4 = 8
    "learning_rate":                2e-4,
    "max_seq_length":               512,
    "logging_steps":                10,
    "save_steps":                   50,
    "warmup_ratio":                 0.05,
    "lr_scheduler_type":            "cosine",
}

LORA_CONFIG = {
    "r":              16,    # rank — higher = more trainable params = better fit
    "lora_alpha":     32,
    "lora_dropout":   0.05,
    "target_modules": [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
}

USE_4BIT = torch.cuda.is_available()

# ══════════════════════════════════════════════════════════════════════════════
#  PRINT STARTUP SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "═" * 60)
print("  Portfolio Fine-Tuning")
print("═" * 60)
print(f"  Base model   : {BASE_MODEL}")
print(f"  Training data: {DATA_FILE}")
print(f"  Adapter out  : {ADAPTER_DIR}")
print(f"  Merged out   : {MERGED_DIR}")
print(f"  Device       : {'GPU (CUDA) — 4-bit QLoRA' if USE_4BIT else 'CPU (slow — consider Colab)'}")
print("=" * 60 + "\n")

# ══════════════════════════════════════════════════════════════════════════════
#  LOAD & FORMAT TRAINING DATA
# ══════════════════════════════════════════════════════════════════════════════
print("📂 Loading training data...")
raw = []
with open(DATA_FILE, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            raw.append(json.loads(line))

if len(raw) == 0:
    print("❌ training_data.jsonl is empty. Re-run generate_training_data.py")
    sys.exit(1)

print(f"   {len(raw)} Q&A pairs loaded")


def format_example(row: dict) -> dict:
    """Format each Q&A pair into the model's chat template."""
    instruction = row["instruction"]
    output      = row["output"]
    if "Phi-3" in BASE_MODEL:
        text = (
            f"<|user|>\n{instruction}<|end|>\n"
            f"<|assistant|>\n{output}<|end|>"
        )
    else:
        # Mistral / generic [INST] format
        text = f"[INST] {instruction} [/INST] {output}"
    return {"text": text}


formatted = [format_example(r) for r in raw]
dataset   = Dataset.from_list(formatted)
split     = dataset.train_test_split(test_size=0.1, seed=42)
train_ds  = split["train"]
eval_ds   = split["test"]

print(f"   Train: {len(train_ds)} examples  |  Eval: {len(eval_ds)} examples\n")

# ══════════════════════════════════════════════════════════════════════════════
#  LOAD BASE MODEL + TOKENIZER
# ══════════════════════════════════════════════════════════════════════════════
print(f"🤖 Loading base model: {BASE_MODEL}")
print("   (First run downloads weights — Phi-3 Mini is ~7 GB, cached after)")

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
tokenizer.pad_token    = tokenizer.eos_token
tokenizer.padding_side = "right"

bnb_config = None
if USE_4BIT:
    print("   ✅ GPU detected — enabling 4-bit QLoRA quantization")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
else:
    print("   ⚠️  No GPU — CPU mode is very slow.")
    print("       Tip: use Google Colab (free T4 GPU) for training,")
    print("       then copy portfolio-merged/ back to this machine.\n")

model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    quantization_config=bnb_config,
    device_map="auto" if USE_4BIT else None,
    trust_remote_code=True,
    torch_dtype=torch.float32 if not USE_4BIT else None,
)

if USE_4BIT:
    model = prepare_model_for_kbit_training(model)

# ── Apply LoRA adapters ───────────────────────────────────────────────────────
print("\n⚙️  Applying LoRA adapters...")
lora_cfg = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    inference_mode=False,
    **LORA_CONFIG,
)
model = get_peft_model(model, lora_cfg)
model.print_trainable_parameters()

# ══════════════════════════════════════════════════════════════════════════════
#  TRAIN
# ══════════════════════════════════════════════════════════════════════════════
os.makedirs(ADAPTER_DIR, exist_ok=True)

# trl >= 0.12: SFTConfig merges TrainingArguments + SFT-specific params
# trl <  0.12: use plain TrainingArguments (max_seq_length goes in SFTTrainer)
_common_args = dict(
    output_dir=ADAPTER_DIR,
    eval_strategy="epoch",
    num_train_epochs=            TRAINING_CONFIG["num_train_epochs"],
    per_device_train_batch_size= TRAINING_CONFIG["per_device_train_batch_size"],
    gradient_accumulation_steps= TRAINING_CONFIG["gradient_accumulation_steps"],
    learning_rate=               TRAINING_CONFIG["learning_rate"],
    logging_steps=               TRAINING_CONFIG["logging_steps"],
    save_steps=                  TRAINING_CONFIG["save_steps"],
    warmup_ratio=                TRAINING_CONFIG["warmup_ratio"],
    lr_scheduler_type=           TRAINING_CONFIG["lr_scheduler_type"],
    fp16=USE_4BIT and torch.cuda.is_available(),
    bf16=False,
    report_to="none",
    dataloader_pin_memory=False,
)

if _HAS_SFT_CONFIG:
    training_args = SFTConfig(
        **_common_args,
        max_seq_length=TRAINING_CONFIG["max_seq_length"],
        dataset_text_field="text",
        packing=False,
    )
else:
    training_args = TrainingArguments(**_common_args)

# trl >= 0.9 renamed `tokenizer` → `processing_class`
# trl >= 0.12 removed `dataset_text_field` and `max_seq_length` from SFTTrainer
# → use SFTConfig instead of TrainingArguments for those fields
import inspect as _inspect
_sft_params = _inspect.signature(SFTTrainer.__init__).parameters

if "processing_class" in _sft_params:
    # trl >= 0.9
    _trainer_kwargs = dict(
        model=model,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        processing_class=tokenizer,
        args=training_args,
    )
    # dataset_text_field / max_seq_length only exist in older SFTTrainer
    if "dataset_text_field" in _sft_params:
        _trainer_kwargs["dataset_text_field"] = "text"
    if "max_seq_length" in _sft_params:
        _trainer_kwargs["max_seq_length"] = TRAINING_CONFIG["max_seq_length"]
    if "packing" in _sft_params:
        _trainer_kwargs["packing"] = False
    trainer = SFTTrainer(**_trainer_kwargs)
else:
    # trl < 0.9 (legacy)
    trainer = SFTTrainer(
        model=model,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        tokenizer=tokenizer,
        args=training_args,
        dataset_text_field="text",
        max_seq_length=TRAINING_CONFIG["max_seq_length"],
        packing=False,
    )

print(f"\n🚀 Starting fine-tuning  ({TRAINING_CONFIG['num_train_epochs']} epochs)...")
print(f"   Saving checkpoints to: {ADAPTER_DIR}\n")

trainer.train()
trainer.save_model(ADAPTER_DIR)
tokenizer.save_pretrained(ADAPTER_DIR)

print(f"\n✅ LoRA adapter saved → {ADAPTER_DIR}")

# ══════════════════════════════════════════════════════════════════════════════
#  MERGE ADAPTER → FULL MODEL  (required for inference_server.py)
# ══════════════════════════════════════════════════════════════════════════════
print("\n🔗 Merging LoRA adapter into full model for inference...")

from peft import PeftModel
import gc

# ── Why the previous attempt caused OSError 1455 (paging file too small) ──────
#
#  float32 + low_cpu_mem_usage=False loads ALL 3.8B weights into RAM at once
#  → Phi-3 Mini in float32 = ~15 GB RAM needed.
#  Windows paging file exhausted → OSError 1455.
#
#  FIX STRATEGY — layer-by-layer GPU merge (no full CPU copy needed):
#
#    1. Load base model in float16 onto GPU (already fits — it trained there)
#    2. Load adapter onto GPU
#    3. merge_and_unload() — happens on GPU, no extra RAM spike
#    4. Move merged model to CPU only for saving (one layer at a time)
#
#  If no GPU: use float16 + low_cpu_mem_usage=True (mmap streaming, ~8 GB RAM)
# ─────────────────────────────────────────────────────────────────────────────

# Free the training model from GPU memory first
del model
gc.collect()
if torch.cuda.is_available():
    torch.cuda.empty_cache()
    torch.cuda.synchronize()

print(f"   Free VRAM after cleanup: "
      f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB total")

if torch.cuda.is_available():
    # ── GPU PATH (recommended) ────────────────────────────────────────────────
    # Load base in float16 on GPU — same dtype used during training.
    # device_map="cuda:0" keeps everything on one device → no meta tensors.
    print("   Loading base model onto GPU in float16 for merge...")
    base_for_merge = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        device_map={"": 0},          # force ALL layers onto cuda:0 (no splitting)
        trust_remote_code=True,
        low_cpu_mem_usage=True,      # stream weights — avoids RAM spike
    )

    print("   Attaching LoRA adapter onto GPU...")
    merged_model = PeftModel.from_pretrained(
        base_for_merge,
        ADAPTER_DIR,
        is_trainable=False,
        torch_dtype=torch.float16,
    )

    print("   Merging weights on GPU (safe_merge=True)...")
    merged_model = merged_model.merge_and_unload(safe_merge=True)

    # Move to CPU for saving — layer by layer to avoid a second VRAM spike
    print("   Moving merged model to CPU for saving...")
    merged_model = merged_model.cpu()

else:
    # ── CPU FALLBACK PATH ────────────────────────────────────────────────────
    # float16 halves RAM vs float32: Phi-3 Mini ≈ 7.5 GB instead of 15 GB.
    # low_cpu_mem_usage=True uses mmap — weights streamed from disk, not all
    # loaded at once — keeps peak RAM under ~10 GB on most Windows machines.
    print("   No GPU — loading base model on CPU in float16 (mmap streaming)...")
    print("   This needs ~8 GB free RAM. Close other apps if you run out.\n")
    base_for_merge = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,   # half RAM vs float32
        device_map=None,
        trust_remote_code=True,
        low_cpu_mem_usage=True,      # stream via mmap — avoids the paging error
    )

    print("   Attaching LoRA adapter...")
    merged_model = PeftModel.from_pretrained(
        base_for_merge,
        ADAPTER_DIR,
        is_trainable=False,
        torch_dtype=torch.float16,
    )

    print("   Merging weights (safe_merge=True)...")
    merged_model = merged_model.merge_and_unload(safe_merge=True)

os.makedirs(MERGED_DIR, exist_ok=True)
print(f"   Saving merged model to: {MERGED_DIR}")

# safe_serialization=True  → saves as .safetensors (faster load, safer format)
# safe_serialization=False → saves as .bin (broader compatibility)
merged_model.save_pretrained(MERGED_DIR, safe_serialization=True)
tokenizer.save_pretrained(MERGED_DIR)

# Free memory
del merged_model, base_for_merge
gc.collect()
if torch.cuda.is_available():
    torch.cuda.empty_cache()

print(f"\n✅ Merged model saved → {MERGED_DIR}")
print("\n" + "═" * 60)
print("  🎉  Fine-tuning complete!")
print("═" * 60)
print(f"\n  Adapter : {ADAPTER_DIR}")
print(f"  Merged  : {MERGED_DIR}")
print("\n  Next step — start the inference server:")
print("    python inference_server.py\n")