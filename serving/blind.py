"""Blind test v3 on the API: friends open a link, answer «Человек» / «ИИ» per message, the page posts the answers here.

GET  /blind/{test_id}            the page (no auth: the id is long and random, the page holds no key)
POST /blind/{test_id}/answers    {sid, name?, answers: ["H" | "A", …]} → stored in <dir>/<id>/responses.jsonl
                                 (no auth; rate-limited, size-capped, junk rejected; no IP or headers are stored)
GET  /blind/{test_id}/responses  the stored responses (bearer token, like every other route)

`eval/blind_test.py publish` puts <dir>/<id>/test.html and questions.json (public: what the page shows, no key) on the
volume; the key stays on the owner's Mac. Mounted as a sub-app so the main app's token dependency doesn't apply to the
two public routes; TokenGate in modal_app.py lets exactly those two through (`public`).
"""

import json
import re
import secrets
import threading
import time
import unicodedata
from collections import defaultdict, deque
from pathlib import Path

TEST_ID = re.compile(r"[A-Za-z0-9_-]{20,64}")
SID = re.compile(r"[A-Za-z0-9_-]{8,40}")
PUBLIC = re.compile(r"/blind/([A-Za-z0-9_-]{20,64})(/answers)?/?")
MAX_BODY = 8 * 1024  # an answer is ~150 bytes
MAX_NAME = 40
MAX_RESPONSES = 400  # per test: a few dozen friends, with resubmits
MAX_FILE = 512 * 1024
PER_IP = (8, 10 * 60)  # 8 posts per 10 minutes from one address
PER_TEST = (120, 60 * 60)  # 120 posts per hour to one test
CHOICES = {"H", "A"}  # «Человек» / «ИИ»


def public(method, path):
    """Whether TokenGate lets this request through without the token: the page and the answer post, nothing else."""
    match = PUBLIC.fullmatch(path or "")
    if not match:
        return False
    return (method == "GET" and not match.group(2)) or (method in ("POST", "OPTIONS") and bool(match.group(2)))


def clean_name(value):
    """An optional nickname: printable, one line, ≤ 40 chars."""
    if not isinstance(value, str):
        return ""
    text = "".join(ch for ch in value if unicodedata.category(ch)[0] != "C")
    return " ".join(text.split())[:MAX_NAME]


def parse_answers(raw, n):
    """The posted body → {sid, name, answers} or ValueError. answers: exactly n choices, each "H" or "A"."""
    if len(raw) > MAX_BODY:
        raise ValueError("too large")
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("not JSON") from error
    if not isinstance(body, dict) or set(body) - {"sid", "name", "answers", "v"}:
        raise ValueError("unexpected fields")
    sid, answers = body.get("sid"), body.get("answers")
    if not isinstance(sid, str) or not SID.fullmatch(sid):
        raise ValueError("bad sid")
    if not isinstance(answers, list) or len(answers) != n or any(a not in CHOICES for a in answers):
        raise ValueError(f"answers must be {n} × H or A")
    return {"sid": sid, "name": clean_name(body.get("name")), "answers": answers}


class Limiter:
    """Sliding-window counts per key (one API container, so in memory is enough)."""

    def __init__(self, limit, window, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.hits = defaultdict(deque)

    def allow(self, key):
        now, hits = self.clock(), self.hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        if len(self.hits) > 10_000:  # forget idle keys
            for k in [k for k, v in self.hits.items() if not v]:
                del self.hits[k]
        return True


class Store:
    """<dir>/<test_id>/{test.html, questions.json, responses.jsonl} on the volume."""

    def __init__(self, root, commit=lambda: None, reload=lambda: None, clock=time.monotonic, every=10):
        self.root, self.commit, self._reload, self.clock, self.every = Path(root), commit, reload, clock, every
        self.lock = threading.Lock()
        self.reloaded = None

    def reload(self, force=False):
        """Sees what was published since this container started; at most every 10 s (random ids can't hammer it)."""
        now = self.clock()
        if not force and self.reloaded is not None and now - self.reloaded < self.every:
            return
        self.reloaded = now
        try:
            self._reload()
        except Exception:
            pass

    def folder(self, test_id):
        if not TEST_ID.fullmatch(test_id or ""):
            return None
        return self.root / test_id

    def _file(self, test_id, name):
        folder = self.folder(test_id)
        if folder is None:
            return None
        path = folder / name
        if not path.exists():
            self.reload()  # published after this container started
        return path if path.exists() else None

    def page(self, test_id):
        path = self._file(test_id, "test.html")
        return path.read_bytes() if path else None

    def count(self, test_id):
        """How many questions the published test has, or None if there is no such test."""
        path = self._file(test_id, "questions.json")
        if not path:
            return None
        try:
            return len(json.loads(path.read_text(encoding="utf-8"))["questions"])
        except (ValueError, KeyError, TypeError):
            return None

    def add(self, test_id, answer):
        """Appends one response → False when the test's file is full."""
        path = self.folder(test_id) / "responses.jsonl"
        line = json.dumps({**answer, "at": int(time.time())}, ensure_ascii=False) + "\n"
        with self.lock:
            rows = self.responses(test_id)
            if len(rows) >= MAX_RESPONSES or (path.exists() and path.stat().st_size + len(line) > MAX_FILE):
                return False
            with path.open("a", encoding="utf-8") as f:
                f.write(line)
            self.commit()
        return True

    def responses(self, test_id):
        folder = self.folder(test_id)
        path = folder / "responses.jsonl" if folder else None
        if not path or not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows


def client_ip(request):
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "?")


def app(root, token, commit=lambda: None, reload=lambda: None, clock=time.monotonic):
    """The /blind sub-app. token: a function returning the expected bearer token (read per request)."""
    from fastapi import FastAPI, Header, HTTPException, Request
    from fastapi.responses import JSONResponse, Response

    store = Store(root, commit, reload, clock=clock)
    by_ip, by_test = Limiter(*PER_IP, clock=clock), Limiter(*PER_TEST, clock=clock)
    web = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    web.state.store = store
    cors = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST",
            "Access-Control-Allow-Headers": "Content-Type", "Cache-Control": "no-store"}
    page_headers = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer",
                    "X-Content-Type-Options": "nosniff",
                    "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; "
                                               "style-src 'unsafe-inline'; connect-src 'self'; img-src data:; "
                                               "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"}

    def error(status, detail):
        return JSONResponse({"detail": detail}, status_code=status, headers=cors)

    @web.get("/{test_id}")
    async def page(test_id: str):
        html = store.page(test_id)
        if html is None:
            raise HTTPException(404)
        return Response(html, media_type="text/html; charset=utf-8", headers=page_headers)

    @web.options("/{test_id}/answers")
    async def preflight(test_id: str):  # the page opened as a file posts cross-origin
        return Response(status_code=204, headers=cors)

    @web.post("/{test_id}/answers")
    async def answers(test_id: str, request: Request):
        declared = request.headers.get("content-length")
        if declared and (not declared.isdigit() or int(declared) > MAX_BODY):
            return error(413, "too large")
        if not by_ip.allow(client_ip(request)):
            return error(429, "too many answers, try again later")
        n = store.count(test_id)
        if n is None:
            return error(404, "no such test")
        if not by_test.allow(test_id):
            return error(429, "too many answers, try again later")
        raw = b""
        async for chunk in request.stream():
            raw += chunk
            if len(raw) > MAX_BODY:
                return error(413, "too large")
        try:
            answer = parse_answers(raw, n)
        except ValueError as problem:
            return error(422, str(problem))
        if not store.add(test_id, answer):
            return error(507, "this test has all the answers it can take")
        return JSONResponse({"ok": True}, headers=cors)

    @web.get("/{test_id}/responses")
    async def responses(test_id: str, authorization: str | None = Header(None)):
        expected = f"Bearer {token()}".encode()
        if not authorization or not secrets.compare_digest(authorization.encode(), expected):
            raise HTTPException(401)
        if store.folder(test_id) is None or store.count(test_id) is None:
            raise HTTPException(404)
        store.reload(force=True)
        return {"responses": store.responses(test_id)}

    return web
