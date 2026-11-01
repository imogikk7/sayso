"""Blind test v2 tool: build from a made-up reply-pair JSONL with a mocked SaySo API and a mocked Muse Spark (no
network), the page holds no key and no English summary, codes decode (v2 and v1), scoring math, and the results
file holds aggregate numbers only.

Usage: python3 -m unittest tests/test_blind_test.py
"""

import base64
import json
import re
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))

import blind_test  # noqa: E402

SYSTEM = {"role": "system", "content": "You write messages exactly like this user."}
PAIRS = [  # made-up summaries and replies
    ("partner", "logistics", "asks when the user will be home tonight and whether to wait with dinner",
     "буду к восьми\nне жди, ешь"),
    ("friends", "invitation", "invites the user to the cinema tomorrow evening and asks which film they prefer",
     "давай!! на что угодно кроме ужастиков"),
    ("family", "thanks", "thanks the user for help with moving and says the new place looks great",
     "да не за что, рада была помочь"),
    ("elder_informal", "request", "asks the user to send the homework file again because the link expired",
     "сейчас скину, извините за задержку"),
    ("friends", "good_news", "says they passed the driving test on the first try and are very happy",
     "ничего себе, поздравляю!!\nкогда катаемся?"),
]
SKIPPED = [  # never used: too short, laughter, emoji only, a rewrite and a compose pair
    ("friends", "joke", "reply", "audience: friends · situation: joke\ntask: reply\nincoming: sends a meme", "ок"),
    ("friends", "joke", "reply", "audience: friends · situation: joke\ntask: reply\nincoming: tells a joke",
     "ахахаха\nахах ору"),
    ("partner", "affection", "reply", "audience: partner · situation: affection\ntask: reply\nincoming: says hi",
     "😍😍😍 ❤️❤️"),
    ("friends", "joke", "rewrite", "audience: friends · situation: joke\ntask: rewrite\ndraft: hi", "приветики всем"),
    ("friends", "joke", "compose", "audience: friends\ntask: compose\ninstruction: say hi", "привет всем!!"),
]


def row(audience, situation, task, user, assistant, split="test"):
    return {"messages": [SYSTEM, {"role": "user", "content": user}, {"role": "assistant", "content": assistant}],
            "meta": {"turn_id": f"{audience}-{situation}-{task}", "audience": audience, "situation": situation,
                     "task": task, "split": split}}


def write_pairs(path):
    rows = [row(a, s, "reply", f"audience: {a} · situation: {s}\ntask: reply\nincoming: {summary}", real)
            for a, s, summary, real in PAIRS]
    rows += [row(*r) for r in SKIPPED]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def spark_reply(content, status=200):
    return status, {"choices": [{"message": {"role": "assistant", "content": content}}]}


class Fake:
    """One request function for both hosts: the SaySo API (POST /chat, GET /warmup) and the Meta Model API."""

    def __init__(self, sayso_text=None, generic_text=None, fail_chat=0):
        self.calls = []
        self.sayso_text, self.generic_text, self.fail_chat = sayso_text, generic_text, fail_chat

    def __call__(self, method, url, token, body=None, timeout=120):
        self.calls.append((method, url, token, body))
        if url.startswith("https://api.test"):
            assert token == "test-token"
            if url.endswith("/warmup"):
                return 200, {"ready": True}
            assert url.endswith("/chat") and method == "POST"
            if self.fail_chat:
                self.fail_chat -= 1
                return 503, None
            summary = body["text"].split(": ", 1)[1]
            return 200, {"text": self.sayso_text or f"SAYSO {body['audience']}\n{summary[:12]}",
                         "parts": [], "alternatives": ["x", "y"], "audience": body["audience"]}
        assert url == blind_test.META_URL and token == "meta-key"
        assert body["model"] == "muse-spark-1.3" and body["reasoning_effort"] == "low"
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        if system == blind_test.TRANSLATE_SYSTEM:
            return spark_reply('{"ru": "ПЕРЕСКАЗ ' + str(len(user)) + '"}')
        assert system == "You are a helpful assistant."
        return spark_reply(self.generic_text or "«Ответ: GENERIC " + str(len(user)) + "»")


def make_code(test_id, choices, name="", prefix="SS2-", v=2):
    raw = json.dumps({"v": v, "t": test_id, "n": name, "c": choices}, ensure_ascii=False).encode()
    return prefix + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def page_data(html):
    return json.loads(re.search(r"const DATA = (.*);\n", html).group(1))


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.pairs = self.dir / "test.jsonl"
        write_pairs(self.pairs)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, fake, n=5, seed=1, **kwargs):
        api = blind_test.Api("https://api.test", "test-token", request=fake, sleep=lambda s: None, attempts=3)
        spark = blind_test.Spark("meta-key", request=fake, sleep=lambda s: None)
        return blind_test.build(n, self.pairs, self.dir / "blind", api, spark, seed=seed, log=lambda *a: None,
                                **kwargs)

    def test_load_pairs_reply_only_and_usable(self):
        pairs = blind_test.load_pairs(self.pairs)
        self.assertEqual(len(pairs), 8)  # 5 good + 3 reply rows that are too short / laughter / emoji
        self.assertEqual(pairs[0]["summary"], PAIRS[0][2])
        self.assertEqual(pairs[0]["real"], PAIRS[0][3])
        self.assertEqual([p["real"] for p in pairs if blind_test.usable(p)], [r for *_, r in PAIRS])

    def test_trivial(self):
        for text in ("ахахах", "ахаха)) ору", "😂😂😂", "))))", "LOL", "хаха хех", "Hahaha!"):
            self.assertTrue(blind_test.trivial(text), text)
        for text in ("ахах ну ты даешь", "ок, давай", "хорошо"):
            self.assertFalse(blind_test.trivial(text), text)

    def test_build_writes_key_and_page(self):
        fake = Fake()
        key = self.build(fake)
        self.assertEqual(key["version"], 2)
        self.assertEqual(fake.calls[0][1], "https://api.test/warmup")
        self.assertEqual(key["writer"], "ready")

        chats = [c[3] for c in fake.calls if c[1].endswith("/chat")]
        self.assertEqual(len(chats), 5)
        for body in chats:
            self.assertEqual(set(body), {"mode", "text", "audience", "format"})
            self.assertEqual((body["mode"], body["format"]), ("reply", "message"))
            self.assertTrue(body["text"].startswith("Что написал собеседник (пересказ): "))
        self.assertEqual({c["text"].split(": ", 1)[1] for c in chats}, {s for _, _, s, _ in PAIRS})
        generic = [c[3] for c in fake.calls if c[1] == blind_test.META_URL
                   and c[3]["messages"][0]["content"] == "You are a helpful assistant."]
        self.assertEqual(len(generic), 5)
        for body in generic:  # plain prompt: no style, no examples, no profile
            user = body["messages"][1]["content"]
            self.assertTrue(user.startswith("Someone (") and "as yourself answering them" in user)
            self.assertNotIn("style", user.lower())

        self.assertEqual(Counter(q["audience"] for q in key["questions"]),
                         Counter({"friends": 2, "partner": 1, "family": 1, "elder_informal": 1}))
        reals = {tuple(blind_test.parts_of(r)) for *_, r in PAIRS}
        for q in key["questions"]:
            self.assertEqual(sorted(q[s] for s in blind_test.SOURCES), ["A", "B", "C"])
            options = {s: q["options"]["ABC".index(q[s])] for s in blind_test.SOURCES}
            self.assertIn(tuple(options["real"]), reals)
            self.assertEqual(options["sayso"][0], "SAYSO " + q["audience"])  # lines → stacked bubbles
            self.assertEqual(len(options["sayso"]), 2)
            self.assertTrue(options["generic"][0].startswith("GENERIC "))  # «Ответ: …» unwrapped
            self.assertTrue(q["context"].startswith("ПЕРЕСКАЗ "))
        self.assertEqual(json.loads((self.dir / "blind" / "answers.json").read_text(encoding="utf-8")), key)

        html = (self.dir / "blind" / "test.html").read_text(encoding="utf-8")
        self.assertIn("Один из трёх ответов написал я, два других — ИИ. Угадай, где я", html)
        self.assertIn('const PREFIX = "SS2-"', html)
        self.assertNotIn("__BLIND_DATA__", html)
        data = page_data(html)
        self.assertEqual(data["test_id"], key["test_id"])
        for page_q, key_q in zip(data["questions"], key["questions"]):
            self.assertEqual(set(page_q), {"id", "who", "context", "options"})  # no key, no summary, no tags
            self.assertEqual(page_q["options"], key_q["options"])
            self.assertIn(page_q["who"], {"Партнёр", "Друг", "Семья", "Преподаватель или старший"})
        for _, situation, summary, _ in PAIRS:
            self.assertNotIn(summary, html)
            self.assertNotIn(f'"{situation}"', html)
        for skipped in ("ахахаха", "😍😍😍", "приветики всем", "привет всем!!"):
            self.assertNotIn(skipped, html)

    def test_shuffles_positions(self):
        positions = Counter()
        for seed in range(12):
            key = self.build(Fake(), seed=seed)
            positions.update(q["real"] for q in key["questions"])
            positions.update("sayso-" + q["sayso"] for q in key["questions"])
        self.assertEqual(set(positions) & set("ABC"), set("ABC"))
        self.assertEqual({k for k in positions if k.startswith("sayso-")}, {"sayso-A", "sayso-B", "sayso-C"})

    def test_skips_identical_replies(self):
        key = self.build(Fake(generic_text="давай!! на что угодно кроме ужастиков"))  # = one real reply
        self.assertEqual(len(key["questions"]), 4)
        self.assertNotIn("invitation", {q["situation"] for q in key["questions"]})

    def test_retries_chat_then_gives_up(self):
        key = self.build(Fake(fail_chat=2), n=1)
        self.assertEqual(len(key["questions"]), 1)
        with self.assertRaises(SystemExit):
            self.build(Fake(fail_chat=99), n=1)

    def test_html_escapes_script_breakers(self):
        html = blind_test.render("abcd", [{"id": "q1", "audience": "friends", "context": "о чём-то",
                                           "options": [["</script><b>x</b>"], ["ok"], ["да"]]}])
        self.assertNotIn("</script><b>", html)
        data = page_data(html)
        self.assertEqual(data["questions"][0]["options"][0], ["</script><b>x</b>"])
        self.assertEqual(data["questions"][0]["who"], "Друг")

    def test_spark_translate_without_json(self):
        spark = blind_test.Spark("meta-key", request=lambda *a, **k: spark_reply("«Спрашивает про завтра»"),
                                 sleep=lambda s: None)
        self.assertEqual(spark.translate("asks about tomorrow"), "Спрашивает про завтра")


class Decode(unittest.TestCase):
    def test_v2_codes(self):
        person = blind_test.decode(" " + make_code("cafe0001", {"q1": "C", "q2": "A", "q3": "D"}, "  Mira  ") + "\n")
        self.assertEqual(person, {"version": 2, "test_id": "cafe0001", "name": "Mira",
                                  "choices": {"q1": "C", "q2": "A"}})

    def test_v1_codes_stay_readable(self):
        person = blind_test.decode(make_code("beef0001", {"q1": "A", "q2": "C"}, "Bob", prefix="SS1-", v=1))
        self.assertEqual(person, {"version": 1, "test_id": "beef0001", "name": "Bob", "choices": {"q1": "A"}})

    def test_bad_codes(self):
        with self.assertRaises(ValueError):
            blind_test.decode("hello")
        with self.assertRaises(ValueError):
            blind_test.decode("SS2-" + base64.urlsafe_b64encode(b'["x"]').decode())


class Score(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        letters = [("A", "B", "C"), ("B", "C", "A"), ("C", "A", "B")]  # (real, sayso, generic)
        questions = []
        for i in range(1, 4):
            real, sayso, generic = letters[i - 1]
            options = [None] * 3
            for source, letter in (("real", real), ("sayso", sayso), ("generic", generic)):
                options["ABC".index(letter)] = [f"{source} текст {i}"]
            questions.append({"id": f"q{i}", "audience": "friends" if i < 3 else "partner", "situation": "joke",
                              "context": f"пересказ {i}", "options": options, "real": real, "sayso": sayso,
                              "generic": generic, "turn_id": f"t{i}"})
        self.key = {"version": 2, "test_id": "cafe0001", "writer": "ready", "questions": questions}
        self.answers = self.dir / "answers.json"
        self.answers.write_text(json.dumps(self.key, ensure_ascii=False), encoding="utf-8")
        self.results = self.dir / "results" / "blind_test.json"

    def tearDown(self):
        self.tmp.cleanup()

    def score(self, codes):
        return blind_test.score(codes, self.answers, self.results, log=lambda *a: None)

    def test_scores_people_and_writes_aggregates_only(self):
        codes = [make_code("cafe0001", {"q1": "A", "q2": "B", "q3": "C"}, "Айгерим"),  # real ×3
                 make_code("cafe0001", {"q1": "B", "q2": "C", "q3": "A"}, "Bob"),  # SaySo ×3
                 make_code("cafe0001", {"q1": "B", "q2": "A"}),  # SaySo, generic
                 make_code("other999", {"q1": "A"}),  # another test: skipped
                 make_code("cafe0001", {"q9": "A"})]  # unknown questions only: skipped
        results = self.score(codes)
        self.assertEqual((results["people"], results["questions"], results["answers"]), (3, 3, 8))
        self.assertEqual((results["real"], results["sayso"], results["generic"]), (3, 4, 1))
        self.assertEqual((results["real_rate"], results["sayso_rate"], results["generic_rate"]), (0.375, 0.5, 0.125))
        self.assertEqual(results["sayso_share_of_wrong_picks"], 0.8)
        self.assertAlmostEqual(results["p_sayso_fools_more_than_generic"], round(6 / 32, 4))  # P(X ≥ 4 | 5, ½)
        two, better = blind_test.binomial_p(3, 8, 1 / 3)
        self.assertEqual((results["p_real_two_sided"], results["p_real_better_than_chance"]),
                         (round(two, 4), round(better, 4)))
        self.assertEqual([p["real"] for p in results["per_person"]], [3, 0, 0])
        self.assertEqual(results["per_person"][0]["real_rate"], 1.0)
        by_q = {q["id"]: (q["real"], q["sayso"], q["generic"]) for q in results["per_question"]}
        self.assertEqual(by_q, {"q1": (1, 2, 0), "q2": (1, 1, 1), "q3": (1, 1, 0)})
        self.assertEqual(results["questions_sayso_picked_most"], 1)
        self.assertEqual(results["top_sayso"][0], "q1")
        self.assertEqual(results["per_audience"]["friends"]["answers"], 6)
        self.assertEqual(results["per_audience"]["partner"]["sayso_rate"], 0.5)

        written = self.results.read_text(encoding="utf-8")
        self.assertEqual(json.loads(written), results)
        for text in ("текст", "пересказ", "Айгерим", "Bob", "t1"):
            self.assertNotIn(text, written)

    def test_binomial_vs_one_third(self):
        # n = 3, p = 1/3: P(0..3) = 8/27, 12/27, 6/27, 1/27
        self.assertAlmostEqual(blind_test.binomial_p(3, 3)[0], 1 / 27)
        self.assertAlmostEqual(blind_test.binomial_p(3, 3)[1], 1 / 27)
        self.assertAlmostEqual(blind_test.binomial_p(2, 3)[0], 7 / 27)
        self.assertAlmostEqual(blind_test.binomial_p(2, 3)[1], 7 / 27)
        self.assertAlmostEqual(blind_test.binomial_p(1, 3)[0], 1.0)
        self.assertAlmostEqual(blind_test.binomial_p(1, 3)[1], 19 / 27)
        self.assertAlmostEqual(blind_test.binomial_p(0, 3)[0], 15 / 27)
        self.assertAlmostEqual(blind_test.binomial_p(10, 10, 0.5)[0], 2 / 1024)
        self.assertEqual(blind_test.binomial_p(0, 0), (1.0, 1.0))

    def test_rejects_v1_keys_and_foreign_codes(self):
        with self.assertRaises(SystemExit):
            self.score([make_code("other999", {"q1": "A"})])
        self.answers.write_text(json.dumps({"test_id": "cafe0001", "questions": []}), encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.score([make_code("cafe0001", {"q1": "A"})])


if __name__ == "__main__":
    unittest.main()
