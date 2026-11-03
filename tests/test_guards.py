"""serving/guards.py: no template placeholders, no self-introduction the user didn't ask for, no remarks about the
request; variants that break a rule are dropped. Made-up texts only.

Usage: python3 -m pytest tests/test_guards.py
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline"), str(ROOT / "eval")]

import guards  # noqa: E402
import series  # noqa: E402


class Placeholders(unittest.TestCase):
    def test_found(self):
        for text in ("Уважаемая команда [Name],", "Hi [Your name]", "Dear <name>,", "from {company}", "(Ваше имя)",
                     "Best, (Name)", "[Компания] просит"):
            self.assertEqual(guards.problems(text), ["placeholder"], text)

    def test_not_placeholders(self):
        for text in ("го в 8 <3", "ок (буду поздно)", "встреча в 3 (если успею)", "ахах :)"):
            self.assertEqual(guards.problems(text), [], text)

    def test_removed_with_the_punctuation_around_them(self):
        cases = {
            "Уважаемая команда [Name],": "Уважаемая команда,",
            "Здравствуйте, [Name]!": "Здравствуйте!",
            "Dear [Name],": "Hello,",
            "[Name], добрый день": "добрый день",
            "Спасибо, (Ваше имя)": "Спасибо",
        }
        for text, fixed in cases.items():
            self.assertEqual(guards.fix(text), fixed, text)

    def test_a_line_that_was_only_a_placeholder_is_dropped(self):
        self.assertEqual(guards.fix("Best regards,\n[Your name]", format="email"), "Best regards,")

    def test_one_the_request_itself_has_is_kept(self):
        self.assertEqual(guards.fix("вот ссылка [link]", "скинь ему [link]"), "вот ссылка [link]")
        self.assertEqual(guards.problems("вот ссылка [link]", "скинь ему [link]"), [])


class Introductions(unittest.TestCase):
    def test_unasked_introduction_is_cut(self):
        text = "Меня зовут Айгерим, я менеджер проектов в компании Альфа. Прошу перенести встречу."
        self.assertEqual(guards.problems(text, "попроси перенести встречу"), ["introduction"])
        self.assertEqual(guards.fix(text, "попроси перенести встречу"), "Прошу перенести встречу.")

    def test_english(self):
        for intro in ("My name is Alex.", "I'm a product manager at Acme.", "I work as a designer.",
                      "As a student of the university, I ask for a delay.", "I am the head of marketing at Beta."):
            self.assertIn("introduction", guards.problems(intro + " Could we move the call?", "move the call"), intro)

    def test_the_formal_profile_role_never_leaks(self):
        """The job title comes from the user's own emails, not from the request: cut."""
        self.assertEqual(guards.fix("Я — руководитель отдела аналитики. Можно перенести звонок?", "перенеси звонок"),
                         "Можно перенести звонок?")

    def test_asked_for_or_given_in_the_request_it_stays(self):
        text = "Меня зовут Айгерим, я студентка 3 курса. Прошу перенести экзамен."
        for request in ("представься и попроси перенести экзамен", "cover letter for the internship",
                        "напиши что меня зовут Айгерим, я студентка 3 курса, и попроси перенести экзамен"):
            self.assertEqual(guards.fix(text, request), text, request)
            self.assertEqual(guards.problems(text, request), [], request)

    def test_an_essay_keeps_first_person_facts_from_the_notes(self):
        text = "Я студент третьего курса и сделал бота для заметок. Я работаю в компании Альфа аналитиком."
        notes = "учусь на 3 курсе, сделал бота для заметок"
        self.assertEqual(guards.fix(text, notes, "essay"), "Я студент третьего курса и сделал бота для заметок.")

    def test_a_chat_that_asks_who_the_user_is(self):
        self.assertEqual(guards.problems("я Айгерим, менеджер из Альфы", "the other person asks who you are"), [])

    def test_name_or_role_under_the_sign_off_is_dropped(self):
        text = "Здравствуйте!\n\nПрошу перенести консультацию.\n\nС уважением,\nАйгерим Б.\nProject Manager, Alpha"
        self.assertEqual(guards.fix(text, "перенеси консультацию", "email"),
                         "Здравствуйте!\n\nПрошу перенести консультацию.\n\nС уважением,")

    def test_ps_under_the_sign_off_stays(self):
        text = "Hello,\n\nThanks.\n\nBest regards\nP.S. See you Friday!"
        self.assertEqual(guards.fix(text, "", "email"), text)

    def test_chat_messages_are_not_signed_off(self):
        self.assertEqual(guards.fix("с уважением\nок буду", "", "series"), "с уважением\nок буду")


class Meta(unittest.TestCase):
    def test_remarks_about_the_request_are_cut(self):
        for remark in ("Детали обращения не были указаны.", "No details were provided.", "You didn't specify a date."):
            text = "Здравствуйте!\n\n" + remark + " Прошу перенести консультацию."
            self.assertEqual(guards.problems(text), ["meta"], remark)
            self.assertEqual(guards.fix(text, "", "email"), "Здравствуйте!\n\nПрошу перенести консультацию.")


class Apply(unittest.TestCase):
    def test_main_fixed_and_bad_alternatives_dropped(self):
        result = {"text": "Здравствуйте, [Name]! Прошу перенести.", "parts": ["x"],
                  "alternatives": ["Меня зовут Алекс. Прошу перенести.", "Прошу перенести, пожалуйста.", "Hi [Name]"]}
        guards.apply(result, "попроси перенести", "official")
        self.assertEqual(result["text"], "Здравствуйте! Прошу перенести.")
        self.assertEqual(result["parts"], [result["text"]])
        self.assertEqual(result["alternatives"], ["Прошу перенести, пожалуйста."])

    def test_candidates_start_with_the_fixed_answer(self):
        result = {"text": "ок [Name]", "parts": ["ок [Name]"], "candidates": ["ок [Name]", "ок", "го <имя>"]}
        guards.apply(result)
        self.assertEqual(result["text"], "ок")
        self.assertEqual(result["candidates"], ["ок"])

    def test_an_answer_that_was_all_introduction_takes_a_clean_alternative(self):
        result = {"text": "Меня зовут Алекс, я дизайнер.", "parts": ["…"], "alternatives": ["Привет! Как дела?"]}
        guards.apply(result, "поздоровайся")
        self.assertEqual(result["text"], "Привет! Как дела?")

    def test_series_parts_are_rebuilt(self):
        result = {"text": "привет [Name]\nкак ты", "parts": ["привет [Name]", "как ты"]}
        guards.apply(result, "", "series", series.parts_of)
        self.assertEqual(result["parts"], ["привет", "как ты"])

    def test_replies_and_subject(self):
        result = {"replies": [{"text": "го [Name]", "parts": ["го [Name]"]}, {"text": "не могу", "parts": ["не могу"]}],
                  "subject": "[Company] meeting"}
        guards.apply(result)
        self.assertEqual([r["text"] for r in result["replies"]], ["го", "не могу"])
        self.assertEqual(result["replies"][0]["parts"], ["го"])
        self.assertEqual(result["subject"], "meeting")


class ForPrompt(unittest.TestCase):
    def test_examples_lose_slots_and_facts_but_keep_list_marks(self):
        shown = "- opens emails with: Уважаемая команда [Name], / Hi [Name]\n«Меня зовут Айгерим. Прошу перенести встречу.»"
        got = guards.for_prompt(shown)
        self.assertNotIn("[Name]", got)
        self.assertNotIn("Айгерим", got)
        self.assertTrue(got.startswith("- opens emails with: Уважаемая команда"))
        self.assertIn("Прошу перенести встречу.", got)


if __name__ == "__main__":
    unittest.main()
