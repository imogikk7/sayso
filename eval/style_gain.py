"""How much each part of the Spark path adds: held-out rewrite pairs of the main style (neutral draft → what the user
really wrote), written four ways, scored against the user's real messages.

  generic    Muse Spark, no style at all
  profile    + the user's style profile (how the API worked before Oct 31)
  examples   + the user's real messages for that audience
  variants   production: + asking for 4 more variants (alternatives for ✨); Spark's own answer is kept.
             Picking the variant closest to the user's statistics instead (best-of-5) scored form 0.94, chrF 41.5 on
             Nov 1, so production doesn't.

Scores: form = 1 − total variation of the form features vs the real messages (serving/build_style.similarity, as in the
style self-check); chrF = character n-gram overlap with the real message (eval/metrics.chrf). Only the numbers are written
(eval/results/style_gain.json); the messages themselves stay on this machine.

  .venv/bin/python eval/style_gain.py --limit 40
"""

import argparse
import asyncio
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "eval")]

import httpx  # noqa: E402

import writer  # noqa: E402
from build_style import similarity  # noqa: E402
from metrics import chrf  # noqa: E402

GENERIC = 'Rewrite this draft as a casual chat message in the language of the draft. Return JSON only: {"text": "<message>"}.'

try:  # python.org builds on macOS ship without root certificates
    import certifi
    VERIFY = certifi.where()
except ImportError:
    VERIFY = True


def held_out(limit):
    rows = [json.loads(line) for line in (ROOT / "data" / "pairs_v4" / "test.jsonl").open(encoding="utf-8")]
    rows = [r for r in rows if r["meta"]["task"] == "rewrite"]
    random.Random(0).shuffle(rows)
    return [{"audience": r["meta"]["audience"], "situation": r["meta"]["situation"], "real": r["messages"][2]["content"],
             "draft": r["messages"][1]["content"].split("draft: ", 1)[1]} for r in rows[:limit]]


async def main(limit):
    env = dict(line.strip().split("=", 1) for line in (ROOT / ".env").open() if "=" in line and not line.startswith("#"))
    rows = held_out(limit)
    async with httpx.AsyncClient(verify=VERIFY, timeout=60) as client:
        w = writer.Writer(client, "http://unused", "", None, env["META_API_KEY"], gpu="off")
        ctx = writer.Context("main")
        gate = asyncio.Semaphore(6)
        style = writer.STYLE_SYSTEM.format(style=ctx.style_text)

        async def write(row, how):
            ask = f"Rewrite this draft the way the user would write it to their {row['audience']} ({row['situation']})."
            async with gate:
                try:
                    if how == "generic":
                        label = await w.spark(GENERIC, row["draft"], "text")
                    elif how == "profile":
                        label = await w.spark(style, f"{ask}{w.format_line('message')}\n\n{row['draft']}", "text")
                    elif how == "examples":
                        label = await w.spark(style, f"{ask}{w.format_line('message')}"
                                                     f"{ctx.examples_for(row['audience'], row['situation'])}\n\n{row['draft']}",
                                              "text")
                    else:
                        return (await w.rewrite(ctx, row["draft"], row["audience"], row["situation"]))["text"]
                    return writer.one_message(label["text"])
                except writer.Unavailable:
                    return ""

        results = {}
        real = [writer.one_message(r["real"]) for r in rows]
        for how in ("generic", "profile", "examples", "variants"):
            written = await asyncio.gather(*(write(r, how) for r in rows))
            pairs = [(o, t) for o, t in zip(written, real) if o]
            results[how] = {"form": similarity([o for o, _ in pairs], real),
                            "chrf": round(statistics.mean(chrf(o, t) for o, t in pairs), 1), "n": len(pairs)}
            print(f"{how:<10} form {results[how]['form']:.2f}   chrF {results[how]['chrf']:.1f}   (n={len(pairs)})")
    out = ROOT / "eval" / "results" / "style_gain.json"
    out.write_text(json.dumps({"pairs": len(rows), "results": results}, indent=1))
    print("→", out.relative_to(ROOT))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=40)
    asyncio.run(main(parser.parse_args().limit))
