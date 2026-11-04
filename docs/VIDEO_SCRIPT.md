# SaySo: demo video script (≤ 3:00)

Filmed on an iPhone 17 Pro in **WhatsApp** (staged chats with a consenting friend, who is not named anywhere), edited
on Nov 4. Narration in the owner's cloned voice, in English; captions in English. **The app's UI is in English for the
demo** (Settings → Language → English). Every Russian message on screen gets an English translation beside it
(translated by Muse Spark 1.3, as CLAUDE.md "Demo language" says). Final timings and caption text live in the edit
(`docs/video/captions.srt`, maintained by the video edit); the voice lines below are the source for both.

**Frame:** 16:9 (1920×1080). The phone's screen recording sits in the middle; the left side carries the English
translations of on-screen messages, the right side carries the model badge for the current step. Keep the phone's own
UI unedited.

**Which model writes what in this video.** Filmed with the GPU on (`SAYSO_GPU=modal`: the user's LoRA on Muse Glimmer
30B served by vLLM on a temporary H100 on Modal):
- **Keyboard ✨**: written live by **the user's LoRA on Muse Glimmer 30B** (5 candidates, the reranker picks one).
- **Back Tap → replies**: **Muse Spark 1.3** reads the screenshot and drafts three replies; **the LoRA** restyles
  each draft in the user's voice.
- **In-app chat** (the story as a series, "in English", 👎 revisions): **Muse Spark Open**.
- **Essays**: **Muse Spark 1.3**. **Voice notes**: **Muse Voice Transcribe 1.0**.
- **Style build** (tagging the chats, the self-check judge) and reading email screenshots: **Muse Spark 1.3**.

Day to day the server runs with `SAYSO_GPU=off` (no GPU credits), and then Muse Spark Open writes the ✨ suggestions
and the replies are Spark 1.3's own drafts. The video doesn't claim otherwise: the end card's footnote says the LoRA
ran on a temporary H100 for the recording.

**Honesty rules for the edit**
- Every suggestion on screen is a real, live output. Never retype or edit a model's text; if a take is bad, run it again.
- **No speed-ups**: model waits play at real speed, so there are no speed-up labels. Dead air may be trimmed only
  before a tap, never between a tap and the answer appearing. The one exception is the **style build in beat 4**,
  shown as a time-lapse (the build really takes a few minutes: it tags at most 500 turns, about 2–4 min).
- Frame SaySo as *your own voice, you always press send*. Never "undetectable AI", never "AI that pretends to be you",
  never "fools people".
- The style card describes **how you write** (length, case, punctuation, slang, linking words), never personality.
- Numbers on screen come from `eval/results/*.json` or from the filmed screen itself. Never type a number that isn't
  in one of those.
- No swearing on screen: the server runs with `SAYSO_CLEAN=on` (the default), so nothing SaySo writes swears.

## Timeline

Target lengths; the final cut decides the exact times.

| # | Beat | Length |
|---|---|---|
| 0 | Hook: the AI reply your friend spotted | ~7 s |
| 1 | Keyboard: what I mean → ✨ → my wording → series stack, tap, send, next | ~24 s |
| 2 | Back Tap: screenshot → who's it for, what to say → three replies → paste | ~22 s |
| 3 | Chat: a story as real messages, then "in English" | ~17 s |
| 4 | Where the voice comes from: chats (time-lapse build) and emails | ~20 s |
| 5 | Essay from a voice note → "Make it stronger" | ~22 s |
| 6 | 👎 Too casual → fixed → learned | ~10 s |
| 7 | Under the hood: four Meta models, the blind test | ~22 s |
| 8 | Close | ~10 s |
| | **Total** | **~2:34** (under 3:00) |

---

## 0 · Hook

**Screen:** A staged WhatsApp chat: a generic AI reply has been sent
(`Конечно! Буду рад помочь. Давайте обсудим детали.` · *Of course! I'd be glad to help. Let's discuss the details.*),
and the friend answers with a single `🤖?` (staged). Hard cut to the SaySo app icon.

**Voiceover:**
> Ever sent an AI reply… and your friend instantly knew? Yeah. Me too.

**Caption:** `Ever sent an AI reply… and your friend instantly knew?`

---

## 1 · Keyboard: a keyboard that texts like me

**Screen (exact taps):**
1. WhatsApp, the staged chat. Tap the message field. The SaySo keyboard is the active one (if not: hold 🌐 →
   **SaySo**). It looks like the stock iOS keyboard, plus a strip on top.
2. The strip shows the audience chip **Friends** and the format chip **Message**. Type with **SaySo's own letter keys**
   what you mean, plainly (for example `Привет, сегодня не получится прийти, задерживаюсь на работе. Давай перенесём
   на завтра?` · *Hi, I can't make it today, I'm stuck at work. Shall we move it to tomorrow?*).
3. Tap **✨**. Header `In your style · tap one to put it in`, then the variant cards replace the keys. Tap one: it
   replaces the draft.
4. Format chip → **Series** → **✨**. The result is a **stack**. Tap it → part 1 goes in → Send. The header reads
   `Series · 1 of 3 sent`, the next card is marked **NEXT** → tap → Send.

**Voiceover:**
> So I built SaySo. A keyboard that texts like me. I type what I mean, tap the sparkle, and my own model writes it the
> way I'd actually say it. Even in bursts. Tap, send, next.

**Caption:** `SaySo: a keyboard that texts like me` · `Type what you mean → ✨` · `Even in bursts: tap, send, next`

**Badge (right):** `Your LoRA on Muse Glimmer 30B (Meta open weights) · live on a temporary H100`

**Edit:** left panel shows the draft's English translation; when the variants appear, highlight in color what
changed: lowercase start, no period at the end, shorter length, emoji or `))`. Over-the-shoulder second camera for
the sends is optional.

---

## 2 · Back Tap: replies from a screenshot

**Screen (exact taps):**
1. In the staged WhatsApp chat, the friend has just sent
   `Слушай, поможешь мне в субботу с переездом? Часов в 10 утра` (*Hey, can you help me move on Saturday? Around 10 am*).
   The keyboard is closed.
2. **Double-tap the back of the phone.** The SaySo shortcut takes the screenshot.
3. Dialog **Who is it for?** → **Friends**. Dialog **Anything to add?** → type what to say (for example
   `politely decline, I'm busy`) → **Done**.
4. Wait at real speed. **Choose from List** shows three replies → tap one → *Copy to Clipboard* copies it.
5. Back in WhatsApp: touch and hold the message field → **Paste** → Send.

**Voiceover:**
> No keyboard? Double-tap the back of the phone. Who's it for, what should I say. Three replies in my voice. Pick one, paste,
> done.

**Caption:** `No keyboard? Double-tap the back of the phone` · `Who's it for · what to say` · `3 replies in my voice → paste`

**Badge (right):** `Muse Spark 1.3 reads the chat · your LoRA rewrites the replies in your voice`

**Edit:** a screen recording can't show the button press, so cut to a **second camera**: a finger pressing the Action
Button (under a second), then back to the screen. Left panel: English translation of the friend's message and of
each reply in the list.

---

## 3 · Chat: a story as real messages

**Screen (exact taps):**
1. SaySo → **Chat** tab. In SaySo's welcome message tap **Series** (menus read **Write**, **Series**, **To Friends**).
2. Ask for a story, for example `расскажи друзьям про выходные в горах: было холодно, но очень красиво, хочу ещё`
   (*tell my friends about the weekend in the mountains: it was cold but really beautiful, I want to go again*) → ↑.
3. The answer is a run of 2–4 bubbles, each with its own copy button.
4. Type `in English` → ↑. The same series comes back in English: same points, same split.

**Voiceover:**
> Same vibe in the app. Ask for a story, get it as real messages. Want it in English? Just say so.

**Caption:** `Ask for a story → real messages` · `"in English" revises the same answer`

**Badge (right):** `Muse Spark Open (Meta open weights) · your style`

**Edit:** left panel: translation of the Russian bubbles (the English revision needs none).

---

## 4 · Where my voice comes from

**Screen (exact taps):**
1. **Styles** tab (title **Your voice**) → style pill → **New style from chats…** → pick the WhatsApp export of the
   staged chat → **Create style**.
2. **Which one is you?** → pick yourself. **Who are these chats with?** → **Friends** → **Continue**.
   **Time-lapse** of the stages ticking off → **Self-check** card → **Use this style**.
3. **Emails** tab → **Add emails** → **Screenshots** → pick 2–3 screenshots of emails the owner sent. The tab now
   shows **Opens with** and **Signs off with**.

**Voiceover:**
> Where does my voice come from? My own chats and emails. It learns how I write, never what other people said.

**Caption:** `Your own chats and emails` · `Only your side of the chat is kept`

**Badge (right):** `Muse Spark 1.3 reads the chats and screenshots · only your own messages are kept`

**Edit:** the time-lapse is the only sped-up footage in the video. The self-check score is whatever the filmed style
shows; don't voice or caption a number. Blur any name or private fact in the `You:` rows, the audience bubbles and
the Opens with / Signs off with lines (see checklist).

---

## 5 · Essays from a voice note

**Screen (exact taps):**
1. **Chat** → ✎ → **Essay**. Field **Essay question or topic**: `Describe a project you are proud of and what you
   learned from it.` Length **250**.
2. Tap **🎙** and speak the notes (non-private facts about this project only). Tap **■**.
3. Wait at real speed. The essay appears in paragraphs with `N words` under it; scroll slowly.
4. **Make it stronger: answer one** → tap a question → hold on it.

**Voiceover:**
> Essays too. I just talk, it writes in my formal voice, only from my facts. Then it asks how to make it stronger.

**Caption:** `🎙 Talk → an essay in your formal voice` · `Only your facts` · `"Make it stronger"`

**Badge (right):** `Muse Voice Transcribe 1.0` while recording, then `Muse Spark 1.3 writes the essay · your formal
voice`.

---

## 6 · Too casual? Thumbs down

**Screen (exact taps):**
1. **Chat** → ✎ → **Write**, **Official** (or a message to **Elders**). Ask for something short.
2. Tap **👎** → reason chip **Too casual**. The revised answer appears; when a lasting rule was taken, the toast
   **Learned: …** shows. (No toast in a take? Use another take; never add one in the edit.)

**Voiceover:**
> Too casual? Thumbs down. It fixes it, and remembers.

**Caption:** `👎 Too casual → fixed → remembered`

**Badge (right):** `Muse Spark Open revises it and writes the rule`

---

## 7 · Under the hood

**Screen:** motion-graphic card (no phone):
```
your LoRA on Muse Glimmer 30B (Meta open weights) ── keyboard ✨, restyles the replies   (live on a temporary H100)
Muse Spark 1.3 (Meta Model API)                   ── reads screenshots and chats, writes essays
Muse Spark Open (Meta open weights)               ── the chat, emails, revisions; the default writer when the GPU is off
Muse Voice Transcribe 1.0                         ── voice notes → text
```
Then the number card (every number is committed in `eval/results/`):
- `My LoRA vs Muse Spark Open · 40 held-out rewrites · form similarity 0.97 vs 0.93 · chrF 55.7 vs 49.3`
- `Blind test · 5 friends · 100 answers · guessed right 53% (chance 50%) · small sample`

Footnote: `style_gain_lora.json: chrF +6.4, 95% CI +0.8…+12.4 · blind_test.json: 10 real + 10 SaySo messages, friends &
family, Russian only · they couldn't reliably tell`.

**Voiceover:**
> Under the hood: four Meta models, including my own LoRA on Muse Glimmer. And in a blind test, my friends guessed
> right just fifty-three percent of the time.

**Caption:** `4 Meta models · incl. my own LoRA on Muse Glimmer 30B` ·
`Blind test: friends guessed right 53% of the time (chance 50%) · small sample`

**Note:** the blind test's SaySo messages were written with the GPU off (Muse Spark 1.3 drafts in the user's style),
before the LoRA was switched on; the card doesn't say the LoRA wrote them.

---

## 8 · Close

**Screen:** the WhatsApp chat: the friend's reply to the series (staged). Fade to the end card: SaySo icon,
`Your words. Your voice. You always press send.`, `Built with Muse Glimmer 30B + my LoRA · Muse Spark Open ·
Muse Spark 1.3 · Muse Voice Transcribe`, repo URL. Small footnote: `LoRA served on a temporary H100 for this video;
by default Muse Spark Open writes`.

**Voiceover:**
> Your words. Your voice. You always press send. This is SaySo.

**Caption:** `Your words. Your voice. You always press send.` · `SaySo`

---

## Filming checklist

### Content and consent
- [ ] **Staged chats only**, in WhatsApp, with a consenting friend (their "yes" in writing) or the owner's second
      number. Never a real third-party conversation on screen. The friend is never named in the video or the docs:
      neutral display name, placeholder avatar, no phone numbers on screen.
- [ ] Clear the chat history above the staged messages, so no older messages show.
- [ ] The Back Tap screenshot only contains the staged chat (it is sent to Muse Spark 1.3).
- [ ] WhatsApp export for beat 4: the staged chat only. Real names in **Which one is you?** and **Who are these chats
      with?** are blurred in the edit.
- [ ] Before filming, open the built style's self-check card, the audience cards and the Emails tab: if any `You:`
      sample, example bubble, greeting or sign-off contains a name, place, number or private fact, blur it.
- [ ] Beat 4 emails: 2–3 emails the owner sent and doesn't mind on camera. Beat 5: notes about this project only.
- [ ] "Learned from you": clear older items before filming (they're the owner's real messages and rules).
- [ ] Nothing from `data/` is shown or committed; this file contains only invented demo lines.

### Phone setup
- [ ] SaySo **Settings → Language → English**, then close and reopen SaySo (so the shortcut dialogs are in English).
- [ ] Do Not Disturb on; one theme for all takes; default text size.
- [ ] SaySo keyboard added, **Full Access** on, active in WhatsApp. Keyboard tab: Formats include Series, variants = 3.
- [ ] Microphone allowed for SaySo, so 🎙 works on the first take.
- [ ] Shortcut installed with **Add the SaySo shortcut**; then Settings → Accessibility → Touch → **Back Tap** → Double Tap → that SaySo
      shortcut. Test it twice right before the take, including the Paste in WhatsApp.
- [ ] The style built in beat 4 is the **active** style for the other beats.

### Server and models (what writes must match the badges)
- [ ] Deployed with `SAYSO_GPU=modal` (and `SAYSO_SCALEDOWN` raised while filming, so the H100 stays warm between
      takes), `SAYSO_WRITER=open`, `SAYSO_CLEAN=on`. Warm it with `GET /warmup` before the first take.
- [ ] ✨ and Back Tap takes: the answer must come from the LoRA (`styled: true` in the `/rewrite` / `/reply`
      response). A cold GPU answers with Muse Spark instead (`styled: false`); then refilm the take or change its badge
      to `Muse Spark Open` (✨) / `Muse Spark 1.3` (replies).
- [ ] If Baseten is down, chat answers come from Spark 1.3 (the fallback): change those badges, or wait and refilm.
- [ ] After filming: redeploy with `SAYSO_GPU=off`, so the H100 isn't kept.

### Numbers (check before the edit)
- [ ] **Beat 7, LoRA card** (`eval/results/style_gain_lora.json`, 40 held-out rewrites): Spark Open form 0.93, chrF
      49.3; LoRA (+ rerank) form 0.97, chrF 55.7; chrF difference +6.4, 95% CI +0.8…+12.4, wins 22 / losses 15.
- [ ] **Beat 7, blind test** (`eval/results/blind_test.json`): 5 people, 100 answers, accuracy 0.53
      (`p_accuracy_vs_half` 0.62), «Человек» for real 0.62 vs SaySo 0.56, difference CI −0.13…+0.24, Fisher p 0.68.
      "Small sample" on screen. Never "indistinguishable" or "fooled": "couldn't reliably tell".
- [ ] **Self-check score** (beat 4): on screen only, whatever the filmed style shows; not voiced or captioned.

### Showing the Meta models
- [ ] A right-side badge in every model moment, exactly as listed per beat above.
- [ ] All four models on the beat 7 card and the end card; "open weights" said or shown for Muse Spark Open and
      Muse Glimmer.

### Edit and export
- [ ] Total ≤ 3:00. Export 1080p, H.264, 30 fps; captions burned in **and** uploaded as `captions.srt`.
- [ ] English translation for every Russian line on screen.
- [ ] Final watch-through for names, numbers, notifications and keys before upload.
