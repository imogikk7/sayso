"""The user's style profile: how they write to each audience, from their imported messages only.

Per audience (and per audience × situation with enough turns): what they choose to do (act shares),
in what tone (tone shares), how often they start the conversation, and the form of the message
(length, lines, punctuation, emoji, laughter, swearing). Describes how the user writes, never personality.
Feeds the app's style card and the v4 "profile" mode (act + tone drawn from these shares).

  python pipeline/style_profile.py            # prints the profile, writes data/style_profile.json
"""

import json
import statistics
import sys
from collections import Counter, defaultdict

from parse_telegram import ROOT

sys.path.insert(0, str(ROOT / "eval"))
from metrics import features  # noqa: E402

MIN_CELL = 30
TOP = 4


def shares(values, top=TOP):
    counts = Counter(values)
    return {k: round(n / len(values), 2) for k, n in counts.most_common(top)}


def describe(turns):
    feats = [features(t["text"]) for t in turns]
    mean = lambda f: round(statistics.mean(x[f] for x in feats), 2)
    return {
        "turns": len(turns),
        "acts": shares([t["act"] for t in turns]),
        "tones": shares([t["tone"] for t in turns]),
        "starts_conversation": round(statistics.mean(t["own"] for t in turns), 2),
        "median_chars": statistics.median(len(t["text"]) for t in turns),
        "lines": mean("lines"),
        "lowercase_start": mean("lower_start"),
        "ends_with_punctuation": mean("end_punct"),
        "question": mean("question"),
        "emoji": mean("emoji_per_line"),
        "laughter": mean("laughter"),
        "swear": mean("swear"),
    }


def build(pairs="pairs_v4"):
    thoughts = {t["turn_id"]: t for t in map(json.loads, (ROOT / "data" / "thoughts.jsonl").open(encoding="utf-8"))}
    sources = {s["turn_id"]: s["source"] for s in map(json.loads, (ROOT / "data" / "situations.jsonl").open(encoding="utf-8"))}
    turns = []
    for line in (ROOT / "data" / pairs / "train.jsonl").open(encoding="utf-8"):
        row = json.loads(line)
        meta = row["meta"]
        thought = thoughts.get(meta["turn_id"])
        if thought:
            turns.append({"audience": meta["audience"], "situation": meta["situation"], "text": row["messages"][2]["content"],
                          "act": thought["act"], "tone": thought["tone"], "own": sources.get(meta["turn_id"]) == "own"})
    by_audience, by_cell = defaultdict(list), defaultdict(list)
    for t in turns:
        by_audience[t["audience"]].append(t)
        by_cell[(t["audience"], t["situation"])].append(t)
    profile = {}
    for audience, items in sorted(by_audience.items(), key=lambda kv: -len(kv[1])):
        profile[audience] = describe(items)
        profile[audience]["situations"] = {
            situation: describe(cell) for (a, situation), cell in sorted(by_cell.items(), key=lambda kv: -len(kv[1]))
            if a == audience and len(cell) >= MIN_CELL and situation != "other"
        }
    return profile


def show(profile):
    for audience, p in profile.items():
        print(f"\n== {audience} ({p['turns']} turns) — starts {p['starts_conversation']:.0%}, "
              f"~{p['median_chars']:.0f} chars, {p['lines']} lines, emoji {p['emoji']}, laughter {p['laughter']:.0%}, "
              f"swear {p['swear']:.0%}, lowercase {p['lowercase_start']:.0%}, end punct {p['ends_with_punctuation']:.0%}")
        print("   acts: " + ", ".join(f"{k} {v:.0%}" for k, v in p["acts"].items()))
        print("   tones: " + ", ".join(f"{k} {v:.0%}" for k, v in p["tones"].items()))
        for situation, c in list(p["situations"].items())[:6]:
            print(f"   · {situation:<11} ({c['turns']}): " + ", ".join(f"{k} {v:.0%}" for k, v in list(c["acts"].items())[:3])
                  + " | " + ", ".join(f"{k} {v:.0%}" for k, v in list(c["tones"].items())[:2])
                  + f" | ~{c['median_chars']:.0f} chars")


if __name__ == "__main__":
    profile = build()
    (ROOT / "data" / "style_profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    show(profile)
