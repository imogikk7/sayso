"""Blind test: can friends tell the user's real message from SaySo's version of the same draft?

Runs on the user's Mac: the pairs and the key are private (data/ is gitignored), the API is the deployed one.

  python3 eval/blind_test.py build --n 15            # → data/blind/test.html (send it) + data/blind/answers.json (key)
  python3 eval/blind_test.py score <code> [<code> …] # codes friends sent back → accuracy, p-value, what fooled them
                                                     #   (or --codes-file codes.txt, one code per line)

build — takes rewrite pairs from data/pairs_v4/test.jsonl (held-out, own messages only: the draft is a neutral
        version of the user's message, the answer is the message itself), balanced across audiences, and asks
        POST {SAYSO_API_URL}/rewrite for SaySo's version of the same draft. Each question shows both, in random
        order, as one line (lines joined with " / " on both sides so line breaks give nothing away).
        The page holds no key: only the two texts, audience and situation. Other people's messages never appear.
score — decodes the codes, prints accuracy per person and overall (50% = indistinguishable), an exact binomial
        p-value against 50%, and the questions that fooled people most. Writes aggregate numbers only (no message
        text, no names) to eval/results/blind_test.json.
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
CODE_PREFIX = "SS1-"
JOIN = " / "
MIN_CHARS, MAX_CHARS = 12, 280
PLACEHOLDER = re.compile(r"\[(?:sticker|photo|video|voice|file|media|link|url|phone|email|card)[^\]]*\]", re.I)

AUDIENCES_RU = {"partner": "партнёру", "friends": "другу / подруге", "family": "семье",
                "elder_informal": "старшему, но на «ты»", "formal": "официально"}
SITUATIONS_RU = {"request": "просьба или вопрос", "invitation": "приглашение, планы", "good_news": "хорошие новости",
                 "sadness": "грусть, усталость", "conflict": "ссора, претензия", "joke": "шутка, мем",
                 "thanks": "благодарность", "apology": "извинение", "logistics": "где / когда",
                 "refusal": "отказ", "affection": "нежность", "sharing": "рассказывает, как дела",
                 "reaction": "реакция", "greeting": "приветствие", "other": "другое"}


# ---------------------------------------------------------------- config and API

def env():
    """SAYSO_API_URL and SAYSO_API_TOKEN from the environment, else from .env (never printed, never written)."""
    values = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.strip().split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
    values.update({k: os.environ[k] for k in ("SAYSO_API_URL", "SAYSO_API_TOKEN") if k in os.environ})
    missing = [k for k in ("SAYSO_API_URL", "SAYSO_API_TOKEN") if not values.get(k)]
    if missing:
        sys.exit(f"missing {', '.join(missing)} in .env")
    return values["SAYSO_API_URL"].rstrip("/"), values["SAYSO_API_TOKEN"]


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
    def __init__(self, url, token, request=http, sleep=time.sleep, attempts=6, wait=20):
        self.url, self.token, self.request, self.sleep = url, token, request, sleep
        self.attempts, self.wait = attempts, wait

    def warmup(self):
        """→ "ready", "off" (the server runs with the GPU off: Muse Spark Open writes, which is the product as
        deployed) or "cold"."""
        status, out = self.request("GET", self.url + "/warmup", self.token, timeout=900)
        if status == 200 and isinstance(out, dict) and out.get("gpu") == "off":
            return "off"
        return "ready" if status == 200 and (not isinstance(out, dict) or out.get("ready", True)) else "cold"

    def rewrite(self, draft, audience, situation, allow_unstyled=False):
        """SaySo's version of the draft, from the user's LoRA. While the GPU is cold the API answers with Muse Spark
        (styled = false): wait and retry, so the test measures the personal model, not the fallback."""
        body = {"text": draft, "audience": audience, "situation": situation, "format": "message"}
        last = None
        for attempt in range(self.attempts):
            status, out = self.request("POST", self.url + "/rewrite", self.token, body)
            if status == 401:
                sys.exit("401 from /rewrite: check SAYSO_API_TOKEN in .env")
            if status == 200 and out and (out.get("text") or "").strip():
                last = out
                if out.get("styled", True) or allow_unstyled:
                    return out
            if attempt < self.attempts - 1:
                self.sleep(self.wait)
        if last is not None:
            raise RuntimeError("the API kept answering with the Muse Spark fallback (GPU cold?); "
                               "run with --allow-unstyled to accept it")
        raise RuntimeError(f"/rewrite failed (last status {status})")


# ---------------------------------------------------------------- build

def one_line(text):
    return JOIN.join(line.strip() for line in text.splitlines() if line.strip())


def draft_of(user_content):
    match = re.search(r"^draft:[ \t]*(.*)\Z", user_content, re.M | re.S)
    return match.group(1).strip() if match else None


def load_pairs(path):
    """Rewrite pairs only: {draft, real, audience, situation, turn_id}. Real = the user's own message."""
    pairs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        meta = row.get("meta") or {}
        if meta.get("task") != "rewrite" or meta.get("split", "test") != "test":
            continue
        roles = {m["role"]: m["content"] for m in row.get("messages", [])}
        draft, real = draft_of(roles.get("user", "")), (roles.get("assistant") or "").strip()
        if not draft or not real:
            continue
        pairs.append({"draft": draft, "real": real, "audience": meta.get("audience", "friends"),
                      "situation": meta.get("situation", "other"), "turn_id": meta.get("turn_id")})
    return pairs


def usable(pair):
    real = one_line(pair["real"])
    return (MIN_CHARS <= len(real) <= MAX_CHARS and not PLACEHOLDER.search(real) and "http" not in real
            and pair["situation"] != "reaction")


def balanced(pairs, rng):
    """Shuffled, then interleaved by audience so a short test still covers every audience."""
    groups = defaultdict(list)
    for pair in pairs:
        groups[pair["audience"]].append(pair)
    for group in groups.values():
        rng.shuffle(group)
    order = sorted(groups, key=lambda a: -len(groups[a]))
    out = []
    while any(groups.values()):
        for audience in order:
            if groups[audience]:
                out.append(groups[audience].pop())
    return out


def build(n=15, pairs_path=PAIRS, out_dir=OUT, api=None, seed=None, allow_unstyled=False, warmup=True,
          log=print):
    rng = random.Random(seed)
    candidates = balanced([p for p in load_pairs(pairs_path) if usable(p)], rng)
    if not candidates:
        sys.exit(f"no usable rewrite pairs in {pairs_path}")
    if len(candidates) < n:
        log(f"only {len(candidates)} usable rewrite pairs, the test will have fewer than {n} questions")
    if warmup:
        log("waking the GPU (/warmup, a cold start takes minutes)…")
        state = api.warmup()
        if state == "off":
            log("  the server runs with the GPU off: testing what it writes now (Muse Spark Open in the user's style)")
            allow_unstyled = True
        elif state != "ready":
            log("  /warmup didn't answer 200; trying anyway")
    questions, seen = [], set()
    for pair in candidates:
        if len(questions) == n:
            break
        real = one_line(pair["real"])
        if real.lower() in seen:
            continue
        try:
            out = api.rewrite(pair["draft"], pair["audience"], pair["situation"], allow_unstyled)
        except RuntimeError as error:
            sys.exit(str(error))
        fake = one_line(out["text"])
        if not fake or fake.lower() == real.lower():  # identical texts make a question with no answer
            log(f"  skipped a pair: SaySo's version is identical to the real one")
            continue
        seen.add(real.lower())
        real_side = rng.choice("AB")
        a, b = (real, fake) if real_side == "A" else (fake, real)
        questions.append({"id": f"q{len(questions) + 1}", "audience": pair["audience"], "situation": pair["situation"],
                          "a": a, "b": b, "real": real_side, "styled": bool(out.get("styled", True)),
                          "turn_id": pair["turn_id"]})
        log(f"  {len(questions)}/{n}")
    test_id = secrets.token_hex(4)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    key = {"test_id": test_id, "created": datetime.datetime.now().isoformat(timespec="seconds"),
           "source": str(Path(pairs_path).name), "questions": questions}
    (out_dir / "answers.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "test.html").write_text(render(test_id, questions), encoding="utf-8")
    log(f"wrote {out_dir / 'test.html'} ({len(questions)} questions, test {test_id}) and the key {out_dir / 'answers.json'}")
    return key


def render(test_id, questions):
    """The page gets only what a friend should see: no key, no drafts, no ids of turns."""
    page = {"test_id": test_id, "questions": [
        {"id": q["id"], "audience": AUDIENCES_RU.get(q["audience"], q["audience"]),
         "situation": SITUATIONS_RU.get(q["situation"], q["situation"]), "a": q["a"], "b": q["b"]}
        for q in questions]}
    data = json.dumps(page, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    return TEMPLATE.read_text(encoding="utf-8").replace("__BLIND_DATA__", data)


# ---------------------------------------------------------------- score

def decode(code):
    """A result code from the page → {test_id, name, choices: {question id: "A" | "B"}}."""
    text = re.sub(r"\s+", "", code)
    if text.upper().startswith(CODE_PREFIX):
        text = text[len(CODE_PREFIX):]
    try:
        raw = json.loads(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)).decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"not a blind-test code: {code[:24]}…") from error
    if not isinstance(raw, dict) or not isinstance(raw.get("c"), dict):
        raise ValueError(f"not a blind-test code: {code[:24]}…")
    choices = {str(k): v for k, v in raw["c"].items() if v in ("A", "B")}
    return {"test_id": raw.get("t"), "name": str(raw.get("n") or "").strip()[:40], "choices": choices}


def binomial_p(k, n):
    """Exact two-sided binomial test against p = 0.5 (and one-sided: better than chance)."""
    if n == 0:
        return 1.0, 1.0
    probs = [math.comb(n, i) / 2 ** n for i in range(n + 1)]
    two = sum(p for p in probs if p <= probs[k] * (1 + 1e-9))
    return min(1.0, two), sum(probs[k:])


def score(codes, answers_path=OUT / "answers.json", results_path=RESULTS, log=print):
    key = json.loads(Path(answers_path).read_text(encoding="utf-8"))
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

    log(f"\nBlind test {key['test_id']}: {len(people)} people × {len(questions)} questions\n")
    per_question = defaultdict(lambda: [0, 0])  # id → [fooled, answered]
    per_audience = defaultdict(lambda: [0, 0])  # audience → [correct, answered]
    total_right = total = 0
    person_rows = []
    for i, person in enumerate(people, 1):
        right = 0
        for qid, choice in person["choices"].items():
            q = questions[qid]
            correct = choice == q["real"]
            right += correct
            per_question[qid][0] += not correct
            per_question[qid][1] += 1
            per_audience[q["audience"]][0] += correct
            per_audience[q["audience"]][1] += 1
        answered = len(person["choices"])
        total_right += right
        total += answered
        person_rows.append({"answered": answered, "correct": right, "accuracy": round(right / answered, 3)})
        log(f"  {person['name'] or f'person {i}':<20} {right:>3}/{answered:<3} {right / answered:>5.0%}")

    accuracy = total_right / total
    p_two, p_better = binomial_p(total_right, total)
    log(f"\n  overall              {total_right:>3}/{total:<3} {accuracy:>5.0%}   (50% = can't tell SaySo from the user)")
    log(f"  binomial vs 50%: p = {p_two:.3g} two-sided, p = {p_better:.3g} that people do better than chance")
    log("  " + ("→ no evidence people can tell them apart" if p_better >= 0.05
                else "→ people can tell them apart better than chance"))
    if len(per_audience) > 1:
        log("\n  by audience: " + ", ".join(f"{a} {c / n:.0%} ({n})" for a, (c, n) in sorted(per_audience.items())))

    ranked = sorted(per_question, key=lambda q: (-per_question[q][0] / per_question[q][1], q))
    log("\n  fooled most (share who picked SaySo's version as the real one):")
    for qid in ranked[:5]:
        fooled, answered = per_question[qid]
        q = questions[qid]
        real, fake = (q["a"], q["b"]) if q["real"] == "A" else (q["b"], q["a"])
        log(f"    {qid:<4} {fooled}/{answered} fooled · {q['audience']} · {q['situation']}\n"
            f"         SaySo: {fake}\n         real:  {real}")

    results = {
        "test_id": key["test_id"], "scored": datetime.date.today().isoformat(),
        "people": len(people), "questions": len(questions), "answers": total, "correct": total_right,
        "accuracy": round(accuracy, 3), "p_two_sided": round(p_two, 4), "p_better_than_chance": round(p_better, 4),
        "fooled_rate": round(1 - accuracy, 3),
        "questions_fooled_majority": sum(f / n > 0.5 for f, n in per_question.values()),
        "per_person": sorted(person_rows, key=lambda r: -r["accuracy"]),  # anonymous: no names
        "per_audience": {a: {"answers": n, "accuracy": round(c / n, 3)} for a, (c, n) in sorted(per_audience.items())},
        "per_question": [{"id": qid, "audience": questions[qid]["audience"], "situation": questions[qid]["situation"],
                          "answers": n, "fooled": f} for qid, (f, n) in sorted(per_question.items(),
                                                                                key=lambda x: int(x[0][1:]))],
        "styled_share": round(sum(q.get("styled", True) for q in questions.values()) / len(questions), 3),
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
    b.add_argument("--no-warmup", action="store_true", help="skip GET /warmup (the GPU is already warm)")
    b.add_argument("--allow-unstyled", action="store_true", help="accept Muse Spark fallback answers")
    s = commands.add_parser("score", help="score the codes friends sent back")
    s.add_argument("codes", nargs="*")
    s.add_argument("--codes-file", help="a text file with one code per line")
    s.add_argument("--answers", default=str(OUT / "answers.json"))
    args = parser.parse_args(argv)

    if args.command == "build":
        url, token = env()
        build(args.n, args.pairs, OUT, Api(url, token), args.seed, args.allow_unstyled, not args.no_warmup)
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
