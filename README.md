# SaySo: an AI that writes the way you'd say it

**▶ [Demo video (3 min)](https://youtu.be/MT7rrQuGGgg)** · [Post on X](https://x.com/imogikk7/status/2118044097198092367) · [Submission write-up](docs/SUBMISSION.md) · [Deck (PDF)](docs/deck/sayso.pdf)

SaySo writes messages the way **you** write them: your length, your case and punctuation, your slang, the way you
react to good news or a complaint, and how all of that changes between your partner, friends, family and elders.
It also writes your **emails and essays** in your own formal voice, learned from emails and essays you wrote yourself.
It lives where you type: **its own iOS keyboard** (normal letter keys plus a ✨ key that rewrites or writes in your
style), a **Back Tap / Action Button shortcut** (double-tap the back of the iPhone or press the Action Button →
screenshot → three replies in your voice, pick one and it's copied) and an **in-app chat** for longer things (Write, Rewrite or Reply, as a message, a series, an
official message, an email or an essay, with 🎙 voice input). The chat remembers the thread, so «на русском» or
"shorter" changes the last answer instead of starting over. It keeps learning: once you turn learning on, messages
you type and send with the SaySo keyboard become new examples, and every 👍, 👎 or edit in the chat becomes an example
or a short rule ("keep messages to family short").

Built solo during the **Meta Global AI Developer Hackathon** (indie track, Oct 27 – Nov 4, 2026) on four Meta
models: the open-weights **Muse Spark Open** writes, **Muse Spark 1.3** reads, **Muse Voice Transcribe 1.0** listens,
and the open-weights **Muse Glimmer 30B** carries the user's own LoRA.

> **Status, honestly.** Day to day the deployed server runs with **`SAYSO_GPU=off`** (no GPU credits left), and then
> ✨ in the keyboard, Write and Rewrite in the chat, official messages and emails are written by **Muse Spark Open**,
> Meta's open-weights model, served by Baseten (hackathon key, `reasoning_effort: low`, about 2–8 s per answer),
> guided by the user's style profile, their real example messages and the rules learned from their feedback.
> **Muse Spark 1.3** (Meta Model API) reads screenshots, pasted chats and photos, and with the GPU off its three drafts
> *are* the replies you get from Back Tap and from the chat's Reply mode (written with the same style profile and
> examples). It also writes essays, fixes voice-note transcripts and turns feedback into rules. Each of the two is the
> fallback for the other.
> The user's own **LoRA on Muse Glimmer 30B** is trained and benchmarked, and on the server's own code path it beat
> Muse Spark Open on 40 held-out rewrites (form similarity 0.97 vs 0.93, chrF 55.7 vs 49.3; see Results). For the
> **demo video** the GPU was switched on (`SAYSO_GPU=modal`, a temporary H100 on Modal): the keyboard's ✨ suggestions
> were written live by the LoRA, and the Back Tap replies were Muse Spark 1.3's drafts restyled by the LoRA. The
> in-app chat, its series and 👎 revisions were Muse Spark Open, essays Muse Spark 1.3, voice notes Muse Voice
> Transcribe 1.0. Outside that recording the LoRA is not hosted (Modal credits are nearly used up, Fireworks uploads
> are disabled service-wide, and the hackathon Baseten key serves only Muse Spark Open), so if you try SaySo now,
> Muse Spark Open writes. Turning the LoRA back on is one environment variable.

---

## What it does

| Surface | What happens |
|---|---|
| **SaySo keyboard** | Its own RU/EN letter keys (Kazakh letters on long-press) with the stock iOS look and sizes, light and dark, and keys that type on touch-down. The strip on top has an audience chip (the AI's guess is marked ✨), a format chip, and ✨. Type a draft, tap ✨, get 1–3 versions in your style (`In your style · tap one to put it in`), tap one to put it in place of the draft. A *series* comes as a stack you send one message at a time (`Series · 1 of 3 sent`, then `NEXT`). The **panel** has Rewrite / Write / Replies (the latest screenshot replies, or paste their message). Settings in the app's **Keyboard** tab, with a live preview: opens with letters or the panel, audiences, formats, number of variants, haptics, accent color, "Capital letter at sentence start" (off by default, since most people who write like this write lowercase) and "Learn from what I type" (off by default). You always send the message yourself. |
| **Back Tap / Action Button → replies** | One iOS Shortcut: *Take Screenshot* → *Reply with SaySo* (App Intent → `/reply`, returns the replies as a list) → *Choose from List* → *Copy to Clipboard*. It asks **Who is it for?** (Auto, Partner, Friends, Family, Elders / formal) and an optional note ("politely decline, I'm busy"). Muse Spark 1.3 reads the chat, guesses the situation, and writes three replies with different intents (for example agree / refuse / joke) in your style. You pick one and Shortcuts copies it (an intent running in the background can't write the clipboard itself, so copying is Shortcuts' own step). The same replies also wait in the SaySo keyboard, which shows them on its own the next time it opens (`From your screenshot · tap one to put it in`). Setting it up is one tap: **Settings → Add the SaySo shortcut** imports the ready shortcut from an iCloud link; then assign it to Back Tap or, on iPhones that have one, the Action Button (the demo video uses the Action Button). |
| **Chat in the app** | A messenger-style thread with SaySo (the horizontal SAY So logo on top, ✎ starts a new chat). Three menus above the field: **mode** (Write: an instruction → your message; Rewrite: your draft → your wording; Reply: paste their message → your reply), **kind** (Message, Series, Official, Email, Essay; Essay only in Write) and **To** (Partner, Friends, Family, Elders; hidden for Email and Essay). SaySo's welcome message has one-tap starts (Message, Email, Essay, Series, Rewrite, Reply) and example chips. **Write → Email** writes a subject and body from your notes; **Reply → Email** answers an email you paste. **Write → Essay** has a question field and a length picker (150 / 250 / 400 / 650 words or Custom, 100–900), writes a plan and the text only from your notes, shows the word count, and ends with up to 3 questions (**Make it stronger: answer one**). The send button is 🎙 when the field is empty: Muse Voice Transcribe turns the note into text. A series answer is a run of bubbles, each with its own copy button; the alternatives (**Or say it like this**) are cards, and a series alternative is a collapsed stack like a notification group (`+2`) that opens on tap. Long-press any bubble: Copy, Copy all messages, Share. Under the answer: Copy, 👍, 👎, ✏️, and, when SaySo guessed more than one audience, a `For Friends?` menu to switch. 👎 offers one-tap reasons (Too long, Too formal, Too casual, Not my words, Wrong meaning, Too rude; for emails and essays: Shorter, Longer, More personal, Simpler words, Less formal) or your own words, typed or spoken; the answer is rewritten, and if the feedback says something lasting, it becomes a rule of the style (`✨ Learned: …`). The thread is remembered: «на русском», "in English", "shorter" or "add that I'm sick" revises the last answer. |
| **Styles** | Titled **Your voice**. The pill on top switches the style in use and adds sources: **New style from chats…** (WhatsApp, Telegram, Instagram exports, or screenshots / a screen recording for iMessage and any other app; SaySo asks which participant is you and who each chat is with, then builds a profile, examples, a self-check score and optionally its own LoRA), **Add emails** and **Add essays** (your own writing as files: .txt, .md, .docx, .pdf, Google Takeout .mbox; photos or screenshots; or pasted text, which becomes your formal voice). Each source has step-by-step guides per app. The tab is split by kind with tabs at the top: **Messages** (the "sounds like you" score vs generic AI, how you write to each audience), **Emails** (tone and length, **Opens with** and **Signs off with**) and **Essays** (structure and voice), each with a "Teach me" card when it is empty. Lists can be edited by hand: greetings and sign-offs for emails (add, remove, reorder, mark a default; the writer uses yours in the email's language) and phrases SaySo must never use, per kind. |
| **Learned from you** | The style card lists every message the keyboard learned from and every rule taken from your corrections. Each one can be deleted. Its **Formal writing** section shows what was learned from your emails and essays (sentence length, linking words, how you open and sign off). |
| **Settings** | **Language** (System, English, Русский; the app and keyboard switch at once, Shortcuts and Siri after SaySo is reopened; what SaySo writes stays in your own language), then **Set up** with a progress ring: 1 add the keyboard, 2 allow Full Access (type in the test field to confirm), 3 the Back Tap shortcut (**Add the SaySo shortcut**, or **Build it yourself** step by step), 4 **Check the connection**. A six-page tour shows the tabs on first launch. |

**Formats:** `message` (one chat message), `series` (2–4 short messages, the way you split a thought), `official`
(a polite message for a work or study chat) and `email`; the chat's Essay mode writes `essay`. The formal ones use
your **formal voice** (below) instead of your chat habits such as lowercase, slang and emoji, but keep your plain
wording.

---

## How it works

```mermaid
flowchart TD
    subgraph phone["iPhone"]
        KB["SaySo keyboard<br/>letters + ✨ + panel"]
        BT["Back Tap shortcut<br/>screenshot → App Intent"]
        CH["App: Chat<br/>Write · Rewrite · Reply · Email · Essay · 🎙"]
        ST["App: Styles<br/>add messages · emails · essays"]
    end

    subgraph api["Modal: FastAPI on CPU (serving/modal_app.py)"]
        W["writer.py<br/>/rewrite /compose /reply /chat"]
        T["/transcribe<br/>audio not stored"]
        L["/learn · /feedback<br/>own text only"]
        B["build_style.py<br/>chat uploads"]
        D["documents.py<br/>own emails and essays"]
    end

    subgraph store["Private volume, per style (styles.py)"]
        P["style profile<br/>per audience × situation"]
        E["user's own messages<br/>examples"]
        F["formal profile<br/>+ own paragraphs"]
        R["learned rules"]
    end

    OPEN["Muse Spark Open (open weights)<br/>Baseten · writes in the user's style"]
    SPARK["Muse Spark 1.3<br/>Meta Model API · reads screenshots,<br/>chats, photos; writes essays"]
    VOICE["Muse Voice Transcribe 1.0<br/>Meta Model API"]
    GLM["Muse Glimmer 30B + user's LoRA<br/>off by default; live in the demo video<br/>(SAYSO_GPU=modal | baseten)"]

    KB --> W
    BT --> W
    CH --> W
    CH -- "voice note" --> T
    T --> VOICE
    KB -- "sent messages, edits" --> L
    CH -- "👍 👎 ✏️" --> L
    ST -- "chat exports, screenshots" --> B
    ST -- "files, photos, pasted text" --> D

    W -- "rewrite, compose, email, chat<br/>+ style, examples, rules" --> OPEN
    W -- "screenshot or pasted chat →<br/>situation, summary, 3 drafts" --> SPARK
    OPEN <-. "fallback both ways" .-> SPARK
    W -. "drafts to rewrite in the user's voice,<br/>5 candidates, rerank" .-> GLM

    store -- "style, examples, formal voice, rules" --> W
    L --> store
    B -- "tagging, profile, self-check" --> SPARK
    B --> store
    D -- "photos, screenshots" --> SPARK
    D --> store
```

### The writing path (`serving/writer.py`)

1. **Read** (replies only). Muse Spark 1.3 gets the screenshot (or pasted messages) plus the style: per audience,
   the usual length, share of lowercase starts, end punctuation, laughter and swearing, and how often the user agrees,
   jokes, teases, asks back and so on in each situation. It returns the audience (and the top 3 guesses), the situation
   (request, invitation, good news, sadness, conflict, joke, thanks, apology, logistics, …), a neutral 20–30-word
   summary of the other person's messages, and **three drafts with different intents**. With the GPU off (now), these
   drafts are the replies the user sees. Nothing from the screenshot is stored. Only the user's suggested replies are
   cached for the keyboard, never the summary.
2. **Write in the user's style.** For ✨, rewrite, compose, the chat's Write and Rewrite, official messages and
   emails, **Muse Spark Open** writes with
   the style profile, up to 8 of the user's real messages to that audience (their newest and approved ones first, then
   the ones closest in words and spelling, picked on our own server with TF-IDF), and the rules learned from their
   feedback. The prompt tells it to keep the user's habits (fillers, laughter, swearing, emoji, splitting a thought
   into several messages) at the user's own rate for that audience, instead of writing cleaner than they do. It
   returns its answer plus 4 more variants: the keyboard shows 1–3 of them, the chat shows the answer and up to 2
   alternatives. Spark Open always
   reasons; `reasoning_effort: low` keeps the thought short (2.7 s instead of 5.5 s in our test). If it fails, Muse
   Spark 1.3 answers instead, and if Spark 1.3 fails, Spark Open does. A compose answer that just repeats the
   instruction ("tell her…") is rewritten by Spark 1.3.
3. **Formal formats** (`official`, `email`, `essay`) get the user's formal voice instead of their chat messages, so
   they don't drift back into lowercase chat (see below). Official messages and emails are written in the language
   of the request (Russian in, Russian out, unless it asks for another), with only the greetings, sign-offs and
   paragraphs of the user's formal writing in that language, nothing the request doesn't say (no "we", no offers,
   no invented details), and the person the text names ("ask the professor…") wins over the audience chip. Every
   variant is checked: a second sign-off is removed, and one that still mixes languages or adds filler is dropped;
   if none is left, Muse Spark 1.3 writes it once more with the problems named.
4. **When the GPU is on** (`SAYSO_GPU=modal` or `baseten`), the style's LoRA on Muse Glimmer 30B rewrites each chat
   draft in the user's voice (rewriting is its strongest task, see the benchmark), samples 5 candidates, and a
   reranker (`pipeline/style_stats.py`) draws one of the user's real messages from the same audience × situation and
   picks the candidate whose features (length, lines, emoji, laughter, signature words, …) are closest, so the output
   follows the user's distribution instead of their average. If the LoRA is cold, or the format is formal, the styled
   draft is returned at once (`styled: false`), so the app never waits on a GPU. Without a chat (summary only), the
   main style's v4 adapter "thinks first": it writes `act · tone · gist` in Glimmer's `to=self` channel, then the
   message.
5. **No swearing** (`SAYSO_CLEAN`, on by default). The user's own style may swear, but nothing SaySo writes does: every
   Muse Spark writing prompt gets a rule against profanity in any language; swearing variants are dropped; a Spark
   answer that still swears goes to the next model in the fallback order (and is used, with those words cut out, only
   if none answers cleanly); the LoRA's swearing candidates are dropped before the rerank (or, if all of them swear,
   the words are cut out). Calls that copy the user's own words (reading a document, fixing a voice note, learning
   from the keyboard) are left as they are.
6. **Last checks on every answer** (`serving/postprocess.py`). **Guards** (`serving/guards.py`): no template
   placeholders (`[Name]`, `<company>`), no self-introduction (name, job, school) the user didn't ask for, no remarks
   about the request; the main answer is fixed and alternatives that break a rule are dropped. **Auto-series**
   (`serving/series.py`): when the user usually splits a thought into several messages to that audience and the
   content is long, a `message` may come back as 2–5 messages. **Essay length** (`serving/length.py`): the asked word
   count ±10 %, with up to two "expand" passes and one "trim" pass that only use the user's own facts.

**Chat memory** (`serving/memory.py`). Each chat request carries up to 3 earlier `{request, answer}` turns of the
thread. A short follow-up that changes the last answer («на русском», "in English", "shorter", "more formal", "add that
I'm sick") revises that answer and keeps its facts, addressee and kind (an email stays an email); anything else is a
new request, with the earlier turns given only as context. It is a heuristic (no extra model call), unit-tested in
`tests/test_memory.py`.

### Emails and essays in the user's formal voice (`serving/documents.py`)

Chats teach how the user writes to friends; their own emails and essays teach how they write when it's official.
In the style card or the Add menu, the user adds **Emails** or **Essays & documents**: `.txt`, `.md`, `.docx`, `.pdf`,
a Google Takeout `.mbox` (Sent label only), pasted text, or photos and screenshots that Muse Spark 1.3 transcribes
(handwritten lines joined into paragraphs, crossed-out words left out, mail app headers and the signature block after
the sign-off skipped, names of other people and companies replaced with `[Name]`). Each source has a
step-by-step guide in the app (Gmail and Apple Mail screenshots, copy and paste, print to PDF, Takeout; photos of
pages, Word / Pages / Google Docs).

What is kept is only the user's own text: quoted earlier messages in emails (someone else's text) are cut off, links,
emails, phone and card numbers are removed, and section labels of old assignments ("Thesis:", "Argument 2:") are cut.
From that, SaySo builds a **formal profile** (sentence length, the linking words the user actually uses, how they open
and sign off) and keeps their paragraphs as examples. The two kinds teach different things:

- **Essays teach voice only**: word choice, sentence length, linking words, how direct the user is. Never their
  structure, headings or topic. The structure comes from the new task.
- **Emails teach manner only**: how the user greets, asks and signs off, how formal and direct they are. Never what
  those emails said.

The author's own style currently holds 8 emails they sent and 11 handwritten essay pages (photographed, names masked
as `[Name]`); only those paragraphs and the formal profile are stored, on the private volume.

**Email** (Write → Email) writes a subject and a body from the user's notes, spoken or typed; **Reply → Email** answers
an email they paste. Every fact comes from the notes and nothing is invented. **Essay mode** plans first (4–6 points), then writes in
the structure the question asks for (an argument, a personal statement, a story, …; a natural essay without headings
if nothing is asked), in the first person and active voice when it is about the user, using only facts from the
user's notes. It reaches the length by explaining the user's facts, never by padding; if the notes are too thin it
writes shorter and asks. Then it checks itself: too long or containing AI clichés ("in today's fast-paced world",
"plays a crucial role", "delve", and their Russian counterparts) → one fix pass. The prompt asks for 3–6 real
paragraphs of 3–6 sentences (never one sentence per line), first person without starting more than two sentences in
a row with "I", and at most one linking word ("thus", "however", "also") per paragraph; the app gets the paragraphs
split on blank lines. It ends with up to 3 questions whose
answers would make the essay stronger; the user taps one, answers by voice or text and the essay is revised. The
length is held to the asked word count ±10 % (`serving/length.py`) and the count is shown under the essay. Essays are
written by Muse Spark 1.3; emails by Muse Spark Open.

### Voice notes (`/transcribe`)

🎙 in the chat records a voice note; **Muse Voice Transcribe 1.0** writes it down and it goes out like typed text
(an instruction, a draft, notes for an essay, an answer to one of its questions). The audio is read in memory and not
stored.

- **Recording:** up to 2 minutes, mono 16-bit **24 kHz** WAV (Muse Voice Transcribe takes 16 or 24 kHz; 24 kHz keeps more of the
  consonants that tell English words apart), the raw microphone (`.measurement`, no system voice processing).
- **Before recognition** (`writer.prepare_wav`): silence before and after the speech trimmed (in silence recognizers
  invent and repeat words), quiet speech raised to about −3 dBFS (at most ×10), other rates resampled.
- **Hints to Muse Voice Transcribe:** `languageBias: ["English"]` when the app's language is English (its list has no
  Russian), and `keywords`: names from the text the note is about (SaySo's last answer when fixing it, the email being
  answered). If the API refuses the hints, the call is repeated without them.
- **A second hearing on the iPhone:** Apple's on-device recognizer (`SFSpeechRecognizer`, on-device only, en-US or
  ru-RU from the app's language, at most a few seconds) hears the same note. Muse Voice Transcribe stays the
  recognizer; the iPhone's text goes to the fix pass as a second opinion, and is used alone only if Muse fails.
- **The fix pass** (Muse Spark 1.3, Spark Open as its fallback, `fix_transcript`): repeated words and doubled stops are removed first
  (`tidy_transcript`), then Spark fixes recognition slips with a prompt for the note's language, detected from its
  letters: the English one knows sound-alike words (their/there, your/you're, to/too, four/for), broken words, missing
  apostrophes and names. It is told what the note is for (the Chat mode and audience) and the known names. The fix is
  kept only if it is still the same note: about the same length, the same language, at most 30% new words (words
  either recognizer heard don't count as new) and most of the recognized words kept. Otherwise the transcript goes
  out as recognized.
- `eval/voice_samples.py` measures word error rate before and after on English and Russian samples.

### Building a style from chat uploads (`serving/build_style.py`)

`parsing` (Telegram HTML/JSON, WhatsApp `.txt`/`.zip` from Android and iOS, including iOS's narrow no-break space
before AM/PM, Instagram JSON via `pipeline/sources.py`; screenshots and screen-recording frames are read by Spark,
right-side bubbles = you, overlapping frames de-duplicated) →
`needs_me` (the app asks **which one is you** and confirms each chat's audience, which Spark guesses; a restarted
build asks again instead of reusing an old answer) →
`reading` (Spark tags up to 500 of your turns, about 2–4 minutes: situation, neutral summary, act · tone · gist, and
a neutral draft plus an instruction for training pairs) → `profile` → pairs → `checking` (**self-check**: held-out replies written in the new
style vs a no-style baseline, form similarity to your real replies, and Spark as a judge of whether they make sense) →
optional `training` of the style's own LoRA (`SAYSO_TRAIN=on`, at least 150 turns) → `ready`.

### Learning from use

- **Keyboard → `/learn`** (opt-in: "Learn from what I type" is off until the user turns it on). When a message is
  typed and sent with the SaySo keyboard's own letter keys, the keyboard queues it. **Pasted text is never learned**
  (it may be someone else's words). A suggestion sent unchanged is not counted as the user's own wording. A ✨
  suggestion the user changed is sent along with their version, and Spark may turn the difference into a rule. Links,
  emails, phone and card numbers are stripped. The keyboard never learns from password, email, URL, number,
  one-time-code or search fields. The new messages serve as examples on the very next request.
- **Chat → `/feedback`.** 👍 keeps the answer as an example, ✏️ keeps the user's version and may teach a rule.
- **Chat → 👎.** A quick reason chip or the user's own words go back to `/chat` as feedback on the last answer: the
  answer is revised, and a lasting preference becomes a rule.
- The style card lists what was learned, and each item can be deleted ("Learned from you").

### The main style's LoRA (offline pipeline)

The author's own model was trained on their Telegram Desktop exports (`pipeline/parse_telegram.py`): own messages
only, consecutive messages merged into one *turn*, URLs, phones, emails, card numbers and media removed, no chat above
35% of the set, the last weeks held out for test. Pairs (`pipeline/build_pairs.py`): **rewrite** (Muse Spark Open writes
a neutral version → the real message), **compose** (Muse Spark Open writes an instruction → the real message), **reply**
(situation + neutral summary from base Glimmer → the real reply). QLoRA with Unsloth on a Modal H100
(`training/modal_train.py`, r=16, lr 2e-4, 2 epochs, loss on the response). Versions: v1, v2 (more context), v3 (SimPO on
word choice: worse, dropped), and **v4** (thought in the `to=self` channel, then the message), which is the one the
server loads when the GPU is on.

---

## Meta models and their roles

| Model | Where | Role in SaySo |
|---|---|---|
| **Muse Spark Open** (`meta-models/muse-spark-open-1026`, open weights) | Baseten, OpenAI-compatible, hackathon key, `reasoning_effort: low` | **Writes in the user's style** in the live app (the default, GPU off): ✨ in the keyboard (`/rewrite`, `/compose`), the chat's Write and Rewrite answers, official messages, emails, and 👎 revisions of everything but essays (`spark(..., writes=True)`, `SAYSO_WRITER=open`, the default). Fallback for every other Spark call. Offline, it built the neutral drafts and instructions for the main style's training pairs. |
| **Muse Spark 1.3** | Meta Model API (`muse-spark-1.3`, `reasoning_effort: low`) | **Reads**: screenshots and pasted chats (audience, situation, neutral summary, three reply drafts; with the GPU off these drafts are the Back Tap and chat Reply answers), photos and screenshots of the user's own emails and essays. **Writes essays** and their revisions. Fixes voice-note transcripts. Tags uploaded chats when building a style, judges the self-check, and turns feedback into rules. Rewrites a compose answer that only echoed the instruction, and an official message or email that still mixes languages. Fallback when Muse Spark Open fails. |
| **Muse Voice Transcribe 1.0** | Meta Model API (`muse-voice-transcribe-1.0`, `/v1/asr/transcribe`) | 🎙 voice notes in the chat → text (`/transcribe`). Audio is not stored. |
| **Muse Glimmer 30B** (open weights) + the user's LoRA | vLLM on Modal (`serving/modal_app.py`) or Baseten (`serving/baseten/`), switched with `SAYSO_GPU` | The personal model, **trained, benchmarked against Muse Spark Open on the server's own code path, and live in the demo video** on a temporary H100 (`SAYSO_GPU=modal`); **off by default** (no GPU credits). With the GPU on, it writes the chat formats (`message`, `series`): it rewrites drafts in the user's voice (✨, and the Back Tap drafts Spark 1.3 wrote), and writes on its own with a "thought first" (v4). Base Glimmer also tagged situations and thoughts for the training data, so other people's messages never left our own hosted model in the offline pipeline. |

---

## Results

All numbers come from the author's own held-out messages. Only aggregated metrics are committed
(`eval/results/*.json`), never message text.

**Metrics.**
- **Fingerprint ↓**: mean normalized gap to the user's real messages over about 15 stylometric features (length, lines,
  end punctuation, lowercase starts, emoji, laughter, swearing, Latin/Kazakh share, …). 0 means the same averages.
- **chrF ↑**: character n-gram F-score against the user's real message for the same input.
- **Memorized ↓**: outputs copying a training message verbatim or sharing a 40-character span with one.

### 1. What the style adds to Muse Spark (the mode running now)

40 held-out rewrite pairs (a neutral draft → what the user really wrote), the same Meta model with more of the style
in the prompt each time. **Form similarity** = 1 − total variation between the outputs and the user's real messages
over 7 form features (length bucket, lowercase start, end punctuation, laughter, emoji, swearing, question). It is the
same score as the in-app self-check (`build_style.similarity`); 1 means the two can't be told apart by form. **chrF** is
against the user's real message. Script: `eval/style_gain.py`, results: `eval/results/style_gain.json` and
`eval/results/style_gain_open.json`.

| Writer and prompt | Form similarity ↑ | chrF ↑ |
|---|---:|---:|
| Muse Spark 1.3, generic (no style) | 0.69 | 41.8 |
| Muse Spark 1.3 + style profile | 0.92 | 47.4 |
| Muse Spark 1.3 + style profile + the user's real example messages (random) | 0.94 | 54.0 |
| Muse Spark 1.3, production prompt (examples by TF-IDF, + 4 variants) | 0.94 | 53.5 |
| **Muse Spark Open, production prompt (what the app runs now)** | **0.93** | **50.4** |

- The style profile does most of the work on **form**; the user's real messages add most of the gain in **wording**
  (chrF).
- Muse Spark Open matches the user's form about as well as Spark 1.3 (0.93 vs 0.94) but shares fewer of their exact
  words (chrF 50.4 vs 53.5). Its chrF rose to 50.4 after the prompt started asking it to keep the user's fillers,
  laughter, swearing, emoji and message splitting at their own rate. The app uses it because it is an open-weights
  model (the path to self-hosting), with Spark 1.3 one call away as the fallback.
- **Picking examples by meaning did not help.** Examples picked by Fireworks embeddings and by local TF-IDF scored the
  same as random examples, within noise (Nov 1 runs, noted in `eval/style_gain.py`, not in the committed JSON). The
  server keeps TF-IDF because it is free and keeps the topic close, and removed the embeddings so nothing leaves the
  server for it. Picking the variant closest to the user's statistics (best-of-5) kept form but lowered chrF in the
  same runs, so the app keeps the model's own answer.
- Spark's outputs vary run to run: differences of about 0.02 form or 2 chrF between reruns of the same script are
  noise. One "examples" output failed in the committed run (n = 39).

### 2. The personal LoRA vs Muse Spark Open, on the server's own code path

Would the user's own model write better than the live default? The same 40 held-out rewrites as above, written the way
the server writes them with the GPU on: the unchanged `Writer` code, its vLLM requests answered by one H100 running
Muse Glimmer 30B + the LoRA (v4) in an ephemeral Modal app (`eval/lora_gpu.py`, 15-minute hard stop, never the
deployed app). Script: `eval/style_gain.py --writer lora --gpu-ok`, results: `eval/results/style_gain_lora.json`.

| Writer (40 held-out rewrites) | Form similarity ↑ | chrF ↑ | chrF vs Spark Open (95% CI) | chrF wins / losses vs Spark Open |
|---|---:|---:|---:|---:|
| Muse Spark Open, production prompt (the live default) | 0.93 | 49.3 | | |
| **Glimmer 30B + the user's LoRA, 5 candidates + rerank (✨ with the GPU on)** | **0.97** | **55.7** | **+6.4 (+0.8 … +12.4)** | **22 / 15** |
| The same LoRA, first candidate only (no rerank) | 0.98 | 50.0 | +0.8 (−6.2 … +7.3) | 19 / 17 |
| Spark Open's answer, then restyled by the LoRA ("open+lora") | 0.94 | 47.3 | −2.0 (−3.9 … −0.6) | 3 / 11 |

- The LoRA path the keyboard uses with the GPU on matches the user's form better (+0.04, 95% CI +0.01 … +0.07) and
  shares more of their exact wording (chrF +6.4). The interval is wide (40 pairs) but above zero.
- Most of the wording gain comes from the rerank: the LoRA's first candidate alone is about level with Spark Open on
  chrF, while its form is the closest of all.
- Restyling Spark Open's finished answer with the LoRA ("open+lora", the way Back Tap drafts are restyled) came out
  slightly **worse** than Spark Open alone on this rewrite task. The test has no Back Tap case (Spark 1.3 drafts from a
  screenshot), so it doesn't measure that path directly.
- Spark Open scored chrF 49.3 here and 50.4 in `style_gain_open.json`: two runs of the same prompt, within the
  run-to-run noise noted above.

### 3. The personal LoRA vs prompting the same base model

499 held-out pairs (250 reply, 143 rewrite, 106 compose), `eval/results/bench_2026-10-28.json`:

| System | Fingerprint ↓ | chrF ↑ (all) | chrF rewrite | chrF compose | Median length | Memorized |
|---|---:|---:|---:|---:|---:|---:|
| Base Glimmer, same prompt | 2.64 | 13.1 | 28.5 | 22.8 | 73 chars | 0.2% |
| Glimmer + 5 of the user's own messages (few-shot) | 1.01 | 20.5 | 40.7 | 25.5 | 27 chars | 3.8% |
| **Glimmer + the user's LoRA (v1)** | **0.04** | **28.9** | **57.2** | **42.5** | 19 chars | 0.6% |

The user's real messages average about 28 characters. Replies are the hardest task: guessing someone's exact answer is
close to impossible (chrF on replies is 0.2 / 6.8 / 7.0 for the three systems), which is why replies are drafted by
Spark, which sees the whole chat. (The LoRA's rewrite chrF of 57.2 on 143 pairs and Spark's 53.5 on 40 pairs come
from different test sets, so they are not a head-to-head comparison; the head-to-head is section 2.)

### 4. v4: thought first, then the message

`eval/results/bench_v4.json` (ceiling and baseline from `docs/PLAN_v4_thinking.md`). Same 499 pairs, 5 candidates
each. The act and tone of every reply were re-tagged by base Glimmer. That tagger agrees with its own earlier labels
only 48% of the time, so about 48% is the ceiling for act match, and always guessing the most common act scores 36.8%.

| | v2 | v4 | v4 + rerank | v4 with act/tone from the profile |
|---|---:|---:|---:|---:|
| Act match on replies | 44% | 40% | **46%** | 42% |
| Tone mix gap (TV ↓) | 0.09 | 0.11 | 0.12 | **0.06** |
| Fingerprint ↓ (all tasks) | 0.075 | 0.072 | 0.045 | **0.044** |
| Mean length, all tasks (real: 28 chars) | 34 | 26 | 30 | **26** |

Takeaway: the thought does not make the model read the user's mind better (both are near the tagger's noise), but it
makes the mood mix and the length match the user, and the act becomes a **control**: prefill `act: agree`,
`act: refuse` or `act: joke` to get three options with different intents in the user's voice.

### 5. Latency

Live writer: Muse Spark Open with `reasoning_effort: low` answers in about 2–8 s (2.7 s instead of 5.5 s at the
default effort in our test; emails take longer than chat messages). With the GPU warm (measured Oct 29): `/reply`
from a summary 2.4 s, from pasted messages 6 s, from a screenshot 9.7 s, `/compose` 7 s (`docs/REVIEW.md`).

### 6. Blind test: can friends tell SaySo from the real person?

**Result (v3, scored Nov 3, `eval/results/blind_test.json`): five friends could not reliably tell the user's real
messages from SaySo's.**

| | The user's real messages | SaySo's messages |
|---|---:|---:|
| Messages in the test | 10 | 10 |
| Answers (5 friends × 10) | 50 | 50 |
| Answered «Человек» (a person wrote it) | 31 (**62%**) | 28 (**56%**) |
| Called «Человек» by most of the 5 | 7 of 10 | 8 of 10 |
| Median length | 26 chars | 22 chars |

- **Accuracy 53%** (53 of 100 answers right; 50% is chance; exact binomial p ≈ 0.62).
- **Difference +6 points** in how often real vs SaySo messages were taken for a person: 95% CI about −13 to +24
  points (Newcombe), Fisher's exact p ≈ 0.68.
- Per friend, accuracy ranged from 40% to 70%; no single friend did better than chance with confidence (best p ≈ 0.12).

**Caveats, stated plainly.**
- **Small sample:** 5 people, 20 messages, 100 answers. The pooled p-values treat answers as independent; they are
  not quite (each person answered 20). The interval still allows real messages to be taken for a person up to 24
  points more often than SaySo's, so this rules out only a large gap.
- **The author's own runs are excluded** (`score --skip`: the author tried the page before sending it).
- **Items were filtered to be shareable:** friends and family only (no partner, no elders), one message each,
  Russian only, nothing private, not trivial («ок», «ахах»). That is an easier, more neutral slice than real chats.
- **Some real items come from the training split** (`build --include-train`, used because too few held-out messages
  passed the filter), so they were among the messages the style learned from.
- **No plain-AI control in this run** (`--generic 0`), so it doesn't show how often generic AI would pass.
- SaySo's messages came from the live API's chat Reply mode with the GPU off, so they are Muse Spark 1.3 drafts in the
  user's style; the JSON records the writer as `unknown` because the build skipped the warm-up check.

**Protocol** (v3, `eval/blind_test.py`): 20 questions, each one message and its situation in Russian («Друг
спрашивает, пойдёшь ли ты вечером в кино», written by Muse Spark from the neutral summary, never the other person's
words), and one question: «Это написал(а) [the user] или ИИ?» with two buttons, «Человек» / «ИИ». About half the
messages are the user's **real** replies (friends and family only), half **SaySo**'s (`/chat` in Reply mode, in the
user's style) to other situations, never both for the same one; `--generic N` adds plain Muse Spark 1.3 answers as a
control. Muse Spark 1.3 screens every shown message, real and generated alike, and keeps it only if it is safe to show
to many people (no names, places, phones or addresses; nothing intimate, about a partner, sexual or about health; no
heavy swearing or private details), friendly, not trivial and has some personal manner; failing items are dropped and
more are drawn. SaySo items are length-matched to the real ones (the same share in each length third). The test is
served by the API at an unguessable link (`GET /blind/{test_id}`, no token, the page holds no key) and works in any
phone browser, Telegram's included; answers are posted back (`POST /blind/{test_id}/answers`, rate-limited and
size-capped), with an `SS3-…` code as the fallback. `score` reports the share answered «Человек» for real messages vs
for SaySo's (close = people can't tell them apart), with a 95% CI of the difference (Newcombe), Fisher's exact p and
accuracy vs 50% (exact binomial), per person and overall, and writes aggregate numbers only (no message text, no names;
the test is named by an 8-character hash of its id, not the link). v2 (three replies, pick the real one; `SS2-` codes) still scores.

---

## Privacy

- **Only the user's own writing is stored.** Other people's messages, from uploads or screenshots, are read in
  memory to understand the situation, sent to Muse Spark for that reading, and dropped. They are never written to
  the volume, the datasets or the training pairs. Tested in `tests/test_styles.py` (builds a style from a made-up
  WhatsApp chat and asserts that none of the other person's lines are written) and `tests/test_privacy.py` (scans
  everything under `data/` for incoming text from the real exports).
- **Emails and essays:** only the user's own text is kept. Quoted earlier messages and signature blocks in emails are
  cut off, links, emails, phone and card numbers are removed, names of other people and companies in photos and
  screenshots become `[Name]`, and the images are read once and not stored. An email the
  user pastes to answer is used for that one answer and not stored.
- **Voice notes** are transcribed in memory and the audio is not stored. The iPhone's second hearing runs on the device
  only (`requiresOnDeviceRecognition`), so the audio isn't sent to Apple.
- Screenshots are processed in memory. The keyboard's "latest replies" cache holds the user's suggested replies and
  the situation tag, never the summary of the other person's messages.
- The keyboard learns only when the user turns it on (off by default), and only from what they type and send with its
  letter keys: pasted text is never learned, since it may be someone else's words. It skips password, email, URL,
  number, one-time-code and search fields (any field with a content type). Typing works without Full Access; the network features need it.
- **Where text goes.** Writing requests (the user's draft or notes, an email they are answering, their style and
  example messages) go to Muse Spark Open on Baseten; reading requests (screenshots, pasted chats, photos of the user's
  documents) and essays go to Muse Spark 1.3 on the Meta Model API. When one fails, the same request goes to the
  other. Voice notes go to Muse Voice Transcribe, and the transcript (with the iPhone's own hearing) to Muse Spark for
  the fix pass. With the GPU on, the drafts the LoRA rewrites go to our own H100 on Modal (vLLM with its own key).
  Nothing else leaves the server: examples are picked locally.
- **Keys live in `.env` and Modal secrets, never in the repo.** vLLM has its own key, never shipped in the app.
  `data/`, exports, adapters and generated iOS secrets are gitignored.
- Styles, formal writing, learned items and rules can be deleted from the app. SaySo describes *how you write*, never
  your personality. It's framed as your own voice with you in the loop: you always send the message yourself.

---

## Scaling and unit economics (estimates)

**Architecture at scale.** One shared Muse Glimmer 30B base on vLLM, with per-user LoRA adapters (r=16, tens of MB)
loaded from object storage and swapped per request (multi-LoRA vLLM; runtime adapter loading is already used for new
styles). One GPU serves thousands of users because the base weights are shared. Muse Spark Open is open weights, so
the writing step can move to our own GPUs too.

**Tiers.** *Free*: Muse Spark Open with the user's style profile, examples, formal voice and learned rules (the mode
running now). *Pro*: plus the user's own LoRA, refreshed from what they send.

**Cost per active user per month, rough estimates, not measured at scale:**

| Item | Now | After optimization |
|---|---:|---:|
| Muse Spark (~900 generations + 150 screenshots/month) | ≈ $2.4 | |
| GPU share: one rented H100 ≈ $1,450/month serving 5–10k actives | ≈ $0.2–0.3 | |
| Periodic LoRA refresh | ≈ $0.5 | |
| Infra (API, storage) | ≈ $0.1 | |
| **Total** | **≈ $3–3.5** | **≈ $1–1.5** (self-hosted Muse Spark Open for writing + prompt caching) |

Price idea: **$6.99/month** for Pro. At small scale a 24/7 GPU is too expensive per user, so until roughly 2–5k users
the LoRA would be served per token (Fireworks / Together multi-LoRA), and a dedicated GPU after that.

---

## Repo map

```
serving/    modal_app.py    Modal app: vLLM (Glimmer + LoRAs, H100) and the FastAPI API on CPU
            writer.py       read → write (Spark Open / Spark 1.3, fallbacks) → optional LoRA rewrite + rerank; formats;
                            chat modes incl. email and essay; /transcribe; /learn and /feedback logic
            documents.py    the user's own emails and essays → paragraphs + formal profile (txt/md/docx/pdf/mbox, photos)
            styles.py       per-style storage: meta, own turns, profile, pairs, formal writing, rules, feedback, learned
            build_style.py  uploads → parse → which one is you → Spark tagging → profile → pairs → self-check → LoRA
            memory.py       the chat thread (`previous`): refinements revise the last answer
            guards.py       no placeholders, no unasked self-introductions, no remarks about the request
            series.py       auto-series and the parts of a series; length.py: essay length ±10 %
            postprocess.py  the last step of every route: guards, parts, alternative_parts
            blind.py        blind test v3 on the API: the public page and answer post, the token-gated responses
            baseten/        the same vLLM server as a Truss (SAYSO_GPU=baseten)
            fireworks.py    Fireworks client (blocked: uploads disabled)
pipeline/   parse_telegram.py, parse_whatsapp.py, parse_instagram.py, sources.py   parsers → one turn format
            situations.py   situation / thought tagging with base Glimmer
            build_pairs.py  rewrite / compose / reply pairs (Muse Spark Open)
            style_profile.py, style_stats.py (reranker), lexicon.py, add_thoughts.py
training/   modal_train.py (Unsloth QLoRA), build_prefs.py + modal_prefs.py (SimPO, v3), fireworks_sft.py
eval/       bench_generate.py, metrics.py, style_gain.py + lora_gpu.py (the LoRA on a one-off H100 for --writer lora),
            smoke_api.py, blind_test.py + blind_template.html, results/ (aggregated metrics only)
tests/      test_api_auth.py, test_blind_test.py, test_blind_api.py, test_parsers.py, test_privacy.py, test_styles.py,
            test_writer_fakes.py, test_formal.py, test_memory.py, test_guards.py, test_series.py, test_length.py,
            test_thread_api.py, test_voice.py, test_sec_review.py, test_style_gain_lora.py, test_whatsapp_time.py,
            test_cov_*.py,
            fixtures/ (made-up chats and documents only)
ios/        SaySoApp/ (Chat with 🎙, Styles split by kind with source guides and editable lists, formal writing
            import, Keyboard settings, Settings (language + setup checklist + "Add the SaySo shortcut"), the
            onboarding tour, App Intents), SaySoKeyboard/ (letter keys with a UIKit touch layer, panel, result
            stack), Shared/ (API client, Localizable.xcstrings: English + Russian), scripts/
docs/       SUBMISSION.md, VIDEO_SCRIPT.md, X_POST.md, DESIGN_BRIEF.md, deck/, video/, reviews/, plans and earlier reviews
```

## API reference

`serving/modal_app.py`, one FastAPI app on Modal CPU. Every route needs `Authorization: Bearer <SAYSO_API_TOKEN>`;
the token (and a 60 MB size cap) is checked before any body is read, so a request without it gets 401 at once.
Generation routes take `style` (default `"main"`) and `format` (`message` | `series` | `official` | `email`; unknown
values fall back to `message`); `audience` is `partner` | `friends` | `family` | `elder_informal` (unknown →
`friends`). Errors: 404 no such style, 413 too large, 422 invalid input, 502 a model didn't answer, 503 the GPU is
warming up (only when `SAYSO_GPU` is on).

| Route | Request | Response |
|---|---|---|
| `POST /rewrite` | JSON `{text` (≤ 2000), `audience, situation?, style?, format?, previous?}` | `{text, parts, candidates, styled, audiences}`: `parts` = the messages of a series (also of a long `message`, see auto-series below), `candidates` = alternatives, `styled` = written by the LoRA |
| `POST /compose` | JSON `{instruction` (≤ 1000), `audience, situation?, style?, format?, previous?}` | same as `/rewrite` |
| `POST /reply` | a screenshot as the raw body (`image/*`, ≤ 4 MB; `?audience=&style=&format=` in the query), or JSON `{image` (base64) `, image_type` \| `messages` (≤ 4000) \| `summary` (≤ 400) `+ situation, options, audience?, instruction?` (≤ 300) `, style?, format?, previous?}`. Sending back `summary` + `options` with another audience restyles without reading again | `{context: {audience, audiences, situation, summary}, replies: [{intent, tone, thought, styled, text, parts}] × 3, options: [{act, draft}], ms: {read, total}}` |
| `POST /chat` | JSON `{mode: write \| rewrite \| reply \| email \| essay, text` (≤ 4000) `, audience, style?, format?, instruction?, history: [{answer, feedback}]` (≤ 12) `, question?` (essay, ≤ 1000) `, words?` (essay, 50–900, default 250) `, reply_to?` (email being answered, ≤ 6000; the app's Reply → Email sends it) `, previous?}`. Feedback on the last history item revises that answer | `{text, parts, alternatives, alternative_parts, audience, audiences, learned}` (`learned` = a new rule or null); email adds `subject`; essay adds `outline, questions, words, cliches` |
| `POST /transcribe` | multipart `audio`: mono 16-bit WAV (must start with `RIFF`, else 422), ≤ 10 MB; optional form fields `language` (en \| ru: English adds `languageBias`), `mode` (the Chat mode), `audience`, `context` (≤ 4000, the text the note is about; its names become `keywords`), `heard` (≤ 4000, the iPhone's on-device transcript) | `{text}` (Muse Voice Transcribe, then the Muse Spark fix pass; audio not stored) |
| `POST /learn` | JSON `{style?, items: [{text` (≤ 2000) `, audience, suggested?}]` (≤ 50)`}` from the keyboard | `{learned, rules}` |
| `POST /feedback` | JSON `{audience, style?, format?, answer, edited?, liked}` | `{learned}` (a rule or null) |
| `GET /styles` | | `{styles: [{id, name, status, stage, progress, error, source, counts, scores, lora, adapter_ready, created, needs, participants, chats, me}]}` |
| `GET /styles/{id}` | | the same fields plus `preferences, formal: {documents, counts, paragraphs, profile, kinds: {email, essay}, openers, signoffs}, custom, learning: {typed, edited, liked, recent}, profile` (per audience) `, examples` |
| `POST /styles` | multipart `name` (≤ 40) + `files` (1–200, ≤ 50 MB in all: chat exports, screenshots, screen-recording frames) | the new style (`stage` moves through parsing → needs_me → reading → profile → checking → [training] → ready; poll `GET /styles/{id}`) |
| `PATCH /styles/{id}` | JSON `{name?, me?, chats?: {chat: audience}, remove_preference?, remove_learned?, clear_documents?}`; `me`/`chats` only while `stage = needs_me` (else 409) | the full style view |
| `PATCH /styles/{id}/custom` | JSON, only the fields that change: `{email?: {openers?, signoffs?, default_opener?, default_signoff?, avoid?}, essay?: {avoid?}, message?: {avoid?}}`; a list replaces the stored one, `null` forgets it (back to what SaySo parsed), `{kind: null}` forgets the kind; unknown fields 422 | the full style view |
| `DELETE /styles/{id}` | | `{deleted}`; 409 for the main style |
| `POST /styles/{id}/documents` | multipart `kind` (`email` \| `essay`, default `essay`), `files` (≤ 40, each ≤ 20 MB, ≤ 25 MB in all: .txt .md .docx .pdf .mbox, photos/screenshots .jpg .png .heic .webp, at most 30 images read) and/or `text` (pasted, first 50,000 characters) | `{documents, counts, paragraphs, profile}` (the formal voice) |
| `GET /latest` | | the last `/reply` for the keyboard: `{audience, situation, replies, at}` or `{}` |
| `GET /warmup` | | `{ready, gpu}`; with `SAYSO_GPU=off` (now) it answers `{ready: false, gpu: "off"}` at once, otherwise it wakes the GPU and waits |
| `GET /blind/{test_id}` | **no token** (the id is 24 random characters) | the blind-test page (`text/html`, `no-store`, `noindex`) or 404 |
| `POST /blind/{test_id}/answers` | **no token**; body (any content type) `{sid, name?, answers: ["H" \| "A" × questions]}`, ≤ 8 KB | `{ok}`; 422 junk, 413 too large, 429 rate limit (8 per 10 min per address, 120 per hour per test), 507 full (400 responses); stored without IP or headers |
| `GET /blind/{test_id}/responses` | | `{responses: [{sid, name, answers, at}]}` |

- **`previous`** (`/rewrite`, `/compose`, JSON `/reply`, `/chat`, including email and essay): up to 3 `{request, answer}`
  (each ≤ 6000 characters), oldest first, the earlier turns of this chat thread. A request that refines the last answer ("на русском", "in
  English", "shorter", "more formal", "add that I'm sick") revises that answer and keeps its content; a new topic is
  written as usual, with the earlier turns only as context for consistency (`serving/memory.py`, a heuristic, no
  extra model call). In `/reply`, a refinement with no new chat returns the last reply revised (`intent: "other"`).
- **`alternative_parts`**: every response with `alternatives` also has it, parallel to `alternatives`: each item is
  the parts of that alternative (its messages if it is a series, else `[alternative]`).
- **Auto-series**: with format `message` (Write, Rewrite), when the user usually sends several short messages to that
  audience (from their own turns) and the content is long, the model may write 2–5 messages: `parts` then has more
  than one item (`serving/series.py`). `series` always splits; `official` and `email` never do.
- **Guards** on every answer (`serving/guards.py`): no template placeholders (`[Name]`, `<company>`), no
  self-introduction (name, role, organization) unless asked, no remarks about the request; the main answer is fixed,
  alternatives that break a rule are dropped. The formal profile shapes tone only, never facts about the user.
- **Essay length**: the prompt states the target and a ±10 % range; under 90 % an "expand to N words" pass runs (up
  to 2), over 115 % a trim pass; `words` is the final count (`serving/length.py`).

## How to run

You need a Modal account, a Meta Model API key, a Baseten key for Muse Spark Open, and for the personal model the
Glimmer weights and an adapter on the `sayso-data` volume. Your own data never goes in the repo.

```bash
cp .env.example .env    # fill META_API_KEY, BASETEN_API_KEY, SAYSO_API_TOKEN; add SAYSO_API_URL and SAYSO_GLIMMER_URL
```

```bash
python3 -m venv .venv && .venv/bin/pip install modal httpx
```

Modal secrets: `sayso` (`SAYSO_API_TOKEN`), `sayso-glimmer` (`GLIMMER_KEY`), `sayso-meta` (`META_API_KEY`),
`sayso-extra` (`BASETEN_API_KEY` for Muse Spark Open), and optionally `sayso-baseten` (the LoRA on Baseten).

```bash
SAYSO_GPU=off .venv/bin/modal deploy serving/modal_app.py
```

`SAYSO_WRITER=open` (default) lets Muse Spark Open write and `SAYSO_WRITER=meta` makes Muse Spark 1.3 the first writer.
Use `SAYSO_GPU=modal` or `SAYSO_GPU=baseten` to serve the LoRA (the demo video was filmed with `SAYSO_GPU=modal`), and
add `SAYSO_TRAIN=on` to let new styles train their own LoRA. `SAYSO_CLEAN=on` (default) keeps swearing out of
everything SaySo writes; `SAYSO_CLEAN=off` lets the user's own swearing through.

**Smoke test the deployed API** (made-up inputs only):

```bash
.venv/bin/python eval/smoke_api.py
```

```bash
.venv/bin/python eval/smoke_api.py --spark --show
```

(`--gpu` also warms the GPU and checks `/rewrite /compose /reply`; `--gpu --vision tests/fixtures/chat.png` reads a
screenshot.)

**Unit tests** (no network, no GPU; tests that need the private exports skip):

```bash
python3 -m unittest discover -s tests
```

**Style gain** (how much the style adds to Muse Spark; needs the private held-out pairs in `data/` and the keys in
`.env`; writes only aggregated numbers):

```bash
.venv/bin/python eval/style_gain.py --limit 40
```

```bash
.venv/bin/python eval/style_gain.py --limit 40 --writer open --only production
```

```bash
.venv/bin/python eval/style_gain.py --limit 40 --writer lora --gpu-ok
```

(the first writes `eval/results/style_gain.json` with Muse Spark 1.3, the second `style_gain_open.json` with Muse Spark
Open, the third `style_gain_lora.json`: the LoRA on the server's GPU-on path next to Spark Open. It starts one H100 in
an ephemeral Modal app, prints the expected cost first and stops at 15 minutes; side-by-side samples go to the
gitignored `data/style_gain/` only.)

**Blind test** (needs `SAYSO_API_URL`, `SAYSO_API_TOKEN`, `META_API_KEY` and the private pairs; the page, the public
questions and the answer key go to the gitignored `data/blind/<test_id>/`):

```bash
python3 eval/blind_test.py build --n 20 --author <name>
```

Deploy the API (it serves the page), then upload the page to the `sayso-data` volume; `publish` prints the link to
send:

```bash
SAYSO_GPU=off .venv/bin/modal deploy serving/modal_app.py
```

```bash
.venv/bin/python eval/blind_test.py publish
```

When friends have answered (codes they sent back, `SS3-…`, can be added after `--server`):

```bash
python3 eval/blind_test.py score --server
```

(`build --generic 2` adds plain-AI controls, `--no-warmup` skips waking the GPU; `score --codes-file codes.txt` reads
one code per line; a v2 test: `score --answers data/blind/answers.json SS2-...`.) `score` writes
`eval/results/blind_test.json`, aggregate numbers only.

**iOS** (Xcode, deployment target iOS 26): generate the API URL and token for the app from `.env`, then open the
project, set your signing team, and run the `SaySo` scheme on a device. Then, in the app's **Settings** tab:

1. **Add the SaySo keyboard**: Settings → General → Keyboard → Keyboards → Add New Keyboard → SaySo.
2. **Allow Full Access** for SaySo (needed to reach the API), then type in the test field and switch to SaySo 🌐 once.
3. **Set up the Back Tap shortcut**: tap **Add the SaySo shortcut** (it opens the ready shortcut, an iCloud link) →
   **Add Shortcut**, then Settings → Accessibility → Touch → Back Tap → Double Tap → that shortcut. **Build it
   yourself** shows the same thing by hand: *Take Screenshot → Reply with SaySo* (leave Audience empty, so it asks every
   time) *→ Choose from List → Copy to Clipboard*. Turn on **I've set it up**.
4. **Check the connection**: **Test now**.

The app, keyboard and shortcut are in English and Russian (Settings → Language).

```bash
sh ios/scripts/gen_secrets.sh
```

```bash
open ios/SaySo.xcodeproj
```

## Current limits

- **Single-user server.** One bearer token for the whole API, readable from the app binary. Fine for a demo, not for
  release. Next: per-device tokens (Sign in with Apple / App Attest).
- **GPU off by default** (`SAYSO_GPU=off`). The personal LoRA beat Muse Spark Open in the head-to-head above and wrote
  the keyboard's ✨ suggestions live in the demo video, on a temporary H100, but it is not hosted day to day (no GPU
  credits). So what you get from the server now comes from Muse Spark Open (and Muse Spark 1.3 for screenshot and
  Reply answers and essays) with the style profile, examples and rules.
- **No swearing** (`SAYSO_CLEAN=on`): a demo choice. For a user who swears a lot it makes SaySo cleaner than they are;
  `SAYSO_CLEAN=off` turns it off.
- **Per-style LoRA is behind `SAYSO_TRAIN`** (off). New styles get a profile, examples and a self-check; their own
  LoRA needs a GPU run (~10–30 min on an H100) and at least 150 of the user's turns.
- The LoRA writes only the chat formats (`message`, `series`); `official`, `email` and `essay` are always written by
  Spark in the user's formal voice. That voice is only as good as the emails and essays the user adds; without them
  SaySo writes plainly.
- The keyboard needs Full Access for network features. Free signing expires every 7 days.
- Chat memory decides "refine the last answer" vs "new request" with a word-list heuristic, so an unusual follow-up
  can be taken as a new request (the earlier turns still go along as context).
- The blind test is small (5 friends, 100 answers) and has no plain-AI control; see Results for its caveats.
- Muse Spark reads other people's messages in screenshots and uploads to understand them (in memory, not stored by
  SaySo). The offline pipeline used our own hosted Glimmer for that instead; moving live reading there is planned.

---

Built during the hackathon, commit by commit. Small commits show what was built when.
