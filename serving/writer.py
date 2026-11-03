"""What the SaySo API does with a request: read the chat, think like the user, write like the user.

Who does what (Meta models):
  Muse Spark Open (Baseten)   writes in the user's style: rewrite, compose, chat, email, and the reply drafts' polish
                              (reasoning "low"); with writer="meta" Muse Spark 1.3 writes instead
  Muse Spark 1.3 (Meta API)   reads screenshots, pasted chats and photos of the user's documents; writes essays;
                              the fallback when Spark Open fails (and the other way round)
  Muse Voice Transcribe       turns a voice note into text (transcribe)
  Muse Glimmer 30B + LoRA     the user's own model: with the GPU on (SAYSO_GPU), it rewrites drafts in their voice and
                              writes replies "thought first" (main style, v4); off by default

  read     — screenshot or messages → {audience, audiences (top 3), situation, summary} + three reply drafts that
             follow the user's style (profile, their real messages, rules learned from their corrections)
  reply    — the drafts, rewritten by the LoRA when it's up, else returned as written
  rewrite / compose — the user's draft or instruction → their wording, in a format: message, series, official, email
  chat     — the same in the app, plus email (subject + body) and essay (plan + text from the user's notes only), and
             revising an answer from feedback; a lasting preference becomes a rule of the style
  formal voice — official messages, emails and essays copy the user's own emails and essays (voice, not structure)
  learn / feedback — what the user sends with the keyboard, likes or corrects becomes examples and rules

Other people's messages are read in memory and never stored. Runs inside the Modal `api` container: the user's data
is on the private volume, mounted so that pipeline/ modules find it at their usual data/ path.
"""

import asyncio
import base64
import io
import math
import json
import random
import re
import sys
import time
import wave
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
FORMATS["essay"] = ("as an essay: paragraphs separated by blank lines, first person, the user's own facts only, in their "
                    "formal voice")
FORMAT_WORDS = {"message": 40, "series": 50, "official": 60, "email": 200, "essay": 900}
CHAT_FORMATS = {"message", "series"}  # the LoRA was trained on chats: it rewrites only these
FORMAL = {"official", "email", "essay"}
# Formal writing overrides the casual habits the shared style prompt asks for (slang, swearing, emoji, splitting).
FORMAL_NOTE = ("\n\nThis is formal writing: ignore the casual chat habits above (no slang, swearing, emoji or splitting "
               "into short messages); keep only the user's formal voice.")  # written in the user's formal voice (their own documents), not their chat one
# Phrases that make a text read as AI-written; an essay or email that has them is rewritten once.
CLICHES = re.compile(
    r"в современном мире|в наше время|игра(?:ет|ют) (важную|ключевую) роль|не секрет, что|неотъемлемой частью|"
    r"в заключение хочется|данная тема|является актуальн|на сегодняшний день|широкий спектр|уникальн(ая|ый) возможност|"
    r"\bdelve|tapestry|in today's (fast-paced )?world|plays a (crucial|vital|pivotal) role|a testament to|"
    r"navigat(e|ing) the complexities|in conclusion,|ever-evolving|unlock (the|my) potential|embark on", re.I)

EMAIL_TASK = """Write an email from the user{reply}.
What the user wants to say (their notes, maybe dictated): {notes}
Write it in their formal voice (below): greeting and sign-off the way they do it, plain and direct, every fact from the
notes, nothing invented. Same language as the notes{reply_lang}.
Return JSON only: {{"subject": "<short subject line>", "text": "<the email: greeting, paragraphs, sign-off, separated
by blank lines>"}}."""

ESSAY_TASK = """The user needs an essay.
Question or topic: {question}
Length: up to about {words} words.
The user's notes (the ONLY source of facts; maybe dictated): {notes}
First plan it (4 to 6 points), then write it in the structure the question or notes ask for (an argumentative
essay, a personal statement, a story, a letter...); if they say nothing, a natural flowing essay without headings. Never
add labels like "Thesis:" or "Argument 1:" unless asked. A personal statement, a story or anything about the user is
written in the first person ("I built…"), active voice; an argument about a topic can be impersonal. Paragraphs separated by blank lines, a
concrete opening (a moment or a fact, not a general statement), every paragraph adds something new, never repeat a
fact, never invent experiences, names, numbers or feelings that are not in the notes. Reach the length by explaining
and connecting the user's facts and saying what they showed or why they mattered, never by repeating or inventing; only
if that is impossible, write it shorter and ask what is missing. Write in the user's formal voice (below): their
sentence length (not choppy short sentences), plain wording, their linking words only where they fit naturally. Same language as
the notes.
Before you answer, check: (1) if it is about the user (a personal statement, their project, their story), every
paragraph speaks as "I" in the active voice, never "the project was built"; (2) each linking word really links two
ideas, or remove it; (3) nothing that is not in the notes.
Return JSON only: {{"outline": ["...", ...], "text": "<the essay>", "questions": ["<up to 3 short questions whose answers
would make the essay stronger, in the notes' language>", ...]}}."""

ESSAY_FIX = """Fix this essay: {problems}. Keep its plan, facts and voice; change only what is needed.
Essay:
{text}
Return JSON only: {{"text": "<the essay>"}}."""

# The input is an instruction ("tell her I'm 20 min late"), not a draft: never send it back as the message.
COMPOSE = ("The input below is the user's instruction about what to say, not the message. Write the message itself, "
           "as the user would send it (\"напиши что буду дома в 9\" → \"буду дома в 9\"); never repeat the instruction's "
           "wording like \"скажи\" / \"напиши\" / \"tell her\". When it names who it's for (\"tell Mira I'm 20 min "
           "late\"), the message goes to that person (\"sorry, running 20 min late\"), it never says \"tell Mira\". Write it")
ECHO = re.compile(r"^\s*(скажи|напиши|спроси|ответь|предложи|передай|tell|write|ask|say)\b", re.I)


def echoes(message, instruction):
    """The message sends the instruction back ("yo tell mira im late") instead of being the message itself."""
    if ECHO.match(message):
        return True
    head = " ".join(clean(instruction).casefold().split()[:2])
    return bool(ECHO.match(head)) and head in clean(message).casefold()
VARIANT_COUNT = 4
VARIANTS = ("\nAlso put 4 other ways this user could write the same message (same meaning and facts, different wording, "
            "length or punctuation, all within their habits) in \"variants\": [\"...\", ...] next to \"text\".")  # the user's casual examples would pull these back to lowercase chat

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
TRANSCRIBE_URL = "https://api.meta.ai/v1/asr/transcribe"  # Muse Voice Transcribe: WAV in, text out
# Its request takes the same hints as its realtime handshake: "keywords" (words to expect: names) and "languageBias"
# (language names from its list; there is no "language" field, which is why that was ignored). Russian and Kazakh are
# not on its list, so a Russian note goes without a language bias.
ASR_LANGUAGES = {"en": "English", "de": "German", "fr": "French", "es": "Spanish", "it": "Italian", "tr": "Turkish",
                 "pl": "Polish"}
ASR_RATES = (16_000, 24_000)  # the WAV rates it takes; 24 kHz is what its realtime API streams
# Muse Voice Transcribe repeats words ("traffic, traffic", "Мире, мире") and doubles the final punctuation ("?.", "..")
REPEATED = re.compile(r"\b(\w{3,})[,.!?;:]?\s+\1\b", re.I)  # short ones ("да да", "ok ok") are often meant
DOUBLED_STOP = re.compile(r"([.!?])[.!?]+")
CYRILLIC = re.compile(r"[а-яёәғқңөұүһі]", re.I)  # Russian and Kazakh letters
LATIN = re.compile(r"[a-z]", re.I)
TRANSCRIPT_FIX = """You fix speech-recognition mistakes in a voice note, nothing else.
Fix: repeated or broken words ("на бая. Абая" → "на Абая"), punctuation, capital letters of names and places.
Keep every word the speaker said, in their language and order; never rephrase, shorten, translate, answer or add anything.
English or Kazakh words inside a Russian note stay as they are.
Return JSON only: {"text": "<the fixed voice note>"}."""
TRANSCRIPT_FIX_EN = """You fix speech-recognition mistakes in an English voice note, nothing else.
The speaker may have an accent, so the recognizer sometimes writes a word that sounds similar but makes no sense. Fix:
- sound-alike words that don't fit the sentence: their/there/they're, your/you're, its/it's, to/too/two, then/than,
  know/no, write/right, here/hear, where/wear/were, whether/weather, by/buy/bye, for/four, one/won, meet/meat,
  week/weak, wait/weight, accept/except, our/hour/are, I'll/aisle, we'll/will, he'll/heel;
- a misheard word or a word broken in two ("for get" → "forget", "a sleep" → "asleep"), or two words run together;
- missing apostrophes ("dont" → "don't", "im" → "I'm"), "i" → "I";
- names and places: capital letters, and the spelling from "Known names" when it sounds the same;
- sentence capitals and punctuation; a question ends with "?".
Keep the speaker's words, order and casual tone ("gonna", "wanna", "ok", "yeah"); never rephrase, shorten, translate,
answer or add anything. When you are not sure a word is wrong, keep it.
Return JSON only: {"text": "<the fixed voice note>"}."""
# What the note is for, from the Chat mode the app was in: tells the fix pass what kind of words to expect.
TRANSCRIPT_USE = {
    "write": "an instruction to SaySo about a message to write",
    "rewrite": "the user's own draft of a chat message",
    "reply": "a message the user got, read aloud",
    "email": "what an email should say, or the email the user got",
    "essay": "the user's notes for an essay",
    "fix": "what to change in SaySo's last answer",
}
# If the Meta API fails (or hits a limit during the demo), Muse Spark Open answers instead (Baseten, hackathon key).
FALLBACK_URL = "https://inference.baseten.co/v1/chat/completions"
FALLBACK_MODEL = "meta-models/muse-spark-open-1026"

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
                     f"swearing {p['swear']:.0%}, emoji {min(p.get('emoji', 0), 1):.0%}, "
                     f"~{p.get('lines', 1):.1f} messages in a row. Moves: {share(p['acts'])}. Tones: {share(p['tones'])}.")
        for situation, c in list(p.get("situations", {}).items())[:5]:
            lines.append(f"  · {situation}: {share(dict(list(c['acts'].items())[:3]))}; "
                         f"{share(dict(list(c['tones'].items())[:2]))}; ~{c['median_chars']:.0f} chars")
    return "\n".join(lines)


STYLE_SYSTEM = """You write messages for one specific user, in their own voice, so that their friends could not
tell it was not them. Use their style below: length, case, punctuation, slang and swearing habits for that audience.
Keep the full meaning: every fact (when, what, who, how much, why) and every request, refusal or question
stays, only the wording changes, and the mood stays (a calm draft doesn't turn rude). Their habits ARE their voice:
their fillers and slang, laughter, swearing, emoji and splitting a thought into several short messages; use each about
as often as the style says for this audience, so a clean neutral draft comes out the way they'd really type it.
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


def grams(text):
    """Character trigrams of the words (spelling, endings, slang) plus the words themselves."""
    tokens = words(text)
    joined = f" {' '.join(tokens)} "
    found = Counter(joined[i:i + 3] for i in range(len(joined) - 2))
    found.update(f"w:{t}" for t in tokens)
    return found


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
    if format in {"email", "essay"}:
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


def tidy_transcript(text):
    """Removes the recognizer's repeated words and doubled final punctuation."""
    previous = None
    while previous != text:
        previous, text = text, REPEATED.sub(r"\1", text)
    return DOUBLED_STOP.sub(r"\1", text).strip()


def transcript_language(text, hint=None):
    """"en" or "ru" (Russian, Kazakh) by the letters of the transcript; the app's language when there are none."""
    cyrillic, latin = len(CYRILLIC.findall(text or "")), len(LATIN.findall(text or ""))
    if cyrillic == latin == 0:
        return hint if hint in ("en", "ru") else "ru"
    return "en" if latin > cyrillic else "ru"


def transcript_words(text):
    """The words of a note for comparing two versions: lowercase, apostrophes dropped ("don't" = "dont")."""
    return set(re.findall(r"\w+", (text or "").replace("'", "").replace("’", "").casefold()))


def names_in(text, limit=12):
    """Capitalized words that don't start a sentence (names, places): hints for the recognizer and the fix pass."""
    found = []
    for sentence in re.split(r"(?<=[.!?\n])\s+", text or ""):
        for word in re.findall(r"[^\W\d_][\w'’-]*", sentence)[1:]:
            if len(word) > 1 and word[0].isupper() and word not in found:
                found.append(word[:40])
    return found[:limit]


def prepare_wav(wav):
    """Gets a voice note ready for the recognizer: one channel, a rate it takes, the silence before and after the
    speech trimmed (in silence recognizers invent and repeat words), quiet speech brought up to a normal level.
    Anything it can't read goes out unchanged."""
    try:
        import numpy as np
        with wave.open(io.BytesIO(wav)) as source:
            channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
            frames = source.readframes(source.getnframes())
        if width != 2 or rate < 8_000:
            return wav
        samples = np.frombuffer(frames[: len(frames) // (2 * channels) * 2 * channels], "<i2").astype(np.float32)
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)
        if rate not in ASR_RATES:  # e.g. 44.1/48 kHz from a test file: smooth, then resample to 24 kHz
            width_ = max(1, round(rate / ASR_RATES[1]))
            samples = np.convolve(samples, np.ones(width_) / width_, mode="same")
            target = int(len(samples) * ASR_RATES[1] / rate)
            samples = np.interp(np.linspace(0, len(samples) - 1, target), np.arange(len(samples)), samples)
            rate = ASR_RATES[1]
        samples = samples - samples.mean()
        frame = rate // 50  # 20 ms
        count = len(samples) // frame
        if count < 10:
            return wav
        energy = np.sqrt((samples[: count * frame].reshape(count, frame) ** 2).mean(axis=1))
        # speech: above 3× the quietest frames, but never more than 20 dB under the loudest (a note with no pause)
        voiced = np.flatnonzero(energy > max(min(np.percentile(energy, 10) * 3, energy.max() * 0.1), 20))
        if not len(voiced):
            return wav
        pad = 15  # 300 ms of silence kept on each side
        start, end = max(voiced[0] - pad, 0) * frame, min(voiced[-1] + pad + 1, count) * frame
        speech = samples[start: len(samples) if end >= count * frame else end]
        peak = np.percentile(np.abs(speech), 99.9)
        if peak < 1:
            return wav
        gain = max(1.0, min(0.7 * 32767 / peak, 10.0))  # up to -3 dBFS, at most ×10; never quieter
        out = np.clip(speech * gain, -32768, 32767).astype("<i2")
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as sink:
            sink.setnchannels(1)
            sink.setsampwidth(2)
            sink.setframerate(rate)
            sink.writeframes(out.tobytes())
        return buffer.getvalue()
    except Exception:
        return wav


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
        self.recent = defaultdict(list)  # sent with the SaySo keyboard: how the user writes right now
        for row in styles.learned(style_id):
            if row.get("audience") in AUDIENCES and row.get("text") and len(row["text"]) <= 300:
                self.recent[row["audience"]].append(row["text"])
                self.examples[(row["audience"], None)].append(row["text"])
        self.preferences = styles.preferences(style_id)
        self.documents = styles.documents(style_id)  # the user's own formal writing: [{doc, kind, text}]
        self.formal = styles.formal(style_id).get("profile") or {}
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
        first = self.approved.get(audience, [])[-3:] + self.recent.get(audience, [])[-3:]
        return list(dict.fromkeys(first + picked))[:k]

    def examples_for(self, audience, situation=None, found=None):
        found = self.sample(audience, situation) if found is None else found
        return ("\nSome of their real messages to " + audience + ": "
                + " · ".join(f"«{one_message(e)}»" for e in found)) if found else ""

    def nearest(self, audience, query, k=EXAMPLES):
        """The user's messages to this audience most like `query` in words and spelling (TF-IDF over character
        trigrams and words, computed here: nothing leaves the server)."""
        if not hasattr(self, "_postings"):
            docs = [grams(t) for _, t in self.pool]
            df = Counter(g for d in docs for g in d)
            self._idf = {g: math.log(len(docs) / n) + 1 for g, n in df.items()}
            self._postings = defaultdict(list)
            for i, d in enumerate(docs):
                weights = {g: (1 + math.log(tf)) * self._idf[g] for g, tf in d.items()}
                norm = math.sqrt(sum(w * w for w in weights.values())) or 1.0
                for g, w in weights.items():
                    self._postings[g].append((i, w / norm))
        scores = defaultdict(float)
        for g, tf in grams(query).items():
            if g in self._idf:
                wq = (1 + math.log(tf)) * self._idf[g]
                for i, w in self._postings[g]:
                    if self.pool[i][0] == audience:
                        scores[i] += wq * w
        return [self.pool[i][1] for i, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:k]]

    def formal_block(self, query=None, k=3, kind=None):
        """The user's formal voice for official messages, emails and essays: their formal profile and the paragraphs of
        their own writing most like `query`, of the same kind first; empty if they haven't added any."""
        if not self.documents:
            return ""
        import documents as parse
        q = grams(query or "")
        def score(text):
            g = grams(text)
            return sum(min(n, g[gram]) for gram, n in q.items()) / (sum(g.values()) ** 0.5 or 1)
        texts = sorted(self.documents, key=lambda r: (r.get("kind", "essay") != kind, -score(r["text"]) if q else 0))
        picked = [r["text"] for r in texts[:k]]
        rules = {"essay": "copy ONLY their voice: word choice, sentence length, linking words, how direct they are. "
                          "Never copy its structure, headings, format or topic: follow the structure the task asks for",
                 "email": "copy ONLY their manner: how they greet, ask and sign off, how formal and direct they are. "
                          "Never copy what those emails say"}[kind if kind in ("essay", "email") else "email"]
        return (f"\nThe user's own formal writing, to {rules}:\n" + parse.profile_text(self.formal) + "\n"
                + "\n".join(f"«{' '.join(t.split()[:120])}»" for t in picked))

    @property
    def pool(self):
        """Every distinct own message with its audience, in a fixed order (what `nearest` searches)."""
        if not hasattr(self, "_pool"):
            self._pool = list(dict.fromkeys((a, t) for (a, s), texts in self.examples.items() if s is None for t in texts))
        return self._pool

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
    def __init__(self, client, glimmer_url, token, tokenizer, meta_key, gpu="modal", reload=None, baseten_model=None,
                 fallback_key=None, retrieval="local", writer="meta"):
        """gpu: "modal" (our vLLM on Modal, glimmer_url + its key), "baseten" (the same vLLM on Baseten: token is the
        Baseten API key, baseten_model its model id), or "off": never touch a GPU, Muse Spark writes alone."""
        self.client, self.url, self.token, self.meta_key = client, glimmer_url.rstrip("/"), token, meta_key
        self.tokenizer = tokenizer
        self.gpu = gpu
        self.baseten = baseten_model
        self.fallback_key = fallback_key  # Muse Spark Open on Baseten, used when the Meta API fails
        self.retrieval = retrieval  # "local" (TF-IDF here) or "random"
        self.writer = writer  # who writes text: "meta" (Muse Spark 1.3) or "open" (Muse Spark Open first)
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
            if await self.is_up():
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

    @property
    def auth(self):
        return {"Authorization": f"Api-Key {self.token}" if self.gpu == "baseten" else f"Bearer {self.token}"}

    async def is_up(self):
        if self.gpu == "baseten":  # Baseten's own status: ACTIVE, or SCALED_TO_ZERO / WAKING_UP / DEPLOYING
            response = await self.client.get(
                f"https://api.baseten.co/v1/models/{self.baseten}/deployments/production", timeout=4, headers=self.auth)
            return response.status_code == 200 and response.json().get("status") == "ACTIVE"
        response = await self.client.get(f"{self.url}/v1/models", timeout=4, headers=self.auth)
        return response.status_code == 200

    async def wake(self):
        try:
            if self.gpu == "baseten":
                await self.client.post(f"https://model-{self.baseten}.api.baseten.co/production/wake", timeout=30,
                                       headers=self.auth)
            else:
                await self.client.get(f"{self.url}/v1/models", timeout=900, headers=self.auth)
        except Exception:
            pass

    async def load_adapter(self, name):
        if name in self.loaded or self.gpu == "baseten":  # Baseten serves only the adapters it started with
            return name in self.loaded
        response = await self.client.post(f"{self.url}/v1/load_lora_adapter", timeout=120, headers=self.auth,
                                          json={"lora_name": name, "lora_path": f"/data/adapters/{name}"})
        if response.status_code == 200 or "already" in response.text:
            self.loaded.add(name)
        return name in self.loaded

    async def complete(self, adapter, prompts, n=1, max_tokens=160, temperature=None):
        """One batched call to our vLLM; returns n texts per prompt (choices are numbered prompt × n + j)."""
        url = (f"https://model-{self.baseten}.api.baseten.co/environments/production/predict" if self.gpu == "baseten"
               else f"{self.url}/v1/completions")
        response = await self.client.post(
            url, timeout=120, headers=self.auth,
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

    async def spark(self, system, user, key, max_tokens=3000, writes=False, timeout=30):
        """One Muse Spark call that returns a JSON object: Muse Spark 1.3 twice, then Muse Spark Open once, then 502.
        writes=True (text in the user's style, no image): Muse Spark Open first when the writer is "open"."""
        meta = [(META_URL, self.meta_key, {"model": "muse-spark-1.3", "reasoning_effort": "low"})] * 2
        # Spark Open always reasons; "low" keeps a short thought (2.7 s instead of 5.5 s, a fifth of the tokens).
        open_ = ([(FALLBACK_URL, self.fallback_key, {"model": FALLBACK_MODEL, "reasoning_effort": "low"})]
                 if self.fallback_key else [])
        tries = open_ + meta if writes and self.writer == "open" else meta + open_
        for url, api_key, model in tries:
            try:
                response = await self.client.post(
                    url, timeout=timeout, headers={"Authorization": f"Bearer {api_key}"},
                    json={**model, "max_tokens": max_tokens,
                          "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
                response.raise_for_status()
                text = response.json()["choices"][0]["message"].get("content") or ""
                match = re.search(r"\{.*\}", text, re.S)
                label = json.loads(match.group(0)) if match else {}
            except Exception:  # 429/5xx, timeout, non-JSON
                label = {}
            value = label.get(key) if isinstance(label, dict) else None
            if (isinstance(value, str) and (value.strip() or key == "rule")) or (isinstance(value, list) and value):
                return label
            await asyncio.sleep(1)
        raise Unavailable(502, "Muse Spark did not answer")

    def format_line(self, format):
        return f"\nFormat: write it {FORMATS.get(format, FORMATS['message'])}."

    async def examples(self, ctx, format, audience, situation=None, query=None):
        """The user's real messages for this audience: their approved and newest ones first, then the ones most like
        `query` (random without one); none for official messages and emails. Picking by similarity scored the same as
        random examples on Nov 1 (eval/style_gain.py), but costs nothing and keeps the topic close."""
        if format in FORMAL:
            return ctx.formal_block(query, kind="essay" if format == "essay" else "email")
        first = ctx.approved.get(audience, [])[-2:] + ctx.recent.get(audience, [])[-2:]
        if self.retrieval == "local" and (query or "").strip():
            nearest = ctx.nearest(audience, clean(query)[:500])
            if nearest:
                return ctx.examples_for(audience, found=list(dict.fromkeys(first + nearest))[:EXAMPLES])
        return ctx.examples_for(audience, situation)

    async def styled(self, ctx, task, field, text, audience, situation, format="message"):
        if not await self.uses_model(ctx, format):  # no LoRA for this, or it's asleep: Muse Spark writes in the style
            ask = {"rewrite": "Rewrite this draft the way the user would write it",
                   "compose": COMPOSE}[task]
            prompt = (f"{ask} to their {audience} ({situation}).{self.format_line(format)}"
                      f"{await self.examples(ctx, format, audience, situation, text)}{VARIANTS}\n\n{clean(text)}")
            label = await self.spark(STYLE_SYSTEM.format(style=ctx.style_text), prompt, "text", writes=True)
            if task == "compose" and echoes(label["text"], text):  # sent the instruction back: Muse Spark 1.3 writes it
                label = await self.spark(STYLE_SYSTEM.format(style=ctx.style_text), prompt, "text")
            # Spark's own answer comes first; the variants are alternatives for ✨. Picking the variant closest to the
            # user's statistics matched their form no better (0.94) and their wording worse (chrF 51 → 42,
            # eval/style_gain.py), so it doesn't replace the answer.
            limit = FORMAT_WORDS.get(format, 40) * 2
            variants = label.get("variants") if isinstance(label.get("variants"), list) else []
            written = [label["text"]] + [v for v in variants if isinstance(v, str)][:VARIANT_COUNT]
            if task == "compose":  # drop the ones that still repeat the instruction, unless that's all there is
                written = [w for w in written if not echoes(w, text)] or written
            candidates = list(dict.fromkeys(shape(clip(clean(v), limit), format)[0] for v in written if clean(v)))
            if not candidates:  # only template tokens or blanks came back
                raise Unavailable(502, "Muse Spark gave an empty answer, try again")
            out, parts = shape(candidates[0], format)
            return {"text": out, "parts": parts, "candidates": [out] + [c for c in candidates if c != out],
                    "styled": False, "audiences": audiences_of(label)}
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
            ask += (f"\nThe user says the other person is their {audience}."
                    + await self.examples(ctx, format, audience, query=messages or instruction))
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
        for option in label.get("options") if isinstance(label.get("options"), list) else []:
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

    async def chat(self, ctx, mode, text, audience, format="message", history=(), instruction="", question="", words=0,
                   reply_to=""):
        """mode: write | rewrite | reply (text = their messages) | email (text = what to say, reply_to = the email being
        answered) | essay (text = the user's notes, question, words). history: earlier answers with the user's feedback
        on each, oldest first; with feedback on the last one, the answer is revised instead."""
        if mode in {"email", "essay"}:
            format = mode
        if history and history[-1].get("feedback"):
            feedback = "\n".join(f"- {h['feedback']}" for h in history if h.get("feedback"))
            task = {"write": COMPOSE,
                    "rewrite": "Rewrite this draft the way the user would write it",
                    "reply": "Write the user's reply to these messages",
                    "email": "Write the user's email from these notes",
                    "essay": f"Write the user's essay ({question or 'from these notes'}) from these notes"}[mode]
            voice = ctx.style_text if format not in FORMAL else (
                (ctx.formal_block(text, kind="essay" if format == "essay" else "email") or "Write plainly and directly, like a real person, not like an AI.") + ctx.rules() + FORMAL_NOTE)
            label = await self.spark(
                REVISE_SYSTEM.format(style=voice),
                f"{task}, to their {audience}.{self.format_line(format)}{await self.examples(ctx, format, audience, query=text)}\n\n"
                f"Input:\n{clean(text)}\n\nYour last answer:\n{clean(history[-1].get('answer', ''))}\n\n"
                f"The user's feedback so far:\n{clean(feedback)}", "text", writes=mode not in {"essay"},
                max_tokens=6000 if mode == "essay" else 3000, timeout=90 if mode == "essay" else 30)
            out, parts = shape(clip(clean(label["text"]), FORMAT_WORDS.get(format, 40) * 2), format)
            rule = clean(str(label.get("rule") or ""))
            if rule and format in FORMAL:  # scoped, so a rule learned on an essay doesn't change chat messages
                rule = f"In {'essays' if format == 'essay' else 'emails and official messages'}: {rule}"
            if rule:
                styles.add_preference(ctx.id, rule)
                styles.commit()
            return {"text": out, "parts": parts, "alternatives": [], "audience": audience, "audiences": [audience],
                    "learned": rule or None, **({"subject": None} if mode != "email" else {})}
        if mode == "email":
            return await self.email(ctx, text, reply_to)
        if mode == "essay":
            return await self.essay(ctx, question, text, words or 250)
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

    def formal_system(self, ctx, query, kind="email"):
        return (STYLE_SYSTEM.split("Return JSON only")[0].format(style="")
                + "\n" + (ctx.formal_block(query, kind=kind) or "The user hasn't added formal writing yet: write plainly and "
                                                     "directly, like a real person, not like an AI.") + ctx.rules() + FORMAL_NOTE)

    async def email(self, ctx, notes, reply_to=""):
        reply = f", answering this email:\n{clean(reply_to)[:3000]}\n" if reply_to.strip() else ""
        label = await self.spark(self.formal_system(ctx, f"{reply_to} {notes}"),
                                 EMAIL_TASK.format(reply=reply, notes=clean(notes),
                                                   reply_lang=" (or of the email being answered)" if reply else ""),
                                 "text", writes=True, timeout=60)
        text, parts = shape(clip(clean(label["text"]), FORMAT_WORDS["email"] * 2), "email")
        subject = clean(str(label.get("subject") or "")) or None  # the fix pass below returns only the text
        if CLICHES.search(text):
            fixed = await self.spark(self.formal_system(ctx, notes), ESSAY_FIX.format(
                problems="remove phrases that sound AI-written: " + ", ".join(sorted({m.group(0) for m in CLICHES.finditer(text)})),
                text=text), "text", timeout=60)
            text, parts = shape(clean(fixed["text"]), "email")
        return {"text": text, "parts": parts, "subject": subject,
                "alternatives": [], "audience": "elder_informal", "audiences": ["elder_informal"], "learned": None}

    async def essay(self, ctx, question, notes, words=250):
        """Plan from the user's own notes, write in their formal voice, then check length and AI clichés (one fix)."""
        words = max(80, min(int(words), 900))
        system = self.formal_system(ctx, f"{question} {notes}", kind="essay")
        args = {"question": clean(question) or "(none given)", "notes": clean(notes)[:4000], "words": words}
        label = await self.spark(system, ESSAY_TASK.format(**args), "text", max_tokens=6000, timeout=90)
        as_list = lambda value: value if isinstance(value, list) else [value] if isinstance(value, str) else []
        outline = [clean(str(point)) for point in as_list(label.get("outline")) if clean(str(point))][:8]
        questions = [clean(str(q)) for q in as_list(label.get("questions")) if clean(str(q))][:3]
        text = clean(label["text"])
        problems = []
        count = len(text.split())
        if count > words * 1.15:  # shorter is allowed: thin notes make a shorter essay, not a padded one
            problems.append(f"it has {count} words, cut it to about {words} without losing facts")
        found = sorted({m.group(0) for m in CLICHES.finditer(text)})
        if found:
            problems.append("remove phrases that sound AI-written: " + ", ".join(found))
        if problems:
            fixed = await self.spark(system, ESSAY_FIX.format(problems="; ".join(problems), text=text), "text",
                                     max_tokens=6000, timeout=90)
            text = clean(fixed["text"])
        text, parts = shape(text, "essay")
        return {"text": text, "parts": parts, "outline": outline, "questions": questions, "words": len(text.split()),
                "cliches": sorted({m.group(0) for m in CLICHES.finditer(text)}), "alternatives": [],
                "audience": "elder_informal", "audiences": ["elder_informal"], "learned": None}

    async def learn(self, ctx, items):
        """What the user sent with the SaySo keyboard: [{audience, text, suggested?}]. Kept as their own messages
        (links, emails, phones and card numbers removed); a suggestion they changed before sending may teach a rule."""
        from parse_telegram import PASTED_CODE
        from parse_telegram import clean as scrub
        rows, rules = [], []
        for item in items:
            text = scrub(clean(item.get("text") or ""))
            if not text or len(text) > 1000 or PASTED_CODE.search(text) or item.get("audience") not in AUDIENCES:
                continue
            suggested = scrub(clean(item.get("suggested") or "")) or None  # compared with the scrubbed text
            rows.append({"audience": item["audience"], "text": text, "kind": "edited" if suggested else "typed",
                         **({"suggested": suggested} if suggested else {})})
            if suggested and suggested != text and len(rules) < 2:
                try:
                    label = await self.spark(LEARN_SYSTEM, f"Audience: {item['audience']}\nSuggested: {suggested}\n"
                                                           f"The user's version: {text}", "rule")
                    rule = clean(str(label.get("rule") or ""))
                except Unavailable:
                    rule = ""
                if rule:
                    styles.add_preference(ctx.id, rule)
                    rules.append(rule)
        if rows:
            styles.add_learned(ctx.id, rows)
        styles.commit()
        return {"learned": len(rows), "rules": rules}

    async def read_page(self, image, image_type="image/jpeg"):
        """A photo of an essay page or a screenshot of a sent email → the user's own text (Muse Spark vision)."""
        import documents as parse
        content = [{"type": "text", "text": "Transcribe the user's own text."},
                   {"type": "image_url", "image_url": {"url": f"data:{image_type};base64," + base64.b64encode(image).decode()}}]
        try:
            label = await self.spark(parse.READ_SYSTEM, content, "text", max_tokens=6000, timeout=90)
        except Unavailable:
            return ""
        return label["text"]

    async def transcribe(self, wav, language=None, mode=None, audience=None, context="", heard=""):
        """The user's voice note (mono 16-bit WAV) → text, with Muse Voice Transcribe, then a Muse Spark pass that
        fixes what it misheard. The audio is not kept.
          language  the app's language ("en", "ru"): Muse Voice Transcribe's language bias (it has no Russian)
          mode, audience  where the text goes in Chat (write, rewrite, reply, email, essay, fix; friends, …)
          context   the text the note is about (SaySo's last answer, the email being answered): its names become
                    keywords for the recognizer and the fix pass; used once, not stored
          heard     what the iPhone's own on-device recognizer heard: a second hearing for the fix pass, and the
                    answer if Muse Voice Transcribe fails"""
        language = language if language in ("en", "ru") else None
        heard = tidy_transcript(clean(heard or ""))[:4000]
        names = list(dict.fromkeys(names_in(context) + names_in(heard)))[:20]
        hints = {**({"languageBias": [ASR_LANGUAGES[language]]} if language in ASR_LANGUAGES else {}),
                 **({"keywords": names} if names else {})}
        audio = prepare_wav(wav)
        try:
            text = await self.recognize(audio, hints)
        except Unavailable:
            if not heard:
                raise
            text = ""  # Muse Voice Transcribe failed: the iPhone's hearing goes through the same fix pass
        text = tidy_transcript(text)
        if heard and transcript_language(heard) != transcript_language(text or heard, language):
            heard = ""  # recognized in the wrong language (e.g. a Russian iPhone locale for an English note)
        if not text:
            text, heard = heard, ""
        return await self.fix_transcript(text, language=language, mode=mode, audience=audience, names=names,
                                         heard=heard)

    async def recognize(self, audio, hints=None):
        """One Muse Voice Transcribe call; if it refuses the hints (400/422), once more without them."""
        for extra in ([hints, {}] if hints else [{}]):
            request = {"mode": "PUSH_TO_TALK", "model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV", **extra}
            try:
                response = await self.client.post(
                    TRANSCRIBE_URL, timeout=60, headers={"Authorization": f"Bearer {self.meta_key}"},
                    files={"request": (None, json.dumps(request), "application/json"),
                           "audio": ("voice.wav", audio, "audio/wav")})
                if extra and response.status_code in (400, 422):
                    continue
                response.raise_for_status()
                return clean(response.json().get("transcript") or "")
            except Exception:
                break
        raise Unavailable(502, "Muse Voice Transcribe did not answer")

    async def fix_transcript(self, text, language=None, mode=None, audience=None, names=(), heard=""):
        """Muse Spark fixes what the recognizer got wrong, with a prompt for the note's language (English has its own:
        sound-alike words, apostrophes, names) and what the note is for. Kept only if it stayed the same note: about
        the same length, and its words are the ones that were said (by Muse Voice Transcribe, the iPhone's second
        hearing or the known names); otherwise the tidied transcript goes out as it is."""
        lang = transcript_language(text, language)
        if len(text.split()) < (2 if heard else 4):
            return text
        lines = []
        if TRANSCRIPT_USE.get(mode):
            lines.append(f"The note is {TRANSCRIPT_USE[mode]}" + (f", for {audience}." if audience in AUDIENCES else "."))
        if names:
            lines.append("Known names: " + ", ".join(names))
        if heard and heard != text:
            lines.append("A second recognizer heard (it makes its own mistakes; where the two differ, take the words "
                         f"that fit the sentence): {heard}")
        user = "\n".join(lines + [f"Voice note: {text}"]) if lines else text
        try:
            fixed = clean(str((await self.spark(TRANSCRIPT_FIX_EN if lang == "en" else TRANSCRIPT_FIX, user, "text",
                                                max_tokens=2000, timeout=15))["text"]))
        except Exception:
            return text
        said, got = transcript_words(text), transcript_words(fixed)
        heard_words = transcript_words(heard) | transcript_words(" ".join(names))
        lengths = [len(text)] + ([len(heard)] if heard else [])
        if (not fixed or not got or transcript_language(fixed, lang) != lang
                or not any(0.7 <= len(fixed) / n <= 1.3 for n in lengths)
                or len(got - said - heard_words) > 0.3 * len(got)  # new words
                or len(said & got) < (0.5 if heard else 0.6 if lang == "en" else 0.7) * len(said)):  # dropped words
            return text
        return fixed

    async def feedback(self, ctx, audience, format, answer, edited=None, liked=False):
        """The user liked an answer or wrote their own version: it becomes an example; an edit may teach a rule."""
        from parse_telegram import clean as scrub
        text = scrub(clean(edited or answer))  # links, emails, phones and cards removed, as in learn()
        if not text or audience not in AUDIENCES:
            return {"learned": None}
        if format in FORMAL:  # a liked or corrected email/essay is formal writing, not a chat example for friends
            styles.add_documents(ctx.id, [(f"{'edited' if edited else 'liked'} in Chat", text)],
                                 kind="essay" if format == "essay" else "email")
            styles.commit()
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
