"""Tag every turn with a situation and a neutral summary, using our own base Glimmer.

The other person's messages are read from the exports in memory (via
parse_telegram.load_turns), sent only to our own vLLM endpoint on Modal, and
never written anywhere. Output: data/situations.jsonl with
{turn_id, situation, summary, source} — resumable, already-tagged turns are skipped.

Usage:
  python3 pipeline/situations.py --limit 200      # pilot on a random sample
  python3 pipeline/situations.py                  # everything
  python3 pipeline/situations.py --check          # distribution + 50 random rows (local only)
Needs SAYSO_GLIMMER_URL and SAYSO_API_TOKEN in .env.
"""

import argparse
import json
import random
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from parse_telegram import ROOT, load_config, load_turns

OUT = ROOT / "data" / "situations.jsonl"

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
    "other": "small talk or anything else",
}

SYSTEM = f"""Reasoning strength: low
You label short chat exchanges for a writing-style dataset.
Return JSON only: {{"situation": "<label>", "summary": "<text>"}}.

situation — what the user's message is responding to (or, if the user starts, what the user is doing). One of:
{chr(10).join(f"- {k}: {v}" for k, v in SITUATIONS.items())}

summary — at most 12 English words, neutral, third person. For a reply describe the other person's message
("asks to move the meeting to tomorrow"); if the user starts, describe the user's message ("user suggests going out tonight").
No names, no quotes, no numbers, addresses or other personal details. Messages may be in Russian, Kazakh or English."""


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


def call_glimmer(url, token, row, retries=3):
    body = json.dumps({
        "model": "muse-glimmer",
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt_for(row)}],
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
            with urllib.request.urlopen(request, timeout=300) as response:
                content = json.load(response)["choices"][0]["message"]["content"] or ""
            match = re.search(r"\{.*\}", content, re.S)
            label = json.loads(match.group(0)) if match else {}
            if label.get("situation") in SITUATIONS and label.get("summary"):
                return label
        except Exception as error:  # network hiccup or cold start
            if attempt == retries - 1:
                print(f"  {row['turn_id']}: {error}", file=sys.stderr)
        time.sleep(2 ** attempt)
    return None


def scrub(summary, names):
    """Safety net: drop contact names and digits, cap at 12 words."""
    for name in names:
        summary = re.sub(rf"\b{re.escape(name)}\b", "", summary, flags=re.I)
    summary = re.sub(r"\d", "", summary)
    return " ".join(summary.split()[:12]).strip(" .,\"'")


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
    args = parser.parse_args()

    config, audiences = load_config(args.config)
    rows, _ = load_turns(config, audiences, with_context=True)
    if args.check:
        check(rows)
        return
    if args.limit:
        rows = random.Random(0).sample(rows, args.limit)
    tag(rows, config, args.workers)


if __name__ == "__main__":
    main()
