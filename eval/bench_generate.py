"""Generate benchmark outputs for every system on the held-out test pairs (Modal, vLLM).

Systems:
  base     — Glimmer with the same prompt as the LoRA, no adapter
  fewshot  — Glimmer + 5 of the user's own train turns from the same audience & situation
  <run>    — Glimmer + LoRA adapter /data/adapters/<run> (one per --adapters entry)
All answers are forced into the user channel with low reasoning, exactly like training. Adapters listed in
--thinking (trained on pairs_v4) first write the user's thought in the `to=self` channel on reply pairs:
  <run>    — the adapter decides act, tone and gist itself, then replies
  <run>p   — act and tone are drawn from the user's own shares for that audience × situation (style profile),
             the adapter writes the gist and the reply
With --tag, every reply candidate and the real reply are labeled with act + tone by base Glimmer
(same prompt as pipeline/situations.py --thoughts), so act/tone shares can be compared fairly.

  .venv/bin/modal run eval/bench_generate.py --adapters v1,v1e1
Writes data/bench/outputs.jsonl locally (gitignored: contains the user's own messages).
"""

import json
from pathlib import Path

import modal

BASE_MODEL = "meta-models/Muse-Glimmer-30B"
REASONING = "Reasoning strength: low."
FEW_SHOT = 5
MIN_CELL = 30
REPLY = " to=user<|message|>"
THOUGHT = " to=self<|message|>"
AFTER_THOUGHT = "<|eom|><|start|>assistant to=user<|message|>"

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
def generate(adapters: list[str], limit: int = 0, seed: int = 0, pairs: str = "pairs", n: int = 1,
             baselines: bool = True, thinking: list[str] = (), tagger: dict | None = None):
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
    llm = LLM(model=BASE_MODEL, max_model_len=4096, enable_lora=bool(adapters or thinking), max_lora_rank=16, max_loras=2,
              gpu_memory_utilization=0.9, seed=seed, limit_mm_per_prompt={"image": 0, "video": 0})
    tokenizer = llm.get_tokenizer()
    stop_ids = [tokenizer.convert_tokens_to_ids(t) for t in ("<|eot|>", "<|eom|>")]
    params = SamplingParams(temperature=1.0, top_p=0.95, top_k=64, max_tokens=160, stop_token_ids=stop_ids, seed=seed)

    def prompt(messages, channel=REPLY):
        system, user = messages[0]["content"], messages[1]["content"]
        rendered = tokenizer.apply_chat_template(
            [{"role": "system", "content": f"{system}\n{REASONING}"}, {"role": "user", "content": user}],
            tokenize=False, add_generation_prompt=True)
        return rendered.removeprefix(tokenizer.bos_token or "") + channel  # vLLM adds BOS itself

    profile = defaultdict(list)  # (audience, situation) and (audience, None) → the user's real (act, tone)
    for pair in train:
        meta = pair["meta"]
        if "act" in meta:
            profile[(meta["audience"], meta["situation"])].append((meta["act"], meta["tone"]))
            profile[(meta["audience"], None)].append((meta["act"], meta["tone"]))

    def think(lora, samples, from_profile):
        """Reply pairs: thought first (`to=self`), then the reply. Other tasks: straight to the user channel."""
        heads, jobs = [], []  # jobs: (test index, sampling seed)
        for i, pair in enumerate(test):
            if pair["meta"]["task"] != "reply":
                continue
            meta = pair["meta"]
            cell = profile[(meta["audience"], meta["situation"])]
            cell = cell if len(cell) >= MIN_CELL else profile[(meta["audience"], None)]
            for k in range(samples):
                head = "act: {} · tone: {} · gist:".format(*rng.choice(cell)) if from_profile else ""
                heads.append(prompt(pair["messages"], THOUGHT) + head)
                jobs.append((i, seed + k))
        sampling = [params.clone() for _ in jobs]
        for sp, (_, s) in zip(sampling, jobs):
            sp.seed, sp.max_tokens = s, 60
        thoughts = [h[h.rindex("<|message|>") + len("<|message|>"):] + o.outputs[0].text
                    for h, o in zip(heads, llm.generate(heads, sampling, lora_request=lora))]
        thoughts = [t.strip() for t in thoughts]
        for sp in sampling:
            sp.max_tokens = 160
        replies = llm.generate([h[:h.rindex(THOUGHT)] + THOUGHT + t + AFTER_THOUGHT for h, t in zip(heads, thoughts)],
                               sampling, lora_request=lora)
        by_row = defaultdict(lambda: ([], []))
        for (i, _), t, o in zip(jobs, thoughts, replies):
            by_row[i][0].append(o.outputs[0].text.strip())
            by_row[i][1].append(t)
        return by_row

    rng = random.Random(seed)
    plain, shots = [], []
    for pair in test:
        meta = pair["meta"]
        plain.append(prompt(pair["messages"]))
        candidates = pool[(meta["audience"], meta["situation"])] or pool[(meta["audience"], None)]
        examples = rng.sample(candidates, min(FEW_SHOT, len(candidates)))
        system = few_shot_system(pair["messages"][0]["content"], examples, meta["audience"], meta["situation"])
        shots.append(prompt([{"content": system}, pair["messages"][1]]))

    runs = {"base": (plain, None, 1), "fewshot": (shots, None, 1)} if baselines else {}
    for i, name in enumerate(adapters, 1):  # adapters sample n candidates (for best-of-n reranking)
        runs[name] = (plain, LoRARequest(name, i, f"/data/adapters/{name}"), n)

    for i, name in enumerate(thinking, len(adapters) + 1):
        lora = LoRARequest(name, i, f"/data/adapters/{name}")
        runs[name] = (plain, lora, n, False)
        runs[name + "p"] = (plain, lora, n, True)

    rows = []
    for name, (prompts, lora, samples, *profiled) in runs.items():
        sampling = params.clone()
        sampling.n = samples
        outputs = llm.generate(prompts, sampling, lora_request=lora)
        thought_rows = think(lora, samples, profiled[0]) if profiled else {}
        for index, (pair, output) in enumerate(zip(test, outputs)):
            candidates, thoughts = thought_rows.get(index, ([o.text.strip() for o in output.outputs], None))
            rows.append({
                "system": name,
                "turn_id": pair["meta"]["turn_id"],
                "task": pair["meta"]["task"],
                "audience": pair["meta"]["audience"],
                "situation": pair["meta"]["situation"],
                "prompt": pair["messages"][1]["content"],
                "target": pair["messages"][2]["content"],
                "output": candidates[0],
                "candidates": candidates,
                **({"thoughts": thoughts} if thoughts else {}),
            })
        print(f"{name}: {len(outputs)} outputs")
    if tagger:
        tag(llm, tokenizer, rows, tagger)
    return rows


def tag(llm, tokenizer, rows, tagger):
    """act + tone for every reply candidate and the real reply, by base Glimmer (no adapter, low reasoning)."""
    import re

    from vllm import SamplingParams

    texts = {}
    for row in rows:
        if row["task"] == "reply" and row["turn_id"] in tagger["summaries"]:
            for text in [row["target"], *row["candidates"]]:
                texts[(row["turn_id"], text)] = None
    prompts = []
    for turn_id, text in texts:
        situation, summary = tagger["summaries"][turn_id]
        user = f"Situation: {situation} — {summary}\n\nUser's message:\n{text}"
        prompts.append(tokenizer.apply_chat_template(
            [{"role": "system", "content": tagger["system"]}, {"role": "user", "content": user}],
            tokenize=False, add_generation_prompt=True).removeprefix(tokenizer.bos_token or "") + REPLY)
    outputs = llm.generate(prompts, SamplingParams(temperature=0, max_tokens=80))
    for key, output in zip(texts, outputs):
        match = re.search(r"\{.*?\}", output.outputs[0].text, re.S)
        try:
            label = json.loads(match.group(0)) if match else {}
        except json.JSONDecodeError:
            label = {}
        texts[key] = [label.get("act"), label.get("tone")]
    for row in rows:
        if row["task"] == "reply" and row["turn_id"] in tagger["summaries"]:
            row["target_tag"] = texts[(row["turn_id"], row["target"])]
            row["candidate_tags"] = [texts[(row["turn_id"], c)] for c in row["candidates"]]
    print(f"tagged {len(texts)} replies")


@app.local_entrypoint()
def main(adapters: str = "v1,v1e1", limit: int = 0, pairs: str = "pairs", out: str = "outputs", n: int = 1,
         baselines: bool = True, thinking: str = "", tag: bool = False):
    tagger = None
    if tag:  # short neutral summaries (no other person's text) for the tagger prompt
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
        from situations import THOUGHT_SYSTEM
        root = Path(__file__).resolve().parent.parent / "data"
        wanted = {json.loads(line)["meta"]["turn_id"] for line in (root / pairs / "test.jsonl").open(encoding="utf-8")}
        summaries = {r["turn_id"]: (r["situation"], r["summary"])
                     for r in map(json.loads, (root / "situations.jsonl").open(encoding="utf-8")) if r["turn_id"] in wanted}
        tagger = {"system": THOUGHT_SYSTEM, "summaries": summaries}
    rows = generate.remote([a for a in adapters.split(",") if a], limit=limit, pairs=pairs, n=n, baselines=baselines,
                           thinking=[a for a in thinking.split(",") if a], tagger=tagger)
    out = Path(__file__).resolve().parent.parent / "data" / "bench" / f"{out}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{len(rows)} outputs → {out}")
