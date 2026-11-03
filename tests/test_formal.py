"""Official messages and emails (serving/writer.py): one language (the request's), nothing invented, one sign-off, the
person the text names wins over the audience chip, and every variant follows the same rules. Fake Muse Spark, no
network, made-up texts only.

Usage: python3 -m pytest tests/test_formal.py
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline"), str(ROOT / "eval"), str(ROOT / "tests")]

import styles  # noqa: E402
import writer  # noqa: E402
from test_writer_fakes import STYLE, WriterTestCase, run  # noqa: E402
from writer import Unavailable  # noqa: E402

ASK = "Спроси у профессора, будет ли керф по физике."
# What the phone showed on Nov 3 (Official, "To Friends"): English start, Russian filler, "we", two sign-offs.
BROKEN = ("Dear Professor, I would like to kindly ask whether a kerf will be held for the Physics course. "
          "Будем благодарны за обратную связь. Если у вас возникнут какие-либо вопросы, мы с радостью её "
          "предоставим. С уважением, Best regards")
GOOD = "Здравствуйте, профессор! Подскажите, пожалуйста, будет ли керф по физике? Спасибо."
GOOD_2 = "Добрый день, профессор! Скажите, пожалуйста, будет ли керф по физике?"
EN_DOC = ("Dear Professor Smith,\n\nI am writing to ask whether the lab report deadline could be moved to Friday, "
          "because I have two exams on Thursday.\n\nThank you for your time.\n\nBest regards")
RU_DOC = ("Здравствуйте, Иван Петрович!\n\nПрошу перенести консультацию на пятницу, в четверг у меня экзамен по "
          "физике.\n\nЗаранее спасибо за понимание и за вашу помощь с моей курсовой работой.\n\nС уважением")


class Spark:
    """Stands in for Writer.spark: answers in turn (the last one repeats) and records each call's arguments."""

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


# ---- the helpers ---------------------------------------------------------------------------------------------

class Language(unittest.TestCase):
    def test_the_request_language(self):
        self.assertEqual(writer.language(ASK), "ru")
        self.assertEqual(writer.language("ask the professor if the kerf in physics will happen"), "en")
        self.assertEqual(writer.language("Сәлеметсіз бе, мұғалім, ертең сабақ бола ма?"), "kk")
        self.assertEqual(writer.language("спроси у препода про керф по physics"), "ru")  # an English word inside
        self.assertIsNone(writer.language("123 :)"))

    def test_an_explicit_language_wins(self):
        self.assertEqual(writer.language("Напиши профессору на английском, что я опоздаю"), "en")
        self.assertEqual(writer.language("write to the dean in Russian that I'm sick"), "ru")
        self.assertEqual(writer.language("напиши по-немецки… на немецком, что я опоздаю"), "other")

    def test_addressee(self):
        self.assertEqual(writer.addressee(ASK), "профессора")
        self.assertEqual(writer.addressee("tell my boss I'm sick"), "boss")
        self.assertIsNone(writer.addressee("скажи что буду в 8"))
        self.assertIsNone(writer.addressee("the deanery is closed? no, the tutorials"))  # not "dean" or "tutor"


class SignOffs(unittest.TestCase):
    def test_the_double_signoff_from_the_phone(self):
        self.assertEqual(writer.dedupe_signoffs("…мы с радостью её предоставим. С уважением, Best regards", "ru"),
                         "…мы с радостью её предоставим. С уважением")

    def test_keeps_the_one_in_the_message_language(self):
        self.assertEqual(writer.dedupe_signoffs("Hi. Best regards, С уважением", "en"), "Hi. Best regards")
        self.assertEqual(writer.dedupe_signoffs("Здравствуйте!\n\nПрошу перенести.\n\nBest regards\n\nС уважением,",
                                                "ru"), "Здравствуйте!\n\nПрошу перенести.\n\nС уважением")
        self.assertEqual(writer.dedupe_signoffs("Hello Professor,\n\nCould you tell me?\n\nBest regards,\nС уважением",
                                                "en"), "Hello Professor,\n\nCould you tell me?\n\nBest regards")

    def test_one_signoff_or_body_words_are_left_alone(self):
        for text in ("Здравствуйте! Прошу перенести консультацию.\nС уважением",
                     "I sincerely hope, with regards to the exam, it is fine. Best regards"):
            self.assertEqual(writer.dedupe_signoffs(text, None), text)
        self.assertEqual(len(writer.signoffs("I sincerely hope, with regards to the exam, it is fine.")), 0)


class MixedLanguage(unittest.TestCase):
    def test_an_english_sentence_in_a_russian_message(self):
        found = writer.foreign_sentences(BROKEN, "ru", ASK)
        self.assertTrue(found and found[0].startswith("Dear Professor"), found)
        self.assertEqual(writer.foreign_sentences(GOOD, "ru", ASK), [])

    def test_a_russian_sentence_in_an_english_message(self):
        self.assertTrue(writer.foreign_sentences("Hello Professor! Will there be a kerf? Заранее спасибо за ответ.",
                                                 "en", "ask the professor about the kerf"))

    def test_the_users_own_terms_do_not_count(self):
        request = "спроси у профессора, будет ли kerf по Physics Lab Report Submission"
        text = "Здравствуйте, профессор! Будет ли kerf по Physics Lab Report Submission?"
        self.assertEqual(writer.foreign_sentences(text, "ru", request), [])
        self.assertTrue(writer.foreign_sentences(text, "ru", "спроси у профессора про керф"))

    def test_no_check_without_a_known_language(self):
        self.assertEqual(writer.foreign_sentences(BROKEN, "other", ASK), [])
        self.assertEqual(writer.foreign_sentences(BROKEN, None, ASK), [])

    def test_problems_name_language_filler_and_we(self):
        problems = writer.formal_problems(writer.dedupe_signoffs(BROKEN, "ru"), "ru", ASK)
        self.assertEqual(len(problems), 3, problems)
        self.assertIn("mixes languages", problems[0])
        self.assertIn("Будем благодарны", problems[1])
        self.assertIn("«мы»", problems[2])
        self.assertIn("more than one sign-off", " ".join(writer.formal_problems("Ок. С уважением, Best regards", "ru")))
        self.assertEqual(writer.formal_problems(GOOD, "ru", ASK), [])
        # what the user wrote themselves is theirs to keep
        self.assertEqual(writer.formal_problems("Мы придём в пятницу.", "ru", "скажи что мы придем в пятницу"), [])
        self.assertEqual(writer.formal_problems("В наше время это важно.", "ru", "x"), [])  # an idiom, not "we"


# ---- official / email through rewrite and compose ------------------------------------------------------------

class Official(Base):
    def compose(self, *answers, text=ASK, audience="friends", format="official"):
        spark = self.use(*answers)
        return spark, run(self.writer.compose(self.ctx(), text, audience, format=format))

    def test_the_bug_from_the_phone_never_comes_back(self):
        spark, out = self.compose({"text": BROKEN, "variants": [BROKEN.replace("Physics", "physics"), GOOD, GOOD_2]})
        self.assertEqual(out["text"], GOOD)  # the broken answer and its broken variant are dropped
        self.assertEqual(out["candidates"], [GOOD, GOOD_2])
        self.assertEqual(len(spark.calls), 1)
        for candidate in out["candidates"]:
            self.assertEqual(writer.formal_problems(candidate, "ru", ASK), [], candidate)

    def test_prompt_language_rules_and_the_named_person(self):
        spark, _ = self.compose({"text": GOOD, "variants": []})
        call = spark.calls[0]
        self.assertTrue(call["writes"])
        self.assertIn("to the профессора the input names", call["user"])
        self.assertIn("Language: Russian", call["user"])
        self.assertIn("Language: Russian", call["system"])
        self.assertIn("Never invent facts", call["system"])
        self.assertIn("«керф»", call["system"])  # keep the user's terms, don't guess what they mean
        self.assertNotIn("from their own chats", call["system"])  # never the casual style for friends
        self.assertNotIn("Some of their real messages", call["user"])

    def test_the_named_person_wins_over_the_chip(self):
        _, out = self.compose({"text": GOOD, "variants": []})
        self.assertEqual(out["audiences"][:2], ["elder_informal", "friends"])  # the chip comes next
        _, out = self.compose({"text": "Добрый день! Буду в 8.", "variants": []}, text="напиши что буду в 8")
        self.assertEqual(out["audiences"][0], "friends")  # nobody named: the chip stays first

    def test_chat_returns_the_inferred_audience_first(self):
        self.use({"text": GOOD, "variants": [GOOD_2]})
        out = run(self.writer.chat(self.ctx(), "write", ASK, "friends", format="official"))
        self.assertEqual(out["audiences"][0], "elder_informal")
        self.assertEqual(out["alternatives"], [GOOD_2])

    def test_a_double_signoff_is_deduped_not_dropped(self):
        _, out = self.compose({"text": "Здравствуйте, профессор! Будет ли керф по физике? С уважением, Best regards",
                               "variants": []})
        self.assertEqual(out["text"], "Здравствуйте, профессор! Будет ли керф по физике? С уважением")

    def test_all_bad_retries_once_with_spark_13(self):
        spark, out = self.compose({"text": BROKEN, "variants": [BROKEN]}, {"text": GOOD, "variants": [GOOD_2]})
        self.assertEqual(len(spark.calls), 2)
        self.assertNotIn("writes", {k for k, v in spark.calls[1].items() if v})  # Muse Spark 1.3 first
        self.assertIn("Your last answer had problems: it mixes languages", spark.calls[1]["user"])
        self.assertEqual(out["text"], GOOD)
        self.assertEqual(out["candidates"], [GOOD, GOOD_2])

    def test_still_bad_returns_the_least_bad(self):
        mixed_only = "Здравствуйте, профессор! Will there be a kerf for physics this term?"
        spark, out = self.compose({"text": BROKEN, "variants": [mixed_only]})
        self.assertEqual(len(spark.calls), 2)
        self.assertEqual(out["text"], mixed_only)  # one problem instead of three; never a 502 for this

    def test_a_failed_retry_still_answers(self):
        spark, out = self.compose({"text": BROKEN, "variants": []}, Unavailable(502, "down"))
        self.assertEqual(out["text"], writer.shape(writer.dedupe_signoffs(BROKEN, "ru"), "official")[0])

    def test_english_request_english_answer(self):
        ask = "ask the professor whether there will be a kerf in physics"
        good = "Hello Professor, could you tell me whether there will be a kerf in physics? Thank you."
        spark, out = self.compose({"text": "Здравствуйте, профессор! Будет ли kerf in physics?",
                                   "variants": [good, good + " Best regards, С уважением"]}, text=ask)
        self.assertIn("Language: English", spark.calls[0]["user"])
        self.assertEqual(out["text"], good)
        self.assertEqual(out["candidates"], [good, good + " Best regards"])

    def test_echo_and_rewrite_still_work(self):
        _, out = self.compose({"text": "Спроси у профессора про керф", "variants": [GOOD]})
        self.assertEqual(out["text"], GOOD)
        spark = self.use({"text": GOOD, "variants": []})
        out = run(self.writer.rewrite(self.ctx(), "профессор будет ли керф по физике", "friends", format="official"))
        self.assertIn("Rewrite this draft", spark.calls[0]["user"])
        self.assertEqual(out["text"], GOOD)

    def test_email_format_on_the_keyboard_follows_the_same_rules(self):
        email = "Здравствуйте, профессор!\nБудет ли керф по физике?\nС уважением,\nBest regards"
        _, out = self.compose({"text": email, "variants": []}, format="email")
        self.assertEqual(out["text"], "Здравствуйте, профессор!\n\nБудет ли керф по физике?\n\nС уважением")

    def test_message_format_is_untouched(self):
        spark, out = self.compose({"text": "проф, керф будет?", "variants": [], "audiences": ["friends"]},
                                  format="message")
        self.assertIn("to their friends", spark.calls[0]["user"])
        self.assertEqual(out["text"], "проф, керф будет?")


class FormalVoiceLanguage(Base):
    def add_docs(self):
        styles.add_documents(STYLE, [("en.txt", EN_DOC)], kind="email")
        styles.add_documents(STYLE, [("ru.txt", RU_DOC)], kind="email")

    def test_greetings_signoffs_and_paragraphs_of_the_language_only(self):
        self.add_docs()
        ctx = self.ctx()
        mixed = ctx.formal_block("экзамен", kind="email")
        self.assertIn("Best regards", mixed)
        self.assertIn("С уважением", mixed)  # without a language: everything, as before
        ru = ctx.formal_block("экзамен", kind="email", lang="ru")
        self.assertIn("С уважением", ru)
        self.assertNotIn("Best regards", ru)
        self.assertNotIn("Dear", ru)
        self.assertNotIn("lab report", ru)
        en = ctx.formal_block("exam", kind="email", lang="en")
        self.assertIn("Best regards", en)
        self.assertNotIn("С уважением", en)
        self.assertNotIn("консультацию", en)

    def test_only_other_language_documents_are_still_shown(self):
        styles.add_documents(STYLE, [("en.txt", EN_DOC)], kind="email")
        block = self.ctx().formal_block("экзамен", kind="email", lang="ru")
        self.assertIn("lab report", block)  # the manner still counts...
        self.assertNotIn("Best regards", block)  # ...but never an English sign-off for a Russian message
        self.assertNotIn("Dear", block)

    def test_official_prompt_gets_the_russian_voice(self):
        self.add_docs()
        spark = self.use({"text": GOOD, "variants": []})
        run(self.writer.compose(self.ctx(), ASK, "friends", format="official"))
        system = spark.calls[0]["system"]
        self.assertIn("С уважением", system)
        self.assertNotIn("Best regards", system)


class Email(Base):
    NOTES = "спроси у профессора будет ли керф по физике"

    def test_language_rule_and_one_call_when_fine(self):
        spark = self.use({"subject": "Керф по физике",
                          "text": "Здравствуйте, профессор!\nБудет ли керф по физике?\nС уважением"})
        out = run(self.writer.email(self.ctx(), self.NOTES))
        self.assertEqual(len(spark.calls), 1)
        self.assertIn("Language: Russian", spark.calls[0]["system"])
        self.assertIn("Never invent facts", spark.calls[0]["system"])
        self.assertEqual(out["text"], "Здравствуйте, профессор!\n\nБудет ли керф по физике?\n\nС уважением")
        self.assertEqual(out["subject"], "Керф по физике")

    def test_mixed_and_padded_email_is_written_again(self):
        bad = {"subject": "Kerf in Physics", "text": "Dear Professor,\nБудет ли керф по физике? Если у вас возникнут "
                                                     "какие-либо вопросы, мы с радостью ответим.\nС уважением,\nBest regards"}
        good = {"subject": "Керф по физике", "text": "Здравствуйте, профессор!\nБудет ли керф по физике?\nС уважением"}
        spark = self.use(bad, good)
        out = run(self.writer.email(self.ctx(), self.NOTES))
        self.assertEqual(len(spark.calls), 2)
        self.assertFalse(spark.calls[1].get("writes"))
        self.assertIn("Your last answer had problems", spark.calls[1]["user"])
        self.assertEqual(out["subject"], "Керф по физике")
        self.assertEqual(out["text"], "Здравствуйте, профессор!\n\nБудет ли керф по физике?\n\nС уважением")

    def test_double_signoff_is_deduped_even_without_a_retry(self):
        spark = self.use({"subject": "Керф", "text": "Здравствуйте!\nБудет ли керф по физике?\nС уважением,\nBest regards"},
                         {"subject": "", "text": "Здравствуйте! Will there be a kerf in Physics?"})
        out = run(self.writer.email(self.ctx(), self.NOTES))
        self.assertEqual(out["text"], "Здравствуйте!\n\nБудет ли керф по физике?\n\nС уважением")
        self.assertEqual(len(spark.calls), 1)  # deduped first: nothing left to fix

    def test_worse_retry_is_ignored(self):
        first = {"subject": "Керф", "text": "Здравствуйте!\nБудет ли керф? Будем благодарны за ответ."}
        worse = {"subject": "Kerf", "text": "Dear Professor, will there be a kerf? We would appreciate it."}
        self.use(first, worse)
        out = run(self.writer.email(self.ctx(), self.NOTES))
        self.assertIn("Будем благодарны", out["text"])  # one problem beats three
        self.assertEqual(out["subject"], "Керф")

    def test_english_notes_english_email(self):
        spark = self.use({"subject": "Kerf", "text": "Hello Professor,\nWill there be a kerf in physics?\nBest regards"})
        out = run(self.writer.email(self.ctx(), "ask the professor if there is a kerf in physics",
                                    reply_to="Здравствуйте, вопросы?"))
        self.assertIn("Language: English", spark.calls[0]["system"])
        self.assertEqual(len(spark.calls), 1)
        self.assertTrue(out["text"].endswith("Best regards"))


class Revision(Base):
    def test_official_revision_keeps_the_language_rules(self):
        spark = self.use({"text": GOOD + " С уважением, Best regards", "rule": ""})
        out = run(self.writer.chat(self.ctx(), "write", ASK, "friends", format="official",
                                   history=[{"answer": BROKEN, "feedback": "Wrong meaning"}]))
        self.assertIn("Language: Russian", spark.calls[0]["system"])
        self.assertIn("Never invent facts", spark.calls[0]["system"])
        self.assertEqual(out["text"], GOOD + " С уважением")


if __name__ == "__main__":
    unittest.main()
