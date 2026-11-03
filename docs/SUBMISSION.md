# SaySo: an AI that writes the way you'd say it

*Meta Global AI Developer Hackathon, indie track. Built solo, Oct 27 – Nov 4, 2026.*
*Meta models: Muse Spark Open (open weights, writes), Muse Spark 1.3 (Meta Model API, reads, drafts replies, writes
essays), Muse Voice Transcribe 1.0 (voice notes), Muse Glimmer 30B (open weights) + a personal LoRA (trained and
benchmarked, not hosted live).*

**In one line:** SaySo is an iPhone keyboard, a Back Tap shortcut and a chat app that write messages, emails and essays
the way *you* write them, learned from your own chats and documents.

## Inspiration

Every AI writing tool makes me sound like the same polite assistant: capital letters, full stops, "I hope you're
doing well". My friends would spot it in one message. I write in short lowercase bursts, split one thought into three
messages, mix Russian with English and some Kazakh, and I write very differently to my partner than to an older
relative. I wanted the opposite of a generic assistant: a model that has learned **how I actually text**, sits in the
keyboard I already use, and gets better every time I correct it. The same goes for the formal side: an email or an
essay "written with AI" reads like everyone else's, full of "in today's fast-paced world". I wanted mine to sound like
the emails and essays I actually write.

## What it does

SaySo writes messages in your own voice: your length, case, punctuation, slang, and the way you react (agree, joke,
tease, ask back), adapted to who you're talking to (partner, friends, family, elders).

- **Its own iOS keyboard.** RU/EN letter keys with the stock iOS look (light and dark, keys that type on touch-down)
  plus ✨: type a rough draft, tap ✨, put in one of 1–3 versions in your style. Formats: one message, a *series* of
  short messages sent one by one from a stack, an official message, or an email.
- **Back Tap → replies.** Double-tap the back of the iPhone: a Shortcut takes a screenshot, asks who it's for and an
  optional note ("politely decline"), Muse Spark 1.3 reads the chat and writes three replies with different intents
  (for example agree / refuse / joke) in your style; you pick one and it's copied. The same replies wait in the SaySo
  keyboard. Installing the shortcut is one tap in the app (**Add the SaySo shortcut**).
- **Chat in the app**: modes Write, Rewrite and Reply, each as a Message, Series, Official message, **Email** (subject
  + body from your notes; Reply → Email answers an email you paste) or **Essay** (a plan and the text built only from
  your own notes, held to the length you ask ±10%, a check for AI clichés, then up to 3 questions whose answers would
  make it stronger). The chat remembers the thread: «на русском» or "shorter" changes the last answer instead of
  starting over. 🎙 lets you dictate: Muse Voice Transcribe hears it, the iPhone's on-device recognizer hears it too,
  and Muse Spark fixes the slips. A series comes as separate bubbles, each with a copy button; alternative series fold
  into stacks like notification groups. 👍 / 👎 / ✏️ under every answer, long-press to copy any bubble.
- **Styles from your own writing.** The Styles tab is split by kind: **Messages**, **Emails**, **Essays**. *Messages*:
  WhatsApp, Telegram or Instagram exports, or screenshots / a screen recording (iMessage), with step-by-step guides.
  SaySo asks which one is you and who each chat is with, then builds a style and checks itself ("sounds like you" vs a
  generic AI). *Emails* and *Essays*: your own files, photos, screenshots or pasted text become your **formal voice**.
  Essays teach only voice (word choice, sentence length, linking words), never structure or topic; emails teach only
  manner (greeting, sign-off, how direct you are), never content. Greetings, sign-offs and "phrases I never use" can be
  edited by hand.
- **English and Russian UI**, switched in Settings → Language; a short tour on first launch.
- **It keeps learning.** Once you turn learning on (it's off by default), messages you type and send with the SaySo
  keyboard's letter keys become examples right away. Pasted text is never learned (it may be someone else's words), and
  neither are password, email, URL, code or search fields. A ✨ suggestion you edited before sending, or a 👎 with a
  one-tap reason ("Too long", "Not my words") or your own words, becomes a rule ("keep messages to family short").
  Everything it learned is listed and can be deleted.

You always send the message yourself. SaySo is about keeping your own voice, not about hiding that AI was used.

## How we built it

- **Data.** I parsed my Telegram exports. Only my own messages are kept, and consecutive messages are merged into one
  "turn". Links, phone numbers and media are stripped, no single chat is allowed to dominate, and the most recent weeks
  are held out for testing. Base Muse Glimmer, hosted by me on Modal, tagged each turn with the situation (invitation,
  sadness, conflict, …), a neutral summary of what the other person said, and the "thought" behind my reply (act ·
  tone · gist). Other people's messages were read in memory and never saved. Muse Spark Open wrote neutral drafts and
  instructions for the rewrite and compose training pairs.
- **The personal model.** A QLoRA on **Muse Glimmer 30B** (Unsloth, Modal H100). Four versions: v3 (SimPO on word
  choice) made things worse and was dropped. The newest **v4** (the one the server loads when a GPU is on) first writes a short thought in Glimmer's own `to=self`
  channel, then the message. Prefilling that thought (`act: refuse`) gives controllable intents in my voice.
- **The writer.** **Muse Spark Open**, Meta's open-weights model on Baseten (`reasoning_effort: low`, about 2–8 s),
  writes in my style: ✨ in the keyboard, rewrites, messages from an instruction, the chat's Write and Rewrite answers,
  official messages and emails.
  Its prompt carries my *style profile* (per audience × situation: usual length, lowercase, punctuation, laughter,
  swearing, and how often I agree, joke or ask back), up to 8 of my real messages to that audience, and the rules
  learned from my corrections. **Muse Spark 1.3** reads screenshots and pasted chats (audience, situation, a neutral
  summary, three reply drafts with different intents, written with the same style; with the GPU off these drafts are
  the Back Tap and chat Reply answers), reads photos of my own emails and essays, writes essays and fixes voice-note
  transcripts. Each is the fallback for the other. With a GPU, my LoRA rewrites each draft in my voice, samples 5 candidates, and a
  reranker picks the one closest to one of my real messages from the same audience × situation, so the output follows
  my distribution instead of my average.
- **Formal voice.** `serving/documents.py` turns my own emails and essays (.txt, .docx, .pdf, Google Takeout .mbox,
  photos, pasted text) into paragraphs and a formal profile (sentence length, linking words, openings and sign-offs).
  Quoted earlier messages, signature blocks and old section labels ("Thesis:") are cut, and names of other people
  and companies in photos become `[Name]`, so it learns my voice and not someone else's text or my homework's
  structure. My own style now holds 8 emails I sent and 11 handwritten essay pages. Essay mode plans first, takes its structure from the task, writes in the first
  person for personal statements, uses only facts from my notes, and fixes itself once if it is too long or sounds
  AI-written.
- **Styles from uploads.** A pipeline goes parse → which one is you → Spark tagging → profile → training pairs →
  self-check → optional per-style LoRA, with progress shown in the app.
- **Last checks on every answer.** Guards strip `[Name]`-style placeholders and self-introductions nobody asked for
  (the formal profile shapes tone, never facts about me); a long message can come back as a series when that's how I
  write to that person; official messages and emails stay in the language of the request with one sign-off and nothing
  invented; a short follow-up in the chat ("shorter", «на русском») revises the last answer.
- **Serving.** FastAPI on Modal CPU, vLLM with multi-LoRA on an H100 (or the same server on Baseten), switched by one
  env flag. The iOS side is SwiftUI with a keyboard extension (a UIKit touch layer for instant keys), App Intents for
  the Shortcut (it returns the replies as a list, so Shortcuts' own *Choose from List → Copy to Clipboard* does the
  copying), and a voice recorder that sends WAV to `/transcribe` (the audio is not stored).
- **Blind test.** A page served by the API (no app needed, opens in any phone browser): one message and its situation
  per question, friends tap «Человек» or «ИИ». Muse Spark 1.3 screens every message so it is safe to show.

## Challenges we ran into

- **Compute ran out before the demo.** Modal credits are nearly gone, Fireworks uploads are disabled service-wide, and
  the hackathon Baseten key only serves Muse Spark Open. The LoRA is trained and benchmarked, but it isn't hosted live
  right now, so the demo runs with `SAYSO_GPU=off`. I turned that into an open-weights path: **Muse Spark Open** writes
  in my style, guided by my style profile, real messages and learned rules, and I measured how much that guidance adds
  (below) so the setup is honest rather than hidden.
- **Spark Open always reasons.** At the default effort a chat message took 5.5 s; `reasoning_effort: low` brought it
  to 2.7 s with a fifth of the tokens. It sometimes sent an instruction back as the message ("tell her…"), so those
  answers are rewritten by Spark 1.3.
- **Learning a voice, not a template.** My uploaded homework came with labels like "Argument 2:", and a model shown
  those paragraphs tends to copy their structure. Section labels are now cut from uploads, essays teach only voice,
  emails only manner, and the structure comes from the new task.
- **Smarter example picking didn't help.** Examples picked by meaning (embeddings) or by TF-IDF scored the same as
  random examples. I report that and kept the free local option.
- **Replies are close to impossible to predict.** On held-out replies every system scores low chrF, because nobody can
  guess my exact answer. That pushed the design toward *Spark drafts with the full chat, the LoRA rewrites*, since
  rewriting is the LoRA's strongest task.
- **Averages lie.** Scoring candidates against my average message made every answer bland (my average message
  "laughs 0.3 times"). Sampling a real message as the target fixed that.
- **Measuring "thinking like me."** The act/tone tagger agrees with itself only 48% of the time, which caps any
  act-match score. I report that ceiling next to the numbers.
- **Privacy in a public repo.** All chats, pairs and adapters stay on a private volume. Tests assert that none of the
  other person's lines are ever written to disk.
- **iOS keyboard limits.** A fixed height, no network without Full Access, free signing that expires every 7 days, and
  a set of field types the keyboard must not learn from (passwords, email, URLs, codes, search). Keys felt slow until
  they moved to a UIKit touch layer that types on touch-down.
- **The clipboard from Back Tap.** iOS drops clipboard writes from an intent running in the background, so the first
  shortcut "copied" nothing. Now the intent returns the replies and the shortcut's own *Copy to Clipboard* copies the
  one you pick; the keyboard shows them too.
- **Chat without memory.** «на русском» after an email produced a brand-new email "about nothing". The chat now sends
  the last turns back and revises the last answer when the request is a refinement.

## Accomplishments that we're proud of

- On 499 held-out pairs, the personal LoRA brought the stylometric fingerprint gap from **2.64** (base Glimmer) and
  **1.01** (few-shot with my own messages) down to **0.04**. Rewrite chrF went from 28.5 / 40.7 to **57.2**, with
  0.6% verbatim memorization.
- With the GPU off, the style alone lifts Muse Spark 1.3 from **0.69 → 0.94** form similarity to my real messages and
  **41.8 → 54.0** chrF (40 held-out rewrites: generic → + profile → + my real messages). **Muse Spark Open**, the
  open-weights writer the app runs now, reaches **0.93** form and **50.4** chrF with the same prompt
  (after it learned to keep my fillers, laughter, swearing, emoji and message splitting at my own rate).
- **Blind test with 5 friends (100 answers): they could not reliably tell my real messages from SaySo's.** Accuracy
  53% (chance 50%, exact binomial p ≈ 0.62); my real messages were taken for a person 62% of the time, SaySo's 56%
  (difference +6 points, 95% CI about −13 to +24, Fisher p ≈ 0.68). Small sample, caveats below.
- The whole loop in one iOS app: keyboard ✨ in any messenger, Back Tap → three replies in my voice, emails and essays
  in my formal voice from dictated notes, and feedback that visibly turns into rules.
- Four Meta models with clear roles: Spark Open writes, Spark 1.3 reads, Voice Transcribe listens, Glimmer carries
  the personal LoRA.
- Building a style from uploads end to end, including "which one is you", a self-check score, and privacy tests.

## What we learned

- A small LoRA on a strong open model captures **form** (length, case, punctuation, rhythm) far better than few-shot
  prompting. Meaning and situation reading are better left to a frontier model that sees the whole chat.
- Splitting *what to say* (Muse Spark) from *how I say it* (my LoRA) works better than asking one model to do both.
- Without a GPU, an open-weights model with an explicit style profile and real examples gets most of the way on form
  (0.93); the user's real messages are what move the wording.
- "Write like me" has to be split by kind: from essays take the voice, never the structure; from emails take the
  manner, never the content.
- A model's "train of thought" doesn't make it read your mind, but it is a good **control knob** for intent.
- Honest baselines matter: a self-consistency ceiling, a no-style baseline, a memorization check.

## What's next

- Host the LoRA again: per-token multi-LoRA serving (Fireworks/Together) until a few thousand users, then one shared
  Glimmer base with per-user adapters swapped per request.
- Self-host Muse Spark Open next to Glimmer, so writing runs on our own GPUs.
- A bigger blind test: more friends, a plain-AI control in the same test, only held-out messages, and partner and
  elder chats once there's a safe way to show them.
- Batch what the keyboard learns into periodic LoRA refreshes behind an eval gate, with rollback.
- Per-device auth instead of the demo's single server token. Move live chat reading to self-hosted models so other
  people's messages never leave our own servers.
- More import channels (Telegram bot forwarding) and an English-speaking user's style built from their own data.
- Business model: free tier on Muse Spark Open with profile, examples and formal voice, Pro with your own LoRA (idea: $6.99/month,
  estimated ≈ $3–3.5 cost per active user now, ≈ $1–1.5 after self-hosting the writer and prompt caching).

## Limitations, honestly

- **The personal LoRA is not serving live.** It is trained and benchmarked, but no GPU is hosting it (Modal credits
  nearly gone, Fireworks uploads disabled, the Baseten key serves only Muse Spark Open). Everything in the demo is
  written by Muse Spark Open or Muse Spark 1.3, guided by my style profile, my real messages and learned rules.
- **The blind test is small.** 5 friends, 20 messages, 100 answers; the confidence interval still allows a gap of up to
  24 points. My own runs of the page are excluded. Items were filtered to be shareable: friends and family only, one
  message each, Russian only, nothing private or trivial. Some of my real items come from the training split. There was
  no plain-AI control in this run. SaySo's items were Muse Spark 1.3 Reply drafts in my style (GPU off).
- **One user, one token.** The server is single-user, with one bearer token in the app. Fine for a demo, not a release.
- **Russian is the tested language.** All numbers come from my own Russian (with some English and Kazakh) messages. An
  English profile needs an English speaker's data; I didn't invent one.
- **Formal voice depends on what you add.** Without your own emails and essays, SaySo writes plainly.
- **Live reading uses Muse Spark 1.3.** Other people's messages in screenshots are sent to the Meta Model API to be read
  (in memory, never stored by SaySo). Moving that to our own hosted model is planned.

**Repo:** https://github.com/imogikk7/sayso. Architecture, benchmarks, privacy and how to run are in the README.
