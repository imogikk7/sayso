"""serving/documents.py: the user's own emails and essays → paragraphs and a formal profile. Made-up texts only.

Covers own_email (every quote marker), mbox_texts (multipart, charsets, empty bodies, the limit), text_of (.docx
entities, broken or bomb archives, .pdf and undecodable bytes), paragraphs (line joining, section labels, scrubbing,
caps), edges, profile and profile_text, and styles.add_documents on top of them.

Usage: .venv/bin/python -m pytest tests/test_cov_documents.py
"""

import io
import sys
import tempfile
import unittest
import zipfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline")]

import documents  # noqa: E402
import styles  # noqa: E402

MINE = "Здравствуйте, Анна Сергеевна!\n\nПрошу перенести защиту на четверг, в среду у меня экзамен.\n\nС уважением,\nАлекс"
THEIRS = "Защита в среду в 14:00, не опаздывайте."


def mbox(*messages):
    """Messages (email.message objects or raw strings) → the bytes of an .mbox file."""
    out = []
    for m in messages:
        raw = m if isinstance(m, str) else m.as_string()
        out.append("From sender@example.com Mon Nov  3 10:00:00 2026\n" + raw.rstrip("\n") + "\n\n")
    return "".join(out).encode()


def docx(xml):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


class OwnEmail(unittest.TestCase):
    def test_every_quote_marker_cuts_the_rest(self):
        markers = [
            "> " + THEIRS,
            "On Mon, 3 Nov 2026 at 10:00 Anna <anna@example.com> wrote:\n> " + THEIRS,
            "3 ноября 2026 г., 10:00 пользователь Анна написал(а):\n" + THEIRS,
            "Анна написала:\n" + THEIRS,
            "-----Original Message-----\n" + THEIRS,
            "-------- Пересылаемое сообщение --------\n" + THEIRS,
            "From: Anna\n" + THEIRS,
            "От: Анна\n" + THEIRS,
            "Sent from my iPhone\n" + THEIRS,
            "Отправлено с iPhone\n" + THEIRS,
        ]
        for tail in markers:
            own = documents.own_email(MINE + "\n\n" + tail)
            self.assertNotIn("опаздывайте", own, tail)
            self.assertIn("перенести защиту на четверг", own, tail)

    def test_no_quote_is_unchanged(self):
        self.assertEqual(documents.own_email(MINE), MINE)

    def test_markers_inside_a_line_do_not_cut(self):
        text = "Я пишу вам, потому что он написал: «приходите в среду». Можно в четверг?"
        self.assertEqual(documents.own_email(text), text)  # "написал:" not at the end of the line: not a quote header


class Mbox(unittest.TestCase):
    def test_plain_and_multipart_messages(self):
        multi = MIMEMultipart("alternative")
        multi.attach(MIMEText("Добрый день!\n\nОтправляю отчёт по практике, прошу проверить до пятницы.", "plain", "utf-8"))
        multi.attach(MIMEText("<p>HTML version</p>", "html", "utf-8"))
        plain = MIMEText(MINE + "\n\nOn Mon, 3 Nov 2026 Anna wrote:\n> " + THEIRS, "plain", "utf-8")
        bodies = documents.mbox_texts(mbox(plain, multi))
        self.assertEqual(len(bodies), 2)
        self.assertIn("перенести защиту", bodies[0])
        self.assertNotIn("опаздывайте", bodies[0])
        self.assertIn("отчёт по практике", bodies[1])
        self.assertNotIn("HTML version", bodies[1])

    def test_declared_charset_is_used(self):
        message = MIMEText("Прошу перенести консультацию на пятницу.", "plain", "cp1251")
        self.assertEqual(documents.mbox_texts(mbox(message)), ["Прошу перенести консультацию на пятницу."])

    def test_html_only_and_quote_only_messages_are_skipped(self):
        html = MIMEText("<p>only html</p>", "html", "utf-8")
        quote_only = MIMEText("> " + THEIRS, "plain", "utf-8")
        self.assertEqual(documents.mbox_texts(mbox(html, quote_only)), [])

    def test_limit(self):
        messages = [MIMEText(f"Письмо номер {i}, в котором я прошу о встрече.", "plain", "utf-8") for i in range(5)]
        self.assertEqual(len(documents.mbox_texts(mbox(*messages), limit=3)), 3)

    def test_garbage_is_empty(self):
        self.assertEqual(documents.mbox_texts(b"\x00\x01 not an mbox"), [])


class TextOf(unittest.TestCase):
    def test_docx_paragraphs_and_entities(self):
        xml = ("<w:document><w:body><w:p><w:r><w:t>Tom &amp; Jerry: a &lt;short&gt; essay</w:t></w:r></w:p>"
               "<w:p><w:r><w:t>Second</w:t></w:r><w:r><w:t> paragraph</w:t></w:r></w:p></w:body></w:document>")
        text = documents.text_of("Essay.DOCX", docx(xml))
        self.assertEqual(text.splitlines(), ["Tom & Jerry: a <short> essay", "Second paragraph"])

    def test_broken_docx_is_empty(self):
        self.assertEqual(documents.text_of("a.docx", b"not a zip"), "")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("other.xml", "<x/>")
        self.assertEqual(documents.text_of("a.docx", buffer.getvalue()), "")  # no word/document.xml

    def test_docx_bomb_is_empty(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", b"\0" * (50 * 1024 * 1024 + 1))
        self.assertLess(len(buffer.getvalue()), 200_000)
        self.assertEqual(documents.text_of("bomb.docx", buffer.getvalue()), "")

    def test_pdf_that_cannot_be_read_is_empty(self):
        self.assertEqual(documents.text_of("paper.pdf", b"%PDF-1.4 garbage"), "")

    def test_text_files_ignore_bad_bytes(self):
        self.assertEqual(documents.text_of("notes.md", "Текст".encode() + b"\xff\xfe"), "Текст")
        self.assertEqual(documents.text_of("noext", b"plain"), "plain")


class Paragraphs(unittest.TestCase):
    def test_wrapped_lines_are_joined_until_a_sentence_ends(self):
        text = ("Это первая строка абзаца, которая\nпродолжается на второй строке и\nзаканчивается здесь.\n"
                "Второй абзац начинается тут и тоже\nзаканчивается точкой в самом конце.")
        self.assertEqual(documents.paragraphs(text), [
            "Это первая строка абзаца, которая продолжается на второй строке и заканчивается здесь.",
            "Второй абзац начинается тут и тоже заканчивается точкой в самом конце."])

    def test_short_sentences_are_joined_to_reach_a_paragraph(self):
        text = "Коротко.\nЕщё одно короткое.\nИ третье предложение здесь."
        self.assertEqual(documents.paragraphs(text), ["Коротко. Ещё одно короткое. И третье предложение здесь."])

    def test_blank_line_blocks_join_their_lines(self):
        blocks = [f"Абзац номер {i} начинается на одной строке\nи продолжается на другой строке." for i in range(3)]
        self.assertEqual(documents.paragraphs("\r\n\r\n".join(blocks)),
                         [b.replace("\n", " ") for b in blocks])

    def test_section_labels_in_both_languages(self):
        cases = {
            "Тезис: Система наследования в степи была гибкой, но нестабильной.": "Система наследования",
            "Аргумент 2 - Правители делили власть между сыновьями и братьями.": "Правители делили",
            "Вывод. Гибкость системы стала и её силой, и её слабостью тоже.": "Гибкость системы",
            "Counter-argument: Some historians argue that it was quite stable.": "Some historians",
            "Prep 3 — Introduction: The steppe states had no single capital city.": "The steppe states",
        }
        paras = documents.paragraphs("\n\n".join(cases))
        self.assertEqual(len(paras), len(cases))
        for para, start in zip(paras, cases.values()):
            self.assertTrue(para.startswith(start), para)

    def test_a_word_that_only_starts_like_a_label_stays(self):
        para = "Bodybuilding taught me discipline long before I started programming."
        self.assertEqual(documents.paragraphs(para), [para])

    def test_contacts_are_scrubbed_and_short_lines_dropped(self):
        text = ("Мой проект можно посмотреть на https://example.com/project, пишите на me@example.com.\n\n"
                "Стр. 2\n\n"
                "Это последний абзац, в нём нет никаких ссылок и контактов.")
        paras = documents.paragraphs(text)
        self.assertEqual(len(paras), 2)
        self.assertNotIn("example.com", " ".join(paras))

    def test_paragraph_is_capped(self):
        self.assertEqual(len(documents.paragraphs("слово " * 1000 + ".")[0]), 2000)

    def test_empty(self):
        self.assertEqual(documents.paragraphs(""), [])
        self.assertEqual(documents.paragraphs("\n\n  \n"), [])


class Profile(unittest.TestCase):
    def test_edges(self):
        self.assertEqual(documents.edges(MINE), ("Здравствуйте, [Name]!", "С уважением,"))
        self.assertEqual(documents.edges("Здравствуйте!\nТекст.\nТел. 8 777 123 4567"), ("Здравствуйте!", None))
        self.assertEqual(documents.edges("Одна строка"), ("Одна строка", None))
        self.assertEqual(documents.edges(""), (None, None))
        long_open = "Добрый день, уважаемая Анна Сергеевна, надеюсь у вас всё хорошо\nТекст\nСпасибо"
        self.assertEqual(documents.edges(long_open), (None, "Спасибо"))

    def test_profile_counts_connectors_as_whole_words(self):
        texts = ["However, I finished the first part. Meanwhile the team waited.",
                 "I built it because my group needed it, and however hard it was, I finished."]
        p = documents.profile(texts, [("Hello Anna,", "Best regards."), ("Hello Anna!", None)])
        self.assertEqual(p["paragraphs"], 2)
        self.assertEqual(p["connectors"][0], "however")
        self.assertIn("because", p["connectors"])
        self.assertNotIn("while", p["connectors"])  # "Meanwhile" is not "while"
        self.assertEqual(p["openings"], ["Hello Anna"])
        self.assertEqual(p["closings"], ["Best regards"])
        self.assertGreater(p["first_person"], 0.1)
        self.assertIsNotNone(p["sentence_words"])

    def test_empty_profile(self):
        p = documents.profile([], [])
        self.assertEqual((p["paragraphs"], p["sentence_words"], p["paragraph_words"]), (0, None, None))
        self.assertEqual(documents.profile_text(p), "")
        self.assertEqual(documents.profile_text(None), "")

    def test_profile_text(self):
        p = documents.profile(["Кроме того, я закончил первую часть работы. Поэтому прошу продлить срок."],
                              [("Здравствуйте,", "С уважением,")])
        text = documents.profile_text(p)
        self.assertIn("sentences of about", text)
        self.assertIn("кроме того", text)
        self.assertIn("opens emails with: Здравствуйте", text)
        self.assertIn("signs off with: С уважением", text)


class AddDocuments(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = styles.DATA, styles.STYLES
        styles.DATA = Path(self.tmp.name)
        styles.STYLES = styles.DATA / "styles"
        self.id = styles.create("Formal")["id"]

    def tearDown(self):
        styles.DATA, styles.STYLES = self.saved
        self.tmp.cleanup()

    def test_kinds_are_counted_and_edges_come_from_emails_only(self):
        styles.add_documents(self.id, [("a.txt", MINE + "\n\n> " + THEIRS)], kind="email")
        formal = styles.add_documents(self.id, [("essay.txt", "Привет!\n\nЭто абзац моего эссе про степные государства.\n\nКонец")],
                                      kind="essay")
        self.assertEqual(formal["counts"], {"email": 1, "essay": 1})
        self.assertEqual(formal["documents"], 2)
        self.assertEqual(formal["profile"]["openings"], ["Здравствуйте, [Name]"])  # not the essay's "Привет"
        self.assertFalse(any("опаздывайте" in r["text"] for r in styles.documents(self.id)))

    def test_a_document_without_paragraphs_adds_nothing(self):
        formal = styles.add_documents(self.id, [("short.txt", "ок")], kind="email")
        self.assertEqual((formal["documents"], formal["ends"]), (0, []))

    def test_paragraphs_are_capped(self):
        text = "\n\n".join(f"Абзац номер {i}, в котором достаточно слов, чтобы его оставить." for i in range(350))
        styles.add_documents(self.id, [("big.txt", text)], kind="essay")
        rows = styles.documents(self.id)
        self.assertEqual(len(rows), documents.MAX_PARAGRAPHS)
        self.assertIn("номер 349", rows[-1]["text"])  # the newest are kept


if __name__ == "__main__":
    unittest.main()
