"""Route an export path to the right parser. Every parser returns the same message dicts:
{id, ts, sender, text, kind} with kind in text / media / forwarded."""

import zipfile
from pathlib import Path


def detect(path: Path) -> str:
    if path.is_dir():
        if any(path.glob("messages*.html")):
            return "telegram"
        if any(path.glob("message_*.json")):
            return "instagram"
    elif path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
        if any(n.endswith(".json") and "/message_" in n for n in names):
            return "instagram"
        if any(n.endswith(".txt") for n in names):
            return "whatsapp"
    elif path.suffix == ".txt":
        return "whatsapp"
    elif path.suffix == ".json":
        return "instagram"
    raise ValueError(f"unrecognized export: {path}")


def read_any(path: Path):
    kind = detect(path)
    if kind == "telegram":
        from parse_telegram import read_messages
        return read_messages([path])
    if kind == "whatsapp":
        from parse_whatsapp import read_messages
    else:
        from parse_instagram import read_messages
    return read_messages(path)


def read_chat(paths):
    """Messages from one chat's exports (possibly several, possibly overlapping), in time order.

    Telegram keeps its real message ids (turn ids depend on them). Other formats have no
    ids, so overlapping exports are deduplicated by content and numbered after merging.
    """
    paths = [Path(p).expanduser() for p in paths]
    if all(detect(p) == "telegram" for p in paths):
        from parse_telegram import read_messages
        return read_messages(paths)
    seen = set()
    messages = []
    for path in paths:
        for msg in read_any(path):
            key = (msg["ts"], msg["sender"], msg["text"])
            if key not in seen:
                seen.add(key)
                messages.append(msg)
    messages.sort(key=lambda m: m["ts"])
    for i, msg in enumerate(messages):
        msg["id"] = i
    return messages
