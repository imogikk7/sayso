"""The user's styles, kept on the private volume. One style = how the user writes, learned from a set of chats.

  data/styles/<id>/meta.json         name, status, stage, scores, chats (name → audience), whether its LoRA is ready
                  turns.jsonl        the user's own turns only: {audience, situation, act, tone, text, split}
                  profile.json       pipeline/style_profile.describe per audience (× situation)
                  pairs/             training pairs for the style's LoRA (pairs_v4 format)
                  preferences.json   rules learned from the user's feedback in Chat ("shorter with family")
                  feedback.jsonl     texts the user liked or wrote themselves when fixing an answer: more examples

The main style is the author's Telegram model; its data stays where it was (data/pairs_v4, data/style_profile.json,
adapter v4) and only its meta.json, preferences and feedback live under data/styles/main.
Other people's messages are never written here.
"""

import json
import re
import secrets
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STYLES = DATA / "styles"
MAIN = "main"
MAX_PREFERENCES = 12
MAX_FEEDBACK = 500
ID = re.compile(r"^[a-z0-9]{1,16}$")

MAIN_META = {"id": MAIN, "name": "Me · Telegram", "status": "ready", "stage": "ready", "source": "Telegram export",
             "adapter": "v4", "adapter_ready": True, "created": 0}

on_write = None  # the API sets this to commit the Modal volume, so other containers see the change


def commit():
    if on_write:
        on_write()


def folder(style_id):
    if not ID.match(style_id or ""):
        raise KeyError(style_id)
    return STYLES / style_id


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def read_jsonl(path):
    try:  # closed right away: Modal can't reload the volume while a file is open
        with Path(path).open(encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def meta(style_id):
    """The style's meta.json, or None if there is no such style."""
    path = folder(style_id) / "meta.json"
    stored = read_json(path)
    if style_id == MAIN:
        return {**MAIN_META, **(stored or {})}
    return stored


def save_meta(style_id, value):
    write_json(folder(style_id) / "meta.json", value)


def update(style_id, **fields):
    value = meta(style_id) or {}
    value.update(fields, updated=time.time())
    save_meta(style_id, value)
    return value


def all_styles():
    found = [meta(MAIN)]
    if STYLES.exists():
        for path in STYLES.iterdir():
            if path.name != MAIN and ID.match(path.name) and (path / "meta.json").exists():
                found.append(meta(path.name))
    return sorted(found, key=lambda m: (m["id"] != MAIN, m.get("created", 0)))


def create(name):
    style_id = secrets.token_hex(4)
    value = {"id": style_id, "name": name.strip()[:40] or "My style", "status": "building", "stage": "uploading",
             "progress": 0.0, "created": time.time(), "adapter": f"style-{style_id}", "adapter_ready": False}
    save_meta(style_id, value)
    return value


def delete(style_id):
    if style_id == MAIN:
        raise PermissionError("the main style can't be deleted")
    shutil.rmtree(folder(style_id), ignore_errors=True)
    shutil.rmtree(DATA / "adapters" / f"style-{style_id}", ignore_errors=True)


def version(style_id):
    """Changes whenever anything the writer reads for this style changes."""
    parts = []
    for name in ("meta.json", "preferences.json", "feedback.jsonl", "profile.json"):
        path = folder(style_id) / name
        parts.append(path.stat().st_mtime if path.exists() else 0)
    return tuple(parts)


def turns(style_id):
    return read_jsonl(folder(style_id) / "turns.jsonl")


def main_turns():
    """The main style's own turns, from its training pairs (every target is a real message of the user's)."""
    rows = read_jsonl(DATA / "pairs_v4" / "train.jsonl")
    return [{"audience": r["meta"]["audience"], "situation": r["meta"]["situation"], "text": r["messages"][2]["content"],
             "act": r["meta"].get("act"), "tone": r["meta"].get("tone"), "split": "train"} for r in rows]


def preferences(style_id):
    return read_json(folder(style_id) / "preferences.json", [])


def add_preference(style_id, rule):
    rule = " ".join(rule.split())[:120].strip(" .")
    current = preferences(style_id)
    if not rule or rule.casefold() in {r.casefold() for r in current}:
        return current
    current = (current + [rule])[-MAX_PREFERENCES:]
    write_json(folder(style_id) / "preferences.json", current)
    return current


def remove_preference(style_id, index):
    current = preferences(style_id)
    if 0 <= index < len(current):
        current.pop(index)
        write_json(folder(style_id) / "preferences.json", current)
    return current


def feedback(style_id):
    return read_jsonl(folder(style_id) / "feedback.jsonl")


def add_feedback(style_id, record):
    """record = {audience, format, text, kind: liked | edited}: only text the user approved or wrote."""
    rows = (feedback(style_id) + [{**record, "at": time.time()}])[-MAX_FEEDBACK:]
    write_jsonl(folder(style_id) / "feedback.jsonl", rows)
