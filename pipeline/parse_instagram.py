"""Parse an Instagram / Facebook Messenger "Download your information" (JSON) thread.

Accepts a thread folder (messages/inbox/<thread>/message_*.json), a single
message_*.json, or the downloaded .zip with exactly one thread. Meta writes UTF-8
text as latin-1 escapes ("Ð¿Ñ\u0080Ð¸Ð²ÐµÑ\u0082"), so every string is re-decoded.
Reactions, likes, shares and media become non-text messages.
"""

import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

NOT_TEXT = re.compile(
    r"^(Reacted .* to your message|Liked a message|.* sent an attachment\.|.* shared a story\.|"
    r"Отреагировал.* на ваше сообщение|.* отправил.* вложение\.)$"
)


def fix_mojibake(text: str) -> str:
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def load_threads(path: Path):
    """Yield the parsed message_*.json documents of one thread, in file order."""
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = sorted(n for n in archive.namelist() if re.search(r"/message_\d+\.json$", n))
            threads = {n.rsplit("/", 2)[-2] for n in names}
            if len(threads) != 1:
                raise ValueError(f"{path.name}: expected one thread, found {len(threads)}; pass its folder instead")
            for name in names:
                yield json.loads(archive.read(name))
    elif path.is_dir():
        for file in sorted(path.glob("message_*.json")):
            yield json.loads(file.read_text(encoding="utf-8"))
    else:
        yield json.loads(path.read_text(encoding="utf-8"))


def read_messages(path: Path):
    raw = [m for doc in load_threads(path) for m in doc.get("messages", [])]
    raw.sort(key=lambda m: m["timestamp_ms"])  # files are newest-first
    messages = []
    for i, m in enumerate(raw):
        text = fix_mojibake(m.get("content", ""))
        if m.get("is_unsent") or "share" in m or any(k in m for k in ("photos", "videos", "audio_files", "gifs", "sticker", "files")) or NOT_TEXT.match(text):
            kind, text = "media", ""
        else:
            kind = "text"
        messages.append({
            "id": i,
            "ts": datetime.fromtimestamp(m["timestamp_ms"] / 1000),
            "sender": fix_mojibake(m.get("sender_name", "")),
            "text": text,
            "kind": kind,
        })
    return messages
