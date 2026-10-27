"""Parse Telegram Desktop HTML exports into the user's own turns.

A turn is a run of consecutive own messages in one chat (no other sender in
between and no gap longer than `turn_gap_minutes`), merged with newlines.
Turns longer than `max_turn_messages` are split at their longest pauses.
Only the user's own text is kept; other people's messages are used only to
detect turn boundaries and are never written out.

Usage:  python3 pipeline/parse_telegram.py [--config data/config.json]
Writes: data/turns.jsonl (gitignored) and prints turn stats per audience.
"""

import argparse
import html
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

MESSAGE_START = re.compile(r'<div class="message ([^"]*)"(?: id="message(-?\d+)")?\s*>')
DATE = re.compile(r'<div class="pull_right date details" title="([^"]+)"')
FROM_NAME = re.compile(r'<div class="from_name">\s*(.*?)\s*</div>', re.S)
TEXT = re.compile(r'<div class="text">(.*?)</div>', re.S)

URL = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+\.(?:com|ru|kz|org|net|io|me|ly|gl)(?:/\S*)?", re.I)
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
PHONE = re.compile(r"(?<![\w:])\+?\d[\d\s()-]{8,}\d(?![\w:])")
PASTED_CODE = re.compile(r"</\w+>|<!DOCTYPE|^\s*(?:def|import|class|function|#include)\b", re.I | re.M)


def parse_date(title: str) -> datetime:
    """Accepts '15 января 2024, 09:15:08' and '15.01.2024 09:15:08 UTC+05:00'."""
    m = re.match(r"(\d{1,2}) (\w+) (\d{4}), (\d{1,2}):(\d{2}):(\d{2})", title)
    if m and m.group(2) in RU_MONTHS:
        d, mon, y, hh, mm, ss = m.groups()
        return datetime(int(y), RU_MONTHS[mon], int(d), int(hh), int(mm), int(ss))
    return datetime.strptime(title[:19], "%d.%m.%Y %H:%M:%S")


def html_to_text(fragment: str) -> str:
    fragment = re.sub(r"<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(fragment).strip()


def clean(text: str) -> str:
    for pattern in (URL, EMAIL, CARD, PHONE):
        text = pattern.sub("", text)
    lines = (re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


def page_number(path: Path) -> int:
    m = re.fullmatch(r"messages(\d*)\.html", path.name)
    return int(m.group(1) or 1)


def read_messages(export_dirs: list[Path]):
    """Yield messages from one chat's exports in order, deduplicated by id.

    Each message: {id, ts, sender, text, kind} where kind is 'text', 'media'
    (no own text: stickers, photos, voice), 'forwarded' or 'service'.
    """
    seen = set()
    messages = []
    for export_dir in export_dirs:
        pages = sorted(export_dir.glob("messages*.html"), key=page_number)
        sender = None
        for page in pages:
            source = page.read_text(encoding="utf-8")
            starts = list(MESSAGE_START.finditer(source))
            for i, start in enumerate(starts):
                block = source[start.start():starts[i + 1].start() if i + 1 < len(starts) else len(source)]
                classes = start.group(1).split()
                if "service" in classes:
                    continue
                msg_id = start.group(2)
                date = DATE.search(block)
                if not date:
                    continue
                name = FROM_NAME.search(block)
                if name:
                    sender = html_to_text(name.group(1))
                elif "joined" not in classes:
                    continue
                if msg_id in seen:
                    continue
                seen.add(msg_id)
                text = TEXT.search(block)
                if 'class="forwarded_from' in block or 'class="forwarded body' in block:
                    kind = "forwarded"
                elif text:
                    kind = "text"
                else:
                    kind = "media"
                messages.append({
                    "id": int(msg_id),
                    "ts": parse_date(date.group(1)),
                    "sender": sender,
                    "text": html_to_text(text.group(1)) if text else "",
                    "kind": kind,
                })
    messages.sort(key=lambda m: (m["ts"], m["id"]))
    return messages


def build_turns(messages, self_name: str, gap: timedelta, max_messages: int):
    """Merge consecutive own text messages into turns of at most max_messages."""
    turns = []
    current = None
    prev_ts = None
    prev_own = False
    for msg in messages:
        own = msg["sender"] == self_name
        if not own:
            current = None
            prev_own = False
            continue
        if current is not None and (not prev_own or msg["ts"] - prev_ts > gap):
            current = None
        prev_ts, prev_own = msg["ts"], True
        if msg["kind"] != "text" or PASTED_CODE.search(msg["text"]):
            continue
        text = clean(msg["text"])
        if not text:
            continue
        if current is None:
            current = {"start": msg["ts"], "end": msg["ts"], "messages": [], "is_reply": None}
            turns.append(current)
        if current["messages"] and current["messages"][-1][1] == text:
            continue  # double send
        current["messages"].append((msg["ts"], text))
        current["end"] = msg["ts"]
    # A turn is a reply if someone else wrote right before it (within the gap).
    by_start = {}
    last_other = None
    for msg in messages:
        if msg["sender"] != self_name:
            last_other = msg["ts"]
        by_start.setdefault(msg["ts"], last_other)
    for turn in turns:
        other = by_start.get(turn["start"])
        turn["is_reply"] = other is not None and turn["start"] - other <= gap
    return [chunk for turn in turns for chunk in split_turn(turn, max_messages)]


def split_turn(turn, max_messages: int):
    """Split a long monologue at its longest pauses until every chunk fits.

    Only the first chunk keeps the turn's is_reply; later chunks follow the user's own messages.
    """
    def split(items):
        if len(items) <= max_messages:
            return [items]
        cut = max(range(1, len(items)), key=lambda i: items[i][0] - items[i - 1][0])
        return split(items[:cut]) + split(items[cut:])

    return [
        {
            "start": items[0][0],
            "end": items[-1][0],
            "messages": [text for _, text in items],
            "is_reply": turn["is_reply"] and i == 0,
        }
        for i, items in enumerate(split(turn["messages"]))
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "data" / "config.json"))
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    audiences = json.loads((ROOT / "data" / "audiences.json").read_text(encoding="utf-8"))
    gap = timedelta(minutes=config.get("turn_gap_minutes", 10))
    test_span = timedelta(weeks=config.get("test_weeks", 4))
    max_messages = config.get("max_turn_messages", 12)
    out_path = ROOT / config.get("output", "data/turns.jsonl")

    rows = []
    per_chat = {}
    for chat, dirs in config["chats"].items():
        audience = audiences.get(chat)
        if audience is None:
            raise SystemExit(f"chat {chat!r} has no audience in data/audiences.json")
        messages = read_messages([Path(d).expanduser() for d in dirs])
        own = [m for m in messages if m["sender"] == config["self_name"]]
        turns = build_turns(messages, config["self_name"], gap, max_messages)
        cutoff = max(t["end"] for t in turns) - test_span if turns else None
        for turn in turns:
            rows.append({
                "chat": chat,
                "audience": audience,
                "start": turn["start"].isoformat(),
                "end": turn["end"].isoformat(),
                "split": "test" if turn["start"] >= cutoff else "train",
                "is_reply": turn["is_reply"],
                "n_messages": len(turn["messages"]),
                "text": "\n".join(turn["messages"]),
            })
        per_chat[chat] = {
            "audience": audience,
            "own_messages": len(own),
            "own_text": sum(m["kind"] == "text" for m in own),
            "turns": len(turns),
            "first": min((t["start"] for t in turns), default=None),
            "last": max((t["end"] for t in turns), default=None),
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print_stats(rows, per_chat, config.get("max_chat_share", 0.35))
    print(f"\nwrote {len(rows)} turns to {out_path.relative_to(ROOT)}")


def print_stats(rows, per_chat, max_share):
    total = len(rows)
    print(f"{'chat':<18}{'audience':<16}{'own msgs':>9}{'own text':>9}{'turns':>7}{'share':>7}  period")
    for chat, s in sorted(per_chat.items(), key=lambda kv: -kv[1]["turns"]):
        share = s["turns"] / total if total else 0
        flag = " > cap" if share > max_share else ""
        period = f"{s['first']:%Y-%m-%d} – {s['last']:%Y-%m-%d}" if s["first"] else "-"
        print(f"{chat:<18}{s['audience']:<16}{s['own_messages']:>9}{s['own_text']:>9}"
              f"{s['turns']:>7}{share:>6.0%}{flag}  {period}")

    by_audience = defaultdict(list)
    for row in rows:
        by_audience[row["audience"]].append(row)
    print(f"\n{'audience':<16}{'chats':>6}{'turns':>7}{'train':>7}{'test':>6}{'share':>7}"
          f"{'msgs/turn':>10}{'chars':>7}{'multi':>7}{'reply':>7}")
    for audience, items in sorted(by_audience.items(), key=lambda kv: -len(kv[1])):
        n = len(items)
        chats = len({r["chat"] for r in items})
        train = sum(r["split"] == "train" for r in items)
        msgs = sum(r["n_messages"] for r in items) / n
        chars = sorted(len(r["text"]) for r in items)[n // 2]
        multi = sum(r["n_messages"] > 1 for r in items) / n
        reply = sum(r["is_reply"] for r in items) / n
        print(f"{audience:<16}{chats:>6}{n:>7}{train:>7}{n - train:>6}{n / total:>6.0%}"
              f"{msgs:>10.2f}{chars:>7}{multi:>6.0%}{reply:>6.0%}")
    print("\nchars = median turn length; multi = turns of 2+ messages; "
          "reply = turn right after someone else's message")


if __name__ == "__main__":
    main()
