"""Preference pairs for word choice (SimPO/DPO): chosen = the user's real turn, rejected = the
same turn with the user's own words swapped back to neutral Russian (чо→что, щас→сейчас, пж→
пожалуйста...). Only the words differ, so the model learns word choice, not content or punctuation.

The swaps come from data/lexicon.json (pipeline/lexicon.py): for every user word, the neutral
word it most often replaced. Pairs with no swappable word are skipped.

  python3 training/build_prefs.py [--pairs pairs_v2]   → data/prefs/train.jsonl (gitignored)
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from lexicon import LAUGH, WORD  # noqa: E402


def neutral_forms(substitutions, neutral_vocab, min_count=3):
    """user word → the neutral word it most often stands for.

    Only swaps where the user's word is (almost) absent from neutral Russian, so "чо→что" and
    "пж→пожалуйста" pass but alignment noise like "не→нет" or "с→из" does not.
    """
    options = defaultdict(Counter)
    for neutral, user, count in substitutions:
        if (count >= min_count and neutral != user and not LAUGH.match(user)
                and neutral_vocab.get(user, 0) <= 0.1 * neutral_vocab.get(neutral, 0)):
            options[user][neutral] += count
    return {user: counts.most_common(1)[0][0] for user, counts in options.items()}


def destyle(text, back):
    """Swap the user's words for neutral ones, keeping everything else (case, punctuation, lines)."""
    swapped = 0

    def replace(match):
        nonlocal swapped
        word = match.group(0)
        neutral = back.get(word.lower())
        if not neutral:
            return word
        swapped += 1
        return neutral.capitalize() if word[:1].isupper() else neutral

    return WORD.sub(replace, text), swapped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", default="pairs_v2")
    args = parser.parse_args()

    lexicon = json.loads((ROOT / "data" / "lexicon.json").read_text(encoding="utf-8"))
    back = neutral_forms(lexicon["substitutions"], lexicon["neutral_vocab"])
    print(f"{len(back)} reverse swaps, e.g. " + ", ".join(f"{u}→{n}" for u, n in list(back.items())[:12]))

    prefs, swaps = [], Counter()
    for line in (ROOT / "data" / args.pairs / "train.jsonl").open(encoding="utf-8"):
        pair = json.loads(line)
        chosen = pair["messages"][2]["content"]
        rejected, n = destyle(chosen, back)
        if n == 0 or rejected == chosen:
            continue
        swaps[min(n, 5)] += 1
        prefs.append({"prompt": pair["messages"][:2], "chosen": chosen, "rejected": rejected, "meta": pair["meta"]})

    out = ROOT / "data" / "prefs" / "train.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for item in prefs:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"{len(prefs)} preference pairs (swaps per pair: {dict(sorted(swaps.items()))}) → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
