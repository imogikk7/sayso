"""Blind test v3 routes on the real FastAPI app (serving/modal_app.py built with the fakes of test_api_auth): the page
and the answer post are the only routes without the token; answers are stored, capped, rate-limited, junk is
rejected; the responses need the token. No network.

Needs fastapi + httpx + python-multipart (see tests/test_api_auth.py); skipped without them.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "tests")]

import blind  # noqa: E402
from test_api_auth import HAVE_FASTAPI, TOKEN, build_app  # noqa: E402

if HAVE_FASTAPI:
    from fastapi.testclient import TestClient

TEST = "Ab3dEfGh1jKlMnOpQrStUv-_"  # made-up, 24 characters like secrets.token_urlsafe(18)
PAGE = "<!DOCTYPE html><html><head><title>Человек или ИИ?</title></head><body>page</body></html>"


class Public(unittest.TestCase):
    def test_only_the_page_and_the_answer_post(self):
        self.assertTrue(blind.public("GET", f"/blind/{TEST}"))
        self.assertTrue(blind.public("POST", f"/blind/{TEST}/answers"))
        self.assertTrue(blind.public("OPTIONS", f"/blind/{TEST}/answers"))
        for method, path in (("GET", f"/blind/{TEST}/responses"), ("POST", f"/blind/{TEST}"),
                             ("GET", f"/blind/{TEST}/answers"), ("DELETE", f"/blind/{TEST}"),
                             ("GET", "/blind/short"), ("GET", f"/blind/{TEST}/../styles"), ("GET", "/styles"),
                             ("GET", f"/x/blind/{TEST}"), ("GET", f"/blind/{TEST}/answers/x"), ("GET", None)):
            self.assertFalse(blind.public(method, path), (method, path))

    def test_parse_answers(self):
        ok = json.dumps({"sid": "abcdefgh", "name": " Ми\u0000ра \n", "answers": ["H", "A", "H"]}).encode()
        self.assertEqual(blind.parse_answers(ok, 3), {"sid": "abcdefgh", "name": "Мира", "answers": ["H", "A", "H"]})
        for raw in (b"", b"{not json", b"[1]", b"\xff\xfe", json.dumps({"sid": "abcdefgh", "answers": ["H"]}).encode(),
                    json.dumps({"sid": "abcdefgh", "answers": ["H", "A", "X"]}).encode(),
                    json.dumps({"sid": "abcdefgh", "answers": ["H", "A", None]}).encode(),
                    json.dumps({"sid": "a b", "answers": ["H", "A", "H"]}).encode(),
                    json.dumps({"answers": ["H", "A", "H"]}).encode(),
                    json.dumps({"sid": "abcdefgh", "answers": ["H", "A", "H"], "ip": "1.2.3.4"}).encode(),
                    b'{"sid": "abcdefgh", "answers": ["H", "A", "H"], "name": "' + b"x" * 9000 + b'"}'):
            with self.assertRaises(ValueError, msg=raw[:40]):
                blind.parse_answers(raw, 3)
        long_name = json.dumps({"sid": "abcdefgh", "name": "я" * 100, "answers": ["H"]}).encode()
        self.assertEqual(len(blind.parse_answers(long_name, 1)["name"]), 40)

    def test_limiter(self):
        now = [0.0]
        limiter = blind.Limiter(2, 60, clock=lambda: now[0])
        self.assertEqual([limiter.allow("a") for _ in range(3)], [True, True, False])
        self.assertTrue(limiter.allow("b"))
        now[0] = 61
        self.assertTrue(limiter.allow("a"))


@unittest.skipUnless(HAVE_FASTAPI, "fastapi, httpx and python-multipart are not installed (see test_api_auth.py)")
class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        import styles
        cls.saved_paths = styles.DATA, styles.STYLES, styles.on_write
        cls.saved_env = dict(os.environ)
        cls.web, _, _ = build_app(cls.tmp.name)
        cls.client = TestClient(cls.web, raise_server_exceptions=False)
        cls.auth = {"Authorization": f"Bearer {TOKEN}"}
        cls.folder = Path(cls.tmp.name) / "blind" / TEST
        cls.folder.mkdir(parents=True)
        (cls.folder / "test.html").write_text(PAGE, encoding="utf-8")
        page = {"version": 3, "test_id": TEST, "author": "",
                "questions": [{"id": f"q{i}", "context": "Друг пишет", "parts": ["го"]} for i in range(1, 6)]}
        (cls.folder / "questions.json").write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
        cls.ip = 0

    @classmethod
    def tearDownClass(cls):
        import styles
        styles.DATA, styles.STYLES, styles.on_write = cls.saved_paths
        os.environ.clear()
        os.environ.update(cls.saved_env)
        cls.tmp.cleanup()

    def setUp(self):
        (self.folder / "responses.jsonl").unlink(missing_ok=True)
        Routes.ip += 1
        self.from_ip = {"X-Forwarded-For": f"10.0.0.{Routes.ip}, 172.16.0.1"}

    def post(self, body, headers=None, test=TEST):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        return self.client.post(f"/blind/{test}/answers", content=raw,
                                headers={"Content-Type": "text/plain;charset=UTF-8", **self.from_ip, **(headers or {})})

    def stored(self):
        path = self.folder / "responses.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def answer(self, sid="session1", name="Мира"):
        return {"sid": sid, "name": name, "answers": ["H", "A", "H", "A", "A"]}

    def test_page_without_the_token(self):
        response = self.client.get(f"/blind/{TEST}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, PAGE)
        self.assertTrue(response.headers["content-type"].startswith("text/html"))
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("noindex", response.headers["x-robots-tag"])
        self.assertIn("connect-src 'self'", response.headers["content-security-policy"])
        self.assertEqual(self.client.get(f"/blind/{TEST}/").status_code, 200)

    def test_unknown_and_malformed_tests(self):
        self.assertEqual(self.client.get("/blind/" + "z" * 24).status_code, 404)
        self.assertEqual(self.client.get("/blind/short").status_code, 401)  # not a test id: the gate wants the token
        self.assertEqual(self.post(self.answer(), test="z" * 24).status_code, 404)

    def test_the_rest_still_needs_the_token(self):
        for method, path in (("GET", f"/blind/{TEST}/responses"), ("POST", f"/blind/{TEST}"),
                             ("GET", f"/blind/{TEST}/answers"), ("DELETE", f"/blind/{TEST}"), ("GET", "/latest"),
                             ("POST", "/chat")):
            self.assertEqual(self.client.request(method, path).status_code, 401, (method, path))
        wrong = {"Authorization": "Bearer wrong"}
        self.assertEqual(self.client.get(f"/blind/{TEST}/responses", headers=wrong).status_code, 401)

    def test_stores_an_answer(self):
        response = self.post(self.answer())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(response.headers["access-control-allow-origin"], "*")  # the page opened as a file
        rows = self.stored()
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]), {"sid", "name", "answers", "at"})  # no IP, no headers
        self.assertEqual((rows[0]["sid"], rows[0]["name"], rows[0]["answers"]),
                         ("session1", "Мира", ["H", "A", "H", "A", "A"]))
        self.assertNotIn("10.0.0", (self.folder / "responses.jsonl").read_text(encoding="utf-8"))

        listed = self.client.get(f"/blind/{TEST}/responses", headers=self.auth)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["responses"], rows)

    def test_preflight(self):
        response = self.client.options(f"/blind/{TEST}/answers", headers=self.from_ip)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers["access-control-allow-origin"], "*")

    def test_rejects_junk(self):
        for body in (b"{not json", b"[]", {"sid": "session1", "answers": ["H"] * 4},
                     {"sid": "session1", "answers": ["H", "A", "H", "A", "maybe"]},
                     {"sid": "bad sid!", "answers": ["H"] * 5}, {"sid": "session1", "answers": "HHHHH"},
                     {**self.answer(), "extra": 1}):
            Routes.ip += 1
            self.from_ip = {"X-Forwarded-For": f"10.0.1.{Routes.ip}"}
            self.assertEqual(self.post(body).status_code, 422, body)
        self.assertEqual(self.stored(), [])

    def test_size_cap(self):
        big = json.dumps({**self.answer(), "name": "x" * (blind.MAX_BODY + 10)}).encode()
        self.assertEqual(self.post(big).status_code, 413)
        self.assertEqual(self.stored(), [])

    def test_rate_limit_per_address(self):
        limit = blind.PER_IP[0]
        codes = [self.post(self.answer(sid=f"session{i}")).status_code for i in range(limit + 2)]
        self.assertEqual(codes, [200] * limit + [429, 429])
        self.assertEqual(len(self.stored()), limit)
        self.from_ip = {"X-Forwarded-For": "10.9.9.9"}
        self.assertEqual(self.post(self.answer(sid="another1")).status_code, 200)

    def test_file_cap(self):
        saved = blind.MAX_RESPONSES
        blind.MAX_RESPONSES = 2
        try:
            codes = []
            for i in range(3):
                Routes.ip += 1
                self.from_ip = {"X-Forwarded-For": f"10.0.2.{Routes.ip}"}
                codes.append(self.post(self.answer(sid=f"session{i}")).status_code)
        finally:
            blind.MAX_RESPONSES = saved
        self.assertEqual(codes, [200, 200, 507])
        self.assertEqual(len(self.stored()), 2)


if __name__ == "__main__":
    unittest.main()
