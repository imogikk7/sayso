# SaySo: an AI that writes the way you'd say it

*Meta Global AI Developer Hackathon, indie track. Built solo, Oct 27 – Nov 4, 2026.*
*Meta models: Muse Spark Open (open weights, writes), Muse Spark 1.3 (Meta Model API, reads), Muse Voice Transcribe 1.0
(voice notes), Muse Glimmer 30B (open weights) + a personal LoRA (trained and benchmarked).*

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

- **Its own iOS keyboard.** RU/EN letter keys plus ✨: type a rough draft, tap ✨, insert one of 1–3 versions in your
  style. Formats: one message, a *series* of short messages sent one by one, an official message, or an email.
- **Back Tap → replies.** Double-tap the back of the iPhone: a Shortcut takes a screenshot, Muse Spark reads the chat,
  and you get three replies with different intents (for example agree / refuse / joke) to pick from. The keyboard shows
  the same three.
- **Chat in the app**: Write, Rewrite, Reply, **Email** (subject + body from your notes, optionally answering an email
  you paste) and **Essay** (a plan and the text built only from your own notes, a check for AI clichés, then up to 3
  questions whose answers would make it stronger). 🎙 lets you dictate notes and answers: Muse Voice Transcribe turns
  them into text. 👍 / 👎 / ✏️ under every answer.
- **Styles from your own writing.** An Add menu with step-by-step guides per app. *Messages*: WhatsApp, Telegram or
  Instagram exports, or screenshots / a screen recording (iMessage). SaySo asks which one is you and who each chat is
  with, then builds a style and checks itself ("sounds like you" vs a generic AI). *Emails* and *Essays & documents*:
  your own files, photos, screenshots or pasted text become your **formal voice**. Essays teach only voice (word choice,
  sentence length, linking words), never structure or topic; emails teach only manner (greeting, sign-off, how direct
  you are), never content.
- **It keeps learning.** Messages you send with the SaySo keyboard's letter keys become examples right away (never
  from password, email, URL, code or search fields). A ✨ suggestion you edited before sending, or a 👎 with
  "shorter", becomes a rule ("keep messages to family short"). Everything it learned is listed and can be deleted.

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
  writes everything in my style: ✨ in the keyboard, rewrites, messages from an instruction, chat answers and emails.
  Its prompt carries my *style profile* (per audience × situation: usual length, lowercase, punctuation, laughter,
  swearing, and how often I agree, joke or ask back), up to 8 of my real messages to that audience, and the rules
  learned from my corrections. **Muse Spark 1.3** reads screenshots and pasted chats (audience, situation, a neutral
  summary, three reply drafts with different intents), reads photos of my own emails and essays, and writes essays.
  Each is the fallback for the other. With a GPU, my LoRA rewrites each draft in my voice, samples 5 candidates, and a
  reranker picks the one closest to one of my real messages from the same audience × situation, so the output follows
  my distribution instead of my average.
- **Formal voice.** `serving/documents.py` turns my own emails and essays (.txt, .docx, .pdf, Google Takeout .mbox,
  photos, pasted text) into paragraphs and a formal profile (sentence length, linking words, openings and sign-offs).
  Quoted earlier messages and old section labels ("Thesis:") are cut, so it learns my voice and not someone else's
  text or my homework's structure. Essay mode plans first, takes its structure from the task, writes in the first
  person for personal statements, uses only facts from my notes, and fixes itself once if it is too long or sounds
  AI-written.
- **Styles from uploads.** A pipeline goes parse → which one is you → Spark tagging → profile → training pairs →
  self-check → optional per-style LoRA, with progress shown in the app.
- **Serving.** FastAPI on Modal CPU, vLLM with multi-LoRA on an H100 (or the same server on Baseten), switched by one
  env flag. The iOS side is SwiftUI with a keyboard extension, App Intents for the Shortcut, and a voice recorder that
  sends WAV to `/transcribe` (the audio is not stored).

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
  a set of field types the keyboard must not learn from (passwords, email, URLs, codes, search).

## Accomplishments that we're proud of

- On 499 held-out pairs, the personal LoRA brought the stylometric fingerprint gap from **2.64** (base Glimmer) and
  **1.02** (few-shot with my own messages) down to **0.04**. Rewrite chrF went from 28.5 / 40.7 to **57.2**, with
  0.6% verbatim memorization.
- With the GPU off, the style alone lifts Muse Spark 1.3 from **0.69 → 0.94** form similarity to my real messages and
  **41.8 → 54.0** chrF (40 held-out rewrites: generic → + profile → + my real messages). **Muse Spark Open**, the
  open-weights writer the app runs now, reaches **0.93** form and **47.5** chrF with the same prompt.
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
- Run the blind test with friends (compose tasks only). **Result: TODO, not run yet.**
- Batch what the keyboard learns into periodic LoRA refreshes behind an eval gate, with rollback.
- Per-device auth instead of the demo's single server token. Move live chat reading to self-hosted models so other
  people's messages never leave our own servers.
- More import channels (Telegram bot forwarding) and an English-speaking user's style built from their own data.
- Business model: free tier on Muse Spark Open with profile, examples and formal voice, Pro with your own LoRA (idea: $6.99/month,
  estimated ≈ $3–3.5 cost per active user now, ≈ $1–1.5 after self-hosting the writer and prompt caching).

**Repo:** https://github.com/imogikk7/sayso. Architecture, benchmarks, privacy and how to run are in the README.
