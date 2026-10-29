"""Style metrics for benchmark outputs (data/bench/outputs.jsonl).

  fingerprint ↓  mean |feature mean(system) − feature mean(real)| / std(real) over ~15 stylometric features
  chrF ↑         character n-gram F-score against the user's real reply to the same prompt
  memorized ↓    share of outputs that copy a train turn verbatim or share a 40-char span with one
  act/tone       (reply pairs tagged by bench_generate --tag) does the output make the same move as the user
                 (act match ↑, tone match ↑) and the same mix of moves per audience (act TV ↓, total variation)
Prints a table per system (and per task with --by task) and writes aggregated numbers only
(no message text) to eval/results/<name>.json.

  python3 eval/metrics.py [--by task|audience|situation] [--name bench_v1]
"""

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
LAUGH = re.compile(r"(ах|ха|хи|хе|аха|lol|lmao|ахах|хах)\1+|ахах|хаха|хих", re.I)
SWEAR = re.compile(r"бля|хуй|хуе|хуё|пизд|еба|ёба|еби|нахуй|нах\b|сука|fuck|shit", re.I)
KAZAKH = re.compile("[әғқңөұүһі]", re.I)


def features(text: str) -> dict:
    lines = [line for line in text.split("\n") if line.strip()] or [""]
    letters = re.findall(r"[^\W\d_]", text)
    latin = sum(ch.isascii() for ch in letters)
    words = text.split()
    return {
        "chars": len(text),
        "lines": len(lines),
        "words_per_line": len(words) / len(lines),
        "end_period": sum(line.rstrip().endswith(".") for line in lines) / len(lines),
        "end_punct": sum(line.rstrip()[-1:] in ".!?" for line in lines) / len(lines),
        "question": sum("?" in line for line in lines) / len(lines),
        "lower_start": sum(line.lstrip()[:1].islower() for line in lines) / len(lines),
        "caps_words": sum(w.isupper() and len(w) > 1 for w in words) / max(len(words), 1),
        "commas_per_word": text.count(",") / max(len(words), 1),
        "emoji_per_line": len(EMOJI.findall(text)) / len(lines),
        "brackets": float("))" in text or ")" in text and "(" not in text),
        "laughter": float(bool(LAUGH.search(text))),
        "swear": float(bool(SWEAR.search(text))),
        "latin_share": latin / max(len(letters), 1),
        "kazakh": float(bool(KAZAKH.search(text))),
    }


def load_lexicon():
    path = ROOT / "data" / "lexicon.json"
    if not path.exists():
        return None
    lex = json.loads(path.read_text(encoding="utf-8"))
    return {"vocab": {w for w, n in lex["vocab"].items() if n >= 2},
            "avoid": set(lex["avoid"]), "signature": set(lex["signature"][:150])}


def word_choice(text, lex):
    """Avoid-word hit, share of words the user never used (2+ times), signature words per word."""
    import sys
    sys.path.insert(0, str(ROOT / "pipeline"))
    from lexicon import words
    tokens = words(text)
    if not tokens:
        return {"avoid_hit": 0.0, "unknown_words": 0.0, "signature_per_word": 0.0}
    return {
        "avoid_hit": float(any(t in lex["avoid"] for t in tokens)),
        "unknown_words": sum(t not in lex["vocab"] for t in tokens) / len(tokens),
        "signature_per_word": sum(t in lex["signature"] for t in tokens) / len(tokens),
    }


def chrf(hypothesis: str, reference: str, n_max: int = 6, beta: float = 2.0) -> float:
    def grams(text, n):
        text = text.replace(" ", "")
        return Counter(text[i:i + n] for i in range(len(text) - n + 1))
    precisions, recalls = [], []
    for n in range(1, n_max + 1):
        h, r = grams(hypothesis, n), grams(reference, n)
        if not h or not r:
            continue
        overlap = sum((h & r).values())
        precisions.append(overlap / sum(h.values()))
        recalls.append(overlap / sum(r.values()))
    if not precisions:
        return 0.0
    p, r = statistics.mean(precisions), statistics.mean(recalls)
    return 0.0 if p + r == 0 else 100 * (1 + beta ** 2) * p * r / (beta ** 2 * p + r)


def train_index(pairs="pairs_v2", window=40):
    turns = [json.loads(line)["messages"][2]["content"] for line in (ROOT / "data" / pairs / "train.jsonl").open(encoding="utf-8")]
    spans = {t[i:i + window] for t in turns for i in range(0, max(len(t) - window + 1, 0))}
    return set(turns), spans, window


def memorized(text, index):
    turns, spans, window = index
    if len(text) >= 15 and text in turns:
        return True
    return any(text[i:i + window] in spans for i in range(0, max(len(text) - window + 1, 0)))


def summarize(rows, index, lex=None):
    real = [features(r["target"]) for r in rows if r["system"] == rows[0]["system"]]
    lexical = lambda items, key: {f: statistics.mean(word_choice(r[key], lex)[f] for r in items)
                                  for f in ("avoid_hit", "unknown_words", "signature_per_word")} if lex else {}
    names = list(real[0])
    real_mean = {f: statistics.mean(x[f] for x in real) for f in names}
    real_std = {f: statistics.pstdev([x[f] for x in real]) or 1.0 for f in names}

    by_system = defaultdict(list)
    for row in rows:
        by_system[row["system"]].append(row)
    first = [r for r in rows if r["system"] == rows[0]["system"]]
    table = {"real": {"features": real_mean, "words": lexical(first, "target")}}
    for system, items in by_system.items():
        feats = [features(r["output"]) for r in items]
        means = {f: statistics.mean(x[f] for x in feats) for f in names}
        table[system] = {
            "n": len(items),
            "fingerprint": statistics.mean(abs(means[f] - real_mean[f]) / real_std[f] for f in names),
            "chrf": statistics.mean(chrf(r["output"], r["target"]) for r in items),
            "memorized": statistics.mean(memorized(r["output"], index) for r in items),
            "empty": statistics.mean(not r["output"].strip() for r in items),
            "median_chars": statistics.median(len(r["output"]) for r in items),
            "features": means,
            "words": lexical(items, "output"),
        }
    return table


def total_variation(a, b):
    ca, cb = Counter(a), Counter(b)
    return sum(abs(ca[k] / len(a) - cb[k] / len(b)) for k in set(ca) | set(cb)) / 2


def thinking(rows):
    """Act/tone of the chosen output vs the user's real reply, tagged by the same base-Glimmer prompt."""
    by_system = defaultdict(list)
    for row in rows:
        if row.get("candidate_tags") and row["output"] in row["candidates"]:
            tag = row["candidate_tags"][row["candidates"].index(row["output"])]
            if None in tag or None in row["target_tag"]:  # the tagger failed: no match, no category
                continue
            by_system[row["system"]].append((row["audience"], row["target_tag"], tag))
    table = {}
    for system, items in by_system.items():
        audiences = defaultdict(lambda: ([], []))
        for audience, real, out in items:
            audiences[audience][0].append(real[0])
            audiences[audience][1].append(out[0])
        table[system] = {
            "n": len(items),
            "act_match": statistics.mean(real[0] == out[0] for _, real, out in items),
            "tone_match": statistics.mean(real[1] == out[1] for _, real, out in items),
            "act_tv": sum(len(r) * total_variation(r, o) for r, o in audiences.values()) / len(items),
            "tone_tv": total_variation([real[1] for _, real, _ in items], [out[1] for _, _, out in items]),
        }
    if table:
        print(f"\n{'act/tone (replies)':<20}{'n':>5}{'act match↑':>12}{'tone match↑':>13}{'act TV↓':>9}{'tone TV↓':>10}")
        for system, t in table.items():
            print(f"{system:<20}{t['n']:>5}{t['act_match']:>12.1%}{t['tone_match']:>13.1%}{t['act_tv']:>9.2f}{t['tone_tv']:>10.2f}")
    return table


def print_table(title, table):
    systems = [s for s in table if s != "real"]
    print(f"\n{title}")
    print(f"{'system':<10}{'n':>5}{'fingerprint↓':>14}{'chrF↑':>8}{'memorized↓':>12}{'empty':>7}{'med chars':>11}")
    for s in systems:
        t = table[s]
        print(f"{s:<10}{t['n']:>5}{t['fingerprint']:>14.2f}{t['chrf']:>8.1f}{t['memorized']:>11.1%}"
              f"{t['empty']:>7.0%}{t['median_chars']:>11.0f}")
    print(f"\n{'feature':<16}{'real':>8}" + "".join(f"{s:>10}" for s in systems))
    for f in ("chars", "lines", "lower_start", "end_period", "end_punct", "emoji_per_line", "laughter",
              "swear", "latin_share", "commas_per_word"):
        print(f"{f:<16}{table['real']['features'][f]:>8.2f}" + "".join(f"{table[s]['features'][f]:>10.2f}" for s in systems))
    if table["real"].get("words"):
        print(f"\n{'word choice':<20}{'real':>8}" + "".join(f"{s:>10}" for s in systems))
        for f, label in (("avoid_hit", "avoid-word hit ↓"), ("unknown_words", "never-used words ↓"),
                         ("signature_per_word", "own words/word ↑")):
            print(f"{label:<20}{table['real']['words'][f]:>8.2f}" + "".join(f"{table[s]['words'][f]:>10.2f}" for s in systems))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--by", choices=["task", "audience", "situation"])
    parser.add_argument("--name", default="bench")
    parser.add_argument("--input", default="outputs", help="data/bench/<input>.jsonl")
    parser.add_argument("--best-of", action="store_true",
                        help="also score '<system>+best' (lexicon) and '<system>+cell' (audience × situation stats)")
    parser.add_argument("--pairs", default="pairs_v2", help="train pairs for the per-cell statistics")
    args = parser.parse_args()

    rows = [json.loads(line) for line in (ROOT / "data/bench" / f"{args.input}.jsonl").open(encoding="utf-8")]
    if args.best_of:  # add "<system>+best": the candidate with the best word-choice score
        import sys
        sys.path.insert(0, str(ROOT / "pipeline"))
        import lexicon
        lex_for_rerank = lexicon.load()
        from style_stats import StyleStats
        stats = StyleStats.from_pairs(args.pairs)
        multi = [r for r in rows if len(r.get("candidates", [])) > 1]
        rows += [{**r, "system": f"{r['system']}+best", "output": max(r["candidates"], key=lambda c: lexicon.score(c, lex_for_rerank))}
                 for r in multi]
        # "+cell": closest to a random real turn of the same audience × situation (user's distribution)
        rows += [{**r, "system": f"{r['system']}+cell",
                  "output": stats.pick(r["candidates"], r["audience"], r["situation"], key=r["turn_id"])}
                 for r in multi]
    index, lex = train_index(args.pairs), load_lexicon()
    results = {"all": summarize(rows, index, lex)}
    print_table("all test pairs", results["all"])
    results["thinking"] = thinking(rows)
    if args.by:
        groups = defaultdict(list)
        for row in rows:
            groups[row[args.by]].append(row)
        for key, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            if len({r["turn_id"] for r in items}) >= 20:
                results[f"{args.by}={key}"] = summarize(items, index, lex)
                print_table(f"{args.by} = {key}", results[f"{args.by}={key}"])

    out = ROOT / "eval" / "results" / f"{args.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\naggregated numbers → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
