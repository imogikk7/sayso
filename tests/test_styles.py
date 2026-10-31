"""Building a style from a made-up WhatsApp chat with a fake Muse Spark: stages, files, and privacy
(none of the other person's lines may be written), plus the writer's context for the new style.

Usage: python3 -m unittest tests/test_styles.py
"""

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

FIXTURE = ROOT / "tests" / "fixtures" / "whatsapp_fake.txt"


def fake_spark(system, user, key):
    if system == build_style.AUDIENCE_SYSTEM:
        return {"audience": "friends"}
    if system == build_style.TAG_SYSTEM:
        count = len(re.findall(r"^\d+\. ", user, re.M))
        return {"items": [{"i": i, "situation": "invitation", "summary": "asks about plans for the evening",
                           "act": "agree", "tone": "playful", "gist": "agrees and asks the time",
                           "draft": "Да, давай. Во сколько?", "instruction": "согласись и спроси время"}
                          for i in range(count)]}
    return {}


class BuildStyle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = styles.DATA, styles.STYLES
        styles.DATA = Path(self.tmp.name)
        styles.STYLES = styles.DATA / "styles"
        self.saved_check = build_style.self_check
        build_style.self_check = lambda *a: {"sounds_like_you": 0.8, "generic": 0.4, "makes_sense": 4.5, "checked": 3,
                                             "samples": []}
        self.stages = []

    def tearDown(self):
        styles.DATA, styles.STYLES = self.saved
        build_style.self_check = self.saved_check
        self.tmp.cleanup()

    def build(self, me="Алекс"):
        meta = styles.create("Test")

        def wait_for_me(current):
            self.stages.append(current["stage"])
            self.assertIn("Алекс", current["participants"])
            self.assertEqual(current["needs"], ["me", "chats"])
            return styles.update(meta["id"], me=me, chats=current["chats"], confirmed=True)

        build_style.build(meta["id"], [("WhatsApp Chat - Mira.txt", FIXTURE.read_bytes())], fake_spark, "",
                          wait_for_me, commit=lambda: self.stages.append(styles.meta(meta["id"])["stage"]))
        return meta["id"]

    def test_stages_and_files(self):
        style_id = self.build()
        meta = styles.meta(style_id)
        self.assertEqual(meta["status"], "ready", meta.get("error"))
        self.assertEqual(meta["lora"], "needs more messages")
        for stage in ("parsing", "needs_me", "reading", "profile", "checking", "ready"):
            self.assertIn(stage, self.stages)
        folder = styles.folder(style_id)
        for name in ("turns.jsonl", "profile.json", "pairs/train.jsonl", "pairs/test.jsonl"):
            self.assertTrue((folder / name).exists(), name)
        self.assertIn("friends", styles.read_json(folder / "profile.json"))

    def test_no_incoming_text_written(self):
        style_id = self.build()
        incoming = [line.split("Мира: ", 1)[1] for line in FIXTURE.read_text().splitlines() if "Мира: " in line]
        for path in styles.folder(style_id).rglob("*"):
            if path.is_file():
                content = path.read_text(encoding="utf-8")
                self.assertEqual([s for s in incoming if s in content], [], path.name)
                self.assertNotIn("context", content, path.name)

    def test_context_for_new_style(self):
        style_id = self.build()
        ctx = writer.Context(style_id)
        self.assertIsNone(ctx.adapter)  # no LoRA yet: Muse Spark writes in this style
        examples = ctx.sample("friends")
        self.assertTrue(examples)
        own = FIXTURE.read_text()
        self.assertTrue(all(e.split("\n")[0] in own for e in examples))
        self.assertIn("Some of their real messages", ctx.read_system)

    def test_preferences_and_feedback(self):
        style_id = self.build()
        styles.add_preference(style_id, "Keep replies short")
        styles.add_preference(style_id, "keep replies short")
        self.assertEqual(styles.preferences(style_id), ["Keep replies short"])
        styles.add_feedback(style_id, {"audience": "friends", "format": "message", "text": "го в 8", "kind": "edited"})
        ctx = writer.Context(style_id)
        self.assertIn("Keep replies short", ctx.style_text)
        self.assertEqual(ctx.sample("friends")[0], "го в 8")

    def test_unknown_me_fails_cleanly(self):
        style_id = self.build(me="Nobody")
        self.assertEqual(styles.meta(style_id)["status"], "failed")


class Helpers(unittest.TestCase):
    def test_merge_frames(self):
        a = [{"side": "them", "text": "привет"}, {"side": "me", "text": "го"}, {"side": "them", "text": "в 8?"}]
        b = [{"side": "me", "text": "го"}, {"side": "them", "text": "в 8?"}, {"side": "me", "text": "да"}]
        merged = build_style.merge_frames([a, b])
        self.assertEqual([m["text"] for m in merged], ["привет", "го", "в 8?", "да"])

    def test_shape_formats(self):
        self.assertEqual(writer.shape("го\nв 8"), ("го в 8", ["го в 8"]))
        self.assertEqual(writer.shape("го\nв 8", "series"), ("го\nв 8", ["го", "в 8"]))
        self.assertEqual(writer.shape("Здравствуйте\nТекст\nСпасибо", "email")[0], "Здравствуйте\n\nТекст\n\nСпасибо")
        self.assertEqual(writer.clip("a b c\nd e", 4), "a b c\nd")

    def test_prompts(self):
        self.assertNotEqual(writer.REVISE_SYSTEM, writer.STYLE_SYSTEM)
        writer.REVISE_SYSTEM.format(style="x")
        writer.STYLE_SYSTEM.format(style="x")

    def test_similarity(self):
        self.assertEqual(build_style.similarity(["го", "ок"], ["го", "ок"]), 1.0)
        self.assertLess(build_style.similarity(["Здравствуйте, я хотел бы уточнить время встречи."], ["го"]), 0.7)


if __name__ == "__main__":
    unittest.main()
