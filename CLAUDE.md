# SaySo — project context for Claude Code

SaySo is an AI that writes the way you'd say it. It fine-tunes a LoRA adapter on Meta's open-weights **Muse Glimmer 30B** using the user's own messages, so drafts, replies and short instructions come out in the user's real voice, adapted to who they're talking to. Delivered as an **iOS app + custom keyboard panel** that works in any messenger.

Built solo for the **Meta Global AI Developer Hackathon** (indie track). This file is public: it must never contain personal data, names of contacts, message text or keys.

## Hackathon rules that constrain everything

- Building period: **Oct 27 – Nov 4, 2026**. Submission due **Nov 4, 9:00 PM ET** (= Nov 5, 07:00 Astana; aim to submit by ~22:00 Astana on Nov 4). Feature freeze Nov 2, record video Nov 3.
- **New work only:** everything in this repo is written during the hackathon. Do not import code from the author's earlier projects.
- **Repo must be public.** Private data and keys must never be committed (see Privacy).
- Must use Meta models (Meta Model API and/or Meta open weights). Judging: creativity, technical ambition, whether it works (indie track). Submission includes a ≤3-minute demo video.
- **Banned categories include "Personality Analyzers".** The style card and situation profile describe *how the user writes*, never personality traits, psychological labels or diagnoses.

## Product

1. **Keyboard panel** (iOS Keyboard Extension, no letter keys): reads the draft before the cursor, user picks an audience chip, taps **Rewrite** (draft → my style) or **Compose** (short instruction → my message), sees a preview, taps **Insert** (replaces the draft). User always sends manually.
2. **Reply from screenshot.** iOS keyboards cannot capture the screen, so the main flow is: **Back Tap** (double-tap the back of the iPhone) runs an iOS **Shortcut** that takes a screenshot and POSTs it to `/reply` → Muse Spark (vision) extracts the conversation and the situation → the personal model writes 2–3 replies in the user's style → server stores them for this user → when the SaySo keyboard opens, it fetches the latest replies and shows them as tap-to-insert options. Fallback: Share Extension (screenshot → Share → SaySo) and in-app picker. Verify early: Shortcut screenshot + HTTP upload, and keyboard fetching replies on open.
3. **Container app (SwiftUI):** onboarding (enable keyboard + Full Access), style card per audience and per situation, "Proof" screen with benchmark results, sandbox, privacy screen with "delete everything".

Audiences come from the data, not a fixed list: `partner`, `friends`, `family`, `elder_informal` (respectful but informal), optionally `formal` (email). The mapping chat → audience lives in `data/audiences.json` (gitignored).

Situations (8–10, tag for training + section of the style card): request/question, invitation/plans, good news, sadness/complaint, conflict/complaint about me, joke/meme, thanks, apology, logistics (where/when), refusal.

## Architecture

```
iOS (SwiftUI app + Keyboard Extension + Share Extension)
   │ HTTPS + bearer token
   ▼
Modal: FastAPI endpoints  /rewrite  /compose  /reply  /profile
   └─ vLLM: Muse Glimmer 30B + LoRA (audience + situation tags in prompt,
             plus 3–5 retrieved own examples from the same audience)
   └─ Meta Model API: Muse Spark (vision) for screenshot parsing
Offline pipeline (Python): parse exports → own messages only → audience + situation tags
   → Muse Spark Open (Baseten) builds pairs → QLoRA on Modal → eval → JSON for the Proof screen
```

### Models and roles (name them in the video)
| Model | Where | Role |
|---|---|---|
| Muse Glimmer 30B + LoRA | Modal (vLLM) | Core personal model |
| Muse Spark Open (`meta-models/muse-spark-open-1026`) | Baseten, OpenAI-compatible, `https://inference.baseten.co/v1` | Batch data synthesis: neutralize real messages, generate instructions; open-weights baseline. Always reasons — take only the final answer |
| Muse Spark 1.3 | Meta Model API (OpenAI-compatible; verify base URL/model id in docs) | Screenshot understanding, style card text, frontier few-shot baseline. Standard tier only |
| Muse Code | dev tool | Helps write Swift |

Compute decision rule (resolve on Oct 28–29):
- **Training plan A: Fireworks SFT/LoRA on Muse Glimmer 30B** (supported, priced per training token). If the adapter can be downloaded → serve it on Modal. If not → serve on a Fireworks on-demand deployment only during testing and filming (LoRA is not available on Fireworks serverless).
- **Training plan B: Modal + Unsloth QLoRA** (Glimmer needs ~24 GB VRAM; use A100/H100/L40S).
- **Serving: Modal + vLLM with LoRA** (vLLM supports Glimmer) + FastAPI in the same Modal app. Keep the container warm only while testing/filming.
- **Fallback:** if Glimmer fails to train/serve or credits don't arrive, switch base to Llama 3.1 8B (QLoRA via MLX on a 16 GB Mac, or Unsloth on Modal). Pipeline code must not depend on the base model.
- Situation tagging of incoming messages runs on our own hosted base Glimmer, not on third-party APIs.

Latency targets: `/rewrite` and `/compose` < 3 s warm; `/reply` (screenshot) ~6–8 s, async.

## Data

- Source: Telegram Desktop **HTML** per-chat exports (`ChatExport_<name>/messages.html, messages2.html, …`; sort numerically). Each message is `div.message.default`; continuation messages have class `joined` and no `from_name` — they belong to the previous sender. Text is in `div.text`. Service messages are `div.message.service`. The user's display name in exports is stored in `data/config.json` as `self_name` (gitignored) — never hardcode it.
- Volume: roughly 43k of the user's own text messages across 5 chats, heavily skewed to one chat (~58%). **Cap per-chat share** when building training sets so audiences stay balanced.
- Exports live outside the repo (e.g. `~/Downloads/ChatExport_*`); pass paths via `data/config.json`.

- **Unit = turn:** consecutive own messages are merged with newlines into one training target (preserves the habit of splitting thoughts into several short messages). The keyboard inserts multi-line text.
- **Cleaning:** strip URLs, phone numbers, emails, card-like numbers, stickers/media placeholders, forwarded messages, duplicates.
- **Balance:** no single chat above 35% of the training set. Up to ~12k pairs total.
- **Split:** last ~4 weeks per chat + a few held-out conversation segments go to test.

### Training pairs
- `rewrite`: neutral version (by Muse Spark Open) → original own message.
- `compose`: instruction ("tell X we meet at 5") generated by Muse Spark Open → original.
- `reply`: (situation tag + short neutralized summary of the incoming message) → own reply.
- Loss on the response only. Filter pairs where meaning changed (LaBSE similarity). Test split by time (most recent weeks) plus a few held-out conversations. Data-size sweep: 250 / 1k / 5k / all.
- QLoRA defaults: r=16, lr 2e-4, 1–3 epochs.

## Evaluation (the core proof)

Systems: base Glimmer · Glimmer few-shot · Muse Spark few-shot · LoRA · LoRA + retrieved own examples.
Metrics: mStyleDistance similarity (`StyleDistance/mstyledistance`), n-gram "is it the user?" classifier, ~20-feature stylometric fingerprint (length, end punctuation, lowercase starts, emoji rate, EN/KZ/RU token share, top words), LaBSE meaning preservation, verbatim-memorization rate.
Blind test: 5–8 friends, compose tasks only (no third-party messages shown), protocol written in `eval/BLIND_TEST.md` before running.

## Demo language

The user writes in Russian (with Kazakh/English mixed in); judges are likely English-speaking. So: English narration and captions; an English translation under each on-screen message (translated by Muse Spark); side-by-side "generic AI vs SaySo" with fingerprint features highlighted in color (length, end punctuation, lowercase, emoticons, EN/KZ insertions) so the difference is visible without reading Russian; benchmark numbers and blind-test results are language-independent. Do not invent an English profile without English data.

## Privacy rules (non-negotiable)

- Train only on the user's **own** outgoing messages. Other people's messages may be read transiently to tag situation/context, then discarded; never stored in datasets, never sent to third-party APIs in raw form for batch processing (summarize/neutralize locally or with our own hosted model where possible), never shown in the demo.
- `data/`, exports, adapters and `.env` are gitignored. Before every commit, check `git status` contains no data files.
- Screenshots in "Reply from screenshot" are processed in memory and not stored.
- After training, raw exports can be deleted; the user keeps the adapter file and the profile.
- Never market SaySo as "undetectable AI". Frame: authenticity, your own voice, human-in-the-loop.

## Repo layout (target)

```
pipeline/   parse_telegram.py, build_pairs.py, situations.py, fingerprint.py
training/   modal_train.py (Unsloth QLoRA), configs/
serving/    modal_app.py (FastAPI + vLLM + LoRA)
eval/       run_benchmark.py, BLIND_TEST.md, results/ (aggregated metrics only)
ios/        SaySo.xcodeproj, SaySoApp/, SaySoKeyboard/, SaySoShare/
docs/       architecture, data-flow diagram
```

## Day plan

| Date | Goal |
|---|---|
| Oct 27 | Repo, parser, `config.json`/`audiences.json`, counts per audience, train/test split |
| Oct 28 | Pairs via Muse Spark Open, fingerprint, few-shot baselines. iOS spike: keyboard inserts text from a test endpoint; Back Tap Shortcut uploads a screenshot to a test endpoint |
| Oct 29 | First Glimmer LoRA on Modal, vLLM serving, `/rewrite` `/compose` |
| Oct 30 | Benchmark (5 systems × metrics) + data-size curve. Watch Fireworks training workshop |
| Oct 31 | SwiftUI app: onboarding, style card, sandbox. Keyboard: chips, actions, preview, insert |
| Nov 1 | Situation tags + `/reply`; Share Extension "reply from screenshot" via Muse Spark vision |
| Nov 2 | **Feature freeze.** Blind test, Proof screen, privacy screen, README with results and data-flow diagram |
| Nov 3 | Record and edit the ≤3-min video |
| Nov 4 | Submit by ~22:00 Astana |

## Conventions

- Python 3.11+, `uv` for envs. Read keys from `.env` only.
- Small, frequent commits with clear messages (judges must see what was built during the hackathon).
- Ask before any change that could expose private data.
