"""What the SaySo API does with a request: read the chat, think like the user, write like the user.

  read     — Muse Spark 1.3 (Meta API) reads a screenshot or pasted messages and returns the same
             {audience, situation, summary} the model was trained on (summary = 20–30 neutral English words
             about the other person's latest messages; nothing is stored)
  rewrite  — the user's draft → their own wording            (v4, user channel)
  compose  — an instruction → the message they'd write          (v4, user channel)
  reply    — Muse Spark, which sees the whole chat and gets the user's style profile (how they usually react
             per audience × situation, how long and how they write), drafts three replies the way this user would
             mean them; v4 rewrites each in the user's voice (its strongest task) and the candidate closest to the
             user's statistics wins. While the GPU is cold, Spark's drafts are returned at once (styled: false).
             Without a chat (summary only), v4 thinks (act · tone · gist) and writes by itself.

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

from situations import ACTS, DETAIL_SYSTEM, SITUATIONS  # noqa: E402
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
DRAFT_WORDS = 40
REWRITE_TEMPERATURE = 0.8  # rewriting a given draft: less drift into made-up words than free writing at 1.0


def read_system(profile_text):
    return DETAIL_SYSTEM.replace(
        'Return JSON only: {"summary": "<text>"}.',
        'Return JSON only: {"chat_name": "<text>", "audience": "<audience>", "situation": "<situation>", '
        '"summary": "<text>", "options": [{"act": "<act>", "draft": "<text>"}, {...}, {...}]}.\n'
        "The user's own messages are on the right (or marked 'me'); describe only the other person's messages.\n"
        "chat_name — the chat title at the top of the screenshot, exactly as written, or empty.\n"
        f"audience — who the other person is to the user, one of: {', '.join(AUDIENCES)}.\n"
        "situation — what the other person's latest messages do, one of:\n"
        + "\n".join(f"- {k}: {v}" for k, v in SITUATIONS.items()) + "\n"
        "options — three replies the user could send now to the other person's LATEST messages. Think like THIS user "
        "(profile below): the first option is what they would most likely do here, the other two are different moves "
        "they also make. act — one of: " + ", ".join(ACTS) + ". draft — the reply itself in the language of the chat, "
        "as ONE message without line breaks, about as long as this user usually writes to that audience, casual and "
        "concrete to this chat, following their case and punctuation habits, no names.\n\n"
        "The user's profile, from their own chats (how they write, not who they are):\n" + profile_text,
    ).replace("Reasoning strength: low\n", "")


def profile_text(profile):
    """data/style_profile.json → a few lines Spark can use to think like the user."""
    share = lambda shares: ", ".join(f"{k} {v:.0%}" for k, v in shares.items())
    lines = []
    for audience, p in profile.items():
        lines.append(f"- {audience}: usually ~{p['median_chars']:.0f} characters; lowercase starts {p['lowercase_start']:.0%}, "
                     f"ends with punctuation {p['ends_with_punctuation']:.0%}, laughter {p['laughter']:.0%}, "
                     f"swearing {p['swear']:.0%}. Moves: {share(p['acts'])}. Tones: {share(p['tones'])}.")
        for situation, c in list(p.get("situations", {}).items())[:5]:
            lines.append(f"  · {situation}: {share(dict(list(c['acts'].items())[:3]))}; "
                         f"{share(dict(list(c['tones'].items())[:2]))}; ~{c['median_chars']:.0f} chars")
    return "\n".join(lines)


STYLE_SYSTEM = """You write chat messages for one specific user, in their own voice, so that their friends could not
tell it was not them. Use their profile below: length, case, punctuation, slang and swearing habits for that audience.
Keep the full meaning: every fact (when, what, who, how much, why) and every request, refusal or question
stays, only the wording changes. Their usual length is for short thoughts; a draft with several points stays complete
(write it as one longer message rather than dropping anything). Write in the language of the input. One message, no line breaks, no names, nothing else.
Return JSON only: {{"text": "<the message>"}}.

The user's profile, from their own chats (how they write, not who they are):
{profile}"""


def one_message(text):
    """The user often sends a reply as several short lines; a suggestion is easier to use as one message."""
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


class Unavailable(Exception):
    """The GPU is cold (warming started) or a model API failed; the API maps it to 503/502."""

    def __init__(self, status, detail):
        super().__init__(detail)
        self.status, self.detail = status, detail


def clean(text):
    return CONTROL.sub("", text).strip()


class Writer:
    def __init__(self, client, glimmer_url, token, tokenizer, meta_key, gpu="modal"):
        self.client, self.url, self.token, self.meta_key = client, glimmer_url.rstrip("/"), token, meta_key
        self.tokenizer = tokenizer
        # The user's own chat → audience labels (private volume): a chat title read from a screenshot beats a guess.
        path = ROOT / "data" / "audiences.json"
        chats = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.chats = {name.casefold().strip(): audience for name, audience in chats.items() if audience in AUDIENCES}
        path = ROOT / "data" / "style_profile.json"
        profile = profile_text(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else ""
        self.read_system = read_system(profile)
        self.style_system = STYLE_SYSTEM.format(profile=profile)
        self.gpu = gpu  # "modal", or "off": never touch the GPU (the user's model), Muse Spark writes alone
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
        if self.gpu == "off":
            raise Unavailable(503, "the user's model is offline")
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

    async def is_warm(self):
        """Like ensure_warm, but answers instead of failing (a cold GPU starts waking up)."""
        try:
            await self.ensure_warm()
            return True
        except Unavailable:
            return False

    async def wake(self):
        try:
            await self.client.get(f"{self.url}/v1/models", timeout=900, headers={"Authorization": f"Bearer {self.token}"})
        except Exception:
            pass

    async def complete(self, prompts, n=1, max_tokens=160, temperature=None):
        """One batched call to our vLLM; returns n texts per prompt (choices are numbered prompt × n + j)."""
        response = await self.client.post(
            f"{self.url}/v1/completions", timeout=120,
            headers={"Authorization": f"Bearer {self.token}"},
            json={"model": ADAPTER, "prompt": prompts, "n": n, "max_tokens": max_tokens,
                  **SAMPLING, **({"temperature": temperature} if temperature else {}),
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

    async def spark(self, system, user, key, max_tokens=3000):
        """One Muse Spark call that returns a JSON object (one retry, then 502)."""
        for attempt in range(2):
            try:
                response = await self.client.post(
                    META_URL, timeout=30, headers={"Authorization": f"Bearer {self.meta_key}"},
                    json={"model": "muse-spark-1.3", "reasoning_effort": "low", "max_tokens": max_tokens,
                          "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
                response.raise_for_status()
                text = response.json()["choices"][0]["message"].get("content") or ""
                match = re.search(r"\{.*\}", text, re.S)
                label = json.loads(match.group(0)) if match else {}
            except Exception:  # 429/5xx, timeout, non-JSON
                label = {}
            if isinstance(label, dict) and isinstance(label.get(key), str) and label[key].strip():
                return label
            await asyncio.sleep(1)
        raise Unavailable(502, "Muse Spark did not answer")

    async def styled(self, task, field, text, audience, situation):
        if not await self.is_warm():  # the user's model is asleep or off: Muse Spark writes in their style alone
            ask = {"rewrite": "Rewrite this draft the way the user would write it",
                   "compose": "Write the message the user would send for this instruction"}[task]
            label = await self.spark(self.style_system, f"{ask} to their {audience} ({situation}):\n{clean(text)}", "text")
            out = one_message(" ".join(clean(label["text"]).split()[:DRAFT_WORDS * 2]))
            return {"text": out, "candidates": [out], "styled": False}
        prompt = self.prompt(audience, situation, task, field, text) + REPLY
        candidates = (await self.complete([prompt], n=CANDIDATES + 2))[0]
        return {"text": self.best(candidates, audience, situation), "candidates": candidates, "styled": True}

    async def rewrite(self, text, audience, situation="other"):
        return await self.styled("rewrite", "draft", text, audience, situation)

    async def compose(self, instruction, audience, situation="other"):
        return await self.styled("compose", "instruction", instruction, audience, situation)

    # ---- reply: think like the user, then write ---------------------------------------------------

    def cell(self, audience, situation):
        cell = self.moves.get((audience, situation), [])
        return cell if len(cell) >= MIN_CELL else self.moves.get((audience, None)) or [("react", "neutral")]

    def tone_for(self, act, audience, situation):
        """The user's most common tone for this act here (style profile), else for this audience."""
        tones = (Counter(t for a, t in self.cell(audience, situation) if a == act)
                 or Counter(t for a, t in self.moves.get((audience, None), []) if a == act))
        return tones.most_common(1)[0][0] if tones else "neutral"

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

    async def reply(self, summary, audience, situation, options=None):
        """options = Spark's drafts [{act, draft}] (it saw the chat and the profile): v4 rewrites them in the user's
        voice, or they come back as they are while the GPU is cold. Without options the model thinks by itself."""
        if options:
            styled = await self.is_warm()
            groups = [[o["draft"]] for o in options]
            if styled:
                prompts = [self.prompt(audience, situation, "rewrite", "draft", o["draft"]) + REPLY for o in options]
                groups = await self.complete(prompts, n=CANDIDATES + 2, temperature=REWRITE_TEMPERATURE)
            replies = []
            for option, group in zip(options, groups):
                text = self.best(group, audience, situation) if styled else option["draft"]
                replies.append({"intent": option["act"], "tone": self.tone_for(option["act"], audience, situation),
                                "thought": f"act: {option['act']} · draft: {option['draft']}", "styled": styled,
                                "text": one_message(text), "parts": [l for l in text.splitlines() if l.strip()]})
            return replies
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
            options.append({"intent": act, "tone": tone, "thought": thoughts[i][group.index(text)], "styled": True,
                            "text": one_message(text), "parts": [l for l in text.splitlines() if l.strip()]})
        return options

    # ---- reading the chat (Muse Spark, nothing stored) --------------------------------------------

    async def read(self, image=None, image_type="image/jpeg", messages=None, audience=None, instruction=""):
        """→ (context, options): context = {audience, situation, summary}; options = up to 3 {act, draft}.
        instruction: what the user wants to say or extra context ("politely decline, I'm busy")."""
        ask = "Describe this chat screenshot."
        if instruction and instruction.strip():
            ask += (f"\nThe user's own note about how to reply: \"{clean(instruction)[:300]}\". All three options "
                    "must follow it (use it as context if it is not an instruction); vary wording, tone and act.")
        if image is not None:
            content = [{"type": "text", "text": ask},
                       {"type": "image_url", "image_url": {"url": f"data:{image_type};base64," + base64.b64encode(image).decode()}}]
        else:
            content = ask.replace("Describe this chat screenshot.", "Messages (latest last):\n" + clean(messages))
        label = await self.spark(self.read_system, content, "summary")
        # The summary goes into our prompt: plain text only, bounded, no template tokens.
        summary = " ".join(clean(label["summary"]).split()[:SUMMARY_WORDS])
        situation = label.get("situation") if label.get("situation") in SITUATIONS else "other"
        guessed = label.get("audience") if label.get("audience") in AUDIENCES else "friends"
        known = self.chats.get(str(label.get("chat_name") or "").casefold().strip())  # the title is not kept
        options = []
        for option in label.get("options") or []:
            if isinstance(option, dict) and option.get("act") in ACTS and isinstance(option.get("draft"), str):
                draft = one_message(" ".join(clean(option["draft"]).split()[:DRAFT_WORDS]))
                if draft and option["act"] not in {o["act"] for o in options}:
                    options.append({"act": option["act"], "draft": draft})
        context = {"audience": audience or known or guessed, "situation": situation, "summary": summary}
        return context, options[:3]
