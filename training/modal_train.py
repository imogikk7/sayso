"""QLoRA fine-tune of Muse Glimmer 30B on SaySo pairs (Modal + Unsloth).

Pairs come from pipeline/build_pairs.py and are uploaded to the private Modal volume
`sayso-data` (never to the repo). The assistant turn is rendered straight into Glimmer's
user channel (`<|start|>assistant to=user<|message|>`) with no reasoning, and the loss
is computed on that reply only. The adapter is saved to /data/adapters/<run>.

  .venv/bin/modal volume put sayso-data data/pairs /pairs --force
  .venv/bin/modal run training/modal_train.py --run smoke --max-steps 30
  .venv/bin/modal run --detach training/modal_train.py --run v1 --epochs 2
"""

import modal

BASE_MODEL = "meta-models/Muse-Glimmer-30B"
REASONING = "Reasoning strength: low."
USER_PART = "<|start|>user<|message|>"
REPLY_PART = "<|start|>assistant to=user<|message|>"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("unsloth", "unsloth_zoo")
    .env({"HF_HOME": "/cache/hf", "HF_XET_HIGH_PERFORMANCE": "1"})
)
hf_cache = modal.Volume.from_name("sayso-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("sayso-data", create_if_missing=True)
app = modal.App("sayso-train")


def with_reasoning_off(messages):
    """Our system prompt plus a low reasoning strength, so the template doesn't add 'high'."""
    system, *rest = messages
    return [{"role": "system", "content": f"{system['content']}\n{REASONING}"}, *rest]


@app.function(image=image, gpu="H100", volumes={"/cache": hf_cache, "/data": data}, timeout=5 * 60 * 60)
def train(run: str, max_steps: int = -1, epochs: float = 2.0, limit: int = 0, r: int = 16, lr: float = 2e-4,
          samples: int = 12, pairs: str = "pairs"):
    import json
    import random
    import time

    from unsloth import FastModel  # noqa: I001  (must be imported before trl/transformers)
    from unsloth.chat_templates import train_on_responses_only
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer

    model, processor = FastModel.from_pretrained(BASE_MODEL, max_seq_length=1024, load_in_4bit=True)
    tokenizer = getattr(processor, "tokenizer", processor)
    model = FastModel.get_peft_model(
        model, finetune_vision_layers=False, finetune_language_layers=True,
        finetune_attention_modules=True, finetune_mlp_modules=True,
        r=r, lora_alpha=r, lora_dropout=0, bias="none", random_state=0,
    )

    def load(split):
        rows = [json.loads(line) for line in open(f"/data/{pairs}/{split}.jsonl", encoding="utf-8")]
        random.Random(0).shuffle(rows)  # files are grouped by chat
        return rows

    def render(rows):
        texts = []
        for row in rows:
            text = tokenizer.apply_chat_template(with_reasoning_off(row["messages"]), tokenize=False)
            texts.append(text.removeprefix(tokenizer.bos_token or ""))
        return Dataset.from_dict({"text": texts})

    train_rows, test_rows = load("train"), load("test")
    if limit:
        train_rows = train_rows[:limit]
    train_set, eval_set = render(train_rows), render(test_rows[:200])
    print("example:", train_set[0]["text"][-300:])

    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer, train_dataset=train_set, eval_dataset=eval_set,
        args=SFTConfig(
            output_dir=f"/data/runs/{run}", dataset_text_field="text", max_length=1024, packing=False,
            per_device_train_batch_size=8, gradient_accumulation_steps=2,
            num_train_epochs=epochs, max_steps=max_steps, learning_rate=lr,
            lr_scheduler_type="cosine", warmup_ratio=0.03, optim="adamw_8bit", weight_decay=0.0,
            bf16=True, logging_steps=10, eval_strategy="steps", eval_steps=100 if max_steps < 0 else max_steps,
            per_device_eval_batch_size=8, save_strategy="no", report_to="none", seed=0,
        ),
    )
    trainer = train_on_responses_only(trainer, instruction_part=USER_PART, response_part=REPLY_PART)

    started = time.time()
    stats = trainer.train()
    minutes = (time.time() - started) / 60
    metrics = trainer.evaluate()
    print(f"trained {stats.global_step} steps in {minutes:.1f} min, eval loss {metrics['eval_loss']:.3f}")

    out = f"/data/adapters/{run}"
    model.save_pretrained(out)
    tokenizer.save_pretrained(out)
    data.commit()

    # A few generations on held-out pairs, answer forced into the user channel (no reasoning).
    FastModel.for_inference(model)
    results = []
    for row in test_rows[:samples]:
        prompt = tokenizer.apply_chat_template(with_reasoning_off(row["messages"][:2]), tokenize=False,
                                               add_generation_prompt=True)
        prompt = prompt.removeprefix(tokenizer.bos_token or "") + " to=user<|message|>"
        ids = tokenizer(prompt, return_tensors="pt").to(model.device)
        output = model.generate(**ids, max_new_tokens=120, do_sample=True, temperature=1.0, top_p=0.95, top_k=64)
        reply = tokenizer.decode(output[0][ids["input_ids"].shape[1]:], skip_special_tokens=False)
        results.append({
            "prompt": row["messages"][1]["content"],
            "target": row["messages"][2]["content"],
            "model": reply.split("<|eot|>")[0].split("<|eom|>")[0].strip(),
        })
    return {"run": run, "steps": stats.global_step, "minutes": round(minutes, 1),
            "train_loss": round(stats.training_loss, 3), "eval_loss": round(metrics["eval_loss"], 3),
            "adapter": out, "samples": results}


@app.local_entrypoint()
def main(run: str = "smoke", max_steps: int = 30, epochs: float = 2.0, limit: int = 0, r: int = 16,
         pairs: str = "pairs"):
    import json
    from pathlib import Path

    result = train.remote(run=run, max_steps=max_steps, epochs=epochs, limit=limit, r=r, pairs=pairs)
    # Samples contain the user's own messages: keep them in gitignored data/, print only metrics.
    out = Path(__file__).resolve().parent.parent / "data" / "runs" / f"{run}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print({k: v for k, v in result.items() if k != "samples"}, f"\nsamples → {out}")
