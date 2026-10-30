"""Serve the user's LoRA on Fireworks (credits) instead of Modal: upload once, then a scale-to-zero deployment.

The adapter is live-merged into Muse Glimmer 30B (one adapter → a plain BF16 deployment, cheaper than the
multi-LoRA shape). Unsloth saved target_modules as a regex; Fireworks wants a list, so the config is rewritten.

  .venv/bin/modal volume get sayso-data /adapters/v4 adapters/       # once, no GPU
  .venv/bin/python serving/fireworks.py upload v4
  .venv/bin/python serving/fireworks.py deploy v4
  .venv/bin/python serving/fireworks.py status
  .venv/bin/python serving/fireworks.py delete                        # stop paying entirely
"""

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.fireworks.ai/v1"
ACCOUNT = "imogikk7"
BASE = "accounts/fireworks/models/muse-glimmer-30b"
DEPLOYMENT = "sayso"
MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

try:  # python.org builds on macOS ship without root certificates
    import certifi
    VERIFY = certifi.where()
except ImportError:
    VERIFY = True


def client():
    env = dict(line.strip().split("=", 1) for line in (ROOT / ".env").open() if "=" in line and not line.startswith("#"))
    return httpx.Client(base_url=API, verify=VERIFY, timeout=120,
                        headers={"Authorization": f"Bearer {env['FIREWORKS_API_KEY']}"})


def model_id(run):
    return f"sayso-{run}"


def upload(run):
    folder = ROOT / "adapters" / run
    config = json.loads((folder / "adapter_config.json").read_text())
    config.update(target_modules=MODULES, base_model_name_or_path="meta-models/Muse-Glimmer-30B")
    out = ROOT / "adapters" / f"{run}-fireworks"
    out.mkdir(exist_ok=True)
    (out / "adapter_config.json").write_text(json.dumps(config, indent=1))
    weights = out / "adapter_model.safetensors"
    if not weights.exists():
        weights.symlink_to(folder / "adapter_model.safetensors")
    files = {"adapter_config.json": out / "adapter_config.json", "adapter_model.safetensors": weights}

    c = client()
    r = c.post(f"/accounts/{ACCOUNT}/models", json={"modelId": model_id(run), "model": {
        "kind": "HF_PEFT_ADDON", "displayName": f"SaySo {run}",
        "peftDetails": {"baseModel": BASE, "r": config["r"], "targetModules": MODULES}}})
    print("create", r.status_code, r.text[:200] if r.status_code != 200 else "")
    r = c.post(f"/accounts/{ACCOUNT}/models/{model_id(run)}:getUploadEndpoint",
               json={"filenameToSize": {name: path.stat().st_size for name, path in files.items()}})
    r.raise_for_status()
    for name, url in r.json()["filenameToSignedUrls"].items():
        size = files[name].stat().st_size
        with files[name].open("rb") as f:
            put = httpx.put(url, content=f.read(), verify=VERIFY, timeout=1800, headers={
                "Content-Type": "application/octet-stream", "x-goog-content-length-range": f"{size},{size}"})
        print("put", name, put.status_code)
        put.raise_for_status()
    for _ in range(30):
        r = c.get(f"/accounts/{ACCOUNT}/models/{model_id(run)}:validateUpload")
        if r.status_code == 200:
            print("validated", r.text[:300])
            break
        time.sleep(10)
    print("state", c.get(f"/accounts/{ACCOUNT}/models/{model_id(run)}").json().get("state"))


def deploy(run):
    c = client()
    model = f"accounts/{ACCOUNT}/models/{model_id(run)}"
    r = c.post(f"/accounts/{ACCOUNT}/deploymentShapeVersions:match",
               json={"createDeploymentRequest": {"deployment": {"baseModel": model}}})
    r.raise_for_status()
    shapes = [v for v in r.json().get("deploymentShapeVersions", [])
              if v["snapshot"]["precision"] == "BF16" and v["snapshot"]["acceleratorType"].startswith("NVIDIA_H")]
    print("shapes", [(v["snapshot"]["acceleratorType"], v["name"]) for v in shapes])
    if not shapes:
        sys.exit("no BF16 H100/H200 shape for live merge")
    r = c.post(f"/accounts/{ACCOUNT}/deployments", params={"deploymentId": DEPLOYMENT}, json={
        "displayName": "SaySo", "baseModel": model, "deploymentShape": shapes[0]["name"],
        "minReplicaCount": 0, "maxReplicaCount": 1,
        "autoscalingPolicy": {"scaleUpWindow": "30s", "scaleDownWindow": "300s", "scaleToZeroWindow": "300s"}})
    print("deploy", r.status_code, r.text[:600])


def status():
    c = client()
    r = c.get(f"/accounts/{ACCOUNT}/deployments/{DEPLOYMENT}")
    d = r.json()
    print(r.status_code, {k: d.get(k) for k in ("state", "replicaCount", "desiredReplicaCount", "acceleratorType",
                                                  "baseModel", "status")})


def delete():
    r = client().delete(f"/accounts/{ACCOUNT}/deployments/{DEPLOYMENT}")
    print("delete", r.status_code, r.text[:200])


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    {"upload": upload, "deploy": deploy, "status": status, "delete": delete}[command](*args)
