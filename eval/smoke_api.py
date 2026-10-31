"""Smoke test for the deployed API, with made-up inputs only (nothing is written to disk).

  .venv/bin/python eval/smoke_api.py                 # CPU only: auth and validation, never wakes the GPU
  .venv/bin/python eval/smoke_api.py --gpu [--show]  # also warms the GPU and checks /rewrite /compose /reply
  .venv/bin/python eval/smoke_api.py --gpu --vision tests/fixtures/chat.png
  .venv/bin/python eval/smoke_api.py --spark [--show]  # Muse Spark only (GPU off): formats, chat, building a style
"""

import argparse
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent

try:  # python.org builds on macOS ship without root certificates
    import certifi
    VERIFY = certifi.where()
except ImportError:
    VERIFY = True


def env():
    pairs = (line.strip().split("=", 1) for line in (ROOT / ".env").open() if "=" in line and not line.startswith("#"))
    return dict(pairs)


class Smoke:
    def __init__(self, show):
        e = env()
        self.url, self.glimmer = e["SAYSO_API_URL"].rstrip("/"), e["SAYSO_GLIMMER_URL"].rstrip("/")
        self.app_token = e["SAYSO_API_TOKEN"]
        self.client = httpx.Client(verify=VERIFY, timeout=120, follow_redirects=True,
                                   headers={"Authorization": f"Bearer {self.app_token}"})
        self.show, self.failed = show, 0

    def check(self, name, ok, detail=""):
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
        self.failed += not ok

    def cpu(self):
        for method, path in (("post", "/rewrite"), ("post", "/compose"), ("post", "/reply"), ("get", "/warmup"),
                             ("post", "/chat"), ("post", "/feedback"), ("get", "/styles"), ("post", "/styles"),
                             ("get", "/styles/main"), ("delete", "/styles/main")):
            r = getattr(httpx, method)(self.url + path, verify=VERIFY, headers={"Authorization": "Bearer wrong"}, timeout=60)
            self.check(f"{path} rejects a wrong token", r.status_code == 401, str(r.status_code))
        r = self.client.post(self.url + "/reply", json={})
        self.check("/reply rejects an empty body", r.status_code == 422, str(r.status_code))
        r = self.client.post(self.url + "/rewrite", json={"text": "x" * 3000})
        self.check("/rewrite rejects a long text", r.status_code == 422, str(r.status_code))
        r = self.client.delete(self.url + "/styles/main")
        self.check("the main style can't be deleted", r.status_code == 409, str(r.status_code))
        r = self.client.get(self.url + "/styles/nope")
        self.check("an unknown style is 404", r.status_code == 404, str(r.status_code))
        r = self.client.get(self.url + "/docs")
        self.check("/docs is closed", r.status_code == 404, str(r.status_code))

    def warm(self, minutes=12):
        started = time.monotonic()
        while time.monotonic() - started < minutes * 60:
            r = self.client.post(self.url + "/rewrite", json={"text": "ок", "audience": "friends"})
            if r.status_code != 503:
                self.check("GPU warm", r.status_code == 200, f"{time.monotonic() - started:.0f}s")
                return r.status_code == 200
            time.sleep(15)
        self.check("GPU warm", False, "timeout")
        return False

    def timed(self, name, budget, request):
        started = time.monotonic()
        r = request()
        seconds = time.monotonic() - started
        self.check(name, r.status_code == 200 and seconds < budget, f"{r.status_code} {seconds:.1f}s (budget {budget}s)")
        if r.status_code == 200 and self.show:
            print("      ", r.json())
        return r.json() if r.status_code == 200 else None

    def gpu(self, vision):
        # The app token must not open the model server directly (vLLM has its own key).
        r = httpx.get(self.glimmer + "/v1/models", verify=VERIFY, headers={"Authorization": f"Bearer {self.app_token}"},
                      timeout=900, follow_redirects=True)
        self.check("app token can't reach vLLM", r.status_code == 401, str(r.status_code))
        if not self.warm():
            return
        self.timed("/rewrite", 3, lambda: self.client.post(self.url + "/rewrite", json={
            "text": "Привет, сегодня не получится, давай завтра?", "audience": "friends", "situation": "invitation"}))
        self.timed("/compose", 3, lambda: self.client.post(self.url + "/compose", json={
            "instruction": "Скажи что задержишься на полчаса из-за пробок", "audience": "partner", "situation": "logistics"}))
        out = self.timed("/reply summary", 5, lambda: self.client.post(self.url + "/reply", json={
            "summary": "Asks if the user is free tonight to join friends at the cinema at 8.",
            "situation": "invitation", "audience": "friends"}))
        if out:
            intents = [r["intent"] for r in out["replies"]]
            self.check("3 different intents with thoughts", len(set(intents)) == 3
                       and all(r["thought"].startswith("act:") for r in out["replies"]), str(intents))
        self.timed("/reply messages", 10, lambda: self.client.post(self.url + "/reply", json={
            "messages": "- ты опять забыл мне позвонить\n- я весь вечер ждала", "audience": "partner"}))
        if vision:
            self.timed("/reply screenshot", 10, lambda: self.client.post(
                self.url + "/reply", content=Path(vision).read_bytes(),
                headers={"Authorization": f"Bearer {self.app_token}", "Content-Type": "image/png"}))


    def spark(self):
        """Muse Spark paths only (the API runs with SAYSO_GPU=off): formats, chat with feedback, building a style."""
        draft = "Привет, сегодня не получится прийти, давай перенесём на завтра, я освобожусь после шести"
        for format in ("message", "series", "official", "email"):
            out = self.timed(f"/rewrite {format}", 20, lambda: self.client.post(self.url + "/rewrite", json={
                "text": draft, "audience": "friends", "format": format}))
            if out:
                ok = len(out["parts"]) >= 2 if format == "series" else len(out["parts"]) == 1
                self.check(f"{format} shape", ok and len(out["audiences"]) == 3, str(len(out["parts"])))
        first = self.timed("/chat write", 20, lambda: self.client.post(self.url + "/chat", json={
            "mode": "write", "text": "скажи что опоздаю минут на 20 из-за пробок", "audience": "partner"}))
        if first:
            fixed = self.timed("/chat feedback", 20, lambda: self.client.post(self.url + "/chat", json={
                "mode": "write", "text": "скажи что опоздаю минут на 20 из-за пробок", "audience": "partner",
                "history": [{"answer": first["text"], "feedback": "короче и без извинений"}]}))
            if fixed:
                self.check("the revision is shorter", len(fixed["text"]) <= len(first["text"]),
                           f"{len(first['text'])} → {len(fixed['text'])}")
        self.build_style()

    def build_style(self):
        fixture = ROOT / "tests" / "fixtures" / "whatsapp_fake.txt"
        r = self.client.post(self.url + "/styles", data={"name": "Smoke test"},
                             files=[("files", ("WhatsApp Chat - Mira.txt", fixture.read_bytes(), "text/plain"))])
        self.check("POST /styles", r.status_code == 200, str(r.status_code))
        if r.status_code != 200:
            return
        style_id = r.json()["id"]
        try:
            meta = self.wait(style_id, {"needs_me", "failed"})
            self.check("needs_me with participants", meta.get("stage") == "needs_me" and "Алекс" in
                       (meta.get("participants") or []), str(meta.get("stage")))
            r = self.client.patch(f"{self.url}/styles/{style_id}", json={"me": "Алекс", "chats": meta.get("chats")})
            self.check("PATCH me", r.status_code == 200, str(r.status_code))
            meta = self.wait(style_id, {"ready", "failed"}, minutes=10)
            self.check("style ready", meta.get("stage") == "ready", f"{meta.get('stage')} {meta.get('error') or ''}")
            print("      scores:", meta.get("scores"))
            out = self.timed("/rewrite in the new style", 20, lambda: self.client.post(self.url + "/rewrite", json={
                "text": "Да, давай, во сколько встречаемся?", "audience": "friends", "style": style_id}))
        finally:
            r = self.client.delete(f"{self.url}/styles/{style_id}")
            self.check("DELETE style", r.status_code == 200, str(r.status_code))

    def wait(self, style_id, stages, minutes=3):
        started, meta = time.monotonic(), {}
        while time.monotonic() - started < minutes * 60:
            meta = self.client.get(f"{self.url}/styles/{style_id}").json()
            if meta.get("stage") in stages:
                return meta
            time.sleep(3)
        return meta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--vision", help="a made-up chat screenshot (PNG)")
    parser.add_argument("--show", action="store_true", help="print the generated replies")
    parser.add_argument("--spark", action="store_true", help="formats, chat and a style build (Muse Spark only)")
    args = parser.parse_args()
    smoke = Smoke(args.show)
    smoke.cpu()
    if args.spark:
        smoke.spark()
    if args.gpu:
        smoke.gpu(args.vision)
    print(f"\n{smoke.failed} failed")
    sys.exit(1 if smoke.failed else 0)


if __name__ == "__main__":
    main()
