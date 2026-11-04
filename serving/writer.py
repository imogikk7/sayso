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
import guards  # noqa: E402  (no placeholders or self-introductions; serving/guards.py)
import length  # noqa: E402  (essay length loop; serving/length.py)
import memory  # noqa: E402  (the chat thread; serving/memory.py)
import series  # noqa: E402  (auto-series; serving/series.py)

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
                "wording, not bureaucratic; a short greeting is fine, a sign-off usually isn't needed (never two)",
    "email": "as a short email: one greeting line, one or two short paragraphs and one sign-off line without a "
             "name, each on its own line, all in the language of the message (Russian: \"Здравствуйте, …\" … \"С "
             "уважением\"; English: \"Hello …\" … \"Best regards\"; never both); capitalized sentences, proper "
             "punctuation, no slang or emoji (this overrides their casual habits), but the user's own plain wording",
}
FORMATS["essay"] = ("as an essay: paragraphs separated by blank lines, first person, the user's own facts only, in their "
                    "formal voice")
FORMAT_WORDS = {"message": 40, "series": 50, "official": 60, "email": 200, "essay": 900}
CHAT_FORMATS = {"message", "series"}  # the LoRA was trained on chats: it rewrites only these
FORMAL = {"official", "email", "essay"}
# Auto-series (serving/series.py): a long "message" to an audience the user writes to in series may come as several.
FORMATS[series.AUTO], FORMAT_WORDS[series.AUTO] = series.AUTO_FORMAT, series.AUTO_WORDS
CHAT_FORMATS.add(series.AUTO)
# Formal writing overrides the casual habits the shared style prompt asks for (slang, swearing, emoji, splitting).
FORMAL_NOTE = ("\n\nThis is formal writing: ignore the casual chat habits above (no slang, swearing, emoji or splitting "
               "into short messages); keep only the user's formal voice.")  # written in the user's formal voice (their own documents), not their chat one
# Phrases that make a text read as AI-written; an essay or email that has them is rewritten once.
CLICHES = re.compile(
    r"в современном мире|в наше время|игра(?:ет|ют) (важную|ключевую) роль|не секрет, что|неотъемлемой частью|"
    r"в заключение хочется|данная тема|является актуальн|на сегодняшний день|широкий спектр|уникальн(ая|ый) возможност|"
    r"\bdelve|tapestry|in today's (fast-paced )?world|plays a (crucial|vital|pivotal) role|a testament to|"
    r"navigat(e|ing) the complexities|in conclusion,|ever-evolving|unlock (the|my) potential|embark on", re.I)

# ---- official messages and emails: one language, nothing invented --------------------------------------------
# The bug this guards against (Nov 3, Official, "Спроси у профессора, будет ли керф по физике"): an English greeting
# and first sentence, then Russian filler ("Будем благодарны за обратную связь…"), "С уважением, Best regards". The
# formal profile listed the user's English and Russian greetings and sign-offs side by side, English email paragraphs
# were the only examples, and nothing said which language to write in or that nothing may be added.
CYRILLIC = re.compile("[а-яёәғқңөұүһі]", re.I)
LATIN = re.compile("[a-z]", re.I)
LANGUAGES = {"ru": "Russian", "en": "English", "kk": "Kazakh"}
SCRIPTS = {"ru": "cyr", "en": "lat", "kk": "cyr"}
ASKED_LANGUAGE = [  # the request explicitly names the language to write in
    ("en", re.compile(r"на английском|по-английски|на англ\b|\bin english\b|\binto english\b", re.I)),
    ("ru", re.compile(r"на русском|по-русски|\bin russian\b|\binto russian\b", re.I)),
    ("kk", re.compile(r"на казахском|по-казахски|қазақша|\bin kazakh\b", re.I)),
    ("other", re.compile(r"на (немецком|французском|испанском|китайском|корейском|японском|турецком|итальянском)|"
                         r"\bin (german|french|spanish|chinese|korean|japanese|turkish|italian)\b", re.I)),
]
SIGNOFF_WORDS = (r"с уважением|с наилучшими пожеланиями|всего доброго|всего хорошего|құрметпен|best regards|"
                 r"kind regards|warm regards|best wishes|yours sincerely|yours faithfully|yours truly|sincerely|regards")
# A sign-off starts a line or a sentence and ends the text, a line, or runs into another sign-off ("С уважением, Best
# regards"); "I sincerely hope" or "with regards to" in the body are not sign-offs.
SIGNOFF = re.compile(rf"(?:^|(?<=[\n.!?,;]))[ \t]*(?:{SIGNOFF_WORDS})[ \t]*[,.!]?"
                     rf"(?=[ \t]*(?:$|\n|(?:{SIGNOFF_WORDS})))", re.I)
# Things the model adds on its own in formal writing: offers, invented teams, thanks for feedback nobody asked for.
FILLER = re.compile(
    r"если у вас (возникнут|появятся|будут|есть) (какие-либо |какие-то |дополнительные )?вопрос|обратн\w+ связ|"
    r"с радостью (её |ее |их )?предостав|готов\w* (предоставить|ответить)|дополнительн\w+ (информаци|сведени)|"
    r"будем (рады|благодарны)|не стесняйтесь|уважаем\w+ команд|"
    r"if you have any (further |other |more )?questions|feel free to|(happy|glad) to provide|"
    r"(additional|further|more) (information|details)|do not hesitate|don't hesitate|dear [\w ]{0,20}team", re.I)
WE = re.compile(r"\b(мы|нас|нам|нами|наш|наша|наше|наши|нашего|нашей|нашему|нашим|наших|we|us|our|ours|we're|we'd|"
                r"we'll|we've)\b", re.I)
OUR_TIME = re.compile(r"в наше время|в наши дни|в нашем (мире|обществе)", re.I)  # idioms, not "we" (CLICHES fixes them)
# Who a formal message is for, when the text names them: this wins over the audience chip (often still "friends").
ADDRESSEE = re.compile(
    r"\b(профессор\w*|преподавател\w*|препод\w*|учител\w*|учительниц\w*|декан\w*|ректор\w*|куратор\w*|начальник\w*|"
    r"руководител\w*|директор\w*|менеджер\w*|работодател\w*|эйчар\w*|HR|professor|teacher|lecturer|instructor|dean|"
    r"boss|manager|supervisor|tutor|recruiter|employer)(?:e?s)?\b", re.I)
FORMAL_AUDIENCE = "elder_informal"  # the closest of the trained audiences to a professor or a boss

FORMAL_RULES = """Use only what the user gave you. Never invent facts, details, reasons, dates, names, numbers,
places, offers ("happy to provide more information", "если возникнут вопросы"), thanks for feedback, questions or
wishes that are not in the input. Never "we", "our team" or a company: the user writes as "I" (unless the input itself
says "we"). Address the person the way the input names them (a professor → "профессор" / "Professor"); never invent a
name, a title or a team, and never write placeholders like [Name]. Keep the user's own words for things exactly as they
wrote them (a course, an exam, an abbreviation or slang like «керф»): do not translate, expand, explain or guess what
they mean. A short or vague request gives a short, plain message (one to three sentences), not padding.
At most one greeting and at most one sign-off, both in the language of the message, never one in each language."""

FORMAL_SYSTEM = """You write official messages and emails for one specific user, the way they would write them
themselves: plain, direct and polite, in their own formal voice (below), never like a template or an AI.
{language}

""" + FORMAL_RULES


def script_of(text):
    """"cyr" or "lat", whichever the letters of `text` mostly are; None without letters."""
    c, l = len(CYRILLIC.findall(text or "")), len(LATIN.findall(text or ""))
    return None if not c + l else "cyr" if c >= l else "lat"


def language(text):
    """The language to write a formal text in: the one the request names ("на английском"), else the one it is
    written in ("ru", "en"; "kk" when Kazakh letters are a real share of it); "other" when it asks for a language we
    can't check; None without letters."""
    text = clean(text or "")
    for lang, pattern in ASKED_LANGUAGE:
        if pattern.search(text):
            return lang
    script = script_of(text)
    if script == "lat":
        return "en"
    if script == "cyr":
        kazakh = len(KAZAKH.findall(text))
        return "kk" if kazakh >= 3 and kazakh >= 0.04 * len(CYRILLIC.findall(text)) else "ru"
    return None


def language_rule(lang):
    if lang in LANGUAGES:
        name = LANGUAGES[lang]
        return (f"Language: {name}, the language of the user's request. Every sentence, the greeting, the sign-off and "
                f"any subject line are in {name}; not one sentence or phrase in another language (the user's own terms "
                f"stay exactly as they wrote them). The user's formal writing below may be in another language: take "
                f"only their manner from it, never its language, greetings or sign-offs.")
    if lang == "other":
        return "Language: the one the user asks for in the request; the whole text in that one language."
    return "Language: the language of the user's request; the whole text in that one language."


def addressee(text):
    """The person a formal message is for, as the text names them ("профессора"), or None."""
    found = ADDRESSEE.search(clean(text or ""))
    return found.group(0) if found else None


def signoffs(text):
    return list(SIGNOFF.finditer(text))


def dedupe_signoffs(text, lang=None):
    """One sign-off at most: "…предоставим. С уважением, Best regards" → "…предоставим. С уважением". Keeps the first
    one in the message's language (the first one if none is), drops the others."""
    found = signoffs(text)
    if len(found) < 2:
        return text
    script = SCRIPTS.get(lang) or script_of(SIGNOFF.sub("", text))
    keep = next((m for m in found if script_of(m.group(0)) == script), found[0])
    out, last = [], 0
    for m in found:
        if m is not keep:
            out.append(text[last:m.start()])
            last = m.end()
    out.append(text[last:])
    lines = [line.rstrip() for line in "".join(out).splitlines()]
    joined = "\n".join(line for i, line in enumerate(lines) if line or (i and lines[i - 1])).strip()
    return joined.rstrip(",;").rstrip()  # "…С уважением," left at the end


def foreign_sentences(text, lang, request=""):
    """Sentences (or lines) mostly in the other script than `lang`'s; the user's own words from the request
    ("керф", "Physics") don't count, and very short ones ("OK", a name) aren't judged."""
    script = SCRIPTS.get(lang)
    if not script:
        return []
    known = {w.casefold() for w in re.findall(r"[^\W\d_]+", clean(request))}
    found = []
    for sentence in re.split(r"(?<=[.!?…])\s+|\n+", text):
        tokens = [w for w in re.findall(r"[^\W\d_]+", sentence) if w.casefold() not in known and w != "Name"]
        joined = "".join(tokens)
        c, l = len(CYRILLIC.findall(joined)), len(LATIN.findall(joined))
        if c + l < 6:
            continue
        if (l if script == "cyr" else c) / (c + l) > 0.5:
            found.append(sentence.strip())
    return found


def formal_problems(text, lang, request=""):
    """What's wrong with an official message or email: mixed languages, two sign-offs, filler or "we" the user
    didn't write. Empty when it's fine."""
    problems = []
    foreign = foreign_sentences(text, lang, request)
    if foreign:
        problems.append(f"it mixes languages: write everything in {LANGUAGES.get(lang, 'one language')}, "
                        f"including «{foreign[0][:80]}»")
    if len(signoffs(text)) > 1:
        problems.append("it has more than one sign-off: keep one")
    filler = FILLER.search(text)
    if filler and not FILLER.search(request):
        problems.append(f"it adds what the user didn't say («{filler.group(0)}»): remove it")
    we = WE.search(OUR_TIME.sub("", text))
    if we and not WE.search(request):
        problems.append(f"it says «{we.group(0)}»: the user writes as I")
    return problems


EMAIL_TASK = """Write an email from the user{reply}.
What the user wants to say (their notes, maybe dictated): {notes}
Write it in their formal voice (below): greeting and sign-off the way they do it (one of each, in the email's
language), plain and direct, every fact from the notes, nothing invented. Same language as the notes{reply_lang}.
Return JSON only: {{"subject": "<short subject line>", "text": "<the email: greeting, paragraphs, sign-off, separated
by blank lines>"}}."""
FORMAL_FIX = """\n\nYour last answer had problems: {problems}. Write it again following every rule, with only what the
user gave you."""

ESSAY_TASK = """The user needs an essay.
Question or topic: {question}
Length: {length}.
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
FORMAL_VARIANT_COUNT = 3
FORMAL_RETURN = ("\nAlso put 3 other ways the user could write the same message in \"variants\": [\"...\", ...], "
                 "different wording or length, but the same language, the same facts and the same rules (nothing "
                 "added).\nReturn JSON only: {\"text\": \"<the message>\", \"variants\": [\"...\", ...]}.")

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

# Demo switch (SAYSO_CLEAN, on by default): nothing SaySo writes swears, whatever the user's own habits are.
CLEAN = __import__("os").environ.get("SAYSO_CLEAN", "on") == "on"
CLEAN_RULE = ("\n\nOverrides everything above: never use swear words, profanity or obscene words in any language "
              "(no Russian мат, not even softened or with asterisks), even where the user's style or examples do. "
              "Keep the rest of their style.")
MAT = re.compile(r"(?<![а-яё])(?:за|на|вы|по|у|от|разъ|съ|въ|подъ|до|при|о|рас)?(?:ёб|еб[аулинт])|ху[йеёяию]|пизд"
                 r"|(?<![а-яё])бля|(?<![а-яё])сук[аиу]|(?<![а-яё])сучк|муда[кч]|мудил|гандон|пид[оа]р|залуп"
                 r"|\bfuck|\bshit|\bbitch", re.I)


def swears(text):
    return CLEAN and bool(MAT.search(text or ""))


def unswear(value):
    """Last resort: the words that swear are cut out (strings, lists and dicts of them)."""
    if isinstance(value, str):
        if not swears(value):
            return value
        words = [x for x in value.split(" ") if not MAT.search(x)]
        return re.sub(r"\s+([,.!?)])", r"\1", " ".join(words)).strip(" ,") or value
    if isinstance(value, list):
        return [unswear(v) for v in value]
    if isinstance(value, dict):
        return {k: unswear(v) if k != "audiences" else v for k, v in value.items()}
    return value


def scrub(label):
    """Drop the variants or replies that swear; if the main text swears, a clean variant takes its place."""
    def ok(item):
        return not swears(item.get("text", "") if isinstance(item, dict) else json.dumps(item, ensure_ascii=False))
    for key, value in list(label.items()):
        if isinstance(value, list) and value and key != "audiences":
            label[key] = [v for v in value if ok(v)] or value
    if isinstance(label.get("text"), str) and swears(label["text"]):
        spare = [v for v in label.get("variants") or [] if isinstance(v, str) and not swears(v)]
        if spare:
            label["text"], label["variants"] = spare[0], spare[1:]
    return label


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
    if format == "series" and len(lines) == 1:
        lines = series.split(lines[0])  # an explicit series always splits
    if format in ("series", series.AUTO) and len(lines) > 1:
        parts = lines[:4] if format == "series" else series.cap(lines, series.MAX_PARTS)
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


CYRILLIC = re.compile(r"[а-яёәғқңөұүһі]", re.I)
LATIN = re.compile(r"[a-z]", re.I)


def is_cyrillic(text):
    return len(CYRILLIC.findall(text or "")) >= max(1, len(LATIN.findall(text or "")))


def preferred_ends(custom, text=""):
    """The greeting and sign-off the user picked in the Styles tab for an email in the language of `text` (Cyrillic or
    Latin): their default first, else the first of that language. (None, None) when they set none for it, so the
    parsed ones from their emails are used."""
    email = (custom or {}).get("email") or {}
    cyrillic = is_cyrillic(text)

    def pick(items, default):
        ordered = ([default] if default in items else []) + [i for i in items if i != default]
        return next((i for i in ordered if is_cyrillic(i) == cyrillic), None)
    return (pick(email.get("openers") or [], email.get("default_opener")),
            pick(email.get("signoffs") or [], email.get("default_signoff")))


def avoid_line(custom, kind):
    """"Never use: …" for the phrases the user marked as not theirs for this kind of text (message, email, essay)."""
    avoid = ((custom or {}).get(kind) or {}).get("avoid") or []
    return ("\nWords and phrases the user never uses (never write them): " + " · ".join(f"«{a}»" for a in avoid)
            if avoid else "")


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
        self.custom = styles.custom(style_id)  # set by hand in the Styles tab: greetings, sign-offs, phrases to avoid
        text = profile_text(profile)
        audiences = [a for a in AUDIENCES if self.examples.get((a, None))]
        shown = "\n".join(f"- {a}: " + " · ".join(f"«{one_message(e)}»" for e in self.sample(a, k=4, seed=0))
                          for a in audiences)
        style = ("The user's style, from their own chats (how they write, not who they are):\n" + text
                 + ("\n\nSome of their real messages:\n" + shown if shown else "") + self.rules()
                 + avoid_line(self.custom, "message"))
        self.read_system = read_system(style)
        self.style_text = ("The user's style, from their own chats:\n" + text + self.rules()
                           + avoid_line(self.custom, "message"))

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

    def formal_block(self, query=None, k=3, kind=None, lang=None):
        """The user's formal voice for official messages, emails and essays: their formal profile and the paragraphs of
        their own writing most like `query`, of the same kind first, then what they set by hand (greeting and sign-off
        in the language of `query`, phrases to avoid); empty if they have neither. With `lang`, only the greetings,
        sign-offs and paragraphs in that language's script (all paragraphs if none are), so an English email doesn't
        pull a Russian message into English."""
        own = self.custom_block(query, kind)
        if not self.documents:
            return ("\nWrite plainly and directly, like a real person, not like an AI." + own) if own else ""
        import documents as parse
        q = grams(query or "")
        def score(text):
            g = grams(text)
            return sum(min(n, g[gram]) for gram, n in q.items()) / (sum(g.values()) ** 0.5 or 1)
        docs, profile = self.documents, self.formal
        script = SCRIPTS.get(lang)
        if script:
            docs = [r for r in docs if script_of(r["text"]) == script] or docs
            profile = {**profile, **{key: [e for e in profile.get(key) or [] if script_of(e) in (script, None)]
                                     for key in ("openings", "closings")}}
        texts = sorted(docs, key=lambda r: (r.get("kind", "essay") != kind, -score(r["text"]) if q else 0))
        picked = [r["text"] for r in texts[:k]]
        rules = {"essay": "copy ONLY their voice: word choice, sentence length, linking words, how direct they are. "
                          "Never copy its structure, headings, format or topic: follow the structure the task asks for",
                 "email": "copy ONLY their manner: how they greet, ask and sign off, how formal and direct they are. "
                          "Never copy what those emails say"}[kind if kind in ("essay", "email") else "email"]
        return (guards.for_prompt(f"\nThe user's own formal writing, to {rules}:\n" + parse.profile_text(profile) + "\n"
                                  + "\n".join(f"«{' '.join(t.split()[:120])}»" for t in picked)) + own + guards.PROMPT_RULE)

    def custom_block(self, query=None, kind=None):
        """The user's own picks from the Styles tab; they override the greetings and sign-offs parsed above."""
        kind = "essay" if kind == "essay" else "email"
        lines = avoid_line(self.custom, kind)
        if kind == "email":
            opener, signoff = preferred_ends(self.custom, query)
            if opener:
                lines += (f"\nIf it opens with a greeting, use exactly the user's own: «{opener}» "
                          "(put the person's name for [Name], or leave the name out if it isn't known).")
            if signoff:
                lines += f"\nIf it signs off, use exactly the user's own sign-off: «{signoff}»."
        return lines

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
        groups = [texts[i * n:(i + 1) * n] for i in range(len(prompts))]
        if CLEAN:  # the LoRA learned the user's swearing: keep the clean ones, else cut the words out
            groups = [[t for t in g if not swears(t)] or [unswear(t) for t in g] for g in groups]
        return groups

    def best(self, ctx, candidates, audience, situation):
        usable = [c for c in candidates if c.strip() and not KAZAKH.search(c)] or [c for c in candidates if c.strip()]
        usable = [c for c in usable if not swears(c)] or usable
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
        user = memory.with_note(user)  # the chat thread's earlier turns, while a new-topic answer is written
        reading = system in (__import__("documents").READ_SYSTEM, TRANSCRIPT_FIX, TRANSCRIPT_FIX_EN, LEARN_SYSTEM)  # copies, not writes
        if CLEAN and not reading:
            system += CLEAN_RULE
        dirty = None
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
                if CLEAN and not reading and swears(json.dumps(scrub(label), ensure_ascii=False)):
                    dirty = dirty or label  # try the next model; use this one only if none answers cleanly
                    continue
                return label
            await asyncio.sleep(1)
        if dirty is not None:
            return unswear(dirty)
        raise Unavailable(502, "Muse Spark did not answer")

    def format_line(self, format):
        return f"\nFormat: write it {FORMATS.get(format, FORMATS['message'])}."

    async def examples(self, ctx, format, audience, situation=None, query=None):
        """The user's real messages for this audience: their approved and newest ones first, then the ones most like
        `query` (random without one); none for official messages and emails. Picking by similarity scored the same as
        random examples on Nov 1 (eval/style_gain.py), but costs nothing and keeps the topic close."""
        if format in FORMAL:
            if format == "essay":
                return ctx.formal_block(query, kind="essay")
            return ctx.formal_block(query, kind="email", lang=language(query or ""))
        first = ctx.approved.get(audience, [])[-2:] + ctx.recent.get(audience, [])[-2:]
        if self.retrieval == "local" and (query or "").strip():
            nearest = ctx.nearest(audience, clean(query)[:500])
            if nearest:
                return ctx.examples_for(audience, found=list(dict.fromkeys(first + nearest))[:EXAMPLES])
        return ctx.examples_for(audience, situation)

    async def formal(self, ctx, task, text, audience, format):
        """An official message or an email from rewrite/compose: the formal voice in the request's language, nothing
        invented, the person the text names wins over the audience chip. Every candidate (the answer and its variants)
        has its sign-offs deduplicated and is dropped if it still mixes languages or adds filler; if none is left,
        Muse Spark 1.3 writes it once more with the problems named, and the least bad one is used at worst."""
        lang = language(text)
        person = addressee(text)
        ask = {"rewrite": "Rewrite this draft the way the user would write it",
               "compose": COMPOSE}[task]
        to = (f" to the {person} the input names (politely formal to that person, whoever the user picked in the app)"
              if person else " to the person it is for")
        prompt = (f"{ask}{to}.{self.format_line(format)}\n{language_rule(lang)}{FORMAL_RETURN}\n\n{clean(text)}")
        system = self.formal_system(ctx, text, lang=lang)
        limit = FORMAT_WORDS.get(format, 60) * 2

        def candidates_of(label):
            variants = label.get("variants") if isinstance(label.get("variants"), list) else []
            written = [label["text"]] + [v for v in variants if isinstance(v, str)][:FORMAL_VARIANT_COUNT]
            if task == "compose":
                written = [w for w in written if not echoes(w, text)] or written
            shaped = (shape(dedupe_signoffs(clip(clean(v), limit), lang), format)[0] for v in written if clean(v))
            return list(dict.fromkeys(c for c in shaped if c))

        label = await self.spark(system, prompt, "text", writes=True)
        candidates = candidates_of(label)
        good = [c for c in candidates if not formal_problems(c, lang, text)]
        if not good:
            problems = formal_problems(candidates[0], lang, text) if candidates else ["it was empty"]
            try:  # Muse Spark 1.3 (writes=False) follows the language rule more strictly than Spark Open
                retry = candidates_of(await self.spark(system, prompt + FORMAL_FIX.format(problems="; ".join(problems)),
                                                       "text"))
            except Unavailable:
                retry = []
            good = [c for c in retry if not formal_problems(c, lang, text)]
            candidates = candidates + retry
            if not good:
                good = sorted(candidates, key=lambda c: len(formal_problems(c, lang, text)))[:1]
        if not good:
            raise Unavailable(502, "Muse Spark gave an empty answer, try again")
        out, parts = shape(good[0], format)
        return {"text": out, "parts": parts, "candidates": [out] + [c for c in good if c != out], "styled": False,
                "audiences": audiences_of({"audiences": [audience]}, FORMAL_AUDIENCE if person else audience)}

    async def styled(self, ctx, task, field, text, audience, situation, format="message"):
        if format in {"official", "email"}:  # never the LoRA (chats only) and never the casual chat style
            return await self.formal(ctx, task, text, audience, format)
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
                if format in {"official", "email"}:
                    draft = dedupe_signoffs(draft, language(messages or ""))
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
            lang = language(text) if format in {"official", "email"} else None
            voice = ctx.style_text if format not in FORMAL else (
                (ctx.formal_block(text, kind="essay" if format == "essay" else "email", lang=lang) or "Write plainly and directly, like a real person, not like an AI.") + ctx.rules() + FORMAL_NOTE
                + ("" if format == "essay" else f"\n{language_rule(lang)}\n{FORMAL_RULES}"))
            label = await self.spark(
                REVISE_SYSTEM.format(style=voice),
                f"{task}, to their {audience}.{self.format_line(format)}{await self.examples(ctx, format, audience, query=text)}\n\n"
                f"Input:\n{clean(text)}\n\nYour last answer:\n{clean(history[-1].get('answer', ''))}\n\n"
                f"The user's feedback so far:\n{clean(feedback)}", "text", writes=mode not in {"essay"},
                max_tokens=6000 if mode == "essay" else 3000, timeout=90 if mode == "essay" else 30)
            revised = clip(clean(label["text"]), FORMAT_WORDS.get(format, 40) * 2)
            out, parts = shape(dedupe_signoffs(revised, lang) if lang or format in {"official", "email"} else revised,
                               format)
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

    def formal_system(self, ctx, query, kind="email", lang=None):
        """The system prompt for official messages and emails (the language rule, nothing invented, the user's formal
        voice) or, with kind="essay", for essays (the shared style prompt without the chat style)."""
        voice = (ctx.formal_block(query, kind=kind, lang=lang if kind != "essay" else None)
                 or "The user hasn't added formal writing yet: write plainly and directly, like a real person, not "
                    "like an AI.")
        if kind == "essay":
            return STYLE_SYSTEM.split("Return JSON only")[0].format(style="") + "\n" + voice + ctx.rules() + FORMAL_NOTE
        return FORMAL_SYSTEM.format(language=language_rule(lang)) + "\n" + voice + ctx.rules()

    async def email(self, ctx, notes, reply_to=""):
        """Subject and body in the language of the user's notes (of the email being answered when the notes have no
        words), only what the notes say; one sign-off. A mixed-language or padded email is written once more by Muse
        Spark 1.3 with the problems named."""
        reply = f", answering this email:\n{clean(reply_to)[:3000]}\n" if reply_to.strip() else ""
        lang = language(notes) or language(reply_to)
        system = self.formal_system(ctx, f"{reply_to} {notes}", lang=lang)
        task = EMAIL_TASK.format(reply=reply, notes=clean(notes),
                                 reply_lang=" (or of the email being answered)" if reply else "")
        request = f"{notes}\n{reply_to}"

        def shaped(label):
            text = shape(dedupe_signoffs(clip(clean(label["text"]), FORMAT_WORDS["email"] * 2), lang), "email")[0]
            subject = clean(str(label.get("subject") or "")) or None
            return text, subject, formal_problems(f"{subject or ''}\n{text}", lang, request)

        text, subject, problems = shaped(await self.spark(system, task, "text", writes=True, timeout=60))
        if problems:
            try:
                again = shaped(await self.spark(system, task + FORMAL_FIX.format(problems="; ".join(problems)), "text",
                                                timeout=60))
                if len(again[2]) < len(problems):
                    text, subject, problems = again[0], again[1] or subject, again[2]
            except Unavailable:
                pass
        if CLICHES.search(text):  # the fix pass returns only the text: the subject stays
            fixed = await self.spark(system, ESSAY_FIX.format(
                problems="remove phrases that sound AI-written: " + ", ".join(sorted({m.group(0) for m in CLICHES.finditer(text)})),
                text=text), "text", timeout=60)
            text = shape(dedupe_signoffs(clean(fixed["text"]), lang), "email")[0]
        return {"text": text, "parts": [text], "subject": subject,
                "alternatives": [], "audience": FORMAL_AUDIENCE, "audiences": [FORMAL_AUDIENCE], "learned": None}

    async def essay(self, ctx, question, notes, words=250):
        """Plan from the user's own notes, write in their formal voice, then fit the length (serving/length.py: target
        ±10 %, expand or trim passes) and remove AI clichés."""
        words = max(80, min(int(words), 900))
        system = self.formal_system(ctx, f"{question} {notes}", kind="essay")
        args = {"question": clean(question) or "(none given)", "notes": clean(notes)[:4000], "words": words,
                "length": length.target(words)}
        label = await self.spark(system, ESSAY_TASK.format(**args), "text", max_tokens=6000, timeout=90)
        as_list = lambda value: value if isinstance(value, list) else [value] if isinstance(value, str) else []
        outline = [clean(str(point)) for point in as_list(label.get("outline")) if clean(str(point))][:8]
        questions = [clean(str(q)) for q in as_list(label.get("questions")) if clean(str(q))][:3]
        text = clean(label["text"])

        def cliches(t):
            found = sorted({m.group(0) for m in CLICHES.finditer(t)})
            return ["remove phrases that sound AI-written: " + ", ".join(found)] if found else []

        async def call(prompt):
            return await self.spark(system, prompt, "text", max_tokens=6000, timeout=90)
        # Under 90 % of the target: expand (up to 2 passes); over 115 %: trim; clichés go into the same pass.
        text, passes = await length.fit(call, text, words, args["notes"], cliches, clean)
        if not passes and cliches(text):
            fixed = await call(ESSAY_FIX.format(problems="; ".join(cliches(text)), text=text))
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
