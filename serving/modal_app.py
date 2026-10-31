"""SaySo serving on Modal.

glimmer — Muse Glimmer 30B + the user's LoRA adapters behind vLLM's OpenAI-compatible server (H100,
          sleeps after 5 idle minutes). Also used by pipeline/situations.py for tagging.
api     — app-facing FastAPI on CPU: /rewrite /compose /reply (logic in serving/writer.py).

Deploy:  .venv/bin/modal deploy serving/modal_app.py
Needs Modal secrets `sayso` (SAYSO_API_TOKEN, the app's token), `sayso-glimmer` (GLIMMER_KEY, vLLM's own key:
never in the app, so a token pulled from the app binary can't reach the model directly) and `sayso-meta`
(META_API_KEY), and on the `sayso-data`
volume: adapters/, pairs_v2/, pairs_v4/, lexicon.json, audiences.json, style_profile.json (the user's own data, never in the repo).
"""

import os
import subprocess
from pathlib import Path

import modal

REPO = Path(__file__).resolve().parent.parent
# "modal": the user's model on our H100; "off": Muse Spark alone, the GPU is never woken (Modal credits are nearly gone).
GPU = os.environ.get("SAYSO_GPU", "off")
# "on": a new style also trains its own LoRA (training/modal_train.py, an H100 for ~10–30 min); "off": profile only.
TRAIN = os.environ.get("SAYSO_TRAIN", "off")
MODEL = "meta-models/Muse-Glimmer-30B"
VLLM_PORT = 8000

image = (
    modal.Image.from_registry("vllm/vllm-openai:v0.28.0", add_python="3.12")
    .entrypoint([])
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "HF_HOME": "/cache/hf"})
)

cache = modal.Volume.from_name("sayso-hf-cache", create_if_missing=True)
# The last /reply result for the keyboard panel: the user's own suggested replies and the situation tag only,
# never the summary of the other person's messages.
latest = modal.Dict.from_name("sayso-latest", create_if_missing=True)
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
    # Runtime LoRA updating: a new style's adapter is loaded on its first request (/v1/load_lora_adapter).
    env = {**os.environ, "VLLM_API_KEY": os.environ["GLIMMER_KEY"], "VLLM_ALLOW_RUNTIME_LORA_UPDATING": "1"}
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
        "--enable-lora", "--max-lora-rank", "16", "--max-loras", "4",
        "--lora-modules", *[f"{name}=/data/adapters/{name}" for name in ADAPTERS],
        "--limit-mm-per-prompt", '{"image": 0, "video": 0}',
    ], env=env)


api_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("fastapi[standard]", "httpx", "transformers", "jinja2")
    .env({"HF_HOME": "/cache/hf", "TRANSFORMERS_VERBOSITY": "error", "SAYSO_GPU": GPU, "SAYSO_TRAIN": TRAIN})
    # pipeline/ modules read the user's data from <repo>/data; here that is the private volume
    .run_commands("mkdir -p /root/sayso && ln -s /data /root/sayso/data")
    .add_local_dir(REPO / "pipeline", "/root/sayso/pipeline", ignore=["__pycache__"])
    .add_local_dir(REPO / "eval", "/root/sayso/eval", ignore=["__pycache__", "results"])
    .add_local_file(REPO / "serving" / "writer.py", "/root/sayso/serving/writer.py")
    .add_local_file(REPO / "serving" / "styles.py", "/root/sayso/serving/styles.py")
    .add_local_file(REPO / "serving" / "build_style.py", "/root/sayso/serving/build_style.py")
)


@app.function(image=api_image, volumes={"/data": data}, secrets=[modal.Secret.from_name("sayso-meta")],
              timeout=3 * 60 * 60, max_containers=2)
def build_style(style_id: str, files: list):
    """Builds a style from the uploads ([(name, bytes)], held in memory only; see serving/build_style.py)."""
    import sys
    import time

    sys.path.insert(0, "/root/sayso/serving")
    import build_style as builder
    import styles

    def wait_for_me(meta):
        started = time.monotonic()
        while time.monotonic() - started < builder.WAIT_FOR_ME:
            time.sleep(3)
            data.reload()
            meta = styles.meta(style_id)
            if meta is None:
                return None  # deleted meanwhile
            if meta.get("confirmed"):
                return meta
        return None

    def train(style_id):
        if os.environ.get("SAYSO_TRAIN") != "on":
            return None
        run = modal.Function.from_name("sayso-train", "train")
        run.remote(run=f"style-{style_id}", pairs=f"styles/{style_id}/pairs")
        data.reload()
        return (Path("/data/adapters") / f"style-{style_id}" / "adapter_config.json").exists()

    builder.build(style_id, [tuple(f) for f in files], builder.Spark(os.environ["META_API_KEY"]),
                  os.environ["META_API_KEY"], wait_for_me, commit=data.commit,
                  train=train if os.environ.get("SAYSO_TRAIN") == "on" else None)
    data.commit()


@app.function(image=api_image, volumes={"/cache": cache, "/data": data},
              secrets=[modal.Secret.from_name(name) for name in ("sayso", "sayso-glimmer", "sayso-meta")],
              scaledown_window=5 * 60, timeout=10 * 60, max_containers=2)
@modal.concurrent(max_inputs=32)
@modal.asgi_app()
def api():
    """Every generation route takes style (default "main") and format (message | series | official | email).
    POST /rewrite {text, audience, situation?}      → {text, parts, candidates, audiences, styled}
    POST /compose {instruction, audience, situation?} → the same
    POST /reply   screenshot (image/*, ≤ 4 MB) or JSON {image (base64) | messages | summary [+ options], audience?,
                  instruction?} → {context: {audience, audiences, situation, summary}, replies: [{intent, tone,
                  thought, text, parts} × 3], options: [{act, draft}], ms}. Sending back summary + options with another
                  audience restyles the same replies without reading the chat again.
    POST /chat    {mode: write | rewrite | reply, text, audience, history: [{answer, feedback}]} → {text, parts,
                  alternatives, audience, audiences, learned}; feedback on the last answer revises it
    POST /feedback {audience, answer, edited?, liked?} → {learned}: the user's approved or own text becomes an example
    GET  /styles, GET /styles/{id}, POST /styles (multipart: name + files), PATCH /styles/{id} {name?, me?, chats?,
                  remove_preference?}, DELETE /styles/{id}
    GET  /latest  the last /reply options (for the keyboard panel)
    GET  /warmup  wakes the GPU and waits (a cold start takes minutes); the app calls it from a button
    While the GPU is cold, generation routes answer at once with Muse Spark in the style and start waking it.
    Screenshots and other people's messages are read in memory and never stored."""
    import base64
    import binascii
    import secrets
    import sys
    import time

    import httpx
    from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field, ValidationError
    from transformers import AutoTokenizer

    sys.path.insert(0, "/root/sayso/serving")
    import styles
    from writer import AUDIENCES, FORMATS, Unavailable, Writer
    from situations import ACTS, SITUATIONS

    def check(authorization: str | None = Header(None)):
        expected = f"Bearer {os.environ['SAYSO_API_TOKEN']}".encode()
        if not authorization or not secrets.compare_digest(authorization.encode(), expected):
            raise HTTPException(status_code=401)

    # Auth runs as an app-wide dependency, before any body is parsed or validated.
    web = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, dependencies=[Depends(check)])
    client = httpx.AsyncClient(follow_redirects=True)  # Modal answers 303 to requests longer than 150 s
    GPU = os.environ.get("SAYSO_GPU", "off")
    styles.on_write = data.commit
    writer = Writer(client, glimmer.get_web_url(), os.environ["GLIMMER_KEY"],
                    AutoTokenizer.from_pretrained(MODEL), os.environ["META_API_KEY"], gpu=GPU, reload=data.reload)
    max_upload = 50 * 1024 * 1024
    max_image = 4 * 1024 * 1024

    @web.exception_handler(Unavailable)
    async def unavailable(_, error: Unavailable):
        return JSONResponse({"detail": error.detail}, status_code=error.status)

    def audience_of(value):
        return value if value in AUDIENCES else "friends"

    def situation_of(value):
        return value if value in SITUATIONS else "other"

    def format_of(value):
        return value if value in FORMATS else "message"

    class Styled(BaseModel):
        text: str = Field("", max_length=2000)
        instruction: str = Field("", max_length=1000)
        audience: str = "friends"
        situation: str = "other"
        style: str = styles.MAIN
        format: str = "message"

    class Option(BaseModel):
        act: str
        draft: str = Field(max_length=2000)

    class Turn(BaseModel):
        answer: str = Field("", max_length=3000)
        feedback: str = Field("", max_length=500)

    class ChatBody(BaseModel):
        mode: str = "write"
        text: str = Field(max_length=4000)
        audience: str = "friends"
        style: str = styles.MAIN
        format: str = "message"
        instruction: str = Field("", max_length=300)
        history: list[Turn] = Field([], max_length=12)

    class FeedbackBody(BaseModel):
        audience: str = "friends"
        style: str = styles.MAIN
        format: str = "message"
        answer: str = Field(max_length=3000)
        edited: str | None = Field(None, max_length=3000)
        liked: bool = False

    class StylePatch(BaseModel):
        name: str | None = Field(None, max_length=40)
        me: str | None = Field(None, max_length=200)
        chats: dict[str, str] | None = None
        remove_preference: int | None = None

    class ReplyBody(BaseModel):
        image: str = Field("", max_length=6_000_000)  # base64 screenshot (≤ 4 MB decoded)
        image_type: str = "image/jpeg"
        messages: str = Field("", max_length=4000)
        summary: str = Field("", max_length=400)
        situation: str = "other"
        audience: str | None = None
        instruction: str = Field("", max_length=300)  # "politely decline, I'm busy" or extra context
        options: list[Option] | None = Field(None, max_length=3)  # from an earlier reply: restyle without rereading
        style: str = styles.MAIN
        format: str = "message"

    @web.post("/rewrite")
    async def rewrite(body: Styled):
        if not body.text.strip():
            raise HTTPException(422, "text is empty")
        return await writer.rewrite(writer.context(body.style), body.text, audience_of(body.audience),
                                    situation_of(body.situation), format_of(body.format))

    @web.post("/compose")
    async def compose(body: Styled):
        if not body.instruction.strip():
            raise HTTPException(422, "instruction is empty")
        return await writer.compose(writer.context(body.style), body.instruction, audience_of(body.audience),
                                    situation_of(body.situation), format_of(body.format))

    @web.post("/reply")
    async def reply(request: Request, audience: str | None = None, style: str = styles.MAIN, format: str = "message"):
        started = time.monotonic()
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("image/"):
            if int(request.headers.get("content-length") or 0) > max_image:
                raise HTTPException(413, "screenshot is larger than 4 MB")
            image = await request.body()
            if len(image) > max_image:
                raise HTTPException(413, "screenshot is larger than 4 MB")
            ctx, format = writer.context(style), format_of(format)
            context, options = await writer.read(ctx, image=image, image_type=content_type.split(";")[0],
                                                 audience=audience, format=format)
        else:
            try:
                body = ReplyBody.model_validate_json(await request.body())
            except ValidationError as error:
                raise HTTPException(422, error.errors(include_url=False, include_input=False))
            audience = body.audience or audience
            ctx, format = writer.context(body.style), format_of(body.format)
            options = None
            if body.image:
                try:
                    image = base64.b64decode(body.image, validate=True)
                except binascii.Error:
                    raise HTTPException(422, "image is not base64")
                if len(image) > max_image:
                    raise HTTPException(413, "screenshot is larger than 4 MB")
                context, options = await writer.read(ctx, image=image, image_type=body.image_type, audience=audience,
                                                     instruction=body.instruction, format=format)
            elif body.summary.strip():
                context = {"audience": audience, "audiences": [audience_of(audience)],
                           "situation": situation_of(body.situation), "summary": body.summary}
                options = [o.model_dump() for o in body.options or [] if o.act in ACTS] or None
            elif body.messages.strip():
                context, options = await writer.read(ctx, messages=body.messages, audience=audience,
                                                     instruction=body.instruction, format=format)
            else:
                raise HTTPException(422, "send a screenshot, messages or a summary")
        read_ms = round((time.monotonic() - started) * 1000)
        context["audience"] = audience_of(context["audience"])
        replies = await writer.reply(ctx, context["summary"], context["audience"], context["situation"], options,
                                     format)
        await latest.put.aio("reply", {"audience": context["audience"], "situation": context["situation"],
                                       "replies": replies, "at": time.time()})
        return {"context": context, "replies": replies, "options": options or [],
                "ms": {"read": read_ms, "total": round((time.monotonic() - started) * 1000)}}

    @web.post("/chat")
    async def chat(body: ChatBody):
        if body.mode not in {"write", "rewrite", "reply"} or not body.text.strip():
            raise HTTPException(422, "mode must be write, rewrite or reply, and text can't be empty")
        return await writer.chat(writer.context(body.style), body.mode, body.text, audience_of(body.audience),
                                 format_of(body.format), [t.model_dump() for t in body.history], body.instruction)

    @web.post("/feedback")
    async def feedback(body: FeedbackBody):
        return await writer.feedback(writer.context(body.style), audience_of(body.audience), format_of(body.format),
                                     body.answer, body.edited, body.liked)

    def style_view(meta, full=False):
        view = {k: meta.get(k) for k in ("id", "name", "status", "stage", "progress", "error", "source", "counts",
                                         "scores", "lora", "adapter_ready", "created", "needs", "participants",
                                         "chats", "me")}
        if full:
            sid = meta["id"]
            view["preferences"] = styles.preferences(sid)
            profile = (styles.read_json(styles.DATA / "style_profile.json", {}) if sid == styles.MAIN
                       else styles.read_json(styles.folder(sid) / "profile.json", {}))
            view["profile"] = {a: {k: p.get(k) for k in ("turns", "acts", "tones", "median_chars", "lowercase_start",
                                                       "ends_with_punctuation", "emoji", "laughter", "swear")}
                               for a, p in profile.items()}
            ctx = writer.context(sid) if meta.get("status") == "ready" else None
            view["examples"] = {a: ctx.sample(a, k=3, seed=1) for a in AUDIENCES if ctx and ctx.examples.get((a, None))}
        return view

    def style_or_404(style_id):
        try:
            meta = styles.meta(style_id)
            if meta is None:
                data.reload()
                meta = styles.meta(style_id)
        except KeyError:
            meta = None
        if meta is None:
            raise HTTPException(404, "no such style")
        return meta

    @web.get("/styles")
    async def list_styles():
        data.reload()
        return {"styles": [style_view(m) for m in styles.all_styles()]}

    @web.get("/styles/{style_id}")
    async def get_style(style_id: str):
        data.reload()
        return style_view(style_or_404(style_id), full=True)

    @web.post("/styles")
    async def create_style(name: str = Form(..., max_length=40), files: list[UploadFile] = File(...)):
        if not 1 <= len(files) <= 200:
            raise HTTPException(422, "send 1 to 200 files")
        uploads, total = [], 0
        for f in files:
            raw = await f.read()
            total += len(raw)
            if total > max_upload:
                raise HTTPException(413, "uploads are larger than 50 MB")
            uploads.append((f.filename or "file", raw))
        meta = styles.create(name)
        data.commit()
        await build_style.spawn.aio(meta["id"], uploads)  # in memory, straight to the build; never on the volume
        return style_view(meta)

    @web.patch("/styles/{style_id}")
    async def patch_style(style_id: str, body: StylePatch):
        meta = style_or_404(style_id)
        fields = {}
        if body.name and body.name.strip():
            fields["name"] = body.name.strip()
        if body.me is not None or body.chats is not None:
            if meta.get("stage") != "needs_me":
                raise HTTPException(409, "this style isn't waiting for that")
            me = body.me or meta.get("me")
            if not me:
                raise HTTPException(422, "say which participant is you")
            chats = {k: v for k, v in (body.chats or meta.get("chats") or {}).items() if v in AUDIENCES}
            fields.update(me=me, chats=chats, confirmed=True)
        if body.remove_preference is not None:
            styles.remove_preference(style_id, body.remove_preference)
        meta = styles.update(style_id, **fields) if fields else meta
        data.commit()
        return style_view(meta, full=True)

    @web.delete("/styles/{style_id}")
    async def delete_style(style_id: str):
        style_or_404(style_id)
        try:
            styles.delete(style_id)
        except PermissionError as error:
            raise HTTPException(409, str(error))
        data.commit()
        writer.contexts.pop(style_id, None)
        return {"deleted": style_id}

    @web.get("/latest")
    async def last_reply():
        return await latest.get.aio("reply") or {}

    @web.get("/warmup")
    async def warmup():
        if writer.gpu == "off":
            return {"ready": False, "gpu": "off"}
        response = await client.get(f"{writer.url}/v1/models", timeout=900,
                                    headers={"Authorization": f"Bearer {writer.token}"})
        return {"ready": response.status_code == 200}

    return web
