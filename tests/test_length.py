"""serving/length.py: essays reach the asked length. Under 90 % of the target → "expand to N words" (at most two
passes), over 115 % → one trim pass; the text closest to the ±10 % range is kept. A fake Muse Spark; no network.

Usage: python3 -m pytest tests/test_length.py
"""

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving")]

import length  # noqa: E402


def essay(n):
    return " ".join(f"w{i}" for i in range(n))


class Spark:
    """Answers each pass with the next essay length in the script (the last one repeats)."""

    def __init__(self, *counts):
        self.counts, self.prompts = list(counts), []

    async def __call__(self, prompt):
        self.prompts.append(prompt)
        n = self.counts.pop(0) if len(self.counts) > 1 else self.counts[0]
        return {"text": essay(n)}


def fit(spark, start, words=200, **kwargs):
    return asyncio.run(length.fit(spark, essay(start), words, notes="мои заметки", **kwargs))


class Fit(unittest.TestCase):
    def test_within_range_no_call(self):
        for n in (180, 200, 230):  # 90 % … 115 %
            spark = Spark(1)
            text, passes = fit(spark, n)
            self.assertEqual((length.count(text), passes, spark.prompts), (n, 0, []), n)

    def test_short_is_expanded_until_in_range(self):
        spark = Spark(150, 195)
        text, passes = fit(spark, 100)
        self.assertEqual((length.count(text), passes), (195, 2))
        self.assertIn("This essay has 100 words; it must have about 200 words (between 180 and 220)", spark.prompts[0])
        self.assertIn("Expand it to about 200 words", spark.prompts[0])
        self.assertIn("The user's notes: мои заметки", spark.prompts[0])
        self.assertIn("Never invent experiences", spark.prompts[0])
        self.assertIn("This essay has 150 words", spark.prompts[1])

    def test_at_most_two_expand_passes(self):
        spark = Spark(120, 140, 160)
        text, passes = fit(spark, 100)
        self.assertEqual((length.count(text), passes), (140, 2))

    def test_expanded_too_far_is_trimmed_once(self):
        spark = Spark(270, 210)  # 270 is closer to the range than 100, so it is kept, then cut
        text, passes = fit(spark, 100)
        self.assertEqual((length.count(text), passes), (210, 2))
        self.assertIn("Cut it to about 200 words", spark.prompts[1])

    def test_long_is_trimmed_once(self):
        spark = Spark(260)
        text, passes = fit(spark, 300)
        self.assertEqual((length.count(text), passes), (260, 1))
        self.assertIn("This essay has 300 words", spark.prompts[0])

    def test_a_pass_that_makes_it_worse_is_not_kept(self):
        spark = Spark(60, 150)
        text, passes = fit(spark, 100)
        self.assertEqual(passes, 2)
        self.assertEqual(length.count(text), 150)
        self.assertIn("This essay has 100 words", spark.prompts[1])  # the second pass starts from the better text

    def test_other_problems_go_into_the_same_pass(self):
        spark = Spark(200)
        fit(spark, 100, problems_of=lambda t: ["remove phrases that sound AI-written: delve"])
        self.assertIn("Also remove phrases that sound AI-written: delve.", spark.prompts[0])

    def test_empty_answer_keeps_the_text(self):
        async def empty(_prompt):
            return {"text": " "}
        text, passes = fit(empty, 100)
        self.assertEqual((length.count(text), passes), (100, 2))

    def test_target_line(self):
        self.assertEqual(length.bounds(250), (225, 275))
        self.assertIn("about 250 words (allowed: 225 to 275 words, ±10%", length.target(250))


if __name__ == "__main__":
    unittest.main()
