"""Word-choice preference tuning on top of an SFT adapter (Modal + Unsloth + TRL CPO/SimPO).

chosen = the user's real turn, rejected = the same turn with their own words swapped back to
neutral Russian (training/build_prefs.py). SimPO needs no reference model; cpo_alpha adds a
small NLL term on the chosen reply so the adapter keeps its fluency.

  .venv/bin/modal volume put sayso-data data/prefs /prefs --force
  .venv/bin/modal run --detach training/modal_prefs.py --base v2 --run v3
"""

import modal

from modal_train import REPLY_PART, data, hf_cache, image, with_reasoning_off

image = image.add_local_python_source("modal_train")  # the container imports the shared helpers too
app = modal.App("sayso-prefs")


@app.function(image=image, gpu="H100", volumes={"/cache": hf_cache, "/data": data}, timeout=2 * 60 * 60)
def train(base: str, run: str, epochs: float = 1.0, lr: float = 1e-5, beta: float = 2.0, gamma: float = 0.5,
          cpo_alpha: float = 0.2):
    import json
    import random
    import time

    from unsloth import FastModel  # noqa: I001  (must be imported before trl/transformers)
    from datasets import Dataset
    from trl import CPOConfig, CPOTrainer

    model, processor = FastModel.from_pretrained(f"/data/adapters/{base}", max_seq_length=1024, load_in_4bit=True)
    tokenizer = getattr(processor, "tokenizer", processor)
    for name, param in model.named_parameters():  # continue training the loaded adapter
        if "lora_" in name:
            param.requires_grad = True

    rows = [json.loads(line) for line in open("/data/prefs/train.jsonl", encoding="utf-8")]
    random.Random(0).shuffle(rows)
    eot = "<|eot|>"
    records = []
    for row in rows:
        prompt = tokenizer.apply_chat_template(with_reasoning_off(row["prompt"]), tokenize=False,
                                               add_generation_prompt=True)
        prompt = prompt.removeprefix(tokenizer.bos_token or "") + REPLY_PART.removeprefix("<|start|>assistant")
        records.append({"prompt": prompt, "chosen": row["chosen"] + eot, "rejected": row["rejected"] + eot})
    split = int(len(records) * 0.95)
    train_set, eval_set = Dataset.from_list(records[:split]), Dataset.from_list(records[split:])

    trainer = CPOTrainer(
        model=model, processing_class=tokenizer, train_dataset=train_set, eval_dataset=eval_set,
        args=CPOConfig(
            output_dir=f"/data/runs/{run}", loss_type="simpo", beta=beta, simpo_gamma=gamma, cpo_alpha=cpo_alpha,
            per_device_train_batch_size=8, gradient_accumulation_steps=1, num_train_epochs=epochs,
            learning_rate=lr, lr_scheduler_type="cosine", warmup_ratio=0.05, optim="adamw_8bit",
            bf16=True, logging_steps=10, eval_strategy="steps", eval_steps=50, per_device_eval_batch_size=8,
            max_length=512, max_prompt_length=384, save_strategy="no", report_to="none", seed=0,
            remove_unused_columns=False,
        ),
    )
    started = time.time()
    stats = trainer.train()
    metrics = trainer.evaluate()
    print(f"trained {stats.global_step} steps in {(time.time() - started) / 60:.1f} min; eval {metrics}")

    out = f"/data/adapters/{run}"
    model.save_pretrained(out)
    tokenizer.save_pretrained(out)
    data.commit()
    return {"run": run, "base": base, "steps": stats.global_step,
            "reward_accuracy": round(metrics.get("eval_rewards/accuracies", float("nan")), 3),
            "eval_loss": round(metrics.get("eval_loss", float("nan")), 4), "adapter": out}


@app.local_entrypoint()
def main(base: str = "v2", run: str = "v3", epochs: float = 1.0, lr: float = 1e-5):
    print(train.remote(base=base, run=run, epochs=epochs, lr=lr))
