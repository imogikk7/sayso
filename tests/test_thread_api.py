"""The API contract of the chat thread, guards and auto-series, through the real FastAPI app (serving/modal_app.py with
the fakes of tests/test_api_auth.py). No network, no GPU, made-up data only.

  previous            /compose, /rewrite, /reply, /chat take up to 3 {request, answer}, oldest first
  alternative_parts   every response with `alternatives` has it: parallel, each the parts of that alternative
  parts               may have more than one item with format "message" (auto-series)

Usage: python3 -m pytest tests/test_thread_api.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline"), str(ROOT / "eval"), str(ROOT / "tests")]

from test_api_auth import HAVE_FASTAPI, TOKEN, build_app  # noqa: E402

if HAVE_FASTAPI:
    from fastapi.testclient import TestClient

ENGLISH = "Hello,\n\nCould we move the consultation to Friday? I have an exam on Thursday.\n\nBest regards"
THREAD = [{"request": "email to my teacher: move the consultation to Friday, exam on Thursday", "answer": ENGLISH}]
LONG = ("Привет! Хотел сказать, что завтра не получится прийти на встречу, потому что у меня поменялись планы на работе. "
        "Может перенесём на четверг или пятницу? Мне оба дня подходят, только после шести. Напиши как тебе удобнее.")


class Spark:
    """Muse Spark for the app: a revision, a reading, or a chat answer whose variants are series."""

    def __init__(self):
        self.calls = []

    async def __call__(self, system, user, key, **kwargs):
        text = user if isinstance(user, str) else user[0]["text"]
        import memory
        self.calls.append({"system": system, "user": text, "key": key, "note": memory.NOTE.get()})
        if text.startswith("You already answered the user"):
            if "Hello," in text:  # the email of THREAD, in Russian, with what the guards must remove
                return {"subject": "Перенос консультации",
                        "text": "Уважаемая команда [Name],\n\nЯ — менеджер проектов в компании Альфа. Можно перенести "
                                "консультацию на пятницу? В четверг у меня экзамен.\n\nС уважением,\n[Your name]"}
            return {"text": "опоздаю на 20", "variants": ["буду через 20 [Name]", "+20 мин"]}
        if key == "summary":
            return {"summary": "asks about plans", "situation": "invitation", "audience": "friends",
                    "options": [{"act": "agree", "draft": "го [Name]"}, {"act": "refuse", "draft": "не могу"}]}
        return {"text": "привет\nзавтра никак\nдавай в чт или пт после 6",
                "variants": ["слушай\nзавтра не смогу", "завтра не получится, давай в чт", "Меня зовут Алекс. ок"]}


@unittest.skipUnless(HAVE_FASTAPI, "fastapi, httpx and python-multipart are not installed (see test_api_auth.py)")
class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import styles
        cls.tmp = tempfile.TemporaryDirectory()
        cls.saved_paths = styles.DATA, styles.STYLES, styles.on_write
        cls.saved_env = dict(os.environ)
        cls.web, cls.writer, cls.latest = build_app(cls.tmp.name)
        from test_series import SPLITTER, make_splitter
        from test_writer_fakes import make_style
        cls.style = make_style()
        make_splitter()
        cls.splitter = SPLITTER
        cls.client = TestClient(cls.web, raise_server_exceptions=False)
        cls.auth = {"Authorization": f"Bearer {TOKEN}"}

    @classmethod
    def tearDownClass(cls):
        import styles
        styles.DATA, styles.STYLES, styles.on_write = cls.saved_paths
        os.environ.clear()
        os.environ.update(cls.saved_env)
        cls.tmp.cleanup()

    def setUp(self):
        self.spark = self.writer.spark = Spark()

    def post(self, path, **body):
        response = self.client.post(path, headers=self.auth, json={"style": self.style, **body})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_chat_email_na_russkom_revises_the_last_email(self):
        out = self.post("/chat", mode="email", text="на русском", previous=THREAD)
        self.assertTrue(self.spark.calls[0]["user"].startswith("You already answered the user"))
        self.assertIn("Could we move the consultation to Friday?", self.spark.calls[0]["user"])
        self.assertEqual(out["text"], "Уважаемая команда,\n\nМожно перенести консультацию на пятницу? В четверг у меня "
                                      "экзамен.\n\nС уважением,")
        self.assertEqual(out["subject"], "Перенос консультации")
        self.assertEqual(out["parts"], [out["text"]])
        self.assertEqual((out["alternatives"], out["alternative_parts"]), ([], []))

    def test_chat_write_has_alternative_parts_parallel_to_alternatives(self):
        out = self.post("/chat", mode="write", text="скажи что завтра не смогу", format="series")
        self.assertEqual(len(out["alternative_parts"]), len(out["alternatives"]))
        self.assertEqual(out["alternative_parts"], [a.split("\n") for a in out["alternatives"]])
        self.assertNotIn("Меня зовут Алекс. ок", out["alternatives"])  # a variant that introduces the user: dropped

    def test_chat_message_refinement_with_previous(self):
        out = self.post("/chat", mode="write", text="короче",
                        previous=[{"request": "скажи что опоздаю", "answer": "я опоздаю минут на 20 сорри"}])
        self.assertEqual(out["text"], "опоздаю на 20")
        self.assertEqual(out["alternatives"], ["+20 мин"])  # the one with a placeholder is dropped
        self.assertEqual(out["alternative_parts"], [["+20 мин"]])

    def test_new_topic_with_previous_gets_the_note(self):
        self.post("/compose", instruction="напиши маме что буду в 9", audience="family", previous=THREAD)
        # set for the route's Spark calls (Writer.spark appends it; that path is tested in test_memory.py)
        self.assertIn("Earlier in this chat", self.spark.calls[0]["note"])
        self.assertIn("email to my teacher", self.spark.calls[0]["note"])

    def test_compose_and_rewrite_refinement(self):
        for path, field in (("/compose", "instruction"), ("/rewrite", "text")):
            self.spark.calls.clear()
            out = self.post(path, **{field: "shorter"}, previous=[{"request": "x", "answer": "я опоздаю минут на 20"}])
            self.assertEqual(out["text"], "опоздаю на 20", path)
            self.assertEqual(out["candidates"], ["опоздаю на 20", "+20 мин"], path)
            self.assertEqual(len(self.spark.calls), 1, path)

    def test_auto_series_for_a_long_message_when_the_user_writes_like_that(self):
        response = self.client.post("/rewrite", headers=self.auth, json={
            "style": self.splitter, "text": LONG, "audience": "friends", "format": "message"})
        out = response.json()
        self.assertIn("2 to 5 separate short chat messages", self.spark.calls[0]["user"])
        self.assertEqual(out["parts"], ["привет", "завтра никак", "давай в чт или пт после 6"])
        chat = self.client.post("/chat", headers=self.auth, json={
            "style": self.splitter, "mode": "rewrite", "text": LONG, "audience": "friends"}).json()
        self.assertEqual(len(chat["parts"]), 3)
        self.assertEqual(chat["alternative_parts"][0], ["слушай", "завтра не смогу"])

    def test_official_and_email_never_auto_split(self):
        for format in ("official", "email"):
            self.spark.calls.clear()
            out = self.client.post("/rewrite", headers=self.auth, json={
                "style": self.splitter, "text": LONG, "audience": "friends", "format": format}).json()
            self.assertEqual(len(out["parts"]), 1, format)
            self.assertNotIn("2 to 5 separate", self.spark.calls[0]["user"], format)

    def test_auto_is_not_a_format_the_app_can_ask_for(self):
        self.post("/compose", instruction="скажи что опоздаю", format="auto")
        self.assertIn("as ONE chat message", self.spark.calls[0]["user"])

    def test_at_most_three_previous(self):
        response = self.client.post("/chat", headers=self.auth, json={
            "style": self.style, "mode": "write", "text": "x", "previous": THREAD * 4})
        self.assertEqual(response.status_code, 422)

    def test_reply_is_guarded_and_takes_previous(self):
        out = self.post("/reply", messages="го в 8?", previous=THREAD)
        self.assertEqual([r["text"] for r in out["replies"]], ["го", "не могу"])
        self.assertEqual(out["options"][0]["draft"], "го")
        self.assertIn("Earlier in this chat", self.spark.calls[0]["note"])

    def test_reply_refinement_without_a_new_chat(self):
        out = self.post("/reply", instruction="shorter",
                        previous=[{"request": "го в 8?", "answer": "я опоздаю минут на 20"}])
        # each reply is an answer of its own: fixed (the placeholder removed), not dropped
        self.assertEqual([r["text"] for r in out["replies"]], ["опоздаю на 20", "буду через 20", "+20 мин"])
        self.assertEqual(out["replies"][0]["intent"], "other")


if __name__ == "__main__":
    unittest.main()
