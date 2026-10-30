"""Train the user's LoRA on Fireworks (credits; Glimmer SFT is free there until Nov 30) from data/pairs_v4.

Fireworks doesn't let this account upload adapter weights, so the same pairs are trained there instead.
Loss only on the assistant turn (system and user get weight 0); the thought goes in reasoning_content, which
Glimmer's template renders into its to=self channel, as in training/modal_train.py.

  .venv/bin/python training/fireworks_sft.py upload v4         # builds data/fireworks/v4.jsonl, uploads it
  .venv/bin/python training/fireworks_sft.py train v4           # starts the job, prints its estimated cost
  .venv/bin/python training/fireworks_sft.py status v4
"""

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "serving"))
from fireworks import ACCOUNT, BASE, VERIFY, client  # noqa: E402

REASONING = "Reasoning strength: low."


def dataset_id(run):
    return f"sayso-{run}-pairs"


def build(run, pairs="pairs_v4"):
    out = ROOT / "data" / "fireworks" / f"{run}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out.open("w", encoding="utf-8") as f:
        for line in (ROOT / "data" / pairs / "train.jsonl").open(encoding="utf-8"):
            system, user, assistant = json.loads(line)["messages"]
            reply = {"role": "assistant", "content": assistant["content"]}
            if assistant.get("reasoning_content"):
                reply["reasoning_content"] = assistant["reasoning_content"]
            f.write(json.dumps({"messages": [
                {"role": "system", "content": f"{system['content']}\n{REASONING}", "weight": 0},
                {"role": "user", "content": user["content"], "weight": 0},
                reply,
            ]}, ensure_ascii=False) + "\n")
            count += 1
    return out, count


def upload(run):
    path, count = build(run)
    c = client()
    r = c.post(f"/accounts/{ACCOUNT}/datasets", json={"datasetId": dataset_id(run), "dataset": {
        "displayName": f"SaySo {run} pairs", "userUploaded": {}, "exampleCount": str(count), "format": "CHAT"}})
    print("create", r.status_code, "" if r.status_code == 200 else r.text[:300])
    with path.open("rb") as f:
        r = httpx.post(f"{c.base_url}/accounts/{ACCOUNT}/datasets/{dataset_id(run)}:upload", verify=VERIFY,
                       timeout=600, headers={"Authorization": c.headers["Authorization"]},
                       files={"file": (path.name, f, "application/jsonl")})
    print("upload", r.status_code, r.text[:200])
    r = c.post(f"/accounts/{ACCOUNT}/datasets/{dataset_id(run)}:validateUpload", json={})
    print("validate", r.status_code, r.text[:200])
    print("state", c.get(f"/accounts/{ACCOUNT}/datasets/{dataset_id(run)}").json().get("state"), count, "examples")


def train(run, epochs=2, lr=2e-4):
    job = {"displayName": f"SaySo {run}", "baseModel": BASE, "dataset": f"accounts/{ACCOUNT}/datasets/{dataset_id(run)}",
           "outputModel": f"accounts/{ACCOUNT}/models/sayso-{run}", "epochs": epochs, "learningRate": lr,
           "loraRank": 16, "maxContextLength": 2048, "batchSizeSamples": 16}
    c = client()
    r = c.post(f"/accounts/{ACCOUNT}/supervisedFineTuningJobs", params={"supervisedFineTuningJobId": f"sayso-{run}"},
               json=job)
    if r.status_code >= 400 and "unknown field" in r.text.lower():
        r = c.post(f"/accounts/{ACCOUNT}/supervisedFineTuningJobs", params={"supervisedFineTuningJobId": f"sayso-{run}"},
                   json={"supervisedFineTuningJob": job})
    print("job", r.status_code, r.text[:800])


def status(run):
    d = client().get(f"/accounts/{ACCOUNT}/supervisedFineTuningJobs/sayso-{run}").json()
    print({k: d.get(k) for k in ("state", "status", "jobProgress", "estimatedCost", "outputModel", "completedTime")})


if __name__ == "__main__":
    command, run = sys.argv[1:3]
    {"upload": upload, "train": train, "status": status}[command](run)
