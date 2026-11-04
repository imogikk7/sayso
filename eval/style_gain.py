"""How much each part of the Spark path adds: held-out rewrite pairs of the main style (neutral draft → what the user
really wrote), written four ways, scored against the user's real messages.

  generic    Muse Spark, no style at all
  profile    + the user's style profile (how the API worked before Oct 31)
  examples   + the user's real messages for that audience (random ones)
  production + the user's messages most like the draft in words and spelling (TF-IDF, computed on our server; on
             Nov 1 Fireworks embeddings scored the same within noise: form 0.93, chrF 53.2), and + asking for 4 more variants (alternatives for ✨); Spark's own answer is kept.
             Picking the variant closest to the user's statistics instead (best-of-5) scored form 0.94, chrF 41.5 on
             Nov 1, so production doesn't.

--writer lora: would the user's own model write better than Muse Spark Open? The same 40 rewrites, written the way the
server writes them with the GPU on (SAYSO_GPU=modal), next to what it writes now:
  production    Muse Spark Open, as above (the live server today)
  lora          ✨ Rewrite with the GPU on: Muse Glimmer 30B + the style's LoRA (v4) rewrites the draft, 5 candidates,
                the one closest to the user's statistics wins (Writer.styled, unchanged)
  lora_norerank the same LoRA, its first candidate (what the rerank adds)
  open+lora     Spark Open's answer, then rewritten by the LoRA like the Back Tap drafts are (Writer.reply with options)
The unchanged Writer code runs here twice: the first pass records every request it would send vLLM, one H100 answers
them all in an ephemeral Modal app (eval/lora_gpu.py: never the deployed one), the second pass finishes them. It needs
--gpu-ok, prints the expected cost first, and writes ~10 side-by-side samples to data/style_gain/ (gitignored).

Scores: form = 1 − total variation of the form features vs the real messages (serving/build_style.similarity, as in the
style self-check); chrF = character n-gram overlap with the real message (eval/metrics.chrf). Only the numbers are written
(eval/results/style_gain.json, style_gain_<writer>.json); the messages themselves stay on this machine.

  .venv/bin/python eval/style_gain.py --limit 40
  .venv/bin/python eval/style_gain.py --writer lora --gpu-ok
"""

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "eval")]

import writer  # noqa: E402
from build_style import similarity  # noqa: E402
from metrics import chrf  # noqa: E402

WRITER = "meta"  # --writer open: Muse Spark Open (Baseten) writes first; --writer lora: the user's LoRA vs Spark Open
GENERIC = 'Rewrite this draft as a casual chat message in the language of the draft. Return JSON only: {"text": "<message>"}.'
SPARK_CONDITIONS = ["generic", "profile", "examples", "production"]
LORA_CONDITIONS = ["production", "lora", "open+lora"]  # lora_norerank comes with lora
RESULTS = ROOT / "eval" / "results"  # aggregate numbers only (committed)
SAMPLES = ROOT / "data" / "style_gain" / "lora_samples.md"  # data/ is gitignored: the user's real messages
GPU_URL = "http://lora-eval"  # never contacted: GPUClient answers these requests

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


def read_env():
    return dict(line.strip().split("=", 1) for line in (ROOT / ".env").open() if "=" in line and not line.startswith("#"))


async def spark_outputs(rows, env, hows, writer_name):
    """{how: [text or "" per row]} written by Muse Spark (writer_name: "meta" or "open" writes first)."""
    import httpx

    async with httpx.AsyncClient(verify=VERIFY, timeout=60) as client:
        w = writer.Writer(client, "http://unused", "", None, env["META_API_KEY"], gpu="off", retrieval="local",
                          fallback_key=env.get("BASETEN_API_KEY"), writer=writer_name)
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

        return {how: list(await asyncio.gather(*(write(r, how) for r in rows))) for how in hows}


def score(written, real):
    pairs = [(o, t) for o, t in zip(written, real) if o]
    return {"form": similarity([o for o, _ in pairs], real),
            "chrf": round(statistics.mean(chrf(o, t) for o, t in pairs), 1) if pairs else 0.0, "n": len(pairs)}


def show(results):
    for how, r in results.items():
        print(f"{how:<14} form {r['form']:.2f}   chrF {r['chrf']:.1f}   (n={r['n']})")


def main(limit):
    rows = held_out(limit)
    real = [writer.one_message(r["real"]) for r in rows]
    written = asyncio.run(spark_outputs(rows, read_env(), ONLY, WRITER))
    results = {how: score(written[how], real) for how in ONLY}
    show(results)
    out = ROOT / "eval" / "results" / ("style_gain.json" if WRITER == "meta" else f"style_gain_{WRITER}.json")
    out.write_text(json.dumps({"pairs": len(rows), "results": results}, indent=1))
    print("→", out.relative_to(ROOT))


# ---- --writer lora: the server with the GPU on, its vLLM calls answered by one ephemeral H100 -----------------------

class MarkTokenizer:
    """Stands in for the model's tokenizer on this machine: Writer.prompt runs unchanged, and the chat messages it
    builds travel to the GPU, where the model's own tokenizer renders them (eval/lora_gpu.render)."""
    bos_token = None

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        import lora_gpu
        return lora_gpu.marked(messages)


class Recorded(Exception):
    """The first pass stops at the first vLLM call of each request, once the request is recorded."""


class Response:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


def body_key(body):
    return json.dumps(body, sort_keys=True, ensure_ascii=False)


class GPUClient:
    """The Writer's HTTP client for its vLLM calls only: the first pass records each /v1/completions body, the second
    answers it with what the GPU generated for that body (identical bodies get their answers in order)."""

    def __init__(self):
        self.bodies, self.answers = [], None

    async def post(self, url, timeout=None, headers=None, json=None):
        if url != f"{GPU_URL}/v1/completions":
            raise AssertionError(f"the LoRA pass called {url}: only vLLM is expected here")
        if self.answers is None:
            self.bodies.append(json)
            raise Recorded
        return Response(self.answers[body_key(json)].pop(0))

    def load(self, keys, answers):
        self.answers = defaultdict(list)
        for key, answer in zip(keys, answers):
            self.answers[key].append(answer)


class LoraWriter(writer.Writer):
    """serving/writer.py's Writer as the server runs it with SAYSO_GPU=modal once the H100 is up and the adapter loaded
    (uses_model without the warm-up check, which only exists so the app never waits for a cold GPU)."""

    async def uses_model(self, ctx, format="message"):
        return bool(ctx.adapter) and format in writer.CHAT_FORMATS


async def lora_pass(w, ctx, rows, drafts):
    """[{condition: text}] per row; in the recording pass a request stops at its vLLM call and gives nothing."""
    out = []
    for row, draft in zip(rows, drafts):
        got = {}
        try:
            result = await w.rewrite(ctx, row["draft"], row["audience"], row["situation"])
            got["lora"], got["lora_norerank"] = result["text"], result["candidates"][0]
        except Recorded:
            pass
        if draft:
            try:  # act is only a label on the reply; the text comes from the draft
                reply = await w.reply(ctx, "", row["audience"], row["situation"],
                                      options=[{"act": "agree", "draft": draft}])
                got["open+lora"] = reply[0]["text"]
            except Recorded:
                pass
        out.append({k: writer.one_message(v) for k, v in got.items()})
    return out


def lora_outputs(ctx, rows, drafts, gpu):
    """gpu(adapter, bodies) → vLLM responses, one per body (lora_gpu.run on a real run, a fake in the tests)."""
    client = GPUClient()
    w = LoraWriter(client, GPU_URL, "", MarkTokenizer(), "", gpu="modal", retrieval="local")
    asyncio.run(lora_pass(w, ctx, rows, drafts))
    keys = [body_key(b) for b in client.bodies]
    print(f"{len(client.bodies)} requests for the LoRA, {sum(len(b['prompt']) for b in client.bodies)} prompts")
    client.load(keys, gpu(ctx.adapter, json.loads(json.dumps(client.bodies))))
    return asyncio.run(lora_pass(w, ctx, rows, drafts))


def paired(base, other, real, rounds=1000, seed=0):
    """other − base on the rows both wrote: chrF (mean of per-row differences) and form, each with a 95 % bootstrap
    interval over the rows, and how often other's chrF beats base's."""
    rows = [(b, o, t) for b, o, t in zip(base, other, real) if b and o]
    if not rows:
        return {"n": 0}
    diffs = [chrf(o, t) - chrf(b, t) for b, o, t in rows]

    def form(sample):
        return similarity([o for _, o, _ in sample], [t for *_, t in sample]) - similarity(
            [b for b, _, _ in sample], [t for *_, t in sample])

    rng = random.Random(seed)
    chrf_boot, form_boot = [], []
    for _ in range(rounds):
        picks = [rng.randrange(len(rows)) for _ in rows]
        chrf_boot.append(statistics.mean(diffs[i] for i in picks))
        form_boot.append(form([rows[i] for i in picks]))

    def ci(values, digits):
        values = sorted(values)
        return [round(values[int(0.025 * len(values))], digits), round(values[int(0.975 * len(values)) - 1], digits)]

    return {"n": len(rows), "chrf_diff": round(statistics.mean(diffs), 1), "chrf_ci": ci(chrf_boot, 1),
            "form_diff": round(form(rows), 2), "form_ci": ci(form_boot, 2),
            "chrf_wins": sum(d > 0 for d in diffs), "chrf_losses": sum(d < 0 for d in diffs)}


def verdict(p):
    """Wording decides (chrF against the user's real message), as long as the form doesn't get clearly worse."""
    if not p.get("n"):
        return "nothing to compare"
    if p["chrf_ci"][0] > 0 and p["form_ci"][1] >= 0:
        return "BETTER than Spark Open: closer to the user's real words, form no worse"
    if p["chrf_ci"][1] < 0 or p["form_ci"][1] < 0:
        return "WORSE than Spark Open"
    return "NO CLEAR DIFFERENCE at this sample size: Spark Open is already live and costs no GPU"


def write_samples(rows, production, lora, count=10):
    """Side by side for the owner to read: data/ only (gitignored), never a committed file."""
    lines = ["# Spark Open vs LoRA, held-out rewrites (private: the user's real messages, never commit)\n"]
    shown = 0
    for row, spark, mine in zip(rows, production, lora):
        if shown == count or not mine.get("lora"):
            continue
        shown += 1
        lines += [f"## {shown}. {row['audience']} · {row['situation']}", f"- draft: {row['draft']}",
                  f"- **real**: {writer.one_message(row['real'])}", f"- spark open: {spark or '—'}",
                  f"- lora: {mine['lora']}", f"- lora (no rerank): {mine.get('lora_norerank', '—')}",
                  f"- open+lora: {mine.get('open+lora', '—')}", ""]
    SAMPLES.parent.mkdir(parents=True, exist_ok=True)
    SAMPLES.write_text("\n".join(lines), encoding="utf-8")
    return shown


def lora_main(limit, gpu_ok, gpu=None):
    import lora_gpu

    print(f"--writer lora: {limit} held-out rewrites, Spark Open (production now) vs the user's LoRA on Muse Glimmer 30B")
    print("GPU:", lora_gpu.estimate())
    if not gpu_ok:
        print("Nothing started. Add --gpu-ok to run it.")
        return 2
    real_gpu = gpu is None
    if real_gpu:
        if lora_gpu.modal is None:
            print("Modal isn't installed here: run it with the project venv (.venv/bin/python, where the Modal CLI is).")
            return 1
        gpu = lora_gpu.run
    env = read_env()
    missing = [k for k in ("META_API_KEY", "BASETEN_API_KEY") if not env.get(k)]
    if missing:
        print(f".env has no {', '.join(missing)}: Spark Open can't write the production answers.")
        return 1
    rows = held_out(limit)
    ctx = writer.Context("main")
    if not ctx.adapter:
        print("the main style has no adapter in its meta: nothing for the LoRA to load")
        return 1
    if real_gpu and (problem := lora_gpu.check_volumes(ctx.adapter)):
        print(f"Not starting the GPU: {problem}")
        return 1
    only = [how for how in LORA_CONDITIONS if how in ONLY] if ONLY else LORA_CONDITIONS
    real = [writer.one_message(r["real"]) for r in rows]
    production = asyncio.run(spark_outputs(rows, env, ["production"], "open"))["production"]
    drafts = production if "open+lora" in only else [""] * len(rows)
    started = time.monotonic()
    try:
        lora = lora_outputs(ctx, rows, drafts, gpu)
    except Exception as error:  # adapter or model missing, Modal not logged in, GPU timeout
        print(f"The GPU run failed after {time.monotonic() - started:.0f} s, nothing written: {error}")
        return 1
    print(f"GPU part took {(time.monotonic() - started) / 60:.1f} min (wall clock, incl. the cold start)")
    written = {"production": production}
    for how in ("lora", "lora_norerank", "open+lora"):
        if how in only or (how == "lora_norerank" and "lora" in only):
            written[how] = [got.get(how, "") for got in lora]
    results = {how: score(texts, real) for how, texts in written.items()}
    show(results)
    compared = {how: paired(production, written[how], real) for how in written if how != "production"}
    for how, p in compared.items():
        if p.get("n"):
            print(f"{how:<14} vs Spark Open: chrF {p['chrf_diff']:+.1f} (95% CI {p['chrf_ci'][0]:+.1f}…"
                  f"{p['chrf_ci'][1]:+.1f}), form {p['form_diff']:+.2f} ({p['form_ci'][0]:+.2f}…{p['form_ci'][1]:+.2f}), "
                  f"wins {p['chrf_wins']}/{p['n']} → {verdict(p)}")
    out = RESULTS / "style_gain_lora.json"
    out.write_text(json.dumps({"pairs": len(rows), "results": results, "vs_production": compared}, indent=1))
    print("→", out)
    shown = write_samples(rows, production, lora)
    print(f"→ {SAMPLES} ({shown} side by side; private, gitignored)")
    return 0


ONLY = None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--writer", choices=["meta", "open", "lora"], default="meta")
    parser.add_argument("--only", nargs="*", default=None,
                        help=f"spark: {' '.join(SPARK_CONDITIONS)}; lora: {' '.join(LORA_CONDITIONS)}")
    parser.add_argument("--gpu-ok", action="store_true", help="--writer lora: allow starting one H100 (~$0.5)")
    args = parser.parse_args()
    WRITER, ONLY = args.writer, args.only
    if WRITER == "lora":
        sys.exit(lora_main(args.limit, args.gpu_ok))
    ONLY = ONLY or SPARK_CONDITIONS
    main(args.limit)
