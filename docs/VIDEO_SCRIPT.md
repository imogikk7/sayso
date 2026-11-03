# SaySo: demo video script (≤ 3:00)

Target runtime **2:54** (6 s of headroom under the 3:00 limit). Filmed on an iPhone 17 Pro, edited the same day.
Narration and captions in English; **the app's UI is in English for the demo** (Settings → Language → English).
Every Russian message on screen gets an English translation beside it (translated by Muse Spark 1.3, as CLAUDE.md
"Demo language" says). Captions file: [`docs/video/captions.srt`](video/captions.srt), in sync with the timeline below.

**Frame:** 16:9 (1920×1080). The phone's screen recording sits in the middle; the left side carries the English
translations of on-screen messages, the right side carries the model badge for the current step (e.g.
`Muse Spark Open · Meta open weights`). Keep the phone's own UI unedited.

**Which model writes what (say it the same way everywhere).** The live server runs with `SAYSO_GPU=off`:
- **Muse Spark Open** (Meta open weights, served by Baseten) writes in the user's style: ✨ in the keyboard, the chat's
  Write and Rewrite answers (message, series, official), emails, and revisions after 👎 or a follow-up like "in English".
- **Muse Spark 1.3** (Meta Model API) reads screenshots, pasted chats and photos of pages; its three drafts, written
  in the user's style, **are** the Back Tap replies and the chat's Reply answers. It writes essays, fixes voice-note
  transcripts and turns feedback into rules.
- **Muse Voice Transcribe 1.0** turns 🎙 notes into text.
- The user's **LoRA on Muse Glimmer 30B** is trained and benchmarked but **not hosted live** (no GPU credits), so never
  say or badge "my LoRA writes this" over a live output.

**Honesty rules for the edit**
- Every suggestion on screen is a real, live output. Never retype or edit a model's text; if a take is bad, run it again.
- Waiting time may be sped up, but say so on screen (`⏩ ×3 · real time 7 s`). Do not cut a wait to zero.
- Frame SaySo as *your own voice, you always press send*. Never "undetectable AI", never "AI that pretends to be you".
- The style card describes **how you write** (length, case, punctuation, slang, linking words), never personality.
- Numbers on screen come from `eval/results/*.json` or from the filmed screen itself. Never type a number that isn't
  in one of those.

## Timeline

| # | Beat | Start | End | Length |
|---|---|---|---|---|
| 0 | Hook: AI replies sound like AI | 0:00 | 0:07 | 7 s |
| 1 | Keyboard: draft → ✨ → variants → series stack | 0:07 | 0:31 | 24 s |
| 2 | Back Tap: one-tap install → screenshot → Choose from List → copied → paste | 0:31 | 0:55 | 24 s |
| 3 | Chat: a series as bubbles, stacked alternatives, "in English" revises it | 0:55 | 1:13 | 18 s |
| 4 | Styles by kind: chats → self-check; your own emails → Opens with / Signs off with | 1:13 | 1:35 | 22 s |
| 5 | Essay from a voice note → "Make it stronger" → Reply → Email | 1:35 | 1:59 | 24 s |
| 6 | 👎 Too long → Learned; what it learned is listed | 1:59 | 2:11 | 12 s |
| 7 | How it works: four Meta models, numbers, blind test | 2:11 | 2:38 | 27 s |
| 8 | Privacy + close | 2:38 | 2:54 | 16 s |
| | **Total** | | | **2:54** |

Narration pace: about 150 words a minute; each beat's voiceover below fits its slot with room to breathe.

---

## 0 · Hook (0:00–0:07)

**Screen:** Split screen. Left: a staged Telegram chat where a generic AI reply has been pasted
(`Конечно! Буду рад помочь. Давайте обсудим детали.` · *Of course! I'd be glad to help. Let's discuss the details.*).
Right: the same friend reacting with a single `🤖?` (staged, second account). Hard cut to the SaySo app icon.

**Voiceover:**
> Every AI reply sounds the same. Polite, tidy, nothing like you. My friends would spot it in a second.

**Caption (on screen):** `AI replies sound like AI. Not like you.`

---

## 1 · Keyboard: your voice in any messenger (0:07–0:31)

**Screen (exact taps):**
1. Telegram, staged chat with the friend (second account). Tap the message field. The SaySo keyboard is already the
   active one (if not: hold 🌐 → **SaySo**). It looks like the stock iOS keyboard, plus a strip on top.
2. The strip shows the audience chip **Friends** and the format chip **Message**. Type with **SaySo's own letter keys**
   (RU layout): `Привет, сегодня не получится прийти, задерживаюсь на работе. Давай перенесём на завтра?`
   (*Hi, I can't make it today, I'm stuck at work. Shall we move it to tomorrow?*)
3. Tap **✨**. Header `In your style · tap one to put it in`, then the variant cards replace the keys. Hold 2 s.
4. Tap **ⓧ** in the results header (*Back to the keys*): the draft is still in the field.
5. Tap the format chip **Message** → choose **Series**. Tap **✨**.
6. The result is a **stack** (the first message on top, the rest peeking underneath). Tap it → part 1 goes in → Send.
7. The header reads `Series · 1 of 3 sent`; the next card is marked **NEXT** (`Send this one, then tap the next`) →
   tap → Send. Repeat for the last part.

**Voiceover:**
> This is SaySo, a keyboard that writes the way you'd say it. I type a plain draft, tap the sparkle, and get versions
> in my own voice. And I don't send one long paragraph, I send bursts. So SaySo does too: a stack. Tap, send. Next. Send.

**Caption:** `Type a draft → ✨ → it sounds like you` · then `Series: sent part by part, like you do`

**B-roll / edit:** left panel shows the draft's English translation; when the variants appear, highlight in color what
changed: lowercase start, no period at the end, shorter length, emoji or `))`. Right badge during ✨:
`Muse Spark Open (Meta open weights) + your style`. Optional: second camera over the shoulder for the three sends.

---

## 2 · Back Tap: reply from a screenshot (0:31–0:55)

**Screen (exact taps):**
1. (3 s, filmed separately) SaySo → **Settings** tab → step 3 **Set up the Back Tap shortcut** → tap
   **Add the SaySo shortcut** → Shortcuts opens → **Add Shortcut**. (Back Tap itself is assigned in iOS Settings before
   filming, see checklist.)
2. In the staged Telegram chat, the friend (second account, consenting) has just sent:
   `Слушай, поможешь мне в субботу с переездом? Часов в 10 утра` (*Hey, can you help me move on Saturday? Around 10 am*).
3. **Double-tap the back of the iPhone.** The shortcut takes the screenshot.
4. Dialog **Who is it for?** → tap **Friends**.
5. Dialog **Anything to add? An instruction or some context, or leave it empty.** → type `politely decline, I'm busy` →
   **Done**.
6. Wait (about 6–10 s). **Choose from List** shows three replies → tap one. *Copy to Clipboard* copies it.
7. Back in Telegram: touch and hold the message field → **Paste** (allow the paste prompt if iOS shows it) → Send.

**Voiceover:**
> Setting it up is one tap. Then a friend asks for help on Saturday, and I can't. I double-tap the back of my phone,
> say who it's for and add a note: politely decline. Three replies, the way I would. Pick one, it's copied. Paste, send.

**Caption:** `One tap: Add the SaySo shortcut` · `Double-tap the back of the phone` · `Pick one → copied → paste`
· small footer: `The same replies also wait in the SaySo keyboard`

**B-roll / edit:** a screen recording can't show Back Tap, so cut to a **second camera**: a finger double-tapping the
back of the phone (0.7 s), then back to the screen. During the wait show `⏩ ×3 · real time N s` and the right badge
`Muse Spark 1.3 (vision, Meta Model API) reads the chat and writes 3 replies in your style`. Left panel: English
translation of the friend's message and of each reply in the list.

---

## 3 · Chat: series, stacks and memory (0:55–1:13)

**Screen (exact taps):**
1. SaySo → **Chat** tab (the SAY So logo on top). In SaySo's welcome message tap **Series** (the menus above the field
   now read **Write**, **Series**, **To Friends**).
2. Type: `расскажи друзьям про выходные в горах: было холодно, но очень красиво, хочу ещё`
   (*tell my friends about the weekend in the mountains: it was cold but really beautiful, I want to go again*) → ↑.
3. The answer is a run of 2–4 bubbles, each with its own copy button. Under **Or say it like this**, a series
   alternative is a collapsed stack with `+2`: tap it → it opens into cards → **Show less**.
4. Long-press the first bubble → **Copy** (show the menu for 1 s, then dismiss).
5. Type `in English` → ↑. The same series comes back in English: same points, same split.

**Voiceover:**
> In the app's chat it's the same voice. A story comes back the way I'd actually send it: in a few messages, each
> one copyable. Other versions fold into stacks. And it remembers the thread: "in English" changes this answer.

**Caption:** `A series = separate bubbles` · `Same thread: "in English" revises the last answer`

**B-roll / edit:** right badge `Muse Spark Open writes · your style`. Left panel: translation of the Russian bubbles
(the English revision needs none).

---

## 4 · Styles by kind (1:13–1:35)

**Screen (exact taps):** (build the WhatsApp style before filming, see checklist; film the start, then cut to the
finished one)
1. **Styles** tab (title **Your voice**) → tap the style pill under the title → **New style from chats…** → name
   `Me on WhatsApp` → **Add chat exports** → pick the WhatsApp export `.zip` → **Create style**.
2. **Which one is you?** → pick your own name. **Who are these chats with?** → the guess (`Friends`) → **Continue**.
   Stages tick off (speed-ramped ×20) → **Self-check** card (`SaySo: … / You: …` rows) → **Use this style**.
3. Back in Styles: the tabs at the top read **Messages · Emails · Essays**. Messages shows the "sounds like you"
   score next to `generic AI` and the audience cards (Partner, Friends, Family, Elders).
4. Tap the **Emails** tab (it says **Teach me**) → **Add emails** → **How to get them** → **Screenshots (easiest)** →
   **Add screenshots or photos** → pick 2–3 screenshots of emails the author sent.
5. The Emails tab now shows tone and length, **Opens with** and **Signs off with**; tap **Edit** on Signs off with for
   1 s to show it can be changed.

**Voiceover:**
> My voice comes from my own writing. Chats teach how I text: SaySo asks which one is me and tests itself on messages
> it hasn't seen. Emails and essays are their own kinds: my sent emails teach how I greet and sign off, never what
> they said.

**Caption:** `Only your side of the chat` · `Checked on messages it hasn't seen` ·
`Emails teach manner, never content · essays teach voice, never structure`

**B-roll / edit:** footnote on the self-check: `generic AI = Muse Spark without your style, same held-out messages`.
The score is whatever the filmed style shows; don't voice or caption a number. Right badge on step 4:
`Muse Spark 1.3 reads your screenshots · not stored`. Blur any name or private fact in the `You:` rows, the audience
bubbles and the Opens with / Signs off with lines (see checklist).

---

## 5 · Essay from your voice, then an email (1:35–1:59)

**Screen (exact taps):**
1. **Chat** tab → ✎ (new chat) → in the welcome message tap **Essay**. Field **Essay question or topic**: paste
   `Describe a project you are proud of and what you learned from it.` Length chip **250** (`about 250 words`).
2. The field is empty, so the round button is **🎙**: tap it and speak the notes (about 15 s, sped up in the edit).
   Use real, non-private facts about this project, for example: *built SaySo alone in nine days for the Meta hackathon;
   a keyboard that writes like me; trained a LoRA on my own messages; GPU credits ran out, so I switched the writer to
   Muse Spark Open and measured what the style adds; learned to report results that didn't work.* Tap **■**: the
   transcript is sent.
3. Wait (speed-ramped, real time shown). The essay appears with `N words` under it; scroll slowly for 2 s.
4. Under it: **Make it stronger: answer one** → tap one question → 🎙 → answer in one sentence → ■. The revised essay
   appears; hold 1.5 s.
5. Quick cut (5 s): mode menu **Reply**, kind menu **Email** (placeholder *The email you got*). Paste a staged email
   from the second account: `Hi! Can you present SaySo at our meetup on Thursday at 6?` → ↑. The answer shows a
   **Subject:** line with **Copy subject**, then the email.

**Voiceover:**
> Now an essay. I paste the question and just talk. Muse Voice Transcribe writes it down; SaySo writes it in my
> formal voice, only from my facts, at the length I asked. Then it asks what would make it stronger. Emails too.

**Caption:** `🎙 Talk → Muse Voice Transcribe` · `Only your facts · your formal voice · ±10% of the length` ·
`"Make it stronger" → answer by voice` · `Reply → Email: subject + body`

**B-roll / edit:** right badge `Muse Voice Transcribe 1.0` while recording, then `Muse Spark 1.3 writes the essay ·
your formal voice`; for the email `Muse Spark Open writes the email`. If the essay is in Russian, the left panel shows
the English translation of its first paragraph only.

---

## 6 · It learns as you use it (1:59–2:11)

**Screen (exact taps):**
1. **Chat** → ✎ → **Message**, **To Friends**. Type `скажи, что опоздаю минут на 20, пробки`
   (*say I'll be ~20 min late, traffic*) → ↑.
2. Tap **👎** → bar **What should change?** with reason chips → tap **Too long**. The shorter answer appears; when a
   lasting rule was taken, a toast **Learned: …** shows. Hold 1.5 s on it. (No toast in a take? Use another take; never
   add one in the edit.)
3. Cut: **Styles** → **Messages** → scroll to **SaySo learned from you**: the new rule is listed; touch and hold it to
   show **Forget**.

**Voiceover:**
> Too long? Thumbs down. It rewrites, and remembers the rule for next time. Everything it learns is listed, and I can
> forget any of it.

**Caption:** `👎 "Too long" → a rule for next time` · `See and delete what it learned`

**B-roll / edit:** zoom on the toast; right badge `Muse Spark Open revises · Muse Spark 1.3 turns feedback into a rule`.

---

## 7 · How it works, and does it work (2:11–2:38)

**Screen:** motion-graphic diagram (no phone), built in the editor:
```
draft · instruction · email ──► Muse Spark Open (Meta open weights): writes it in your style
screenshot · chat · photos  ──► Muse Spark 1.3 (Meta Model API): reads, writes replies in your style, writes essays
🎙 voice note               ──► Muse Voice Transcribe 1.0: speech → text
                                ▲ style profile per audience × situation + your real messages
                                  + your formal voice + rules learned from you
your LoRA on Muse Glimmer 30B (Meta open weights): trained + benchmarked, waiting for a GPU
```
Then a number card (every number is committed in `eval/results/`):
- `Form similarity to my real messages · generic Muse Spark 0.69 → with my style 0.94 · Muse Spark Open, live: 0.93`
- `My LoRA on Glimmer 30B: style gap 2.64 → 0.04 vs the base model`
- `Blind test · 5 friends · 100 answers · accuracy 53% (chance 50%) · "a person wrote it": my real messages 62%,
  SaySo's 56% · small sample`

Footnote: `40 held-out rewrites (style_gain*.json) · 499 held-out pairs (bench_2026-10-28.json) · blind_test.json:
10 real + 10 SaySo messages, friends & family, Russian only`.

**Voiceover:**
> Under the hood, four Meta models. Muse Spark Open, open weights, writes in my style. Muse Spark 1.3 reads. Muse
> Voice Transcribe listens. My own LoRA on Muse Glimmer is trained, waiting for a GPU. In a blind test, five friends
> guessed right fifty-three percent of the time. Chance is fifty.

**Caption:** `Spark Open writes · Spark 1.3 reads · Voice Transcribe listens · Glimmer 30B + your LoRA` ·
`Blind test: friends guessed right 53% of the time (chance 50%)`

**B-roll:** a quick scroll through the style card (`~20 characters · starts lowercase…`) under the diagram.

---

## 8 · Privacy + close (2:38–2:54)

**Screen:** **Keyboard** tab → the **Learn from what I type** toggle and its footer (*Only your own typing: pasted text,
password, email, link, code and search fields are never learned. Off until you turn it on.*). Then Styles → the style
card → bottom: **Delete style** (don't confirm). Then back to the Telegram chat; the friend replies `😂 ок, понял`
(*😂 ok, got it*) to the series. Fade to the end card: SaySo icon, `Write the way you'd say it.`,
`Built with Muse Spark Open · Muse Spark 1.3 · Muse Voice Transcribe · Muse Glimmer 30B`, repo URL.

**Voiceover:**
> Only my own writing is stored. Other people's messages, screenshots and voice notes are read, then dropped.
> SaySo. Your words, your voice. And you always press send.

**Caption:** `Only your own writing is kept. Screenshots and voice notes aren't stored.` · `SaySo · Write the way you'd say it.`

---

## Filming checklist

### Content and consent
- [ ] **Staged chats only.** The Telegram chat in beats 1, 2, 8 is with a **consenting friend** (ask in writing first
      and keep their "yes") or the author's **second account**. Never a real third-party conversation on screen.
- [ ] The friend's display name is neutral (e.g. `Alex`) and the avatar is a placeholder. No phone numbers on screen.
- [ ] Clear the chat history above the staged messages (new chat or new second account), so no older messages show.
- [ ] Back Tap screenshot only contains the staged chat (it is sent to Muse Spark 1.3; nothing else should be on screen).
- [ ] WhatsApp export for beat 4: a chat whose other side consented, or the author's own second number.
      Names in **Which one is you?** and **Who are these chats with?** are blurred in the edit if they're real.
- [ ] Before filming, open the built style's self-check card, the audience cards and the Emails tab: if any `You:`
      sample, example bubble, greeting or sign-off contains a name, place, number or private fact, blur it in the edit.
- [ ] **Beat 4 emails:** 2–3 emails the author sent and doesn't mind on camera. Show the photo picker only briefly.
- [ ] **Beat 5:** the essay notes are about this project only (no school names, grades, family or health facts).
      The email being answered is staged from the second account.
- [ ] "SaySo learned from you" and "Learned from you": clear older items before filming (they're the author's real
      messages and rules).
- [ ] Nothing from `data/` is shown or committed; this file and the captions contain only invented demo lines.

### Phone setup
- [ ] **Settings → Language → English** in SaySo (then close and reopen SaySo, so the shortcut dialogs are in English).
- [ ] **Do Not Disturb** (Focus) on; notifications for all other apps silenced; no banners during takes.
- [ ] Clean status bar: full battery, Wi-Fi full, no VPN icon. iOS can't set 9:41 on a device: film around a neat time
      or cover the clock in the edit consistently in every shot.
- [ ] Light mode for all takes (or dark for all; don't mix). Default text size. Wallpaper plain.
- [ ] SaySo keyboard added, **Full Access** on (needed for the network), set as the active keyboard in Telegram.
      Keyboard tab: Audiences on, Formats include Series, variants = 3, `Learn from what I type` on.
- [ ] Microphone allowed for SaySo (Settings → SaySo), so 🎙 works on the first take.
- [ ] Shortcut installed with **Add the SaySo shortcut**; Back Tap: Settings → Accessibility → Touch → Back Tap →
      Double Tap → that shortcut. Test it twice right before the take, including the Paste in Telegram.
- [ ] The style built in beat 4 is the **active** style (checkmark in the style pill) for beats 1, 2, 3, 5, 6.

### Screen recording settings
- [ ] Control Center → Screen Recording, **microphone off** for beats without 🎙 (voiceover recorded separately, quiet
      room, 48 kHz). For beat 5 the spoken notes may be kept quietly under the voiceover or muted.
- [ ] Record each beat as its own clip; 3 good takes of each live-model moment (✨, Back Tap, chat series, essay, 👎).
- [ ] Second camera (another phone) on a tripod for the **Back Tap finger shot** and the over-the-shoulder sends.

### Server and models (what writes must match what the video says)
- [ ] Deployed with `SAYSO_GPU=off` and `SAYSO_WRITER=open` (the default): Muse Spark Open writes, Muse Spark 1.3 reads
      and writes the replies.
- [ ] Before filming, run `eval/smoke_api.py --spark --show` once: the Baseten key (Muse Spark Open) and the Meta key
      (Muse Spark 1.3, Voice Transcribe) both answer. If Baseten is down, answers come from Spark 1.3 (the fallback):
      then change the ✨, chat and email badges to `Muse Spark 1.3` for those takes, or wait and refilm.
- [ ] Don't badge or say "my LoRA writes" over any live output: the LoRA is not hosted (no GPU credits).
- [ ] Latency: note the real wait for ✨, Back Tap (about 6–10 s) and the essay, and show it on the speed-ramp label.

### Numbers (check before the edit)
- [ ] **Self-check score** (beat 4): shown on screen only, whatever the filmed style shows; not voiced or captioned.
- [ ] **Beat 7 card**: `0.69 → 0.94` is Muse Spark 1.3 generic → with profile + real messages, and `0.93` (chrF 50.4)
      is Muse Spark Open with the production prompt (`eval/results/style_gain.json`, `style_gain_open.json`; 40 held-out
      rewrites). `2.64 → 0.04` is the fingerprint gap of base Glimmer vs the user's LoRA (v1) on 499 held-out pairs
      (`eval/results/bench_2026-10-28.json`).
- [ ] **Blind test** (beat 7): from `eval/results/blind_test.json`: 5 people, 100 answers, accuracy 0.53
      (`p_accuracy_vs_half` 0.62), «Человек» for real 0.62 vs SaySo 0.56, difference CI −0.13…+0.24, Fisher p 0.68.
      Say "small sample" on screen. Don't say "indistinguishable" or "fooled": say "couldn't reliably tell".

### Showing the Meta models (judging requires Meta models; bonus for open weights)
- [ ] Right-side badge in every model moment: ✨, chat series, "in English", email, 👎 revisions →
      `Muse Spark Open (Meta open weights)`; Back Tap and reading screenshots → `Muse Spark 1.3 (vision, Meta Model
      API)`; essay → `Muse Spark 1.3`; 🎙 → `Muse Voice Transcribe 1.0`; self-check → `generic AI = Muse Spark without
      your style`.
- [ ] Say the model names out loud in beat 7 and keep all four on the end card. "Open weights" is said for Muse Spark
      Open and Glimmer.

### Edit and export
- [ ] Total ≤ 3:00 (target 2:54). Export 1080p, H.264, 30 fps; captions burned in **and** uploaded as `captions.srt`.
- [ ] English translation shown for every Russian line on screen (left panel).
- [ ] Final watch-through for names, numbers, notifications and keys before upload.
