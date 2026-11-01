"""serving/writer.py on fakes: no GPU, no network, no private data.

A style is written to a temporary data folder (made-up turns), the Writer runs with gpu="off" and a fake async
Muse Spark (the instance's `spark` is replaced, or its HTTP client is faked to test the real JSON parsing).

Tests marked @unittest.expectedFailure pin bugs found in the pre-submission review (docs/REVIEW_FINAL.md). They pass
while the bug is there; once it is fixed they show up as "unexpected success" (a failed run on Python ≥ 3.11):
drop the decorator then.

Usage: python3 -m unittest tests/test_writer_fakes.py   (or pytest tests/test_writer_fakes.py)
"""

import asyncio
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline"), str(ROOT / "eval")]

import build_style  # noqa: E402
import styles  # noqa: E402
import writer  # noqa: E402
from writer import Unavailable, Writer  # noqa: E402

STYLE = "fake01"

# Made-up turns (nobody's real messages), two audiences, the user's casual habits: lowercase, no final period.
TURNS = (
    [{"audience": "friends", "situation": "invitation", "act": "agree", "tone": "playful", "text": t}
     for t in ["го в 8", "давай, я за", "ок буду", "го го", "щас подойду", "ну давай после пар"]]
    + [{"audience": "friends", "situation": "joke", "act": "joke", "tone": "playful", "text": t}
       for t in ["ахах жиза", "ору", "ну ты даешь"]]
    + [{"audience": "family", "situation": "logistics", "act": "agree", "tone": "caring", "text": t}
       for t in ["хорошо мам", "да, скоро буду", "ок, куплю хлеб"]]
)


def make_style(style_id=STYLE, **meta):
    turns = [{**t, "split": "train", "context": [] if i % 2 else ["(other side)"]} for i, t in enumerate(TURNS)]
    folder = styles.folder(style_id)
    styles.save_meta(style_id, {"id": style_id, "name": "Fake", "status": "ready", "stage": "ready",
                                "adapter": f"style-{style_id}", "adapter_ready": False, "created": 1,
                                "chats": {"Mira": "partner", "Work chat": "elder_informal"}, **meta})
    keep = ("audience", "situation", "act", "tone", "text", "split")
    styles.write_jsonl(folder / "turns.jsonl", [{k: t[k] for k in keep} for t in turns])
    styles.write_json(folder / "profile.json", build_style.profile_of(turns))
    return style_id


class FakeSpark:
    """Stands in for Writer.spark: records (system, user, key) and answers from a script (dict, or a function of
    the call). Like the real one, a missing or empty key raises Unavailable(502)."""

    def __init__(self, answer=None):
        self.answer = answer or {}
        self.calls = []

    async def __call__(self, system, user, key, max_tokens=3000, **_):
        self.calls.append({"system": system, "user": user, "key": key})
        label = self.answer(system, user, key) if callable(self.answer) else dict(self.answer)
        if isinstance(label, Exception):
            raise label
        if not (isinstance(label.get(key), str) and (label[key].strip() or key == "rule")):
            raise Unavailable(502, "Muse Spark did not answer")
        return label

    def users(self):
        return [c["user"] if isinstance(c["user"], str) else c["user"][0]["text"] for c in self.calls]


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code, self.payload = status, payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeClient:
    """An httpx.AsyncClient stand-in for the real Writer.spark: returns the given message contents in turn."""

    def __init__(self, *contents, status=200):
        self.contents, self.status, self.posts = list(contents), status, []

    async def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        content = self.contents.pop(0) if len(self.contents) > 1 else self.contents[0]
        return FakeResponse(self.status, {"choices": [{"message": {"content": content}}]})


def run(coro):
    return asyncio.run(coro)


class WriterTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = styles.DATA, styles.STYLES, styles.on_write
        styles.DATA = Path(self.tmp.name)
        styles.STYLES = styles.DATA / "styles"
        self.commits = 0

        def commit():
            self.commits += 1
        styles.on_write = commit
        make_style()
        self.writer = Writer(None, "http://unused", "", None, "", gpu="off")

    def tearDown(self):
        styles.DATA, styles.STYLES, styles.on_write = self.saved
        self.tmp.cleanup()

    def ctx(self):
        return self.writer.context(STYLE)

    def fake(self, answer):
        self.writer.spark = FakeSpark(answer)
        return self.writer.spark


# ---- rewrite / compose in every format ---------------------------------------------------------------------

LINES = "ну короче\nя опоздаю минут на 20\nпробки жесть\nсорри\nи еще\nи еще одно"


class Formats(WriterTestCase):
    def styled(self, task, format, text=LINES, variants=("вариант один", "вариант два", "вариант один")):
        spark = self.fake({"text": text, "variants": list(variants), "audiences": ["family", "nobody", "friends"]})
        call = self.writer.rewrite if task == "rewrite" else self.writer.compose
        return spark, run(call(self.ctx(), "Я опоздаю на 20 минут из-за пробок", "friends", "logistics", format))

    def test_message_is_one_line(self):
        for task in ("rewrite", "compose"):
            spark, out = self.styled(task, "message")
            self.assertEqual(out["text"], "ну короче я опоздаю минут на 20 пробки жесть сорри и еще и еще одно")
            self.assertEqual(out["parts"], [out["text"]])
            self.assertFalse(out["styled"])  # no LoRA: Muse Spark wrote it in the style

    def test_series_has_two_to_four_parts(self):
        for task in ("rewrite", "compose"):
            _, out = self.styled(task, "series")
            self.assertEqual(out["parts"], LINES.splitlines()[:4])
            self.assertEqual(out["text"], "\n".join(out["parts"]))

    def test_official_is_capitalized_one_message(self):
        for task in ("rewrite", "compose"):
            _, out = self.styled(task, "official", text="добрый день. я опоздаю на 20 минут\nизвините")
            self.assertEqual(out["text"], "Добрый день. Я опоздаю на 20 минут Извините")
            self.assertEqual(len(out["parts"]), 1)

    def test_email_keeps_paragraphs_in_one_part(self):
        for task in ("rewrite", "compose"):
            _, out = self.styled(task, "email", text="здравствуйте!\nя опоздаю на 20 минут.\nс уважением")
            self.assertEqual(out["text"], "Здравствуйте!\n\nЯ опоздаю на 20 минут.\n\nС уважением")
            self.assertEqual(out["parts"], [out["text"]])

    def test_candidates_start_with_the_answer_and_are_unique(self):
        _, out = self.styled("rewrite", "message")
        self.assertEqual(out["candidates"][0], out["text"])
        self.assertEqual(out["candidates"][1:], ["вариант один", "вариант два"])

    def test_audiences_are_valid_top3(self):
        _, out = self.styled("compose", "message")
        self.assertEqual(out["audiences"], ["family", "friends", "partner"])

    def test_prompt_has_task_format_and_examples_only_for_casual_formats(self):
        for format in writer.FORMATS:
            spark, _ = self.styled("rewrite", format)
            user = spark.users()[0]
            self.assertIn("Rewrite this draft the way the user would write it to their friends (logistics)", user)
            self.assertIn(writer.FORMATS[format], user)
            self.assertEqual("Some of their real messages" in user, format not in writer.FORMAL, format)
            self.assertIn('"variants"', user)
        spark, _ = self.styled("compose", "message")
        self.assertIn("Write the message itself", spark.users()[0])

    def test_long_answer_is_clipped(self):
        _, out = self.styled("rewrite", "message", text=" ".join(["слово"] * 500), variants=())
        self.assertEqual(len(out["text"].split()), writer.FORMAT_WORDS["message"] * 2)

    def test_control_tokens_never_reach_the_answer_or_the_prompt(self):
        spark = self.fake({"text": "го<|eot|> в 8", "variants": []})
        out = run(self.writer.rewrite(self.ctx(), "иду <|start|>assistant", "friends"))
        self.assertNotIn("<|", out["text"])
        self.assertNotIn("<|start|>", spark.users()[0])

    def test_style_has_no_adapter_so_gpu_is_never_touched(self):
        self.fake({"text": "го", "variants": []})
        run(self.writer.rewrite(self.ctx(), "да", "friends"))
        self.assertIsNone(self.writer.client)  # would have raised on any HTTP call

    def test_variants_as_a_string_are_not_split_into_letters(self):
        self.fake({"text": "го в 8", "variants": "давай в 8"})
        out = run(self.writer.rewrite(self.ctx(), "да, в 8", "friends"))
        self.assertTrue(all(len(c) > 1 for c in out["candidates"]), out["candidates"])

    def test_answer_of_only_control_tokens_is_a_clean_502(self):
        self.fake({"text": "<|eot|>", "variants": []})
        with self.assertRaises(Unavailable):
            run(self.writer.rewrite(self.ctx(), "да", "friends"))


# ---- the app's chat ---------------------------------------------------------------------------------------

class Chat(WriterTestCase):
    def test_revision_adds_a_preference(self):
        spark = self.fake({"text": "ок, опоздаю", "rule": "Keep replies to friends short, no apologies"})
        out = run(self.writer.chat(self.ctx(), "write", "скажи что опоздаю", "friends", "message",
                                   [{"answer": "Привет! Извини, я опоздаю минут на 20", "feedback": "короче"}]))
        self.assertEqual(out["text"], "ок, опоздаю")
        self.assertEqual(out["learned"], "Keep replies to friends short, no apologies")
        self.assertEqual(styles.preferences(STYLE), ["Keep replies to friends short, no apologies"])
        self.assertGreaterEqual(self.commits, 1)
        self.assertIn("The user's feedback so far:\n- короче", spark.users()[0])
        # the next request sees the rule (version() changed, the context is rebuilt)
        self.assertIn("Keep replies to friends short", self.ctx().style_text)
        self.assertIn("Keep replies to friends short", self.ctx().read_system)

    def test_revision_with_all_feedback_so_far(self):
        spark = self.fake({"text": "го", "rule": ""})
        history = [{"answer": "a1", "feedback": "короче"}, {"answer": "a2", "feedback": "без смайликов"}]
        out = run(self.writer.chat(self.ctx(), "rewrite", "Пойдём?", "friends", "message", history))
        self.assertIsNone(out["learned"])
        self.assertEqual(styles.preferences(STYLE), [])
        self.assertIn("- короче\n- без смайликов", spark.users()[0])
        self.assertIn("Your last answer:\na2", spark.users()[0])

    def test_rule_is_cleaned_and_deduplicated(self):
        self.fake({"text": "го", "rule": "  No emoji <|eot|> with family.  "})
        for _ in range(2):
            run(self.writer.chat(self.ctx(), "write", "x", "family", "message", [{"answer": "a", "feedback": "f"}]))
        self.assertEqual(styles.preferences(STYLE), ["No emoji with family"])

    def test_preferences_are_capped(self):
        for i in range(styles.MAX_PREFERENCES + 3):
            styles.add_preference(STYLE, f"rule number {i}")
        kept = styles.preferences(STYLE)
        self.assertEqual(len(kept), styles.MAX_PREFERENCES)
        self.assertEqual(kept[-1], f"rule number {styles.MAX_PREFERENCES + 2}")

    def test_write_mode_returns_up_to_two_alternatives(self):
        self.fake({"text": "го", "variants": ["давай", "ок", "го", "ладно"]})
        out = run(self.writer.chat(self.ctx(), "write", "согласись", "friends"))
        self.assertEqual(out["text"], "го")
        self.assertEqual(out["alternatives"], ["давай", "ок"])
        self.assertIsNone(out["learned"])

    def test_reply_mode_reads_and_returns_spark_drafts_when_gpu_is_off(self):
        self.fake({"summary": "asks if the user is coming to the cinema at 8", "situation": "invitation",
                   "audience": "friends", "audiences": ["friends", "partner"],
                   "options": [{"act": "agree", "draft": "го"}, {"act": "refuse", "draft": "не, я пас"},
                               {"act": "joke", "draft": "только если ты платишь"}]})
        out = run(self.writer.chat(self.ctx(), "reply", "- идешь в кино в 8?", "friends"))
        self.assertEqual(out["text"], "го")
        self.assertEqual(out["alternatives"], ["не, я пас", "только если ты платишь"])


# ---- learning: /feedback and /learn ----------------------------------------------------------------------

class Learning(WriterTestCase):
    def test_liked_answer_becomes_an_example_without_a_spark_call(self):
        spark = self.fake({})
        out = run(self.writer.feedback(self.ctx(), "friends", "message", "го в 8", liked=True))
        self.assertEqual(out, {"learned": None})
        self.assertEqual(spark.calls, [])
        self.assertEqual([(f["text"], f["kind"]) for f in styles.feedback(STYLE)], [("го в 8", "liked")])
        self.assertEqual(self.ctx().sample("friends")[0], "го в 8")

    def test_edit_is_stored_and_may_teach_a_rule(self):
        spark = self.fake({"rule": "Write 'ок' instead of 'хорошо'"})
        out = run(self.writer.feedback(self.ctx(), "family", "message", "Хорошо, мама", edited="ок мам"))
        self.assertEqual(out["learned"], "Write 'ок' instead of 'хорошо'")
        self.assertEqual(styles.feedback(STYLE)[-1]["kind"], "edited")
        self.assertIn("Suggested: Хорошо, мама\nThe user's version: ок мам", spark.users()[0])

    def test_unknown_audience_or_empty_text_is_ignored(self):
        self.fake({})
        run(self.writer.feedback(self.ctx(), "boss", "message", "текст"))
        run(self.writer.feedback(self.ctx(), "friends", "message", "<|eot|>"))
        self.assertEqual(styles.feedback(STYLE), [])

    def test_feedback_is_scrubbed_like_learn(self):
        self.fake({})
        run(self.writer.feedback(self.ctx(), "friends", "message", "звони +7 701 123 45 67 или https://x.example/a",
                                 liked=True))
        stored = styles.feedback(STYLE)[-1]["text"]
        self.assertNotIn("701", stored)
        self.assertNotIn("https://", stored)

    def test_learn_scrubs_and_skips(self):
        spark = self.fake({})
        out = run(self.writer.learn(self.ctx(), [
            {"audience": "friends", "text": "пиши на a.b@mail.example или +7 701 123 45 67"},
            {"audience": "friends", "text": "карта 4111 1111 1111 1111 ок"},
            {"audience": "friends", "text": "def f():\n    return 1"},  # pasted code
            {"audience": "friends", "text": "х" * 1001},  # too long for a chat message
            {"audience": "friends", "text": "<|eot|>"},
            {"audience": "colleague", "text": "ок"},
        ]))
        self.assertEqual(out, {"learned": 2, "rules": []})
        texts = [r["text"] for r in styles.learned(STYLE)]
        self.assertEqual(texts, ["пиши на или", "карта ок"])
        self.assertTrue(all(r["kind"] == "typed" and r["id"] and r["at"] for r in styles.learned(STYLE)))
        self.assertEqual(spark.calls, [])
        self.assertGreaterEqual(self.commits, 1)

    def test_changed_suggestion_teaches_at_most_two_rules(self):
        spark = self.fake({"rule": "Drop the final period"})
        items = [{"audience": "friends", "text": f"ок {i}", "suggested": f"Хорошо {i}."} for i in range(4)]
        out = run(self.writer.learn(self.ctx(), items))
        self.assertEqual(out["learned"], 4)
        self.assertEqual(len(spark.calls), 2)
        self.assertEqual(out["rules"], ["Drop the final period"] * 2)
        self.assertEqual(styles.preferences(STYLE), ["Drop the final period"])
        self.assertEqual({r["kind"] for r in styles.learned(STYLE)}, {"edited"})

    def test_spark_down_still_keeps_the_message(self):
        self.fake(lambda *a: Unavailable(502, "down"))
        out = run(self.writer.learn(self.ctx(), [{"audience": "friends", "text": "го", "suggested": "Пойдём"}]))
        self.assertEqual(out, {"learned": 1, "rules": []})

    def test_learned_messages_become_examples_at_once(self):
        self.fake({})
        run(self.writer.learn(self.ctx(), [{"audience": "family", "text": "мам я дома"}]))
        self.assertEqual(self.ctx().sample("family")[0], "мам я дома")

    def test_no_rule_call_when_only_a_link_was_scrubbed(self):
        spark = self.fake({"rule": "Never send links"})
        run(self.writer.learn(self.ctx(), [{"audience": "friends", "text": "смотри https://x.example",
                                            "suggested": "смотри https://x.example"}]))
        self.assertEqual(spark.calls, [])

    def test_remove_learned(self):
        self.fake({})
        run(self.writer.learn(self.ctx(), [{"audience": "friends", "text": "а"}, {"audience": "friends", "text": "б"}]))
        first = styles.learned(STYLE)[0]["id"]
        styles.remove_learned(STYLE, first)
        self.assertEqual([r["text"] for r in styles.learned(STYLE)], ["б"])

    def test_a_torn_jsonl_line_does_not_break_the_style(self):
        path = styles.folder(STYLE) / "learned.jsonl"
        path.write_text(json.dumps({"audience": "friends", "text": "го", "id": "a"}) + "\n{\"audience\": \"fri",
                        encoding="utf-8")
        ctx = self.ctx()  # raises json.JSONDecodeError today
        self.assertIn("го", ctx.sample("friends"))


# ---- read(): what Muse Spark says about the chat ------------------------------------------------------------

class Read(WriterTestCase):
    def test_label_is_validated(self):
        summary = "asks <|eot|> whether " + " ".join(["word"] * 80)
        self.fake({"summary": summary, "situation": "world_domination", "audience": "boss", "chat_name": "  MIRA ",
                   "options": [{"act": "agree", "draft": "го\nв 8"}, {"act": "agree", "draft": "дубль"},
                               {"act": "hack", "draft": "x"}, {"act": "refuse", "draft": 5},
                               {"act": "joke", "draft": "<|eot|>"}, "nonsense",
                               {"act": "refuse", "draft": "не могу"}, {"act": "joke", "draft": "ахах"},
                               {"act": "tease", "draft": "четвертый"}]})
        context, options = run(self.writer.read(self.ctx(), messages="- придешь?"))
        self.assertNotIn("<|", context["summary"])
        self.assertEqual(len(context["summary"].split()), writer.SUMMARY_WORDS)
        self.assertEqual(context["situation"], "other")
        self.assertEqual(context["audience"], "partner")  # the chat title maps to the confirmed audience
        self.assertEqual(context["audiences"][0], "partner")
        self.assertEqual(options, [{"act": "agree", "draft": "го в 8"}, {"act": "refuse", "draft": "не могу"},
                                   {"act": "joke", "draft": "ахах"}])

    def test_user_choice_beats_the_title_and_the_guess(self):
        self.fake({"summary": "s", "audience": "family", "chat_name": "Mira", "options": []})
        context, options = run(self.writer.read(self.ctx(), messages="x", audience="elder_informal"))
        self.assertEqual(context["audience"], "elder_informal")
        self.assertEqual(options, [])

    def test_options_of_the_wrong_type_are_ignored(self):
        for bad in ({"act": "agree", "draft": "го"}, "го", None):
            self.fake({"summary": "s", "options": bad})
            _, options = run(self.writer.read(self.ctx(), messages="x"))
            self.assertEqual(options, [], bad)

    def test_options_as_a_number_are_ignored(self):
        self.fake({"summary": "s", "options": 3})
        _, options = run(self.writer.read(self.ctx(), messages="x"))
        self.assertEqual(options, [])

    def test_series_drafts_keep_their_lines(self):
        self.fake({"summary": "s", "options": [{"act": "agree", "draft": "го\nв 8"}]})
        _, options = run(self.writer.read(self.ctx(), messages="x", format="series"))
        self.assertEqual(options[0]["draft"], "го\nв 8")

    def test_note_and_screenshot_go_into_the_request(self):
        spark = self.fake({"summary": "s"})
        run(self.writer.read(self.ctx(), image=b"\x89PNG", image_type="image/png", instruction="откажи <|eot|>"))
        content = spark.calls[0]["user"]
        self.assertIn('"откажи"', content[0]["text"])
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_no_drafts_for_a_new_style_is_a_502_not_a_hang(self):
        with self.assertRaises(Unavailable) as caught:
            run(self.writer.reply(self.ctx(), "s", "friends", "other", options=[]))
        self.assertEqual(caught.exception.status, 502)

    def test_reply_without_gpu_returns_drafts_with_the_users_tone(self):
        replies = run(self.writer.reply(self.ctx(), "s", "friends", "invitation",
                                        [{"act": "agree", "draft": "го\nв 8"}], "series"))
        self.assertEqual(replies[0]["parts"], ["го", "в 8"])
        self.assertEqual(replies[0]["tone"], "playful")
        self.assertFalse(replies[0]["styled"])


class RealSparkParsing(WriterTestCase):
    """The real Writer.spark against a fake HTTP client: bad JSON, prose around JSON, HTTP errors."""

    def setUp(self):
        super().setUp()
        self.saved_sleep = writer.asyncio.sleep

        async def no_sleep(_):
            return None
        writer.asyncio.sleep = no_sleep

    def tearDown(self):
        writer.asyncio.sleep = self.saved_sleep
        super().tearDown()

    def test_bad_json_is_a_502_after_one_retry(self):
        self.writer.client = FakeClient('{"summary": "unterminated')
        with self.assertRaises(Unavailable) as caught:
            run(self.writer.read(self.ctx(), messages="x"))
        self.assertEqual(caught.exception.status, 502)
        self.assertEqual(len(self.writer.client.posts), 2)

    def test_prose_around_json_is_parsed(self):
        self.writer.client = FakeClient('Sure! {"summary": "asks about 8pm", "situation": "invitation"} Hope it helps')
        context, _ = run(self.writer.read(self.ctx(), messages="x"))
        self.assertEqual(context["situation"], "invitation")

    def test_retry_recovers(self):
        self.writer.client = FakeClient("no json at all", '{"summary": "ok"}')
        context, _ = run(self.writer.read(self.ctx(), messages="x"))
        self.assertEqual(context["summary"], "ok")

    def test_http_error_is_a_502(self):
        self.writer.client = FakeClient('{"summary": "x"}', status=429)
        with self.assertRaises(Unavailable):
            run(self.writer.read(self.ctx(), messages="x"))

    def test_json_that_is_not_an_object_is_a_502(self):
        self.writer.client = FakeClient('["summary"]')
        with self.assertRaises(Unavailable):
            run(self.writer.read(self.ctx(), messages="x"))

    def test_empty_rule_is_a_valid_answer(self):
        self.writer.client = FakeClient('{"rule": ""}')
        out = run(self.writer.feedback(self.ctx(), "friends", "message", "Хорошо", edited="ок"))
        self.assertEqual(out, {"learned": None})

    def test_key_and_model_are_sent(self):
        self.writer.meta_key = "test-key"
        self.writer.client = FakeClient('{"summary": "x"}')
        run(self.writer.read(self.ctx(), messages="x"))
        url, kwargs = self.writer.client.posts[0]
        self.assertEqual(url, writer.META_URL)
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer test-key"})
        self.assertEqual(kwargs["json"]["model"], "muse-spark-1.3")


class Helpers(unittest.TestCase):
    def test_shape_is_idempotent(self):
        for format in writer.FORMATS:
            for text in ("а\nб\nв", "один", "x\n\n y \n", "a\nb\nc\nd\ne\nf"):
                once = writer.shape(text, format)[0]
                self.assertEqual(writer.shape(once, format)[0], once, (format, text))

    def test_series_of_one_line_is_one_part(self):
        self.assertEqual(writer.shape("го", "series"), ("го", ["го"]))

    def test_clip_keeps_lines(self):
        self.assertEqual(writer.clip("a b\nc d e\nf", 4), "a b\nc d")
        self.assertEqual(writer.clip("a b", 0), "")

    def test_capitalize(self):
        self.assertEqual(writer.capitalize("да. ок! ну? и"), "Да. Ок! Ну? И")

    def test_audiences_of(self):
        self.assertEqual(writer.audiences_of({"audiences": ["x", "family"]}, "partner"), ["partner", "family", "friends"])
        self.assertEqual(writer.audiences_of("not a dict"), ["partner", "friends", "family"])

    def test_read_json_bad_file_is_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            path.write_text("{bad", encoding="utf-8")
            self.assertEqual(styles.read_json(path, []), [])

    def test_style_ids_are_checked(self):
        for bad in ("../main", "", "A", "x" * 17, "a/b", None):
            with self.assertRaises(KeyError):
                styles.folder(bad)

    def test_control_regex(self):
        self.assertEqual(writer.clean("a<|eot|>b<|start|>"), "ab")
        self.assertTrue(re.search(writer.CONTROL, "<|message|>"))


if __name__ == "__main__":
    unittest.main()
