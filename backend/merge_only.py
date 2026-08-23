import os, gc, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE_MODEL  = "microsoft/Phi-3-mini-4k-instruct"
BASE_DIR    = r"D:\portfolio\portfolio_Main\backend"
ADAPTER_DIR = os.path.join(BASE_DIR, "portfolio-adapter")
MERGED_DIR  = os.path.join(BASE_DIR, "portfolio-merged")

tokenizer = AutoTokenizer.from_pretrained(ADAPTER_DIR, trust_remote_code=True)

print("Loading base model onto GPU in float16...")
base = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, torch_dtype=torch.float16,
    device_map={"": 0}, trust_remote_code=True, low_cpu_mem_usage=True,
)
print("Attaching adapter...")
model = PeftModel.from_pretrained(base, ADAPTER_DIR, is_trainable=False, torch_dtype=torch.float16)
print("Merging...")
model = model.merge_and_unload(safe_merge=True)
model = model.cpu()

os.makedirs(MERGED_DIR, exist_ok=True)
model.save_pretrained(MERGED_DIR, safe_serialization=True)
tokenizer.save_pretrained(MERGED_DIR)

gc.collect()
torch.cuda.empty_cache()
print(f"✅ Done → {MERGED_DIR}")