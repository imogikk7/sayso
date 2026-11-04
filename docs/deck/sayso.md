---
marp: true
theme: sayso
paginate: true
size: 16:9
title: SaySo — AI that writes the way you'd say it
footer: SaySo · Meta Global AI Developer Hackathon 2026
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "" -->

![w:120](../../ios/SaySoApp/Assets.xcassets/AppIcon.appiconset/icon.png)

# SaySo

AI that writes the way *you'd* say it.

Your own voice, adapted to who you're talking to — in any messenger.

<p class="note">Built on Meta Muse Spark Open (open weights) · Muse Spark 1.3 · Muse Voice Transcribe · Muse Glimmer 30B · Meta Global AI Developer Hackathon · indie track · solo</p>

---

<div class="kicker">The problem</div>

## AI replies sound like AI, not like you.

<div class="cols wide-left">
<div>

- Too long, too polite, perfect punctuation — people notice at once.
- Real chat is short, lowercase, split into several messages, languages mixed.
- You write differently to your partner, your friends and your elders. Generic AI writes the same way to everyone.

</div>
<div>

<div class="card">
<span class="who">How the author really writes (held-out messages)</span>

**95%** start lowercase
**4%** end with punctuation
**~28** characters per turn, **~1.9** messages in a row

</div>

<p class="note">Aggregated form statistics from <code>eval/results/bench_v4.json</code>; no message text leaves the author's machine.</p>

</div>
</div>

---

<div class="kicker">The product</div>

## Writes like you, where you type

<div class="cols wide-left">
<div style="font-size: 22px;">

- **Own keyboard**, RU / EN keys, stock iOS look; ✨ → 1–3 versions *in your style*
- **Audience** and **format**: message · series (a stack, sent part by part) · official · email
- **Back Tap / Action Button**: screenshot → three replies in your voice → pick one, it's copied
- **Chat**: Write · Rewrite · Reply → message, series, official, **email**, **essay**; 🎙 voice; remembers the thread ("in English")
- **Styles** by kind: Messages · Emails · Essays, with a self-check
- **Keeps learning** from what you send (opt-in) and fix (👎)
- English and Russian UI

</div>
<div style="font-size: 18px;">

<div class="card" style="margin-bottom: 16px;">
<span class="who">One iOS Shortcut</span>
<b>Take Screenshot → Reply with SaySo → Choose from List → Copy to Clipboard</b>
One tap installs it (<em>Add the SaySo shortcut</em>). Replies also wait in the keyboard.
</div>
<div class="card">
<span class="who">Chat answers</span>
<b>A series is separate bubbles</b>
Each with a copy button; other versions fold into stacks.
</div>

</div>
</div>

---

<div class="kicker">The product · formal voice</div>

## Emails and essays that sound like you, too

<div class="cols">
<div style="font-size: 23px;">

- Add **your own** emails and essays: files (.txt · .docx · .pdf · Gmail Takeout), photos of pages, screenshots, paste. Step-by-step guides per app.
- **Essays teach voice only**: word choice, sentence length, linking words. Never structure or topic.
- **Emails teach manner only**: greeting, sign-off, how direct you are. Never content.
- Quoted replies from others and old section labels are cut off.

</div>
<div style="font-size: 23px;">

- **Email**: subject + body from your notes, optionally answering an email you paste.
- **Essay**: plan → text from **your notes only**, structure from the task, first person for personal statements.
- Self-check for AI clichés ("in today's fast-paced world") and length, one fix pass.
- Then up to **3 questions** that would make it stronger: answer by 🎙 voice or text.

</div>
</div>

<p class="note">Voice notes: Muse Voice Transcribe 1.0, audio not stored. Photos of pages: read by Muse Spark 1.3, not stored. Source: <code>serving/documents.py</code>, <code>serving/writer.py</code>.</p>

---

<div class="kicker">How it works</div>

## Four Meta models, one voice

<div class="cols-4" style="font-size: 17px;">
<div class="card accent">
<span class="who">Open weights · Baseten</span>
<b>Muse Spark Open</b>
<strong>Writes</strong> in your style: chat, email, revisions; ✨ when the GPU is off.
</div>
<div class="card">
<span class="who">Meta Model API</span>
<b>Muse Spark 1.3</b>
<strong>Reads</strong> screenshots, chats, photos; drafts replies; writes essays.
</div>
<div class="card">
<span class="who">Meta Model API</span>
<b>Muse Voice Transcribe 1.0</b>
<strong>Listens</strong>: 🎙 notes in Chat become text. Audio not stored.
</div>
<div class="card">
<span class="who">Meta open weights</span>
<b>Your LoRA on Muse Glimmer 30B</b>
Writes ✨ and restyles replies with the GPU on. Live in the demo; off by default.
</div>
</div>

<p style="font-size: 22px; margin-top: 18px;">In every prompt: <strong>your style profile</strong> per audience × situation · <strong>your real messages</strong> as examples · <strong>your formal voice</strong> · <strong>rules learned</strong> from your corrections. You always send manually.</p>

<p class="note">The style profile describes how you write — length, case, punctuation, emoji, languages, linking words — never personality.</p>

---

<div class="kicker">Results · the live path</div>

## Each layer makes it sound more like you

<div class="steps">
<div class="card">
<span class="who">Generic Muse Spark</span>
<div class="row"><div class="stat-label">Form similarity</div><div class="stat">0.69</div></div>
<div class="row"><div class="stat-label">chrF</div><div class="stat" style="font-size: 44px;">41.8</div></div>
</div>
<div class="arrow">→</div>
<div class="card">
<span class="who">+ your style profile</span>
<div class="row"><div class="stat-label">Form similarity</div><div class="stat">0.92</div></div>
<div class="row"><div class="stat-label">chrF</div><div class="stat" style="font-size: 44px;">47.4</div></div>
</div>
<div class="arrow">→</div>
<div class="card accent">
<span class="who">+ your real messages</span>
<div class="row"><div class="stat-label">Form similarity</div><div class="stat accent">0.94</div></div>
<div class="row"><div class="stat-label">chrF</div><div class="stat accent" style="font-size: 44px;">54.0</div></div>
</div>
</div>

<br>

<p style="font-size: 23px;">40 held-out pairs: a neutral draft → what the user really wrote. Muse Spark 1.3, only the prompt changes. <strong>Default live writer (GPU off), Muse Spark Open (open weights) with the same prompt: form 0.93 · chrF 50.4</strong> — about the same form, fewer of the user's exact words (it keeps their fillers, swearing, emoji and message splitting at their own rate). Picking examples by meaning scored the same as random ones.</p>

<p class="note">Form similarity = 1 − total variation of form features (length, case, punctuation, emoji, languages) vs the real messages, as in the app's style self-check. chrF = character n-gram overlap with the real message. Reruns vary by about 0.02 form / 2 chrF. Source: <code>eval/style_gain.py</code> → <code>eval/results/style_gain.json</code>, <code>style_gain_open.json</code>.</p>

---

<div class="kicker">Results · personal model</div>

## Your own LoRA vs the live writer

<div class="cols-4">
<div class="card accent">
<span class="who">Form similarity</span>
<div class="stat accent">0.97</div>
<div class="stat-label">LoRA · Muse Spark Open 0.93</div>
</div>
<div class="card accent">
<span class="who">chrF</span>
<div class="stat accent">55.7</div>
<div class="stat-label">LoRA · Muse Spark Open 49.3</div>
</div>
<div class="card">
<span class="who">chrF difference</span>
<div class="stat">+6.4</div>
<div class="stat-label">95% CI +0.8…+12.4</div>
</div>
<div class="card">
<span class="who">Better / worse</span>
<div class="stat">22<span style="font-size: 36px;"> / 15</span></div>
<div class="stat-label">of 40 held-out rewrites</div>
</div>
</div>

<div style="font-size: 17px; margin-top: 10px;">

- Server's GPU-on path (Glimmer 30B + LoRA v4, 5 candidates + rerank) vs Muse Spark Open, 40 held-out rewrites. Rerank does most of it (first candidate: chrF 50.0); restyling Spark Open's answer: chrF −2.0.
- v4 thinks first (intent + tone), then writes: 26 chars (real 28), intent match 46% (ceiling ~48%). Live in the demo on a temporary H100; off by default.

</div>

<p class="note">Source: <code>eval/results/style_gain_lora.json</code> (<code>eval/style_gain.py --writer lora</code>, one H100 in an ephemeral Modal app) · <code>eval/results/bench_v4.json</code> (length: v4 with act/tone from the profile; intent match: v4 + rerank) · ceiling and baseline: <code>docs/PLAN_v4_thinking.md</code>.</p>

---

<div class="kicker">Results · blind test</div>

## Friends couldn't reliably tell SaySo from the user

<div class="cols-4">
<div class="card accent">
<span class="who">Accuracy</span>
<div class="stat accent">53%</div>
<div class="stat-label">chance 50% · exact binomial p ≈ 0.62</div>
</div>
<div class="card">
<span class="who">"A person wrote it" · real</span>
<div class="stat">62%</div>
<div class="stat-label">of answers on the user's real messages</div>
</div>
<div class="card">
<span class="who">"A person wrote it" · SaySo</span>
<div class="stat accent">56%</div>
<div class="stat-label">of answers on SaySo's messages</div>
</div>
<div class="card">
<span class="who">Difference</span>
<div class="stat">+6</div>
<div class="stat-label">points · 95% CI −13…+24 · Fisher p ≈ 0.68</div>
</div>
</div>

<div style="font-size: 18px; margin-top: 14px;">

- 5 friends × 20 messages (10 real, 10 SaySo) = 100 answers; one message per question, tap «Человек» or «ИИ».
- **Small sample**, author's own runs excluded; shareable items only (friends and family, one message, Russian); some real items from the training split; no plain-AI control. SaySo: Muse Spark 1.3 replies in the user's style.

</div>

<p class="note">Source: <code>eval/results/blind_test.json</code> (aggregate numbers only) · <code>eval/blind_test.py</code>.</p>

---

<div class="kicker">Privacy by design</div>

## Only your own writing is kept

<div class="cols" style="font-size: 24px;">
<div>

- Trained and prompted **only on what you wrote**.
- Other people's messages are read **in memory** for context, then discarded.
- Uploads are parsed in memory (quoted email replies and signatures cut off, other people's names → [Name]); **screenshots, photos and voice notes are never stored**.
- The keyboard learns only if you turn it on, never from pasted text, and ignores password, email, URL, one-time-code and search fields.

</div>
<div>

- See **what it learned from you**; forget any rule.
- Delete a style at any time.
- No sign-up.
- Public repo holds code and aggregated numbers only — no messages, no data.

</div>
</div>

<br>

<p class="note">Positioning: authenticity and your own voice, human in the loop. Not "undetectable AI".</p>

---

<div class="kicker">How it scales</div>

## One base model, one small adapter per user

<div class="cols">
<div>

- **One shared Muse Glimmer 30B** base on the GPU.
- **Per-user LoRA adapters** swapped per request (multi-LoRA vLLM) — a new user adds an adapter, not a GPU.
- Users without their own LoRA yet run on Muse Spark Open + their style profile — open weights, so it can be self-hosted too.

<p class="note">Cost per active user / month: ≈ <strong>$3–3.5</strong> now → ≈ <strong>$1–1.5</strong> optimized. Estimates.</p>

</div>
<div>

<div class="card" style="margin-bottom: 18px;">
<span class="who">Free</span>
<b>Muse Spark Open + your style profile</b>
Styles from your chats, emails and essays; keyboard, Back Tap replies.
</div>
<div class="card accent">
<span class="who">Pro · $6.99 / month (estimate)</span>
<b>Your own LoRA on Muse Glimmer</b>
A personal model trained on your own messages.
</div>

</div>
</div>

---

<div class="kicker">Roadmap</div>

## What's next

<div class="cols-4">
<div class="card"><b>Accounts</b>Sync styles across devices, beyond a single-device token.</div>
<div class="card"><b>LoRA training queue</b>Per-user adapters trained in the background as people upload chats.</div>
<div class="card"><b>Kazakh &amp; more languages</b>Kazakh first, then any language people write in.</div>
<div class="card"><b>Android</b>The same keyboard and screenshot replies.</div>
</div>

---

<!-- _class: lead -->
<!-- _footer: "" -->

# Thank you

SaySo — AI that writes the way *you'd* say it.

Try it, break it, tell us where it doesn't sound like you.

<p class="note">github.com/imogikk7/sayso · built solo during the hackathon on Meta Muse Spark Open · Muse Spark 1.3 · Muse Voice Transcribe · Muse Glimmer 30B</p>
