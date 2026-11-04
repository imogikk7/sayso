"""The user's LoRA on one H100, only for the length of one eval run (eval/style_gain.py --writer lora --gpu-ok).

The production server sends vLLM's /v1/completions a JSON body (serving/writer.py, Writer.complete). Here the same
bodies, recorded on the owner's machine by the unchanged Writer code, run through vLLM in an *ephemeral* Modal app,
"sayso-eval-lora": nothing in the deployed "sayso" app changes, its `glimmer` function is never woken, and when the
run ends (or fails) Modal stops the app and its H100.

Same as the `glimmer` function in serving/modal_app.py: the vLLM image, Muse Glimmer 30B from the sayso-hf-cache
volume, the adapter from /data/adapters/<name> on sayso-data, LoRA rank 16, text only. Different on purpose: offline
vLLM in the function (no web endpoint, no key), eager mode (no CUDA-graph capture: a minute or two less of H100 for
~400 short completions), and the model is never downloaded (HF_HUB_OFFLINE: fail at once instead of paying for 60 GB).

Cost guard: one container at most, no retries, a hard 15-minute timeout, the container stops as soon as the app does.
The prompts carry the user's chat messages only to our own GPU (the same as the server would), and nothing is written
to the volumes.
"""

import json

try:
    import modal
except ImportError:  # the tests import the helpers below without Modal
    modal = None

MODEL = "meta-models/Muse-Glimmer-30B"  # serving/modal_app.py MODEL
MODEL_CACHE = "/hf/hub/models--meta-models--Muse-Glimmer-30B"  # on sayso-hf-cache (HF_HOME=/cache/hf)
TIMEOUT_MIN = 15
H100_PER_HOUR = 3.95  # Modal's list price for an H100 (USD), for the estimate printed before starting
TYPICAL_MIN = (6, 9)  # cold start (~60 GB of weights from the volume) + a minute of generation
# Writer.prompt renders the chat messages with the model's tokenizer. On the owner's machine there is no tokenizer, so
# a stand-in (style_gain.MarkTokenizer) wraps the messages in these markers and the GPU renders them with the real one.
MARK, END = "\x00sayso-messages\x00", "\x00end\x00"
SAMPLING_KEYS = ("n", "max_tokens", "temperature", "top_p", "top_k", "stop", "skip_special_tokens")


def estimate():
    low, high = TYPICAL_MIN
    rate = H100_PER_HOUR / 60
    return (f"one H100 for ~{low}–{high} min (≈ ${low * rate:.2f}–{high * rate:.2f}), hard stop at {TIMEOUT_MIN} min "
            f"(≤ ${TIMEOUT_MIN * rate:.2f}); ephemeral app, stops when the run ends")


def marked(messages):
    return MARK + json.dumps(messages, ensure_ascii=False) + END


def render(prompt, tokenizer):
    """A prompt recorded on the owner's machine → the exact text the server sends vLLM: the messages rendered with the
    model's chat template (BOS removed, vLLM adds it), then whatever Writer appended (" to=user<|message|>", a thought)."""
    if not prompt.startswith(MARK) or END not in prompt:
        raise ValueError("prompt was not recorded by style_gain.MarkTokenizer")
    messages, rest = prompt[len(MARK):].split(END, 1)
    rendered = tokenizer.apply_chat_template(json.loads(messages), tokenize=False, add_generation_prompt=True)
    return rendered.removeprefix(tokenizer.bos_token or "") + rest


def sampling(body):
    """The /v1/completions body → SamplingParams arguments. Fails on any field it doesn't know, so a change to
    Writer.complete can't silently be dropped here."""
    unknown = set(body) - set(SAMPLING_KEYS) - {"model", "prompt"}
    if unknown:
        raise ValueError(f"Writer.complete sends fields this eval doesn't map: {sorted(unknown)}")
    return {k: body[k] for k in SAMPLING_KEYS if k in body}


def answer(bodies, generate):
    """bodies → vLLM-style responses ({"choices": [{"index": prompt × n + j, "text"}]}), in one batch.
    generate(prompts, params) → per prompt, its n texts (what LLM.generate gives)."""
    prompts, params, where = [], [], []
    for b, body in enumerate(bodies):
        for p, prompt in enumerate(body["prompt"]):
            prompts.append(prompt)
            params.append(sampling(body))
            where.append((b, p))
    out = [{"choices": []} for _ in bodies]
    for (b, p), texts in zip(where, generate(prompts, params)):
        n = bodies[b].get("n", 1)
        out[b]["choices"] += [{"index": p * n + j, "text": t} for j, t in enumerate(texts)]
    return out


if modal:
    image = (
        modal.Image.from_registry("vllm/vllm-openai:v0.28.0")  # serving/modal_app.py; the image's own Python has vllm
        .entrypoint([])
        .run_commands("ln -sf $(command -v python3) /usr/local/bin/python")  # as in eval/bench_generate.py
        .env({"HF_HOME": "/cache/hf", "HF_HUB_OFFLINE": "1"})
    )
    cache = modal.Volume.from_name("sayso-hf-cache")  # no create_if_missing: a missing volume fails at once
    data = modal.Volume.from_name("sayso-data")
    app = modal.App("sayso-eval-lora")

    @app.function(image=image, gpu="H100", volumes={"/cache": cache, "/data": data}, timeout=TIMEOUT_MIN * 60,
                  max_containers=1, scaledown_window=10)  # no retries (Modal's default)
    def generate(adapter: str, bodies: list) -> list:
        import os
        import time

        started = time.monotonic()
        if not os.path.exists(f"/data/adapters/{adapter}/adapter_config.json"):
            raise RuntimeError(f"adapter {adapter!r} not found at /data/adapters/{adapter} on the sayso-data volume")
        if not os.path.isdir(f"/cache{MODEL_CACHE}/snapshots"):
            raise RuntimeError(f"{MODEL} is not cached on the sayso-hf-cache volume ({MODEL_CACHE}); this eval never "
                               "downloads it")
        if {b.get("model") for b in bodies} != {adapter}:
            raise RuntimeError("every request must use the same adapter")

        from vllm import LLM, SamplingParams
        from vllm.lora.request import LoRARequest

        llm = LLM(model=MODEL, max_model_len=8192, enable_lora=True, max_lora_rank=16, max_loras=1,
                  gpu_memory_utilization=0.92, limit_mm_per_prompt={"image": 0, "video": 0}, enforce_eager=True)
        print(f"model + adapter loaded in {time.monotonic() - started:.0f} s")
        tokenizer = llm.get_tokenizer()
        lora = LoRARequest(adapter, 1, f"/data/adapters/{adapter}")
        for body in bodies:
            body["prompt"] = [render(p, tokenizer) for p in body["prompt"]]

        def run(prompts, params):
            outputs = llm.generate(prompts, [SamplingParams(**p) for p in params], lora_request=lora)
            return [[o.text for o in output.outputs] for output in outputs]

        out = answer(bodies, run)
        print(f"{sum(len(b['prompt']) for b in bodies)} prompts in {time.monotonic() - started:.0f} s of H100")
        return out

    def check_volumes(adapter):
        """Before any GPU starts: the adapter and the cached model are on the volumes (a metadata call, no container).
        → a message for the owner, or None. Older Modal clients without Volume.listdir skip this; the GPU function
        checks the same before loading anything."""
        for volume, name, path, what in ((data, "sayso-data", f"/adapters/{adapter}", f"the LoRA adapter {adapter!r}"),
                                         (cache, "sayso-hf-cache", f"{MODEL_CACHE}/snapshots", MODEL)):
            try:
                entries = list(volume.listdir(path))
            except AttributeError:
                return None
            except Exception as error:  # missing volume or path, not logged in
                return f"can't see {what} at {path} on the Modal volume {name}: {error}"
            if not entries:
                return f"{what} is missing: {path} on the Modal volume {name} is empty"
        return None

    def run(adapter, bodies):
        """The whole GPU part of an eval: one call into a fresh ephemeral app, stopped as soon as it returns."""
        with modal.enable_output(), app.run():
            return generate.remote(adapter, bodies)
