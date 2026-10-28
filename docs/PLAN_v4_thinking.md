# v4: imitate the user's train of thought, not their vocabulary

Goal: given the other person's message, the model first decides what *this user* would think and do,
then says it in their speech. Style profile from imports drives both.

## Data (status 2026-10-28 evening)
- `pipeline/situations.py --thoughts` → `data/thoughts.jsonl`: for every turn in `data/pairs_v2`,
  our base Glimmer labels the user's own message with `act` (agree, refuse, ask_back, clarify, joke, tease,
  support, comfort, apologize, argue, explain, share, react, affection, plan, other), `tone` (warm, playful,
  teasing, neutral, blunt, irritated, excited, tired, caring, sarcastic) and `gist` (6–15 neutral English words:
  what they mean). Input: situation + summary + the user's own message only. Resumable; re-run to finish.

## Training format (v4)
Use Glimmer's own reasoning channel for the thought, then the user channel for the message:
```
<|start|>assistant to=self<|message|>act: joke · tone: playful · gist: says the plan sounds fine but teases about lateness<|eom|>
<|start|>assistant to=user<|message|>го / только ты опять опоздаешь 😏<|eot|>
```
- In `training/modal_train.py`: render messages with `{"role": "assistant", "reasoning_content": thought, "content": reply}`
  (the template writes reasoning_content into `to=self`), loss on both the thought and the reply.
- Keep audience + situation header in the user turn as now. Reply task input = detailed summary (pairs_v2).
- At inference: let the model write its own thought (no forced `to=user`), or sample act/tone from the user's
  distribution for that audience × situation (style profile) and prefill the thought for controllable output.

## Style profile (also the app's style card)
Per audience × situation: shares of act and tone, initiative (is_reply), form features (`pipeline/style_stats.py`),
vocabulary (`pipeline/lexicon.py`). Describes *how the user writes*, never personality.

## Eval
Benchmark v4 vs v2 (+cell rerank): chrF, fingerprint, and new: act/tone distribution match per cell
(tag model outputs with the same `--thoughts` prompt, compare with the user's shares).

## Budget
Modal ≈ $16 left: thoughts tagging ≈ $1, v4 training ≈ $1.5, benchmark ≈ $0.5. Fireworks ($100, Glimmer SFT
free until Nov 30) can train v4 if Modal runs low — check it accepts reasoning_content in SFT data.
