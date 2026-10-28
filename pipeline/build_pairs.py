"""Build training/test pairs from own turns + situation tags.

Each selected turn becomes one pair (target = the user's real turn):
  reply   — audience + situation + neutral summary of the other person's message → own reply
  rewrite — neutral version of the turn (Muse Spark Open on Baseten) → own turn
  compose — short instruction (Muse Spark Open) → own turn
Only the user's own turns are sent to Baseten; the reply input is the summary from
situations.py, never the other person's text.

Selection: no chat above `max_chat_share` of the pairs, rare situations sampled more
often, turns over 600 chars dropped, up to 12k train pairs. Time-based split is kept;
the test set takes up to 250 turns per chat instead of the share cap.

Usage:
  python3 pipeline/build_pairs.py --dry-run     # selection stats only, no API calls
  python3 pipeline/build_pairs.py               # synthesize inputs (resumable) and write pairs
Writes data/pairs/train.jsonl and data/pairs/test.jsonl (chat-format messages + meta).
"""

import argparse
import functools
import json
import random
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from parse_telegram import ROOT, load_config
from situations import SSL_CONTEXT, load_env

DATA = ROOT / "data"
CACHE = DATA / "synth_cache.jsonl"
MAX_CHARS = 600
TRAIN_BUDGET = 12000
TEST_PER_CHAT = 250

SYSTEM = "You write chat messages exactly the way this user writes them."

# macOS's resolver fails under many parallel lookups ("nodename nor servname"); resolve each host once.
socket.getaddrinfo = functools.lru_cache(maxsize=32)(socket.getaddrinfo)

SYNTH_PROMPTS = {
    "rewrite": (
        "Rewrite the chat message in plain, neutral standard Russian: full sentences, normal capitalization "
        "and punctuation, no slang, no swearing, no emoji, no abbreviations; translate Kazakh or English words "
        "into Russian; merge several lines into one message. Keep the meaning and every fact. "
        "Output only the rewritten text."
    ),
    "compose": (
        "Write the short instruction someone would give an assistant to get exactly this chat message written. "
        "Russian, imperative, at most 12 words, starting with a verb like «напиши», «скажи», «спроси», «ответь», "
        "«предложи». Keep the facts (time, place, what), but do not copy the wording, slang or emoji. "
        "Output only the instruction."
    ),
}


def load_rows():
    turns = [json.loads(line) for line in (DATA / "turns.jsonl").open(encoding="utf-8")]
    labels = {}
    for line in (DATA / "situations.jsonl").open(encoding="utf-8"):
        label = json.loads(line)
        labels[label["turn_id"]] = label
    rows = []
    for turn in turns:
        label = labels.get(turn["turn_id"])
        if label and len(turn["text"]) <= MAX_CHARS:
            rows.append({**turn, **label})
    return rows


def chat_quotas(sizes, budget, max_share):
    """Largest per-chat counts with no chat above max_share of the total (water-filling)."""
    quotas = dict(sizes)
    for _ in range(50):
        total = sum(quotas.values())
        cap = int(max_share * total)
        capped = {chat: min(size, cap) for chat, size in sizes.items()}
        if capped == quotas:
            break
        quotas = capped
    total = sum(quotas.values())
    if total > budget:
        quotas = {chat: int(q * budget / total) for chat, q in quotas.items()}
    return quotas


def select(rows, rng, budget=None, max_share=None, per_chat=None):
    """Pick turns per chat quota; rare situations get a higher chance (inverse sqrt frequency).

    Train uses budget + max_share; test uses a flat per_chat limit so every audience is evaluated.
    """
    by_chat = defaultdict(list)
    for row in rows:
        by_chat[row["chat"]].append(row)
    sizes = {chat: len(items) for chat, items in by_chat.items()}
    if per_chat:
        quotas = {chat: min(size, per_chat) for chat, size in sizes.items()}
    else:
        quotas = chat_quotas(sizes, budget, max_share)
    freq = Counter(row["situation"] for row in rows)
    picked = []
    for chat, items in by_chat.items():
        # Efraimidis–Spirakis: key = u^(1/w) with w = 1/sqrt(freq); take the largest keys.
        keyed = sorted(items, key=lambda r: rng.random() ** (freq[r["situation"]] ** 0.5), reverse=True)
        picked += keyed[:quotas[chat]]
    return picked


def assign_task(row, rng):
    meaningful = re.search(r"\w", row["text"]) is not None
    if row["source"] == "incoming":
        if not meaningful:
            return "reply"  # emoji-only or "?" answers are still style
        return rng.choices(["reply", "rewrite", "compose"], [0.5, 0.3, 0.2])[0]
    if not meaningful:
        return None
    return rng.choices(["rewrite", "compose"], [0.6, 0.4])[0]


def call_spark(env, task, text, retries=7):
    body = json.dumps({
        "model": env["BASETEN_MODEL"],
        "messages": [{"role": "system", "content": SYNTH_PROMPTS[task]}, {"role": "user", "content": text}],
        "max_tokens": 4096,
    }).encode()
    request = urllib.request.Request(
        env["BASETEN_BASE_URL"].rstrip("/") + "/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Api-Key {env['BASETEN_API_KEY']}"},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=180, context=SSL_CONTEXT) as response:
                content = (json.load(response)["choices"][0]["message"]["content"] or "").strip()
            content = content.strip("«»\"' \n")
            if content:
                return content
        except urllib.error.HTTPError as error:
            if attempt == retries - 1:
                print(f"  {task}: {error}", file=sys.stderr)
            if error.code == 429:  # rate limited: wait as told, else back off longer
                time.sleep(float(error.headers.get("Retry-After") or 5 * 2 ** attempt) + random.random())
                continue
        except Exception as error:
            if attempt == retries - 1:
                print(f"  {task}: {error}", file=sys.stderr)
        time.sleep(2 ** attempt + random.random())
    return None


def synthesize(jobs, workers):
    """jobs: list of (turn_id, task, text). Returns {(turn_id, task): input}; cached on disk."""
    cache = {}
    if CACHE.exists():
        for line in CACHE.open(encoding="utf-8"):
            item = json.loads(line)
            cache[(item["turn_id"], item["task"])] = item["input"]
    todo = [job for job in jobs if (job[0], job[1]) not in cache]
    print(f"synthesis: {len(jobs) - len(todo)} cached, {len(todo)} to go")
    if not todo:
        return cache
    env = load_env()
    started = time.time()
    with CACHE.open("a", encoding="utf-8") as out, ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(call_spark, env, task, text): (turn_id, task) for turn_id, task, text in todo}
        for i, future in enumerate(as_completed(futures), 1):
            turn_id, task = futures[future]
            result = future.result()
            if result:
                cache[(turn_id, task)] = result
                out.write(json.dumps({"turn_id": turn_id, "task": task, "input": result}, ensure_ascii=False) + "\n")
            if i % 250 == 0:
                out.flush()
                print(f"  {i}/{len(todo)}  {i / (time.time() - started):.1f}/s")
    return cache


def user_prompt(row, task, synth_input):
    header = f"audience: {row['audience']} · situation: {row['situation']}\ntask: {task}"
    if task == "reply":
        return f"{header}\nincoming: {row['summary']}"
    if task == "rewrite":
        return f"{header}\ndraft: {synth_input}"
    return f"{header}\ninstruction: {synth_input}"


def build(rows, cache):
    pairs = []
    for row in rows:
        task = row["task"]
        synth_input = cache.get((row["turn_id"], task))
        if task != "reply" and not synth_input:
            continue
        pairs.append({
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_prompt(row, task, synth_input)},
                {"role": "assistant", "content": row["text"]},
            ],
            "meta": {k: row[k] for k in ("turn_id", "audience", "situation", "split")} | {"task": task},
        })
    return pairs


def print_stats(name, pairs, rows_by_id):
    print(f"\n{name}: {len(pairs)} pairs")
    chats = Counter(rows_by_id[p["meta"]["turn_id"]]["chat"] for p in pairs)
    print("  chat share: " + ", ".join(f"{c / len(pairs):.0%}" for c in sorted(chats.values(), reverse=True)))
    for field in ("task", "audience", "situation"):
        counts = Counter(p["meta"][field] for p in pairs)
        print(f"  {field}: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DATA / "config.json"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    config, _ = load_config(args.config)
    max_share = config.get("max_chat_share", 0.35)
    rng = random.Random(0)
    rows = load_rows()
    rows_by_id = {row["turn_id"]: row for row in rows}

    splits = {
        "train": select([r for r in rows if r["split"] == "train"], rng, budget=TRAIN_BUDGET, max_share=max_share),
        "test": select([r for r in rows if r["split"] == "test"], rng, per_chat=TEST_PER_CHAT),
    }
    for split, picked in splits.items():
        for row in picked:
            row["task"] = assign_task(row, rng)
        splits[split] = [row for row in picked if row["task"]]

    if args.dry_run:
        for split, picked in splits.items():
            print_stats(f"{split} (selection)", build(picked, {(r["turn_id"], r["task"]): "-" for r in picked}), rows_by_id)
        return

    jobs = [(r["turn_id"], r["task"], r["text"]) for picked in splits.values() for r in picked if r["task"] != "reply"]
    cache = synthesize(jobs, args.workers)

    out_dir = DATA / "pairs"
    out_dir.mkdir(exist_ok=True)
    for split, picked in splits.items():
        pairs = build(picked, cache)
        with (out_dir / f"{split}.jsonl").open("w", encoding="utf-8") as f:
            for pair in pairs:
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")
        print_stats(split, pairs, rows_by_id)


if __name__ == "__main__":
    main()
