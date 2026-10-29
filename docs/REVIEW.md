# Review, Oct 29 (agents from everything-claude-code)

The planner, architect, security-reviewer, code-reviewer and tdd-guide agents went over the repo read-only.
The plan for the rest of the week is in `docs/PLAN_final_week.md`; this file tracks what they found.

## Fixed
| Area | Finding | Fix |
|---|---|---|
| Security | One token for the app and vLLM; anyone with the app binary could call the model directly | vLLM has its own `GLIMMER_KEY` (secret `sayso-glimmer`), never shipped in the app |
| Security / cost | Any request can autoscale H100s | `max_containers=1` on `glimmer`, 2 on `api` |
| Security | No input limits | Screenshot ≤ 4 MB, text ≤ 2000, messages ≤ 4000, summary ≤ 400 chars; validated bodies (422, not 500) |
| Security | Template-token injection (`<\|eot\|>…`) through user text or Spark's summary | Control tokens stripped from every field; summary capped at 45 words; outputs cut at the first `<\|` |
| Security | Public `/docs`, non-ASCII header → 500 | Docs off; byte-wise `compare_digest` |
| Reliability | Cold GPU: requests hang, Modal answers 303 after 150 s | Generation routes answer 503 "warming up" at once and wake the GPU; client follows redirects |
| Reliability | Meta API 429/5xx/garbage → 500 | One retry, then 502; the image keeps its real content type (PNG screenshots) |
| Correctness | Empty audience → `random.choice([])` crash | Falls back to all turns |
| Correctness | Unknown situation strings grew the profile dict | Situation validated, lookups with `.get` |
| Benchmark | Failed tags counted as act/tone matches | Dropped from the comparison (numbers in PLAN_v4 updated) |
| Benchmark | Memorization checked against `pairs`, not the pairs the model trained on | `--pairs` passed through |
| Benchmark | Double BOS in bench prompts | Stripped like training and serving (old numbers kept; both systems had it) |
| Tests | Privacy test failed on laughter strings in model outputs | Lines need ≥ 8 distinct characters; model outputs (data/bench) are not stored input |

Measured warm latency after deploy: /reply from a summary 2.4 s, from pasted messages 6 s, from a screenshot 9.7 s, /compose 7 s.

## To do this week
- **Rotate `SAYSO_API_TOKEN`** before a build leaves the laptop (it is readable from the app binary).
- iOS `ReplyStore`: don't keep the other person's summary in `UserDefaults`; replies only, App Group with file protection.
- Keyboard: the server is the source of truth (`GET /latest`), the App Group is an optimisation (free signing may block it); show a "warming" state on 503.
- Tests (cheap, no GPU): `tests/test_writer.py` with a fake vLLM/Spark client (choice regrouping, `read()` fallbacks, `intents()`, `best()`), `tests/test_api.py` (401, 413, 422, image vs JSON), `tests/test_metrics.py`. `eval/smoke_api.py`: a CPU stage (401/422) and an opt-in `--gpu` stage.
- Check that vLLM does not log prompts (`modal app logs sayso` after a tagging run).
- `/reply` first option uses the user's most common act; the bench measured random draws from the profile (v4p). Benchmark the served policy before quoting numbers on the Proof screen.

## After the hackathon
- Serving reads a small `serving_profile.json` built offline, not raw training pairs (so "delete everything" is true); prompt constants in one shared module.
- Per-user adapters loaded at runtime from object storage, a warm pool, per-device tokens (Sign in with Apple / App Attest).
- Feedback queue → batched LoRA continuation → eval gate → promote, with rollback.
- Pin dependency versions and the vLLM image digest; pin the model revision.
- The installed `.claude/` config is generic JS boilerplate: keep its continuous-learning hook off in this repo (it would copy transcripts that touch private chats into `~/.claude/skills/learned/`).
