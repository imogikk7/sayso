"""serving/series.py: auto-series. A long "message" to an audience the user writes to in several short messages comes
as 2 to 5 parts; "series" always splits; "official" and "email" never do. Made-up turns only; no network.

Usage: python3 -m pytest tests/test_series.py
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline"), str(ROOT / "eval"), str(ROOT / "tests")]

import build_style  # noqa: E402
import postprocess  # noqa: E402
import series  # noqa: E402
import styles  # noqa: E402
import writer  # noqa: E402
from test_writer_fakes import FakeSpark, WriterTestCase, run  # noqa: E402

SPLITTER = "split01"
# To friends this made-up user sends a thought as several quick messages; to family, one message.
FRIENDS = ["го в 8\nя за", "ахах\nжиза\nору", "ну давай\nпосле пар", "щас\nподойду", "ок буду", "ору\nну ты даешь",
           "сорри\nопоздаю\nпробки"]
FAMILY = ["хорошо мам, скоро буду", "да, куплю хлеб", "ок, позвоню вечером", "буду в 9", "да, всё хорошо"]
LONG = ("Привет! Хотел сказать, что завтра не получится прийти на встречу, потому что у меня поменялись планы на работе. "
        "Может перенесём на четверг или пятницу? Мне оба дня подходят, только после шести. Напиши как тебе удобнее.")


def make_splitter():
    turns = ([{"audience": "friends", "situation": "other", "act": "react", "tone": "playful", "text": t} for t in FRIENDS]
             + [{"audience": "family", "situation": "other", "act": "agree", "tone": "caring", "text": t} for t in FAMILY])
    turns = [{**t, "split": "train", "context": []} for t in turns]
    styles.save_meta(SPLITTER, {"id": SPLITTER, "name": "Splitter", "status": "ready", "stage": "ready", "created": 1})
    styles.write_jsonl(styles.folder(SPLITTER) / "turns.jsonl", [{k: t[k] for k in (
        "audience", "situation", "act", "tone", "text", "split")} for t in turns])
    styles.write_json(styles.folder(SPLITTER) / "profile.json", build_style.profile_of(turns))


class Choose(WriterTestCase):
    def setUp(self):
        super().setUp()
        make_splitter()
        self.split = self.writer.context(SPLITTER)

    def test_habit_from_the_users_own_turns(self):
        h = series.habit(self.split, "friends")
        self.assertEqual(h["turns"], len(FRIENDS))
        self.assertAlmostEqual(h["splits"], 6 / 7)
        self.assertEqual(series.habit(self.split, "family")["splits"], 0)
        self.assertEqual(series.habit(self.split, "partner")["turns"], 0)

    def test_long_message_to_an_audience_they_split_for_is_auto(self):
        self.assertEqual(series.choose(self.split, "friends", LONG, "message"), series.AUTO)

    def test_short_content_or_no_habit_stays_one_message(self):
        self.assertEqual(series.choose(self.split, "friends", "го в 8?", "message"), "message")
        self.assertEqual(series.choose(self.split, "family", LONG, "message"), "message")
        self.assertEqual(series.choose(self.ctx(), "friends", LONG, "message"), "message")  # the fake style: one-liners

    def test_other_formats_are_never_changed(self):
        for format in ("series", "official", "email", "essay"):
            self.assertEqual(series.choose(self.split, "friends", LONG, format), format)

    def test_the_prompt_lets_the_model_decide_and_lines_become_parts(self):
        spark = self.writer.spark = FakeSpark({
            "text": "привет\nзавтра не получится, планы на работе поменялись\nможет в чт или пт?\nпосле шести\nнапиши как удобнее\nок?",
            "variants": ["слушай завтра никак\nдавай чт или пт после 6", "завтра не смогу, давай в чт или пт после 6"]})
        out = run(self.writer.rewrite(self.split, LONG, "friends", "other", series.AUTO))
        self.assertIn("2 to 5 separate short chat messages", spark.calls[0]["user"])
        self.assertEqual(len(out["parts"]), 5)  # six lines merged into five, nothing lost
        self.assertEqual(" ".join(out["parts"]).split(), out["text"].split())
        self.assertIn("ок?", out["text"])
        result = {"text": out["text"], "parts": out["parts"], "alternatives": out["candidates"][1:]}
        postprocess.finish(result, LONG, series.AUTO)
        self.assertEqual(result["alternative_parts"], [["слушай завтра никак", "давай чт или пт после 6"],
                                                       ["завтра не смогу, давай в чт или пт после 6"]])

    def test_a_long_rewrite_is_not_clipped_to_one_messages_length(self):
        long_answer = "\n".join(["слово " * 15] * 4)
        self.writer.spark = FakeSpark({"text": long_answer, "variants": []})
        out = run(self.writer.rewrite(self.split, LONG, "friends", "other", series.AUTO))
        self.assertEqual(len(out["text"].split()), 60)


class Parts(unittest.TestCase):
    def test_explicit_series_of_one_line_is_split_into_sentences(self):
        text, parts = writer.shape("Завтра не смогу. Давай в четверг? После шести норм", "series")
        self.assertEqual(parts, ["Завтра не смогу.", "Давай в четверг?", "После шести норм"])
        self.assertEqual(text, "\n".join(parts))

    def test_one_long_sentence_is_split_at_clauses(self):
        parts = series.parts_of("слушай завтра никак не получится, давай перенесём на четверг или пятницу после шести",
                                "series")
        self.assertEqual(parts, ["слушай завтра никак не получится,", "давай перенесём на четверг или пятницу после шести"])

    def test_auto_one_line_stays_one_message(self):
        self.assertEqual(writer.shape("ок буду в 8", series.AUTO), ("ок буду в 8", ["ок буду в 8"]))
        self.assertEqual(series.parts_of("ок буду в 8", series.AUTO), ["ок буду в 8"])

    def test_cap_merges_neighbours_and_keeps_every_word(self):
        lines = ["a", "bb", "c", "dddd", "e", "ff", "g"]
        capped = series.cap(lines, 5)
        self.assertEqual(len(capped), 5)
        self.assertEqual(" ".join(capped).split(), lines)

    def test_formal_and_message_formats_are_one_part(self):
        for format in ("message", "official", "email", "essay"):
            self.assertEqual(series.parts_of("a\nb", format), ["a\nb"])

    def test_shape_is_idempotent_for_auto(self):
        for text in ("а\nб\nв", "один", "a\nb\nc\nd\ne\nf\ng"):
            once = writer.shape(text, series.AUTO)[0]
            self.assertEqual(writer.shape(once, series.AUTO)[0], once)


if __name__ == "__main__":
    unittest.main()
