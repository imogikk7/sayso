"""Tag every turn with a situation and a neutral summary, using our own base Glimmer.

The other person's messages are read from the exports in memory (via
parse_telegram.load_turns), sent only to our own vLLM endpoint on Modal, and
never written anywhere. Output: data/situations.jsonl with
{turn_id, situation, summary, source} — resumable, already-tagged turns are skipped.

Usage:
  python3 pipeline/situations.py --limit 200      # pilot on a random sample
  python3 pipeline/situations.py                  # everything
  python3 pipeline/situations.py --check          # distribution + 50 random rows (local only)
  python3 pipeline/situations.py --detail         # 25-30 word summaries for reply turns in data/pairs
Needs SAYSO_GLIMMER_URL and SAYSO_API_TOKEN in .env.
"""

import argparse
import json
import random
import re
import ssl
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from parse_telegram import ROOT, load_config, load_turns

OUT = ROOT / "data" / "situations.jsonl"

try:  # python.org builds on macOS ship without root certificates
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = None

SITUATIONS = {
    "request": "asks for something or asks a question",
    "invitation": "invites, suggests plans or a meeting",
    "good_news": "shares good news or excitement",
    "sadness": "is sad, tired, complains about life",
    "conflict": "is upset with the other person, argues, complains about them",
    "joke": "jokes, teases, sends a meme or something funny",
    "thanks": "thanks or praises",
    "apology": "apologizes",
    "logistics": "coordinates where/when, on the way, timing, practical details",
    "refusal": "declines or says no",
    "affection": "is tender, flirts, compliments, misses the other person",
    "sharing": "tells what they are doing or what happened, everyday updates and opinions",
    "reaction": "only laughs, reacts with emoji, or sends media without text",
    "greeting": "says hello, good morning or good night",
    "other": "none of the above",
}

TRANSLIT = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
     "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"],
))

SYSTEM = f"""Reasoning strength: low
You label short chat exchanges for a writing-style dataset.
Return JSON only: {{"situation": "<label>", "summary": "<text>"}}.

If the other person's messages are given, BOTH fields describe the OTHER PERSON's messages, not the user's reply.
Never start such a summary with "user". Only if the user starts the topic, both fields describe the user's message.
Use "other" only when nothing else fits.

situation — one of:
{chr(10).join(f"- {k}: {v}" for k, v in SITUATIONS.items())}

summary — at most 12 English words, neutral, third person, starting with a verb for the other person
("asks to move the meeting to tomorrow") or with "user" when the user starts ("user suggests going out tonight").
No names, no quotes, no numbers, addresses or other personal details. Messages may be in Russian, Kazakh or English.

Examples:
Other: "ты опять не пришел, я ждала час" / User: "прости, я забыл" → {{"situation": "conflict", "summary": "complains the user didn't show up again"}}
Other: "завтра кино идем?" / User: "го" → {{"situation": "invitation", "summary": "asks if they are going to the cinema tomorrow"}}
Other: "ахаха" / User: "ну а че" → {{"situation": "reaction", "summary": "laughs"}}
Other: "соскучилась по тебе" / User: "я тоже" → {{"situation": "affection", "summary": "says she misses the user"}}
User starts: "ты где" → {{"situation": "logistics", "summary": "user asks where the other person is"}}"""


def load_env():
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def prompt_for(row):
    if row["context"]:
        incoming = "\n".join(f"- {m}" for m in row["context"])
        return f"Other person's messages (latest last):\n{incoming}\n\nUser's reply:\n{row['text']}"
    return f"No earlier message; the user starts.\n\nUser's message:\n{row['text']}"


def valid_tag(label):
    return label.get("situation") in SITUATIONS and label.get("summary")


def call_glimmer(url, token, row, retries=3, system=SYSTEM, user=None, valid=valid_tag):
    body = json.dumps({
        "model": "muse-glimmer",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user or prompt_for(row)}],
        "temperature": 0.6,
        "top_p": 0.95,
        "max_tokens": 1024,
    }).encode()
    request = urllib.request.Request(
        url.rstrip("/") + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=300, context=SSL_CONTEXT) as response:
                content = json.load(response)["choices"][0]["message"]["content"] or ""
            match = re.search(r"\{.*\}", content, re.S)
            label = json.loads(match.group(0)) if match else {}
            if valid(label):
                return label
        except Exception as error:  # network hiccup or cold start
            if attempt == retries - 1:
                print(f"  {row['turn_id']}: {error}", file=sys.stderr)
        time.sleep(2 ** attempt)
    return None


def name_forms(names):
    """Names as written plus Latin transliterations (Илья → ilya), since summaries are English."""
    forms = set()
    for name in names:
        latin = "".join(TRANSLIT.get(ch, ch) for ch in name.lower())
        forms |= {name, latin, latin.replace("ya", "ia"), latin.replace("y", "i")}
    return {f for f in forms if len(f) >= 3}


def scrub(summary, names, max_words=12, keep_short_numbers=False):
    """Safety net: drop contact names and digits (or only long digit runs), cap the length."""
    for name in name_forms(names):
        summary = re.sub(rf"\b{re.escape(name)}\w*", "", summary, flags=re.I)
    summary = re.sub(r"\d{5,}" if keep_short_numbers else r"\d", "", summary)
    summary = re.sub(r"\s+([,.:;!?])", r"\1", summary)  # "at :" left by removed numbers
    return " ".join(summary.split()[:max_words]).strip(" .,:\"'")


DETAIL_SYSTEM = """Reasoning strength: low
You describe what the other person wrote in a chat, so that someone could reply without seeing the messages.
Return JSON only: {"summary": "<text>"}.

summary — 20 to 30 English words, third person, neutral. Say what they tell, ask or feel, the facts needed to
answer (what, when, where, how many), and their tone (joking, upset, tender, in a hurry). Focus on the latest
messages. Don't guess how anyone will reply.
No names (say "a friend", "her mom", "the teacher"), no quotes, no phone numbers, addresses or other personal
details. Short numbers like times and prices are fine. Messages may be in Russian, Kazakh or English.

Example: messages "ты где?? / мы уже у кинотеатра / начало в 7" →
{"summary": "Asks impatiently where the user is, says the group is already waiting at the cinema and the film starts at 7."}"""

OUT_DETAIL = ROOT / "data" / "summaries_detailed.jsonl"


def detail(rows, config, workers):
    """Detailed summaries (other person's messages only, no user reply) for reply-task turns in data/pairs."""
    reply_ids = set()
    for split in ("train", "test"):
        for line in (ROOT / "data" / "pairs" / f"{split}.jsonl").open(encoding="utf-8"):
            meta = json.loads(line)["meta"]
            if meta["task"] == "reply":
                reply_ids.add(meta["turn_id"])
    env = load_env()
    url, token = env["SAYSO_GLIMMER_URL"], env["SAYSO_API_TOKEN"]
    names = {word for chat in config["chats"] for word in chat.split()} | {config["self_name"]}
    done = {json.loads(line)["turn_id"] for line in OUT_DETAIL.open(encoding="utf-8")} if OUT_DETAIL.exists() else set()
    todo = [r for r in rows if r["turn_id"] in reply_ids and r["context"] and r["turn_id"] not in done]
    print(f"{len(done)} already summarized, {len(todo)} to go")
    failed = 0
    started = time.time()
    with OUT_DETAIL.open("a", encoding="utf-8") as out, ThreadPoolExecutor(workers) as pool:
        futures = {
            pool.submit(call_glimmer, url, token, row, system=DETAIL_SYSTEM,
                        user="Other person's messages (latest last):\n" + "\n".join(f"- {m}" for m in row["context"]),
                        valid=lambda label: bool(label.get("summary"))): row
            for row in todo
        }
        for i, future in enumerate(as_completed(futures), 1):
            row, label = futures[future], future.result()
            if label is None:
                failed += 1
                continue
            summary = scrub(label["summary"], names, max_words=35, keep_short_numbers=True)
            out.write(json.dumps({"turn_id": row["turn_id"], "summary": summary}, ensure_ascii=False) + "\n")
            if i % 200 == 0:
                out.flush()
                print(f"  {i}/{len(todo)}  {i / (time.time() - started):.1f}/s")
    print(f"done, {failed} failed (re-run to retry them)")


def tag(rows, config, workers):
    env = load_env()
    url, token = env["SAYSO_GLIMMER_URL"], env["SAYSO_API_TOKEN"]
    names = {word for chat in config["chats"] for word in chat.split()} | {config["self_name"]}
    done = {json.loads(line)["turn_id"] for line in OUT.open(encoding="utf-8")} if OUT.exists() else set()
    todo = [r for r in rows if r["turn_id"] not in done]
    print(f"{len(done)} already tagged, {len(todo)} to go")
    failed = 0
    started = time.time()
    with OUT.open("a", encoding="utf-8") as out, ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(call_glimmer, url, token, row): row for row in todo}
        for i, future in enumerate(as_completed(futures), 1):
            row, label = futures[future], future.result()
            if label is None:
                failed += 1
                continue
            out.write(json.dumps({
                "turn_id": row["turn_id"],
                "situation": label["situation"],
                "summary": scrub(label["summary"], names),
                "source": "incoming" if row["context"] else "own",
            }, ensure_ascii=False) + "\n")
            if i % 200 == 0:
                out.flush()
                print(f"  {i}/{len(todo)}  {i / (time.time() - started):.1f}/s")
    print(f"done, {failed} failed (re-run to retry them)")


def check(rows):
    """Local-only report: tag distribution per audience and 50 random rows to eyeball."""
    by_id = {r["turn_id"]: r for r in rows}
    labels = [json.loads(line) for line in OUT.open(encoding="utf-8")]
    per_audience = defaultdict(Counter)
    for label in labels:
        per_audience[by_id[label["turn_id"]]["audience"]][label["situation"]] += 1
    print(f"{'situation':<12}" + "".join(f"{a:>16}" for a in per_audience))
    for situation in SITUATIONS:
        print(f"{situation:<12}" + "".join(
            f"{c[situation] / sum(c.values()):>15.0%} " for c in per_audience.values()))
    print()
    for label in random.Random(0).sample(labels, min(50, len(labels))):
        own = by_id[label["turn_id"]]["text"].replace("\n", " / ")[:80]
        print(f"[{label['situation']}] {label['summary']}\n    → {own}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "data" / "config.json"))
    parser.add_argument("--limit", type=int, help="tag only a random sample of this size")
    parser.add_argument("--workers", type=int, default=48)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--detail", action="store_true", help="25-30 word summaries for reply turns in data/pairs")
    args = parser.parse_args()

    config, audiences = load_config(args.config)
    rows, _ = load_turns(config, audiences, with_context=True)
    if args.check:
        check(rows)
        return
    if args.detail:
        detail(rows, config, args.workers)
        return
    if args.limit:
        rows = random.Random(0).sample(rows, args.limit)
    tag(rows, config, args.workers)


if __name__ == "__main__":
    main()
