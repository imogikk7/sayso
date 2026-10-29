# Final week plan (Oct 29 → Nov 4), planner pass

Made with the `planner` agent from everything-claude-code over CLAUDE.md, the approved plan and the v4 results.

## Overview
The model is done (v4 + style-profile prefill + reranker, benchmarked). What's left is an **iPhone that shows it**
and **proof a judge can see**. All remaining effort: keyboard panel, Back Tap overlay on a real device,
Proof/blind test. No new GPU training, no new import channels.

## Original plan items
| Item | Verdict | Reason |
|---|---|---|
| A1–A6 (situations, pairs, v4, eval) | KEEP (done) | Freeze; no more training runs |
| B Back Tap overlay | KEEP | Most memorable demo beat; spike exists |
| Keyboard panel | KEEP | It is the product |
| C1 WhatsApp/Instagram parsers | KEEP as code (done) | Shown in README; no phone import UI |
| Share Extension import + "who is who" | LATER | Phone import → training can't be end-to-end on the budget |
| Telegram bot, X parser, screen-recording iMessage | CUT | New surfaces, no demo payoff |
| C2 5-step onboarding | DOWNGRADE | One Setup screen: API, keyboard, shortcut status |
| Push on train | CUT | No push with free signing, no in-app training |
| D0 training-mode letter keys | CUT | Days of Swift layout work, high risk |
| D1 signals | DOWNGRADE | Drafts before Rewrite + picks (+ edits if time) |
| D2 instant retrieval | DOWNGRADE | Learned samples feed the reranker immediately |
| update_lora (LoRA+DPO) + feedback curve | CUT | Budget; SimPO (v3) was already worse |
| "Learned from you" | KEEP (lite) | List + delete; honest "learns" claim |
| Style card, Proof, Privacy, Sandbox | KEEP | Cheap SwiftUI, judges look at them |
| Blind test (5 friends, compose only) | KEEP | Strongest proof |
| Fireworks serving | LATER | Backup if Modal runs out |

## Architecture changes
- `serving/modal_app.py`: `POST /feedback`, `GET/DELETE /learned`, `GET /profile`, `compare` flag on /rewrite and /compose
  (base Glimmer vs SaySo); scaledown from env (5 min, 20 min while filming). Feedback in `modal.Dict("sayso-feedback")`, own text only.
- `serving/writer.py`: `baseline()` (same prompt, no LoRA); `learn(sample)` updates the reranker statistics.
- `pipeline/style_card.py`: style profile → Muse Spark writes the card text → `data/style_card.json` on the volume.
- iOS: `ios/Shared/` (API, ReplyStore, App Group token), keyboard target `ios/SaySoKeyboard/`,
  `ios/SaySoApp/Screens/` (Setup, StyleCard, Proof, Sandbox, Learned, Privacy).
- `eval/BLIND_TEST.md`, `eval/blind_test.py`, `eval/results/blind_test.json` (aggregated), README with a data-flow diagram.

## Steps
1. Deploy + smoke test (/warmup, /rewrite, /reply screenshot); record cold and warm latency.
2. Device signing today (Personal Team, Developer Mode), spike on the phone with real /reply, Back Tap shortcut.
3. CPU-only server additions: /profile, /feedback, /learned, compare.
4. Keyboard extension: audience chips, Rewrite / Compose / Replies tabs, Insert via `textDocumentProxy`,
   Replies from the App Group, draft + pick → /feedback.
5. App screens (Proof reads `eval/results/bench_v4.json`).
6. Blind test: protocol first, 20 compose tasks (real vs v4 vs base), one warm GPU session.
7. README + submission text.

## Risks
- **Modal ≈ $13 ≈ 3 H100 hours**: UI work against CPU endpoints; planned GPU windows (~1 h dev, 1.5 h filming, 0.3 h blind test); try A100-80GB; Fireworks as backup.
- **Cold start while filming**: /warmup 10 min before, scaledown 20 min, film all GPU shots in one session.
- **Full Access**: needed for network; explained on the Privacy screen.
- **Interactive snippet iOS version**: check the phone today; fallback plain dialog + copy.
- **Free signing expires in 7 days, App Groups limits**: install by Oct 31, re-sign Nov 3; fallback keyboard fetches last replies from the server.
- **Other people's messages in the video**: staged chat with a consenting friend or second account.

## Success criteria
- [ ] Warm API: /rewrite < 3 s, /reply < 10 s
- [ ] Keyboard inserts styled text in two real messengers on the iPhone
- [ ] Back Tap → snippet with 3 intents on the device
- [ ] Proof screen + blind-test numbers committed (aggregated only)
- [ ] ≤ 3 min video, README, clean public repo, submitted by Nov 4 22:00 Astana

## Schedule
| Day | Work |
|---|---|
| Oct 29 | Deploy + smoke; signing, spike on phone, Back Tap; server endpoints |
| Oct 30 | Keyboard extension (panel, chips, Insert, shared API client); first device test |
| Oct 31 | Replies via App Group, feedback logging, app screens; `style_card.py` |
| Nov 1 | Full device run, fixes; blind test sent out; README draft |
| Nov 2 | **Freeze**; blind-test results, Proof screen, video script |
| Nov 3 | Re-sign; one warm filming session; edit |
| Nov 4 | Buffer, submission, repo privacy check, submit |
