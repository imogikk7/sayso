# Submission plan, Nov 2 (planner agent)

Read-only pass with the everything-claude-code `planner` agent over `README.md`, `CLAUDE.md`, `docs/SUBMISSION.md`,
`docs/VIDEO_SCRIPT.md`, `docs/deck/`, `eval/results/*.json`, `serving/modal_app.py`, `ios/scripts/`, the git log and
the risks section of `docs/reviews/architecture.md` (R1–R8 below are its numbers). Not read: `data/`, `.env`. No code
was changed. Repo state: `main` at `d9cb2aa`, clean, `imogikk7/sayso` is public (GitHub API answers 200 without auth).

**Deadline:** Nov 4, 9:00 PM ET. US daylight saving ended Nov 1, so that is **02:00 UTC Nov 5 = 07:00 Astana Nov 5**.
Target: submit by **22:00 Astana Nov 4** (9 h of buffer), as `CLAUDE.md` already says.

---

## 0. Stage 1 (pass/fail)

| Check | Status | Evidence |
|---|---|---|
| Theme | Pass: **Build for Your World** (a personal tool built around the author's own voice, languages and audiences) | README intro, SUBMISSION "Inspiration" |
| Meta models, reasonably used | Pass: Muse Spark Open (Baseten, writes everything live), Muse Spark 1.3 (reads screenshots, photos, essays), Muse Voice Transcribe 1.0 (voice notes), Muse Glimmer 30B + LoRA (trained on Modal, benchmarked) | README "Meta models and their roles", `serving/writer.py:139-141, 536-560, 819` |
| Public repo | Pass | `https://github.com/imogikk7/sayso` |
| New work, clearly identified | Mostly pass. First commit Oct 27 19:02 +0500; CLAUDE.md says "everything in this repo is written during the hackathon". Not yet said in README. | `git log --reverse` |
| Demo shows only event work | Pass if the video follows `VIDEO_SCRIPT.md` (third-party apps such as Telegram and WhatsApp only appear as the place SaySo is used) | |

Cheap fix: add a 3-line "Built during the event" block at the top of README (first commit date, solo, open-source
libraries used: Unsloth, vLLM, FastAPI, SwiftUI; no code from earlier projects).

---

## 1. Rubric scores (Stage 2), evidence, cheapest raises

Scores are my estimate of how a judge reading the repo and watching the planned video would score it today, and
after the moves listed. Effort is the author's time.

### Impact: **6 / 10** now → 7 with the moves

Evidence for:
- A clear, felt problem ("AI replies sound like AI") with a concrete user: someone who texts in several languages and
  writes differently to partner, friends, family and elders. Formal voice (emails, essays from your own notes) widens it.
- Lives where people type (own keyboard, Back Tap, chat), not in a separate chatbot.
- Privacy designed in and tested (`tests/test_privacy.py`, `tests/test_styles.py`); only the user's own text is kept.
- A business model with an honest cost table (README "Scaling and unit economics").

Evidence against:
- n = 1. Every number is on the author's own messages; nobody else has used it. The blind test is still TODO in
  README, SUBMISSION and the deck.
- A judge may read "AI that writes like you" as impersonation, and Essay mode as ghostwriting homework.

Cheapest raises:
1. **Run the blind test tonight** (no GPU; `eval/blind_test.py` v2 is merged): `python3 eval/blind_test.py build --n 15`,
   send `data/blind/test.html` to 8–12 friends tonight, score Nov 4 morning, commit `eval/results/blind_test.json`.
   Even "friends found the real me 41% vs chance 33%, n = 9" is real evidence from people other than the author.
   If fewer than 5 answer, replace the TODO with "protocol written, running" and drop it from the video. (30 min)
2. **Name who benefits in one sentence** in the gallery blurb, SUBMISSION and the video: people who write across
   languages and audiences every day, and people writing emails or a personal statement in a second language who want
   it to still sound like them. Don't claim accessibility users unless someone like that has tried it.
3. **Frame Essay mode as personal statements and cover letters from your own notes**, not homework. Keep "you always
   press send" and "your facts only" in the voiceover (the script already does). (5 min of wording)

### Use of Meta AI Tooling: **7 / 10** now → 8.5 with the moves

Evidence for:
- Four Meta models with distinct, sensible roles, and a two-way fallback between Spark Open and Spark 1.3.
- Non-obvious uses: Glimmer's own `to=self` reasoning channel used for a "thought first" (act · tone · gist) and as an
  **intent control** by prefilling `act: refuse` (README §3, `bench_v4.json`); Spark 1.3 vision reading handwritten
  essay pages into paragraphs (commit `ec4236c`); Spark as the judge in the style self-check; Spark turning a 👎
  comment into a standing rule.
- Open weights twice: Spark Open writes every live message; Glimmer carries the personal LoRA.

Evidence against:
- What judges will *see* live is prompting (Spark Open + profile + examples). The most original part, the LoRA and
  its thought channel, appears only as "trained and benchmarked, waiting for a GPU". "Waiting for a GPU" reads as
  unfinished.

Cheapest raises:
1. **Serve the LoRA live for one 45-minute window on Nov 3** (section 4) and put 10–12 s of it in the video: Back Tap
   giving three replies with different intents from your own model, plus 2 s of terminal proof (`"styled": true`, the
   adapter name in the vLLM log). This turns "waiting for a GPU" into "my own model, live".
2. In beat 7, say the intent-control trick in one line: "My model writes a short thought first, in Glimmer's own
   reasoning channel. I can set that thought to agree, refuse or joke, and get three replies in my voice."
3. In the submission text, name the surprising bits in one list (thought channel as a control knob, handwriting
   reading, Spark as self-check judge, feedback → rules) instead of leaving them spread through the README.

### Technical Depth & Execution: **8 / 10** now → 8.5–9 with the moves

Evidence for:
- Honest, reproducible evaluation: held-out sets, fingerprint + chrF + memorization, a tagger self-consistency
  ceiling (48%) and a majority baseline (36.8%), negative results reported (v3 SimPO worse, embeddings no better than
  random, best-of-5 hurts chrF), run-to-run noise stated. Committed aggregates only.
- Numbers that matter: fingerprint 2.64 → 1.02 → **0.04** and rewrite chrF 28.5 → 40.7 → **57.2** (base → few-shot →
  LoRA, `bench_2026-10-28.json`); style lift 0.69 → 0.94 form (`style_gain.json`).
- Real engineering: multi-LoRA vLLM on Modal with an env switch, style-building pipeline with stages, keyboard
  extension with field-type exclusions, App Intents, atomic writes and auth middleware after review
  (commit `377c967`), about 100 tests including privacy tests.

Evidence against:
- **Numbers out of sync (R7):** `style_gain_open.json` says Spark Open **form 0.93, chrF 50.4** (commit `f1c0fe5`), but
  README (results table and bullet), SUBMISSION ("Accomplishments") and deck slide 6 still say **47.5**. Judges who
  check claims against the JSON will notice.
- Deck slide 7 compares v4 raw (0.07) with "earlier LoRA 0.12", which is v2 + rerank; README's table compares v2 0.075
  vs v4 0.072. Use the README table's like-for-like numbers.
- Deck slide 3 still has two dashed screenshot placeholders (`docs/deck/img/` is empty).
- README is 30 KB; a judge has no 60-second path through it.

Cheapest raises (all text, about 45 min total):
1. Replace 47.5 with 50.4 in README (table row and bullet), SUBMISSION, deck slide 6; rebuild the PDF.
2. Fix deck slide 7 to the README's like-for-like numbers; drop in `img/keyboard.png` and `img/backtap.png` from the
   Nov 3 takes.
3. Add a "Judge path" box at the top of README: video link, the three numbers, where the code for each surface lives,
   and how the LoRA was served for the video.
4. Add a LICENSE (MIT) if you are fine with it; open-source judges look for one.

### Demo: **6 / 10** now (not filmed) → 8 with the moves

Evidence for:
- `VIDEO_SCRIPT.md` is precise (taps, captions, badges, honesty rules, consent checklist) and fits 2:48.
- The Back Tap moment is visual and easy to understand; the series stack is distinctive.

Evidence against:
- Eight beats in 2:48 is dense; beats 3–5 (style import, formal import, essay) are three "settings" beats in a row.
- Most on-screen text is Russian; non-Russian judges read translations on the left panel at speed.
- The most impressive tech (own model) isn't shown live.
- Spark output varies per take (R8); latency 6–10 s for Back Tap needs speed ramps.

Cheapest raises:
1. **Cold open with the payoff**: the first 3 s are the finger double-tapping the phone and three replies appearing,
   then the "AI replies sound like AI" line. Stage 3 judges watch live; win the first 10 s.
2. **Compress beats 3 + 4 into one 20 s beat** (style from chats, then emails and essays as a 4 s cut) and use the
   freed ~12 s for the live LoRA clip in beat 7. Keep the total ≤ 2:50.
3. **One English line on screen per Russian output**, large, next to the bubble (not only on the far left panel),
   with the differences highlighted (lowercase, no period, split into bursts), as the script suggests.
4. Replace "waiting for a GPU" in the beat 7 voiceover with: "And my own model, a LoRA on Muse Glimmer 30B, served
   live for this demo." (The public server still runs Spark Open; say that in README, not in the video.)

Revised timeline (suggestion):

| # | Beat | Length |
|---|---|---|
| 0 | Cold open: double-tap → three replies (3 s), "AI replies sound like AI" (5 s) | 8 s |
| 1 | Keyboard ✨ → variants → series stack | 27 s |
| 2 | Back Tap in Telegram → replies → paste | 22 s |
| 3+4 | Style from a WhatsApp export → self-check; then own emails and essays (4 s cut) | 20 s |
| 5 | Essay from voice notes → questions → answer by voice; Email | 27 s |
| 6 | 👎 "shorter" → Learned; keyboard learns | 12 s |
| 7 | Four Meta models + numbers (8 s), **own model live: three intents + terminal proof** (12 s) | 20 s |
| 8 | Privacy + close | 14 s |
| | **Total** | **2:30–2:50** |

---

## 2. Extra bonus tracks: Best Agentic ($5k), Best Creative with Muse Image/Wonder ($5k)

**Recommendation: enter neither. Enter Best Open Weight Models, Most Viral on X and Community Vote.**

- **Best Open Weight Models ($10k): strong fit, go.** Muse Spark Open on Baseten (partner inference) writes every live
  message; Muse Glimmer 30B + the author's LoRA is trained and, on Nov 3, served on the author's own Modal H100. In the
  form, say both and point to `serving/writer.py` (Spark Open call) and `serving/modal_app.py` (vLLM + LoRA).
- **Best Agentic: no.** What exists are fixed workflows: Essay mode (plan → write → self-check → questions → revise),
  the style build pipeline, feedback → rule. There is no model choosing tools or deciding its own next step. Making it
  genuinely agentic (for example a reply agent that decides to ask you, look up your earlier messages to that person,
  or split into a series) is 1–2 days of work after the Nov 2 freeze, would put Nov 3 filming at risk, and would
  compete against teams who built agents from day one. Expected value is a few hundred dollars against a real risk to
  the main-track demo. Ticking the box without the substance reads as padding.
- **Best Creative with Muse Image/Wonder: no.** SaySo doesn't generate images, and bolting one on (a "style card" image
  or stickers) is off-product and wouldn't be the kind of creative use that wins that prize. Using Muse Image only for a
  thumbnail doesn't count as building with it.

---

## 3. Virality: X posts, 20-second hook, Community Vote blurb

Rules for all posts: upload the video **natively** (not a YouTube link), captions burned in (X autoplays muted), tag
the hackathon's official account and hashtag from the hackathon guide (check the exact ones; `@AIatMeta` if allowed),
repo link in the first reply, not in the post. Only staged demo lines on screen, never real chat content. Never buy or
bot engagement (disqualification risk). Post **Nov 4 around 8:30 AM ET (18:30 Astana)**, before submitting, so the
post URL can go into the form; pin it; reply to every comment through Nov 8.

**Variant A, story (default):**
> Every AI reply sounds like a support bot.
> So I built one that texts like me: lowercase, short bursts, Russian + English mixed, different for my mom than for
> my friends.
> Double-tap the back of my iPhone → 3 replies in my voice.
> Built solo in 9 days on Meta's Muse models. [video]

**Variant B, challenge (use only if the blind test has a real number):**
> One of these replies is mine. One is my AI. One is a generic AI.
> My friends picked my AI as "the real me" N% of the time (n = …).
> Can you tell? Answer before you watch how it works. [video, first 3 s shows the three replies]

(Use a staged situation for the public quiz, not the blind test's real messages.)

**Variant C, builders:**
> I fine-tuned Meta's open-weights Muse Glimmer 30B on my own texts.
> Style gap to how I really write, 499 held-out messages:
> base 2.64 → few-shot 1.02 → my LoRA 0.04
> Then put it in an iOS keyboard + Back Tap. Code and benchmarks are public. [video]

Post A as the main post; post C as a reply in the thread on Nov 5 (US morning) to give the thread a second wave; post
B on Nov 6 if the blind test finished.

**20-second hook (vertical 9:16, for X, cut from the Nov 3 takes):**

| Time | Picture | On-screen text |
|---|---|---|
| 0–2 s | Friend's message arrives in the staged chat | `AI writes like a robot. Watch this.` |
| 2–4 s | Second camera: finger double-taps the back of the phone | `double-tap` |
| 4–8 s | Three replies appear (sped up, real time labelled) | English translation under each |
| 8–11 s | Split: a generic AI reply vs the SaySo reply the take actually produced | `generic AI` / `me, via SaySo` |
| 11–15 s | Keyboard: draft → ✨ → series stack, three bursts sent | `it even texts in bursts, like I do` |
| 15–18 s | Card | `My own model on Meta's open-weights Glimmer 30B · style gap 2.64 → 0.04` |
| 18–20 s | End card | `SaySo · write the way you'd say it · built in 9 days` |

**Community Vote gallery blurb (≈ 80 words):**
> **SaySo writes the way you'd say it.** Every AI reply sounds like the same polite assistant. SaySo learns how *you*
> text: your length, slang, punctuation and languages, and how you write differently to your partner, friends and
> family. Use it from its own iPhone keyboard, or double-tap the back of your phone for three replies in your voice.
> It also writes emails and essays from your own notes in your formal voice. Only your own writing is kept, and you
> always press send. Built solo in 9 days on four Meta models.

---

## 4. Nov 3 filming plan (Astana time, UTC+5)

### Tonight (Nov 2) so tomorrow is only filming
- [ ] Send the blind test (section 1, Impact move 1). No GPU needed.
- [ ] Build the WhatsApp demo style (Spark only) so it's ready; film only the start of a fresh build tomorrow.
- [ ] Staged chats with the second account (consent in writing if a friend), neutral names, no older history.
- [ ] Ask organisers when the Baseten and Meta keys expire and their rate limits (R1).
- [ ] Open the Modal billing page: confirm how much credit is left and whether the monthly credit reset on Nov 1
      (R4). **Set a workspace budget limit** in the Modal dashboard (you do this; it's an account setting).
- [ ] Fix the 47.5 → 50.4 numbers (text only) so the beat 7 card and the docs agree.

### Model per shot

| Shot | Writer | Needs the live LoRA? |
|---|---|---|
| 0 cold open, 2 Back Tap (WhatsApp style) | Spark 1.3 reads, Spark Open writes | No |
| 1 keyboard ✨ and series | Spark Open | No |
| 3+4 style build, emails and essays import | Spark 1.3 (reading, tagging, self-check) | No |
| 5 essay (Spark 1.3), email (Spark Open), 🎙 (Voice Transcribe) | as named | No |
| 6 👎 → rule, Learned list | Spark Open + Spark 1.3 | No |
| 8 privacy screens, end card, deck screenshots, X vertical clips | none / Spark Open | No |
| **Control takes for the comparison**: main (Telegram) style active, beat-1 draft in Chat → Rewrite; Back Tap on the moving-help chat | Spark Open | No (morning, GPU off) |
| **L1** Back Tap with the main style: three replies with different intents from the LoRA | Spark 1.3 reads, **LoRA rewrites** | **Yes** |
| **L2** Chat → Rewrite, same draft as the control take (side-by-side) | **LoRA** | **Yes** |
| **L3** Keyboard ✨ in Telegram, format Message | **LoRA** | **Yes** (optional) |
| **L4** Terminal proof: `eval/smoke_api.py --gpu --show` → `"styled": true`, `thought: act: … ·`, vLLM log line with the adapter | **LoRA** | **Yes** |

Two things decide whether the LoRA actually writes (otherwise the server silently returns the Spark draft with
`styled: false`): the **active style must be the main style** (the only one with an adapter, v4; the WhatsApp demo
style has none since `SAYSO_TRAIN` is off), and the **format must be Message or Series** (formal formats skip the
LoRA). The iOS UI doesn't show `styled`, so L4 is the proof; blur the URL and token in it.

### Schedule

| Time | What |
|---|---|
| 07:30–08:00 | Phone setup checklist from `VIDEO_SCRIPT.md` (Focus on, Full Access, Back Tap → "Reply with SaySo", mic allowed, light mode, Learned list cleared). |
| 08:00–08:15 | Server: `SAYSO_GPU=off SAYSO_TRAIN=off .venv/bin/modal deploy serving/modal_app.py`; `/warmup` must answer `{"gpu": "off"}`; `.venv/bin/python eval/smoke_api.py --spark --show` (both keys answer). Open the app before each take so the CPU container is warm (R3). |
| 08:15–09:00 | Beats 3+4: start a fresh WhatsApp build on camera, cut to the prebuilt style; formal writing import. |
| 09:00–10:30 | Beats 1, 2, 6 with the WhatsApp style, 3 takes each; second camera for the double-tap finger shot. Then switch to the main style and record the two control takes. Note every real wait time. |
| 10:30–11:30 | Beat 5 (essay + email by voice), beat 8 screens, end card, deck screenshots (`img/keyboard.png`, `img/backtap.png`), vertical clips for the X hook. |
| 11:30–12:45 | Review takes, retakes, lunch. If Baseten failed in any take, the badge must read Spark 1.3 or the take is refilmed. |
| 12:45–13:00 | GPU pre-flight (below). |
| **13:00–13:45** | **GPU window** (below). Hard stop at 13:45. |
| 13:45–14:00 | Verify everything is off; billing screenshot. |
| 14:00–15:00 | Voiceover (quiet room, 48 kHz), with the revised beat 7 line. |
| 15:00–20:00 | Edit the 16:9 cut (≤ 2:50), captions burned in plus `captions.srt`, translations next to each Russian bubble. |
| 20:00–21:00 | Cut the 20 s vertical hook for X. |
| 21:00–21:30 | Export 1080p H.264; watch end to end for names, keys, notifications; upload to YouTube **unlisted** so processing finishes overnight. |

### GPU window, minute by minute (T = 13:00, budget ≈ 45 min of H100)

Modal lists the H100 at about $3.95/h (check the current price): 45 min ≈ $3, cold start included. That leaves room in
$5 for the CPU API through Nov 8, which scales to zero when idle.

| T | Action |
|---|---|
| T−15 | `modal app list` (nothing on GPU). Billing page open, budget limit set. App: active style = **main style**, format Message. Mac: terminal 1 `modal app logs <app>`, terminal 2 the smoke command typed but not run, Mac screen recording ready. Phone: staged chats ready, take list printed. |
| T+0 | `SAYSO_GPU=modal SAYSO_SCALEDOWN=600 SAYSO_TRAIN=off .venv/bin/modal deploy serving/modal_app.py` (10 min scaledown so a pause between takes doesn't trigger a second cold start). |
| T+1 | Hit `/warmup` once (the app's warm-up button or curl). Start a stopwatch. Touch nothing else. |
| T+1–6 | Cold start (3–5 min). Re-check phone settings. |
| **T+10** | **Abort rule:** not ready by T+10 → go straight to the shutdown step and keep the "trained and benchmarked" line in the video. |
| T+6–9 | L4 terminal proof, 1 take: `.venv/bin/python eval/smoke_api.py --gpu --show`. Confirm `"styled": true` before filming anything else. |
| T+9–19 | L1 Back Tap with the main style: 3 takes with the note "politely decline", 2 takes with no note (three intents). |
| T+19–27 | L2 Chat → Rewrite with the beat-1 draft, 3 takes (side-by-side with the morning Spark Open take). |
| T+27–35 | L3 keyboard ✨ in Telegram, 2 takes (skip if behind). |
| T+35–40 | Retakes of whatever failed. |
| T+40 | Shutdown: `SAYSO_GPU=off SAYSO_TRAIN=off .venv/bin/modal deploy serving/modal_app.py`; `modal container list` → `modal container stop <id>` for any Glimmer container; `/warmup` → `{"gpu": "off"}`. |
| T+45 | `modal app list` again; billing screenshot; write down the GPU minutes for the README note. |

---

## 5. Nov 4 submission checklist (Astana time)

**Morning (08:00–13:00): numbers, repo, security**
- [ ] Score the blind test: `python3 eval/blind_test.py score <codes…>` → commit `eval/results/blind_test.json`
      (aggregates only). Update the TODO lines in README §5, SUBMISSION "What's next", deck slide 7.
- [ ] Numbers: 50.4 everywhere Spark Open chrF appears; deck slide 7 like-for-like; screenshots into `docs/deck/img/`;
      `docs/deck/build.sh`.
- [ ] README top: video link, "Judge path (60 s)", "Built during the event" block, and one honest line: "For the
      video, the LoRA was served on Modal on Nov 3 (H100, ~45 min); the public server runs Muse Spark Open."
- [ ] LICENSE (MIT) if you want it.
- [ ] `git status` clean, push, check README renders on GitHub logged out.
- [ ] **Token rotation (R6)**, in this order: new `SAYSO_API_TOKEN` → Modal secret `sayso` (you run
      `modal secret create sayso SAYSO_API_TOKEN=… --force`) → `.env` → `sh ios/scripts/gen_secrets.sh` → redeploy with
      `SAYSO_GPU=off SAYSO_TRAIN=off` → old token gets 401. Revoke the unused Fireworks key too.
- [ ] **Re-sign the iOS build (R5)** in the same step: Xcode → SaySo scheme → Personal Team WL5B45CYV9 → Run on the
      iPhone (installs app + keyboard extension with fresh 7-day profiles, valid to about Nov 11). Write down the
      install date. Don't change bundle IDs (free teams cap App IDs). Then test: keyboard ✨, Back Tap, Chat, 🎙.
- [ ] Keys through Nov 8 (R1): confirm from organisers or the dashboards; if the Baseten key ends with the event,
      `SAYSO_WRITER=meta` is the one-env switch.
- [ ] **Claim the Meta credits** offered in the hackathon guide if not yet claimed, and check the Meta API key's quota
      covers Nov 5–8.

**Afternoon (13:00–18:30): video and post**
- [ ] Final video ≤ 3:00 (check the exact duration in the player, not the editor). YouTube **unlisted** (not private),
      title "SaySo · Meta Global AI Developer Hackathon (indie)", captions uploaded. Open the link in a logged-out
      incognito window and on a phone on mobile data. Backup copy on Google Drive with "Anyone with the link".
- [ ] 18:30 (8:30 AM ET): post variant A on X with the native 20 s hook or the full video; repo and gallery link in the
      first reply; pin; copy the post URL.

**Evening (19:00–22:00): the form (field names to verify on the Cerebral Valley platform)**
- [ ] Project name, tagline ("AI that writes the way you'd say it"), track **Indie**, theme **Build for Your World**.
- [ ] Description: from `docs/SUBMISSION.md` (with 50.4, the blind test result, the LoRA-live note).
- [ ] Meta models used: all four with roles; open-weights models named explicitly.
- [ ] Repo URL, video URL, X post URL, screenshots/thumbnail, solo team member.
- [ ] Bonus categories: **Best Build on Meta Open Weight Models**, **Most Viral on X**, **Community Vote**.
- [ ] Submit by 22:00 Astana. Screenshot the confirmation; open the submission page logged out.
- [ ] `git tag submission && git push --tags`. After 07:00 Nov 5, work only on a branch, so `main` matches what was
      judged.
- [ ] Server left with `SAYSO_GPU=off SAYSO_TRAIN=off`, budget limit on. For any live judging slot: open the app a
      minute before (warms the CPU container).

**Nov 5–8:** answer replies on X daily, post variant C as a reply Nov 5, variant B Nov 6 if the blind test has a
number, share the gallery link for Community Vote with friends (asking people to look is fine; buying or botting is
not).

---

## 6. Risks and mitigations

| # | Risk | Mitigation |
|---|---|---|
| R1 | Hackathon keys expire or rate-limit (Baseten event key, Meta tier); screenshots have no real fallback since Spark Open can't read images | Ask organisers today; `SAYSO_WRITER=meta` switch; record every live beat Nov 3 and keep raw takes for any live session |
| R2 | Fallback slower than the client: 30 s per try vs keyboard 20 s / Back Tap 25 s, so a hanging Baseten call times out before Spark 1.3 runs | For filming: retakes. For Nov 5–8: the 2-line per-try timeout (8–10 s) from the architecture review is worth it only if you accept a post-freeze change; it has a fake-client test |
| R3 | Cold API container makes the first ✨ slow | Open the app a minute before each take or live slot (no code change); `min_containers=1` on `api` only during filming if you accept a one-line change, revert after |
| R4 | Accidental GPU spend (`/warmup` wakes an H100 for anyone with the token, `SAYSO_TRAIN=on`) | Deploy with both off; Modal budget limit; abort rule at T+10; shutdown checklist at T+40 |
| R5 | Free provisioning dies Nov 7 | Re-sign on Nov 4 (to about Nov 11) |
| R6 | Single token in the app binary | Rotate Nov 4 after filming; never share the IPA |
| R7 | Numbers out of sync (47.5 vs 50.4; blind test TODO) | Section 5 morning list |
| R8 | Spark output variance on camera | 3 takes per live moment; pasted-chat path as Back Tap backup; never edit a model's text |
| R9 | Deadline confusion: ET is EST since Nov 1 | 9 PM ET = 07:00 Astana Nov 5; submit by 22:00 Astana Nov 4 |
| R10 | Video over 3:00, private link, or still processing | Target 2:30–2:50; upload unlisted the night before; test logged out; Drive backup |
| R11 | Private data on screen (names in self-check rows, a key or URL in the log insert) | Blur pass in the final watch-through; staged chats only; L4 terminal crops |
| R12 | Ethics read: "AI pretending to be you", essay ghostwriting | "Your voice, your facts, you press send" in voiceover and blurb; Essay framed as personal statements/cover letters from your own notes; no "undetectable" wording |
| R13 | Judges can't read Russian | English line next to every bubble, differences highlighted, English voiceover throughout |
| R14 | LoRA shot shows Spark output by mistake (`styled: false` with the wrong active style or a formal format) | Main style active, Message format, L4 proof first; badge LoRA only on takes taken after `"styled": true` |
| R15 | GPU cold start runs long or fails | Abort at T+10; video falls back to "trained and benchmarked" with the numbers card |
| R16 | Commits after the deadline look like late work | Tag `submission`; branch afterwards |
| R17 | Low X engagement | US-morning post, native video, hook in the first 2 s, thread follow-ups Nov 5–6, reply to comments |
