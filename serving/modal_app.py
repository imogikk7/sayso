"""SaySo serving on Modal.

glimmer — Muse Glimmer 30B + the user's LoRA adapters behind vLLM's OpenAI-compatible server (H100,
          sleeps after 5 idle minutes). Also used by pipeline/situations.py for tagging.
api     — app-facing FastAPI on CPU: /rewrite /compose /reply (logic in serving/writer.py).

Deploy:  .venv/bin/modal deploy serving/modal_app.py
Needs Modal secrets `sayso` (SAYSO_API_TOKEN) and `sayso-meta` (META_API_KEY), and on the `sayso-data`
volume: adapters/, pairs_v2/, pairs_v4/, lexicon.json (the user's own data, never in the repo).
"""

import subprocess
from pathlib import Path

import modal

REPO = Path(__file__).resolve().parent.parent
MODEL = "meta-models/Muse-Glimmer-30B"
VLLM_PORT = 8000

image = (
    modal.Image.from_registry("vllm/vllm-openai:v0.28.0", add_python="3.12")
    .entrypoint([])
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "HF_HOME": "/cache/hf"})
)

cache = modal.Volume.from_name("sayso-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("sayso-data", create_if_missing=True)  # LoRA adapters in /data/adapters
ADAPTERS = ["v2", "v4"]
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
        # Personal adapters, requested as model="v4" etc. Text only: LoRA + image-encoder
        # profiling crashes in vLLM 0.28, and screenshots are read by Muse Spark anyway.
        "--enable-lora", "--max-lora-rank", "16",
        "--lora-modules", *[f"{name}=/data/adapters/{name}" for name in ADAPTERS],
        "--limit-mm-per-prompt", '{"image": 0, "video": 0}',
    ], env=env)


api_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("fastapi[standard]", "httpx", "transformers", "jinja2")
    .env({"HF_HOME": "/cache/hf", "TRANSFORMERS_VERBOSITY": "error"})
    # pipeline/ modules read the user's data from <repo>/data; here that is the private volume
    .run_commands("mkdir -p /root/sayso && ln -s /data /root/sayso/data")
    .add_local_dir(REPO / "pipeline", "/root/sayso/pipeline", ignore=["__pycache__"])
    .add_local_dir(REPO / "eval", "/root/sayso/eval", ignore=["__pycache__", "results"])
    .add_local_file(REPO / "serving" / "writer.py", "/root/sayso/serving/writer.py")
)


@app.function(image=api_image, volumes={"/cache": cache, "/data": data},
              secrets=[modal.Secret.from_name("sayso"), modal.Secret.from_name("sayso-meta")],
              scaledown_window=5 * 60, timeout=10 * 60)
@modal.concurrent(max_inputs=32)
@modal.asgi_app()
def api():
    """POST /rewrite {text, audience, situation?}      → {text, candidates}
    POST /compose {instruction, audience, situation?} → {text, candidates}
    POST /reply   screenshot (image/*) or {messages} or {summary, situation}, audience optional
                  → {context: {audience, situation, summary}, replies: [{intent, tone, thought, text} × 3]}
    GET  /warmup  wakes the GPU (a cold start takes a few minutes); the app calls it when opened
    Screenshots and other people's messages are read in memory and never stored."""
    import os
    import secrets
    import sys

    import httpx
    from fastapi import FastAPI, Header, HTTPException, Request
    from pydantic import BaseModel
    from transformers import AutoTokenizer

    sys.path.insert(0, "/root/sayso/serving")
    from writer import AUDIENCES, Writer

    web = FastAPI()
    client = httpx.AsyncClient()
    writer = Writer(client, glimmer.get_web_url(), os.environ["SAYSO_API_TOKEN"],
                    AutoTokenizer.from_pretrained(MODEL), os.environ["META_API_KEY"])

    def check(authorization: str | None):
        expected = f"Bearer {os.environ['SAYSO_API_TOKEN']}"
        if not authorization or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=401)

    def audience_of(value):
        return value if value in AUDIENCES else "friends"

    class Styled(BaseModel):
        text: str = ""
        instruction: str = ""
        audience: str = "friends"
        situation: str = "other"

    @web.post("/rewrite")
    async def rewrite(body: Styled, authorization: str | None = Header(None)):
        check(authorization)
        return await writer.rewrite(body.text, audience_of(body.audience), body.situation)

    @web.post("/compose")
    async def compose(body: Styled, authorization: str | None = Header(None)):
        check(authorization)
        return await writer.compose(body.instruction, audience_of(body.audience), body.situation)

    @web.post("/reply")
    async def reply(request: Request, authorization: str | None = Header(None), audience: str | None = None):
        check(authorization)
        if request.headers.get("content-type", "").startswith("image/"):
            context = await writer.read(image=await request.body(), audience=audience)
        else:
            body = await request.json()
            audience = body.get("audience") or audience
            if body.get("summary"):
                context = {"audience": audience, "situation": body.get("situation") or "other",
                           "summary": body["summary"]}
            else:
                context = await writer.read(messages=body["messages"], audience=audience)
        context["audience"] = audience_of(context["audience"])
        replies = await writer.reply(context["summary"], context["audience"], context["situation"])
        return {"context": context, "replies": replies}

    @web.get("/warmup")
    async def warmup(authorization: str | None = Header(None)):
        check(authorization)
        response = await client.get(f"{writer.url}/v1/models", timeout=900,
                                    headers={"Authorization": f"Bearer {writer.token}"})
        return {"ready": response.status_code == 200}

    return web
