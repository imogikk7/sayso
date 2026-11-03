# SaySo — project context for Claude Code

SaySo is an AI that writes the way you'd say it: chat messages in the user's own voice (length, case, punctuation,
slang, how they react), adapted to who they're talking to, plus emails and essays in the user's own **formal voice**.
Delivered as an **iOS app + its own keyboard** (letter keys + ✨) that works in any messenger, a **Back Tap shortcut**
for replies from a screenshot, and an **in-app chat**.

Built solo for the **Meta Global AI Developer Hackathon** (indie track). This file is public: it must never contain
personal data, names of contacts, message text or keys. README.md is the judge-facing description; keep this file and
README consistent, and check claims against `serving/*.py` and `ios/` (the code is the source of truth).

_Last updated: 2026-11-02 (after the feature freeze)._

## Hackathon rules that constrain everything

- Building period: **Oct 27 – Nov 4, 2026**. Submission due **Nov 4, 9:00 PM ET** (= Nov 5, 07:00 Astana; aim to submit by ~22:00 Astana on Nov 4). Feature freeze Nov 2, record video Nov 3.
- **New work only:** everything in this repo is written during the hackathon. Do not import code from the author's earlier projects.
- **Repo must be public.** Private data and keys must never be committed (see Privacy).
- Must use Meta models (Meta Model API and/or Meta open weights). Judging: creativity, technical ambition, whether it works (indie track). Submission includes a ≤3-minute demo video.
- **Banned categories include "Personality Analyzers".** The style card and situation profile describe *how the user writes*, never personality traits, psychological labels or diagnoses.

## Current state (what the code does now)

The deployed server runs with **`SAYSO_GPU=off`** (Modal credits nearly gone, Fireworks uploads disabled service-wide,
the hackathon Baseten key serves only Muse Spark Open). So all live text comes from Muse Spark models guided by the
user's style; the personal LoRA is trained and benchmarked but not hosted.

### Models and roles (say it the same way everywhere: README, deck, video)
| Model | Where | Role |
|---|---|---|
| **Muse Spark Open** (`meta-models/muse-spark-open-1026`, open weights) | Baseten, OpenAI-compatible, `https://inference.baseten.co/v1`, `reasoning_effort: low` | **Writes** in the user's style: ✨, `/rewrite`, `/compose`, Chat Write/Rewrite answers and revisions, emails (`spark(..., writes=True)` with `SAYSO_WRITER=open`, the default). Fallback for every other Spark call. It always reasons; take only the final answer. |
| **Muse Spark 1.3** (`muse-spark-1.3`) | Meta Model API, `https://api.meta.ai/v1/chat/completions`, `reasoning_effort: low` | **Reads**: screenshots and pasted chats (audience, situation, 20–30-word neutral summary, three reply drafts — with the GPU off these drafts are the Back Tap / Reply answers), photos and screenshots of the user's own emails and essays, chat uploads when building a style (tagging, self-check judge). **Writes essays.** Turns feedback into rules. Rewrites a compose answer that just echoed the instruction. Fallback when Spark Open fails. |
| **Muse Voice Transcribe 1.0** (`muse-voice-transcribe-1.0`) | Meta Model API, `/v1/asr/transcribe` | 🎙 in Chat → text (`/transcribe`). Audio is not stored. |
| **Muse Glimmer 30B** + the user's LoRA (open weights) | vLLM on Modal (`SAYSO_GPU=modal`) or Baseten (`SAYSO_GPU=baseten`, `serving/baseten/`) | Trained and benchmarked, **not served now**. When on: rewrites chat-format drafts (`message`, `series`) in the user's voice, 5 candidates + rerank; without a chat the main style's v4 "thinks first" (`act · tone · gist` in `to=self`). Base Glimmer tagged situations/thoughts for the main style's offline training data. |

Fallback order (`Writer.spark`): reading calls try Muse Spark 1.3 twice, then Spark Open once; writing calls try Spark
Open first, then Spark 1.3 twice; then 502.

### Product surfaces (ios/)
- **Keyboard** (`SaySoKeyboard/`): its own RU/EN letter keys (Kazakh letters on long-press), a top strip with an
  audience chip (AI guess marked ✨), a format chip and ✨ (1–3 variants; a *series* comes as a stack sent part by part),
  and a panel with **Rewrite / Write / Replies** (latest Back Tap replies + system Paste button). Settings (app's
  Keyboard tab): opens with letters or panel, audiences, formats, variants, haptics, **"Capital letter at sentence
  start" (off by default)**, accent, and **"Learn from what I type" (off by default)**.
- **Back Tap**: Shortcut *Take Screenshot → SaySo App Intent* → `/reply` → system list of three replies (tap = copy).
- **Chat** (`ChatView.swift`): modes **Write / Rewrite / Reply / Email / Essay**, audience + format pickers, 🎙 voice
  input (`VoiceRecorder.swift` → `/transcribe`). Under each answer: Copy, 👍, 👎, ✏️. 👎 shows **quick reason chips**
  (chat: Too long, Too formal, Too casual, Not my words, Wrong meaning, Too rude; Email/Essay: Shorter, Longer, More
  personal, Simpler words, Less formal) or free text; a lasting preference becomes a rule ("✨ Learned: …"). Email
  returns a subject; Essay returns an outline, word count and up to 3 "make it stronger" questions.
- **Styles** (`StylesView`, `AddStyleView`, `FormalImportView`, `SourceGuides`, `StyleCardView`): an **Add** menu with
  **Messages (chats) / Emails / Essays & documents**, each with step-by-step source guides. Style card: per-audience
  profile, self-check, **Formal writing** (counts, sentence length, linking words, openings, sign-offs), **Learned from
  you** (keyboard messages, deletable) and **Learned from your corrections** (rules, deletable).
- **Setup** tab: keyboard + Full Access + Back Tap checklist, last screenshot replies.

Formats: `message`, `series` (2–4 short messages), `official`, `email`; Chat's Essay mode uses `essay`. `official`,
`email`, `essay` are written in the **formal voice**; the LoRA (when on) writes only `message` and `series`.

### Formal voice (`serving/documents.py`, `styles.add_documents`)
The user's own emails and essays (.txt/.md/.docx/.pdf, Google Takeout .mbox Sent only, photos/screenshots read by Muse
Spark 1.3, pasted text) → paragraphs + a formal profile. Quoted earlier messages and the signature block after the
sign-off are cut; section labels of old assignments ("Thesis:", "Argument 2:") are cut; links, emails, phones, card
numbers removed; when Spark reads a photo or screenshot, names of other people and companies become `[Name]`. Two kinds
with different rules in the prompt (`Context.formal_block`): **essays teach voice only** (never structure or topic),
**emails teach manner only** (greeting, sign-off, directness; never content).

### Learning from use
- `/learn` (keyboard, opt-in): messages typed **and** sent with SaySo's letter keys; pasted text (more than one
  character arriving at once) is never learned; secure/email/URL/number/one-time-code/search fields are skipped. An
  edited ✨ suggestion is sent with the user's version and may become a rule. Scrubbed of links/emails/phones/cards.
- `/feedback` (Chat): 👍 keeps the answer as an example; ✏️ keeps the user's version and may teach a rule.
- 👎 in Chat goes through `/chat` with `history[].feedback`: the answer is revised and a lasting preference becomes a
  rule (`preferences.json`, max 12).
- Chat thread: requests carry `previous` (≤ 3 `{request, answer}`); a refinement ("на русском", "shorter") revises the
  last answer (`serving/memory.py`). Every answer passes `serving/guards.py`; a long `message` may come as a series
  when the user writes like that (`serving/series.py`); essays are fitted to the asked length ±10 %
  (`serving/length.py`). Responses with `alternatives` also return `alternative_parts`.

## Architecture

```
iOS (SwiftUI app + Keyboard Extension + App Intents)
   │ HTTPS + one bearer token (TokenGate checks it before any body is read)
   ▼
Modal app "sayso" (serving/modal_app.py)
   api  — FastAPI on CPU, max 1 container (one writer to the volume): routes below, logic in serving/writer.py
   build_style — background function: uploads → style (serving/build_style.py)
   glimmer — vLLM, Muse Glimmer 30B + LoRAs v2/v4 on an H100 (only used when SAYSO_GPU=modal)
   sayso-data volume — the user's data (styles/, pairs, profiles, adapters); never in the repo
External: Muse Spark Open (Baseten) · Muse Spark 1.3 + Muse Voice Transcribe (Meta Model API)
```

Routes: `/rewrite`, `/compose`, `/reply`, `/chat`, `/transcribe`, `/learn`, `/feedback`, `/styles` (GET/POST),
`/styles/{id}` (GET/PATCH/DELETE), `/styles/{id}/documents`, `/latest`, `/warmup`. Request/response fields: README
"API reference". Env flags at deploy: `SAYSO_GPU` (off | modal | baseten), `SAYSO_WRITER` (open | meta),
`SAYSO_TRAIN` (off | on: new styles train their own LoRA, ≥150 turns).

Modal secrets: `sayso` (`SAYSO_API_TOKEN`), `sayso-glimmer` (`GLIMMER_KEY`, vLLM's own key, never in the app),
`sayso-meta` (`META_API_KEY`), `sayso-extra` (`BASETEN_API_KEY`), optional `sayso-baseten` (LoRA on Baseten).

Audiences: `partner`, `friends`, `family`, `elder_informal`. Situations (`pipeline/situations.py`): request,
invitation, good_news, sadness, conflict, joke, thanks, apology, logistics, refusal, affection, sharing, reaction,
greeting, other. Acts and tones describe
the user's moves (agree, refuse, joke, ask_back, …). Style is conditioned on **audience + situation**, never per contact.

## Data and the offline pipeline (main style)

- Source: Telegram Desktop **HTML** per-chat exports (`ChatExport_<name>/messages.html, messages2.html, …`; sort numerically). Each message is `div.message.default`; continuation messages have class `joined` and no `from_name` — they belong to the previous sender. Text is in `div.text`. Service messages are `div.message.service`. The user's display name in exports is stored in `data/config.json` as `self_name` (gitignored) — never hardcode it.
- Other parsers (`pipeline/parse_whatsapp.py`, `parse_instagram.py`, `sources.py`) output the same turn format; they
  are used by `build_style.py` for uploads from the app. Raw uploads are parsed in memory and never written.
- **Unit = turn:** consecutive own messages merged with newlines. **Cleaning:** strip URLs, phone numbers, emails,
  card-like numbers, media placeholders, forwards, duplicates. **Balance:** no chat above 35% of the set.
  **Split:** last weeks per chat held out for test.
- Tagging: for the **main style**, base Glimmer on our own Modal endpoint tagged situation, a neutral summary and the
  thought (act · tone · gist) (`pipeline/situations.py`, `add_thoughts.py`), so other people's messages never left our
  hosted model offline. For **styles built in the app**, Muse Spark 1.3 does that tagging (`build_style.py`), and live
  `/reply` reading also uses Muse Spark 1.3. Only `{turn_id, situation, summary, …}` of the user's own turns is saved.
- Pairs (`pipeline/build_pairs.py`): `rewrite` (Spark Open neutral draft → real message), `compose` (Spark Open
  instruction → real message), `reply` (situation + neutral summary → real reply). QLoRA with Unsloth on a Modal H100
  (`training/modal_train.py`, r=16, lr 2e-4, 2 epochs, loss on the response). v1, v2, v3 (SimPO, worse, dropped), **v4**
  (thought first) is what the server loads when the GPU is on. `training/fireworks_sft.py` and `serving/fireworks.py`
  exist but Fireworks uploads are disabled; they are not part of the running system.

## Evaluation (committed numbers: `eval/results/*.json`, aggregated only)

- `bench_2026-10-28.json`: base Glimmer vs few-shot vs LoRA v1 on 499 held-out pairs (fingerprint, chrF, memorized).
- `bench_v4.json`: v2 vs v4 (+ rerank / profile-drawn act and tone), including act/tone match.
- `style_gain.json` / `style_gain_open.json` (`eval/style_gain.py`): 40 held-out rewrites, Muse Spark 1.3 with more of
  the style each step, and Muse Spark Open with the production prompt (form 0.93 / chrF 50.4).
- **Blind test v2** (`eval/blind_test.py`): per question a situation (neutral summary, retold in Russian, plus who it
  is) and three replies — the real one, SaySo's (`/chat` reply), a generic Muse Spark 1.3 answer; pairs where the real
  reply doesn't fit or contains names are skipped. `score` → `eval/results/blind_test.json`. **Not run yet (TODO);
  never invent its numbers.**
- Any number in README, deck or video must match those files exactly.

## Demo language

The user writes in Russian (with Kazakh/English mixed in); judges are likely English-speaking. So: English narration and captions; an English translation under each on-screen message (translated by Muse Spark); side-by-side "generic AI vs SaySo" with fingerprint features highlighted in color (length, end punctuation, lowercase, emoticons, EN/KZ insertions) so the difference is visible without reading Russian; benchmark numbers and blind-test results are language-independent. Do not invent an English profile without English data.

## Privacy rules (non-negotiable)

- Train and prompt only on the user's **own** writing. Other people's messages may be read transiently to understand
  the situation, then discarded; never stored in datasets, styles or pairs, never shown in the demo. (Live reading of
  screenshots and uploads sends them to Muse Spark 1.3 in memory; the offline pipeline used our own hosted Glimmer.)
- `data/`, exports, adapters, generated iOS secrets and `.env` are gitignored. Before every commit, check `git status` contains no data files.
- Screenshots, photos of documents and voice notes are processed in memory and not stored. The `/latest` cache holds
  the user's suggested replies and the situation tag only, never the summary of the other person's messages.
- Formal writing: only the user's own text is kept (quoted messages, signatures cut; other names → `[Name]` when read
  from images). An email pasted to answer is used once and not stored.
- Keyboard learning is opt-in and never learns pasted text or sensitive fields.
- After training, raw exports can be deleted; the user keeps the adapter file and the profile.
- Never market SaySo as "undetectable AI". Frame: authenticity, your own voice, human-in-the-loop.

## Repo layout

```
serving/    modal_app.py (Modal: vLLM + FastAPI + build function), writer.py, styles.py, build_style.py,
            documents.py, memory.py (chat thread: `previous`), guards.py (no placeholders / unasked
            self-introductions), series.py (auto-series), length.py (essay length), postprocess.py,
            baseten/ (Truss for SAYSO_GPU=baseten), fireworks.py (unused: uploads disabled)
pipeline/   parse_telegram.py, parse_whatsapp.py, parse_instagram.py, sources.py, situations.py, add_thoughts.py,
            build_pairs.py, style_profile.py, style_stats.py (reranker), lexicon.py
training/   modal_train.py (Unsloth QLoRA), build_prefs.py + modal_prefs.py (SimPO, v3), fireworks_sft.py
eval/       bench_generate.py, metrics.py, style_gain.py, smoke_api.py, blind_test.py + blind_template.html,
            results/ (aggregated metrics only)
tests/      test_api_auth.py, test_blind_test.py, test_parsers.py, test_privacy.py, test_styles.py,
            test_writer_fakes.py, test_memory.py, test_guards.py, test_series.py, test_length.py,
            test_thread_api.py, fixtures/ (made-up data only)
ios/        SaySoApp/, SaySoKeyboard/, Shared/ (API.swift, Settings.swift, Generated/), scripts/gen_secrets.sh
docs/       SUBMISSION.md, VIDEO_SCRIPT.md, DESIGN_BRIEF.md, deck/, video/, reviews/, plans and earlier reviews
```

## How to run (details in README)

- Deploy: `SAYSO_GPU=off .venv/bin/modal deploy serving/modal_app.py`
- Smoke: `.venv/bin/python eval/smoke_api.py --spark --show` (made-up inputs only)
- Tests: `python3 -m unittest discover -s tests` (no network; tests needing private exports skip)
- Blind test: `python3 eval/blind_test.py build --n 15`, then `python3 eval/blind_test.py score <codes…>`
- Style gain: `.venv/bin/python eval/style_gain.py --limit 40 [--writer open]`

## Conventions

- Python 3.11+; project venv in `.venv` (Modal CLI lives there). Pipeline scripts use the standard library where possible. Read keys from `.env` only.
- Small, frequent commits with clear messages (judges must see what was built during the hackathon).
- Ask before any change that could expose private data.
