# SaySo: demo video script (≤ 3:00)

Target runtime **2:50** (10 s of headroom under the 3:00 limit). Filmed Nov 3 on an iPhone 17 Pro, edited the same day.
Narration and captions in English; every Russian message on screen gets an English translation beside it
(translated by Muse Spark 1.3, as CLAUDE.md "Demo language" says). Captions file: [`docs/video/captions.srt`](video/captions.srt).

**Frame:** 16:9 (1920×1080). The phone's screen recording sits in the middle; the left side carries the English
translations of on-screen messages, the right side carries the model badge for the current step (e.g.
`Muse Spark 1.3 · Meta Model API`). Keep the phone's own UI unedited.

**Honesty rules for the edit**
- Every suggestion on screen is a real, live output. Never retype or edit a model's text; if a take is bad, run it again.
- Waiting time may be sped up, but say so on screen (`⏩ ×3 · real time 7 s`). Do not cut a wait to zero.
- Frame SaySo as *your own voice, you always press send*. Never "undetectable AI", never "AI that pretends to be you".
- The style card describes **how you write** (length, case, punctuation, slang), never personality.

## Timeline

| # | Beat | Start | End | Length |
|---|---|---|---|---|
| 0 | Hook: AI replies sound like AI | 0:00 | 0:10 | 10 s |
| 1 | Keyboard: draft → ✨ → 3 variants → series stack | 0:10 | 0:45 | 35 s |
| 2 | Back Tap in Telegram → replies → paste | 0:45 | 1:15 | 30 s |
| 3 | Add a style from a WhatsApp export → self-check | 1:15 | 1:45 | 30 s |
| 4 | Chat feedback 👎 "shorter" → Learned; keyboard learns | 1:45 | 2:10 | 25 s |
| 5 | How it works (Meta models, numbers) | 2:10 | 2:30 | 20 s |
| 6 | Privacy | 2:30 | 2:40 | 10 s |
| 7 | Close | 2:40 | 2:50 | 10 s |
| | **Total** | | | **2:50** |

Narration pace: about 150 words a minute; each beat's voiceover below fits its slot with room to breathe.

---

## 0 · Hook (0:00–0:10)

**Screen:** Split screen. Left: a staged Telegram chat where a generic AI reply has been pasted
(`Конечно! Буду рад помочь. Давайте обсудим детали.` · *Of course! I'd be glad to help. Let's discuss the details.*).
Right: the same friend reacting with a single `🤖?` (staged, second account). Hard cut to the SaySo app icon on the home screen.

**Voiceover:**
> Every AI reply sounds the same. Polite, tidy, and nothing like you. My friends would spot it in a second.

**Caption (on screen):** `AI replies sound like AI. Not like you.`

**B-roll:** close-up of a thumb hovering over Send, then pulling back. App icon tap with a soft zoom into the Styles tab.

---

## 1 · Keyboard: your voice in any messenger (0:10–0:45)

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
> This is SaySo, a keyboard that writes the way you'd say it. I type a plain draft… tap the sparkle… and get three
> versions in my own voice. And I don't send one long paragraph, I send bursts. So SaySo does too: a series,
> stacked like notifications. Tap, send. Next. Send. Same meaning, my rhythm.

**Caption:** `Type a draft → ✨ → it sounds like you` · then `Series: sent part by part, like you do`

**B-roll / edit:** left panel shows the draft's English translation; when the variants appear, highlight in color what
changed: lowercase start, no period at the end, shorter length, emoji or `))`. Right badge during ✨:
`Your LoRA on Muse Glimmer 30B`. Optional: second camera over the shoulder for the three sends (bubbles popping up).

---

## 2 · Back Tap: reply from a screenshot (0:45–1:15)

**Screen (exact taps):**
1. In the staged Telegram chat, the friend (second account, consenting) has just sent:
   `Слушай, поможешь мне в субботу с переездом? Часов в 10 утра` (*Hey, can you help me move on Saturday? Around 10 am*).
2. **Double-tap the back of the iPhone** (Back Tap → "Reply with SaySo" shortcut). The shortcut takes the screenshot.
3. System dialog **"Who is it for?"** → tap **Friends**.
4. Dialog **"Anything to add? …"** → type `politely decline, I'm busy` → Done.
5. Wait (~6–8 s). The system **list of replies** appears (Choose from List). Tap the one you like → it's copied.
6. Back in Telegram: long-press the message field → **Paste** (allow the paste prompt if iOS shows it) → Send.

**Voiceover:**
> A friend asks for help on Saturday, and I can't. I double-tap the back of my phone. SaySo grabs the screen and asks
> who it's for. I add a note: politely decline, I'm busy. Muse Spark reads the chat, my own model writes the replies.
> Pick one, paste, send. I never left Telegram.

**Caption:** `Double-tap the back of the phone` · `Note: "politely decline, I'm busy"` · `Pick → paste → send`

**B-roll / edit:** a screen recording can't show Back Tap, so cut to a **second camera**: a finger double-tapping the
back of the phone (0.7 s), then back to the screen. During the wait show `⏩ ×3 · real time N s` and the right badge
`Muse Spark 1.3 (vision) reads the screenshot` → `Your LoRA on Muse Glimmer 30B writes`. Left panel: English
translation of the friend's message and of each reply in the list.

---

## 3 · Add a style from your own chats (1:15–1:45)

**Screen (exact taps):** (build the real style before filming, see checklist; film the start, then cut to the finished one)
1. SaySo app → **Styles** tab → **+ Add style**. Name: `Me on WhatsApp`.
2. **Add chat exports** → pick the WhatsApp export (`.zip` made with *Export Chat → Without Media*). The file shows in the
   list with its size → Continue.
3. **"Which one is you?"** → pick your own name. **"Who are these chats with?"** → the AI's guess is already set
   (`Friends`) → **Continue**.
4. Stages tick off: `Reading your files…` → `Learning how you react…` → `Building your profile…` → `Self-check` → `Ready`.
5. **Self-check card**: `Sounds like you 78% (generic AI 41%)`, `Makes sense 4.6/5`, 2–3 rows `SaySo: … / You: …`.
   Tap **Use this style**.

**Voiceover:**
> Where does my voice come from? My own chats. I export one from WhatsApp and drop it in. SaySo asks which one is me:
> it only learns from my side. It reads how I react, builds my profile, then tests itself on messages it hasn't seen.
> Sounds like me: seventy-eight percent. Generic AI: forty-one.

**Caption:** `Only your side of the chat` · `Self-check on messages it never saw` ·
`Sounds like you 78% · generic AI 41%` (TODO: use the numbers from the filmed run)

**B-roll / edit:** speed-ramp the stages (`⏩ ×20`). On the self-check card, split the frame: left `Generic AI` reply,
right `SaySo` reply to the same held-out message, with the form features highlighted in color (length, end punctuation,
lowercase start, laughter/emoji, swearing). Footnote: `generic AI = Muse Spark 1.3 with no style, same messages`.
Blur any name or personal fact in the `You:` rows (see checklist).

---

## 4 · It learns as you use it (1:45–2:10)

**Screen (exact taps):**
1. **Chat** tab. Mode **Write**, `For: Friends`, format `Message`. Type:
   `скажи, что опоздаю минут на 20, пробки` (*say I'll be ~20 min late, traffic*) → send.
2. The answer appears (if it's already short, ask for something longer first, e.g. add *and that I'll bring snacks*).
   Tap **👎** → bar `Fixing the last answer` → type `shorter` → send.
3. The revised answer appears and the toast **`✨ Learned: …`** slides in at the top. Hold 1.5 s on the toast.
4. Cut: keyboard in Telegram, type a short message with SaySo's letter keys → Send.
5. Cut: **Styles** → tap the style → scroll to **Learned from you** → the message just sent is at the top.
   Swipe it → **Delete** (or just show that you can).

**Voiceover:**
> And it keeps learning. Too long? Thumbs down: "shorter." It rewrites, and remembers the rule for next time.
> Every message I send with SaySo's keyboard becomes a new example right away. And I can delete any of them.

**Caption:** `👎 "shorter" → a rule for next time` · `What you send teaches it, instantly` · `You can see and delete it all`

**B-roll / edit:** zoom on the `Learned:` toast; right badge `Muse Spark 1.3 turns feedback into a rule`.

---

## 5 · How it works (2:10–2:30)

**Screen:** motion-graphic diagram (no phone), built in the editor:
```
screenshot / draft ──► Muse Spark 1.3 (Meta Model API): reads the chat, drafts what you'd mean
                    ──► your LoRA on Muse Glimmer 30B (Meta open weights): says it in your words
                        ▲ style profile per audience × situation + your real examples + learned rules
```
Then a number card:
`Form similarity  0.67 → 0.94` · `chrF  41 → 51` (label: `without → with your style`)
(TODO: confirm both numbers and their source before the edit, see checklist.)

**Voiceover:**
> Under the hood: Meta's Muse Spark 1.3 reads the chat and drafts. My own LoRA on Muse Glimmer 30B puts it in my words,
> guided by my style profile and real examples. Form similarity goes from 0.67 to 0.94; chrF from 41 to 51.

**Caption:** `Muse Spark 1.3 reads · Muse Glimmer 30B + your LoRA writes` · `0.67 → 0.94 form · chrF 41 → 51`

**B-roll:** a quick scroll through the style card (`~20 characters · 96% start lowercase…`) under the diagram.
If the blind test finished (TODO), swap the chrF line for `Friends picked SaySo as "you" N% of the time (blind test, n = …)`.

---

## 6 · Privacy (2:30–2:40)

**Screen:** Styles → style card → bottom: **Delete style**; Keyboard tab: `Learn from what I type` toggle and its footer
(*Only your own text; never password, email, link, code or search fields*).

**Voiceover:**
> Only my own messages are stored. Other people's messages and screenshots are read in memory, then dropped.

**Caption:** `Only your own messages are kept. Screenshots aren't stored. Delete anytime.`

---

## 7 · Close (2:40–2:50)

**Screen:** back to the Telegram chat; the friend replies `😂 ок, понял` (*😂 ok, got it*) to the series. Fade to the
end card: SaySo icon, `Write the way you'd say it.`, `Built with Muse Spark 1.3 · Muse Glimmer 30B`, repo URL.

**Voiceover:**
> SaySo. Your words, your voice. And you always press send.

**Caption:** `SaySo · Write the way you'd say it.`

---

## Filming checklist

### Content and consent
- [ ] **Staged chats only.** The Telegram chat in beats 1, 2, 7 is with a **consenting friend** (ask in writing first
      and keep their "yes") or the author's **second account**. Never a real third-party conversation on screen.
- [ ] The friend's display name is neutral (e.g. `Alex`) and the avatar is a placeholder. No phone numbers on screen.
- [ ] Clear the chat history above the staged messages (new chat or new second account), so no older messages show.
- [ ] Back Tap screenshot only contains the staged chat (it is sent to Muse Spark; nothing else should be on screen).
- [ ] WhatsApp export for beat 3: a chat whose other side consented, or the author's own second number.
      Names in "Which one is you?" and "Who are these chats with?" are blurred in the edit if they're real.
- [ ] Before filming, open the built style's self-check card and the style card: if any `You:` sample or example
      bubble contains a name, place, number or private fact, blur it in the edit (or rebuild with another chat).
- [ ] "Learned from you" list: clear older items before filming (they're the author's real messages).
- [ ] Nothing from `data/` is shown or committed; this file and the captions contain only invented demo lines.

### Phone setup
- [ ] **Do Not Disturb** (Focus) on; notifications for all other apps silenced; no banners during takes.
- [ ] Clean status bar: full battery (or charging icon hidden by cropping), Wi-Fi full, no VPN icon. iOS can't set
      9:41 on a device: either film around a neat time or cover the clock in the edit consistently in every shot.
- [ ] Light mode for all takes (or dark for all; don't mix). Default text size. Wallpaper plain.
- [ ] SaySo keyboard added, **Full Access** on (needed for the network), set as the active keyboard in Telegram.
      Keyboard settings: Audiences on, Formats include Series, `✨ gives 1–3 variants` = 3, `Learn from what I type` on.
- [ ] Back Tap: Settings → Accessibility → Touch → Back Tap → Double Tap → **Reply with SaySo** shortcut.
      Test it twice right before the take.
- [ ] The built style from beat 3 is the **active** (checked) style for beats 1, 2, 4.

### Screen recording settings
- [ ] Control Center → Screen Recording, **microphone off** (voiceover recorded separately, quiet room, phone mic or
      a lav; 48 kHz).
- [ ] Record each beat as its own clip; 3 good takes of each live-model moment (✨, Back Tap, 👎).
- [ ] The red recording pill in the status bar is fine; trim the Control Center opening/closing in the edit.
- [ ] Second camera (another phone) on a tripod for the **Back Tap finger shot** and the over-the-shoulder sends.

### Server and models (the outputs must really be the user's model)
- [ ] 10 min before filming: call `/warmup` (button in the app or `curl`), set scaledown to 20 min while filming.
- [ ] Check a test `/rewrite` returns **`styled: true`** (the LoRA wrote it). While the GPU is cold, answers come from
      Muse Spark alone (`styled: false`): don't film those for beats 1–2, the voiceover says "my own model writes".
- [ ] Film all GPU shots (beats 1, 2, 4) in one warm session; then let it scale down.
- [ ] Latency: note the real wait for Back Tap (target 6–8 s) and show it on the speed-ramp label.

### Numbers to update before the edit (TODO)
- [ ] **Self-check card** (beat 3): the design brief's example is `78% (generic AI 41%)` and `Makes sense 4.6/5`.
      Use the numbers the filmed style actually shows; update the voiceover and `captions.srt` to match.
- [ ] **Form similarity 0.67 → 0.94, chrF 41 → 51** (beat 5): confirm the source file, the test set and what
      "without → with style" compares. These figures are not in `eval/results/bench_*.json` in this repo (those report
      fingerprint distance and chrF ≈ 13 → 30 for base → v2 on 499 test pairs), so commit the aggregated result
      that produces them, or switch the card to the committed numbers.
- [ ] **Blind test** (beat 5, optional swap): `Friends picked SaySo as "you" N% (n = …)` from
      `eval/results/blind_test.json` once it exists (aggregated only).

### Showing the Meta models (judging requires Meta models)
- [ ] Right-side badge in every model moment: ✨ and series → `Your LoRA on Muse Glimmer 30B (Meta open weights)`;
      Back Tap → `Muse Spark 1.3 (vision, Meta Model API) reads` then `Glimmer LoRA writes`; 👎 → `Muse Spark 1.3`;
      self-check → `generic AI = Muse Spark 1.3 without your style`.
- [ ] Say both names out loud in beat 5 ("Muse Spark 1.3", "Muse Glimmer 30B") and keep them on the end card.
- [ ] Optional 1 s insert: the server log line or the Modal/Baseten dashboard showing the Glimmer + LoRA deployment.
      Blur keys, tokens and URLs with secrets.

### Edit and export
- [ ] Total ≤ 3:00 (target 2:50). Export 1080p, H.264, 30 fps; captions burned in **and** uploaded as `captions.srt`.
- [ ] English translation shown for every Russian line on screen (left panel).
- [ ] Final watch-through for names, numbers, notifications and keys before upload.
