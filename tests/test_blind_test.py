"""Blind test v3 tool, no network: build from made-up reply pairs with a fake SaySo API and a fake Muse Spark (the
selection filter on real and SaySo text, length matching, never two items from one situation), the page holds no
key, publish uploads only the public files, scoring math (Fisher, Newcombe CI, binomial), server responses + SS3
codes, and SS1-/SS2- codes and v2 keys still decode and score.

Usage: python3 -m pytest tests/test_blind_test.py   (or python3 -m unittest tests/test_blind_test.py)
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
WORDS = ["давай", "ну", "го", "слушай", "короче", "кстати", "норм", "щас", "потом", "завтра", "вечером", "погнали"]


def real_text(i):
    """Made-up replies of growing length (8 … ~120 chars), some in two bubbles."""
    words = [WORDS[(i + k) % len(WORDS)] for k in range(2 + i % 14)]
    text = " ".join(words) + ("!!" if i % 3 == 0 else ")")
    return text.replace(" потом ", "\nпотом ", 1) if i % 4 == 0 else text


def made_up_pairs(n=120):
    pairs = []
    for i in range(n):
        audience = ["friends", "friends", "family", "partner", "elder_informal"][i % 5]
        pairs.append((audience, "invitation", f"asks about weekend plan number {i} and what to bring", real_text(i)))
    return pairs


def row(audience, situation, task, user, assistant, turn_id, split="test"):
    return {"messages": [SYSTEM, {"role": "user", "content": user}, {"role": "assistant", "content": assistant}],
            "meta": {"turn_id": turn_id, "audience": audience, "situation": situation, "task": task, "split": split}}


def write_pairs(path, pairs, extra=()):
    rows = [row(a, s, "reply", f"audience: {a} · situation: {s}\ntask: reply\nincoming: {summary}", real, f"t{i}")
            for i, (a, s, summary, real) in enumerate(pairs)]
    rows += [row(*r) for r in extra]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def spark_reply(content, status=200):
    return status, {"choices": [{"message": {"role": "assistant", "content": content}}]}


class Fake:
    """One request function for both hosts: the SaySo API (/chat, /warmup, /blind/…) and the Meta Model API.
    sayso(summary) → the SaySo text; vet(text) → the label Muse Spark returns."""

    def __init__(self, sayso=None, vet=None, generic=None):
        self.calls, self.vetted = [], []
        self.sayso = sayso or (lambda s: "ну " + s.split("number ")[1].split(" ")[0] + " давай вечером го)")
        self.vet = vet or (lambda text: {})
        self.generic = generic or (lambda s: "«Ответ: Конечно, с удовольствием! Что взять с собой?»")

    def __call__(self, method, url, token, body=None, timeout=120):
        self.calls.append((method, url, token, body))
        if url.startswith("https://api.test"):
            assert token == "test-token"
            if url.endswith("/warmup"):
                return 200, {"ready": False, "gpu": "off"}
            assert url.endswith("/chat") and method == "POST"
            assert set(body) == {"mode", "text", "audience", "format"}
            assert (body["mode"], body["format"]) == ("reply", "message")
            summary = body["text"].split(": ", 1)[1]
            return 200, {"text": self.sayso(summary), "parts": [], "alternatives": []}
        assert url == blind_test.META_URL and token == "meta-key"
        assert body["model"] == "muse-spark-1.3" and body["reasoning_effort"] == "low"
        system, user = body["messages"][0]["content"], body["messages"][1]["content"]
        if system == blind_test.VET_SYSTEM:
            summary, text = re.match(r"Situation: (.*)\nMessage: (.*)\Z", user, re.S).groups()
            self.vetted.append((summary, text))
            label = {"safe": True, "normal": True, "trivial": False, "personal": True, "fits": True}
            return spark_reply(json.dumps({**label, **self.vet(text)}))
        if system.startswith("You turn a short neutral"):
            who = re.search(r"Start with «(.*?)»", system).group(1)
            return spark_reply(json.dumps({"ru": f"{who} спрашивает про план {user.split('number ')[1][:3]}"},
                                          ensure_ascii=False))
        assert system == blind_test.GENERIC_SYSTEM
        return spark_reply(self.generic(user))


def make_code(test_id, choices, name="", prefix="SS2-", v=2):
    raw = json.dumps({"v": v, "t": test_id, "n": name, "c": choices}, ensure_ascii=False).encode()
    return prefix + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def make_code3(test_id, picks, sid="sid-aaaa-1", name=""):
    raw = json.dumps({"v": 3, "t": test_id, "s": sid, "n": name, "a": picks}, ensure_ascii=False).encode()
    return "SS3-" + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def page_data(html):
    return json.loads(re.search(r"var DATA = (.*);\n", html).group(1))


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.pairs = self.dir / "test.jsonl"
        write_pairs(self.pairs, made_up_pairs())

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, fake, n=20, seed=1, **kwargs):
        api = blind_test.Api("https://api.test", "test-token", request=fake, sleep=lambda s: None, attempts=2)
        spark = blind_test.Spark("meta-key", request=fake, sleep=lambda s: None)
        kwargs.setdefault("post_url", lambda test_id: f"https://api.test/blind/{test_id}/answers")
        return blind_test.build(n, self.pairs, self.dir / "blind", api, spark, seed=seed, log=lambda *a: None,
                                **kwargs)

    def files(self, key):
        folder = self.dir / "blind" / key["test_id"]
        return (folder / "test.html").read_text(encoding="utf-8"), \
            json.loads((folder / "questions.json").read_text(encoding="utf-8")), \
            json.loads((folder / "answers.json").read_text(encoding="utf-8"))

    def test_twenty_questions_half_real_half_sayso(self):
        fake = Fake()
        key = self.build(fake, author="Тест")
        self.assertEqual(key["version"], 3)
        self.assertEqual(key["writer"], "off")
        self.assertEqual(len(key["questions"]), 20)
        self.assertEqual(Counter(q["source"] for q in key["questions"]), Counter({"real": 10, "sayso": 10}))
        self.assertEqual([q["id"] for q in key["questions"]], [f"q{i}" for i in range(1, 21)])
        self.assertEqual({q["audience"] for q in key["questions"]} - {"friends", "family"}, set())
        # one message per situation: never the real and the SaySo reply to the same one
        self.assertEqual(len({q["turn_id"] for q in key["questions"]}), 20)
        self.assertEqual(len({q["summary"] for q in key["questions"]}), 20)
        # shuffled: the sources are mixed, not 10 real then 10 SaySo
        self.assertNotEqual([q["source"] for q in key["questions"]], ["real"] * 10 + ["sayso"] * 10)
        for q in key["questions"]:
            self.assertTrue(q["context"].startswith({"friends": "Друг", "family": "Кто-то из семьи"}[q["audience"]]))
            self.assertIn((q["summary"], " / ".join(q["parts"])), fake.vetted)  # every shown text was screened
        self.assertGreaterEqual(len(key["test_id"]), 22)
        self.assertRegex(key["test_id"], r"^[A-Za-z0-9_-]+$")
        latest = json.loads((self.dir / "blind" / "latest.json").read_text())
        self.assertEqual(latest, {"test_id": key["test_id"]})

    def test_page_holds_no_key(self):
        key = self.build(Fake(), author="Тест")
        html, questions, stored = self.files(key)
        self.assertEqual(stored, key)
        data = page_data(html)
        self.assertEqual(data, questions)  # the public file the server gets is exactly what the page shows
        self.assertEqual(set(data), {"version", "test_id", "author", "questions", "post"})
        self.assertEqual(data["post"], f"https://api.test/blind/{key['test_id']}/answers")
        self.assertEqual(data["author"], "Тест")
        for page_q, key_q in zip(data["questions"], key["questions"]):
            self.assertEqual(set(page_q), {"id", "context", "parts"})
            self.assertEqual((page_q["context"], page_q["parts"]), (key_q["context"], key_q["parts"]))
        for q in key["questions"]:
            self.assertNotIn(q["summary"], html)
            self.assertNotIn(q["turn_id"] + '"', html)
        for secret in ("test-token", "meta-key", '"source"', '"real"', '"sayso"', '"summary"', '"audience"',
                       "__BLIND_DATA__"):
            self.assertNotIn(secret, html)
        self.assertIn('var PREFIX = "SS3-"', html)
        self.assertIn('<meta property="og:title"', html)
        self.assertIn('name="color-scheme" content="light dark"', html)
        self.assertIn(">Человек<", html)
        self.assertIn(">ИИ<", html)
        self.assertIn("Спасибо", html)
        self.assertIsNone(re.search(r"""(?:src|href)\s*=\s*["']?(?:https?:)?//""", html), "an external request")
        self.assertNotIn("@import", html)

    def test_audiences_friends_and_family_only(self):
        key = self.build(Fake())
        audiences = {f"t{i}": a for i, (a, *_) in enumerate(made_up_pairs())}
        self.assertEqual({audiences[q["turn_id"]] for q in key["questions"]}, {"friends", "family"})

    def test_filter_drops_failing_items_and_draws_more(self):
        marked = {real_text(i) for i in range(0, 120, 3)}  # every third real reply is "unsafe"

        def vet(text):
            if text.replace(" / ", "\n") in marked:
                return {"safe": False}
            if "ПЛОХО" in text:
                return {"personal": False}
            return {}
        fake = Fake(vet=vet, sayso=lambda s: "ПЛОХО ПЛОХО ПЛОХО" if int(s.split("number ")[1].split(" ")[0]) % 2 else
                    "ну давай " + s.split("number ")[1].split(" ")[0] + " вечером)")
        key = self.build(fake)
        self.assertEqual(Counter(q["source"] for q in key["questions"]), Counter({"real": 10, "sayso": 10}))
        html = self.files(key)[0]
        self.assertNotIn("ПЛОХО", html)
        for q in key["questions"]:
            if q["source"] == "real":
                self.assertNotIn("\n".join(q["parts"]), marked)
        self.assertTrue(any("ПЛОХО" in text for _, text in fake.vetted))  # SaySo text is screened too

    def test_unclear_vet_is_a_no(self):
        spark = blind_test.Spark("meta-key", request=lambda *a, **k: spark_reply("not json"), sleep=lambda s: None)
        self.assertFalse(spark.vet("asks", "ну давай вечером"))
        spark = blind_test.Spark("meta-key", request=lambda *a, **k: spark_reply('{"safe": true}'),
                                 sleep=lambda s: None)
        self.assertFalse(spark.vet("asks", "ну давай вечером"))  # missing fields: not kept
        spark = blind_test.Spark("meta-key", request=lambda *a, **k: (503, None), sleep=lambda s: None)
        self.assertFalse(spark.vet("asks", "ну давай вечером"))

    def test_cheap_checks(self):
        for parts in (["ок"], ["ахахах ору"], ["😂😂😂"], ["звони 8 701 123 45 67"], ["пиши на a@b.kz"],
                      ["смотри https://x.y"], ["[photo] вот"], ["а" * 300]):
            self.assertFalse(blind_test.showable(parts), parts)
        for parts in (["ну давай вечером"], ["го в 8", "я за"]):
            self.assertTrue(blind_test.showable(parts), parts)
        for text in ("ахахах", "ахаха)) ору", "😂😂😂", "))))", "LOL", "хаха хех", "Hahaha!"):
            self.assertTrue(blind_test.trivial(text), text)

    def test_length_matching(self):
        lengths = [10, 12, 15, 20, 25, 30, 40, 60, 80, 100]
        edges = blind_test.length_edges(lengths)
        self.assertEqual(edges, [20, 40])
        self.assertEqual([blind_test.bin_of(x, edges) for x in (5, 19, 20, 39, 40, 500)], [0, 0, 1, 1, 2, 2])
        self.assertEqual(blind_test.quotas(lengths, edges, 10), [3, 3, 4])
        self.assertEqual(blind_test.quotas(lengths, edges, 5), [2, 1, 2])
        self.assertEqual(sum(blind_test.quotas(lengths, edges, 7)), 7)

        # SaySo writes mostly short messages: the rarer lengths are found by drawing more, short extras are dropped
        def sayso(summary):
            i = int(summary.split("number ")[1].split(" ")[0])
            return {0: "слушай ну давай тогда вечером созвонимся и решим что берём с собой ок? а то я хз вообще",
                    1: "ну давай вечером созвонимся и решим, норм? я за)))"}.get(i % 4, "давай го)")
        fake = Fake(sayso=sayso)
        key = self.build(fake)
        real = [q["chars"] for q in key["questions"] if q["source"] == "real"]
        made = [q["chars"] for q in key["questions"] if q["source"] == "sayso"]
        edges = blind_test.length_edges(real)
        self.assertEqual(len({blind_test.bin_of(x, edges) for x in (9, 50, 88)}), 3, edges)  # one length per group
        self.assertEqual([sum(blind_test.bin_of(x, edges) == g for x in made) for g in range(3)],
                         blind_test.quotas(real, edges, 10))
        self.assertGreater(sum(c[1].endswith("/chat") for c in fake.calls), 10)  # drew more than it kept

    def test_length_fallback_takes_the_nearest(self):
        key = self.build(Fake(sayso=lambda s: "давай го)"))  # one length only: still 10, the nearest there are
        self.assertEqual(Counter(q["source"] for q in key["questions"])["sayso"], 10)
        spare = [{"chars": 9}, {"chars": 50}, {"chars": 200}]
        self.assertEqual(blind_test.closest(spare, 1, [20, 40], [10, 25, 30, 35, 60])["chars"], 50)

    def test_length_groups_exact_when_possible(self):
        def sayso(summary):  # every length available: the groups match the real ones exactly
            i = int(summary.split("number ")[1].split(" ")[0])
            return real_text((i * 7) % 60).replace("\n", " ")
        key = self.build(Fake(sayso=sayso))
        real = [q["chars"] for q in key["questions"] if q["source"] == "real"]
        made = [q["chars"] for q in key["questions"] if q["source"] == "sayso"]
        edges = blind_test.length_edges(real)
        self.assertEqual([sum(blind_test.bin_of(x, edges) == g for x in made) for g in range(3)],
                         blind_test.quotas(real, edges, 10))

    def test_generic_controls(self):
        fake = Fake()
        key = self.build(fake, generic=2)
        self.assertEqual(Counter(q["source"] for q in key["questions"]),
                         Counter({"real": 9, "sayso": 9, "generic": 2}))
        generic = [q for q in key["questions"] if q["source"] == "generic"]
        self.assertTrue(all(q["parts"] == ["Конечно, с удовольствием! Что взять с собой?"] for q in generic))
        prompts = [c[3]["messages"][1]["content"] for c in fake.calls
                   if c[1] == blind_test.META_URL and c[3]["messages"][0]["content"] == blind_test.GENERIC_SYSTEM]
        self.assertTrue(prompts and all("style" not in p.lower() for p in prompts))
        self.assertEqual(Counter(q["source"] for q in self.build(Fake())["questions"])["generic"], 0)  # default

    def test_html_escapes_script_breakers(self):
        key = {"test_id": "x" * 24, "author": "</script>", "questions": [
            {"id": "q1", "context": "Друг <b>", "parts": ["</script><b>x</b>", "a & b  "]}]}
        html = blind_test.render(blind_test.public(key))
        self.assertNotIn("</script><b>", html)
        self.assertEqual(html.count("</script>"), 1)
        data = page_data(html)
        self.assertEqual(data["questions"][0]["parts"], ["</script><b>x</b>", "a & b  "])
        self.assertEqual(data["author"], "</script>")


class Publish(unittest.TestCase):
    def test_uploads_public_files_only_and_prints_the_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "abcdefghijklmnopqrstuvwx"
            folder.mkdir()
            for name in ("test.html", "questions.json", "answers.json"):
                (folder / name).write_text("{}", encoding="utf-8")
            uploaded, said = [], []
            fake = lambda method, url, token, body=None, timeout=120: (200, "<html>") if token is None else (401, None)
            api = blind_test.Api("https://api.test/", None, request=fake)
            url = blind_test.publish(folder.name, api, Path(tmp), put=uploaded.extend, log=said.append)
            self.assertEqual(url, "https://api.test/blind/abcdefghijklmnopqrstuvwx")
            self.assertEqual([r for _, r in uploaded], ["/blind/abcdefghijklmnopqrstuvwx/test.html",
                                                        "/blind/abcdefghijklmnopqrstuvwx/questions.json"])
            self.assertTrue(any(url in s for s in said))
            with self.assertRaises(SystemExit):
                blind_test.publish("missing-test-id-xxxxxxxxx", api, Path(tmp), put=uploaded.extend, log=said.append)

    def test_responses_need_the_token(self):
        seen = []

        def fake(method, url, token, body=None, timeout=120):
            seen.append((method, url, token))
            return 200, {"responses": [{"sid": "s1", "answers": ["H"]}]}
        api = blind_test.Api("https://api.test", "test-token", request=fake)
        self.assertEqual(api.responses("t" * 24), [{"sid": "s1", "answers": ["H"]}])
        self.assertEqual(seen, [("GET", f"https://api.test/blind/{'t' * 24}/responses", "test-token")])
        with self.assertRaises(SystemExit):
            blind_test.Api("https://api.test", "bad", request=lambda *a, **k: (401, None)).responses("t" * 24)


class Decode(unittest.TestCase):
    def test_v3_codes(self):
        person = blind_test.decode(" " + make_code3("T" * 24, "HA-AH", sid="sid-1234", name="  Mira ") + "\n")
        self.assertEqual(person, {"version": 3, "test_id": "T" * 24, "name": "Mira", "sid": "sid-1234",
                                  "choices": {"q1": "H", "q2": "A", "q4": "A", "q5": "H"}})

    def test_v2_codes(self):
        person = blind_test.decode(make_code("cafe0001", {"q1": "C", "q2": "A", "q3": "D"}, "  Mira  "))
        self.assertEqual(person, {"version": 2, "test_id": "cafe0001", "name": "Mira",
                                  "choices": {"q1": "C", "q2": "A"}})

    def test_v1_codes_stay_readable(self):
        person = blind_test.decode(make_code("beef0001", {"q1": "A", "q2": "C"}, "Bob", prefix="SS1-", v=1))
        self.assertEqual(person, {"version": 1, "test_id": "beef0001", "name": "Bob", "choices": {"q1": "A"}})

    def test_bad_codes(self):
        for code in ("hello", "SS2-" + base64.urlsafe_b64encode(b'["x"]').decode(),
                     "SS3-" + base64.urlsafe_b64encode(b'{"v": 3, "a": 5}').decode()):
            with self.assertRaises(ValueError):
                blind_test.decode(code)


class Stats(unittest.TestCase):
    def test_binomial(self):
        # n = 3, p = 1/3: P(0..3) = 8/27, 12/27, 6/27, 1/27
        self.assertAlmostEqual(blind_test.binomial_p(3, 3)[0], 1 / 27)
        self.assertAlmostEqual(blind_test.binomial_p(2, 3)[0], 7 / 27)
        self.assertAlmostEqual(blind_test.binomial_p(1, 3)[0], 1.0)
        self.assertAlmostEqual(blind_test.binomial_p(10, 10, 0.5)[0], 2 / 1024)
        self.assertAlmostEqual(blind_test.binomial_p(5, 10, 0.5)[0], 1.0)
        self.assertEqual(blind_test.binomial_p(0, 0), (1.0, 1.0))

    def test_fisher(self):
        self.assertAlmostEqual(blind_test.fisher_p(3, 3, 0, 3), 0.1)  # 2 / C(6,3)
        self.assertAlmostEqual(blind_test.fisher_p(0, 3, 3, 3), 0.1)
        self.assertAlmostEqual(blind_test.fisher_p(2, 4, 2, 4), 1.0)
        self.assertAlmostEqual(blind_test.fisher_p(1, 9, 11, 14), 0.002759, places=5)  # the textbook example
        self.assertEqual(blind_test.fisher_p(0, 0, 3, 5), 1.0)

    def test_newcombe_interval(self):
        # Newcombe (1998), method 10: 56/70 − 48/80 → 0.0524 … 0.3339
        self.assertEqual(blind_test.difference_ci(56, 70, 48, 80), [0.052, 0.334])
        low, high = blind_test.difference_ci(10, 10, 0, 10)
        self.assertTrue(0.6 < low < 1 and high == 1.0)
        self.assertIsNone(blind_test.difference_ci(1, 0, 1, 2))


class ScoreV3(unittest.TestCase):
    TEST = "T" * 24

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        sources = ["real", "sayso", "real", "sayso", "generic"]
        questions = [{"id": f"q{i}", "source": s, "audience": "friends", "situation": "joke",
                      "summary": f"made-up summary {i}", "context": f"Друг пишет {i}", "parts": [f"текст {i}"],
                      "chars": 7, "turn_id": f"turn{i}"} for i, s in enumerate(sources, 1)]
        self.key = {"version": 3, "test_id": self.TEST, "writer": "off", "questions": questions,
                    "lengths": {"real": 7, "sayso": 7, "generic": 7}}
        self.answers = self.dir / "answers.json"
        self.answers.write_text(json.dumps(self.key, ensure_ascii=False), encoding="utf-8")
        self.results = self.dir / "results" / "blind_test.json"

    def tearDown(self):
        self.tmp.cleanup()

    def score(self, codes=(), responses=()):
        return blind_test.score(list(codes), self.answers, self.results, log=lambda *a: None,
                                responses=list(responses))

    def test_server_responses_and_codes(self):
        responses = [
            {"sid": "aaaaaaaa", "name": "Айгерим", "answers": ["A", "A", "A", "A", "A"], "at": 1},  # replaced below
            {"sid": "aaaaaaaa", "name": "Айгерим", "answers": ["H", "A", "H", "A", "A"], "at": 2},  # all correct
            {"sid": "bbbbbbbb", "name": "", "answers": ["H", "H", "H", "H", "H"], "at": 3},  # all «Человек»
            {"sid": "cccccccc", "answers": ["H", "H"], "at": 4},  # wrong length: skipped
        ]
        codes = [make_code3(self.TEST, "AHAH-", sid="dddddddd", name="Bob"),  # all wrong, generic unanswered
                 make_code3("O" * 24, "HHHHH", sid="eeeeeeee"),  # another test: skipped
                 make_code("cafe0001", {"q1": "A"})]  # a v2 code: skipped
        r = self.score(codes, responses)
        self.assertEqual((r["version"], r["people"], r["questions"], r["answers"]), (3, 3, 5, 14))
        self.assertEqual(r["items"], {"real": 2, "sayso": 2, "generic": 1})
        self.assertEqual(r["via"], {"server": 2, "code": 1})
        self.assertEqual((r["real_answers"], r["real_human"], r["real_human_rate"]), (6, 4, 0.667))
        self.assertEqual((r["sayso_answers"], r["sayso_human"], r["sayso_human_rate"]), (6, 4, 0.667))
        self.assertEqual((r["generic_answers"], r["generic_human"]), (2, 1))
        self.assertEqual(r["real_minus_sayso"], 0.0)
        self.assertEqual(r["p_real_vs_sayso"], 1.0)
        self.assertEqual(r["correct"], 4 + 2 + 1)
        self.assertEqual(r["accuracy"], 0.5)
        self.assertEqual(r["p_accuracy_vs_half"], round(blind_test.binomial_p(7, 14, 0.5)[0], 4))
        low, high = r["real_minus_sayso_ci95"]
        self.assertTrue(low < 0 < high)
        self.assertEqual([p["accuracy"] for p in r["per_person"]], [1.0, 0.4, 0.0])
        self.assertEqual(r["per_person"][0]["p_real_vs_sayso"], round(blind_test.fisher_p(2, 2, 0, 2), 4))
        by_q = {q["id"]: (q["source"], q["answers"], q["human"]) for q in r["per_question"]}
        self.assertEqual(by_q, {"q1": ("real", 3, 2), "q2": ("sayso", 3, 2), "q3": ("real", 3, 2),
                                "q4": ("sayso", 3, 2), "q5": ("generic", 2, 1)})
        self.assertEqual(r["item_mean_human_rate"]["sayso"], 0.667)
        self.assertEqual(r["sayso_items_judged_human_by_most"], 2)

        written = self.results.read_text(encoding="utf-8")
        self.assertEqual(json.loads(written), r)
        for text in ("текст", "Друг пишет", "made-up summary", "Айгерим", "Bob", "turn1", self.TEST, "aaaaaaaa"):
            self.assertNotIn(text, written)

    def test_sayso_judged_less_human(self):
        responses = [{"sid": f"person{i:02d}", "answers": ["H", "A", "H", "A", "A"], "at": i} for i in range(6)]
        r = self.score(responses=responses)
        self.assertEqual((r["real_human_rate"], r["sayso_human_rate"]), (1.0, 0.0))
        self.assertEqual(r["p_real_vs_sayso"], round(blind_test.fisher_p(12, 12, 0, 12), 4))
        self.assertLess(r["p_real_vs_sayso"], 0.001)
        self.assertEqual(r["accuracy"], 1.0)

    def test_nothing_to_score(self):
        with self.assertRaises(SystemExit):
            self.score([make_code3("O" * 24, "HHHHH")])


class ScoreV2(unittest.TestCase):
    """v2 keys and SS2 codes collected before v3 still score the old way."""

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
                 make_code("cafe0001", {"q9": "A"}),  # unknown questions only: skipped
                 make_code3("cafe0001", "HHH")]  # a v3 code: skipped
        results = self.score(codes)
        self.assertEqual(results["version"], 2)
        self.assertEqual((results["people"], results["questions"], results["answers"]), (3, 3, 8))
        self.assertEqual((results["real"], results["sayso"], results["generic"]), (3, 4, 1))
        self.assertEqual(results["sayso_share_of_wrong_picks"], 0.8)
        self.assertAlmostEqual(results["p_sayso_fools_more_than_generic"], round(6 / 32, 4))  # P(X ≥ 4 | 5, ½)
        written = self.results.read_text(encoding="utf-8")
        for text in ("текст", "пересказ", "Айгерим", "Bob", "t1"):
            self.assertNotIn(text, written)

    def test_rejects_v1_keys_and_foreign_codes(self):
        with self.assertRaises(SystemExit):
            self.score([make_code("other999", {"q1": "A"})])
        self.answers.write_text(json.dumps({"test_id": "cafe0001", "questions": []}), encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.score([make_code("cafe0001", {"q1": "A"})])


if __name__ == "__main__":
    unittest.main()
