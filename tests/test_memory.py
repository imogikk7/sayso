"""serving/memory.py: the chat thread (`previous`). The refinement classifier, the revision of the last answer, and the
note that keeps a new topic consistent. Made-up texts only; no network.

Usage: python3 -m pytest tests/test_memory.py
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline"), str(ROOT / "eval"), str(ROOT / "tests")]

import memory  # noqa: E402
import postprocess  # noqa: E402
from test_writer_fakes import FakeClient, WriterTestCase, run  # noqa: E402

EMAIL = "Здравствуйте!\n\nПрошу перенести консультацию на пятницу: в четверг у меня экзамен.\n\nС уважением"
THREAD = [{"request": "письмо преподавателю: перенести консультацию на пятницу, в четверг экзамен", "answer": EMAIL}]

REFINE = [
    ("на русском", "email"), ("In English", "email"), ("in english please", "write"), ("по-английски", "write"),
    ("а теперь на казахском", "write"), ("переведи на английский", "email"), ("shorter", "write"),
    ("сделай покороче и вежливее", "write"), ("more formal pls", "email"), ("короче", "rewrite"),
    ("слишком длинно", "write"), ("ещё раз", "write"), ("add that I'm sick", "email"), ("добавь что я болею", "email"),
    ("убери про деньги", "write"), ("also mention the deadline", "email"), ("добавь что я болею", "rewrite"),
    ("make it less formal", "reply"), ("shorter", "essay"),
]
NEW = [
    ("напиши маме что буду в 9", "write"), ("Напиши письмо декану о переносе экзамена на пятницу", "email"),
    ("напиши на английском приглашение на свадьбу", "write"), ("го в кино завтра?", "write"),
    ("добавь соль в суп", "rewrite"),  # a draft in rewrite mode, not an edit of the last answer
    ("short message for mom about dinner", "write"), ("Thanks for the update, see you Monday", "rewrite"),
    ("ок буду в 8", "rewrite"), ("английский завтра в 9", "write"), ("", "write"),
    ("add " + "very " * 30 + "long thing", "email"),
]


class Classifier(unittest.TestCase):
    def test_refinements(self):
        for request, mode in REFINE:
            self.assertTrue(memory.is_refinement(request, THREAD, mode), (request, mode))

    def test_new_topics(self):
        for request, mode in NEW:
            self.assertFalse(memory.is_refinement(request, THREAD, mode), (request, mode))

    def test_without_a_previous_answer_nothing_is_a_refinement(self):
        for previous in ([], None, [{"request": "x", "answer": ""}]):
            self.assertFalse(memory.is_refinement("на русском", previous, "email"))

    def test_turns_keep_the_last_three_with_an_answer(self):
        previous = [{"request": f"r{i}", "answer": f"a{i}"} for i in range(5)] + [{"request": "r5", "answer": " "}]
        self.assertEqual([t["answer"] for t in memory.turns(previous)], ["a2", "a3", "a4"])


class Note(unittest.TestCase):
    def test_note_is_context_only_and_bounded(self):
        note = memory.note_for([{"request": "<|eot|>письмо", "answer": "я" * 1000}])
        self.assertIn("context only, for consistency", note)
        self.assertIn("never carry over facts", note)
        self.assertNotIn("<|", note)
        self.assertNotIn("я" * (memory.NOTE_CHARS + 1), note)
        self.assertEqual(memory.note_for([]), "")

    def test_with_note_appends_to_text_and_to_the_text_part_of_an_image_request(self):
        token = memory.NOTE.set("\n\nNOTE")
        try:
            self.assertEqual(memory.with_note("ask"), "ask\n\nNOTE")
            image = [{"type": "text", "text": "ask"}, {"type": "image_url", "image_url": {"url": "data:"}}]
            self.assertEqual(memory.with_note(image)[0]["text"], "ask\n\nNOTE")
            self.assertEqual(memory.with_note(image)[1], image[1])
        finally:
            memory.NOTE.reset(token)
        self.assertEqual(memory.with_note("ask"), "ask")


class Spark:
    """Writer.spark stand-in that also records the thread note in effect for each call."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    async def __call__(self, system, user, key, **kwargs):
        self.calls.append({"system": system, "user": user, "key": key, "note": memory.NOTE.get(), **kwargs})
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        return dict(answer)


class Revise(WriterTestCase):
    def use(self, *answers):
        self.writer.spark = Spark(*answers)
        return self.writer.spark

    def test_the_reported_bug_na_russkom_revises_the_email(self):
        """An email, then «на русском» in the same chat: the same email in Russian, not a new one about nothing."""
        english = "Hello,\n\nCould we move the consultation to Friday? I have an exam on Thursday.\n\nBest regards"
        thread = [{"request": "email to my teacher: move the consultation to Friday, exam on Thursday",
                   "answer": english}]
        spark = self.use({"subject": "Перенос консультации [Name]",
                          "text": "Уважаемая команда [Name],\n\nМеня зовут Айгерим, я менеджер проектов в компании Альфа. "
                                  "Можно перенести консультацию на пятницу? В четверг у меня экзамен.\n\n"
                                  "Детали обращения не были указаны.\n\nС уважением,\nАйгерим Б."})
        result, format = run(memory.respond(self.writer, self.ctx(), "email", "на русском", thread, "friends", "email",
                                            run=None))
        call = spark.calls[0]
        self.assertEqual(format, "email")
        self.assertIn(english.splitlines()[2], call["user"])  # the last answer is what gets changed
        self.assertIn("What they ask now: на русском", call["user"])
        self.assertIn("Never start a new text from scratch", call["user"])
        self.assertIn('"subject"', call["user"])
        self.assertTrue(call["writes"])
        self.assertIn("Never introduce the user", call["system"])
        out = postprocess.finish(result, "на русском", "email", thread)
        self.assertEqual(out["text"], "Уважаемая команда,\n\nМожно перенести консультацию на пятницу? В четверг у меня "
                                      "экзамен.\n\nС уважением,")
        self.assertEqual(out["subject"], "Перенос консультации")
        self.assertEqual(out["parts"], [out["text"]])
        self.assertEqual(out["alternatives"], [])
        self.assertEqual(out["alternative_parts"], [])

    def test_chat_message_refinement_returns_variants_as_alternatives(self):
        thread = [{"request": "скажи что опоздаю", "answer": "я опоздаю минут на 20 сорри"}]
        spark = self.use({"text": "опоздаю на 20", "variants": ["буду через 20", "опоздаю на 20", "сорри, +20 мин"]})
        result, format = run(memory.respond(self.writer, self.ctx(), "write", "короче", thread, "friends", "message",
                                            run=None))
        self.assertEqual(format, "message")
        self.assertIn("The user's style", spark.calls[0]["system"])
        self.assertIn('"variants"', spark.calls[0]["user"])
        self.assertEqual(result["text"], "опоздаю на 20")
        self.assertEqual(result["alternatives"], ["буду через 20", "сорри, +20 мин"])

    def test_styled_shape_for_rewrite_and_compose(self):
        self.use({"text": "опоздаю на 20", "variants": ["буду через 20"]})
        result, _ = run(memory.respond(self.writer, self.ctx(), "write", "shorter",
                                       [{"request": "x", "answer": "я опоздаю минут на 20"}], "friends", "message",
                                       run=None, shape="styled"))
        self.assertEqual(result["candidates"], ["опоздаю на 20", "буду через 20"])
        self.assertFalse(result["styled"])

    def test_essay_refinement_counts_words_and_uses_the_long_budget(self):
        spark = self.use({"text": "Первый абзац эссе.\nВторой абзац."})
        result, _ = run(memory.respond(self.writer, self.ctx(), "essay", "короче",
                                       [{"request": "notes", "answer": "длинное эссе"}], "friends", "message", run=None))
        call = spark.calls[0]
        self.assertFalse(call["writes"])
        self.assertEqual((call["max_tokens"], call["timeout"]), (6000, 90))
        self.assertEqual(result["words"], 5)
        self.assertEqual(result["text"], "Первый абзац эссе.\n\nВторой абзац.")

    def test_new_topic_runs_the_route_with_the_note_then_clears_it(self):
        spark = self.use({"text": "буду в 9", "variants": []})
        thread = [{"request": "письмо декану", "answer": EMAIL}]
        result, format = run(memory.respond(
            self.writer, self.ctx(), "write", "напиши маме что буду в 9", thread, "family", "message",
            run=lambda: self.writer.compose(self.ctx(), "напиши маме что буду в 9", "family")))
        self.assertEqual(result["text"], "буду в 9")
        self.assertIn("Earlier in this chat", spark.calls[0]["note"])
        self.assertIn("письмо декану", spark.calls[0]["note"])
        self.assertEqual(memory.NOTE.get(), "")

    def test_the_real_spark_call_carries_the_note(self):
        self.writer.client = FakeClient('{"text": "буду в 9"}')
        token = memory.NOTE.set(memory.note_for(THREAD))
        try:
            run(self.writer.spark("system", "напиши маме", "text"))
        finally:
            memory.NOTE.reset(token)
        sent = self.writer.client.posts[0][1]["json"]["messages"][1]["content"]
        self.assertTrue(sent.startswith("напиши маме"))
        self.assertIn("Earlier in this chat", sent)


if __name__ == "__main__":
    unittest.main()
