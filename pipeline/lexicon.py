"""The user's personal dictionary: which words they use, which they never use, and how they
swap ordinary words for their own.

Reference corpus: the neutral standard-Russian drafts that Muse Spark Open wrote for the
user's own turns (data/synth_cache.jsonl, task rewrite). Each draft is paired with what the
user actually wrote, so the comparison is about word choice, not topic.

  signature      words the user writes far more often than neutral Russian (log-odds, informative prior)
  avoid          words neutral Russian uses for the same content but the user (almost) never does
  substitutions  draft word → user word, from word-level alignment of draft vs real turn

Usage: python3 pipeline/lexicon.py      → data/lexicon.json (gitignored) + top lists printed
"""

import difflib
import json
import math
import re
from collections import Counter

from parse_telegram import ROOT

DATA = ROOT / "data"
WORD = re.compile(r"[а-яёa-zәғқңөұүһі]+", re.I)
LAUGH = re.compile(r"^(а?х[аеиох]){2,}х?$|^(х[аи]){2,}$")


def words(text):
    out = []
    for word in WORD.findall(text.lower()):
        out.append("ахах~" if LAUGH.match(word) else word)
    return out


def load(path=None):
    lex = json.loads((path or DATA / "lexicon.json").read_text(encoding="utf-8"))
    return {"vocab": {w for w, n in lex["vocab"].items() if n >= 2},
            "avoid": set(lex["avoid"]), "signature": set(lex["signature"][:150])}


USER_SIGNATURE_RATE = 0.10  # own words per word in the user's real turns (benchmark "real" column)
USER_UNKNOWN_RATE = 0.10    # share of words outside their 2+ vocabulary in real turns
USER_TYPICAL_CHARS = 28     # mean turn length; longer candidates dilute the rates, so length is scored too


def score(text, lex):
    """Word-choice score for reranking candidates: closest to the user's own rates wins.

    Maximizing own words picks caricatures ("ахахах бля короче"), so the score rewards matching
    the user's signature-word rate, penalizes never-used words above their usual rate, and avoided words.
    """
    tokens = words(text)
    if not tokens:
        return -1.0
    signature = sum(t in lex["signature"] for t in tokens) / len(tokens)
    unknown = sum(t not in lex["vocab"] for t in tokens) / len(tokens)
    avoided = sum(t in lex["avoid"] for t in tokens)
    length = abs(math.log((len(text) + 10) / (USER_TYPICAL_CHARS + 10)))
    return (-abs(signature - USER_SIGNATURE_RATE) - max(0.0, unknown - USER_UNKNOWN_RATE)
            - 0.5 * avoided - 0.05 * length)


def log_odds(a: Counter, b: Counter, prior: Counter, alpha=0.01):
    """Monroe et al. log-odds ratio with an informative Dirichlet prior; returns z-scores (a vs b)."""
    na, nb = sum(a.values()), sum(b.values())
    a0 = sum(prior.values()) * alpha
    scores = {}
    for word in set(a) | set(b):
        p = prior[word] * alpha or alpha
        la = math.log((a[word] + p) / (na + a0 - a[word] - p))
        lb = math.log((b[word] + p) / (nb + a0 - b[word] - p))
        variance = 1 / (a[word] + p) + 1 / (b[word] + p)
        scores[word] = (la - lb) / math.sqrt(variance)
    return scores


def substitutions(pairs):
    """Count 1:1 word replacements between neutral draft and the user's real turn."""
    swaps = Counter()
    for draft, real in pairs:
        a, b = words(draft), words(real)
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
            if op == "replace" and i2 - i1 == j2 - j1:
                for x, y in zip(a[i1:i2], b[j1:j2]):
                    if x != y:
                        swaps[(x, y)] += 1
    return swaps


def main():
    turns = {}
    for line in (DATA / "turns.jsonl").open(encoding="utf-8"):
        row = json.loads(line)
        turns[row["turn_id"]] = row["text"]
    pairs = []
    for line in (DATA / "synth_cache.jsonl").open(encoding="utf-8"):
        item = json.loads(line)
        if item["task"] == "rewrite" and item["turn_id"] in turns:
            pairs.append((item["input"], turns[item["turn_id"]]))

    user_all = Counter(w for text in turns.values() for w in words(text))
    user_paired = Counter(w for _, real in pairs for w in words(real))
    neutral = Counter(w for draft, _ in pairs for w in words(draft))
    scores = log_odds(user_paired, neutral, user_all + neutral)

    signature = [w for w, s in sorted(scores.items(), key=lambda kv: -kv[1]) if s > 3 and user_all[w] >= 10]
    total_user, total_neutral = sum(user_all.values()), sum(neutral.values())
    avoid = [w for w, s in sorted(scores.items(), key=lambda kv: kv[1])
             if s < -2 and neutral[w] >= 5
             and user_all[w] / total_user < neutral[w] / total_neutral / 5]  # used 5x less than neutral Russian
    swaps = [(x, y, n) for (x, y), n in substitutions(pairs).most_common() if n >= 3]

    lexicon = {
        "vocab": dict(user_all.most_common()),
        "neutral_vocab": dict(neutral.most_common()),
        "signature": signature[:300],
        "avoid": avoid[:300],
        "substitutions": swaps[:300],
        "pairs_used": len(pairs),
    }
    (DATA / "lexicon.json").write_text(json.dumps(lexicon, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(pairs)} draft/real pairs, user vocabulary {len(user_all)} words\n")
    print("signature:", ", ".join(signature[:50]))
    print("\navoid:", ", ".join(avoid[:40]))
    print("\nsubstitutions:", ", ".join(f"{x}→{y} ({n})" for x, y, n in swaps[:40]))
    print(f"\n→ {(DATA / 'lexicon.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
