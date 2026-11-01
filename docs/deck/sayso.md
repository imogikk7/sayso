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

# SaySo

AI that writes the way *you'd* say it.

Your own voice, adapted to who you're talking to — in any messenger.

<p class="note">Built on Meta Muse Spark 1.3 + Muse Glimmer 30B · Meta Global AI Developer Hackathon · indie track · solo</p>

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

## A keyboard that writes like you

<div class="cols" style="grid-template-columns: 1.4fr 1fr 1fr; gap: 28px;">
<div style="font-size: 23px;">

- **Own keyboard**, RU / EN letter keys; tap ✨ → *in your style*
- Pick **audience** and **format**: message · series · official · email
- **Series** come as a stack, sent part by part
- **Back Tap** on the iPhone: screenshot → ready replies
- **Styles** built from your uploaded chats, with a self-check
- **Chat and keyboard keep learning** from what you send and fix

</div>
<div>

<!-- Replace this div with: ![h:400](img/keyboard.png) -->
<div class="ph">screenshot:<br>keyboard → ✨ → variants<br>(img/keyboard.png)</div>

</div>
<div>

<!-- Replace this div with: ![h:400](img/backtap.png) -->
<div class="ph">screenshot:<br>Back Tap → replies<br>or style self-check<br>(img/backtap.png)</div>

</div>
</div>

---

<div class="kicker">How it works</div>

## Two Meta models, one voice

<div class="cols-3">
<div class="card">
<span class="who">Meta Model API</span>
<b>Muse Spark 1.3</b>
Reads uploaded chats and screenshots, understands the situation, drafts what to say.
</div>
<div class="card accent">
<span class="who">Meta open weights</span>
<b>Your LoRA on Muse Glimmer 30B</b>
Fine-tuned on your own messages only. Writes the draft in your voice.
</div>
<div class="card">
<span class="who">In every prompt</span>
<b>Your style, made explicit</b>
Style profile per audience · your real messages as examples · rules learned from your corrections.
</div>
</div>

<br>

<p>Draft → <strong>Spark</strong> (what to say) → <strong>your LoRA</strong> (how you'd say it) → you pick, edit, send. You always send manually.</p>

<p class="note">The style profile describes how you write — length, case, punctuation, emoji, languages — never personality.</p>

---

<div class="kicker">Results · Muse Spark path</div>

## Each layer makes it sound more like you

<div class="steps">
<div class="card">
<span class="who">Generic Muse Spark</span>
<div class="row"><div class="stat-label">Form similarity</div><div class="stat">0.68</div></div>
<div class="row"><div class="stat-label">chrF</div><div class="stat" style="font-size: 44px;">39.5</div></div>
</div>
<div class="arrow">→</div>
<div class="card">
<span class="who">+ your style profile</span>
<div class="row"><div class="stat-label">Form similarity</div><div class="stat">0.91</div></div>
<div class="row"><div class="stat-label">chrF</div><div class="stat" style="font-size: 44px;">46.4</div></div>
</div>
<div class="arrow">→</div>
<div class="card accent">
<span class="who">+ your real messages</span>
<div class="row"><div class="stat-label">Form similarity</div><div class="stat accent">0.93</div></div>
<div class="row"><div class="stat-label">chrF</div><div class="stat accent" style="font-size: 44px;">53.7</div></div>
</div>
</div>

<br>

<p>40 held-out pairs: a neutral draft → what the user really wrote. Same Meta model, only the prompt changes; the last column is what the app runs.</p>

<p class="note">Form similarity = 1 − total variation of form features (length, case, punctuation, emoji, languages) vs the real messages, as in the app's style self-check. chrF = character n-gram overlap with the real message. Source: <code>eval/style_gain.py</code> → <code>eval/results/style_gain.json</code>.</p>

---

<div class="kicker">Results · personal model</div>

## The LoRA thinks first, then writes like you

<div class="cols-4">
<div class="card">
<span class="who">Reply length</span>
<div class="stat accent">24</div>
<div class="stat-label">chars · real 28 · earlier LoRA 38</div>
</div>
<div class="card">
<span class="who">Form distance</span>
<div class="stat accent">0.07</div>
<div class="stat-label">vs 0.12 earlier LoRA (lower is better)</div>
</div>
<div class="card">
<span class="who">Tone mix distance</span>
<div class="stat accent nowrap" style="font-size: 50px; line-height: 1.68;">0.05–0.07</div>
<div class="stat-label">vs 0.09 earlier LoRA</div>
</div>
<div class="card">
<span class="who">Intent match</span>
<div class="stat accent">46%</div>
<div class="stat-label">ceiling ~48% · guessing 36.8%</div>
</div>
</div>

<div style="font-size: 23px; margin-top: 22px;">

- 499 held-out test pairs. The model writes a short thought (intent + tone) in Glimmer's reasoning channel, then the message.
- The intent is a control: *agree*, *refuse*, *joke* → three replies with different intents, all in your voice.
- **Blind test** (friends guess: real or SaySo?): *TODO — results pending.*

</div>

<p class="note">Source: <code>docs/PLAN_v4_thinking.md</code>, <code>eval/results/bench_v4.json</code>. Intent ceiling = how often the tagger agrees with itself.</p>

---

<div class="kicker">Privacy by design</div>

## Only your own messages are kept

<div class="cols">
<div>

- Trained and prompted **only on what you wrote**.
- Other people's messages are read **in memory** for context, then discarded.
- Uploaded chats are parsed in memory; **screenshots are never stored**.
- The keyboard ignores password, email, URL, one-time-code and search fields.

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
- Users without their own LoRA yet run on Muse Spark + their style profile.

<p class="note">Cost per active user / month: ≈ <strong>$3</strong> now → ≈ <strong>$1–1.5</strong> optimized. Estimates.</p>

</div>
<div>

<div class="card" style="margin-bottom: 18px;">
<span class="who">Free</span>
<b>Muse Spark + your style profile</b>
Styles from your chats, keyboard, Back Tap replies.
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

<p class="note">github.com/imogikk7/sayso · built solo during the hackathon on Meta Muse Spark 1.3 + Muse Glimmer 30B</p>
