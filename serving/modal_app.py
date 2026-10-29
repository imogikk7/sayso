"""SaySo serving on Modal.

glimmer — Muse Glimmer 30B + the user's LoRA adapters behind vLLM's OpenAI-compatible server (H100,
          sleeps after 5 idle minutes). Also used by pipeline/situations.py for tagging.
api     — app-facing FastAPI on CPU: /rewrite /compose /reply (logic in serving/writer.py).

Deploy:  .venv/bin/modal deploy serving/modal_app.py
Needs Modal secrets `sayso` (SAYSO_API_TOKEN, the app's token), `sayso-glimmer` (GLIMMER_KEY, vLLM's own key:
never in the app, so a token pulled from the app binary can't reach the model directly) and `sayso-meta`
(META_API_KEY), and on the `sayso-data`
volume: adapters/, pairs_v2/, pairs_v4/, lexicon.json (the user's own data, never in the repo).
"""

import os
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
    secrets=[modal.Secret.from_name("sayso-glimmer")],
    timeout=60 * 60,
    scaledown_window=int(os.environ.get("SAYSO_SCALEDOWN", 5 * 60)),  # 5 min; 20 min while filming
    max_containers=1,  # one H100 at most, whatever the traffic
)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=VLLM_PORT, startup_timeout=30 * 60)
def glimmer():
    import os

    # Passed via env, not --api-key: vLLM logs its CLI args at startup.
    env = {**os.environ, "VLLM_API_KEY": os.environ["GLIMMER_KEY"]}
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
              secrets=[modal.Secret.from_name(name) for name in ("sayso", "sayso-glimmer", "sayso-meta")],
              scaledown_window=5 * 60, timeout=10 * 60, max_containers=2)
@modal.concurrent(max_inputs=32)
@modal.asgi_app()
def api():
    """POST /rewrite {text, audience, situation?}      → {text, candidates}
    POST /compose {instruction, audience, situation?} → {text, candidates}
    POST /reply   screenshot (image/*, ≤ 4 MB) or {messages} or {summary, situation}, audience optional
                  → {context: {audience, situation, summary}, replies: [{intent, tone, thought, text} × 3], ms}
    GET  /warmup  wakes the GPU and waits (a cold start takes minutes); the app calls it from a button
    While the GPU is cold, generation routes answer 503 {"detail": "warming up…"} at once and start waking it.
    Screenshots and other people's messages are read in memory and never stored."""
    import secrets
    import sys
    import time

    import httpx
    from fastapi import Depends, FastAPI, Header, HTTPException, Request
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field, ValidationError
    from transformers import AutoTokenizer

    sys.path.insert(0, "/root/sayso/serving")
    from writer import AUDIENCES, Unavailable, Writer
    from situations import SITUATIONS

    def check(authorization: str | None = Header(None)):
        expected = f"Bearer {os.environ['SAYSO_API_TOKEN']}".encode()
        if not authorization or not secrets.compare_digest(authorization.encode(), expected):
            raise HTTPException(status_code=401)

    # Auth runs as an app-wide dependency, before any body is parsed or validated.
    web = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, dependencies=[Depends(check)])
    client = httpx.AsyncClient(follow_redirects=True)  # Modal answers 303 to requests longer than 150 s
    writer = Writer(client, glimmer.get_web_url(), os.environ["GLIMMER_KEY"],
                    AutoTokenizer.from_pretrained(MODEL), os.environ["META_API_KEY"])
    max_image = 4 * 1024 * 1024

    @web.exception_handler(Unavailable)
    async def unavailable(_, error: Unavailable):
        return JSONResponse({"detail": error.detail}, status_code=error.status)

    def audience_of(value):
        return value if value in AUDIENCES else "friends"

    def situation_of(value):
        return value if value in SITUATIONS else "other"

    class Styled(BaseModel):
        text: str = Field("", max_length=2000)
        instruction: str = Field("", max_length=1000)
        audience: str = "friends"
        situation: str = "other"

    class ReplyBody(BaseModel):
        summary: str = Field("", max_length=400)
        messages: str = Field("", max_length=4000)
        situation: str = "other"
        audience: str | None = None

    @web.post("/rewrite")
    async def rewrite(body: Styled):
        if not body.text.strip():
            raise HTTPException(422, "text is empty")
        return await writer.rewrite(body.text, audience_of(body.audience), situation_of(body.situation))

    @web.post("/compose")
    async def compose(body: Styled):
        if not body.instruction.strip():
            raise HTTPException(422, "instruction is empty")
        return await writer.compose(body.instruction, audience_of(body.audience), situation_of(body.situation))

    @web.post("/reply")
    async def reply(request: Request, audience: str | None = None):
        started = time.monotonic()
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("image/"):
            if int(request.headers.get("content-length") or 0) > max_image:
                raise HTTPException(413, "screenshot is larger than 4 MB")
            image = await request.body()
            if len(image) > max_image:
                raise HTTPException(413, "screenshot is larger than 4 MB")
            await writer.ensure_warm()  # fail fast before paying for Muse Spark
            context = await writer.read(image=image, image_type=content_type.split(";")[0], audience=audience)
        else:
            try:
                body = ReplyBody.model_validate_json(await request.body())
            except ValidationError as error:
                raise HTTPException(422, error.errors(include_url=False, include_input=False))
            audience = body.audience or audience
            if body.summary.strip():
                context = {"audience": audience, "situation": situation_of(body.situation), "summary": body.summary}
            elif body.messages.strip():
                await writer.ensure_warm()
                context = await writer.read(messages=body.messages, audience=audience)
            else:
                raise HTTPException(422, "send a screenshot, messages or a summary")
        read_ms = round((time.monotonic() - started) * 1000)
        context["audience"] = audience_of(context["audience"])
        replies = await writer.reply(context["summary"], context["audience"], context["situation"])
        return {"context": context, "replies": replies,
                "ms": {"read": read_ms, "total": round((time.monotonic() - started) * 1000)}}

    @web.get("/warmup")
    async def warmup():
        response = await client.get(f"{writer.url}/v1/models", timeout=900,
                                    headers={"Authorization": f"Bearer {writer.token}"})
        return {"ready": response.status_code == 200}

    return web
