"""Style metrics for benchmark outputs (data/bench/outputs.jsonl).

  fingerprint ↓  mean |feature mean(system) − feature mean(real)| / std(real) over ~15 stylometric features
  chrF ↑         character n-gram F-score against the user's real reply to the same prompt
  memorized ↓    share of outputs that copy a train turn verbatim or share a 40-char span with one
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


def train_index(window=40):
    turns = [json.loads(line)["messages"][2]["content"] for line in (ROOT / "data/pairs/train.jsonl").open(encoding="utf-8")]
    spans = {t[i:i + window] for t in turns for i in range(0, max(len(t) - window + 1, 0))}
    return set(turns), spans, window


def memorized(text, index):
    turns, spans, window = index
    if len(text) >= 15 and text in turns:
        return True
    return any(text[i:i + window] in spans for i in range(0, max(len(text) - window + 1, 0)))


def summarize(rows, index):
    real = [features(r["target"]) for r in rows if r["system"] == rows[0]["system"]]
    names = list(real[0])
    real_mean = {f: statistics.mean(x[f] for x in real) for f in names}
    real_std = {f: statistics.pstdev([x[f] for x in real]) or 1.0 for f in names}

    by_system = defaultdict(list)
    for row in rows:
        by_system[row["system"]].append(row)
    table = {"real": {"features": real_mean}}
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
        }
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--by", choices=["task", "audience", "situation"])
    parser.add_argument("--name", default="bench")
    parser.add_argument("--input", default="outputs", help="data/bench/<input>.jsonl")
    args = parser.parse_args()

    rows = [json.loads(line) for line in (ROOT / "data/bench" / f"{args.input}.jsonl").open(encoding="utf-8")]
    index = train_index()
    results = {"all": summarize(rows, index)}
    print_table("all test pairs", results["all"])
    if args.by:
        groups = defaultdict(list)
        for row in rows:
            groups[row[args.by]].append(row)
        for key, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            if len({r["turn_id"] for r in items}) >= 20:
                results[f"{args.by}={key}"] = summarize(items, index)
                print_table(f"{args.by} = {key}", results[f"{args.by}={key}"])

    out = ROOT / "eval" / "results" / f"{args.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\naggregated numbers → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
