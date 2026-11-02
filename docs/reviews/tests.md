# Test review: coverage, gaps, and a manual iPhone checklist

Date: 2026-11-02. Scope: the Python backend (`serving/`, `eval/`) with automated tests, and the iOS app with a manual
checklist. Feature freeze: only `tests/` and this file changed. Nothing in `serving/`, `ios/`, `pipeline/` or `eval/` was edited.

Run it (coverage data stays out of the repo):

```bash
COVERAGE_FILE=/tmp/sayso.cov .venv/bin/python -m pytest -q tests --cov=serving --cov=eval --cov-report=term-missing
```

## 1. Coverage before and after

Before means the 107 tests that existed already. After means those 107 plus the four new `tests/test_cov_*.py` files.
`tests/test_sec_review.py`, added at the same time by the security review, is left out so that the numbers show only
this work.

| File | Stmts | Before | After |
|---|---:|---:|---:|
| serving/writer.py | 513 | 75% | **84%** |
| serving/documents.py | 107 | 91% | **99%** |
| serving/styles.py | 158 | 95% | **99%** |
| serving/build_style.py | 271 | 70% | **91%** |
| serving/modal_app.py | 359 | 70% | **86%** |
| serving/fireworks.py | 72 | 0% | 0% |
| **serving/ total** | 1480 | **73%** | **84%** |
| serving + eval (the command above) | 2303 | 59% | 67% |

Tests: 107 → 201 (94 new: 90 pass and 4 are `expectedFailure`, each pinning a bug). The full suite, including
`test_sec_review.py`, takes about 25 s. It gave the same result on two runs in a row. It needs no network, no GPU and
no `data/`.

### New test files

| File | Tests | What it covers |
|---|---:|---|
| `tests/test_cov_writer.py` | 37 | `Writer.email`: one call, the formal voice, `reply_to`, the cliché fix pass, clipping, control tokens, a 502. `Writer.essay`: the prompt includes the first-person and no-invention rules; the length fix fires only above +15%; cliché and length are fixed together in one call; leftover clichés are reported; `words` is clamped to 80..900; notes are capped at 4000 chars; outline is capped at 8 and questions at 3. `/chat` in email and essay modes, including revisions. `Context.formal_block` per kind: same-kind paragraphs first, each kind's rules, `k`, the 120-word cut, profile lines, and no chat examples for formal formats. `Writer.read_page` and `Writer.transcribe` on a fake HTTP client. |
| `tests/test_cov_documents.py` | 28 | `own_email` with all 10 quote markers. `mbox_texts`: multipart, cp1251, HTML-only and quote-only bodies skipped, the limit, garbage input. `text_of`: `.docx` entities, broken zip, missing XML, zip bomb, `.pdf` without pypdf, bad bytes. `paragraphs`: line joining, RU and EN section labels, "Bodybuilding" kept, contact scrubbing, the 2000-char cap. `edges`, `profile` (whole-word connectors), `profile_text`. `styles.add_documents`: counts per kind, greetings and sign-offs taken from emails only, the 300-paragraph cap. |
| `tests/test_cov_api.py` | 21 | Uses the real FastAPI app through the `test_api_auth.py` harness. `POST /styles/{id}/documents` with pasted text, `.mbox`, `.docx` + `.txt`, and photos (read by the faked Spark, never stored); 404, 422, and 413 over 25 MB. `POST /transcribe` through the real `Writer.transcribe`: 200, 422 for non-WAV or no file, 413, and 502. **TokenGate** called directly over ASGI: 401 before the body is read on every route, 401 takes priority over 413, and 413 above 60 MB (exactly 60 MB passes). Unauthenticated multipart is never parsed. Also: PATCH removals, the full style view, delete (the cached context is dropped), `/warmup` with the GPU off, and a `/reply` restyle from a summary without rereading. |
| `tests/test_cov_build.py` | 8 | The build's sync `Spark`: JSON wrapped in prose, retry with backoff, an empty label after 3 failures. `read_images`: frames merged per chat, bad messages dropped, the "Screenshots" fallback, the PNG or JPEG data URL. `self_check` with a faked `Writer.read`: scores, skipped empty drafts, failing reads. |

## 2. Bugs the new tests revealed (pinned with `@unittest.expectedFailure`)

| Id | Where | Bug | Severity |
|---|---|---|---|
| **TEST-1** | `writer.py` `Writer.email` | When the email contains an AI cliché, the fix call returns only `{"text"}`. The code then reads `subject` from that new label, so **the subject is lost (`None`)**, and the app's "Copy subject" button disappears. Fix: keep the subject from the first label. | Medium (demo-visible) |
| **TEST-2** | `writer.py` `Writer.essay` | If Spark returns `questions` (or `outline`) as a string instead of a list, the code iterates over its characters, so **the app shows single letters as questions**. This is the same class of bug as the `variants` one fixed earlier. Fix: `isinstance(..., list)` guards. | Low–medium |
| **TEST-3** | `writer.py` `CLICHES` | Only the singular "играет важную/ключевую роль" is listed. **The plural "играют важную роль"**, the more common form in essays, passes the cliché check. (The existing `test_cliches` passed only because "В современном мире" in the same sentence matched.) Fix: `игра(ет\|ют)`. | Low |
| **TEST-4** | `modal_app.py` `/styles/{id}/documents` | Each file is read with `f.read(20 MB + 1)`, but nothing checks that size. A 21 MB file is **silently cut to 20 MB and kept**, not refused with 413. Only the 25 MB total is enforced. A cut `.docx` simply comes back empty. Fix: `if len(raw) > 20 MB: raise HTTPException(413)`. | Low |

All four were re-run without the decorator, and each fails for the stated reason: `None != 'Перенос'`,
`['К','а','к']`, `None`, `200 != 413`.

## 3. What is still untested, and why

| Area | Lines | Why it is not covered |
|---|---|---|
| The GPU / LoRA path in `writer.py`: `ensure_warm`, `uses_model`, `is_up`, `wake`, `load_adapter`, `complete`, `best`, `styled` with an adapter, `reply` with an adapter or the main model's think-then-write | 447–534, 599–602, 620–646 | Every existing test runs with `gpu="off"`. This could be covered with a fake vLLM client (choices with `index`) and a fake tokenizer, and it is **the largest remaining gap that matters for the demo** if the H100 or Baseten is on. It was left out to keep this pass to the listed priorities. |
| `Context` for the main style | 288–291 | Needs `data/pairs_v2` and `data/pairs_v4`, the author's private data. Tests must not read `data/`. |
| The compose echo retry (`ECHO` matched → Spark 1.3 again) | 586 | Easy to add with the existing `FakeSpark`. Low risk. |
| `modal_app.py`: `glimmer()` (vLLM subprocess), the `build_style` Modal function (`wait_for_me`, `train`), raw `image/*` and base64-image `/reply`, `/warmup` with the GPU on | 55–60, 96–126, 305–309, 324–326, 524–532 | These are Modal and GPU wiring. The image `/reply` paths only add size checks on top of `Writer.read`, which is tested. The `build_style` closure needs `modal.Function.from_name` and the volume. |
| `build_style.py`: `read_exports` with `.html` / `.zip` Telegram exports, the "no messages" and "nobody confirmed" failures, the training branch | 175–191, 365–379, 412–418 | The zip-bomb guard and the Telegram-folder unpacking deserve a test (cheap: build a zip in memory). They were left out for time. |
| `serving/fireworks.py` (0%) | all | An alternative hosting path that the demo doesn't use. It calls the network. |
| `eval/bench_generate.py`, `smoke_api.py`, `style_gain.py`, most of `metrics.py` | all | Offline eval and smoke scripts that call the deployed API or models. Rules for this pass forbid network or API calls. |
| The iOS app, keyboard extension and shortcuts | — | No XCTest target exists, and adding one would break the feature freeze. Covered by the manual checklist below. |

## 4. Manual iPhone test checklist (demo)

Run it on the demo iPhone, on the deployed build, against the same server and style as the video. Before you start,
tap **Setup → Test now** and check that the server answers. If the GPU is in use, tap Warm up and wait about 1 min.
Mark each step ✅ or ❌, and write down what you saw when a step fails.

### A. Keyboard in Telegram

- [ ] Settings → General → Keyboard: SaySo is added, and **Allow Full Access** is on.
- [ ] Open a Telegram chat and switch to SaySo with the 🌐 key. The letter keys type normally, Backspace and Return work, and **Capital letter at sentence start** follows the toggle.
- [ ] The top strip shows the mode (Rewrite · Write · Replies), the audience chip, the format chip and ✨.
- [ ] **Rewrite**: type "я опоздаю на 20 минут из-за пробок" and tap ✨. The result replaces the keys, reads like you, and tapping it inserts it into Telegram's field.
- [ ] **Write**: type "tell her I'm 20 min late" and tap ✨. The result is the message itself, not "tell her…" (the echo guard).
- [ ] **Replies**: with the last screenshot replies present (see section F), the panel lists them.
- [ ] Airplane mode: tap ✨. A readable error and **Retry** appear, not a frozen keyboard.

### B. ✨ variants

- [ ] After ✨, the first answer is shown and the alternatives can be reached (up to 4). They differ in wording or length but keep every fact.
- [ ] Tap ✨ again on the same text: you get new variants and the keyboard does not crash.
- [ ] A very long draft (several sentences) stays complete. No fact is dropped.

### C. Audience and format chips

- [ ] Audience chip: switch Partner → Friends → Family → Elder. The tone changes (for example, Family is softer and Elder is more polite). The AI-suggested audience shows ✨ in the menu.
- [ ] Format **Message**: one line, no line breaks.
- [ ] Format **Official**: capitalized, punctuated, no slang, no emoji.
- [ ] Format **Email** (from the keyboard): greeting, paragraphs, sign-off on separate lines.

### D. Series stack

- [ ] Format **Series** + ✨ → "N messages" with a "+N-1" badge. **Send this one, then tap the next**: each tap inserts the next part, and Telegram receives 2–4 separate messages in order.
- [ ] Leave the stack halfway and type something else. Nothing stale is inserted later.

### E. Learning on/off

- [ ] Keyboard settings → **Learn from what I type** ON. Send 2–3 messages in Telegram with SaySo, one of them an edited suggestion. My styles → the style → **Learned from you** lists them, and an edit shows "instead of: …".
- [ ] Send a message that contains a link, email or phone number. In Learned it appears **scrubbed**.
- [ ] Turn learning OFF and send another message. It does **not** appear in Learned.
- [ ] A correction that states a habit ("shorter with family", "no emoji") appears under **Learned from your corrections**.

### F. Back Tap shortcut

- [ ] Setup step 3 is done: Shortcuts has *Take Screenshot → Reply from Screenshot → Choose from List → Copy to Clipboard*, and Settings → Accessibility → Touch → Back Tap → Double Tap is set to that shortcut.
- [ ] In a Telegram chat, double-tap the back of the phone. Within a few seconds a list of 3 replies appears. Pick one, paste it into Telegram, and check that it fits the chat.
- [ ] On a chat whose title is mapped to an audience (for example "Mira" → Partner), the reply uses that audience.
- [ ] Setup → **Last screenshot replies** shows the same 3 replies. The other person's messages are not stored anywhere in the app.
- [ ] Run it with the GPU cold or Spark rate-limited. Replies still arrive (Spark drafts) or a clear message appears. It must not hang.

### G. Chat modes (app → Chat)

- [ ] **Write**: an instruction gives the message, plus up to 2 alternatives.
- [ ] **Rewrite**: a draft comes back in your voice.
- [ ] **Reply**: paste the other person's messages. You get 3 replies with different moves (agree, refuse, joke…), and **For: <audience>** shows the right audience.
- [ ] 👎 then a one-tap reason (or type "короче"): **Fixing the last answer** appears and a revised answer comes back. If the feedback states a lasting habit, a "learned" toast appears.
- [ ] **Email**: write notes, and optionally paste the email you are answering. The result has a **Subject**, and **Copy subject** works. Greeting, paragraphs and sign-off appear in your formal voice.
  - [ ] Notes that tempt clichés ("в современном мире…"): the answer has no cliché, and the **Subject is still shown** (this is TEST-1; if it is missing, the bug is still there).
- [ ] **Essay**: enter a question and your notes, and set the words (for example 300). The essay is in the first person ("I built…"), uses only your facts, and has a "N words" count close to the target or below it.
  - [ ] **Make it stronger: answer one** shows up to 3 real questions. If single letters show up instead, that is TEST-2.
- [ ] The empty-state hints read correctly: the Email hint says "Say or type…", and the Essay hint mentions 🎙.

### H. 🎙 voice

- [ ] On first use, iOS asks for microphone permission. Denying it gives "Allow the microphone in Settings → SaySo".
- [ ] Chat → 🎙 → speak 5–10 s in Russian → stop. The transcript is sent like typed text and the answer follows.
- [ ] Essay notes dictated for about 1 min are transcribed fully.
- [ ] With no network, a clear error appears. The recording does not stay on the device or the server.

### I. Add emails and essays (formal writing)

- [ ] Style → **Add emails** → **Paste text**: paste 2 of your sent emails, one of them with a quoted reply ("On … wrote:", "> …"). The **Opens with** and **Signs off with** values are yours, and the quoted text is not stored.
- [ ] **Add essays & documents** → add a `.docx` and a `.txt`. The paragraph count goes up, and **Links ideas with:** lists your connectors.
- [ ] Add a photo of a printed or handwritten page, then a screenshot of a sent email. The text is read and the counts go up.
- [ ] A Google Takeout `.mbox` (Sent) is accepted and counted as several emails.
- [ ] Afterwards, write an Email and an Essay in Chat again. The greeting and sign-off now match yours.
- [ ] **Remove all formal writing**: the counts drop to 0.

### J. Delete learned items

- [ ] Style → Learned from you → swipe or tap **Forget** on one message. It disappears and stays gone after you reopen the app (server-side).
- [ ] Learned from your corrections → **Remove** a rule. The next answer no longer follows it.
- [ ] Create a test style, then **Delete style**. It disappears from My styles. The main style has no Delete option (the server answers 409).

### K. Before you film

- [ ] Run `.venv/bin/python -m pytest -q tests`: all tests pass, and the 4 pinned bugs show as expected failures (fewer if any were fixed: then remove the decorator).
- [ ] The server token in the app matches the deployed one: Setup → Test now is green.
- [ ] The GPU decision is made: with the GPU off, everything above works through Muse Spark, and `/warmup` reports `gpu: off`.
