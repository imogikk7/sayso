"""Build a new style from what the user uploaded: chat exports, screenshots, frames of a screen recording.

Stages (written to the style's meta.json; the app polls them):
  parsing   exports → messages (pipeline/sources: Telegram, WhatsApp, Instagram); images → Muse Spark reads the
            bubbles (right side = the user), overlapping lines of neighbouring frames are dropped
  needs_me  the app asks which participant is the user and confirms each chat's audience (Spark guesses it)
  reading   Muse Spark tags the user's turns: situation, a neutral summary, act · tone · gist, plus a neutral
            draft and an instruction for the rewrite / compose pairs
  profile   pipeline/style_profile.describe per audience (× situation)
  training  the style's own LoRA on Muse Glimmer (training/modal_train.py), only when SAYSO_TRAIN=on
  checking  held-out replies written in the new style vs the user's real ones: how much it sounds like them
            (vs a no-style baseline) and whether the answers make sense (Spark as judge)
  ready     (or failed, with a reason)

Other people's messages exist only in this process's memory: they are read, sent to Muse Spark, and dropped.
What is written: the user's own turns with tags, the profile, pairs and scores.
"""

import asyncio
import io
import json
import random
import statistics
import sys
import tempfile
import time
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "pipeline"), str(ROOT / "eval"), str(ROOT / "serving")]

import styles  # noqa: E402
from metrics import features, total_variation  # noqa: E402
from situations import ACTS, SITUATIONS, TONES  # noqa: E402

AUDIENCES = ["partner", "friends", "family", "elder_informal"]
SYSTEM = "You write chat messages exactly the way this user writes them."
EXPORTS = {".zip", ".txt", ".json", ".html"}
IMAGES = {".png", ".jpg", ".jpeg", ".heic", ".webp"}
MAX_TURNS = 2000  # tagging budget per style
BATCH = 10
WORKERS = 12
CHECK_TURNS = 20
MIN_LORA_TURNS = 150
WAIT_FOR_ME = 30 * 60
GAP = timedelta(minutes=10)
CONTEXT_WINDOW = timedelta(minutes=30)

SCREEN_SYSTEM = """You read a screenshot of a chat for the user who took it. Return JSON only:
{"chat_name": "<the chat title at the top, or empty>", "messages": [{"side": "me" | "them", "text": "<text>"}]}
messages — every text bubble, top to bottom, exactly as written (keep slang, typos, emoji and line breaks).
"me" = the user's own bubbles (on the right, usually colored); "them" = the other side (on the left).
Skip times, dates, read marks, reactions, system lines and media without text."""

AUDIENCE_SYSTEM = """You see a few messages from one chat of a user. Who is the other person to the user?
Return JSON only: {"audience": "<one of: """ + ", ".join(AUDIENCES) + """>"}.
partner — girlfriend/boyfriend/spouse; friends — friends, classmates, peers; family — parents, siblings, relatives
of similar closeness; elder_informal — teachers, bosses, older people, anyone the user is polite with."""

TAG_SYSTEM = f"""You label a user's own chat messages for a writing-style dataset. For each item you get the user's
message (and, if they were replying, what the other person wrote before it). Return JSON only:
{{"items": [{{"i": <number>, "situation": "<label>", "summary": "<text>", "act": "<act>", "tone": "<tone>",
"gist": "<text>", "draft": "<text>", "instruction": "<text>"}}, ...]}}
situation — what the OTHER person's messages do (or the user's message, if the user started), one of:
{chr(10).join(f"- {k}: {v}" for k, v in SITUATIONS.items())}
summary — 20 to 30 English words, neutral, third person: what the other person tells, asks or feels, with the facts
needed to answer, and their tone; if the user started, describe the user's message starting with "user". No names.
act — what the user chose to do, one of: {", ".join(ACTS)}
tone — one of: {", ".join(TONES)}
gist — what the user means, 6 to 15 English words, neutral, no names.
draft — the user's message rewritten in plain neutral standard language of the message (full sentences, normal
capitalization and punctuation, no slang, swearing or emoji), same meaning and facts.
instruction — the short instruction someone would give an assistant to get this message written, in the message's
language, imperative, at most 12 words, keeping the facts but not the wording."""

JUDGE_SYSTEM = """You check suggested chat replies. For each item: the other person's messages and a reply.
Score 1–5 how much the reply makes sense as an answer: 5 = clear, coherent and fits, 3 = understandable but off,
1 = nonsense or unrelated. Return JSON only: {"scores": [{"i": <number>, "score": <1-5>}, ...]}."""

BASELINE_SYSTEM = """Write a short chat reply to the latest messages, in the language of the chat.
Return JSON only: {"text": "<the reply>"}."""


# ---- Muse Spark (sync, for the build process) ------------------------------------------------------

class Spark:
    def __init__(self, key, client=None):
        import httpx
        self.key = key
        self.client = client or httpx.Client(timeout=60)

    def __call__(self, system, user, key):
        import re
        for attempt in range(3):
            try:
                response = self.client.post(
                    "https://api.meta.ai/v1/chat/completions", headers={"Authorization": f"Bearer {self.key}"},
                    json={"model": "muse-spark-1.3", "reasoning_effort": "low", "max_tokens": 6000,
                          "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
                response.raise_for_status()
                text = response.json()["choices"][0]["message"].get("content") or ""
                match = re.search(r"\{.*\}", text, re.S)
                label = json.loads(match.group(0)) if match else {}
                if isinstance(label, dict) and key in label:
                    return label
            except Exception:
                pass
            time.sleep(2 * (attempt + 1))
        return {}


# ---- parsing ----------------------------------------------------------------------------------------

def norm(text):
    return " ".join(text.casefold().split())


def merge_frames(frames):
    """Frames of one scroll overlap: append each frame's messages after the longest overlap with what came before."""
    merged = []
    for frame in frames:
        frame = [m for m in frame if m.get("text", "").strip()]
        best = 0
        for k in range(min(len(merged), len(frame)), 0, -1):
            if [(m["side"], norm(m["text"])) for m in merged[-k:]] == [(m["side"], norm(m["text"])) for m in frame[:k]]:
                best = k
                break
        merged.extend(frame[best:])
    return merged


def read_images(images, spark):
    """[(name, bytes)] in upload order → {chat_name: [messages]} (the user is the sender "me")."""
    import base64

    def one(item):
        name, raw = item
        kind = "image/png" if name.lower().endswith(".png") else "image/jpeg"
        content = [{"type": "text", "text": "Read this chat screenshot."},
                   {"type": "image_url", "image_url": {"url": f"data:{kind};base64," + base64.b64encode(raw).decode()}}]
        label = spark(SCREEN_SYSTEM, content, "messages")
        messages = [m for m in label.get("messages") or [] if isinstance(m, dict) and m.get("side") in {"me", "them"}
                    and isinstance(m.get("text"), str)]
        return str(label.get("chat_name") or "").strip() or "Screenshots", messages

    with ThreadPoolExecutor(WORKERS) as pool:
        read = list(pool.map(one, images))
    frames = defaultdict(list)
    for chat, messages in read:
        frames[chat].append(messages)
    chats = {}
    start = datetime(2000, 1, 1)
    for chat, chat_frames in frames.items():
        merged = merge_frames(chat_frames)
        chats[chat] = [{"id": i, "ts": start + timedelta(minutes=i), "sender": "me" if m["side"] == "me" else "them",
                        "text": m["text"], "kind": "text"} for i, m in enumerate(merged)]
    return chats


def read_exports(exports):
    """[(name, bytes)] → {chat_name: [messages]}; parsed from a temporary folder that is deleted right after."""
    from sources import detect, read_any
    chats = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, raw in exports:
            path = Path(tmp) / Path(name).name
            path.write_bytes(raw)
            if path.suffix == ".html":  # a Telegram export page lives in a folder of its own
                folder = Path(tmp) / f"telegram-{len(chats)}"
                folder.mkdir()
                path = path.rename(folder / "messages.html")
                path = folder
            elif path.suffix == ".zip":
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    if any(n.endswith("messages.html") for n in archive.namelist()):
                        folder = Path(tmp) / f"telegram-{len(chats)}"
                        archive.extractall(folder)
                        path = next(p.parent for p in folder.rglob("messages.html"))
            try:
                detect(path)
            except ValueError:
                continue
            chats[Path(name).stem] = list(read_any(path))
    return chats


# ---- turns ------------------------------------------------------------------------------------------

def turns_of(chat, messages, me, audience):
    """The user's turns in one chat (pipeline/parse_telegram.build_turns), each with the other person's messages
    before it in `context` (memory only), and a time-based split: the last 15% are held out for the self-check."""
    from parse_telegram import build_turns
    turns = build_turns(messages, me, GAP, max_messages=12, max_chars=1000, context_window=CONTEXT_WINDOW)
    cut = int(len(turns) * 0.85)
    return [{"chat": chat, "audience": audience, "text": "\n".join(t["messages"]), "context": t["context"],
             "split": "test" if i >= cut and len(turns) >= 20 else "train", "start": t["start"].isoformat()}
            for i, t in enumerate(turns)]


def tag(turns, spark):
    """Adds situation, summary, act, tone, gist, draft, instruction to each turn (Spark, batches of 10)."""
    batches = [turns[i:i + BATCH] for i in range(0, len(turns), BATCH)]

    def one(batch):
        lines = []
        for i, t in enumerate(batch):
            other = " / ".join(t["context"])[:600]
            lines.append(f"{i}. " + (f"Other person: {other}\n   " if other else "(the user started)\n   ")
                         + f"User: {t['text'][:600]}")
        label = spark(TAG_SYSTEM, "\n".join(lines), "items")
        for item in label.get("items") or []:
            if isinstance(item, dict) and isinstance(item.get("i"), int) and 0 <= item["i"] < len(batch):
                t = batch[item["i"]]
                t["situation"] = item.get("situation") if item.get("situation") in SITUATIONS else "other"
                t["act"] = item.get("act") if item.get("act") in ACTS else "other"
                t["tone"] = item.get("tone") if item.get("tone") in TONES else "neutral"
                for field in ("summary", "gist", "draft", "instruction"):
                    t[field] = " ".join(str(item.get(field) or "").split())[:400]

    with ThreadPoolExecutor(WORKERS) as pool:
        list(pool.map(one, batches))
    return [t for t in turns if t.get("situation")]


def profile_of(turns):
    from style_profile import describe
    MIN = 10  # a new style has fewer turns than the main one; smaller cells still say something
    by_audience, by_cell = defaultdict(list), defaultdict(list)
    for t in turns:
        row = {**t, "own": not t["context"]}
        by_audience[t["audience"]].append(row)
        by_cell[(t["audience"], t["situation"])].append(row)
    profile = {}
    for audience, items in sorted(by_audience.items(), key=lambda kv: -len(kv[1])):
        profile[audience] = describe(items)
        profile[audience]["situations"] = {
            s: describe(cell) for (a, s), cell in sorted(by_cell.items(), key=lambda kv: -len(kv[1]))
            if a == audience and len(cell) >= MIN and s != "other"}
    return profile


def pairs_of(turns):
    """The same format as pairs_v4: reply pairs carry the thought in reasoning_content."""
    out = defaultdict(list)
    for t in turns:
        header = f"audience: {t['audience']} · situation: {t['situation']}"
        tasks = []
        if t["context"] and t.get("summary"):
            tasks.append(("reply", f"incoming: {t['summary']}"))
        if t.get("draft"):
            tasks.append(("rewrite", f"draft: {t['draft']}"))
        if t.get("instruction") and not t["context"]:
            tasks.append(("compose", f"instruction: {t['instruction']}"))
        for task, field in tasks:
            reply = {"role": "assistant", "content": t["text"]}
            if task == "reply":
                reply["reasoning_content"] = f"act: {t['act']} · tone: {t['tone']} · gist: {t['gist']}"
            out[t["split"]].append({
                "messages": [{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": f"{header}\ntask: {task}\n{field}"}, reply],
                "meta": {"audience": t["audience"], "situation": t["situation"], "task": task, "split": t["split"],
                         **({"act": t["act"], "tone": t["tone"]} if task == "reply" else {})}})
    return out


# ---- self-check ---------------------------------------------------------------------------------------

FORM = {  # the form of a message, as the user's friends would notice it
    "length": lambda t, f: min(len(t) // 20, 5),
    "lowercase start": lambda t, f: f["lower_start"] > 0.5,
    "ends with punctuation": lambda t, f: f["end_punct"] > 0.5,
    "laughter": lambda t, f: bool(f["laughter"]),
    "emoji": lambda t, f: f["emoji_per_line"] > 0,
    "swearing": lambda t, f: bool(f["swear"]),
    "question": lambda t, f: f["question"] > 0,
}


def similarity(generated, real):
    """1 − total variation between the two sets, per form feature, averaged (1 = indistinguishable by form).
    The user's real turns are joined into one message first, like the suggestions."""
    if not generated or not real:
        return 0.0
    real = [" ".join(line.strip() for line in t.splitlines() if line.strip()) for t in real]
    scores = []
    for value in FORM.values():
        a = [value(t, features(t)) for t in generated]
        b = [value(t, features(t)) for t in real]
        scores.append(1 - total_variation(a, b))
    return round(statistics.mean(scores), 2)


def self_check(style_id, held_out, spark, meta_key):
    """Writes the held-out replies with the production writer (Muse Spark + the new style), and a no-style baseline."""
    import httpx
    from writer import Context, Writer

    held_out = held_out[:CHECK_TURNS]
    if not held_out:
        return {"note": "too few messages to check"}

    async def run():
        async with httpx.AsyncClient(timeout=60) as client:
            writer = Writer(client, "http://unused", "", None, meta_key, gpu="off")
            ctx = Context(style_id)
            semaphore = asyncio.Semaphore(6)

            async def one(t):
                async with semaphore:
                    try:
                        context, options = await writer.read(ctx, messages="\n".join(t["context"]),
                                                             audience=t["audience"])
                        return options[0]["draft"] if options else ""
                    except Exception:
                        return ""
            return await asyncio.gather(*(one(t) for t in held_out))

    styled = asyncio.run(run())

    def baseline(t):
        return spark(BASELINE_SYSTEM, "Messages (latest last):\n" + "\n".join(t["context"]), "text").get("text") or ""

    with ThreadPoolExecutor(WORKERS) as pool:
        generic = list(pool.map(baseline, held_out))
    items = [(t, s) for t, s in zip(held_out, styled) if s]
    judged = spark(JUDGE_SYSTEM, "\n".join(f"{i}. Other person: {' / '.join(t['context'])[:500]}\n   Reply: {s}"
                                           for i, (t, s) in enumerate(items)), "scores")
    scores = [s["score"] for s in judged.get("scores") or [] if isinstance(s, dict) and isinstance(s.get("score"), (int, float))]
    real = [t["text"] for t in held_out]
    return {
        "sounds_like_you": similarity([s for s in styled if s], real),
        "generic": similarity([g for g in generic if g], real),
        "makes_sense": round(statistics.mean(scores), 1) if scores else None,
        "checked": len(items),
        "samples": [{"suggested": s, "real": t["text"]} for t, s in items[:3]],  # both are the user's side only
    }


# ---- the whole build -----------------------------------------------------------------------------------

def build(style_id, files, spark, meta_key, wait_for_me, commit=lambda: None, train=None):
    """files: [(name, bytes)]. wait_for_me(meta) → meta with "me" and "chats" set by the app, or None (timed out).
    train(style_id) → starts the LoRA and returns when it's saved, or None when training is off."""
    def stage(name, progress, **fields):
        styles.update(style_id, stage=name, progress=progress, **fields)
        commit()

    try:
        stage("parsing", 0.05)
        exports = [(n, b) for n, b in files if Path(n).suffix.lower() in EXPORTS]
        images = [(n, b) for n, b in files if Path(n).suffix.lower() in IMAGES]
        chats = read_exports(exports)
        chats.update({f"{name}": messages for name, messages in read_images(images, spark).items()})
        chats = {name: messages for name, messages in chats.items() if messages}
        if not chats:
            return stage("failed", 0, status="failed", error="Couldn't read any messages from these files.")

        participants = Counter(m["sender"] for messages in chats.values() for m in messages)
        guesses = {}
        for name, messages in chats.items():
            sample = "\n".join(f"{m['sender']}: {m['text'][:200]}" for m in messages[-40:] if m["kind"] == "text")
            guesses[name] = spark(AUDIENCE_SYSTEM, sample, "audience").get("audience")
            if guesses[name] not in AUDIENCES:
                guesses[name] = "friends"
        me = "me" if set(participants) <= {"me", "them"} else None
        stage("needs_me", 0.15, participants=[p for p, _ in participants.most_common(12) if p not in {"them"}],
              chats=guesses, me=me, needs=["me", "chats"] if me is None else ["chats"])
        confirmed = wait_for_me(styles.meta(style_id))
        if confirmed is None:
            return stage("failed", 0, status="failed", error="Nobody said which participant is you.")
        me, audiences = confirmed["me"], confirmed.get("chats") or guesses

        stage("reading", 0.25, participants=[], needs=[])
        turns = []
        for name, messages in chats.items():
            turns += turns_of(name, messages, me, audiences.get(name, "friends"))
        del chats  # the other people's messages go away as soon as possible
        if len(turns) < 10:
            return stage("failed", 0, status="failed", error=f"Only {len(turns)} of your messages found; add more chats.")
        train_turns = [t for t in turns if t["split"] == "train"]
        held_out = [t for t in turns if t["split"] == "test" and t["context"]]
        random.Random(0).shuffle(train_turns)
        tagged = tag(train_turns[:MAX_TURNS] + held_out[:CHECK_TURNS], spark)
        keep = ("audience", "situation", "act", "tone", "text", "split", "start")
        styles.write_jsonl(styles.folder(style_id) / "turns.jsonl", [{k: t[k] for k in keep} for t in tagged])

        stage("profile", 0.6)
        own = [t for t in tagged if t["split"] == "train"]
        styles.write_json(styles.folder(style_id) / "profile.json", profile_of(own))
        pairs = pairs_of(tagged)
        for split in ("train", "test"):
            styles.write_jsonl(styles.folder(style_id) / "pairs" / f"{split}.jsonl", pairs[split])
        counts = {"chats": len(audiences), "turns": len(own), "pairs": len(pairs["train"])}
        stage("checking", 0.7, counts=counts)
        check = self_check(style_id, [t for t in tagged if t["split"] == "test" and t["context"]], spark, meta_key)
        for t in tagged:
            t.pop("context", None)

        lora = len(own) >= MIN_LORA_TURNS and train is not None
        stage("training" if lora else "ready", 0.85 if lora else 1.0, status="ready", scores=check,
              lora="training" if lora else ("waiting for GPU" if len(own) >= MIN_LORA_TURNS else "needs more messages"))
        if lora:
            saved = train(style_id)
            stage("ready", 1.0, adapter_ready=bool(saved), lora="ready" if saved else "failed")
    except Exception as error:  # the app shows it; nothing of the uploads is kept
        stage("failed", 0, status="failed", error=f"Build failed: {type(error).__name__}")
        raise
