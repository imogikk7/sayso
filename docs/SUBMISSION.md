# SaySo: an AI that writes the way you'd say it

*Meta Global AI Developer Hackathon, indie track. Built solo, Oct 27 – Nov 4, 2026.*
*Meta models: Muse Spark 1.3 (Meta Model API), Muse Glimmer 30B (open weights) + a personal LoRA, Muse Spark Open.*

## Inspiration

Every AI writing tool makes me sound like the same polite assistant: capital letters, full stops, "I hope you're
doing well". My friends would spot it in one message. I write in short lowercase bursts, split one thought into three
messages, mix Russian with English and some Kazakh, and I write very differently to my partner than to an older
relative. I wanted the opposite of a generic assistant: a model that has learned **how I actually text**, sits in the
keyboard I already use, and gets better every time I correct it.

## What it does

SaySo writes messages in your own voice: your length, case, punctuation, slang, and the way you react (agree, joke,
tease, ask back), adapted to who you're talking to (partner, friends, family, elders).

- **Its own iOS keyboard.** RU/EN letter keys plus ✨: type a rough draft, tap ✨, insert one of 1–3 versions in your
  style. Formats: one message, a *series* of short messages sent one by one, an official message, or an email.
- **Back Tap → replies.** Double-tap the back of the iPhone: a Shortcut takes a screenshot, Muse Spark reads the chat,
  and you get three replies with different intents (for example agree / refuse / joke) to pick from. The keyboard shows
  the same three.
- **Chat in the app** with 👍 / 👎 / ✏️ under every answer.
- **Styles from your own chats.** Upload WhatsApp, Telegram or Instagram exports, or screenshots. SaySo asks which
  one is you and who each chat is with, then builds a style and checks itself ("sounds like you" vs a generic AI).
- **It keeps learning.** Messages you send with the SaySo keyboard become examples right away. A suggestion you edited
  before sending, or a 👎 with "shorter", becomes a rule ("keep messages to family short").

You always send the message yourself. SaySo is about keeping your own voice, not about hiding that AI was used.

## How we built it

- **Data.** I parsed my Telegram exports. Only my own messages are kept, and consecutive messages are merged into one
  "turn". Links, phone numbers and media are stripped, no single chat is allowed to dominate, and the most recent weeks
  are held out for testing. Base Muse Glimmer, hosted by me on Modal, tagged each turn with the situation (invitation,
  sadness, conflict, …), a neutral summary of what the other person said, and the "thought" behind my reply (act ·
  tone · gist). Other people's messages were read in memory and never saved. Muse Spark Open wrote neutral drafts and
  instructions for the rewrite and compose training pairs.
- **The personal model.** A QLoRA on **Muse Glimmer 30B** (Unsloth, Modal H100). Four versions: v3 (SimPO on word
  choice) made things worse and was dropped. The served **v4** first writes a short thought in Glimmer's own `to=self`
  channel, then the message. Prefilling that thought (`act: refuse`) gives controllable intents in my voice.
- **The writer.** **Muse Spark 1.3** reads the screenshot or chat, then drafts three replies guided by my *style
  profile* (per audience × situation: usual length, lowercase, punctuation, laughter, swearing, and how often I agree,
  joke or ask back) plus up to 8 of my real messages to that audience. My LoRA rewrites each draft in my voice and
  samples 5 candidates. A reranker picks the candidate closest to one of my real messages from the same audience ×
  situation, so the output follows my distribution instead of my average.
- **Styles from uploads.** A pipeline goes parse → which one is you → Spark tagging → profile → training pairs →
  self-check → optional per-style LoRA, with progress shown in the app.
- **Serving.** FastAPI on Modal CPU, vLLM with multi-LoRA on an H100 (or the same server on Baseten), switched by one
  env flag. The iOS side is SwiftUI with a keyboard extension and App Intents for the Shortcut.

## Challenges we ran into

- **Compute ran out before the demo.** Modal credits are nearly gone, Fireworks uploads are disabled service-wide, and
  the hackathon Baseten key only serves Muse Spark Open. The LoRA is trained and benchmarked, but it isn't hosted live
  right now, so the demo runs with `SAYSO_GPU=off`: Muse Spark writes alone, guided by my style profile and real
  messages. I measured how much that guidance adds (below) so the fallback is honest rather than hidden.
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
- With the GPU off, the style alone lifts Muse Spark from **0.67 → 0.94** form similarity to my real messages and
  **41.0 → 51.4** chrF (40 held-out rewrites: generic → + profile → + my real messages).
- The whole loop in one iOS app: keyboard ✨ in any messenger, Back Tap → three replies in my voice, and feedback that
  visibly turns into rules.
- Building a style from uploads end to end, including "which one is you", a self-check score, and privacy tests.

## What we learned

- A small LoRA on a strong open model captures **form** (length, case, punctuation, rhythm) far better than few-shot
  prompting. Meaning and situation reading are better left to a frontier model that sees the whole chat.
- Splitting *what to say* (Muse Spark) from *how I say it* (my LoRA) works better than asking one model to do both.
- A model's "train of thought" doesn't make it read your mind, but it is a good **control knob** for intent.
- Honest baselines matter: a self-consistency ceiling, a no-style baseline, a memorization check.

## What's next

- Host the LoRA again: per-token multi-LoRA serving (Fireworks/Together) until a few thousand users, then one shared
  Glimmer base with per-user adapters swapped per request.
- Run the blind test with friends (compose tasks only). **Result: TODO, not run yet.**
- Batch what the keyboard learns into periodic LoRA refreshes behind an eval gate, with rollback.
- Per-device auth instead of the demo's single server token. Move live chat reading to self-hosted models so other
  people's messages never leave our own servers.
- More import channels (Telegram bot forwarding, iMessage via screen recording) and an English-speaking user's style
  built from their own data.
- Business model: free tier on Muse Spark with profile and examples, Pro with your own LoRA (idea: $6.99/month,
  estimated ≈ $3–3.5 cost per active user now, ≈ $1–1.5 after self-hosting the drafter and prompt caching).

**Repo:** https://github.com/imogikk7/sayso. Architecture, benchmarks, privacy and how to run are in the README.
