"""Generate benchmark outputs for every system on the held-out test pairs (Modal, vLLM).

Systems:
  base     — Glimmer with the same prompt as the LoRA, no adapter
  fewshot  — Glimmer + 5 of the user's own train turns from the same audience & situation
  <run>    — Glimmer + LoRA adapter /data/adapters/<run> (one per --adapters entry)
All answers are forced into the user channel with low reasoning, exactly like training.

  .venv/bin/modal run eval/bench_generate.py --adapters v1,v1e1
Writes data/bench/outputs.jsonl locally (gitignored: contains the user's own messages).
"""

import json
from pathlib import Path

import modal

BASE_MODEL = "meta-models/Muse-Glimmer-30B"
REASONING = "Reasoning strength: low."
FEW_SHOT = 5

image = (
    modal.Image.from_registry("vllm/vllm-openai:v0.28.0")  # use the image's own Python, where vllm lives
    .entrypoint([])
    .run_commands("ln -sf $(command -v python3) /usr/local/bin/python")  # Modal looks for `python`
    .env({"HF_HOME": "/cache/hf"})
)
hf_cache = modal.Volume.from_name("sayso-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("sayso-data", create_if_missing=True)
app = modal.App("sayso-bench")


def few_shot_system(system, examples, audience, situation):
    shots = "\n\n".join(f"<example>\n{text}\n</example>" for text in examples)
    return (f"{system}\nHere are real messages this user wrote to {audience} in similar situations "
            f"({situation}). Match their style exactly: length, punctuation, case, emoji, slang, line breaks.\n\n{shots}")


@app.function(image=image, gpu="H100", volumes={"/cache": hf_cache, "/data": data}, timeout=2 * 60 * 60)
def generate(adapters: list[str], limit: int = 0, seed: int = 0, pairs: str = "pairs"):
    import random
    from collections import defaultdict

    from vllm import LLM, SamplingParams
    from vllm.lora.request import LoRARequest

    def load(split):
        return [json.loads(line) for line in open(f"/data/{pairs}/{split}.jsonl", encoding="utf-8")]

    train, test = load("train"), load("test")
    if limit:
        test = test[:limit]
    pool = defaultdict(list)
    for pair in train:
        pool[(pair["meta"]["audience"], pair["meta"]["situation"])].append(pair["messages"][2]["content"])
        pool[(pair["meta"]["audience"], None)].append(pair["messages"][2]["content"])

    # Text only: with LoRA on, vLLM's image-encoder memory profiling crashes (lora_shrink assert),
    # and SaySo's model never sees images (screenshots are read by Muse Spark).
    llm = LLM(model=BASE_MODEL, max_model_len=4096, enable_lora=bool(adapters), max_lora_rank=16, max_loras=2,
              gpu_memory_utilization=0.9, seed=seed, limit_mm_per_prompt={"image": 0, "video": 0})
    tokenizer = llm.get_tokenizer()
    stop_ids = [tokenizer.convert_tokens_to_ids(t) for t in ("<|eot|>", "<|eom|>")]
    params = SamplingParams(temperature=1.0, top_p=0.95, top_k=64, max_tokens=160, stop_token_ids=stop_ids, seed=seed)

    def prompt(messages):
        system, user = messages[0]["content"], messages[1]["content"]
        rendered = tokenizer.apply_chat_template(
            [{"role": "system", "content": f"{system}\n{REASONING}"}, {"role": "user", "content": user}],
            tokenize=False, add_generation_prompt=True)
        return rendered + " to=user<|message|>"

    rng = random.Random(seed)
    plain, shots = [], []
    for pair in test:
        meta = pair["meta"]
        plain.append(prompt(pair["messages"]))
        candidates = pool[(meta["audience"], meta["situation"])] or pool[(meta["audience"], None)]
        examples = rng.sample(candidates, min(FEW_SHOT, len(candidates)))
        system = few_shot_system(pair["messages"][0]["content"], examples, meta["audience"], meta["situation"])
        shots.append(prompt([{"content": system}, pair["messages"][1]]))

    runs = {"base": (plain, None), "fewshot": (shots, None)}
    for i, name in enumerate(adapters, 1):
        runs[name] = (plain, LoRARequest(name, i, f"/data/adapters/{name}"))

    rows = []
    for name, (prompts, lora) in runs.items():
        outputs = llm.generate(prompts, params, lora_request=lora)
        for pair, output in zip(test, outputs):
            rows.append({
                "system": name,
                "turn_id": pair["meta"]["turn_id"],
                "task": pair["meta"]["task"],
                "audience": pair["meta"]["audience"],
                "situation": pair["meta"]["situation"],
                "prompt": pair["messages"][1]["content"],
                "target": pair["messages"][2]["content"],
                "output": output.outputs[0].text.strip(),
            })
        print(f"{name}: {len(outputs)} outputs")
    return rows


@app.local_entrypoint()
def main(adapters: str = "v1,v1e1", limit: int = 0, pairs: str = "pairs", out: str = "outputs"):
    rows = generate.remote([a for a in adapters.split(",") if a], limit=limit, pairs=pairs)
    out = Path(__file__).resolve().parent.parent / "data" / "bench" / f"{out}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{len(rows)} outputs → {out}")
