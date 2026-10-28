"""Parse a WhatsApp "Export Chat" (Without media) into the common message format.

Accepts the exported .zip or the _chat.txt inside it. Handles the iOS format
"[15.01.2024, 09:15:08] Name: text" and the Android format "15.01.2024, 09:15 - Name: text",
with day-first or month-first dates and 12/24-hour times. Continuation lines belong to
the previous message. Media placeholders and system lines are marked so they never
become training text.
"""

import re
import zipfile
from datetime import datetime
from pathlib import Path

IOS = re.compile(r"^‎?\[(\d{1,4}[./-]\d{1,2}[./-]\d{1,4}),? (\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AaPp]\.?[Mm]\.?)?)\] (.*)$")
ANDROID = re.compile(r"^‎?(\d{1,4}[./-]\d{1,2}[./-]\d{1,4}),? (\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AaPp]\.?[Mm]\.?)?) [-–] (.*)$")
MEDIA = re.compile(
    r"<attached: |<Media omitted>|<Без медиафайлов>|(image|video|audio|sticker|GIF|document) omitted|"
    r"(изображение|видео|аудиофайл|стикер|GIF|документ) (отсутствует|отсутствуют|omitted)|"
    r"This message was deleted|Данное сообщение удалено|Вы удалили это сообщение|You deleted this message",
    re.I,
)
SYSTEM = re.compile(  # iOS signs these with the chat name, as if the contact wrote them
    r"end-to-end encrypted|сквозным шифрованием|security code (with .* )?changed|код безопасности", re.I,
)
EDITED = re.compile(r"\s*‎?<(This message was edited|Сообщение изменено)>\s*$", re.I)
INVISIBLE = "‎‏‪‬﻿"


def read_text(path: Path) -> str:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            name = next(n for n in archive.namelist() if n.endswith(".txt"))
            return archive.read(name).decode("utf-8")
    return path.read_text(encoding="utf-8")


def parse_timestamp(date: str, time: str, day_first: bool) -> datetime:
    time = time.replace(".", "").upper().replace(" ", "")
    parts = re.split(r"[./-]", date)
    if len(parts[0]) == 4:  # 2024-01-15
        year, month, day = parts
    elif day_first:
        day, month, year = parts
    else:
        month, day, year = parts
    year = int(year) + (2000 if len(year) == 2 else 0)
    clock = "%I:%M:%S%p" if time.endswith("M") and time.count(":") == 2 else \
            "%I:%M%p" if time.endswith("M") else "%H:%M:%S" if time.count(":") == 2 else "%H:%M"
    t = datetime.strptime(time, clock)
    return datetime(year, int(month), int(day), t.hour, t.minute, t.second)


def guess_day_first(dates) -> bool:
    """Month-first if any date has a second field above 12, else day-first."""
    for date in dates:
        parts = re.split(r"[./-]", date)
        if len(parts[0]) != 4 and int(parts[1]) > 12:
            return False
    return True


def read_messages(path: Path):
    lines = read_text(path).splitlines()
    heads = [IOS.match(line) or ANDROID.match(line) for line in lines]
    day_first = guess_day_first(m.group(1) for m in heads if m)
    messages = []
    for line, head in zip(lines, heads):
        if not head:
            if messages:  # continuation of a multi-line message
                messages[-1]["text"] += "\n" + line
            continue
        date, time, rest = head.groups()
        sender, sep, text = rest.partition(": ")
        if not sep or SYSTEM.search(text):  # system line: "X created group", encryption notice
            continue
        messages.append({
            "id": len(messages),
            "ts": parse_timestamp(date, time, day_first),
            "sender": sender.strip(INVISIBLE + " ~"),
            "text": text,
            "kind": "text",
        })
    for msg in messages:
        msg["text"] = EDITED.sub("", msg["text"]).strip(INVISIBLE + " ")
        if MEDIA.search(msg["text"]):
            msg["kind"], msg["text"] = "media", ""
    return messages
