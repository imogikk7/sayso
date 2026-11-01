"""Blind test v2: a situation and three replies — the user's real one, SaySo's, a generic AI's. Can friends find the user?

Runs on the user's Mac: the pairs and the key are private (data/ is gitignored), the API is the deployed one.

  python3 eval/blind_test.py build --n 15            # → data/blind/test.html (send it) + data/blind/answers.json (key)
  python3 eval/blind_test.py score <code> [<code> …] # codes friends sent back → who found the user, who fooled them
                                                     #   (or --codes-file codes.txt, one code per line)

build — takes reply pairs from data/pairs_v4/test.jsonl (held-out; the incoming side is only a neutral English summary
        of the other person's latest messages, no names, never their words; the answer is the user's real reply),
        balanced across audiences. For each one, three replies written independently to the same situation:
          real    — what the user actually answered;
          SaySo   — POST {SAYSO_API_URL}/chat {mode: reply, text: "Что написал собеседник (пересказ): <summary>"};
          generic — Muse Spark 1.3 with a plain prompt (no style, no profile, no examples).
        Friends see who it is (Партнёр / Друг / Семья / Преподаватель или старший) and the summary translated to
        natural Russian by Muse Spark, then the three replies in random order. The page holds no key.
score — decodes the codes (SS2-…; v1 SS1- codes still decode), prints per person and overall the share who found the
        real reply (chance = 1/3, exact binomial p), the share fooled by SaySo vs by the generic AI (the key
        comparison), by audience, and the questions where SaySo was picked most. Writes aggregate numbers only (no
        message text, no names) to eval/results/blind_test.json.

Needs SAYSO_API_URL, SAYSO_API_TOKEN and META_API_KEY in .env (or the environment).
"""

import argparse
import base64
import binascii
import datetime
import json
import math
import os
import random
import re
import secrets
import ssl
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
VERSION = 2
CODE_PREFIX = "SS2-"
CODE_PREFIXES = ("SS1-", "SS2-")  # v1 codes (two options) still decode
LETTERS = "ABC"
SOURCES = ("real", "sayso", "generic")
CHANCE = 1 / 3
MIN_CHARS, MAX_CHARS = 8, 280
META_URL = "https://api.meta.ai/v1/chat/completions"
META_MODEL = "muse-spark-1.3"
PLACEHOLDER = re.compile(r"\[(?:sticker|photo|video|voice|file|media|link|url|phone|email|card)[^\]]*\]", re.I)
LAUGHTER = re.compile(r"(?:[аaхxhеeи]*[хxh][аaхxhеeи]*|лол|lol|ору|ржу|kek|кек)+")

WHO_RU = {"partner": "Партнёр", "friends": "Друг", "family": "Семья", "elder_informal": "Преподаватель или старший",
          "formal": "Коллега"}
WHO_EN = {"partner": "your partner", "friends": "a friend", "family": "a family member",
          "elder_informal": "an older person you know well (a teacher or an elder), informal but respectful",
          "formal": "a colleague"}
SAYSO_TEXT = "Что написал собеседник (пересказ): {summary}"
TRANSLATE_SYSTEM = ("You translate short neutral summaries of chat messages into natural, everyday Russian. Keep the "
                    "meaning, keep it neutral and short, no names, add nothing. Write it as a description of what the "
                    "other person wrote (e.g. «Спрашивает, в силе ли встреча завтра»). "
                    'Return JSON only: {"ru": "..."}')
GENERIC_SYSTEM = "You are a helpful assistant."
GENERIC_USER = ("Write a short casual chat reply in Russian to this situation: {summary}\n"
                "You are replying to {who}. Return only the reply text.")


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
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context()) as response:
            return response.status, json.loads(response.read() or b"null")
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


class Spark:
    """Muse Spark 1.3 on the Meta Model API: translates summaries and writes the generic AI's reply."""

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

    def translate(self, summary):
        """The neutral English summary → natural Russian, for the friends who take the test."""
        text = self.ask(TRANSLATE_SYSTEM, summary)
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
    """Lines of a reply = messages sent in a row; shown as stacked bubbles on all three sides alike."""
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def same(a, b):
    return " ".join(" ".join(a).casefold().split()) == " ".join(" ".join(b).casefold().split())


def incoming_of(user_content):
    match = re.search(r"^incoming:[ \t]*(.*)\Z", user_content, re.M | re.S)
    return " ".join(match.group(1).split()) if match else None


def load_pairs(path):
    """Reply pairs only: {summary, real, audience, situation, turn_id}. Real = the user's own reply."""
    pairs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        meta = row.get("meta") or {}
        if meta.get("task") != "reply" or meta.get("split", "test") != "test":
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
    return not letters or bool(LAUGHTER.fullmatch(letters))


def usable(pair):
    real = " ".join(parts_of(pair["real"]))
    return (MIN_CHARS <= len(real) <= MAX_CHARS and not trivial(real) and not PLACEHOLDER.search(real)
            and "http" not in real and pair["audience"] in WHO_RU)


def balanced(pairs, rng):
    """Shuffled, then interleaved by audience so a short test still covers every audience."""
    groups = defaultdict(list)
    for pair in pairs:
        groups[pair["audience"]].append(pair)
    for group in groups.values():
        rng.shuffle(group)
    order = sorted(groups, key=lambda a: (-len(groups[a]), a))
    out = []
    while any(groups.values()):
        for audience in order:
            if groups[audience]:
                out.append(groups[audience].pop())
    return out


def build(n=15, pairs_path=PAIRS, out_dir=OUT, api=None, spark=None, seed=None, warmup=True, log=print):
    rng = random.Random(seed)
    candidates = balanced([p for p in load_pairs(pairs_path) if usable(p)], rng)
    if not candidates:
        sys.exit(f"no usable reply pairs in {pairs_path}")
    if len(candidates) < n:
        log(f"only {len(candidates)} usable reply pairs, the test will have fewer than {n} questions")
    writer = "unknown"
    if warmup:
        log("waking the GPU (/warmup, a cold start takes minutes)…")
        writer = api.warmup()
        if writer == "off":
            log("  the server runs with the GPU off: testing what it writes now (Muse Spark Open in the user's style)")
        elif writer != "ready":
            log("  /warmup didn't answer 200; trying anyway")
    questions, seen = [], set()
    for pair in candidates:
        if len(questions) == n:
            break
        real = parts_of(pair["real"])
        if " ".join(real).casefold() in seen:
            continue
        try:
            sayso = parts_of(api.reply(pair["summary"], pair["audience"]))
            generic = parts_of(spark.generic(pair["summary"], pair["audience"]))
            context = spark.translate(pair["summary"])
        except RuntimeError as error:
            sys.exit(str(error))
        texts = {"real": real, "sayso": sayso, "generic": generic}
        if not sayso or not generic or same(real, sayso) or same(real, generic) or same(sayso, generic):
            log("  skipped a pair: two of the replies are identical or empty")  # a question with no answer
            continue
        seen.add(" ".join(real).casefold())
        order = list(SOURCES)
        rng.shuffle(order)
        letters = {source: LETTERS[i] for i, source in enumerate(order)}
        questions.append({"id": f"q{len(questions) + 1}", "audience": pair["audience"],
                          "situation": pair["situation"], "context": context,
                          "options": [texts[source] for source in order], **letters, "turn_id": pair["turn_id"]})
        log(f"  {len(questions)}/{n}")
    if not questions:
        sys.exit("no questions: every pair was skipped")
    test_id = secrets.token_hex(4)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    key = {"version": VERSION, "test_id": test_id, "created": datetime.datetime.now().isoformat(timespec="seconds"),
           "source": Path(pairs_path).name, "writer": writer, "questions": questions}
    (out_dir / "answers.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "test.html").write_text(render(test_id, questions), encoding="utf-8")
    log(f"wrote {out_dir / 'test.html'} ({len(questions)} questions, test {test_id}) and the key {out_dir / 'answers.json'}")
    return key


def render(test_id, questions):
    """The page gets only what a friend should see: who it is, the Russian context and three replies. No key, no
    English summary, no situation tags, no turn ids."""
    page = {"test_id": test_id, "questions": [
        {"id": q["id"], "who": WHO_RU.get(q["audience"], q["audience"]), "context": q["context"],
         "options": q["options"]} for q in questions]}
    data = json.dumps(page, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    return TEMPLATE.read_text(encoding="utf-8").replace("__BLIND_DATA__", data)


# ---------------------------------------------------------------- score

def decode(code):
    """A result code from the page → {version, test_id, name, choices: {question id: letter}}.
    SS2- codes pick among A/B/C; v1 SS1- codes among A/B."""
    text = re.sub(r"\s+", "", code)
    version = VERSION
    for prefix in CODE_PREFIXES:
        if text.upper().startswith(prefix):
            text, version = text[len(prefix):], int(prefix[2])
            break
    try:
        raw = json.loads(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)).decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"not a blind-test code: {code[:24]}…") from error
    if not isinstance(raw, dict) or not isinstance(raw.get("c"), dict):
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


def rate(k, n):
    return round(k / n, 3) if n else None


def counts():
    return {"answers": 0, "real": 0, "sayso": 0, "generic": 0}


def shares(c):
    return {"answers": c["answers"], **{s: c[s] for s in SOURCES},
            **{f"{s}_rate": rate(c[s], c["answers"]) for s in SOURCES}}


def score(codes, answers_path=OUT / "answers.json", results_path=RESULTS, log=print):
    key = json.loads(Path(answers_path).read_text(encoding="utf-8"))
    if key.get("version") != VERSION:
        sys.exit("this key is from the v1 test (two options per question); v2 scores only v2 keys")
    questions = {q["id"]: q for q in key["questions"]}
    people = []
    for code in codes:
        person = decode(code)
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
        "version": VERSION, "test_id": key["test_id"], "scored": datetime.date.today().isoformat(),
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
    b = commands.add_parser("build", help="make data/blind/test.html and the key")
    b.add_argument("--n", type=int, default=15)
    b.add_argument("--pairs", default=str(PAIRS))
    b.add_argument("--seed", type=int)
    b.add_argument("--no-warmup", action="store_true", help="skip GET /warmup (the GPU is already warm or off)")
    s = commands.add_parser("score", help="score the codes friends sent back")
    s.add_argument("codes", nargs="*")
    s.add_argument("--codes-file", help="a text file with one code per line")
    s.add_argument("--answers", default=str(OUT / "answers.json"))
    args = parser.parse_args(argv)

    if args.command == "build":
        keys = env()
        build(args.n, args.pairs, OUT, Api(keys["SAYSO_API_URL"], keys["SAYSO_API_TOKEN"]),
              Spark(keys["META_API_KEY"]), args.seed, not args.no_warmup)
    else:
        codes = list(args.codes)
        if args.codes_file:
            codes += [line for line in Path(args.codes_file).read_text(encoding="utf-8").split() if line.strip()]
        if not codes:
            parser.error("give at least one code")
        try:
            score(codes, args.answers)
        except ValueError as error:
            sys.exit(str(error))


if __name__ == "__main__":
    main()
