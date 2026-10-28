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

## Result (2026-10-28, `eval/results/bench_v4.json`)
v4 trained 2 epochs on pairs_v4 (15.5 min H100). Benchmark on 499 test pairs, 5 candidates each, act/tone of every
reply re-tagged by base Glimmer with one prompt (the tagger agrees with its own earlier labels only 48% of the time,
so ~48% is the ceiling for act match; always guessing the cell's most common act gives 36.8%).
- Act match on replies: v2 41%, v4 38%, v4+best 44% (closest to the ceiling). Act mix per audience (TV↓): v4+cell 0.14 vs v2 0.19.
- Tone mix: v4p (act + tone drawn from the style profile) halves the gap, tone TV 0.06 vs 0.11 for v2.
- Form: v4p reply fingerprint 0.07 vs v2 0.12; reply length 24 chars vs v2 38 (real 28). chrF on replies a bit lower (6.4 vs 7.7).
- Rewrite chrF slightly up (56.6 vs 55.3).
Takeaway: the thought does not make the model read the user's mind better than v2 (both near the tagger's noise),
but it makes the mood mix and length match the user, and the act becomes a control: prefill `act: agree` /
`act: refuse` / `act: joke` to get three options with different intents in the user's voice (A5).
