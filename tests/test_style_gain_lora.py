"""eval/style_gain.py --writer lora, no network and no GPU: the run needs --gpu-ok and touches nothing without it, the
GPU gets exactly the prompts and sampling the server would send vLLM (Writer.prompt/complete unchanged), the eval's
LoRA answer equals the server's for the same completions, the vLLM batching keeps indices right, the committed result
holds numbers only, and the side-by-side samples go to the gitignored data/ folder.

Usage: python3 -m pytest tests/test_style_gain_lora.py   (or python3 -m unittest tests/test_style_gain_lora.py)
"""

import asyncio
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "eval")]

import lora_gpu  # noqa: E402
import style_gain  # noqa: E402
import writer  # noqa: E402

ROWS = [  # made up
    {"audience": "friends", "situation": "invitation", "draft": "I can come tomorrow evening.", "real": "го завтра вечером"},
    {"audience": "family", "situation": "logistics", "draft": "I will call you later.", "real": "позже наберу"},
    {"audience": "partner", "situation": "affection", "draft": "Miss you.", "real": "скучаю("},
]


class FakeTokenizer:
    """A chat template that keeps the roles visible, with a BOS the prompt must drop."""
    bos_token = "<|bos|>"

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        return self.bos_token + "".join(f"[{m['role']}]{m['content']}" for m in messages) + "[assistant]"


def fake_completion(prompt, j, temperature):
    """Deterministic text from the rendered prompt: which draft it rewrites and which sample this is."""
    draft = prompt.split("draft: ", 1)[1].split("[assistant]", 1)[0]
    return f"{'r' if temperature == 0.8 else 'w'}{j} {draft[:12].lower()}<|eot|>junk"


def fake_gpu(calls=None):
    """lora_gpu.generate without vLLM: renders each recorded prompt with FakeTokenizer, answers in vLLM's shape."""
    def gpu(adapter, bodies):
        if calls is not None:
            calls.append((adapter, json.loads(json.dumps(bodies))))
        for body in bodies:
            body["prompt"] = [lora_gpu.render(p, FakeTokenizer()) for p in body["prompt"]]
        return lora_gpu.answer(bodies, lambda prompts, params: [
            [fake_completion(p, j, sp.get("temperature")) for j in range(sp["n"])] for p, sp in zip(prompts, params)])
    return gpu


def fake_ctx():
    return types.SimpleNamespace(id="main", adapter="v4", stats=None, lexical_weight=0.0,
                                 tone_for=lambda act, audience, situation: "neutral")


class ServerClient:
    """What the production Writer (SAYSO_GPU=modal) talks to: a warm vLLM answering with fake_completion."""

    async def get(self, url, **kwargs):
        return style_gain.Response({"data": []})

    async def post(self, url, timeout=None, headers=None, json=None):
        assert url.endswith("/v1/completions")
        prompts = json["prompt"]
        choices = [{"index": i * json["n"] + j, "text": fake_completion(p, j, json.get("temperature"))}
                   for i, p in enumerate(prompts) for j in range(json["n"])]
        return style_gain.Response({"choices": list(reversed(choices))})  # vLLM's order isn't guaranteed


class Patched:
    def patched(self, tmp):
        async def spark(rows, env, hows, writer_name):
            assert writer_name == "open"  # the live writer today
            return {"production": ["го завтра", "", "скучаю очень"]}  # the second one failed
        stack = mock.patch.multiple(style_gain, read_env=lambda: {"META_API_KEY": "x", "BASETEN_API_KEY": "y"},
                                    held_out=lambda limit: [dict(r) for r in ROWS[:limit]], spark_outputs=spark,
                                    RESULTS=tmp / "results", SAMPLES=tmp / "data" / "lora_samples.md")
        context = mock.patch.object(writer, "Context", lambda style_id: fake_ctx())

        class Both:
            def __enter__(self):
                (tmp / "results").mkdir()
                stack.__enter__()
                context.__enter__()

            def __exit__(self, *exc):
                context.__exit__(*exc)
                stack.__exit__(*exc)
        return Both()


class GuardTest(Patched, unittest.TestCase):
    def test_nothing_starts_without_gpu_ok(self):
        boom = mock.Mock(side_effect=AssertionError("touched"))
        with mock.patch.object(style_gain, "read_env", boom), mock.patch.object(style_gain, "held_out", boom), \
                mock.patch.object(lora_gpu, "check_volumes", boom, create=True), \
                mock.patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()) as out:
            self.assertEqual(style_gain.lora_main(40, gpu_ok=False, gpu=boom), 2)
        self.assertIn("--gpu-ok", out.getvalue())
        self.assertIn("H100", out.getvalue())
        boom.assert_not_called()

    def test_estimate_is_bounded(self):
        self.assertEqual(lora_gpu.TIMEOUT_MIN, 15)
        self.assertIn("hard stop at 15 min", lora_gpu.estimate())
        self.assertIn("$", lora_gpu.estimate())

    def test_gpu_failure_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, self.patched(Path(tmp)), \
                mock.patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()) as out:
            def broken(adapter, bodies):
                raise RuntimeError("adapter 'v4' not found at /data/adapters/v4 on the sayso-data volume")
            self.assertEqual(style_gain.lora_main(3, gpu_ok=True, gpu=broken), 1)
            self.assertEqual([p for p in Path(tmp).rglob("*") if p.is_file()], [])
        self.assertIn("not found", out.getvalue())


class PromptTest(unittest.TestCase):
    def test_gpu_renders_the_server_prompt(self):
        server = writer.Writer(None, "http://x", "", FakeTokenizer(), "", gpu="modal")
        here = style_gain.LoraWriter(None, style_gain.GPU_URL, "", style_gain.MarkTokenizer(), "", gpu="modal")
        for task, field, text in [("rewrite", "draft", "ну <|eot|> ок\nпотом"), ("compose", "instruction", "say hi")]:
            expected = server.prompt("friends", "joke", task, field, text) + writer.REPLY
            recorded = here.prompt("friends", "joke", task, field, text) + writer.REPLY
            self.assertEqual(lora_gpu.render(recorded, FakeTokenizer()), expected)
            self.assertFalse(expected.startswith("<|bos|>"))

    def test_render_refuses_unrecorded_prompts(self):
        with self.assertRaises(ValueError):
            lora_gpu.render("plain text", FakeTokenizer())

    def test_sampling_maps_every_field_the_server_sends(self):
        calls = []
        style_gain.lora_outputs(fake_ctx(), ROWS, ["го завтра", "", "скучаю"], fake_gpu(calls))
        for body in calls[0][1]:
            params = lora_gpu.sampling(body)
            self.assertEqual(params["stop"], ["<|eot|>", "<|eom|>"])
            self.assertIs(params["skip_special_tokens"], False)
            self.assertEqual((params["top_p"], params["top_k"]), (0.95, 64))
        with self.assertRaises(ValueError):
            lora_gpu.sampling({"model": "v4", "prompt": [], "n": 1, "presence_penalty": 1})

    def test_answer_keeps_vllm_indices(self):
        bodies = [{"model": "v4", "prompt": ["a", "b"], "n": 2}, {"model": "v4", "prompt": ["c"], "n": 3}]
        out = lora_gpu.answer(bodies, lambda prompts, params: [[f"{p}{j}" for j in range(sp["n"])]
                                                              for p, sp in zip(prompts, params)])
        self.assertEqual(out[0]["choices"], [{"index": 0, "text": "a0"}, {"index": 1, "text": "a1"},
                                             {"index": 2, "text": "b0"}, {"index": 3, "text": "b1"}])
        self.assertEqual([c["index"] for c in out[1]["choices"]], [0, 1, 2])


class LoraPathTest(unittest.TestCase):
    def test_requests_are_the_servers(self):
        calls = []
        style_gain.lora_outputs(fake_ctx(), ROWS, ["го завтра", "", "скучаю"], fake_gpu(calls))
        self.assertEqual(len(calls), 1)  # one GPU call for the whole run
        adapter, bodies = calls[0]
        self.assertEqual(adapter, "v4")
        self.assertEqual(len(bodies), 5)  # 3 rewrites + 2 Spark answers to restyle (one Spark answer failed)
        self.assertEqual({b["model"] for b in bodies}, {"v4"})
        self.assertEqual({b["n"] for b in bodies}, {writer.CANDIDATES + 2})
        temperatures = sorted(b["temperature"] for b in bodies)
        self.assertEqual(temperatures, [0.8, 0.8, 1.0, 1.0, 1.0])  # reply drafts: REWRITE_TEMPERATURE

    def test_same_answer_as_the_server(self):
        server = writer.Writer(ServerClient(), "http://glimmer", "k", FakeTokenizer(), "", gpu="modal")
        out = style_gain.lora_outputs(fake_ctx(), ROWS, ["го завтра", "", "скучаю"], fake_gpu())
        for row, got in zip(ROWS, out):
            expected = asyncio.run(server.rewrite(fake_ctx(), row["draft"], row["audience"], row["situation"]))
            self.assertEqual(got["lora"], expected["text"])
            self.assertEqual(got["lora_norerank"], expected["candidates"][0])
            self.assertNotIn("<|", got["lora"])
        expected = asyncio.run(server.reply(fake_ctx(), "", "partner", "affection",
                                            options=[{"act": "agree", "draft": "скучаю"}]))
        self.assertEqual(out[2]["open+lora"], expected[0]["text"])
        self.assertTrue(out[2]["open+lora"].startswith("r"))
        self.assertNotIn("open+lora", out[1])  # Spark Open failed there: nothing to restyle

    def test_spark_is_never_called_in_the_lora_pass(self):
        client = style_gain.GPUClient()
        with self.assertRaises(AssertionError):
            asyncio.run(client.post("https://api.meta.ai/v1/chat/completions", json={}))


class ResultTest(Patched, unittest.TestCase):
    def test_end_to_end_numbers_only(self):
        with tempfile.TemporaryDirectory() as tmp, self.patched(Path(tmp)), \
                mock.patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()) as out:
            self.assertEqual(style_gain.lora_main(3, gpu_ok=True, gpu=fake_gpu()), 0)
            result = json.loads((Path(tmp) / "results" / "style_gain_lora.json").read_text())
            samples = (Path(tmp) / "data" / "lora_samples.md").read_text()
        self.assertEqual(set(result), {"pairs", "results", "vs_production"})
        self.assertEqual(set(result["results"]), {"production", "lora", "lora_norerank", "open+lora"})
        for r in result["results"].values():
            self.assertEqual(set(r), {"form", "chrf", "n"})
        self.assertEqual(result["results"]["production"]["n"], 2)
        text = json.dumps(result, ensure_ascii=False)
        for row in ROWS:
            self.assertNotIn(row["real"], text)
            self.assertNotIn(row["draft"][:12].lower(), text)
        self.assertIn("**real**: го завтра вечером", samples)
        self.assertIn("lora: w", samples)
        self.assertIn("vs Spark Open", out.getvalue())

    def test_samples_are_private(self):
        self.assertEqual(style_gain.SAMPLES.relative_to(ROOT).parts[0], "data")
        self.assertIn("data/", (ROOT / ".gitignore").read_text().splitlines())


class PairedTest(unittest.TestCase):
    def test_better_worse_and_tie(self):
        real = ["го завтра вечером ок"] * 20
        same = ["привет как дела"] * 20
        close = ["го завтра вечером"] * 20
        better = style_gain.paired(same, close, real, rounds=50)
        self.assertGreater(better["chrf_ci"][0], 0)
        self.assertEqual(better["chrf_wins"], 20)
        self.assertTrue(style_gain.verdict(better).startswith("BETTER"))
        self.assertTrue(style_gain.verdict(style_gain.paired(close, same, real, rounds=50)).startswith("WORSE"))
        tie = style_gain.paired(same, same, real, rounds=50)
        self.assertEqual(tie["chrf_diff"], 0)
        self.assertTrue(style_gain.verdict(tie).startswith("NO CLEAR"))
        self.assertEqual(style_gain.paired(["", ""], ["a", "b"], ["a", "b"]), {"n": 0})


if __name__ == "__main__":
    unittest.main()
