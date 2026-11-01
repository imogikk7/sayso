"""Blind test tool: build from a made-up 4-pair JSONL with a mocked API (no network), the page holds no key,
codes decode, scoring and the binomial p-value, and the results file holds aggregate numbers only.

Usage: python3 -m unittest tests/test_blind_test.py
"""

import base64
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))

import blind_test  # noqa: E402

SYSTEM = {"role": "system", "content": "You write messages exactly like this user."}
PAIRS = [  # made-up texts
    ("partner", "logistics", "I will be late by twenty minutes because of traffic.", "опоздаю минут на 20\nпробки жесть"),
    ("friends", "invitation", "Are we going to the cinema tomorrow?", "завтра кино в силе?\nя за"),
    ("family", "thanks", "Thank you for the dinner, it was very tasty.", "спасибо за ужин, было оч вкусно"),
    ("elder_informal", "request", "Can you send me the address again, please?", "скинь адрес еще раз плиз"),
]


def row(audience, situation, task, user, assistant, split="test"):
    return {"messages": [SYSTEM, {"role": "user", "content": user}, {"role": "assistant", "content": assistant}],
            "meta": {"turn_id": f"{audience}-{task}", "audience": audience, "situation": situation, "task": task,
                     "split": split}}


def write_pairs(path):
    rows = [row(a, s, "rewrite", f"audience: {a} · situation: {s}\ntask: rewrite\ndraft: {draft}", real)
            for a, s, draft, real in PAIRS]
    rows.append(row("friends", "joke", "reply", "audience: friends · situation: joke\ntask: reply\nincoming: jokes",
                    "ахах ну ты даешь"))  # not a rewrite pair: never used
    rows.append(row("friends", "joke", "compose", "audience: friends\ntask: compose\ninstruction: say hi", "привет!!"))
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


class FakeApi:
    """Answers like POST /rewrite; `cold` first calls come back from the Muse Spark fallback (styled = false)."""

    def __init__(self, cold=0, echo_real=()):
        self.calls, self.cold, self.echo_real = [], cold, set(echo_real)

    def __call__(self, method, url, token, body=None, timeout=120):
        assert token == "test-token" and url.startswith("https://api.test")
        self.calls.append((method, url, body))
        if url.endswith("/warmup"):
            return 200, {"ready": True}
        assert url.endswith("/rewrite") and body["format"] == "message"
        styled = len([c for c in self.calls if c[1].endswith("/rewrite")]) > self.cold
        real = {draft: real for _, _, draft, real in PAIRS}[body["text"]]
        text = real if body["text"] in self.echo_real else f"SAYSO {body['audience']}\nвторая строка"
        return 200, {"text": text, "parts": [text], "candidates": [text], "audiences": [], "styled": styled}


def make_code(test_id, choices, name=""):
    raw = json.dumps({"v": 1, "t": test_id, "n": name, "c": choices}, ensure_ascii=False).encode()
    return "SS1-" + base64.urlsafe_b64encode(raw).decode().rstrip("=")


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.pairs = self.dir / "test.jsonl"
        write_pairs(self.pairs)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, fake, n=4, **kwargs):
        api = blind_test.Api("https://api.test", "test-token", request=fake, sleep=lambda s: None, attempts=3)
        return blind_test.build(n, self.pairs, self.dir / "blind", api, seed=1, log=lambda *a: None, **kwargs)

    def test_build_writes_key_and_page(self):
        fake = FakeApi()
        key = self.build(fake)
        rewrites = [c for c in fake.calls if c[1].endswith("/rewrite")]
        self.assertEqual(len(rewrites), 4)
        self.assertEqual({c[2]["text"] for c in rewrites}, {d for _, _, d, _ in PAIRS})
        self.assertEqual(fake.calls[0][1], "https://api.test/warmup")
        self.assertEqual({q["audience"] for q in key["questions"]}, {"partner", "friends", "family", "elder_informal"})

        saved = json.loads((self.dir / "blind" / "answers.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, key)
        for q in key["questions"]:
            real, fake_text = (q["a"], q["b"]) if q["real"] == "A" else (q["b"], q["a"])
            self.assertIn(real, {r.replace("\n", " / ") for *_, r in PAIRS})  # lines joined with " / "
            self.assertTrue(fake_text.startswith("SAYSO") and " / " in fake_text and "\n" not in fake_text)

        html = (self.dir / "blind" / "test.html").read_text(encoding="utf-8")
        self.assertIn("Один из двух вариантов написал я, другой — ИИ. Угадай, где я", html)
        self.assertNotIn("__BLIND_DATA__", html)
        data = json.loads(re.search(r"const DATA = (.*);\n", html).group(1))
        self.assertEqual(data["test_id"], key["test_id"])
        for page_q, key_q in zip(data["questions"], key["questions"]):
            self.assertEqual(set(page_q), {"id", "audience", "situation", "a", "b"})  # no key, no draft
            self.assertEqual((page_q["a"], page_q["b"]), (key_q["a"], key_q["b"]))
        for _, _, draft, _ in PAIRS:
            self.assertNotIn(draft, html)
        self.assertNotIn("ахах ну ты даешь", html)  # reply / compose rows are never used
        self.assertNotIn("привет!!", html)

    def test_html_escapes_script_breakers(self):
        html = blind_test.render("abcd", [{"id": "q1", "audience": "friends", "situation": "joke",
                                           "a": "</script><b>x</b>", "b": "ok", "real": "A"}])
        self.assertNotIn("</script><b>", html)
        data = json.loads(re.search(r"const DATA = (.*);\n", html).group(1))
        self.assertEqual(data["questions"][0]["a"], "</script><b>x</b>")
        self.assertEqual(data["questions"][0]["audience"], "другу / подруге")

    def test_waits_for_the_personal_model(self):
        fake = FakeApi(cold=2)  # two Spark fallbacks, then the LoRA
        key = self.build(fake, n=1)
        self.assertTrue(key["questions"][0]["styled"])
        with self.assertRaises(SystemExit):
            self.build(FakeApi(cold=99), n=1)
        key = self.build(FakeApi(cold=99), n=1, allow_unstyled=True)
        self.assertFalse(key["questions"][0]["styled"])

    def test_skips_identical_versions(self):
        echo = {PAIRS[0][2]}
        key = self.build(FakeApi(echo_real=echo), n=4)
        self.assertEqual(len(key["questions"]), 3)
        self.assertNotIn(PAIRS[0][3].replace("\n", " / "), json.dumps(key, ensure_ascii=False))

    def test_load_pairs_rewrite_only(self):
        pairs = blind_test.load_pairs(self.pairs)
        self.assertEqual(len(pairs), 4)
        self.assertEqual(pairs[0]["draft"], PAIRS[0][2])
        self.assertEqual(pairs[0]["real"], PAIRS[0][3])


class Score(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.key = {"test_id": "cafe0001", "questions": [
            {"id": f"q{i}", "audience": "friends" if i % 2 else "partner", "situation": "joke",
             "a": f"реальный текст {i}" if i % 2 else f"текст SaySo {i}",
             "b": f"текст SaySo {i}" if i % 2 else f"реальный текст {i}", "real": "A" if i % 2 else "B",
             "styled": True} for i in range(1, 5)]}
        self.answers = self.dir / "answers.json"
        self.answers.write_text(json.dumps(self.key, ensure_ascii=False), encoding="utf-8")
        self.results = self.dir / "results" / "blind_test.json"

    def tearDown(self):
        self.tmp.cleanup()

    def score(self, codes):
        return blind_test.score(codes, self.answers, self.results, log=lambda *a: None)

    def test_scores_people_and_writes_aggregates_only(self):
        right = {"q1": "A", "q2": "B", "q3": "A", "q4": "B"}
        codes = [make_code("cafe0001", right, "Айгерим"),  # 4/4
                 make_code("cafe0001", {"q1": "B", "q2": "A", "q3": "A", "q4": "B"}, "Bob"),  # 2/4
                 "  " + make_code("cafe0001", {"q1": "B", "q2": "A", "q3": "B"}) + "\n",  # 0/3, whitespace ok
                 make_code("other999", right)]  # another test: skipped
        results = self.score(codes)
        self.assertEqual((results["people"], results["answers"], results["correct"]), (3, 11, 6))
        self.assertAlmostEqual(results["accuracy"], round(6 / 11, 3))
        self.assertEqual([p["correct"] for p in results["per_person"]], [4, 2, 0])
        fooled = {q["id"]: q["fooled"] for q in results["per_question"]}
        self.assertEqual(fooled, {"q1": 2, "q2": 2, "q3": 1, "q4": 0})
        self.assertEqual(results["questions_fooled_majority"], 2)
        self.assertEqual(set(results["per_audience"]), {"friends", "partner"})

        written = self.results.read_text(encoding="utf-8")
        self.assertEqual(json.loads(written), results)
        for text in ("реальный", "SaySo ", "Айгерим", "Bob"):
            self.assertNotIn(text, written)

    def test_binomial(self):
        two, better = blind_test.binomial_p(10, 10)
        self.assertAlmostEqual(two, 2 / 1024)
        self.assertAlmostEqual(better, 1 / 1024)
        two, better = blind_test.binomial_p(5, 10)
        self.assertAlmostEqual(two, 1.0)
        self.assertAlmostEqual(better, 638 / 1024)
        self.assertAlmostEqual(blind_test.binomial_p(2, 10)[0], blind_test.binomial_p(8, 10)[0])

    def test_bad_codes(self):
        with self.assertRaises(ValueError):
            blind_test.decode("hello")
        with self.assertRaises(ValueError):
            blind_test.decode("SS1-" + base64.urlsafe_b64encode(b'["x"]').decode())
        person = blind_test.decode(make_code("cafe0001", {"q1": "A", "q2": "C"}, "  Mira  "))
        self.assertEqual(person, {"test_id": "cafe0001", "name": "Mira", "choices": {"q1": "A"}})
        with self.assertRaises(SystemExit):
            self.score([make_code("other999", {"q1": "A"})])


if __name__ == "__main__":
    unittest.main()
