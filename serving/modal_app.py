"""SaySo serving on Modal.

Stage 1 (now): base Muse Glimmer 30B behind vLLM's OpenAI-compatible server,
used by pipeline/situations.py for situation tagging. LoRA and the FastAPI
endpoints (/rewrite /compose /reply /feedback) come next.

Deploy:  .venv/bin/modal deploy serving/modal_app.py
Needs the Modal secret `sayso` with SAYSO_API_TOKEN (and HF_TOKEN if the weights are gated).
"""

import subprocess

import modal

MODEL = "meta-models/Muse-Glimmer-30B"
VLLM_PORT = 8000

image = (
    modal.Image.from_registry("vllm/vllm-openai:v0.28.0", add_python="3.12")
    .entrypoint([])
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "HF_HOME": "/cache/hf"})
)

cache = modal.Volume.from_name("sayso-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("sayso-data", create_if_missing=True)  # LoRA adapters in /data/adapters
ADAPTERS = ["v1"]
app = modal.App("sayso")


@app.function(
    image=image,
    gpu="H100",
    volumes={"/cache": cache, "/data": data},
    secrets=[modal.Secret.from_name("sayso")],
    timeout=60 * 60,
    scaledown_window=5 * 60,  # stay warm only while in use
)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=VLLM_PORT, startup_timeout=30 * 60)
def glimmer():
    import os

    # Passed via env, not --api-key: vLLM logs its CLI args at startup.
    env = {**os.environ, "VLLM_API_KEY": os.environ["SAYSO_API_TOKEN"]}
    subprocess.Popen([
        "vllm", "serve", MODEL,
        "--served-model-name", "muse-glimmer",
        "--host", "0.0.0.0", "--port", str(VLLM_PORT),
        "--max-model-len", "8192",
        "--max-num-seqs", "64",
        "--gpu-memory-utilization", "0.92",
        "--reasoning-parser", "muse_glimmer",
        "--generation-config", "auto",
        # Personal adapters, requested as model="v1" etc. Text only: LoRA + image-encoder
        # profiling crashes in vLLM 0.28, and screenshots are read by Muse Spark anyway.
        "--enable-lora", "--max-lora-rank", "16",
        "--lora-modules", *[f"{name}=/data/adapters/{name}" for name in ADAPTERS],
        "--limit-mm-per-prompt", '{"image": 0, "video": 0}',
    ], env=env)


api_image = modal.Image.debian_slim(python_version="3.12").pip_install("fastapi[standard]")


@app.function(image=api_image, secrets=[modal.Secret.from_name("sayso")], scaledown_window=5 * 60)
@modal.asgi_app()
def api():
    """App-facing API. For now /reply is a test stub for the iOS overlay spike:
    it checks the token, reads the uploaded screenshot and returns fixed replies."""
    import os
    import secrets

    from fastapi import FastAPI, Header, HTTPException, Request

    web = FastAPI()

    def check(authorization: str | None):
        expected = f"Bearer {os.environ['SAYSO_API_TOKEN']}"
        if not authorization or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=401)

    @web.post("/reply")
    async def reply(request: Request, authorization: str | None = Header(None)):
        check(authorization)
        size_kb = len(await request.body()) // 1024  # screenshot bytes, not stored
        return {
            "context": {
                "audience": "friends",
                "situation": "invitation",
                "summary": f"asks if you're free on Saturday (test, got {size_kb} KB)",
            },
            "replies": [
                {"intent": "yes", "text": "го, во сколько?"},
                {"intent": "no", "text": "ой не смогу в субботу\nдавай в воскресенье"},
                {"intent": "joke", "text": "смотря что по программе 😏"},
            ],
        }

    return web
