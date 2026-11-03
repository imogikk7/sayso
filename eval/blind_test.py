"""Blind test v3: one message and its situation per question — did the user write it, or SaySo? Friends tap «Человек»
or «ИИ» on a page that opens on any phone.

Runs on the user's Mac: the pairs and the key are private (data/ is gitignored), the API is the deployed one.

  python3 eval/blind_test.py build [--n 20] [--generic 0] [--author NAME]
                                   # → data/blind/<test_id>/{test.html, questions.json, answers.json (the key)}
  .venv/bin/python eval/blind_test.py publish
                                   # test.html + questions.json → the sayso-data volume; prints the link to send
  python3 eval/blind_test.py score --server [SS3-… …]
                                   # answers from the server (and any codes) → eval/results/blind_test.json

build — takes reply pairs from data/pairs_v4/test.jsonl (held-out; the incoming side is only a neutral English summary
        of the other person's latest messages, no names, never their words), friends and family only. About half the
        questions show the user's **real** reply, half **SaySo**'s reply to another situation (POST {SAYSO_API_URL}/chat
        {mode: reply, text: "Что написал собеседник (пересказ): <summary>"}, as v2), and --generic N adds plain
        Muse Spark 1.3 answers as a control. Each question shows one message: never the real and the SaySo reply to
        the same situation. Muse Spark 1.3 screens every shown message (real and generated alike) and keeps it only if
        it is safe to show to many people (no names, places, phones, addresses; nothing intimate, about a partner,
        sexual, about health, no heavy swearing, no private details), friendly, not trivial («ок», «ахах») and with some
        personal manner; failing items are dropped and more are drawn. SaySo items are length-matched to the real ones
        (same share in each length third). The situation is shown in Russian («Друг спрашивает, пойдёшь ли ты вечером
        в кино»), written by Muse Spark from the summary. The page holds no key.
publish — uploads the page and the public questions to /blind/<test_id>/ on the sayso-data volume (the modal Python
        API, else `modal volume put`); the deployed API serves it at GET {SAYSO_API_URL}/blind/<test_id> with no
        auth (the id is long and random) and stores answers posted to /blind/<test_id>/answers.
score — per question the share answered «Человек»; the key numbers: the human-rate of real messages vs of SaySo's
        (close = people can't tell them apart), with a 95% CI of the difference and Fisher's exact two-proportion p,
        plus accuracy vs 50% (exact binomial), per person and overall. --server pulls the answers (GET
        /blind/<id>/responses with SAYSO_API_TOKEN); SS3- codes from the page's fallback also count. SS1-/SS2- codes
        (and v2 keys) still decode and score as before. Writes aggregate numbers only (no message text, no names, no
        test id) to eval/results/blind_test.json.

Needs SAYSO_API_URL, SAYSO_API_TOKEN and META_API_KEY in .env (or the environment).
"""

import argparse
import base64
import binascii
import datetime
import hashlib
import itertools
import json
import math
import os
import random
import re
import secrets
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAIRS = ROOT / "data" / "pairs_v4" / "test.jsonl"
OUT = ROOT / "data" / "blind"
TEMPLATE = Path(__file__).resolve().parent / "blind_template.html"
RESULTS = ROOT / "eval" / "results" / "blind_test.json"
VERSION = 3
CODE_PREFIX = "SS3-"
CODE_PREFIXES = ("SS1-", "SS2-", "SS3-")  # v1 and v2 codes still decode
LETTERS = "ABC"
SOURCES = ("real", "sayso", "generic")  # v2: the three options of a question; v3: what wrote the shown message
CHANCE = 1 / 3
MIN_CHARS, MAX_CHARS = 8, 280
VOLUME = "sayso-data"
META_URL = "https://api.meta.ai/v1/chat/completions"
META_MODEL = "muse-spark-1.3"
PLACEHOLDER = re.compile(r"\[(?:sticker|photo|video|voice|file|media|link|url|phone|email|card)[^\]]*\]", re.I)
LAUGH_WORDS = re.compile(r"лол|lol|ору|ржу|kek|кек")
LAUGHTER = re.compile(r"(?:[аaхxhеeи]*[хxh][аaхxhеeи]*|лол|lol|ору|ржу|kek|кек)+")
DIGITS = re.compile(r"\d[\d\s()+-]{5,}\d")  # phone- or card-like: never on a page for many people

AUDIENCES = ("friends", "family")  # v3: no partner (intimate) and no elders (names, formal)
WHO_RU = {"partner": "Партнёр", "friends": "Друг", "family": "Семья", "elder_informal": "Преподаватель или старший",
          "formal": "Коллега"}
WHO_START = {"friends": "Друг", "family": "Кто-то из семьи"}
WHO_EN = {"partner": "your partner", "friends": "a friend", "family": "a family member",
          "elder_informal": "an older person you know well (a teacher or an elder), informal but respectful",
          "formal": "a colleague"}
SAYSO_TEXT = "Что написал собеседник (пересказ): {summary}"
TRANSLATE_SYSTEM = ("You turn a short neutral English summary of what someone wrote in a chat into one short, natural "
                    "Russian sentence that sets the scene for a quiz. Start with «{who}» and speak of the reader as "
                    "«ты», e.g. «Друг спрашивает, пойдёшь ли ты вечером в кино». Keep the meaning, keep it neutral and "
                    "short, no names, no places, no quotes, add nothing. "
                    'Return JSON only: {{"ru": "..."}}')
VET_SYSTEM = (
    "You screen one item of a blind test that will be shown to many people (the author's friends). The item is a short "
    "situation and a chat message. Return JSON only: "
    '{"safe": true|false, "normal": true|false, "trivial": true|false, "personal": true|false, "fits": true|false}.\n'
    "safe: false if the message or the situation contains a person's name or nickname, a place someone could "
    "identify (a street, district, school, workplace, venue), a phone, an address, an account or another private "
    "detail; anything intimate, romantic, about a partner or sexual; health, illness or medicine; heavy swearing; "
    "money troubles, gossip or conflicts about other people. Otherwise true.\n"
    "normal: friendly, everyday, nothing a reader could find hurtful, embarrassing or strange to show.\n"
    "trivial: true if it is too short or generic to show any personal manner («ок», «да», «ахах», «спасибо», a lone "
    "emoji or a single word).\n"
    "personal: it has some personal manner of writing (wording, slang, punctuation, letter case, emoji, rhythm) that "
    "a careful reader could pick up on.\n"
    "fits: the message is a natural reply in that situation.")
GENERIC_SYSTEM = "You are a helpful assistant."
GENERIC_USER = ("Someone ({who}) wrote to you; here is what they said, retold: {summary}\n"
                "Write your short casual reply to them in Russian, as yourself answering them (not as them). "
                "Return only the reply text.")


# ---------------------------------------------------------------- config and API

def env(keys=("SAYSO_API_URL", "SAYSO_API_TOKEN", "META_API_KEY")):
    """Keys from the environment, else from .env (never printed, never written)."""
    values = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.strip().split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
    values.update({k: os.environ[k] for k in keys if k in os.environ})
    missing = [k for k in keys if not values.get(k)]
    if missing:
        sys.exit(f"missing {', '.join(missing)} in .env")
    return values


def ssl_context():
    try:  # python.org builds on macOS ship without root certificates
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def http(method, url, token, body=None, timeout=120):
    """→ (status, parsed JSON or None). Network errors count as status 0."""
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context()) as response:
            raw = response.read()
            if "json" not in response.headers.get("Content-Type", "json"):
                return response.status, raw.decode("utf-8", "replace")
            return response.status, json.loads(raw or b"null")
    except urllib.error.HTTPError as error:
        return error.code, None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return 0, None


class Api:
    """The deployed SaySo API."""

    def __init__(self, url, token, request=http, sleep=time.sleep, attempts=4, wait=15):
        self.url, self.token, self.request, self.sleep = url.rstrip("/"), token, request, sleep
        self.attempts, self.wait = attempts, wait

    def warmup(self):
        """→ "ready", "off" (the server runs with the GPU off: Muse Spark Open writes in the user's style, which is the
        product as deployed) or "cold"."""
        status, out = self.request("GET", self.url + "/warmup", self.token, timeout=900)
        if status == 200 and isinstance(out, dict) and out.get("gpu") == "off":
            return "off"
        return "ready" if status == 200 and (not isinstance(out, dict) or out.get("ready", True)) else "cold"

    def reply(self, summary, audience):
        """SaySo's reply to the situation, in the user's style for this audience."""
        body = {"mode": "reply", "text": SAYSO_TEXT.format(summary=summary), "audience": audience, "format": "message"}
        status = None
        for attempt in range(self.attempts):
            status, out = self.request("POST", self.url + "/chat", self.token, body)
            if status == 401:
                sys.exit("401 from /chat: check SAYSO_API_TOKEN in .env")
            if status == 200 and isinstance(out, dict) and isinstance(out.get("text"), str) and out["text"].strip():
                return out["text"]
            if attempt < self.attempts - 1:
                self.sleep(self.wait)
        raise RuntimeError(f"/chat failed (last status {status})")

    def responses(self, test_id):
        """The answers friends posted to the published test (authenticated)."""
        status, out = self.request("GET", f"{self.url}/blind/{test_id}/responses", self.token)
        if status == 401:
            sys.exit("401 from /blind/…/responses: check SAYSO_API_TOKEN in .env")
        if status == 404:
            sys.exit("the server has no such test: publish it first (and deploy the API with the /blind routes)")
        if status != 200 or not isinstance(out, dict) or not isinstance(out.get("responses"), list):
            raise RuntimeError(f"/blind/…/responses failed (status {status})")
        return out["responses"]

    def page(self, test_id):
        """→ status of the public page (no token sent)."""
        status, _ = self.request("GET", f"{self.url}/blind/{test_id}", None)
        return status


class Spark:
    """Muse Spark 1.3 on the Meta Model API: screens items, writes the Russian situation and the generic AI's reply."""

    def __init__(self, key, request=http, sleep=time.sleep, attempts=3, url=META_URL):
        self.key, self.request, self.sleep, self.attempts, self.url = key, request, sleep, attempts, url

    def ask(self, system, user, max_tokens=2000):
        body = {"model": META_MODEL, "reasoning_effort": "low", "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        status = None
        for attempt in range(self.attempts):
            status, out = self.request("POST", self.url, self.key, body)
            if status == 401:
                sys.exit("401 from the Meta Model API: check META_API_KEY in .env")
            try:
                text = (out["choices"][0]["message"].get("content") or "").strip()
            except (TypeError, KeyError, IndexError, AttributeError):
                text = ""
            if status == 200 and text:
                return text
            if attempt < self.attempts - 1:
                self.sleep(2 * (attempt + 1))
        raise RuntimeError(f"Muse Spark failed (last status {status})")

    def vet(self, summary, text):
        """Whether this message, with its situation, may be shown to many people (see VET_SYSTEM). Anything unclear
        (no JSON, an error) is a no: the item is dropped and another one drawn."""
        try:
            answer = self.ask(VET_SYSTEM, f"Situation: {summary}\nMessage: {text}", max_tokens=2000)
            label = json.loads(re.search(r"\{.*\}", answer, re.S).group(0))
        except (RuntimeError, AttributeError, ValueError):
            return False
        return (label.get("safe") is True and label.get("normal") is True and label.get("trivial") is False
                and label.get("personal") is True and label.get("fits") is True)

    def translate(self, summary, audience="friends"):
        """The neutral English summary → one Russian sentence for the page, starting with who it is."""
        text = self.ask(TRANSLATE_SYSTEM.format(who=WHO_START.get(audience, "Друг")), summary)
        match = re.search(r"\{.*\}", text, re.S)
        try:
            ru = json.loads(match.group(0)).get("ru") if match else None
        except (json.JSONDecodeError, AttributeError):
            ru = None
        return unquote(ru if isinstance(ru, str) and ru.strip() else text)

    def generic(self, summary, audience):
        """A plain assistant's reply: no style, no profile, no examples — the baseline people already have."""
        return unquote(self.ask(GENERIC_SYSTEM, GENERIC_USER.format(summary=summary,
                                                                    who=WHO_EN.get(audience, "someone"))))


# ---------------------------------------------------------------- build

def unquote(text):
    previous = None
    while text != previous:
        previous = text
        text = re.sub(r"^(?:ответ|reply|answer)\s*:\s*", "", text.strip(), flags=re.I)
        if len(text) >= 2 and text[0] + text[-1] in ('""', "«»", "''", "“”", "„“"):
            text = text[1:-1].strip()
    return text


def parts_of(text):
    """Lines of a message = messages sent in a row; shown as stacked bubbles whoever wrote them."""
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def chars(parts):
    return len(" ".join(parts))


def incoming_of(user_content):
    match = re.search(r"^incoming:[ \t]*(.*)\Z", user_content, re.M | re.S)
    return " ".join(match.group(1).split()) if match else None


def load_pairs(path, splits=("test",)):
    """Reply pairs only: {summary, real, audience, situation, turn_id}. Real = the user's own reply. Held-out (test)
    turns by default; `splits` can add the training turns when the held-out ones are too few to fill a test."""
    pairs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        meta = row.get("meta") or {}
        if meta.get("task") != "reply" or meta.get("split", "test") not in splits:
            continue
        roles = {m["role"]: m["content"] for m in row.get("messages", [])}
        summary, real = incoming_of(roles.get("user", "")), (roles.get("assistant") or "").strip()
        if not summary or not real:
            continue
        pairs.append({"summary": summary, "real": real, "audience": meta.get("audience", "friends"),
                      "situation": meta.get("situation", "other"), "turn_id": meta.get("turn_id")})
    return pairs


def trivial(text):
    """Only emoji, punctuation or laughter ("ахахах", "))", "😂😂", "lol"): nothing to tell apart."""
    letters = "".join(ch for ch in text.casefold() if ch.isalpha())
    if not letters:
        return True
    # Plain set checks: the old one-regex version backtracked exponentially on long messages made of those letters.
    rest = LAUGH_WORDS.sub("", letters)  # «лол», «ору» and the like, then what's left must be «ахах»-letters only
    return not rest or (set(rest) <= set("аaхxhеeи") and any(ch in "хxh" for ch in rest))


def showable(parts):
    """The cheap checks before Muse Spark looks: a sane length, words, no placeholders, links or long numbers."""
    text = " ".join(parts)
    return (MIN_CHARS <= len(text) <= MAX_CHARS and not trivial(text) and not PLACEHOLDER.search(text)
            and "http" not in text.lower() and "@" not in text and not DIGITS.search(text))


def usable(pair):
    return pair["audience"] in AUDIENCES and showable(parts_of(pair["real"]))


def length_edges(lengths, bins=3):
    """Cut points that split the real messages' lengths into `bins` groups of about the same size."""
    ordered = sorted(lengths)
    if not ordered:
        return []
    return sorted({ordered[min(len(ordered) - 1, len(ordered) * k // bins)] for k in range(1, bins)})


def bin_of(length, edges):
    return sum(length >= edge for edge in edges)


def quotas(lengths, edges, total):
    """How many SaySo items each length group should get: the real items' shares, rounded by largest remainder."""
    groups = len(edges) + 1
    counts = [0] * groups
    for length in lengths:
        counts[bin_of(length, edges)] += 1
    if not lengths or total <= 0:
        return [0] * groups
    exact = [total * c / len(lengths) for c in counts]
    out = [int(x) for x in exact]
    for i in sorted(range(groups), key=lambda i: -(exact[i] - out[i]))[:total - sum(out)]:
        out[i] += 1
    return out


def closest(spare, want, edges, lengths):
    """The spare item whose length is nearest to the real items of group `want` (when a group can't be filled)."""
    group = [x for x in lengths if bin_of(x, edges) == want] or lengths
    middle = sorted(group)[len(group) // 2]
    return min(spare, key=lambda item: abs(item["chars"] - middle))


MEDIA = re.compile(r"\b(?:media|file|photo|picture|image|screenshot|video|voice|sticker|forward\w*|link|"
                   r"without (?:any )?text|no text|can't see|cannot see|attachment|gif|meme|emoji\w*|unclear|"
                   r"without (?:any )?context|no context|single (?:letter|word)|one letter|random|meaningless|nonsense|"
                   r"cryptic|incomprehensible|gibberish|just says|only says|typo\w*|fragment|unfinished)\b", re.I)


def russian(parts):
    """Cyrillic writing (the questions are in Russian, so a Latin or translit answer gives itself away) and no
    keyboard-smash words («хмхсхаххааххахап»)."""
    text = " ".join(parts)
    cyr = sum("а" <= ch.casefold() <= "я" or ch.casefold() == "ё" for ch in text)
    lat = sum("a" <= ch.casefold() <= "z" for ch in text)
    words = re.findall(r"[^\W\d_]+", text)
    return cyr > 0 and lat <= cyr * 0.1 and all(len(w) <= 14 for w in words)


def run_all(fn, batch):
    """fn over the batch on parallel threads (each call waits on the network), results in the batch's order."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(1, len(batch))) as pool:
        return list(pool.map(fn, batch))


def build(n=20, pairs_path=PAIRS, out_dir=OUT, api=None, spark=None, seed=None, warmup=True, log=print, generic=0,
          author="", post_url=None, max_draws=None, workers=12, splits=("test",), max_parts=None):
    """→ the key. Writes <out_dir>/<test_id>/{test.html, questions.json, answers.json} and <out_dir>/latest.json."""
    rng = random.Random(seed)
    pairs, seen = [], set()
    for pair in load_pairs(pairs_path, splits):
        text = " ".join(parts_of(pair["real"])).casefold()
        if usable(pair) and text not in seen:
            seen.add(text)
            pairs.append(pair)
    rng.shuffle(pairs)
    if not pairs:
        sys.exit(f"no usable friends/family reply pairs in {pairs_path}")
    generic = max(0, min(generic, n - 2))
    want = {"sayso": (n - generic) // 2, "generic": generic}
    want["real"] = n - generic - want["sayso"]
    if len(pairs) < n:
        log(f"only {len(pairs)} usable pairs, the test will have fewer than {n} questions")

    writer = "unknown"
    if warmup:
        log("waking the GPU (/warmup, a cold start takes minutes)…")
        writer = api.warmup()
        if writer == "off":
            log("  the server runs with the GPU off: testing what it writes now (Muse Spark Open in the user's style)")
        elif writer != "ready":
            log("  /warmup didn't answer 200; trying anyway")

    pool = iter(pairs)  # each situation is used once: never the real and the SaySo reply to the same one
    items = {"real": [], "sayso": [], "generic": []}
    dropped = defaultdict(int)

    def item(pair, source, parts):
        return {"source": source, "audience": pair["audience"], "situation": pair["situation"],
                "summary": pair["summary"], "parts": parts, "chars": chars(parts), "turn_id": pair["turn_id"]}

    def screened(pair, parts, source):
        if not parts or not showable(parts):
            dropped[f"{source}: too short, too long or has links/numbers"] += 1
            return False
        if MEDIA.search(pair["summary"]):
            dropped[f"{source}: the situation is about a file, photo or forward"] += 1
            return False
        if max_parts and len(parts) > max_parts:
            dropped[f"{source}: more than {max_parts} message(s)"] += 1
            return False
        if not russian(parts):
            dropped[f"{source}: not in Russian (Cyrillic) or a keyboard smash"] += 1
            return False
        if not spark.vet(pair["summary"], " / ".join(parts)):
            dropped[f"{source}: Muse Spark said not safe, trivial or plain"] += 1
            return False
        return True

    log(f"picking {want['real']} real messages…")
    def screen_real(pair):
        parts = parts_of(pair["real"])
        return pair, parts, screened(pair, parts, "real")

    while len(items["real"]) < want["real"]:
        batch = list(itertools.islice(pool, workers))
        if not batch:
            break
        for pair, parts, ok in run_all(screen_real, batch):
            if ok and len(items["real"]) < want["real"]:
                items["real"].append(item(pair, "real", parts))
                log(f"  real {len(items['real'])}/{want['real']}")

    # A situation dropped above for the user's reply (a series, a smash, Spark's no) is still a fine one to answer:
    # SaySo and the controls draw from every situation not shown with a real reply.
    shown = {i["summary"] for i in items["real"]}
    pool = iter([p for p in pairs if p["summary"] not in shown and not MEDIA.search(p["summary"])])

    if want["generic"]:
        log(f"writing {want['generic']} generic AI controls…")
    for pair in pool:
        if len(items["generic"]) == want["generic"]:
            break
        try:
            parts = parts_of(spark.generic(pair["summary"], pair["audience"]))
        except RuntimeError as error:
            sys.exit(str(error))
        if screened(pair, parts, "generic"):
            items["generic"].append(item(pair, "generic", parts))

    real_lengths = [i["chars"] for i in items["real"]]
    edges = length_edges(real_lengths)
    quota = quotas(real_lengths, edges, want["sayso"])
    filled, spare = [0] * len(quota), []
    draws, limit = 0, max_draws if max_draws is not None else 30 * want["sayso"] + 20
    log(f"writing {want['sayso']} SaySo messages (length groups {quota}, cut at {edges} chars)…")
    def write_sayso(pair):
        try:
            parts = parts_of(api.reply(pair["summary"], pair["audience"]))
        except RuntimeError as error:
            return pair, None, str(error)
        return pair, parts, screened(pair, parts, "sayso")

    used_texts = set()
    while len(items["sayso"]) < want["sayso"] and draws < limit:
        batch = list(itertools.islice(pool, min(max(1, workers // 2), limit - draws)))  # the API: a few at a time
        if not batch:
            break
        draws += len(batch)
        results = run_all(write_sayso, batch)
        if all(isinstance(ok, str) for _, _, ok in results):
            sys.exit(results[0][2])
        for pair, parts, ok in results:
            if isinstance(ok, str):
                dropped[f"sayso: the API failed ({ok[:60]})"] += 1
            if ok is not True:
                continue
            key = " ".join(parts).casefold().strip(" .!?")
            if key in used_texts:
                dropped["sayso: the same text as another item"] += 1
                continue
            used_texts.add(key)
            candidate = item(pair, "sayso", parts)
            group = bin_of(candidate["chars"], edges)
            if filled[group] < quota[group] and len(items["sayso"]) < want["sayso"]:
                filled[group] += 1
                items["sayso"].append(candidate)
                log(f"  SaySo {len(items['sayso'])}/{want['sayso']}")
            else:
                spare.append(candidate)
                dropped["sayso: its length group was full"] += 1
    while len(items["sayso"]) < want["sayso"] and spare:  # groups that never filled: the nearest lengths left
        group = max(range(len(quota)), key=lambda g: quota[g] - filled[g])
        best = closest(spare, group, edges, real_lengths)
        spare.remove(best)
        filled[group] += 1
        items["sayso"].append(best)

    for reason, count in sorted(dropped.items()):
        log(f"  dropped {count}: {reason}")
    for source in SOURCES:
        if len(items[source]) < want[source]:
            log(f"  only {len(items[source])} of {want[source]} {source} items passed: the test is shorter")
    questions = [i for source in SOURCES for i in items[source]]
    if not items["real"] or not items["sayso"]:
        sys.exit("not enough items passed the filter for a test (need real and SaySo messages)")
    rng.shuffle(questions)
    try:
        for i, q in enumerate(questions, 1):
            q["id"] = f"q{i}"
            q["context"] = spark.translate(q["summary"], q["audience"])
    except RuntimeError as error:
        sys.exit(str(error))
    questions = [{k: q[k] for k in ("id", "source", "audience", "situation", "summary", "context", "parts", "chars",
                                    "turn_id")} for q in questions]

    test_id = secrets.token_urlsafe(18)  # 24 characters: the page's address, unguessable
    folder = Path(out_dir) / test_id
    folder.mkdir(parents=True, exist_ok=True)
    key = {"version": VERSION, "test_id": test_id, "created": datetime.datetime.now().isoformat(timespec="seconds"),
           "source": Path(pairs_path).name, "writer": writer, "author": author, "questions": questions,
           "lengths": {s: median([q["chars"] for q in questions if q["source"] == s]) for s in SOURCES}}
    page = public(key, post_url(test_id) if callable(post_url) else post_url)
    (folder / "answers.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    (folder / "questions.json").write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    (folder / "test.html").write_text(render(page), encoding="utf-8")
    (Path(out_dir) / "latest.json").write_text(json.dumps({"test_id": test_id}), encoding="utf-8")
    counts = {s: len(items[s]) for s in SOURCES}
    log(f"wrote {folder}/ — {len(questions)} questions ({counts['real']} real, {counts['sayso']} SaySo, "
        f"{counts['generic']} generic), median length {key['lengths']}; the key is answers.json (keep it private)")
    log("next: publish it (after deploying the API): .venv/bin/python eval/blind_test.py publish")
    return key


def median(values):
    ordered = sorted(values)
    if not ordered:
        return None
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def public(key, post_url=None):
    """What the page (and the server) may know: the Russian situation and the message, in order. No source, no key, no
    English summary, no audience or situation tags, no turn ids."""
    page = {"version": VERSION, "test_id": key["test_id"], "author": key.get("author") or "",
            "questions": [{"id": q["id"], "context": q["context"], "parts": q["parts"]} for q in key["questions"]]}
    if post_url:
        page["post"] = post_url  # where the page posts its answers when opened as a file
    return page


def render(page):
    data = (json.dumps(page, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    return TEMPLATE.read_text(encoding="utf-8").replace("__BLIND_DATA__", data)


def author_default():
    """The name in the question («Это написал(а) <name> или ИИ?»): --author, else data/config.json "blind_author",
    else the first word of "self_name"; empty → «Это написал человек или ИИ?»."""
    try:
        config = json.loads((ROOT / "data" / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    name = config.get("blind_author") or (config.get("self_name") or "").split(" ")[0]
    return name.strip() if isinstance(name, str) else ""


# ---------------------------------------------------------------- publish

def latest_id(out_dir=OUT):
    try:
        return json.loads((Path(out_dir) / "latest.json").read_text(encoding="utf-8"))["test_id"]
    except (OSError, ValueError, KeyError):
        sys.exit(f"no v3 test in {out_dir}: run build first (or pass --test)")


def modal_put(files, volume=VOLUME):
    """[(local path, remote path)] → the volume. The modal Python API when it imports, else the modal CLI."""
    try:
        import modal
    except ImportError:
        modal = None
    if modal is not None:
        vol = modal.Volume.from_name(volume)
        with vol.batch_upload(force=True) as batch:
            for local, remote in files:
                batch.put_file(str(local), remote)
        return
    cli = ROOT / ".venv" / "bin" / "modal"
    cli = str(cli) if cli.exists() else shutil.which("modal")
    if not cli:
        sys.exit("needs Modal: run it with .venv/bin/python (or install the modal CLI)")
    for local, remote in files:
        subprocess.run([cli, "volume", "put", "--force", volume, str(local), remote], check=True)


def publish(test_id, api, out_dir=OUT, put=modal_put, log=print):
    """Uploads test.html and questions.json (never answers.json) to /blind/<id>/ and checks the page answers."""
    folder = Path(out_dir) / test_id
    files = [(folder / name, f"/blind/{test_id}/{name}") for name in ("test.html", "questions.json")]
    for local, _ in files:
        if not local.exists():
            sys.exit(f"missing {local}: run build first")
    put(files)
    url = f"{api.url}/blind/{test_id}"
    status = api.page(test_id)
    if status == 200:
        log("uploaded; the page answers 200")
    else:
        log(f"uploaded, but the page answered {status or 'nothing'}: deploy the API first "
            "(SAYSO_GPU=off .venv/bin/modal deploy serving/modal_app.py), then open the link once")
    log(f"\nsend this link:\n{url}\n")
    return url


# ---------------------------------------------------------------- score

def decode(code):
    """A result code from the page → {version, test_id, name, choices: {question id: choice}} (+ sid for v3).
    SS3- codes carry «Человек»/«ИИ» as H/A per question in order; SS2- codes pick among A/B/C; v1 SS1- among A/B."""
    text = re.sub(r"\s+", "", code)
    version = 2
    for prefix in CODE_PREFIXES:
        if text.upper().startswith(prefix):
            text, version = text[len(prefix):], int(prefix[2])
            break
    try:
        raw = json.loads(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)).decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"not a blind-test code: {code[:24]}…") from error
    if not isinstance(raw, dict):
        raise ValueError(f"not a blind-test code: {code[:24]}…")
    if raw.get("v") == 3 or (version == 3 and "a" in raw):
        if not isinstance(raw.get("a"), str):
            raise ValueError(f"not a blind-test code: {code[:24]}…")
        return {"version": 3, "test_id": raw.get("t"), "name": str(raw.get("n") or "").strip()[:40],
                "sid": str(raw.get("s") or ""),
                "choices": {f"q{i}": c for i, c in enumerate(raw["a"][:200], 1) if c in ("H", "A")}}
    if not isinstance(raw.get("c"), dict):
        raise ValueError(f"not a blind-test code: {code[:24]}…")
    version = raw.get("v") if raw.get("v") in (1, 2) else version
    valid = LETTERS if version == 2 else "AB"
    choices = {str(k): v for k, v in raw["c"].items() if isinstance(v, str) and len(v) == 1 and v in valid}
    return {"version": version, "test_id": raw.get("t"), "name": str(raw.get("n") or "").strip()[:40],
            "choices": choices}


def binomial_p(k, n, p=CHANCE):
    """Exact binomial test of k successes in n against probability p → (two-sided p, one-sided p of ≥ k)."""
    if n == 0:
        return 1.0, 1.0
    probs = [math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(n + 1)]
    two = sum(q for q in probs if q <= probs[k] * (1 + 1e-9))
    return min(1.0, two), min(1.0, sum(probs[k:]))


def fisher_p(a, n1, c, n2):
    """Fisher's exact two-sided test that a/n1 and c/n2 come from the same proportion (an exact two-proportion test)."""
    if not n1 or not n2:
        return 1.0
    total, column = n1 + n2, a + c
    low, high = max(0, column - n2), min(column, n1)
    denominator = math.comb(total, column)
    probs = {x: math.comb(n1, x) * math.comb(n2, column - x) / denominator for x in range(low, high + 1)}
    return min(1.0, sum(q for q in probs.values() if q <= probs[a] * (1 + 1e-9)))


def wilson(k, n, z=1.96):
    if not n:
        return 0.0, 1.0
    p = k / n
    centre, half = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - half) / (1 + z * z / n), (centre + half) / (1 + z * z / n)


def difference_ci(k1, n1, k2, n2):
    """95% CI of k1/n1 − k2/n2 (Newcombe's hybrid score interval: sane with small counts and rates near 0 or 1)."""
    if not n1 or not n2:
        return None
    p1, p2 = k1 / n1, k2 / n2
    (l1, u1), (l2, u2) = wilson(k1, n1), wilson(k2, n2)
    d = p1 - p2
    return [round(d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), 3),
            round(d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2), 3)]


def rate(k, n):
    return round(k / n, 3) if n else None


def load_key(path):
    key = json.loads(Path(path).read_text(encoding="utf-8"))
    if key.get("version") not in (2, 3):
        sys.exit("this key is from the v1 test (two options per question); only v2 and v3 keys are scored")
    return key


def score(codes, answers_path=None, results_path=RESULTS, log=print, responses=()):
    """Dispatches on the key's version: v3 (human or AI per message) or v2 (pick the real one of three)."""
    key = load_key(answers_path)
    if key["version"] == 2:
        return score_v2(key, codes, results_path, log)
    return score_v3(key, codes, responses, results_path, log)


def people_v3(key, codes, responses, log=print):
    """Server responses and SS3 codes → one answer set per person (the last one per page session wins)."""
    ids = [q["id"] for q in key["questions"]]
    latest = {}
    for i, row in enumerate(sorted(responses, key=lambda r: r.get("at") or 0) if responses else []):
        answers = row.get("answers") if isinstance(row, dict) else None
        if not isinstance(answers, list) or len(answers) != len(ids):
            log("skipped a server response that doesn't match this test")
            continue
        sid = str(row.get("sid") or f"server-{i}")
        latest[sid] = {"name": str(row.get("name") or "")[:40], "via": "server",
                       "choices": {q: a for q, a in zip(ids, answers) if a in ("H", "A")}}
    for i, code in enumerate(codes):
        person = decode(code)
        if person["version"] != 3:
            log(f"skipped a v{person['version']} code: this key is for the v3 test")
            continue
        if person["test_id"] != key["test_id"]:
            log("skipped a code from another test")
            continue
        sid = person["sid"] or f"code-{i}"
        latest[sid] = {"name": person["name"], "via": "code",
                       "choices": {q: c for q, c in person["choices"].items() if q in ids}}
    return [p for p in latest.values() if p["choices"]]


def tally(choices, questions):
    """→ {source: [answers, «Человек» answers]} for one person or everyone."""
    out = {s: [0, 0] for s in SOURCES}
    for qid, choice in choices:
        out[questions[qid]["source"]][0] += 1
        out[questions[qid]["source"]][1] += choice == "H"
    return out


def summary_of(t):
    """Human-rates per source, the real-vs-SaySo comparison and accuracy (H on real, ИИ on SaySo/generic)."""
    (nr, hr), (ns, hs), (ng, hg) = t["real"], t["sayso"], t["generic"]
    correct, answers = hr + (ns - hs) + (ng - hg), nr + ns + ng
    return {"answers": answers,
            **{f"{s}_answers": t[s][0] for s in SOURCES},
            **{f"{s}_human": t[s][1] for s in SOURCES},
            **{f"{s}_human_rate": rate(t[s][1], t[s][0]) for s in SOURCES},
            "real_minus_sayso": round(hr / nr - hs / ns, 3) if nr and ns else None,
            "real_minus_sayso_ci95": difference_ci(hr, nr, hs, ns),
            "p_real_vs_sayso": round(fisher_p(hr, nr, hs, ns), 4),
            "p_real_vs_generic": round(fisher_p(hr, nr, hg, ng), 4) if ng else None,
            "correct": correct, "accuracy": rate(correct, answers),
            "p_accuracy_vs_half": round(binomial_p(correct, answers, 0.5)[0], 4)}


def score_v3(key, codes, responses, results_path=RESULTS, log=print):
    questions = {q["id"]: q for q in key["questions"]}
    people = people_v3(key, codes, responses, log)
    if not people:
        sys.exit("no answers for this test yet (server responses or SS3 codes)")
    sources = {s: sum(q["source"] == s for q in key["questions"]) for s in SOURCES}
    log(f"\nBlind test v3: {len(people)} people × {len(questions)} messages ({sources['real']} real, "
        f"{sources['sayso']} SaySo, {sources['generic']} generic AI); «Человек» or «ИИ» each\n")
    everyone = [(q, c) for p in people for q, c in p["choices"].items()]
    rows = []
    for i, person in enumerate(people, 1):
        row = summary_of(tally(person["choices"].items(), questions))
        rows.append(row)
        log(f"  {person['name'] or f'person {i}':<18} said «Человек» to real {row['real_human']}/{row['real_answers']}"
            f"  SaySo {row['sayso_human']}/{row['sayso_answers']}"
            + (f"  generic {row['generic_human']}/{row['generic_answers']}" if row["generic_answers"] else "")
            + f"   accuracy {row['correct']}/{row['answers']}   p(real≠SaySo) = {row['p_real_vs_sayso']:.3g}")
    total = summary_of(tally(everyone, questions))
    log(f"\n  «Человек» for real messages:  {total['real_human']}/{total['real_answers']} = "
        f"{total['real_human_rate']:.0%}")
    log(f"  «Человек» for SaySo messages: {total['sayso_human']}/{total['sayso_answers']} = "
        f"{total['sayso_human_rate']:.0%}")
    if total["generic_answers"]:
        log(f"  «Человек» for generic AI:     {total['generic_human']}/{total['generic_answers']} = "
            f"{total['generic_human_rate']:.0%}   p(real≠generic) = {total['p_real_vs_generic']:.3g}")
    ci = total["real_minus_sayso_ci95"]
    if ci:
        log(f"  difference real − SaySo: {total['real_minus_sayso']:+.0%} (95% CI {ci[0]:+.0%} … {ci[1]:+.0%}); "
            f"Fisher's exact p = {total['p_real_vs_sayso']:.3g} (high p and a narrow CI around 0 = can't tell apart)")
    log(f"  accuracy {total['correct']}/{total['answers']} = {total['accuracy']:.0%} "
        f"(50% = guessing; exact binomial p = {total['p_accuracy_vs_half']:.3g})")
    log("  (pooled p-values treat every answer as independent; per-person rows above are the stricter view)")

    per_question = defaultdict(lambda: [0, 0])
    for qid, choice in everyone:
        per_question[qid][0] += 1
        per_question[qid][1] += choice == "H"
    ordered = sorted(questions, key=lambda q: int(q[1:]) if q[1:].isdigit() else 0)
    item_rows = [{"id": qid, "source": questions[qid]["source"], "audience": questions[qid]["audience"],
                  "situation": questions[qid]["situation"], "chars": questions[qid].get("chars"),
                  "answers": per_question[qid][0], "human": per_question[qid][1],
                  "human_rate": rate(per_question[qid][1], per_question[qid][0])} for qid in ordered]
    by_item = {s: [r["human_rate"] for r in item_rows if r["source"] == s and r["answers"]] for s in SOURCES}
    convincing = sorted((r for r in item_rows if r["source"] == "sayso" and r["answers"]),
                        key=lambda r: -r["human_rate"])
    log("\n  SaySo messages most often taken for the user (local view, not saved):")
    for r in convincing[:5]:
        q = questions[r["id"]]
        log(f"    {r['id']:<4} «Человек» {r['human']}/{r['answers']} · {q['context']}\n         {' / '.join(q['parts'])}")

    results = {
        "version": VERSION, "test": hashlib.sha256(key["test_id"].encode()).hexdigest()[:8],
        "scored": datetime.date.today().isoformat(), "writer": key.get("writer", "unknown"),
        "people": len(people), "questions": len(questions), "items": sources,
        "via": {v: sum(p["via"] == v for p in people) for v in ("server", "code")},
        **total,
        "item_mean_human_rate": {s: round(sum(v) / len(v), 3) if v else None for s, v in by_item.items()},
        "sayso_items_judged_human_by_most": sum(r > 0.5 for r in by_item["sayso"]),
        "median_chars": key.get("lengths"),
        "per_person": sorted(rows, key=lambda r: (-(r["accuracy"] or 0), -r["answers"])),  # anonymous
        "per_question": item_rows,
        "note": "human_rate = share of answers «Человек»; pooled p-values treat answers as independent",
    }
    Path(results_path).parent.mkdir(parents=True, exist_ok=True)
    Path(results_path).write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"\nwrote {results_path} (aggregate numbers only)")
    return results


# ---- v2 (three replies, pick the real one): kept so codes already collected still score

def counts():
    return {"answers": 0, "real": 0, "sayso": 0, "generic": 0}


def shares(c):
    return {"answers": c["answers"], **{s: c[s] for s in SOURCES},
            **{f"{s}_rate": rate(c[s], c["answers"]) for s in SOURCES}}


def score_v2(key, codes, results_path=RESULTS, log=print):
    questions = {q["id"]: q for q in key["questions"]}
    people = []
    for code in codes:
        person = decode(code)
        if person["version"] == 3:
            log("skipped an SS3 code: this key is for the v2 test")
            continue
        if person["test_id"] != key["test_id"]:
            log(f"skipped a code from another test ({person['test_id']}, this one is {key['test_id']})")
            continue
        person["choices"] = {q: c for q, c in person["choices"].items() if q in questions}
        if person["choices"]:
            people.append(person)
    if not people:
        sys.exit("no valid codes for this test")

    log(f"\nBlind test {key['test_id']}: {len(people)} people × {len(questions)} questions "
        f"(1 real reply, 1 SaySo, 1 generic AI each; chance = 33%)\n")
    total = counts()
    per_question = defaultdict(counts)
    per_audience = defaultdict(counts)
    person_rows = []
    for i, person in enumerate(people, 1):
        mine = counts()
        for qid, choice in person["choices"].items():
            q = questions[qid]
            source = next(s for s in SOURCES if q[s] == choice)
            for c in (mine, total, per_question[qid], per_audience[q["audience"]]):
                c["answers"] += 1
                c[source] += 1
        person_rows.append(shares(mine))
        log(f"  {person['name'] or f'person {i}':<20} found me {mine['real']:>2}/{mine['answers']:<2} "
            f"{mine['real'] / mine['answers']:>5.0%}   picked SaySo {mine['sayso']:>2}   picked generic AI "
            f"{mine['generic']:>2}")

    n = total["answers"]
    p_two, p_better = binomial_p(total["real"], n, CHANCE)
    fooled = total["sayso"] + total["generic"]
    p_sayso_more = binomial_p(total["sayso"], fooled, 0.5)[1] if fooled else 1.0
    log(f"\n  overall: found the real reply {total['real']}/{n} = {total['real'] / n:.0%}   (chance 33%)")
    log(f"  binomial vs 1/3: p = {p_two:.3g} two-sided, p = {p_better:.3g} that people find me better than chance")
    log(f"  fooled by SaySo      {total['sayso']}/{n} = {total['sayso'] / n:.0%}")
    log(f"  fooled by generic AI {total['generic']}/{n} = {total['generic'] / n:.0%}")
    if fooled:
        log(f"  of the wrong picks, SaySo got {total['sayso'] / fooled:.0%} (50% = no better than generic AI); "
            f"p = {p_sayso_more:.3g} that SaySo fools people more often than generic AI")
    if len(per_audience) > 1:
        log("\n  by audience (found me · SaySo · generic):")
        for audience, c in sorted(per_audience.items()):
            log(f"    {audience:<15} {c['real'] / c['answers']:>4.0%} · {c['sayso'] / c['answers']:>4.0%} · "
                f"{c['generic'] / c['answers']:>4.0%}   ({c['answers']} answers)")

    ranked = sorted(per_question, key=lambda q: (-per_question[q]["sayso"] / per_question[q]["answers"],
                                                 int(q[1:]) if q[1:].isdigit() else 0))
    log("\n  SaySo picked as the real one most often:")
    for qid in ranked[:5]:
        c, q = per_question[qid], questions[qid]
        by = {s: " / ".join(q["options"][LETTERS.index(q[s])]) for s in SOURCES}
        log(f"    {qid:<4} SaySo {c['sayso']}/{c['answers']} · real {c['real']} · generic {c['generic']} · "
            f"{q['audience']} · {q['situation']}\n         context: {q['context']}\n"
            f"         SaySo:   {by['sayso']}\n         real:    {by['real']}\n         generic: {by['generic']}")

    results = {
        "version": 2, "test_id": key["test_id"], "scored": datetime.date.today().isoformat(),
        "writer": key.get("writer", "unknown"), "people": len(people), "questions": len(questions), "chance": 0.333,
        **shares(total),
        "p_real_two_sided": round(p_two, 4), "p_real_better_than_chance": round(p_better, 4),
        "sayso_share_of_wrong_picks": rate(total["sayso"], fooled),
        "p_sayso_fools_more_than_generic": round(p_sayso_more, 4),
        "questions_sayso_picked_most": sum(c["sayso"] > max(c["real"], c["generic"]) for c in per_question.values()),
        "per_person": sorted(person_rows, key=lambda r: (-(r["real_rate"] or 0), -r["answers"])),  # anonymous
        "per_audience": {a: shares(c) for a, c in sorted(per_audience.items())},
        "per_question": [{"id": qid, "audience": questions[qid]["audience"], "situation": questions[qid]["situation"],
                          **per_question[qid]}
                         for qid in sorted(per_question, key=lambda q: int(q[1:]) if q[1:].isdigit() else 0)],
        "top_sayso": ranked[:5],
    }
    Path(results_path).parent.mkdir(parents=True, exist_ok=True)
    Path(results_path).write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"\nwrote {results_path} (aggregate numbers only)")
    return results


# ---------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    b = commands.add_parser("build", help="make data/blind/<test_id>/ (the page, the public questions, the key)")
    b.add_argument("--n", type=int, default=20, help="questions (default 20: about half real, half SaySo)")
    b.add_argument("--generic", type=int, default=0, help="plain Muse Spark answers added as controls (default 0)")
    b.add_argument("--author", help="the name in «Это написал(а) <name> или ИИ?» (default: data/config.json)")
    b.add_argument("--pairs", default=str(PAIRS))
    b.add_argument("--seed", type=int)
    b.add_argument("--no-warmup", action="store_true", help="skip GET /warmup (the GPU is already warm or off)")
    b.add_argument("--single", action="store_true",
                   help="one message per item on both sides (a series of several next to one short reply is a tell)")
    b.add_argument("--include-train", action="store_true",
                   help="also draw from the training turns (when too few held-out ones pass the screen)")
    p = commands.add_parser("publish", help="upload the page to the sayso-data volume and print the link")
    p.add_argument("--test", help="the test id (default: the last build)")
    s = commands.add_parser("score", help="score the answers (server and/or codes)")
    s.add_argument("codes", nargs="*")
    s.add_argument("--codes-file", help="a text file with one code per line")
    s.add_argument("--server", action="store_true", help="pull the answers posted to the published page")
    s.add_argument("--skip", type=int, default=0, help="leave out the first N server responses (the author's own)")
    s.add_argument("--test", help="the v3 test id (default: the last build)")
    s.add_argument("--answers", help="a key file (default: data/blind/<test>/answers.json; for v2: "
                                     "data/blind/answers.json)")
    args = parser.parse_args(argv)

    if args.command == "build":
        keys = env()
        author = args.author if args.author is not None else author_default()
        url = keys["SAYSO_API_URL"].rstrip("/")
        build(args.n, args.pairs, OUT, Api(url, keys["SAYSO_API_TOKEN"]), Spark(keys["META_API_KEY"]), args.seed,
              not args.no_warmup, generic=args.generic, author=author,
              post_url=lambda test_id: f"{url}/blind/{test_id}/answers",
              splits=("test", "train") if args.include_train else ("test",),
              max_parts=1 if args.single else None)
    elif args.command == "publish":
        keys = env(("SAYSO_API_URL",))
        publish(args.test or latest_id(), Api(keys["SAYSO_API_URL"], None))
    else:
        codes = list(args.codes)
        if args.codes_file:
            codes += [line for line in Path(args.codes_file).read_text(encoding="utf-8").split() if line.strip()]
        if args.answers:
            answers = Path(args.answers)
        else:
            answers = OUT / (args.test or latest_id()) / "answers.json"
        responses = []
        if args.server:
            key = load_key(answers)
            if key["version"] != 3:
                parser.error("--server is for v3 tests")
            keys = env(("SAYSO_API_URL", "SAYSO_API_TOKEN"))
            try:
                responses = Api(keys["SAYSO_API_URL"], keys["SAYSO_API_TOKEN"]).responses(key["test_id"])
            except RuntimeError as error:
                sys.exit(str(error))
            print(f"{len(responses)} responses on the server")
            if args.skip:  # the author's own runs (trying the page) are not a friend's guesses
                responses = sorted(responses, key=lambda r: r.get("at") or 0)[args.skip:]
                print(f"  skipping the first {args.skip} (the author's own), scoring {len(responses)}")
        elif not codes:
            parser.error("give codes, or --server for the answers posted to the page")
        try:
            score(codes, answers, responses=responses)
        except ValueError as error:
            sys.exit(str(error))


if __name__ == "__main__":
    main()
