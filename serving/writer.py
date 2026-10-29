"""What the SaySo API does with a request: read the chat, think like the user, write like the user.

  read     — Muse Spark 1.3 (Meta API) reads a screenshot or pasted messages and returns the same
             {audience, situation, summary} the model was trained on (summary = 20–30 neutral English words
             about the other person's latest messages; nothing is stored)
  rewrite  — the user's draft → their own wording            (v4, user channel)
  compose  — an instruction → the message they'd write          (v4, user channel)
  reply    — summary → three options with different intents. For each intent the thought is prefilled with
             an act and a tone from the user's own shares for that audience × situation (style profile),
             v4 writes the gist and the reply, and the candidate closest to the user's statistics wins.

Runs inside the Modal `api` container: the user's data (pairs, lexicon, profile) is on the private volume,
mounted so that pipeline/ modules find it at their usual data/ path.
"""

import asyncio
import base64
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "pipeline"), str(ROOT / "eval")]

from situations import DETAIL_SYSTEM, SITUATIONS  # noqa: E402
from style_stats import MIN_CELL, StyleStats  # noqa: E402

SYSTEM = "You write chat messages exactly the way this user writes them."
REASONING = "Reasoning strength: low."
REPLY = " to=user<|message|>"
THOUGHT = " to=self<|message|>"
AFTER_THOUGHT = "<|eom|><|start|>assistant to=user<|message|>"
ADAPTER = "v4"
AUDIENCES = ["partner", "friends", "family", "elder_informal"]  # the audiences the model was trained on
CANDIDATES = 3
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 64}
KAZAKH = re.compile("[әғқңөұүһі]", re.I)  # v4 sometimes drifts into garbled Kazakh letters; the user rarely writes them
CONTROL = re.compile(r"<\|[^|<>]{1,30}\|>")  # template tokens: never let user text or Spark's summary inject them
SUMMARY_WORDS = 45

# The three options for /reply: the user's most likely move first, then contrasting ones that fit the situation.
CONTRASTS = {
    "invitation": ["agree", "refuse", "joke"],
    "request": ["agree", "refuse", "ask_back"],
    "logistics": ["agree", "ask_back", "plan"],
    "sadness": ["support", "comfort", "joke"],
    "conflict": ["apologize", "argue", "joke"],
    "apology": ["agree", "argue", "joke"],
    "affection": ["affection", "tease", "joke"],
    "good_news": ["react", "ask_back", "joke"],
    "thanks": ["react", "joke", "affection"],
    "joke": ["joke", "tease", "react"],
}
DEFAULT_CONTRASTS = ["agree", "ask_back", "joke"]

META_URL = "https://api.meta.ai/v1/chat/completions"
READ_SYSTEM = DETAIL_SYSTEM.replace(
    'Return JSON only: {"summary": "<text>"}.',
    'Return JSON only: {"audience": "<audience>", "situation": "<situation>", "summary": "<text>"}.\n'
    "The user's own messages are on the right (or marked 'me'); describe only the other person's messages.\n"
    f"audience — who the other person is to the user, one of: {', '.join(AUDIENCES)}.\n"
    "situation — what the other person's latest messages do, one of:\n"
    + "\n".join(f"- {k}: {v}" for k, v in SITUATIONS.items()),
).replace("Reasoning strength: low\n", "")


class Unavailable(Exception):
    """The GPU is cold (warming started) or a model API failed; the API maps it to 503/502."""

    def __init__(self, status, detail):
        super().__init__(detail)
        self.status, self.detail = status, detail


def clean(text):
    return CONTROL.sub("", text).strip()


class Writer:
    def __init__(self, client, glimmer_url, token, tokenizer, meta_key):
        self.client, self.url, self.token, self.meta_key = client, glimmer_url.rstrip("/"), token, meta_key
        self.tokenizer = tokenizer
        self.warm_until = 0.0
        self.warming = None
        self.stats = StyleStats.from_pairs("pairs_v2")
        self.moves = defaultdict(list)  # (audience, situation) and (audience, None) → the user's real (act, tone)
        for line in (ROOT / "data" / "pairs_v4" / "train.jsonl").open(encoding="utf-8"):
            meta = json.loads(line)["meta"]
            if "act" in meta:
                self.moves[(meta["audience"], meta["situation"])].append((meta["act"], meta["tone"]))
                self.moves[(meta["audience"], None)].append((meta["act"], meta["tone"]))

    # ---- prompts and generation -------------------------------------------------------------------

    def prompt(self, audience, situation, task, field, text):
        user = f"audience: {audience} · situation: {situation}\ntask: {task}\n{field}: {clean(text)}"
        rendered = self.tokenizer.apply_chat_template(
            [{"role": "system", "content": f"{SYSTEM}\n{REASONING}"}, {"role": "user", "content": user}],
            tokenize=False, add_generation_prompt=True)
        return rendered.removeprefix(self.tokenizer.bos_token or "")

    async def ensure_warm(self):
        """Fail fast while the H100 is cold: start waking it in the background and tell the app to retry,
        instead of holding the request for minutes (iOS intents and the keyboard can't wait that long)."""
        if time.monotonic() < self.warm_until:
            return
        try:
            response = await self.client.get(f"{self.url}/v1/models", timeout=4,
                                             headers={"Authorization": f"Bearer {self.token}"})
            if response.status_code == 200:
                self.warm_until = time.monotonic() + 60
                return
        except Exception:
            pass
        if self.warming is None or self.warming.done():
            self.warming = asyncio.create_task(self.wake())
        raise Unavailable(503, "warming up, retry in a minute")

    async def wake(self):
        try:
            await self.client.get(f"{self.url}/v1/models", timeout=900, headers={"Authorization": f"Bearer {self.token}"})
        except Exception:
            pass

    async def complete(self, prompts, n=1, max_tokens=160):
        """One batched call to our vLLM; returns n texts per prompt (choices are numbered prompt × n + j)."""
        response = await self.client.post(
            f"{self.url}/v1/completions", timeout=120,
            headers={"Authorization": f"Bearer {self.token}"},
            json={"model": ADAPTER, "prompt": prompts, "n": n, "max_tokens": max_tokens, **SAMPLING,
                  "stop": ["<|eot|>", "<|eom|>"], "skip_special_tokens": False})
        if response.status_code != 200:
            raise Unavailable(502, f"model error {response.status_code}")
        self.warm_until = time.monotonic() + 60
        choices = sorted(response.json()["choices"], key=lambda c: c["index"])
        texts = [c["text"].split("<|")[0].strip() for c in choices]  # cut any other control token
        return [texts[i * n:(i + 1) * n] for i in range(len(prompts))]

    def best(self, candidates, audience, situation):
        usable = [c for c in candidates if c.strip() and not KAZAKH.search(c)] or [c for c in candidates if c.strip()]
        return self.stats.pick(usable, audience, situation) if usable else ""

    async def styled(self, task, field, text, audience, situation):
        await self.ensure_warm()
        prompt = self.prompt(audience, situation, task, field, text) + REPLY
        candidates = (await self.complete([prompt], n=CANDIDATES + 2))[0]
        return {"text": self.best(candidates, audience, situation), "candidates": candidates}

    async def rewrite(self, text, audience, situation="other"):
        return await self.styled("rewrite", "draft", text, audience, situation)

    async def compose(self, instruction, audience, situation="other"):
        return await self.styled("compose", "instruction", instruction, audience, situation)

    # ---- reply: think like the user, then write ---------------------------------------------------

    def intents(self, audience, situation):
        cell = self.moves.get((audience, situation), [])
        cell = cell if len(cell) >= MIN_CELL else self.moves.get((audience, None)) or [("react", "neutral")]
        likely = Counter(a for a, _ in cell).most_common(1)[0][0]
        acts = [likely] + [a for a in CONTRASTS.get(situation, DEFAULT_CONTRASTS) if a != likely]
        moves = []
        for act in acts[:3]:
            tones = (Counter(t for a, t in cell if a == act)
                     or Counter(t for a, t in self.moves.get((audience, None), []) if a == act))
            moves.append((act, tones.most_common(1)[0][0] if tones else "neutral"))
        return moves

    async def reply(self, summary, audience, situation):
        await self.ensure_warm()
        base = self.prompt(audience, situation, "reply", "incoming", summary) + THOUGHT
        moves = self.intents(audience, situation)
        heads = [f"act: {act} · tone: {tone} · gist:" for act, tone in moves]
        gists = await self.complete([base + h for h in heads], n=CANDIDATES, max_tokens=60)
        thoughts = [[f"{h} {g}" for g in group] for h, group in zip(heads, gists)]
        flat = [t for group in thoughts for t in group]
        replies = await self.complete([base + t + AFTER_THOUGHT for t in flat])
        options = []
        for i, (act, tone) in enumerate(moves):
            group = [r[0] for r in replies[i * CANDIDATES:(i + 1) * CANDIDATES]]
            text = self.best(group, audience, situation)
            options.append({"intent": act, "tone": tone, "thought": thoughts[i][group.index(text)], "text": text})
        return options

    # ---- reading the chat (Muse Spark, nothing stored) --------------------------------------------

    async def read(self, image=None, image_type="image/jpeg", messages=None, audience=None):
        if image is not None:
            content = [{"type": "text", "text": "Describe this chat screenshot."},
                       {"type": "image_url", "image_url": {"url": f"data:{image_type};base64," + base64.b64encode(image).decode()}}]
        else:
            content = "Messages (latest last):\n" + clean(messages)
        label = {}
        for attempt in range(2):
            try:
                response = await self.client.post(
                    META_URL, timeout=30, headers={"Authorization": f"Bearer {self.meta_key}"},
                    json={"model": "muse-spark-1.3", "reasoning_effort": "low", "max_tokens": 3000,
                          "messages": [{"role": "system", "content": READ_SYSTEM}, {"role": "user", "content": content}]})
                response.raise_for_status()
                text = response.json()["choices"][0]["message"].get("content") or ""
                match = re.search(r"\{.*\}", text, re.S)
                label = json.loads(match.group(0)) if match else {}
            except Exception:  # 429/5xx, timeout, non-JSON: one retry, then 502
                label = {}
            if isinstance(label, dict) and isinstance(label.get("summary"), str) and label["summary"].strip():
                break
            await asyncio.sleep(1)
        else:
            raise Unavailable(502, "could not read the chat")
        # The summary goes into our prompt: plain text only, bounded, no template tokens.
        summary = " ".join(clean(label["summary"]).split()[:SUMMARY_WORDS])
        situation = label.get("situation") if label.get("situation") in SITUATIONS else "other"
        guessed = label.get("audience") if label.get("audience") in AUDIENCES else "friends"
        return {"audience": audience or guessed, "situation": situation, "summary": summary}
