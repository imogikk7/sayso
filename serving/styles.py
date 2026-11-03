"""The user's styles, kept on the private volume. One style = how the user writes, learned from a set of chats.

  data/styles/<id>/meta.json         name, status, stage, scores, chats (name → audience), whether its LoRA is ready
                  turns.jsonl        the user's own turns only: {audience, situation, act, tone, text, split}
                  profile.json       pipeline/style_profile.describe per audience (× situation)
                  pairs/             training pairs for the style's LoRA (pairs_v4 format)
                  preferences.json   rules learned from the user's feedback in Chat ("shorter with family")
                  feedback.jsonl     texts the user liked or wrote themselves when fixing an answer: more examples
                  learned.jsonl      messages the user typed and sent with the SaySo keyboard, and how they changed a
                                     suggestion before sending it (their own text only)
                  documents.jsonl    paragraphs of the user's own formal writing (emails, essays) and formal.json, its
                                     profile: their formal voice for official messages, emails and essays
                  custom.json        what the user set by hand in the Styles tab: their own greetings and sign-offs
                                     for emails (and the default of each), phrases they never use per kind of text

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
MAX_LEARNED = 3000
ID = re.compile(r"^[a-z0-9]{1,16}$")

MAIN_META = {"id": MAIN, "name": "Me · Telegram", "status": "ready", "stage": "ready", "source": "Telegram export",
             "adapter": "v4", "adapter_ready": True, "lora": "ready", "created": 0,
             # measured by eval/style_gain.py on 40 held-out messages (form of the writer's output vs the user's own)
             "scores": {"sounds_like_you": 0.93, "generic": 0.69, "checked": 40,
                        "note": "Measured on 40 of your messages the model never saw (eval/style_gain.py)."}}

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
            lines = [line for line in f if line.strip()]
    except FileNotFoundError:
        return []
    rows = []
    for line in lines:  # a torn line (a write cut short) is skipped, not fatal for the whole style
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)  # atomic: readers see the old file or the new one, never half of it


_main_counts = None


def main_counts():
    """How many of the user's own messages the main style was built from (its training pairs), counted once."""
    global _main_counts
    if _main_counts is None:
        try:
            with (DATA / "pairs_v4" / "train.jsonl").open(encoding="utf-8") as f:
                _main_counts = {"turns": sum(1 for line in f if line.strip())}
        except FileNotFoundError:
            return {}
    return _main_counts


def meta(style_id):
    """The style's meta.json, or None if there is no such style."""
    path = folder(style_id) / "meta.json"
    stored = read_json(path)
    if style_id == MAIN:
        return {**MAIN_META, "counts": main_counts(), **(stored or {})}
    return stored


def save_meta(style_id, value):
    write_json(folder(style_id) / "meta.json", value)


class Gone(Exception):
    """The style was deleted while something was still working on it."""


def update(style_id, **fields):
    value = meta(style_id)
    if value is None:  # deleted meanwhile: don't bring a half meta.json back
        raise Gone(style_id)
    value.update(fields, updated=time.time())
    save_meta(style_id, value)
    return value


def all_styles():
    found = [meta(MAIN)]
    if STYLES.exists():
        for path in STYLES.iterdir():
            if path.name != MAIN and ID.match(path.name) and (path / "meta.json").exists():
                value = meta(path.name)
                if isinstance(value, dict) and value.get("id") == path.name:
                    found.append(value)
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
    for name in ("meta.json", "preferences.json", "feedback.jsonl", "learned.jsonl", "profile.json", "formal.json",
                 "custom.json"):
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


def learned(style_id):
    return read_jsonl(folder(style_id) / "learned.jsonl")


def add_learned(style_id, rows):
    """rows = [{audience, text, kind: typed | edited, suggested?}]: what the user wrote with the keyboard."""
    stamped = [{**row, "id": secrets.token_hex(4), "at": time.time()} for row in rows]
    write_jsonl(folder(style_id) / "learned.jsonl", (learned(style_id) + stamped)[-MAX_LEARNED:])
    return stamped


def remove_learned(style_id, learned_id):
    rows = learned(style_id)
    kept = [r for r in rows if r.get("id") != learned_id]
    if len(kept) != len(rows):
        write_jsonl(folder(style_id) / "learned.jsonl", kept)


def documents(style_id):
    return read_jsonl(folder(style_id) / "documents.jsonl")


def formal(style_id):
    return read_json(folder(style_id) / "formal.json", {})


def add_documents(style_id, uploads, kind="essay"):
    """uploads = [(name, text)] of the user's own writing of one kind ("email" or "essay") → paragraphs appended,
    formal profile recomputed (greetings and sign-offs come from emails only)."""
    import documents as parse
    rows = documents(style_id)
    ends = [tuple(e) for e in formal(style_id).get("ends", [])]
    for name, text in uploads:
        if kind == "email":
            text = parse.own_email(text)
        paragraphs = parse.paragraphs(text)
        if paragraphs:
            rows += [{"doc": name[:80], "kind": kind, "text": t} for t in paragraphs]
            if kind == "email":
                ends.append(parse.edges(text))
    rows = rows[-parse.MAX_PARAGRAPHS:]
    write_jsonl(folder(style_id) / "documents.jsonl", rows)
    counts = {k: len({r["doc"] for r in rows if r.get("kind", "essay") == k}) for k in parse.KINDS}
    value = {"documents": len({r["doc"] for r in rows}), "counts": counts, "ends": ends[-50:],
             "profile": parse.profile([r["text"] for r in rows], ends)}
    write_json(folder(style_id) / "formal.json", value)
    return value


def clear_documents(style_id):
    for name in ("documents.jsonl", "formal.json"):
        (folder(style_id) / name).unlink(missing_ok=True)


# ---- what the user set by hand ------------------------------------------------------------------------------

CUSTOM_LISTS = {"email": ("openers", "signoffs", "avoid"), "essay": ("avoid",), "message": ("avoid",)}
CUSTOM_DEFAULTS = {"email": {"openers": "default_opener", "signoffs": "default_signoff"}}  # list → its default
MAX_CUSTOM_ITEMS = 20
MAX_CUSTOM_CHARS = 80


def custom(style_id):
    """custom.json: {email: {openers, signoffs, default_opener, default_signoff, avoid}, essay: {avoid},
    message: {avoid}}. A list that is missing was never edited (the app shows what SaySo parsed instead)."""
    value = read_json(folder(style_id) / "custom.json", {})
    return value if isinstance(value, dict) else {}


def custom_items(values):
    """Trimmed, one line each, no duplicates (ignoring case), at most MAX_CUSTOM_ITEMS of MAX_CUSTOM_CHARS."""
    out, seen = [], set()
    for value in values or []:
        item = " ".join(str(value).split())[:MAX_CUSTOM_CHARS].strip()
        if item and item.casefold() not in seen:
            seen.add(item.casefold())
            out.append(item)
    return out[:MAX_CUSTOM_ITEMS]


def set_custom(style_id, changes):
    """changes = {kind: {field: value} | None}, only the fields being changed. A list replaces the stored one (None =
    forget it, back to what SaySo parsed); a default must be one of its list's items, or it is dropped."""
    current = custom(style_id)
    for kind, fields in (changes or {}).items():
        if kind in CUSTOM_LISTS and fields is None:  # {kind: null}: forget everything set for this kind
            current.pop(kind, None)
            continue
        if kind not in CUSTOM_LISTS or not isinstance(fields, dict):
            raise ValueError(f"unknown kind of text: {kind}")
        defaults = CUSTOM_DEFAULTS.get(kind, {})
        section = dict(current.get(kind) or {})
        for name, value in fields.items():
            if name in CUSTOM_LISTS[kind]:
                if value is None:
                    section.pop(name, None)
                elif isinstance(value, list):
                    section[name] = custom_items(value)
                else:
                    raise ValueError(f"{kind}.{name} must be a list")
            elif name in defaults.values():
                item = " ".join(str(value or "").split())[:MAX_CUSTOM_CHARS].strip()
                section[name] = item or None
            else:
                raise ValueError(f"unknown field: {kind}.{name}")
        for list_name, default_name in defaults.items():
            chosen = section.get(default_name)
            match = [i for i in section.get(list_name) or [] if chosen and i.casefold() == chosen.casefold()]
            if match:
                section[default_name] = match[0]
            else:
                section.pop(default_name, None)
        if section:
            current[kind] = section
        else:
            current.pop(kind, None)
    write_json(folder(style_id) / "custom.json", current)
    return current


def parsed_ends(style_id, limit=8):
    """Every greeting and sign-off SaySo found in the user's emails, most used first: (openers, signoffs)."""
    from collections import Counter
    openers, signoffs = Counter(), Counter()
    for pair in formal(style_id).get("ends", []):
        opening, closing = (list(pair) + [None, None])[:2]
        if opening:
            openers[opening.rstrip(",:!")] += 1
        if closing:
            signoffs[closing.rstrip(",.")] += 1
    return [o for o, _ in openers.most_common(limit)], [c for c, _ in signoffs.most_common(limit)]


def formal_by_kind(style_id):
    """The formal profile of each kind of text on its own ({email: …, essay: …}), so emails and essays each show
    their own traits; plus how many documents and paragraphs per document."""
    import statistics
    import documents as parse
    rows, out = documents(style_id), {}
    ends = [tuple(e) for e in formal(style_id).get("ends", [])]
    for kind in parse.KINDS:
        mine = [r for r in rows if r.get("kind", "essay") == kind]
        if not mine:
            continue
        per_doc = {}
        for r in mine:
            per_doc[r["doc"]] = per_doc.get(r["doc"], 0) + 1
        profile = parse.profile([r["text"] for r in mine], ends if kind == "email" else [])
        out[kind] = {**profile, "documents": len(per_doc),
                     "paragraphs_per_doc": round(statistics.median(per_doc.values()), 1)}
    return out
