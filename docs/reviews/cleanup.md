# Cleanup review (dead code, duplicates, stale docs, naming)

_2026-11-02, after the feature freeze. Review only: no code was changed._

How it was checked: `ruff check --select F401,F811,F841,E401` and `vulture` (installed into `.venv`) over
`pipeline/ serving/ training/ eval/ tests/`; a reference count of every top-level Python symbol across the repo; for
Swift, every declared type, function and property grepped across `ios/` (whole repo and per file for `private`
members); `git log` for when each suspect file was last touched; `python -m unittest discover -s tests` as a baseline
(144 tests, OK, 3 expected failures). `data/` and `.env` were not read.

Line numbers are for the working tree at the time of review. `CLAUDE.md` and `README.md` had uncommitted edits by then,
so their line numbers can move.

Verdicts:
- **safe to delete now**: nothing references it and removing it changes no behaviour. It is still a commit during the freeze, so it is your call.
- **keep**: still used, or worth keeping (the reason is given).
- **after the hackathon**: a real cleanup, but it touches live paths or the docs that judges read.

---

## 1. Dead or unused code

| # | What | Where | Confidence | Evidence | Verdict |
|---|---|---|---|---|---|
| 1.1 | Fireworks serving client (whole file) | `serving/fireworks.py:1-113` | High | Only importer is `training/fireworks_sft.py:21`. No route, test or script calls it. Last touched Oct 30. Fireworks uploads are disabled service-wide (CLAUDE.md:24, README.md:22). Also hardcodes the account id `ACCOUNT = "imogikk7"` (`:22`); this is not a secret, since it matches the Modal workspace. | **safe to delete now**, together with 1.2 and their mentions: README.md:363, README.md:368 (`fireworks_sft.py`), CLAUDE.md:118-119, CLAUDE.md:155, CLAUDE.md:158, `.env.example:17-18`. The git history and README's "what didn't work" keep the story. |
| 1.2 | Fireworks SFT script (whole file) | `training/fireworks_sft.py:1-85` | High | Nothing imports it. Its commit is titled "blocked: uploads disabled on the account" (Oct 30). Unused `import time` at `:14`. Docstring `:1` says "free there until Nov 30". | **safe to delete now** (with 1.1) |
| 1.3 | `retrieval` switch in the writer (`"random"` is never passed) | `serving/writer.py:416` (param), `:424` (attr + comment "or random"), `:572` (`self.retrieval == "local" and`); only caller passing it is `eval/style_gain.py:58` (`retrieval="local"`) | High | `git grep retrieval` finds no `"random"` value anywhere. `modal_app.py:199-202` never passes it, so the default `"local"` always applies. The random fallback without a query (`writer.py:576`) stays. | **safe to delete now**: drop the param, the attr and the `self.retrieval == "local" and` condition, and remove `retrieval="local"` at `eval/style_gain.py:58`. |
| 1.4 | Embeddings leftovers | none in code | High | Fireworks embeddings code is already gone. Only results text is left: README.md:248-250, `eval/style_gain.py:8`, `docs/SUBMISSION.md:88`. | **keep**: it reports a measured result ("picking by meaning didn't help"). |
| 1.5 | Baseten Truss path for the LoRA (`SAYSO_GPU=baseten`) | `serving/baseten/config.yaml:1-29`; writer branches `serving/writer.py:417-418, 422, 483, 486-489, 495-497, 504, 514-515`; `serving/modal_app.py:131, 198-201, 525` | Medium-high (never exercised) | The hackathon Baseten key serves only Muse Spark Open, so this path never ran for the LoRA. No test covers it: all tests use `gpu="off"` (`tests/test_writer_fakes.py:115`, `tests/test_styles.py:108`). README.md:210 and CLAUDE.md:34 and :92 advertise it as a switch. | **after the hackathon**: removing it edits live `writer.py`/`modal_app.py` and judge-facing docs. Until then, README could say "written, not deployed". |
| 1.6 | `SaySoAPI.restyle(_:for:)` | `ios/Shared/API.swift:241-250` | High | No caller in `ios/` (grep `restyle(` hits only the definition and the comment at `:22`). | **safe to delete now**. `ReplyIdea` (`:23-26`) and `ReplyResponse.options` (`:31`) then only decode a server field nobody reads: **after the hackathon** (harmless). |
| 1.7 | `SaySoAPI.warmup()` | `ios/Shared/API.swift:272-277` | High | No caller in `ios/`. The server route `/warmup` is still used by `eval/blind_test.py` (see `tests/test_blind_test.py:74`), so keep the route. | **safe to delete now** (the Swift function only) |
| 1.8 | `ReplyStore` / `RepliesView` | `ios/SaySoApp/ReplyStore.swift:4-18`, `ios/SaySoApp/RepliesView.swift:5-24` | n/a | **Used**: written by `Intents.swift:63`, read by `SetupView.swift:11` and `:53`, shown at `SetupView.swift:47`. Left from the Oct 30 spike, but wired into Setup ("Last screenshot replies"). | **keep** |
| 1.9 | Old spike view | none | High | No `SpikeView` exists. The spike's `RepliesSnippetView.swift` was already deleted (`git log --diff-filter=D`; spike commit `6258ae6`). Only historical mentions remain in `docs/PLAN_final_week.md:14, 41, 67`. | nothing to delete. See 3.12 for the plan docs. |
| 1.10 | Decoded but never read reply fields | `ios/Shared/API.swift:16-19` (`tone`, `thought`, `styled`) | High | No Swift code reads them; they are part of the server's response contract. | **keep** (useful for debugging and the demo; costs nothing) |
| 1.11 | Unused imports | `pipeline/situations.py:26` (`Path`), `training/build_prefs.py:13` (`re`), `training/fireworks_sft.py:14` (`time`) | High (ruff F401) | ruff | **safe to delete now** (the third goes with 1.2) |
| 1.12 | Unused local variable | `eval/smoke_api.py:143` (`out = self.timed(...)`) | High (ruff F841) | `self.timed` already records pass/fail. Drop the `out =`, keep the call. | **safe to delete now** |
| 1.13 | Redundant re-imports in Modal functions | `serving/modal_app.py:55` (`import os`; already imported at `:14`), `serving/modal_app.py:359` (`import asyncio as aio`; `asyncio` imported at `:153`) | High | Same module twice under two names. | **safe to delete now** (trivial; use `asyncio` at `:378` and `:383`) |
| 1.14 | Unused constant | `eval/blind_test.py:49` (`CODE_PREFIX = "SS2-"`) | High | Only `CODE_PREFIXES` (`:50`) is used. The page hardcodes `const PREFIX = "SS2-"` at `eval/blind_template.html:149`. | **after the hackathon**: inject `CODE_PREFIX` into the template instead of deleting it (see 2.9) |
| 1.15 | Modal check-only functions | `training/modal_prefs.py:28` (`check_imports`), `training/modal_train.py:126` (`check_render`) | False positive | Run by hand with `modal run file::fn` (CPU checks before paying for a GPU). | **keep** |
| 1.16 | FastAPI route handlers flagged by vulture | `serving/modal_app.py:206, 454, 459, 464, 480, 505, 516` | False positive | Registered by decorators. | **keep** |
| 1.17 | v3 SimPO training (dropped model) | `training/build_prefs.py`, `training/modal_prefs.py` | n/a | v3 is not served, but `eval/results/bench_v3_2026-10-28.json` and README report it. | **keep** (evidence for a reported result) |
| 1.18 | Unused `.env.example` keys | `.env.example:10` (`META_BASE_URL`), `:11` (`META_MODEL`), `:17-18` (`FIREWORKS_API_KEY`) | High | `git grep` finds no reader. | **safe to delete now** (no code reads them) |

## 2. Duplicated logic worth merging (all after the hackathon unless noted)

| # | What | Where | Suggestion |
|---|---|---|---|
| 2.1 | Turning an edit into a rule (Spark + `LEARN_SYSTEM` + `add_preference`) | `serving/writer.py:791-800` (`learn`) and `:838-843` (`feedback`) | One helper. They also behave differently: `learn` catches `Unavailable`, but `feedback` doesn't. So a Spark failure in `/feedback` returns 502 after `add_feedback` already ran (`:835`) and skips `styles.commit()` (`:844`). Worth fixing with the merge. |
| 2.2 | Meta Spark JSON call, written 4 ways | `serving/writer.py:536-560` (`Writer.spark`, async), `serving/build_style.py:92-113` (`Spark`, sync), `eval/blind_test.py:55-56` and its request code, `pipeline/build_pairs.py:136` (`call_spark`, Baseten) | One small client in `serving/` (URL, model id, `reasoning_effort`, JSON extraction). Model id `"muse-spark-1.3"` is a literal in `writer.py:539`, `build_style.py:104`, `blind_test.py:56`. |
| 2.3 | `.env` parsing, 6 copies | `pipeline/situations.py:85` (`load_env`), `eval/blind_test.py:78`, `eval/smoke_api.py:25`, `eval/style_gain.py:55`, `serving/fireworks.py:35`; `pipeline/build_pairs.py:34` reuses `situations.load_env` | Reuse `situations.load_env` everywhere, as `build_pairs` does. |
| 2.4 | certifi / SSL fallback block, 5 copies | `pipeline/situations.py:32-34`, `eval/blind_test.py:94-97`, `eval/smoke_api.py:18-20`, `eval/style_gain.py:39-41`, `serving/fireworks.py:27-29` | One helper next to `load_env`. |
| 2.5 | `REASONING = "Reasoning strength: low."`, 4 copies + literals | `serving/writer.py:45`, `eval/bench_generate.py:25`, `training/modal_train.py:16`, `training/fireworks_sft.py:23`; literal in `pipeline/situations.py:62, 150, 170` (stripped again by `writer.py:163`) | One constant, since training and serving must render the same template. |
| 2.6 | Audience list | `serving/writer.py:49`, `serving/build_style.py:40`; Swift `Audience` (`ios/Shared/API.swift:49-61`) and `ReplyAudience` (`ios/SaySoApp/Intents.swift:6-24`) | `build_style` can import `writer.AUDIENCES` (or move it to `styles.py`). |
| 2.7 | Adapters loaded at vLLM start | `serving/modal_app.py:39` (`ADAPTERS = ["v2", "v4"]`) and `serving/writer.py:428` (`self.loaded = {"v2", "v4"}`) | Pass `ADAPTERS` into `Writer`. |
| 2.8 | Repeated prompt strings | `"Rewrite this draft the way the user would write it"` at `serving/writer.py:580`, `:697`, `eval/style_gain.py:65`; the "write plainly and directly, like a real person, not like an AI" fallback at `writer.py:702` and `:735-736` | Module constants. `style_gain` must keep matching production, which is one more reason. |
| 2.9 | Blind-test code prefix | `eval/blind_test.py:49-50` and `eval/blind_template.html:149` | Fill the template's `PREFIX` from `CODE_PREFIX` when building. |
| 2.10 | Swift multipart body builder, 3 copies | `ios/Shared/API.swift:301-319` (`addDocuments`), `:335-344` (`transcribe`), `:368-383` (`createStyle`; also uses `.data(using: .utf8)!` where the others use `Data(...utf8)`) | One `multipart(fields:files:)` helper. |
| 2.11 | Keyboard: reading the whole field, 3 copies | `ios/SaySoKeyboard/PanelModel.swift:88`, `:102`, `:214` | A `fieldText` computed property. |
| 2.12 | Keyboard: `ReplyOption` → `PanelOption`, 2 copies | `ios/SaySoKeyboard/PanelModel.swift:302`, `:317` | `PanelOption(reply:)` initializer. |
| 2.13 | Input validation in two layers | `serving/modal_app.py:210-217` (`audience_of`/`situation_of`/`format_of`) and `serving/writer.py:270-273` (`audiences_of`) plus checks inside `read()` | Fine as is; merge only if the writer becomes a library. |

## 3. Stale comments and docstrings

| # | Where | What is stale | Verdict |
|---|---|---|---|
| 3.1 | `serving/writer.py:6-7` (module docstring) | Says rewrite/compose are written by "the style's LoRA". With the deployed `SAYSO_GPU=off`, **Muse Spark Open** writes them in the style: TF-IDF examples plus 4 variants (`styled()` at `:578-598`, `writes=True`). The docstring mentions the Spark path only for `reply` (`:11-12`). | **fix now** (docstring only) |
| 3.2 | `serving/writer.py:17-18` | Formats list omits `essay` (`:69`). Nothing about email/essay in the **formal voice** (`formal_block`, `documents.py`), **voice** (`transcribe`, `:817`), `learn`/`feedback`, or `read_page`. | **fix now** (docstring only) |
| 3.3 | `serving/writer.py:120` | Trailing comment "the user's casual examples would pull these back to lowercase chat" sits on `VARIANTS`, where it explains nothing. It is left over from an earlier formal/variants rule. | **fix now** (move it or delete it) |
| 3.4 | `serving/writer.py:417-418` (`Writer.__init__` docstring) | Covers `gpu` only. `writer=` (who writes first), `fallback_key` (actually Spark Open's key) and `retrieval` are undocumented. | **fix now** with 1.3 |
| 3.5 | `serving/modal_app.py:3-5` (module docstring) | `api` lists only `/rewrite /compose /reply`. The `build_style` function isn't mentioned. | **fix now** |
| 3.6 | `serving/modal_app.py:8-11` | The secrets list misses `sayso-extra` (`BASETEN_API_KEY`, used at `:130`) and `sayso-baseten` (`:131`). The volume list misses `styles/`. | **fix now** |
| 3.7 | `serving/modal_app.py:21` | `GPU` comment names "modal" and "off" only; `"baseten"` is also accepted (`:131`, `:198`). | **fix now** |
| 3.8 | `serving/modal_app.py:136-152` (`api` docstring) | `/chat` lists modes `write \| rewrite \| reply` only (also email and essay, with `question`/`words`/`reply_to`). `/learn` and `POST /styles/{id}/documents` are missing. `:150`: "the app calls it from a button" is false: no Swift code calls `/warmup` (see 1.7); only `eval/blind_test.py` does. | **fix now** |
| 3.9 | `ios/Shared/API.swift:22` | "sent back to restyle for another audience": nothing does that any more (1.6). | **fix now** with 1.6 |
| 3.10 | `ios/Shared/API.swift:220` + `serving/writer.py:457` | With `SAYSO_GPU=off`, `ensure_warm` returns 503 "the user's model is offline" (reachable at `writer.py:631`, `/reply` with a summary and no options). The app maps every 503 to "Your model is waking up (about 2 minutes)" (`API.swift:429`), which is wrong in GPU-off mode. | **after the hackathon** (behaviour/text change in the app) |
| 3.11 | `CLAUDE.md` (committed `HEAD`) | The committed version predates Spark Open writing, voice, formal writing and the real keyboard. It describes Fireworks as plan A, a Share Extension, an "interactive snippet" over the messenger, a 5-step onboarding, Proof and privacy screens, `update_lora.py` + DPO, `parse_x.py`/`parse_forwarded.py`, `eval/BLIND_TEST.md`, a `/profile` endpoint, and a Kazakh long-press list that doesn't match `ios/SaySoKeyboard/Layouts.swift:34-36` (code: у→ұ, ю→ү, plus е→ё, ь→ъ). The **working-tree rewrite** (uncommitted, "Last updated: 2026-11-02") fixes all of these; I checked it against the code (models and fallback order `writer.py:536-560`, routes, situations `pipeline/situations.py:39-53`, `MIN_LORA_TURNS = 150` at `build_style.py:48`, Setup tab, keyboard settings). Remaining nit: the broken line wrap at `CLAUDE.md:100-101`. | **fix now**: commit the rewrite. Once 1.1 and 1.2 are done, drop the Fireworks lines at `CLAUDE.md:118-119, 155, 158`. |
| 3.12 | `docs/PLAN_final_week.md`, `docs/PLAN_v4_thinking.md`, `docs/REVIEW.md` | Plans from before the rewrite. They mention `/profile`, `/learned`, a `compare` flag, `ReplyStore` in `Shared/` (`PLAN_final_week.md:31, 35`) and the spike. | **keep** (history). After the hackathon: move to `docs/archive/` or add a one-line "historical plan" header. |
| 3.13 | `README.md:369-370` (repo map) | `eval/` omits `blind_test.py`/`blind_template.html`. `tests/` omits `test_api_auth.py`, `test_blind_test.py`, `test_writer_fakes.py` (CLAUDE.md:159-162 already has them). | **fix now** (docs) |
| 3.14 | `.env.example` | Missing `SAYSO_API_URL`, which README.md:"How to run", `ios/scripts/gen_secrets.sh:7`, `eval/blind_test.py:78` and `eval/smoke_api.py:33` require. Missing `SAYSO_GLIMMER_URL`, which `eval/smoke_api.py:33` reads unconditionally (KeyError without it). Stale keys are covered in 1.18. Line 8: "style card" no longer uses Spark the way that comment describes. | **fix now** |
| 3.15 | `training/fireworks_sft.py:1`, `.env.example:17` | "SFT free until Nov 30", "LoRA deployments": obsolete. | goes with 1.1 and 1.2 |

## 4. Inconsistent naming (after the hackathon: renames touch the API contract or the app)

| # | Names | Where |
|---|---|---|
| 4.1 | One task, three names: **compose** (route `/compose`, `writer.compose`), **write** (Chat mode `write`, `ChatMode.write`), **Write** tab with raw value of `compose` | `serving/modal_app.py:291`, `serving/writer.py:608, 696, 728`; `ios/Shared/API.swift:187`; `ios/SaySoKeyboard/PanelModel.swift:6` (`case compose = "Write"`) |
| 4.2 | **intent** vs **act** for the same thing | `ReplyOption.intent` (`ios/Shared/API.swift:14`) and `"intent": option["act"]` (`serving/writer.py:625`) vs `ReplyIdea.act` (`API.swift:24`) and `options[].act` |
| 4.3 | `elder_informal`: shown as "Elders" (`ios/Shared/API.swift:58`) and as "Elders / formal" with case `.elders` (`ios/SaySoApp/Intents.swift:7, 12, 21`). Email and essay answers report audience `elder_informal` even though they are formal (`serving/writer.py:751, 776`). | as listed |
| 4.4 | **preferences** (storage, `remove_preference`, `styles.preferences`) vs **rules** (`Context.rules()` at `writer.py:330`, `"rule"` in `LEARN_SYSTEM`/`REVISE_SYSTEM`, UI "Learned from your corrections") | `serving/styles.py:164-185`, `serving/writer.py:201, 206, 330`, `serving/modal_app.py:270` |
| 4.5 | `FALLBACK_URL` / `FALLBACK_MODEL` / `fallback_key` name Muse Spark Open, which is the **first** writer with the deployed `SAYSO_WRITER=open` | `serving/writer.py:139-141, 423, 541`; `serving/modal_app.py:201` |
| 4.6 | `Writer(..., writer="meta")`: a parameter called `writer` on class `Writer`, and its default (`"meta"`) differs from the deployed default (`"open"`, `modal_app.py:202`) and from `eval/style_gain.py:36` (`"meta"`) | `serving/writer.py:416, 425` |
| 4.7 | `gpu` takes hosting names (`"modal"`, `"baseten"`, `"off"`); the env var `SAYSO_GPU` does the same | `serving/writer.py:415-421`, `serving/modal_app.py:22` |
| 4.8 | Env names: `BASETEN_MODEL` (Spark Open model id, `.env.example:6`, `pipeline/build_pairs.py:138`) vs `BASETEN_MODEL_ID` (the Truss deployment, `serving/modal_app.py:201`) | as listed |
| 4.9 | `read_system`: a module function and a `Context` attribute with the same name | `serving/writer.py:146` and `:327` |
| 4.10 | `options` means Spark's drafts `{act, draft}` on the server but suggestion cards (`PanelOption`) in the keyboard | `serving/writer.py:652`, `ios/SaySoKeyboard/PanelModel.swift:16, 36` |

---

## Safe to delete or fix now (summary)

1. Delete `serving/fireworks.py` and `training/fireworks_sft.py`, plus their mentions: README.md:363 and :368, CLAUDE.md:118-119, :155 and :158, `.env.example:17-18`.
2. Drop the unused `retrieval` switch: `serving/writer.py:416`, `:424`, `:572` and `eval/style_gain.py:58`.
3. Delete the unused Swift API functions: `ios/Shared/API.swift:241-250` (`restyle`) and `:272-277` (`warmup`), and fix the comment at `:22`.
4. Remove unused imports and variables: `pipeline/situations.py:26`, `training/build_prefs.py:13`, `eval/smoke_api.py:143`, `serving/modal_app.py:55` and `:359`.
5. `.env.example`: remove `:10-11` and `:17-18`; add `SAYSO_API_URL` and `SAYSO_GLIMMER_URL`.
6. Docstrings and comments (no behaviour change): `serving/writer.py:6-7`, `:17-18`, `:120`, `:417-418`; `serving/modal_app.py:3-5`, `:8-11`, `:21`, `:136-152`; `README.md:369-370`. Commit the working-tree `CLAUDE.md` rewrite.

After each batch: `.venv/bin/python -m unittest discover -s tests` (currently 144 tests, OK), and build the iOS targets after step 3.
