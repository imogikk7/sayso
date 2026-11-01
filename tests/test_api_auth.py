"""The real FastAPI app from serving/modal_app.py, built without Modal: auth on every route, input limits, upload
handling. A fake `modal` module (decorators that return the function, an in-memory Dict, a no-op Volume) and a fake
`transformers` are put in sys.modules before the import; the Writer gets a fake Muse Spark. No network, no GPU.

Needs fastapi + httpx + python-multipart (the API image's own dependencies, not the pipeline's); skipped without them:
  python3 -m venv /tmp/venv && /tmp/venv/bin/pip install fastapi httpx python-multipart
  /tmp/venv/bin/python -m unittest tests/test_api_auth.py

Tests marked @unittest.expectedFailure pin findings of docs/REVIEW_FINAL.md; drop the decorator once fixed.
"""

import asyncio
import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline"), str(ROOT / "eval"), str(ROOT / "tests")]

try:
    import fastapi  # noqa: F401
    import httpx  # noqa: F401
    import multipart  # noqa: F401  (python-multipart, for POST /styles)
    from fastapi.testclient import TestClient
    HAVE_FASTAPI = True
except ImportError:
    HAVE_FASTAPI = False

TOKEN = "test-token-not-a-secret"


# ---- a fake `modal` -----------------------------------------------------------------------------------------

class _Aio:
    """f(...) and f.aio(...), like Modal's sync/async method pairs."""

    def __init__(self, fn):
        self.fn = fn

    def __call__(self, *a, **k):
        return self.fn(*a, **k)

    async def aio(self, *a, **k):
        return self.fn(*a, **k)


class _Function:
    spawned = []

    def __init__(self, fn):
        self.fn = fn
        self.spawn = _Aio(lambda *a, **k: _Function.spawned.append((fn.__name__, a, k)))

    def __call__(self, *a, **k):
        return self.fn(*a, **k)

    def get_web_url(self):
        return "http://glimmer.invalid"


class _Image:
    def __getattr__(self, name):
        return lambda *a, **k: self

    @classmethod
    def from_registry(cls, *a, **k):
        return cls()

    @classmethod
    def debian_slim(cls, *a, **k):
        return cls()


class _Dict:
    def __init__(self):
        self.store = {}
        self.put = _Aio(lambda key, value: self.store.__setitem__(key, value))
        self.get = _Aio(lambda key, default=None: self.store.get(key, default))

    @classmethod
    def from_name(cls, *a, **k):
        return cls()


class _Volume:
    commits = 0

    @classmethod
    def from_name(cls, *a, **k):
        return cls()

    def commit(self):
        _Volume.commits += 1

    def reload(self):
        pass


class _App:
    def __init__(self, *a, **k):
        pass

    def function(self, *a, **k):
        return lambda fn: _Function(fn)


def _passthrough(*a, **k):
    return lambda fn: fn


def fake_modal():
    modal = types.ModuleType("modal")
    modal.Image, modal.Volume, modal.Dict, modal.App = _Image, _Volume, _Dict, _App
    modal.Secret = types.SimpleNamespace(from_name=lambda *a, **k: None)
    modal.Function = types.SimpleNamespace(from_name=lambda *a, **k: None)
    modal.concurrent = modal.web_server = modal.asgi_app = _passthrough
    return modal


def fake_transformers():
    transformers = types.ModuleType("transformers")
    transformers.AutoTokenizer = types.SimpleNamespace(from_pretrained=lambda *a, **k: None)
    return transformers


# ---- the app ------------------------------------------------------------------------------------------------

def build_app(data_dir):
    """modal_app.api() with the fakes: returns (FastAPI app, the Writer it uses, the latest Dict)."""
    saved = {name: sys.modules.get(name) for name in ("modal", "transformers", "modal_app")}
    sys.modules["modal"], sys.modules["transformers"] = fake_modal(), fake_transformers()
    os.environ.update(SAYSO_API_TOKEN=TOKEN, GLIMMER_KEY="g", META_API_KEY="m", SAYSO_GPU="off")  # read per request
    import styles
    import writer
    styles.DATA = Path(data_dir)
    styles.STYLES = styles.DATA / "styles"
    captured = {}
    real_init = writer.Writer.__init__

    def init(self, *a, **k):
        real_init(self, *a, **k)
        captured["writer"] = self
    writer.Writer.__init__ = init
    try:
        sys.modules.pop("modal_app", None)
        modal_app = importlib.import_module("modal_app")
        web = modal_app.api()
    finally:
        writer.Writer.__init__ = real_init
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    return web, captured["writer"], modal_app.latest


class FakeSpark:
    def __init__(self):
        self.calls = []

    async def __call__(self, system, user, key, max_tokens=3000, **_):
        self.calls.append(key)
        if key == "summary":
            return {"summary": "asks about plans at 8", "situation": "invitation", "audience": "friends",
                    "options": [{"act": "agree", "draft": "го"}, {"act": "refuse", "draft": "не могу"}]}
        if key == "rule":
            return {"rule": ""}
        return {"text": "го в 8", "variants": ["давай в 8"]}


@unittest.skipUnless(HAVE_FASTAPI, "fastapi, httpx and python-multipart are not installed (see the docstring)")
class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        import styles
        cls.saved_paths = styles.DATA, styles.STYLES, styles.on_write
        cls.saved_env = dict(os.environ)
        cls.web, cls.writer, cls.latest = build_app(cls.tmp.name)
        cls.writer.spark = FakeSpark()
        # a made-up style (the main one needs the author's private pairs); every generation request names it
        from test_writer_fakes import make_style
        cls.style = make_style()
        cls.client = TestClient(cls.web, raise_server_exceptions=False)
        cls.auth = {"Authorization": f"Bearer {TOKEN}"}

    @classmethod
    def tearDownClass(cls):
        import styles
        styles.DATA, styles.STYLES, styles.on_write = cls.saved_paths
        os.environ.clear()
        os.environ.update(cls.saved_env)
        cls.tmp.cleanup()

    def routes(self):
        from fastapi.routing import APIRoute
        return [(method, route.path) for route in self.web.routes if isinstance(route, APIRoute)
                for method in route.methods]

    # ---- auth ----------------------------------------------------------------------------------------------

    def test_every_route_needs_the_token(self):
        routes = self.routes()
        self.assertGreaterEqual(len(routes), 13, routes)
        for method, path in routes:
            url = path.replace("{style_id}", "main")
            for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": TOKEN},
                            {"Authorization": f"bearer {TOKEN}"}, {"Authorization": f"Bearer {TOKEN} "}):
                response = self.client.request(method, url, headers=headers, json={})
                self.assertEqual(response.status_code, 401, (method, path, headers))

    def test_non_ascii_token_is_401_not_500(self):
        response = self.client.post("/rewrite", headers={"Authorization": "Bearer тест".encode()},
                                    json={"text": "x"})
        self.assertEqual(response.status_code, 401)

    def test_no_docs_or_openapi(self):
        for path in ("/docs", "/redoc", "/openapi.json"):
            self.assertIn(self.client.get(path, headers=self.auth).status_code, {401, 404}, path)

    def test_bad_body_is_401_before_parsing(self):
        response = self.client.post("/rewrite", content=b"{not json", headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_upload_is_not_parsed(self):
        from starlette.requests import Request
        parsed = []
        real_form = Request.form

        def form(self, *a, **k):
            parsed.append(True)
            return real_form(self, *a, **k)
        Request.form = form
        try:
            response = self.client.post("/styles", data={"name": "x"}, files={"files": ("a.txt", b"x" * 100_000)})
        finally:
            Request.form = real_form
        self.assertEqual(response.status_code, 401)
        self.assertEqual(parsed, [], "the multipart body was parsed (and spooled) before the token was checked")

    # ---- limits and validation --------------------------------------------------------------------------------

    def test_empty_text_and_instruction_are_422(self):
        self.assertEqual(self.client.post("/rewrite", headers=self.auth, json={"text": "  "}).status_code, 422)
        self.assertEqual(self.client.post("/compose", headers=self.auth, json={"instruction": ""}).status_code, 422)

    def test_text_limits_are_422(self):
        too_long = [("/rewrite", {"text": "x" * 2001}), ("/compose", {"instruction": "x" * 1001}),
                    ("/chat", {"text": "x" * 4001}), ("/feedback", {"answer": "x" * 3001}),
                    ("/learn", {"items": [{"text": "x"}] * 51}), ("/reply", {"messages": "x" * 4001})]
        for path, body in too_long:
            self.assertEqual(self.client.post(path, headers=self.auth, json=body).status_code, 422, path)

    def test_big_screenshot_is_413(self):
        headers = {**self.auth, "Content-Type": "image/png"}
        response = self.client.post(f"/reply?style={self.style}", headers=headers,
                                    content=b"\0" * (4 * 1024 * 1024 + 1))
        self.assertEqual(response.status_code, 413)

    def test_bad_base64_is_422(self):
        response = self.client.post("/reply", headers=self.auth, json={"image": "@@@not base64@@@", "style": self.style})
        self.assertEqual(response.status_code, 422)

    def test_reply_needs_something_to_read(self):
        self.assertEqual(self.client.post("/reply", headers=self.auth, json={"style": self.style}).status_code, 422)

    def test_unknown_style_is_404(self):
        response = self.client.post("/rewrite", headers=self.auth, json={"text": "да", "style": "nosuch"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get("/styles/..%2Fmain", headers=self.auth).status_code, 404)

    def test_main_style_cannot_be_deleted(self):
        self.assertEqual(self.client.delete("/styles/main", headers=self.auth).status_code, 409)

    def test_upload_count_and_size(self):
        response = self.client.post("/styles", headers=self.auth, data={"name": "x"},
                                    files=[("files", (f"{i}.txt", b"x")) for i in range(201)])
        self.assertEqual(response.status_code, 422)

    # ---- the happy paths (fake Spark, GPU off) -------------------------------------------------------------

    def test_rewrite_with_token(self):
        response = self.client.post("/rewrite", headers=self.auth, json={"text": "да, в 8", "format": "nonsense", "style": self.style})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["text"], "го в 8")

    def test_reply_from_messages_stores_only_the_users_side(self):
        response = self.client.post("/reply", headers=self.auth, json={"messages": "- идешь в 8?", "style": self.style})
        self.assertEqual(response.status_code, 200, response.text)
        stored = asyncio.run(self.latest.get.aio("reply"))
        self.assertEqual(set(stored), {"audience", "situation", "replies", "at"})
        self.assertNotIn("asks about plans", str(stored))  # the summary of their messages is not kept
        self.assertEqual(self.client.get("/latest", headers=self.auth).json()["replies"][0]["text"], "го")

    def test_learn_and_feedback(self):
        response = self.client.post("/learn", headers=self.auth,
                                    json={"style": self.style, "items": [{"text": "го https://x.example", "audience": "friends"}]})
        self.assertEqual(response.json(), {"learned": 1, "rules": []})
        response = self.client.post("/feedback", headers=self.auth, json={"answer": "го", "audience": "friends",
                                                                          "liked": True, "style": self.style})
        self.assertEqual(response.status_code, 200)

    def test_create_style_spawns_the_build_in_memory(self):
        _Function.spawned.clear()
        response = self.client.post("/styles", headers=self.auth, data={"name": "Work"},
                                    files={"files": ("WhatsApp Chat - X.txt", b"1/1/24, 10:00 - A: hi")})
        self.assertEqual(response.status_code, 200, response.text)
        name, args, _ = _Function.spawned[-1]
        self.assertEqual(name, "build_style")
        self.assertEqual(args[1], [("WhatsApp Chat - X.txt", b"1/1/24, 10:00 - A: hi")])
        import styles
        self.assertEqual(sorted(p.name for p in styles.folder(args[0]).iterdir()), ["meta.json"])

    def test_patch_me_only_while_waiting(self):
        import styles
        meta = styles.create("Pending")
        url = f"/styles/{meta['id']}"
        self.assertEqual(self.client.patch(url, headers=self.auth, json={"me": "A"}).status_code, 409)
        styles.update(meta["id"], stage="needs_me")
        response = self.client.patch(url, headers=self.auth, json={"me": "A", "chats": {"c": "friends", "d": "boss"}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(styles.meta(meta["id"])["chats"], {"c": "friends"})


if __name__ == "__main__":
    unittest.main()
