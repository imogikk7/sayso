"""Parsers on small made-up exports: same message format, own turns built the same way.

Usage: python3 -m unittest tests/test_parsers.py
"""

import json
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

from parse_telegram import build_turns  # noqa: E402
from sources import detect, read_chat  # noqa: E402

WHATSAPP_IOS = """‎[15.01.2024, 09:15:08] Анна: Сообщения и звонки защищены сквозным шифрованием.
[15.01.2024, 09:15:08] Анна: завтра кино идем?
[15.01.2024, 09:16:01] Лев: го
[15.01.2024, 09:16:05] Лев: во сколько
после пар норм?
[15.01.2024, 09:17:00] Анна: ‎изображение отсутствует
[15.01.2024, 09:18:30] Лев: ахах ну да ‎<Сообщение изменено>
"""

WHATSAPP_ANDROID = """1/15/24, 9:15 PM - Messages and calls are end-to-end encrypted.
1/15/24, 9:15 PM - Sam: are you free on saturday?
1/15/24, 9:16 PM - Leo: yes!!
1/15/24, 9:16 PM - Leo: <Media omitted>
1/15/24, 9:40 PM - Leo: what time
"""


def mojibake(text):
    return text.encode("utf-8").decode("latin-1")


def instagram_thread():
    base = int(datetime(2024, 1, 15, 9, 15).timestamp() * 1000)
    return {
        "participants": [{"name": mojibake("Аня")}, {"name": mojibake("Лев")}],
        "messages": [  # newest first, as Meta writes them
            {"sender_name": mojibake("Лев"), "timestamp_ms": base + 120_000, "content": mojibake("ну давай 😅")},
            {"sender_name": mojibake("Аня"), "timestamp_ms": base + 90_000, "content": "Reacted ❤ to your message"},
            {"sender_name": mojibake("Лев"), "timestamp_ms": base + 60_000, "content": mojibake("го")},
            {"sender_name": mojibake("Аня"), "timestamp_ms": base + 30_000, "share": {"link": "https://x"}},
            {"sender_name": mojibake("Аня"), "timestamp_ms": base, "content": mojibake("пойдем гулять?")},
        ],
    }


def own_turns(messages, self_name):
    return build_turns(messages, self_name, timedelta(minutes=10), 12, 1000, timedelta(minutes=30))


class WhatsApp(unittest.TestCase):
    def test_ios_russian(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "WhatsApp Chat.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("_chat.txt", WHATSAPP_IOS)
            self.assertEqual(detect(path), "whatsapp")
            messages = read_chat([path])
        self.assertEqual([m["sender"] for m in messages], ["Анна", "Лев", "Лев", "Анна", "Лев"])
        self.assertEqual(messages[2]["text"], "во сколько\nпосле пар норм?")
        self.assertEqual(messages[3]["kind"], "media")
        self.assertEqual(messages[4]["text"], "ахах ну да")
        self.assertEqual(messages[1]["ts"], datetime(2024, 1, 15, 9, 16, 1))
        turns = own_turns(messages, "Лев")
        self.assertEqual([t["messages"] for t in turns], [["го", "во сколько\nпосле пар норм?"], ["ахах ну да"]])
        self.assertEqual(turns[0]["context"], ["завтра кино идем?"])
        self.assertEqual(turns[1]["context"], ["[media]"])

    def test_android_us_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chat.txt"
            path.write_text(WHATSAPP_ANDROID, encoding="utf-8")
            messages = read_chat([path])
        self.assertEqual(messages[0]["ts"], datetime(2024, 1, 15, 21, 15))
        self.assertEqual([m["kind"] for m in messages], ["text", "text", "media", "text"])
        turns = own_turns(messages, "Leo")
        # 24 min gap after the media message → two turns
        self.assertEqual([t["messages"] for t in turns], [["yes!!"], ["what time"]])


class Instagram(unittest.TestCase):
    def test_json_with_mojibake(self):
        with tempfile.TemporaryDirectory() as tmp:
            thread = Path(tmp) / "messages" / "inbox" / "anya_123"
            thread.mkdir(parents=True)
            (thread / "message_1.json").write_text(json.dumps(instagram_thread()), encoding="utf-8")
            self.assertEqual(detect(thread), "instagram")
            messages = read_chat([thread])
        self.assertEqual([m["sender"] for m in messages], ["Аня", "Аня", "Лев", "Аня", "Лев"])
        self.assertEqual([m["kind"] for m in messages], ["text", "media", "text", "media", "text"])
        turns = own_turns(messages, "Лев")
        self.assertEqual([t["messages"] for t in turns], [["го"], ["ну давай 😅"]])
        self.assertEqual(turns[0]["context"], ["пойдем гулять?", "[media]"])


if __name__ == "__main__":
    unittest.main()
