"""serving/build_style.py, the parts the first suites left untested: the build's synchronous Muse Spark (retries,
JSON in prose), reading chat screenshots (frames merged per chat), and the self-check (production writer and a
no-style baseline, both faked). No network, no GPU, made-up messages only.

Usage: .venv/bin/python -m pytest tests/test_cov_build.py
"""

import base64

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline"), str(ROOT / "eval"), str(ROOT / "tests")]

import build_style  # noqa: E402
import writer  # noqa: E402
from test_writer_fakes import STYLE, FakeResponse, WriterTestCase  # noqa: E402


class SyncClient:
    def __init__(self, *answers):
        self.answers, self.posts = list(answers), []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        status, content = answer
        return FakeResponse(status, {"choices": [{"message": {"content": content}}]})


class SyncSpark(unittest.TestCase):
    def setUp(self):
        self.saved_sleep, self.slept = build_style.time.sleep, []
        build_style.time.sleep = self.slept.append

    def tearDown(self):
        build_style.time.sleep = self.saved_sleep

    def test_json_in_prose_on_the_first_try(self):
        client = SyncClient((200, 'Sure! {"audience": "family"} hope it helps'))
        spark = build_style.Spark("k", client=client)
        self.assertEqual(spark("sys", "user", "audience"), {"audience": "family"})
        url, kwargs = client.posts[0]
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer k"})
        self.assertEqual(kwargs["json"]["messages"][0], {"role": "system", "content": "sys"})
        self.assertEqual(self.slept, [])

    def test_retries_then_succeeds(self):
        client = SyncClient((500, ""), TimeoutError(), (200, '{"text": "ok"}'))
        self.assertEqual(build_style.Spark("k", client=client)("s", "u", "text"), {"text": "ok"})
        self.assertEqual(self.slept, [2, 4])

    def test_three_failures_are_an_empty_label(self):
        for answer in ((200, "no json here"), (200, '{"other": 1}'), (200, "[1, 2]"), (429, "")):
            client = SyncClient(answer)
            self.assertEqual(build_style.Spark("k", client=client)("s", "u", "text"), {}, answer)
            self.assertEqual(len(client.posts), 3)


class ReadImages(unittest.TestCase):
    def test_frames_of_one_chat_are_merged_and_bad_messages_dropped(self):
        frames = {
            b"one": {"chat_name": "Mira", "messages": [{"side": "them", "text": "идешь?"}, {"side": "me", "text": "да"}]},
            b"two": {"chat_name": "Mira", "messages": [{"side": "me", "text": "да"}, {"side": "them", "text": "в 8"},
                                                       {"side": "narrator", "text": "x"}, {"side": "me", "text": 5},
                                                       "garbage"]},
            b"three": {"messages": [{"side": "me", "text": "ок"}]},
        }
        seen = []

        def spark(system, content, key):
            raw = base64.b64decode(content[1]["image_url"]["url"].split(",", 1)[1])
            seen.append((content[1]["image_url"]["url"].split(";")[0], raw))
            self.assertEqual((system, key), (build_style.SCREEN_SYSTEM, "messages"))
            return frames[raw]
        chats = build_style.read_images([("a.PNG", b"one"), ("b.jpg", b"two"), ("c.jpeg", b"three")], spark)
        self.assertEqual(sorted(seen), [("data:image/jpeg", b"three"), ("data:image/jpeg", b"two"),
                                        ("data:image/png", b"one")])
        self.assertEqual([(m["sender"], m["text"]) for m in chats["Mira"]], [("them", "идешь?"), ("me", "да"), ("them", "в 8")])
        self.assertEqual([m["text"] for m in chats["Screenshots"]], ["ок"])  # no title read
        self.assertLess(chats["Mira"][0]["ts"], chats["Mira"][1]["ts"])

    def test_unreadable_screenshot_is_no_messages(self):
        self.assertEqual(build_style.read_images([("x.png", b"x")], lambda *a: {}), {"Screenshots": []})


class SelfCheck(WriterTestCase):
    def setUp(self):
        super().setUp()
        self.saved_read = writer.Writer.read

    def tearDown(self):
        writer.Writer.read = self.saved_read
        super().tearDown()

    def test_too_few(self):
        self.assertEqual(build_style.self_check(STYLE, [], None, ""), {"note": "too few messages to check"})

    def test_scores_styled_against_baseline(self):
        drafts = iter(["го в 8", "", "ахах ок"])  # the second read gives no draft: not judged

        async def read(self, ctx, messages=None, audience=None, **_):
            draft = next(drafts)
            return {}, ([{"act": "agree", "draft": draft}] if draft else [])
        writer.Writer.read = read
        calls = []

        def spark(system, user, key):
            calls.append(key)
            if key == "scores":
                return {"scores": [{"i": 0, "score": 4}, {"i": 1, "score": 5}, {"i": 2}, "bad"]}
            return {"text": "Hello! Sure, I will be there at 8."}
        held_out = [{"context": ["идешь?"], "audience": "friends", "text": t} for t in ("го", "не могу", "ахах да")]
        check = build_style.self_check(STYLE, held_out, spark, "")
        self.assertEqual(check["checked"], 2)
        self.assertEqual(check["makes_sense"], 4.5)
        self.assertEqual([s["suggested"] for s in check["samples"]], ["го в 8", "ахах ок"])
        self.assertGreater(check["sounds_like_you"], check["generic"])
        self.assertEqual(calls.count("text"), 3)

    def test_failing_reads_are_skipped(self):
        async def read(self, *a, **k):
            raise writer.Unavailable(502, "down")
        writer.Writer.read = read
        check = build_style.self_check(STYLE, [{"context": ["x"], "audience": "friends", "text": "го"}],
                                       lambda s, u, k: {}, "")
        self.assertEqual((check["checked"], check["makes_sense"], check["sounds_like_you"]), (0, None, 0.0))


if __name__ == "__main__":

    unittest.main()
