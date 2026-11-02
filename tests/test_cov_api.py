"""The real FastAPI app (serving/modal_app.py, built with the fakes of tests/test_api_auth.py): the routes the first
suite left untested. POST /styles/{id}/documents (pasted text, .mbox, .docx, photos, limits), POST /transcribe
(through the real Writer.transcribe on a fake HTTP client), the TokenGate middleware called directly at the ASGI level
(401 and 413 before any body is read), PATCH /styles/{id} removals, /chat email and essay, /warmup with the GPU off.
No network, no GPU, no private data.

Tests marked @unittest.expectedFailure pin bugs (ids TEST-n, see docs/reviews/tests.md).

Usage: .venv/bin/python -m pytest tests/test_cov_api.py
"""

import asyncio
import io
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline"), str(ROOT / "eval"), str(ROOT / "tests")]

from test_api_auth import HAVE_FASTAPI, TOKEN, build_app  # noqa: E402

if HAVE_FASTAPI:
    from fastapi.testclient import TestClient

ESSAY = ("Мой проект начался с простой проблемы: я терял заметки после каждой пары.\n\n"
         "Поэтому я написал бота, который собирает их в одну таблицу и напоминает о дедлайнах.\n\n"
         "Через месяц им пользовалась вся группа, и я понял, что люблю делать полезные вещи.")
MAIL = ("Здравствуйте, Иван Петрович!\n\nПрошу перенести консультацию на пятницу, в четверг у меня экзамен.\n\n"
        "С уважением\n\nOn Mon, 3 Nov 2026 Ivan wrote:\n> Консультация в четверг, не опаздывайте.\n")
PAGE = "Это абзац с фотографии страницы моего эссе, достаточно длинный, чтобы его оставить."


class Spark:
    """Muse Spark for the app: a transcribed page for photos, an essay, an email, a chat answer."""

    def __init__(self):
        self.calls = []

    async def __call__(self, system, user, key, max_tokens=3000, **_):
        import documents
        self.calls.append({"system": system, "user": user, "key": key})
        if system == documents.READ_SYSTEM:
            return {"text": PAGE}
        text = user if isinstance(user, str) else ""
        if "The user needs an essay" in text:
            return {"outline": ["a", "b"], "text": "Первый абзац эссе.\nВторой абзац эссе.", "questions": ["Когда?"]}
        if text.startswith("Write an email"):
            return {"subject": "Консультация", "text": "Здравствуйте.\nПрошу перенести консультацию.\nС уважением"}
        return {"text": "го в 8", "variants": []}


class Http:
    """The app's httpx client, faked: answers Muse Voice Transcribe."""

    def __init__(self, status=200, transcript="скажи маме что буду в 9"):
        self.status, self.transcript, self.posts = status, transcript, []

    async def post(self, url, **kwargs):
        from test_writer_fakes import FakeResponse
        self.posts.append((url, kwargs))
        return FakeResponse(self.status, {"transcript": self.transcript})


def wav(n=64):
    return b"RIFF" + b"\0" * 4 + b"WAVEfmt " + b"\0" * n


def docx(paragraphs):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs))
    return buffer.getvalue()


@unittest.skipUnless(HAVE_FASTAPI, "fastapi, httpx and python-multipart are not installed (see test_api_auth.py)")
class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        import styles
        cls.saved_paths = styles.DATA, styles.STYLES, styles.on_write
        cls.saved_env = dict(os.environ)
        cls.web, cls.writer, cls.latest = build_app(cls.tmp.name)
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
        import styles
        from test_writer_fakes import make_style
        self.spark = self.writer.spark = Spark()
        self.http = self.writer.client = Http()
        self.style = make_style(styles.create("Docs")["id"])  # a fresh made-up style per test
        self.url = f"/styles/{self.style}/documents"

    def post_docs(self, files=None, **data):
        return self.client.post(self.url, headers=self.auth, data=data, files=files)

    # ---- /styles/{id}/documents ---------------------------------------------------------------------------

    def test_pasted_essay(self):
        response = self.post_docs(text=ESSAY, kind="essay")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual((body["documents"], body["counts"], body["paragraphs"]), (1, {"email": 0, "essay": 1}, 3))
        self.assertIn("поэтому", body["profile"]["connectors"])
        view = self.client.get(f"/styles/{self.style}", headers=self.auth).json()
        self.assertEqual(view["formal"]["documents"], 1)

    def test_mbox_messages_become_email_documents_without_quotes(self):
        box = "".join(f"From me@example.com Mon Nov  3 10:00:00 2026\nContent-Type: text/plain; charset=utf-8\n\n{MAIL}\n"
                      for _ in range(2)).encode()
        response = self.post_docs(files={"files": ("Sent.mbox", box)}, kind="email")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["counts"], {"email": 2, "essay": 0})
        import styles
        stored = " ".join(r["text"] for r in styles.documents(self.style))
        self.assertIn("перенести консультацию", stored)
        self.assertNotIn("не опаздывайте", stored)
        self.assertEqual(response.json()["profile"]["openings"], ["Здравствуйте, [Name]"])

    def test_docx_and_txt_files(self):
        files = [("files", ("essay.docx", docx(ESSAY.split("\n\n")))), ("files", ("more.txt", ESSAY.encode()))]
        response = self.post_docs(files=files, kind="essay")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["documents"], 2)

    def test_photos_are_read_by_spark_and_not_kept(self):
        files = [("files", ("page.HEIC", b"heic-bytes", "application/octet-stream")),
                 ("files", ("scan", b"png-bytes", "image/png"))]
        response = self.post_docs(files=files, kind="essay")
        self.assertEqual(response.status_code, 200, response.text)
        reads = [c for c in self.spark.calls if c["key"] == "text"]
        self.assertEqual(len(reads), 2)
        urls = sorted(c["user"][1]["image_url"]["url"].split(";")[0] for c in reads)
        self.assertEqual(urls, ["data:image/jpeg", "data:image/png"])  # unknown type → jpeg, declared type kept
        import styles
        folder = styles.folder(self.style)
        self.assertFalse(any(b"heic-bytes" in p.read_bytes() for p in folder.rglob("*") if p.is_file()))
        self.assertEqual(response.json()["documents"], 2)

    def test_unknown_style_bad_kind_and_nothing_readable(self):
        self.assertEqual(self.client.post("/styles/nosuch/documents", headers=self.auth,
                                          data={"text": ESSAY}).status_code, 404)
        self.assertEqual(self.post_docs(text=ESSAY, kind="poem").status_code, 422)
        self.assertEqual(self.post_docs(files={"files": ("empty.txt", b"")}, kind="essay").status_code, 422)
        self.assertEqual(self.post_docs(text="   ").status_code, 422)

    def test_more_than_25_mb_is_413(self):
        big = b"a" * (13 * 1024 * 1024)
        response = self.post_docs(files=[("files", ("a.txt", big)), ("files", ("b.txt", big))], kind="essay")
        self.assertEqual(response.status_code, 413)

    def test_one_file_over_20_mb_is_413(self):
        response = self.post_docs(files={"files": ("big.txt", b"a " * (11 * 1024 * 1024))}, kind="essay")
        self.assertEqual(response.status_code, 413)

    def test_clear_documents(self):
        self.post_docs(text=ESSAY, kind="essay")
        response = self.client.patch(f"/styles/{self.style}", headers=self.auth, json={"clear_documents": True})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["formal"]["documents"], 0)

    # ---- /transcribe -----------------------------------------------------------------------------------------

    def test_transcribe(self):
        response = self.client.post("/transcribe", headers=self.auth, files={"audio": ("v.wav", wav(), "audio/wav")})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"text": "скажи маме что буду в 9"})
        url, kwargs = self.http.posts[0]
        self.assertTrue(url.endswith("/asr/transcribe"))
        self.assertEqual(kwargs["files"]["audio"][1], wav())

    def test_transcribe_limits(self):
        not_wav = self.client.post("/transcribe", headers=self.auth, files={"audio": ("v.m4a", b"ftypM4A ...")})
        self.assertEqual(not_wav.status_code, 422)
        too_big = self.client.post("/transcribe", headers=self.auth,
                                   files={"audio": ("v.wav", wav(10 * 1024 * 1024))})
        self.assertEqual(too_big.status_code, 413)
        self.assertEqual(self.client.post("/transcribe", headers=self.auth).status_code, 422)  # no file at all
        self.assertEqual(self.http.posts, [])

    def test_transcribe_upstream_error_is_502(self):
        self.writer.client = Http(status=500)
        response = self.client.post("/transcribe", headers=self.auth, files={"audio": ("v.wav", wav())})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "Muse Voice Transcribe did not answer")

    # ---- the token gate ----------------------------------------------------------------------------------------

    def asgi(self, path, headers):
        """Calls the app the way uvicorn does; returns (status, whether the body was read)."""
        received, sent = [], []

        async def receive():
            received.append(True)
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
                 "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
                 "headers": headers, "client": ("127.0.0.1", 1), "server": ("test", 80)}
        asyncio.run(self.web(scope, receive, send))
        return sent[0]["status"], bool(received)

    def test_gate_401_before_reading_any_body(self):
        for path in ("/transcribe", self.url, "/styles", "/chat"):
            for headers in ([], [(b"authorization", b"Bearer wrong")], [(b"authorization", TOKEN.encode())]):
                self.assertEqual(self.asgi(path, headers + [(b"content-length", b"5")]), (401, False), (path, headers))

    def test_gate_401_comes_before_413(self):
        self.assertEqual(self.asgi("/transcribe", [(b"content-length", b"999999999")]), (401, False))

    def test_gate_413_on_a_huge_declared_size(self):
        headers = [(b"authorization", f"Bearer {TOKEN}".encode()), (b"content-length", str(60 * 1024 * 1024 + 1).encode())]
        self.assertEqual(self.asgi("/transcribe", headers), (413, False))
        headers[1] = (b"content-length", str(60 * 1024 * 1024).encode())  # exactly 60 MB passes the gate
        self.assertNotEqual(self.asgi("/warmup", headers)[0], 413)

    def test_unauthenticated_multipart_is_not_parsed(self):
        from starlette.requests import Request
        parsed, real_form = [], Request.form

        def form(self, *a, **k):
            parsed.append(True)
            return real_form(self, *a, **k)
        Request.form = form
        try:
            for path, files in (("/transcribe", {"audio": ("v.wav", wav(100_000))}),
                                (self.url, {"files": ("a.txt", b"x" * 100_000)})):
                self.assertEqual(self.client.post(path, files=files).status_code, 401, path)
        finally:
            Request.form = real_form
        self.assertEqual(parsed, [])

    # ---- the rest ------------------------------------------------------------------------------------------------

    def test_chat_email_and_essay(self):
        email = self.client.post("/chat", headers=self.auth, json={"mode": "email", "text": "перенести консультацию",
                                                                   "style": self.style, "reply_to": "Когда удобно?"})
        self.assertEqual(email.status_code, 200, email.text)
        self.assertEqual(email.json()["subject"], "Консультация")
        essay = self.client.post("/chat", headers=self.auth, json={"mode": "essay", "text": "мои заметки",
                                                                   "question": "Почему я?", "words": 300,
                                                                   "style": self.style})
        self.assertEqual(essay.status_code, 200, essay.text)
        self.assertEqual((essay.json()["outline"], essay.json()["questions"]), (["a", "b"], ["Когда?"]))
        self.assertEqual(self.client.post("/chat", headers=self.auth, json={"mode": "essay", "text": "x", "words": 40,
                                                                            "style": self.style}).status_code, 422)
        self.assertEqual(self.client.post("/chat", headers=self.auth, json={"mode": "poem", "text": "x",
                                                                            "style": self.style}).status_code, 422)

    def test_patch_removes_a_preference_and_a_learned_message(self):
        import styles
        styles.add_preference(self.style, "No emoji with family")
        row = styles.add_learned(self.style, [{"audience": "friends", "text": "го", "kind": "typed"}])[0]
        response = self.client.patch(f"/styles/{self.style}", headers=self.auth,
                                     json={"remove_preference": 0, "remove_learned": row["id"], "name": "  Renamed "})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual((body["preferences"], body["learning"]["recent"], body["name"]), ([], [], "Renamed"))
        self.assertEqual(self.client.patch(f"/styles/{self.style}", headers=self.auth,
                                           json={"remove_preference": 7}).status_code, 200)  # out of range: no-op

    def test_full_view_and_list(self):
        import styles
        styles.add_feedback(self.style, {"audience": "friends", "format": "message", "text": "го", "kind": "liked"})
        view = self.client.get(f"/styles/{self.style}", headers=self.auth).json()
        self.assertEqual(view["learning"]["liked"], 1)
        self.assertIn("friends", view["examples"])
        self.assertIn("friends", view["profile"])
        listed = self.client.get("/styles", headers=self.auth).json()["styles"]
        self.assertIn(self.style, [s["id"] for s in listed])
        self.assertEqual(self.client.get("/styles/nosuch", headers=self.auth).status_code, 404)

    def test_delete_drops_the_cached_context(self):
        self.writer.context(self.style)
        self.assertEqual(self.client.delete(f"/styles/{self.style}", headers=self.auth).status_code, 200)
        self.assertNotIn(self.style, self.writer.contexts)
        self.assertEqual(self.client.delete(f"/styles/{self.style}", headers=self.auth).status_code, 404)

    def test_warmup_with_the_gpu_off(self):
        self.assertEqual(self.client.get("/warmup", headers=self.auth).json(), {"ready": False, "gpu": "off"})

    def test_reply_from_a_summary_restyles_without_reading(self):
        response = self.client.post("/reply", headers=self.auth, json={
            "summary": "asks if I come at 8", "audience": "family", "style": self.style,
            "options": [{"act": "agree", "draft": "да, буду"}, {"act": "nonsense", "draft": "x"}]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([r["text"] for r in response.json()["replies"]], ["да, буду"])
        self.assertEqual(self.spark.calls, [])  # nothing was read again


if __name__ == "__main__":
    unittest.main()
