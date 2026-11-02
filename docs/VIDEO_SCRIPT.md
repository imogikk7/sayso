# SaySo: demo video script (≤ 3:00)

Target runtime **2:48** (12 s of headroom under the 3:00 limit). Filmed Nov 3 on an iPhone 17 Pro, edited the same day.
Narration and captions in English; every Russian message on screen gets an English translation beside it
(translated by Muse Spark 1.3, as CLAUDE.md "Demo language" says). Captions file: [`docs/video/captions.srt`](video/captions.srt).

**Frame:** 16:9 (1920×1080). The phone's screen recording sits in the middle; the left side carries the English
translations of on-screen messages, the right side carries the model badge for the current step (e.g.
`Muse Spark Open · Meta open weights`). Keep the phone's own UI unedited.

**Which model writes what (say it the same way everywhere).** The live app runs with the GPU off:
**Muse Spark Open** (Meta open weights, served by Baseten) writes everything in the user's style (✨, rewrite, compose,
chat, email); **Muse Spark 1.3** (Meta Model API) reads screenshots, chats and photos, drafts the Back Tap replies and
writes essays; **Muse Voice Transcribe 1.0** turns 🎙 notes into text. The user's **LoRA on Muse Glimmer 30B** is
trained and benchmarked but **not hosted live** (no GPU credits), so never say or badge "my LoRA writes this" over a
live output.

**Honesty rules for the edit**
- Every suggestion on screen is a real, live output. Never retype or edit a model's text; if a take is bad, run it again.
- Waiting time may be sped up, but say so on screen (`⏩ ×3 · real time 7 s`). Do not cut a wait to zero.
- Frame SaySo as *your own voice, you always press send*. Never "undetectable AI", never "AI that pretends to be you".
- The style card describes **how you write** (length, case, punctuation, slang, linking words), never personality.

## Timeline

| # | Beat | Start | End | Length |
|---|---|---|---|---|
| 0 | Hook: AI replies sound like AI | 0:00 | 0:08 | 8 s |
| 1 | Keyboard: draft → ✨ → variants → series stack | 0:08 | 0:35 | 27 s |
| 2 | Back Tap in Telegram → replies → paste | 0:35 | 0:59 | 24 s |
| 3 | Add a style from a WhatsApp export → self-check | 0:59 | 1:17 | 18 s |
| 4 | Add your own emails and essays → formal voice | 1:17 | 1:31 | 14 s |
| 5 | Essay from voice notes → questions → answer by voice; Email | 1:31 | 2:00 | 29 s |
| 6 | Chat feedback 👎 "shorter" → Learned; keyboard learns | 2:00 | 2:14 | 14 s |
| 7 | How it works (four Meta models, numbers) | 2:14 | 2:33 | 19 s |
| 8 | Privacy + close | 2:33 | 2:48 | 15 s |
| | **Total** | | | **2:48** |

Narration pace: about 150 words a minute; each beat's voiceover below fits its slot with room to breathe.

---

## 0 · Hook (0:00–0:08)

**Screen:** Split screen. Left: a staged Telegram chat where a generic AI reply has been pasted
(`Конечно! Буду рад помочь. Давайте обсудим детали.` · *Of course! I'd be glad to help. Let's discuss the details.*).
Right: the same friend reacting with a single `🤖?` (staged, second account). Hard cut to the SaySo app icon on the home screen.

**Voiceover:**
> Every AI reply sounds the same. Polite, tidy, nothing like you. My friends would spot it in a second.

**Caption (on screen):** `AI replies sound like AI. Not like you.`

**B-roll:** close-up of a thumb hovering over Send, then pulling back.

---

## 1 · Keyboard: your voice in any messenger (0:08–0:35)

**Screen (exact taps):**
1. Telegram, staged chat with the friend (second account). Tap the message field. The SaySo keyboard is already selected
   (if not: 🌐 → SaySo).
2. Top strip shows `👥 Friends` and `💬 Message`. Type with **SaySo's own letter keys** (RU layout):
   `Привет, сегодня не получится прийти, задерживаюсь на работе. Давай перенесём на завтра?`
   (*Hi, I can't make it today, I'm stuck at work. Shall we move it to tomorrow?*)
3. Tap **✨**. Header `In your style`, then 1–3 variant cards replace the keys. Hold 2 s on the cards.
4. Tap **✕** in the results header to go back to the keys with the draft still in the field (tapping a card would
   insert it in place of the draft; that's shown by the series below).
5. Tap the format chip `💬 Message` → choose **Series**. Tap **✨**.
6. The result is a **stack** (top message, 1–2 peeking underneath, `+2`). Tap it → part 1 is inserted → tap Send.
7. Card `Next: …` appears (header `Series · 1 of 3 sent`) → tap → Send. Repeat for the last part.

**Voiceover:**
> This is SaySo, a keyboard that writes the way you'd say it. I type a plain draft, tap the sparkle, and get versions
> in my own voice. And I don't send one long paragraph, I send bursts. So SaySo does too: a series, stacked like
> notifications. Tap, send. Next. Send. Same meaning, my rhythm.

**Caption:** `Type a draft → ✨ → it sounds like you` · then `Series: sent part by part, like you do`

**B-roll / edit:** left panel shows the draft's English translation; when the variants appear, highlight in color what
changed: lowercase start, no period at the end, shorter length, emoji or `))`. Right badge during ✨:
`Muse Spark Open (Meta open weights) + your style`. Optional: second camera over the shoulder for the three sends.

---

## 2 · Back Tap: reply from a screenshot (0:35–0:59)

**Screen (exact taps):**
1. In the staged Telegram chat, the friend (second account, consenting) has just sent:
   `Слушай, поможешь мне в субботу с переездом? Часов в 10 утра` (*Hey, can you help me move on Saturday? Around 10 am*).
2. **Double-tap the back of the iPhone** (Back Tap → "Reply with SaySo" shortcut). The shortcut takes the screenshot.
3. System dialog **"Who is it for?"** → tap **Friends**.
4. Dialog **"Anything to add? …"** → type `politely decline, I'm busy` → Done.
5. Wait (~6–10 s). The system **list of replies** appears (Choose from List). Tap the one you like → it's copied.
6. Back in Telegram: long-press the message field → **Paste** (allow the paste prompt if iOS shows it) → Send.

**Voiceover:**
> A friend asks for help on Saturday, and I can't. I double-tap the back of my phone. SaySo grabs the screen and asks
> who it's for. I add a note: politely decline. Muse Spark reads the chat and writes three replies the way I would.
> Pick one, paste, send.

**Caption:** `Double-tap the back of the phone` · `Note: "politely decline, I'm busy"` · `Pick → paste → send`

**B-roll / edit:** a screen recording can't show Back Tap, so cut to a **second camera**: a finger double-tapping the
back of the phone (0.7 s), then back to the screen. During the wait show `⏩ ×3 · real time N s` and the right badge
`Muse Spark 1.3 (vision, Meta Model API) reads the chat and drafts 3 replies in your style`. Left panel: English
translation of the friend's message and of each reply in the list.

---

## 3 · Add a style from your own chats (0:59–1:17)

**Screen (exact taps):** (build the real style before filming, see checklist; film the start, then cut to the finished one)
1. SaySo app → **Styles** tab → **Add** menu → **Messages (chats)**. Name: `Me on WhatsApp`. The WhatsApp guide is
   visible for a second (`Open the chat → contact name → Export Chat → Without Media`).
2. **Add chat exports** → pick the WhatsApp export `.zip`. The file shows in the list with its size → **Create style**.
3. **"Which one is you?"** → pick your own name. **"Who are these chats with?"** → the AI's guess is already set
   (`Friends`) → **Continue**.
4. Stages tick off (speed-ramped) → `Ready`.
5. **Self-check card**: `Sounds like you 78% (generic AI 41%)`, 2–3 rows `SaySo: … / You: …`. Tap **Use this style**.

**Voiceover:**
> My voice comes from my own chats. I drop in a WhatsApp export, SaySo asks which one is me, and tests itself on
> messages it hasn't seen. Sounds like me: seventy-eight percent. Generic AI: forty-one.

**Caption:** `Only your side of the chat` · `Sounds like you 78% · generic AI 41%` (TODO: use the numbers from the filmed run)

**B-roll / edit:** speed-ramp the stages (`⏩ ×20`). Footnote on the self-check: `generic AI = Muse Spark without your
style, same held-out messages`. Blur any name or personal fact in the `You:` rows (see checklist).

---

## 4 · Add your own emails and essays (1:17–1:31)

**Screen (exact taps):**
1. Styles → the style → **Formal writing** → **Add essays & documents**. The **How to get them** guides are visible
   (`Photos of pages`, `Word, Pages, Google Docs`, `Copy and paste`); open **Photos of pages** for a second.
2. **Add screenshots or photos** → pick 3 photos of pages of an essay the author wrote (prepared before filming,
   see checklist) → Add. Wait for the count to update (`… paragraphs`).
3. Quick cut: **Add emails** → the guide list (`Screenshots (easiest)`, `Gmail as PDF`, `Many at once (computer)`) →
   **Add screenshots or photos** → 2–3 screenshots of emails the author sent.
4. The style card's **Formal writing** section now shows `Links ideas with: …`, `Opens with: …`, `Signs off with: …`.

**Voiceover:**
> Chats are how I text. For emails and essays, I add things I wrote myself: photos of old essays, a few sent emails.
> SaySo takes my voice from them, not their structure or content.

**Caption:** `Your own emails and essays → your formal voice` · `Essays teach voice, never structure · emails teach manner, never content`

**B-roll / edit:** right badge `Muse Spark 1.3 reads your pages`. Footer line: `Photos aren't stored. Quoted replies from
others are cut off.`

---

## 5 · Essay from your voice, then an email (1:31–2:00)

**Screen (exact taps):**
1. **Chat** tab → mode **Essay**. Field *Essay question or topic*: paste
   `Describe a project you are proud of and what you learned from it.` Stepper: `About 250 words`.
2. Tap **🎙** and speak the notes (about 15 s, sped up in the edit). Use real, non-private facts about this project,
   for example: *built SaySo alone in nine days for the Meta hackathon; a keyboard that writes like me; trained a LoRA
   on my own messages; GPU credits ran out, so I switched the writer to Muse Spark Open and measured what the style
   adds; learned to report results that didn't work.* Tap **■**: the transcript appears and is sent.
3. Wait (speed-ramped, real time shown). The answer shows the essay text and `N words`; scroll it slowly for 2 s.
4. Under it: **Make it stronger: answer one** with up to 3 questions. Tap one → tap **🎙** → answer in one sentence →
   send. The revised essay appears; hold 1.5 s.
5. Quick cut (5 s): mode **Email**. Paste a staged email from the second account into *The email you're answering (optional)*
   field (`Hi! Can you present SaySo at our meetup on Thursday at 6?`), 🎙 *"yes, I'll be there, ask if I should
   bring a laptop"* → the answer shows a **subject** line and the email. Tap **Copy subject** if visible.

**Voiceover:**
> Now an essay. I paste the question and just talk: what I built, what broke, what I learned. Muse Voice Transcribe
> writes it down. SaySo plans it and writes it in my formal voice, only from my own facts. No "in today's fast-paced
> world". Then it asks what would make it stronger. I answer out loud, and it's revised. Emails work the same way.

**Caption:** `🎙 Talk → Muse Voice Transcribe` · `Only your facts · in your formal voice · no AI clichés` ·
`"What would make it stronger?" → answer by voice` · `Email: subject + body, answering theirs`

**B-roll / edit:** right badge `Muse Voice Transcribe 1.0` while recording, then `Muse Spark 1.3 writes the essay ·
your formal voice`; for the email `Muse Spark Open writes the email`. If the essay is in Russian, the left panel shows
the English translation of its first paragraph only (no need to translate it all).

---

## 6 · It learns as you use it (2:00–2:14)

**Screen (exact taps):**
1. **Chat** tab. Mode **Write**, `For: Friends`, format `Message`. Type:
   `скажи, что опоздаю минут на 20, пробки` (*say I'll be ~20 min late, traffic*) → send.
2. Tap **👎** → bar `Fixing the last answer` and a row of reason chips (`Too long`, `Too formal`, `Not my words`, …).
   Type `shorter` and send (or tap **Too long**; typing matches the voiceover). The revised answer and the toast
   **`✨ Learned: …`** appear. Hold 1.5 s on the toast.
3. Cut: **Styles** → the style → **Learned from you** → a message just sent with SaySo's letter keys is at the top.
   Swipe it → **Delete** (or just show that you can).

**Voiceover:**
> Too long? Thumbs down: "shorter." It rewrites and remembers the rule. Every message I send with SaySo's keys becomes
> a new example right away, and I can delete any of them.

**Caption:** `👎 "shorter" → a rule for next time` · `What you send teaches it · see and delete it all`

**B-roll / edit:** zoom on the `Learned:` toast; right badge `Muse Spark Open revises · Muse Spark turns feedback into
a rule`. Keyboard learning is opt-in (`Learn from what I type` is on for filming, see checklist) and never learns
pasted text; beat 8 shows the toggle.

---

## 7 · How it works (2:14–2:33)

**Screen:** motion-graphic diagram (no phone), built in the editor:
```
screenshot · chat · photos ──► Muse Spark 1.3 (Meta Model API): reads, drafts replies, writes essays
draft · instruction · email ──► Muse Spark Open (Meta open weights): writes it in your style
🎙 voice note               ──► Muse Voice Transcribe 1.0: speech → text
                                ▲ style profile per audience × situation + your real messages
                                  + your formal voice + rules learned from you
your LoRA on Muse Glimmer 30B (Meta open weights): trained + benchmarked, waiting for a GPU
```
Then a number card (all numbers committed in `eval/results/`):
- `Form similarity to my real messages · generic Muse Spark 0.69 → with my style 0.94 · Muse Spark Open, live: 0.93`
- `My LoRA on Glimmer 30B: style gap 2.64 → 0.04 vs the base model`
Footnote: `40 held-out rewrites (style_gain*.json) · 499 held-out pairs (bench_2026-10-28.json)`.

**Voiceover:**
> Under the hood, four Meta models. Muse Spark Open, open weights, writes in my style. Muse Spark 1.3 reads
> screenshots. Muse Voice Transcribe listens. And my own LoRA on Muse Glimmer 30B is trained and benchmarked, waiting
> for a GPU.

**Caption:** `Spark Open writes · Spark 1.3 reads · Voice Transcribe listens · Glimmer 30B + your LoRA`

**B-roll:** a quick scroll through the style card (`~20 characters · 96% start lowercase…`) under the diagram.
If the blind test finished (TODO), add a line `Blind test: friends found the real reply N% (chance 33%) · fooled by
SaySo N% vs generic AI N% (n = …)`, from `eval/results/blind_test.json`.

---

## 8 · Privacy + close (2:33–2:48)

**Screen:** Styles → style card → bottom: **Delete style**; Keyboard tab: `Learn from what I type` toggle and its footer
(*off until you turn it on; only your own typing: pasted text, password, email, link, code and search fields are never
learned*). Then back to the Telegram chat; the friend
replies `😂 ок, понял` (*😂 ok, got it*) to the series. Fade to the end card: SaySo icon, `Write the way you'd say it.`,
`Built with Muse Spark Open · Muse Spark 1.3 · Muse Voice Transcribe · Muse Glimmer 30B`, repo URL.

**Voiceover:**
> Only my own writing is stored. Other people's messages, screenshots and voice notes are read in memory, then
> dropped. SaySo. Your words, your voice. And you always press send.

**Caption:** `Only your own writing is kept. Screenshots and voice notes aren't stored.` · `SaySo · Write the way you'd say it.`

---

## Filming checklist

### Content and consent
- [ ] **Staged chats only.** The Telegram chat in beats 1, 2, 8 is with a **consenting friend** (ask in writing first
      and keep their "yes") or the author's **second account**. Never a real third-party conversation on screen.
- [ ] The friend's display name is neutral (e.g. `Alex`) and the avatar is a placeholder. No phone numbers on screen.
- [ ] Clear the chat history above the staged messages (new chat or new second account), so no older messages show.
- [ ] Back Tap screenshot only contains the staged chat (it is sent to Muse Spark; nothing else should be on screen).
- [ ] WhatsApp export for beat 3: a chat whose other side consented, or the author's own second number.
      Names in "Which one is you?" and "Who are these chats with?" are blurred in the edit if they're real.
- [ ] Before filming, open the built style's self-check card and the style card: if any `You:` sample or example
      bubble contains a name, place, number or private fact, blur it in the edit (or rebuild with another chat).
- [ ] **Beat 4 material:** pick 3 essay pages and 2–3 sent emails the author wrote and doesn't mind on camera. Show the
      photo picker only briefly; blur names, addresses, grades and anything private on the pages and in the style
      card's `Opens with` / `Signs off with` lines (a greeting may contain a real name).
- [ ] **Beat 5:** the essay notes are about this project only (no school names, grades, family or health facts).
      The email being answered is staged from the second account.
- [ ] "Learned from you" list: clear older items before filming (they're the author's real messages).
- [ ] Nothing from `data/` is shown or committed; this file and the captions contain only invented demo lines.

### Phone setup
- [ ] **Do Not Disturb** (Focus) on; notifications for all other apps silenced; no banners during takes.
- [ ] Clean status bar: full battery (or charging icon hidden by cropping), Wi-Fi full, no VPN icon. iOS can't set
      9:41 on a device: either film around a neat time or cover the clock in the edit consistently in every shot.
- [ ] Light mode for all takes (or dark for all; don't mix). Default text size. Wallpaper plain.
- [ ] SaySo keyboard added, **Full Access** on (needed for the network), set as the active keyboard in Telegram.
      Keyboard settings: Audiences on, Formats include Series, `✨ gives 1–3 variants` = 3, `Learn from what I type` on.
- [ ] Microphone allowed for SaySo (Settings → SaySo), so 🎙 works on the first take.
- [ ] Back Tap: Settings → Accessibility → Touch → Back Tap → Double Tap → **Reply with SaySo** shortcut.
      Test it twice right before the take.
- [ ] The built style from beat 3 is the **active** (checked) style for beats 1, 2, 5, 6.

### Screen recording settings
- [ ] Control Center → Screen Recording, **microphone off** for beats without 🎙 (voiceover recorded separately, quiet
      room, phone mic or a lav; 48 kHz). For beat 5 the spoken notes may be kept quietly under the voiceover or muted.
- [ ] Record each beat as its own clip; 3 good takes of each live-model moment (✨, Back Tap, essay, 👎).
- [ ] The red recording pill in the status bar is fine; trim the Control Center opening/closing in the edit.
- [ ] Second camera (another phone) on a tripod for the **Back Tap finger shot** and the over-the-shoulder sends.

### Server and models (what writes must match what the video says)
- [ ] Deployed with `SAYSO_GPU=off` and `SAYSO_WRITER=open` (the default): Muse Spark Open writes, Muse Spark 1.3 reads.
- [ ] Before filming, run `eval/smoke_api.py --spark --show` once: the Baseten key (Muse Spark Open) and the Meta key
      (Muse Spark 1.3, Voice Transcribe) both answer. If Baseten is down, answers come from Spark 1.3 (the fallback):
      then change the ✨ and email badges to `Muse Spark 1.3` for those takes, or wait and refilm.
- [ ] Don't badge or say "my LoRA writes" over any live output: the LoRA is not hosted (no GPU credits).
- [ ] Latency: note the real wait for ✨, Back Tap (about 6–10 s) and the essay, and show it on the speed-ramp label.

### Numbers to update before the edit (TODO)
- [ ] **Self-check card** (beat 3): the design brief's example is `78% (generic AI 41%)`. Use the numbers the filmed
      style actually shows; update the voiceover and `captions.srt` to match.
- [ ] **Beat 7 card**: `0.69 → 0.94` is Muse Spark 1.3 generic → with profile + real messages, and `0.93` (chrF 50.4)
      is Muse Spark Open with the production prompt (`eval/results/style_gain.json`, `style_gain_open.json`; 40 held-out
      rewrites). `2.64 → 0.04` is the fingerprint gap of base Glimmer vs the user's LoRA (v1) on 499 held-out pairs
      (`eval/results/bench_2026-10-28.json`). If `style_gain.py` is rerun before the edit, use the new file's numbers.
- [ ] **Blind test** (beat 7, optional line): v2 shows a situation and three replies (real, SaySo, generic Muse Spark
      1.3). Use the found-the-real-reply rate (chance = 1/3) and the fooled-by-SaySo vs fooled-by-generic rates from
      `eval/results/blind_test.json` once it exists (aggregated only).

### Showing the Meta models (judging requires Meta models; bonus for open weights)
- [ ] Right-side badge in every model moment: ✨, series, email, 👎 revisions → `Muse Spark Open (Meta open weights)`;
      Back Tap and reading pages → `Muse Spark 1.3 (vision, Meta Model API)`; essay → `Muse Spark 1.3`;
      🎙 → `Muse Voice Transcribe 1.0`; self-check → `generic AI = Muse Spark without your style`.
- [ ] Say the model names out loud in beat 7 and keep all four on the end card. "Open weights" is said for Muse Spark
      Open and Glimmer.
- [ ] Optional 1 s insert: the server log line showing `meta-models/muse-spark-open-1026` answering. Blur keys, tokens
      and URLs with secrets.

### Edit and export
- [ ] Total ≤ 3:00 (target 2:48). Export 1080p, H.264, 30 fps; captions burned in **and** uploaded as `captions.srt`.
- [ ] English translation shown for every Russian line on screen (left panel).
- [ ] Final watch-through for names, numbers, notifications and keys before upload.
