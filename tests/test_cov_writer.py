"""serving/writer.py, the parts the first suites left untested: Writer.email and Writer.essay (the cliché fix pass,
the word limit, questions, the first-person rule), Context.formal_block per kind, Writer.read_page and
Writer.transcribe on a fake HTTP client. No GPU, no network, no private data (made-up texts only).

Tests marked @unittest.expectedFailure pin bugs (ids TEST-n, see docs/reviews/tests.md): they pass while the bug is
there; drop the decorator once it's fixed.

Usage: .venv/bin/python -m pytest tests/test_cov_writer.py
"""

import base64
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline"), str(ROOT / "eval"), str(ROOT / "tests")]

import documents  # noqa: E402
import styles  # noqa: E402
import writer  # noqa: E402
from test_writer_fakes import STYLE, FakeClient, FakeResponse, WriterTestCase, run  # noqa: E402
from writer import Unavailable  # noqa: E402

# Made-up formal writing (nobody's real documents).
ESSAY_DOC = ("Моя курсовая работа посвящена истории степных государств и их системам наследования власти.\n\n"
             "Кроме того, я изучил источники о том, как правители делили власть между своими сыновьями.\n\n"
             "Поэтому я считаю, что эта система была гибкой, но нестабильной для всего государства.")
EMAIL_DOC = ("Здравствуйте, Иван Петрович!\n\n"
             "Прошу перенести консультацию на пятницу, в четверг у меня экзамен по физике.\n\n"
             "Заранее спасибо за понимание и за вашу помощь с моей курсовой работой.\n\n"
             "С уважением")


class Spark:
    """Stands in for Writer.spark and records every call with its keyword arguments; answers in turn (the last one
    repeats). An Exception in the script is raised."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    async def __call__(self, system, user, key, **kwargs):
        self.calls.append({"system": system, "user": user, "key": key, **kwargs})
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return dict(answer)


class Base(WriterTestCase):
    def use(self, *answers):
        self.writer.spark = Spark(*answers)
        return self.writer.spark

    def add_docs(self):
        styles.add_documents(STYLE, [("essay.txt", ESSAY_DOC)], kind="essay")
        styles.add_documents(STYLE, [("mail.txt", EMAIL_DOC)], kind="email")


# ---- email ---------------------------------------------------------------------------------------------------

class Email(Base):
    ANSWER = {"subject": "Перенос консультации",
              "text": "здравствуйте, Иван Петрович!\nпрошу перенести консультацию на пятницу.\nС уважением"}

    def test_one_call_formal_voice_and_paragraphs(self):
        spark = self.use(self.ANSWER)
        out = run(self.writer.email(self.ctx(), "перенести консультацию на пятницу"))
        self.assertEqual(len(spark.calls), 1)
        call = spark.calls[0]
        self.assertEqual(call["key"], "text")
        self.assertTrue(call["writes"])
        self.assertIn("перенести консультацию на пятницу", call["user"])
        self.assertIn("hasn't added formal writing yet", call["system"])  # no documents: the plain-voice fallback
        self.assertNotIn("Return JSON only", call["system"].split("Write an email")[0])
        self.assertEqual(out["text"], "Здравствуйте, Иван Петрович!\n\nПрошу перенести консультацию на пятницу.\n\n"
                                      "С уважением")
        self.assertEqual(out["parts"], [out["text"]])
        self.assertEqual(out["subject"], "Перенос консультации")
        self.assertEqual((out["audience"], out["learned"], out["alternatives"]), ("elder_informal", None, []))

    def test_reply_to_goes_into_the_prompt(self):
        spark = self.use(self.ANSWER)
        run(self.writer.email(self.ctx(), "согласен", reply_to="Can we move the meeting to Friday?"))
        user = spark.calls[0]["user"]
        self.assertIn("answering this email:\nCan we move the meeting to Friday?", user)
        self.assertIn("(or of the email being answered)", user)
        spark = self.use(self.ANSWER)
        run(self.writer.email(self.ctx(), "согласен", reply_to="   "))
        self.assertNotIn("answering this email", spark.calls[0]["user"])

    def test_documents_and_rules_shape_the_voice(self):
        self.add_docs()
        styles.add_preference(STYLE, "Never use exclamation marks")
        spark = self.use(self.ANSWER)
        run(self.writer.email(self.ctx(), "консультация в пятницу"))
        system = spark.calls[0]["system"]
        self.assertIn("how they greet, ask and sign off", system)  # the email rules of formal_block
        self.assertIn("Never use exclamation marks", system)
        self.assertNotIn("hasn't added formal writing yet", system)

    def test_control_tokens_never_reach_the_prompt_or_the_answer(self):
        spark = self.use({"subject": "<|eot|>Тема", "text": "Здравствуйте<|eom|>\nТекст письма."})
        out = run(self.writer.email(self.ctx(), "перенос<|start|> встречи"))
        self.assertNotIn("<|", spark.calls[0]["user"])
        self.assertNotIn("<|", out["text"] + out["subject"])

    def test_cliche_is_fixed_once(self):
        cliche = {"subject": "Перенос", "text": "Здравствуйте!\nВ современном мире всё меняется, прошу перенести "
                                                "консультацию.\nС уважением"}
        fixed = {"text": "Здравствуйте!\nПрошу перенести консультацию на пятницу.\nС уважением"}
        spark = self.use(cliche, fixed)
        out = run(self.writer.email(self.ctx(), "перенести консультацию"))
        self.assertEqual(len(spark.calls), 2)
        self.assertTrue(spark.calls[1]["user"].startswith("Fix this essay: remove phrases that sound AI-written: "
                                                          "В современном мире"))
        self.assertNotIn("современном мире", out["text"])
        self.assertIn("\n\nПрошу перенести", out["text"])

    def test_subject_survives_the_cliche_fix(self):
        self.use({"subject": "Перенос", "text": "Здравствуйте!\nВ наше время прошу перенести консультацию."},
                 {"text": "Здравствуйте!\nПрошу перенести консультацию."})
        self.assertEqual(run(self.writer.email(self.ctx(), "перенос"))["subject"], "Перенос")

    def test_long_email_is_clipped(self):
        self.use({"subject": "x", "text": " ".join(["слово"] * 1000)})
        out = run(self.writer.email(self.ctx(), "длинное письмо"))
        self.assertEqual(len(out["text"].split()), writer.FORMAT_WORDS["email"] * 2)

    def test_empty_subject_is_none(self):
        self.use({"text": "Здравствуйте.\nТекст."})
        self.assertIsNone(run(self.writer.email(self.ctx(), "x"))["subject"])

    def test_spark_down_is_a_502(self):
        self.use(Unavailable(502, "Muse Spark did not answer"))
        with self.assertRaises(Unavailable):
            run(self.writer.email(self.ctx(), "x"))


# ---- essay ---------------------------------------------------------------------------------------------------

def essay_text(n_words, extra=""):
    words = [f"слово{i}" for i in range(n_words)]
    return " ".join(words[:n_words // 2]) + "\n\n" + extra + " ".join(words[n_words // 2:])


class Essay(Base):
    def answer(self, text, **more):
        return {"outline": ["начало", "проект", "итог"], "text": text, "questions": ["Какой был результат?"], **more}

    def test_prompt_has_the_task_rules_and_first_person(self):
        spark = self.use(self.answer(essay_text(250)))
        out = run(self.writer.essay(self.ctx(), "Расскажите о своём проекте", "я сделал бота для заметок", 250))
        call = spark.calls[0]
        self.assertEqual(len(spark.calls), 1)  # within the limit, no cliché: no fix
        self.assertEqual((call["key"], call["max_tokens"], call["timeout"]), ("text", 6000, 90))
        for needed in ("Расскажите о своём проекте", "about 250 words (allowed: 225 to 275 words", "я сделал бота для заметок",
                       'written in the first person ("I built…")', 'it speaks in\nthe first person and the active voice',
                       "never invent experiences", '"questions"'):
            self.assertIn(needed, call["user"])
        self.assertEqual(out["outline"], ["начало", "проект", "итог"])
        self.assertEqual(out["questions"], ["Какой был результат?"])
        self.assertEqual(out["words"], 250)
        self.assertEqual(out["cliches"], [])
        self.assertEqual(len(out["parts"]), 1)
        self.assertIn("\n\n", out["text"])

    def test_essay_rules_of_formal_block_with_documents(self):
        self.add_docs()
        spark = self.use(self.answer(essay_text(60)))
        run(self.writer.essay(self.ctx(), "", "заметки про курсовую", 250))
        self.assertIn("Never copy its structure", spark.calls[0]["system"])
        self.assertIn("Question or topic: (none given)", spark.calls[0]["user"])

    def test_too_long_is_cut_once(self):
        spark = self.use(self.answer(essay_text(200)), {"text": essay_text(100)})
        out = run(self.writer.essay(self.ctx(), "q", "notes", 100))
        self.assertEqual(len(spark.calls), 2)
        self.assertIn("This essay has 200 words; it must have about 100 words (between 90 and 110)", spark.calls[1]["user"])
        self.assertIn("Cut it to about 100 words", spark.calls[1]["user"])
        self.assertEqual(out["words"], 100)
        self.assertEqual(out["outline"], ["начало", "проект", "итог"])  # the plan of the first answer is kept

    def test_slightly_long_or_short_is_left_alone(self):
        for n in (114, 90):  # up to 15 % over and down to 90 % of the target are fine
            spark = self.use(self.answer(essay_text(n)))
            run(self.writer.essay(self.ctx(), "q", "notes", 100))
            self.assertEqual(len(spark.calls), 1, n)

    def test_too_short_is_expanded_with_the_notes(self):
        spark = self.use(self.answer(essay_text(40)), {"text": essay_text(70)}, {"text": essay_text(98)})
        out = run(self.writer.essay(self.ctx(), "q", "я сделал бота", 100))
        self.assertEqual(len(spark.calls), 3)  # two expand passes, then it is within ±10 %
        self.assertIn("This essay has 40 words; it must have about 100 words (between 90 and 110)", spark.calls[1]["user"])
        self.assertIn("Expand it to about 100 words", spark.calls[1]["user"])
        self.assertIn("The user's notes: я сделал бота", spark.calls[1]["user"])
        self.assertIn("This essay has 70 words", spark.calls[2]["user"])
        self.assertEqual(out["words"], 98)

    def test_cliche_and_length_in_one_fix(self):
        spark = self.use(self.answer(essay_text(200, "В современном мире интернет играет важную роль. ")),
                         {"text": essay_text(90)})
        out = run(self.writer.essay(self.ctx(), "q", "notes", 100))
        fix = spark.calls[1]["user"]
        self.assertIn("Cut it to about 100 words", fix)
        self.assertIn("Also remove phrases that sound AI-written: В современном мире, играет важную роль", fix)
        self.assertEqual(out["cliches"], [])

    def test_cliches_left_after_the_fix_are_reported(self):
        stubborn = essay_text(50, "In today's world it plays a crucial role. ")
        self.use(self.answer(stubborn), {"text": stubborn})
        out = run(self.writer.essay(self.ctx(), "q", "notes", 100))
        self.assertEqual(out["cliches"], ["In today's world", "plays a crucial role"])

    def test_words_are_clamped(self):
        for asked, used in ((10, 80), (5000, 900), ("300", 300)):
            spark = self.use(self.answer(essay_text(40)))
            run(self.writer.essay(self.ctx(), "q", "notes", asked))
            self.assertIn(f"Length: about {used} words (allowed:", spark.calls[0]["user"], asked)

    def test_notes_are_capped_and_cleaned(self):
        spark = self.use(self.answer(essay_text(40)))
        run(self.writer.essay(self.ctx(), "q<|eot|>", "<|start|>" + "я" * 5000, 250))
        user = spark.calls[0]["user"]
        self.assertNotIn("<|", user)
        self.assertIn("я" * 4000, user)
        self.assertNotIn("я" * 4001, user)

    def test_outline_and_questions_are_capped(self):
        self.use(self.answer(essay_text(40), outline=[f"p{i}" for i in range(12)] + ["", "<|eot|>"],
                             questions=["a?", "", "b?", "c?", "d?"]))
        out = run(self.writer.essay(self.ctx(), "q", "notes", 250))
        self.assertEqual(out["outline"], [f"p{i}" for i in range(8)])
        self.assertEqual(out["questions"], ["a?", "b?", "c?"])

    def test_questions_as_a_string_are_not_split_into_letters(self):
        self.use(self.answer(essay_text(40), questions="Какой был результат?", outline="план"))
        out = run(self.writer.essay(self.ctx(), "q", "notes", 250))
        self.assertNotIn("К", out["questions"])
        self.assertNotIn("п", out["outline"])


class Cliches(unittest.TestCase):
    def test_listed_phrases_are_caught(self):
        for text in ("Не секрет, что", "является актуальной", "на сегодняшний день", "Let me delve into",
                     "a rich tapestry", "In conclusion, I", "an ever-evolving field", "embark on a journey"):
            self.assertTrue(writer.CLICHES.search(text), text)
        self.assertFalse(writer.CLICHES.search("Я собрал бота за выходные и показал его группе."))

    def test_plural_plays_a_role_is_caught(self):
        self.assertTrue(writer.CLICHES.search("Технологии играют важную роль в образовании"))


# ---- chat: email / essay modes -------------------------------------------------------------------------------

class ChatFormal(Base):
    def test_email_mode_passes_reply_to(self):
        spark = self.use({"subject": "Re", "text": "Здравствуйте.\nДа, подходит."})
        out = run(self.writer.chat(self.ctx(), "email", "да, подходит", "friends", reply_to="Подходит ли пятница?"))
        self.assertIn("Подходит ли пятница?", spark.calls[0]["user"])
        self.assertEqual(out["subject"], "Re")

    def test_essay_mode_defaults_to_250_words(self):
        spark = self.use({"text": essay_text(40), "outline": [], "questions": []})
        out = run(self.writer.chat(self.ctx(), "essay", "мои заметки", "friends", question="Почему я?"))
        self.assertIn("Length: about 250 words (allowed: 225 to 275 words", spark.calls[0]["user"])
        self.assertIn("Почему я?", spark.calls[0]["user"])
        self.assertEqual(out["questions"], [])

    def test_essay_revision_uses_the_formal_voice_and_a_long_budget(self):
        spark = self.use({"text": "Первый абзац.\nВторой абзац.", "rule": ""})
        out = run(self.writer.chat(self.ctx(), "essay", "мои заметки", "friends", question="Почему я?",
                                   history=[{"answer": "старое эссе", "feedback": "короче"}]))
        call = spark.calls[0]
        self.assertFalse(call["writes"])
        self.assertEqual((call["max_tokens"], call["timeout"]), (6000, 90))
        self.assertIn("Write the user's essay (Почему я?) from these notes", call["user"])
        self.assertIn("like a real person, not like an AI", call["system"])  # no documents yet
        self.assertNotIn("The user's style, from their own chats", call["system"])
        self.assertEqual(out["text"], "Первый абзац.\n\nВторой абзац.")
        self.assertIsNone(out["learned"])

    def test_email_revision_writes_with_documents(self):
        self.add_docs()
        spark = self.use({"text": "Здравствуйте.\nТекст.", "rule": "Keep emails short"})
        out = run(self.writer.chat(self.ctx(), "email", "заметки", "friends",
                                   history=[{"answer": "старое", "feedback": "короче, всегда"}]))
        self.assertTrue(spark.calls[0]["writes"])
        self.assertIn("how they greet, ask and sign off", spark.calls[0]["system"])
        self.assertEqual(out["learned"], "In emails and official messages: Keep emails short")
        self.assertIn("In emails and official messages: Keep emails short", styles.preferences(STYLE))


# ---- Context.formal_block --------------------------------------------------------------------------------------

def quoted(block):
    import re
    return re.findall(r"«(.*?)»", block)


class FormalBlock(Base):
    def test_empty_without_documents(self):
        self.assertEqual(self.ctx().formal_block("x", kind="essay"), "")

    def test_same_kind_first_and_its_rules(self):
        self.add_docs()
        ctx = self.ctx()
        essay = ctx.formal_block("консультация экзамен", kind="essay")
        self.assertIn("Never copy its structure, headings, format or topic", essay)
        self.assertEqual(len(quoted(essay)), 3)  # three essay paragraphs exist: no email one is picked
        self.assertTrue(all(q in ESSAY_DOC.replace("\n\n", " ") for q in quoted(essay)), quoted(essay))
        email = ctx.formal_block("курсовая история", kind="email")
        self.assertIn("how they greet, ask and sign off", email)
        picked = quoted(email)
        self.assertTrue(all(q in EMAIL_DOC for q in picked[:2]), picked)  # both email paragraphs first...
        self.assertIn(picked[2], ESSAY_DOC)  # ...then the closest essay one fills the third slot

    def test_unknown_kind_uses_the_email_rules(self):
        self.add_docs()
        self.assertIn("how they greet", self.ctx().formal_block("x", kind=None))
        self.assertIn("how they greet", self.ctx().formal_block("x", kind="official"))

    def test_most_similar_first_and_k(self):
        self.add_docs()
        ctx = self.ctx()
        block = ctx.formal_block("правители делили власть между сыновьями", kind="essay")
        self.assertIn("правители делили власть", quoted(block)[0])
        self.assertEqual(len(quoted(ctx.formal_block("x", k=2, kind="essay"))), 2)

    def test_long_paragraph_is_cut_to_120_words(self):
        long = " ".join(f"слово{i}" for i in range(200)) + "."
        styles.add_documents(STYLE, [("long.txt", long)], kind="essay")
        block = self.ctx().formal_block("слово1", kind="essay")
        self.assertEqual(len(quoted(block)[0].split()), 120)

    def test_profile_lines_are_included(self):
        self.add_docs()
        block = self.ctx().formal_block("x", kind="email")
        self.assertIn("opens emails with: Здравствуйте,", block)
        self.assertNotIn("[Name]", block.split("Never write template placeholders")[0])  # guards.for_prompt
        self.assertIn("signs off with: С уважением", block)

    def test_formal_formats_get_no_chat_examples(self):
        self.add_docs()
        ctx = self.ctx()
        for format in ("official", "email", "essay"):
            got = run(self.writer.examples(ctx, format, "friends", query="консультация"))
            self.assertNotIn("Some of their real messages", got, format)
            self.assertIn("formal writing", got, format)
        self.assertIn("Some of their real messages", run(self.writer.examples(ctx, "message", "friends", query="го")))


# ---- read_page and transcribe on a fake HTTP client ---------------------------------------------------------

class NoSleep(WriterTestCase):
    def setUp(self):
        super().setUp()
        self.saved_sleep = writer.asyncio.sleep

        async def no_sleep(_):
            return None
        writer.asyncio.sleep = no_sleep

    def tearDown(self):
        writer.asyncio.sleep = self.saved_sleep
        super().tearDown()


class ReadPage(NoSleep):
    def test_text_comes_back_and_the_image_is_sent_inline(self):
        self.writer.client = FakeClient(json.dumps({"text": "Мой абзац эссе."}))
        out = run(self.writer.read_page(b"\x89PNG fake", "image/png"))
        self.assertEqual(out, "Мой абзац эссе.")
        url, kwargs = self.writer.client.posts[0]
        self.assertEqual(url, writer.META_URL)
        system, user = kwargs["json"]["messages"]
        self.assertEqual(system["content"], documents.READ_SYSTEM)
        self.assertEqual(user["content"][1]["image_url"]["url"],
                         "data:image/png;base64," + base64.b64encode(b"\x89PNG fake").decode())
        self.assertEqual(kwargs["json"]["max_tokens"], 6000)

    def test_no_text_or_errors_are_empty_not_a_crash(self):
        for client in (FakeClient('{"text": ""}'), FakeClient("not json"), FakeClient("{}", status=500)):
            self.writer.client = client
            self.assertEqual(run(self.writer.read_page(b"x")), "")
            self.assertEqual(len(client.posts), 2)  # Muse Spark 1.3 twice, no fallback key


class Http:
    def __init__(self, status=200, payload=None, error=None):
        self.status, self.payload, self.error, self.posts = status, payload or {}, error, []

    async def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if self.error:
            raise self.error
        return FakeResponse(self.status, self.payload)


class Transcribe(WriterTestCase):
    def test_wav_in_text_out(self):
        self.writer.meta_key = "k"
        self.writer.client = Http(payload={"transcript": "  скажи маме<|eot|> что буду в 9 "})
        self.assertEqual(run(self.writer.transcribe(b"RIFF....WAVE")), "скажи маме что буду в 9")
        url, kwargs = self.writer.client.posts[0]
        self.assertEqual(url, writer.TRANSCRIBE_URL)
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer k"})
        request = json.loads(kwargs["files"]["request"][1])
        self.assertEqual(request["audioEncoding"], "WAV")
        self.assertEqual(kwargs["files"]["audio"], ("voice.wav", b"RIFF....WAVE", "audio/wav"))

    def test_no_transcript_is_empty(self):
        self.writer.client = Http(payload={"transcript": None})
        self.assertEqual(run(self.writer.transcribe(b"RIFF")), "")

    def test_errors_are_a_502(self):
        for client in (Http(status=500), Http(error=TimeoutError()), Http(payload=["not", "a", "dict"])):
            self.writer.client = client
            with self.assertRaises(Unavailable) as caught:
                run(self.writer.transcribe(b"RIFF"))
            self.assertEqual(caught.exception.status, 502)


if __name__ == "__main__":
    unittest.main()
