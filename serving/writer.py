"""What the SaySo API does with a request: read the chat, think like the user, write like the user.

  read     — Muse Spark 1.3 (Meta API) reads a screenshot or pasted messages and returns the same
             {audience, situation, summary} the model was trained on (summary = 20–30 neutral English words
             about the other person's latest messages; nothing is stored), the top 3 audiences, and three drafts
  rewrite  — the user's draft → their own wording            (the style's LoRA, user channel)
  compose  — an instruction → the message they'd write          (the style's LoRA, user channel)
  reply    — Muse Spark, which sees the whole chat and gets the style (how the user usually reacts per
             audience × situation, how long and how they write, their real messages, the rules learned in Chat),
             drafts three replies the way this user would mean them; the style's LoRA rewrites each in the user's
             voice (its strongest task) and the candidate closest to the user's statistics wins. While the GPU is
             cold or the style has no LoRA yet, Spark's drafts are returned at once (styled: false).
             Without a chat (summary only), the main style's v4 thinks (act · tone · gist) and writes by itself.
  chat     — the same tasks in the app's chat, plus revising an answer from the user's feedback; a feedback that
             says something lasting ("shorter with family") becomes a rule of the style.

Formats: message (one chat message), series (2–4 short messages, sent one by one), official (a polite message for
a work or study chat), email.

Runs inside the Modal `api` container: the user's data (pairs, lexicon, profiles, styles) is on the private
volume, mounted so that pipeline/ modules find it at their usual data/ path.
"""

import asyncio
import base64
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "pipeline"), str(ROOT / "eval"), str(ROOT / "serving")]

import styles  # noqa: E402
from lexicon import words  # noqa: E402
from situations import ACTS, DETAIL_SYSTEM, SITUATIONS  # noqa: E402
from style_stats import MIN_CELL, StyleStats  # noqa: E402

SYSTEM = "You write chat messages exactly the way this user writes them."
REASONING = "Reasoning strength: low."
REPLY = " to=user<|message|>"
THOUGHT = " to=self<|message|>"
AFTER_THOUGHT = "<|eom|><|start|>assistant to=user<|message|>"
AUDIENCES = ["partner", "friends", "family", "elder_informal"]  # the audiences the model was trained on
CANDIDATES = 3
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 64}
KAZAKH = re.compile("[әғқңөұүһі]", re.I)  # v4 sometimes drifts into garbled Kazakh letters; the user rarely writes them
CONTROL = re.compile(r"<\|[^|<>]{1,30}\|>")  # template tokens: never let user text or Spark's summary inject them
SUMMARY_WORDS = 45
EXAMPLES = 8

FORMATS = {
    "message": "as ONE chat message without line breaks, about as long as this user usually writes to that audience",
    "series": "as a short series of 2 to 4 separate chat messages, the way this user splits a thought into several "
              "quick messages; put each message on its own line",
    "official": "as ONE polite message for a work, study or official chat: capitalized sentences, proper punctuation, "
                "no slang, no swearing, no emoji (this overrides their casual habits), but still the user's own plain "
                "wording, not bureaucratic",
    "email": "as a short email: a polite greeting line (\"Здравствуйте, …\" / \"Hello …\"), one or two short "
             "paragraphs, and a sign-off line (\"С уважением\" / \"Best regards\") without a name, each on its own "
             "line; capitalized sentences, proper punctuation, no slang or emoji (this overrides their casual habits), "
             "but the user's own plain wording",
}
FORMAT_WORDS = {"message": 40, "series": 50, "official": 60, "email": 200}
CHAT_FORMATS = {"message", "series"}  # the LoRA was trained on chats: it rewrites only these
FORMAL = {"official", "email"}  # the user's casual examples would pull these back to lowercase chat

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
REWRITE_TEMPERATURE = 0.8  # rewriting a given draft: less drift into made-up words than free writing at 1.0


def read_system(style_text):
    return DETAIL_SYSTEM.replace(
        'Return JSON only: {"summary": "<text>"}.',
        'Return JSON only: {"chat_name": "<text>", "audience": "<audience>", "audiences": ["<audience>", ...], '
        '"situation": "<situation>", "summary": "<text>", '
        '"options": [{"act": "<act>", "draft": "<text>"}, {...}, {...}]}.\n'
        "The user's own messages are on the right (or marked 'me'); describe only the other person's messages.\n"
        "chat_name — the chat title at the top of the screenshot, exactly as written, or empty.\n"
        f"audience — who the other person is to the user, one of: {', '.join(AUDIENCES)}.\n"
        "audiences — the three most likely of these, most likely first.\n"
        "situation — what the other person's latest messages do, one of:\n"
        + "\n".join(f"- {k}: {v}" for k, v in SITUATIONS.items()) + "\n"
        "options — three replies the user could send now to the other person's LATEST messages. Think like THIS user "
        "(style below): the first option is what they would most likely do here, the other two are different moves "
        "they also make. act — one of: " + ", ".join(ACTS) + ". draft — the reply itself in the language of the chat, "
        "in the format the user asks for, concrete to this chat, following their case, punctuation and slang habits "
        "for that audience, no names.\n\n" + style_text,
    ).replace("Reasoning strength: low\n", "")


def profile_text(profile):
    """A style's profile.json → a few lines Spark can use to think like the user."""
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


STYLE_SYSTEM = """You write messages for one specific user, in their own voice, so that their friends could not
tell it was not them. Use their style below: length, case, punctuation, slang and swearing habits for that audience.
Keep the full meaning: every fact (when, what, who, how much, why) and every request, refusal or question
stays, only the wording changes, and so does the tone: don't add swear words or jokes that aren't in the draft.
Their usual length is for short thoughts; a draft with several points stays complete (write it as one longer
message rather than dropping anything). Write in the language of the input. No names.
An official message or an email overrides their casual habits: capitalized sentences, proper punctuation, no slang,
swearing or emoji; keep only their plain wording and directness.
Return JSON only: {{"text": "<the message>", "audiences": ["<audience>", ...]}} — audiences: the three of
""" + ", ".join(AUDIENCES) + """ this message most likely is for, most likely first.

{style}"""

REVISE_SYSTEM = STYLE_SYSTEM.replace(
    'Return JSON only: {{"text": "<the message>", "audiences": ["<audience>", ...]}} — audiences: the three of\n'
    + ", ".join(AUDIENCES) + " this message most likely is for, most likely first.",
    'The user didn\'t like your last answer and says what to change. Write a new answer that follows ALL their '
    "feedback so far, still in their voice.\n"
    'Return JSON only: {{"text": "<the new answer>", "rule": "<text>"}} — rule: if the feedback says how this user '
    "generally wants their messages (length, tone, words, emoji, punctuation, formality), for this audience or "
    "always, one short English instruction, at most 12 words (\"Keep replies to family short, no emoji\"); if it "
    "only concerns this one message, an empty string. Never put names or facts from the conversation in the rule.")

LEARN_SYSTEM = """You compare a suggested chat message with the version the user wrote instead, to learn how they
like to write. Return JSON only: {"rule": "<text>"} — if the edit shows a general habit (length, tone, words, emoji,
punctuation, formality), one short English instruction, at most 12 words ("Write 'ок' instead of 'хорошо'"); if it
only changes what this one message says, an empty string. Never put names or facts from the conversation in it."""


def clip(text, limit):
    """At most `limit` words, keeping the line structure (series and emails have one item per line)."""
    out, left = [], limit
    for line in text.splitlines():
        taken = line.split()[:left]
        left -= len(taken)
        if taken:
            out.append(" ".join(taken))
        if left <= 0:
            break
    return "\n".join(out)


def capitalize(line):
    """Sentence case for formal formats: the first letter of the line and after . ! ?"""
    return re.sub(r"(^|[.!?]\s+)(\w)", lambda m: m.group(1) + m.group(2).upper(), line)


def shape(text, format="message"):
    """→ (text, parts): parts are the messages to send one by one (one, except for a series)."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if format in FORMAL:
        lines = [capitalize(line) for line in lines]
    if format == "series" and len(lines) > 1:
        parts = lines[:4]
        return "\n".join(parts), parts
    if format == "email":
        return "\n\n".join(lines), ["\n\n".join(lines)]
    one = " ".join(lines)
    return one, [one]


def one_message(text):
    """The user often sends a reply as several short lines; a suggestion is easier to use as one message."""
    return shape(text)[0]


class Unavailable(Exception):
    """The GPU is cold (warming started) or a model API failed; the API maps it to 503/502."""

    def __init__(self, status, detail):
        super().__init__(detail)
        self.status, self.detail = status, detail


def clean(text):
    return CONTROL.sub("", text).strip()


def audiences_of(label, first=None):
    found = [a for a in label.get("audiences") or [] if a in AUDIENCES] if isinstance(label, dict) else []
    ranked = ([first] if first in AUDIENCES else []) + found + AUDIENCES
    return list(dict.fromkeys(ranked))[:3]


class Context:
    """One style, ready to write with: its profile and prompts, the user's real messages as examples, their
    statistics for reranking, what they usually do per audience × situation, and the rules learned in Chat."""

    def __init__(self, style_id):
        meta = styles.meta(style_id)
        if meta is None:
            raise KeyError(style_id)
        self.id, self.name = style_id, meta["name"]
        self.adapter = meta.get("adapter") if meta.get("adapter_ready") else None
        self.version = styles.version(style_id)
        if style_id == styles.MAIN:
            profile = styles.read_json(styles.DATA / "style_profile.json", {})
            turns = styles.main_turns()
            self.stats, self.lexical_weight = StyleStats.from_pairs("pairs_v2"), 10.0
            chats = styles.read_json(styles.DATA / "audiences.json", {})
        else:
            profile = styles.read_json(styles.folder(style_id) / "profile.json", {})
            turns = [t for t in styles.turns(style_id) if t.get("split") != "test"]
            vocab = Counter(w for t in turns for w in words(t["text"]))
            lex = {"vocab": {w for w, n in vocab.items() if n >= 2}, "signature": set(), "avoid": set()}
            self.stats = StyleStats([(t["audience"], t["situation"], t["text"]) for t in turns], lex) if turns else None
            self.lexical_weight = 0.0  # lexicon.score is tuned to the main style's word rates
            chats = meta.get("chats", {})
        self.chats = {name.casefold().strip(): a for name, a in chats.items() if a in AUDIENCES}
        self.examples, self.moves = defaultdict(list), defaultdict(list)
        for t in turns:
            if len(t["text"]) <= 300:
                self.examples[(t["audience"], t["situation"])].append(t["text"])
                self.examples[(t["audience"], None)].append(t["text"])
            if t.get("act"):
                self.moves[(t["audience"], t["situation"])].append((t["act"], t["tone"]))
                self.moves[(t["audience"], None)].append((t["act"], t["tone"]))
        self.approved = defaultdict(list)  # liked or written by the user in Chat: always shown first
        for f in styles.feedback(style_id):
            if f.get("audience") in AUDIENCES and f.get("text"):
                self.approved[f["audience"]].append(f["text"])
        self.preferences = styles.preferences(style_id)
        text = profile_text(profile)
        audiences = [a for a in AUDIENCES if self.examples.get((a, None))]
        shown = "\n".join(f"- {a}: " + " · ".join(f"«{one_message(e)}»" for e in self.sample(a, k=4, seed=0))
                          for a in audiences)
        style = ("The user's style, from their own chats (how they write, not who they are):\n" + text
                 + ("\n\nSome of their real messages:\n" + shown if shown else "") + self.rules())
        self.read_system = read_system(style)
        self.style_text = "The user's style, from their own chats:\n" + text + self.rules()

    def rules(self):
        if not self.preferences:
            return ""
        return ("\n\nThe user's own corrections (follow them, they override everything above):\n"
                + "\n".join(f"- {r}" for r in self.preferences))

    def sample(self, audience, situation=None, k=EXAMPLES, seed=None):
        """The user's real messages for this audience (and situation, if there are enough): their approved ones first."""
        cell = self.examples.get((audience, situation), [])
        pool = cell if len(cell) >= k else self.examples.get((audience, None), [])
        picked = random.Random(seed).sample(pool, min(k, len(pool)))
        return (self.approved.get(audience, [])[-3:] + picked)[:k]

    def examples_for(self, audience, situation=None):
        found = self.sample(audience, situation)
        return ("\nSome of their real messages to " + audience + ": "
                + " · ".join(f"«{one_message(e)}»" for e in found)) if found else ""

    def cell(self, audience, situation):
        cell = self.moves.get((audience, situation), [])
        return cell if len(cell) >= MIN_CELL else self.moves.get((audience, None)) or [("react", "neutral")]

    def tone_for(self, act, audience, situation):
        """The user's most common tone for this act here (style profile), else for this audience."""
        tones = (Counter(t for a, t in self.cell(audience, situation) if a == act)
                 or Counter(t for a, t in self.moves.get((audience, None), []) if a == act))
        return tones.most_common(1)[0][0] if tones else "neutral"

    def intents(self, audience, situation):
        cell = self.cell(audience, situation)
        likely = Counter(a for a, _ in cell).most_common(1)[0][0]
        acts = [likely] + [a for a in CONTRASTS.get(situation, DEFAULT_CONTRASTS) if a != likely]
        return [(act, self.tone_for(act, audience, situation)) for act in acts[:3]]


class Writer:
    def __init__(self, client, glimmer_url, token, tokenizer, meta_key, gpu="modal", reload=None):
        self.client, self.url, self.token, self.meta_key = client, glimmer_url.rstrip("/"), token, meta_key
        self.tokenizer = tokenizer
        self.gpu = gpu  # "modal", or "off": never touch the GPU (the user's models), Muse Spark writes alone
        self.reload = reload or (lambda: None)  # sees styles written by other containers (the build function)
        self.contexts = {}
        self.loaded = {"v2", "v4"}  # LoRAs vLLM loads at startup; a new style's is loaded on first use
        self.warm_until = 0.0
        self.warming = None

    def context(self, style_id=styles.MAIN):
        style_id = style_id or styles.MAIN
        cached = self.contexts.get(style_id)
        try:
            if cached is None or cached.version != styles.version(style_id):
                if styles.meta(style_id) is None:
                    self.reload()
                self.contexts[style_id] = cached = Context(style_id)
        except KeyError:
            raise Unavailable(404, "no such style")
        return cached

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

    async def uses_model(self, ctx, format="message"):
        """Whether the style's LoRA writes this one: it exists, fits the format, and the GPU is up (a cold GPU starts
        waking up, and Muse Spark answers meanwhile)."""
        if not ctx.adapter or format not in CHAT_FORMATS:
            return False
        try:
            await self.ensure_warm()
        except Unavailable:
            return False
        return await self.load_adapter(ctx.adapter)

    async def wake(self):
        try:
            await self.client.get(f"{self.url}/v1/models", timeout=900, headers={"Authorization": f"Bearer {self.token}"})
        except Exception:
            pass

    async def load_adapter(self, name):
        if name in self.loaded:
            return True
        response = await self.client.post(f"{self.url}/v1/load_lora_adapter", timeout=120,
                                          headers={"Authorization": f"Bearer {self.token}"},
                                          json={"lora_name": name, "lora_path": f"/data/adapters/{name}"})
        if response.status_code == 200 or "already" in response.text:
            self.loaded.add(name)
        return name in self.loaded

    async def complete(self, adapter, prompts, n=1, max_tokens=160, temperature=None):
        """One batched call to our vLLM; returns n texts per prompt (choices are numbered prompt × n + j)."""
        response = await self.client.post(
            f"{self.url}/v1/completions", timeout=120,
            headers={"Authorization": f"Bearer {self.token}"},
            json={"model": adapter, "prompt": prompts, "n": n, "max_tokens": max_tokens,
                  **SAMPLING, **({"temperature": temperature} if temperature else {}),
                  "stop": ["<|eot|>", "<|eom|>"], "skip_special_tokens": False})
        if response.status_code != 200:
            raise Unavailable(502, f"model error {response.status_code}")
        self.warm_until = time.monotonic() + 60
        choices = sorted(response.json()["choices"], key=lambda c: c["index"])
        texts = [c["text"].split("<|")[0].strip() for c in choices]  # cut any other control token
        return [texts[i * n:(i + 1) * n] for i in range(len(prompts))]

    def best(self, ctx, candidates, audience, situation):
        usable = [c for c in candidates if c.strip() and not KAZAKH.search(c)] or [c for c in candidates if c.strip()]
        if not usable:
            return ""
        if ctx.stats is None:
            return usable[0]
        return ctx.stats.pick(usable, audience, situation, lexical_weight=ctx.lexical_weight)

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
            if isinstance(label, dict) and isinstance(label.get(key), str) and (label[key].strip() or key == "rule"):
                return label
            await asyncio.sleep(1)
        raise Unavailable(502, "Muse Spark did not answer")

    def format_line(self, format):
        return f"\nFormat: write it {FORMATS.get(format, FORMATS['message'])}."

    def examples(self, ctx, format, audience, situation=None):
        return "" if format in FORMAL else ctx.examples_for(audience, situation)

    async def styled(self, ctx, task, field, text, audience, situation, format="message"):
        if not await self.uses_model(ctx, format):  # no LoRA for this, or it's asleep: Muse Spark writes in the style
            ask = {"rewrite": "Rewrite this draft the way the user would write it",
                   "compose": "Write the message the user would send for this instruction"}[task]
            label = await self.spark(STYLE_SYSTEM.format(style=ctx.style_text),
                                     f"{ask} to their {audience} ({situation}).{self.format_line(format)}"
                                     f"{self.examples(ctx, format, audience, situation)}\n\n{clean(text)}", "text")
            out, parts = shape(clip(clean(label["text"]), FORMAT_WORDS.get(format, 40) * 2), format)
            return {"text": out, "parts": parts, "candidates": [out], "styled": False,
                    "audiences": audiences_of(label)}
        prompt = self.prompt(audience, situation, task, field, text) + REPLY
        candidates = (await self.complete(ctx.adapter, [prompt], n=CANDIDATES + 2))[0]
        out, parts = shape(self.best(ctx, candidates, audience, situation), format)
        return {"text": out, "parts": parts, "candidates": [shape(c, format)[0] for c in candidates], "styled": True,
                "audiences": [audience]}

    async def rewrite(self, ctx, text, audience, situation="other", format="message"):
        return await self.styled(ctx, "rewrite", "draft", text, audience, situation, format)

    async def compose(self, ctx, instruction, audience, situation="other", format="message"):
        return await self.styled(ctx, "compose", "instruction", instruction, audience, situation, format)

    # ---- reply: think like the user, then write ---------------------------------------------------

    async def reply(self, ctx, summary, audience, situation, options=None, format="message"):
        """options = Spark's drafts [{act, draft}] (it saw the chat and the style): the style's LoRA rewrites them in
        the user's voice, or they come back as they are while it can't. Without options the main model thinks."""
        if options:
            styled = await self.uses_model(ctx, format)
            groups = [[o["draft"]] for o in options]
            if styled:
                prompts = [self.prompt(audience, situation, "rewrite", "draft", o["draft"]) + REPLY for o in options]
                groups = await self.complete(ctx.adapter, prompts, n=CANDIDATES + 2, temperature=REWRITE_TEMPERATURE)
            replies = []
            for option, group in zip(options, groups):
                text, parts = shape(self.best(ctx, group, audience, situation) if styled else option["draft"], format)
                replies.append({"intent": option["act"], "tone": ctx.tone_for(option["act"], audience, situation),
                                "thought": f"act: {option['act']} · draft: {option['draft']}", "styled": styled,
                                "text": text, "parts": parts})
            return replies
        if ctx.id != styles.MAIN or format not in CHAT_FORMATS:
            raise Unavailable(502, "Muse Spark gave no drafts, try again")
        await self.ensure_warm()
        base = self.prompt(audience, situation, "reply", "incoming", summary) + THOUGHT
        moves = ctx.intents(audience, situation)
        heads = [f"act: {act} · tone: {tone} · gist:" for act, tone in moves]
        gists = await self.complete(ctx.adapter, [base + h for h in heads], n=CANDIDATES, max_tokens=60)
        thoughts = [[f"{h} {g}" for g in group] for h, group in zip(heads, gists)]
        flat = [t for group in thoughts for t in group]
        replies = await self.complete(ctx.adapter, [base + t + AFTER_THOUGHT for t in flat])
        out = []
        for i, (act, tone) in enumerate(moves):
            group = [r[0] for r in replies[i * CANDIDATES:(i + 1) * CANDIDATES]]
            text = self.best(ctx, group, audience, situation)
            shaped, parts = shape(text, format)
            out.append({"intent": act, "tone": tone, "thought": thoughts[i][group.index(text)], "styled": True,
                        "text": shaped, "parts": parts})
        return out

    # ---- reading the chat (Muse Spark, nothing stored) --------------------------------------------

    async def read(self, ctx, image=None, image_type="image/jpeg", messages=None, audience=None, instruction="",
                   format="message"):
        """→ (context, options): context = {audience, audiences, situation, summary}; options = up to 3 {act, draft}.
        instruction: what the user wants to say or extra context ("politely decline, I'm busy")."""
        ask = "Describe this chat screenshot." if image is not None else "Messages (latest last):\n" + clean(messages)
        ask += self.format_line(format)
        if audience in AUDIENCES:
            ask += f"\nThe user says the other person is their {audience}." + self.examples(ctx, format, audience)
        if instruction and instruction.strip():
            ask += (f"\nThe user's own note about how to reply: \"{clean(instruction)[:300]}\". All three options "
                    "must follow it (use it as context if it is not an instruction); vary wording, tone and act.")
        content = ask
        if image is not None:
            content = [{"type": "text", "text": ask},
                       {"type": "image_url", "image_url": {"url": f"data:{image_type};base64," + base64.b64encode(image).decode()}}]
        label = await self.spark(ctx.read_system, content, "summary")
        # The summary goes into our prompt: plain text only, bounded, no template tokens.
        summary = " ".join(clean(label["summary"]).split()[:SUMMARY_WORDS])
        situation = label.get("situation") if label.get("situation") in SITUATIONS else "other"
        guessed = label.get("audience") if label.get("audience") in AUDIENCES else "friends"
        known = ctx.chats.get(str(label.get("chat_name") or "").casefold().strip())  # the title is not kept
        options = []
        for option in label.get("options") or []:
            if isinstance(option, dict) and option.get("act") in ACTS and isinstance(option.get("draft"), str):
                draft = clip(clean(option["draft"]), FORMAT_WORDS.get(format, 40))
                if format not in {"series", "email"}:
                    draft = one_message(draft)
                if draft and option["act"] not in {o["act"] for o in options}:
                    options.append({"act": option["act"], "draft": draft})
        chosen = audience or known or guessed
        context = {"audience": chosen, "audiences": audiences_of(label, known or guessed), "situation": situation,
                   "summary": summary}
        return context, options[:3]

    # ---- the app's chat ----------------------------------------------------------------------------

    async def chat(self, ctx, mode, text, audience, format="message", history=(), instruction=""):
        """mode: write | rewrite | reply (text = their messages). history: earlier answers with the user's feedback
        on each, oldest first; with feedback on the last one, the answer is revised instead."""
        if history and history[-1].get("feedback"):
            feedback = "\n".join(f"- {h['feedback']}" for h in history if h.get("feedback"))
            task = {"write": "Write the message the user would send for this instruction",
                    "rewrite": "Rewrite this draft the way the user would write it",
                    "reply": "Write the user's reply to these messages"}[mode]
            label = await self.spark(
                REVISE_SYSTEM.format(style=ctx.style_text),
                f"{task}, to their {audience}.{self.format_line(format)}{self.examples(ctx, format, audience)}\n\n"
                f"Input:\n{clean(text)}\n\nYour last answer:\n{clean(history[-1].get('answer', ''))}\n\n"
                f"The user's feedback so far:\n{clean(feedback)}", "text")
            out, parts = shape(clip(clean(label["text"]), FORMAT_WORDS.get(format, 40) * 2), format)
            rule = clean(str(label.get("rule") or ""))
            if rule:
                styles.add_preference(ctx.id, rule)
                styles.commit()
            return {"text": out, "parts": parts, "alternatives": [], "audience": audience, "audiences": [audience],
                    "learned": rule or None}
        if mode == "reply":
            context, options = await self.read(ctx, messages=text, audience=audience, instruction=instruction,
                                               format=format)
            replies = await self.reply(ctx, context["summary"], context["audience"], context["situation"], options,
                                       format)
            return {"text": replies[0]["text"], "parts": replies[0]["parts"],
                    "alternatives": [r["text"] for r in replies[1:]], "audience": context["audience"],
                    "audiences": context["audiences"], "learned": None}
        result = await (self.compose if mode == "write" else self.rewrite)(ctx, text, audience, format=format)
        return {"text": result["text"], "parts": result["parts"],
                "alternatives": [c for c in result["candidates"] if c != result["text"]][:2],
                "audience": audience, "audiences": result["audiences"], "learned": None}

    async def feedback(self, ctx, audience, format, answer, edited=None, liked=False):
        """The user liked an answer or wrote their own version: it becomes an example; an edit may teach a rule."""
        text = clean(edited or answer)
        if not text or audience not in AUDIENCES:
            return {"learned": None}
        styles.add_feedback(ctx.id, {"audience": audience, "format": format, "text": text,
                                     "kind": "edited" if edited else "liked"})
        rule = None
        if edited and clean(answer) != text:
            label = await self.spark(LEARN_SYSTEM, f"Audience: {audience}\nSuggested: {clean(answer)}\nThe user's "
                                                   f"version: {text}", "rule")
            rule = clean(str(label.get("rule") or "")) or None
            if rule:
                styles.add_preference(ctx.id, rule)
        styles.commit()
        return {"learned": rule}
