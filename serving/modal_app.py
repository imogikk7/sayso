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
app = modal.App("sayso")


@app.function(
    image=image,
    gpu="H100",
    volumes={"/cache": cache},
    secrets=[modal.Secret.from_name("sayso")],
    timeout=60 * 60,
    scaledown_window=5 * 60,  # stay warm only while in use
)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=VLLM_PORT, startup_timeout=30 * 60)
def glimmer():
    import os

    subprocess.Popen([
        "vllm", "serve", MODEL,
        "--served-model-name", "muse-glimmer",
        "--host", "0.0.0.0", "--port", str(VLLM_PORT),
        "--api-key", os.environ["SAYSO_API_TOKEN"],
        "--max-model-len", "8192",
        "--max-num-seqs", "64",
        "--gpu-memory-utilization", "0.92",
        "--reasoning-parser", "muse_glimmer",
        "--generation-config", "auto",
    ])
