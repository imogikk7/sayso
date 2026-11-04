# X post (draft)

Posted from the author's account, so "me" / "my" is the author. Every number is from `eval/results/` (blind test:
`blind_test.json`; form similarity: `style_gain.json`, `style_gain_open.json`; LoRA vs Spark Open: `style_gain_lora.json`). No names, no real messages.
Attach the demo video (or a 10–15 s clip of beat 1: draft → ✨ → series stack) to the main post.

## Main post (278 / 280 characters; X counts the link as 23)

```
AI replies sound like AI. SaySo writes like you: your length, lowercase, slang, the way you split one thought into 3 texts.

iOS keyboard + Back Tap + chat, on Meta's Muse models.

Blind test: 5 friends told me from SaySo 53% of the time. Chance is 50%.

github.com/imogikk7/sayso
```

## Optional thread (3 replies, each ≤ 280)

**1/3 · how it works (245)**
```
How it works: Muse Spark 1.3 reads the chat. My own LoRA on Muse Glimmer 30B (Meta open weights) writes it my way: in the demo it ran live on a temporary H100. GPU off, Muse Spark Open writes in my style. Muse Voice Transcribe hears voice notes.
```

**2/3 · what you do with it (≈ 250)**
```
Press the Action Button on any chat: it reads the screenshot and writes 3 replies the way you would. Pick one, it's copied. Emails and essays come out in your formal voice, learned from your own. 👎 "too casual" becomes a rule. You always press send.
```

**3/3 · honest numbers (256)**
```
Honest numbers: on 40 held-out rewrites my LoRA scored chrF 55.7 vs 49.3 for Muse Spark Open (CI +0.8…+12.4). Blind test is small: 100 answers, no plain-AI control. Built solo in 9 days for the Meta Global AI Developer Hackathon. Code and evals are public.
```

## Rules for any edit
- Don't say "undetectable", "fools people" or "passes as human". Say "couldn't reliably tell" or give the number.
- Keep "small sample" (or the CI) next to the blind-test number whenever there is room.
- Don't claim the personal LoRA writes the live answers today: it wrote the ✨ suggestions in the demo video on a
  temporary H100; day to day the GPU is off and Muse Spark Open writes.
- Add the hackathon's required hashtag or handle here if the rules ask for one (check the submission page).
