# Docs pass, Nov 2 (doc-updater agent)

Documentation only: every claim was checked against `serving/*.py`, `ios/`, `eval/*.py` and `eval/results/*.json`
(not `data/`, not `.env`). No code was changed. Tree as of commit `d9cb2aa` plus uncommitted work from other sessions.

## Files changed

| File | What changed |
|---|---|
| `CLAUDE.md` | Rewritten around the code as it is now: current state (`SAYSO_GPU=off`), model roles and fallback order (`Writer.spark`), product surfaces (own-letter keyboard + ✨ + panel, Chat's five modes, 🎙, 👎 reason chips, Add menu + guides, Formal writing, Learned from you, caps and learning toggles off by default), formal voice rules and `[Name]` masking, learning rules, architecture and routes, env flags and secrets, real situation list, tagging split (base Glimmer offline for the main style; Muse Spark 1.3 for app-built styles and live reading), evaluation files, blind test v2, actual repo layout, how to run. Removed the old panel-only keyboard, "training mode" letter keys, base-Glimmer-only tagging, Fireworks plan A/B, the day plan and the stale target layout. Hackathon rules, demo language and privacy rules kept (privacy extended with formal-writing and keyboard rules). |
| `README.md` | Learning is opt-in and never learns pasted text (intro, keyboard row, Learning from use); 👎 quick reasons; keyboard settings incl. caps off by default; Spark 1.3 drafts Back Tap replies with the GPU off; writer keeps the user's habits at their own rate; `[Name]` masking and signature cut; the author's style holds 8 sent emails and 11 handwritten essay pages; **numbers**: Spark Open chrF 47.5 → 50.4, few-shot fingerprint 1.02 → 1.01, v4 table's reply-length row (not in any JSON) replaced by mean length from `bench_v4.json`; uncommitted Nov 1 numbers (embeddings, best-of-5, earlier run) no longer quoted as results; blind test v2 protocol (results TODO); new **API reference** table for all 16 routes; how to run style_gain and the blind test; repo map adds `blind_test.py` and all test files. |
| `docs/SUBMISSION.md` | Same number fixes (1.01, 50.4), opt-in learning and pasted text, 👎 reasons, `[Name]`/signatures, formal-voice counts, blind test v2 description. |
| `docs/deck/sayso.md` | chrF 50.4; slide 7 length and form-distance cards now from `bench_v4.json` (26 vs 34 chars, 0.044 vs 0.075) instead of `PLAN_v4_thinking.md` reply-only numbers; blind test v2 line; privacy slide (opt-in, pasted text, `[Name]`); cost "$3–3.5" to match README. |
| `docs/deck/README.md` | Number sources updated; note that `sayso.pdf` must be rebuilt. |
| `docs/VIDEO_SCRIPT.md` | Beat 6 shows the 👎 reason chips; learning toggle is opt-in and never learns pasted text; blind-test line uses v2 metrics; beat 7 checklist adds chrF 50.4. |
| `docs/DESIGN_BRIEF.md` | Chat switcher has five modes; reason chips marked done; Keyboard tab gets Learning and Typing (caps) toggles; new section "Экраны, добавленные после брифа": Email/Essay modes, 🎙, 👎 chips, Add menu + source guides, Formal writing import and card section, Learned from you. |

## Needed docstring / comment changes (code, not edited)

1. `serving/modal_app.py` module docstring: `api` lists only `/rewrite /compose /reply`; secrets omit `sayso-extra`
   (`BASETEN_API_KEY`) and optional `sayso-baseten`.
2. `serving/modal_app.py` `api()` docstring: `/chat` modes miss `email | essay` and the `instruction, question, words,
   reply_to` fields and the extra response fields (`subject`; `outline, questions, words, cliches`); `/learn` and
   `POST /styles/{id}/documents` are missing; `PATCH` misses `remove_learned`, `clear_documents`; reply items miss
   `styled`.
3. `serving/build_style.py` docstring lists `training` before `checking`; the code runs `checking`, then `training`.
4. `serving/writer.py` module docstring: rewrite/compose are described as "the style's LoRA", but with the GPU off
   Muse Spark Open writes them; formats list omits `essay`; no mention of Muse Spark Open as the writer or of
   `/transcribe`.
5. `eval/style_gain.py` docstring names only `style_gain.json`; `--writer open` writes `style_gain_open.json`. The
   comment in `writer.styled` says best-of-5 gave "chrF 51 → 42" while the `style_gain.py` docstring says 41.5.
6. `.env.example` (config): lacks `SAYSO_API_URL` and `SAYSO_GLIMMER_URL` (read by `gen_secrets.sh`, `smoke_api.py`,
   `blind_test.py`) and still presents Fireworks as the fine-tuning path.

## Left as is / open

- `docs/deck/sayso.pdf` is stale until `docs/deck/build.sh` is run.
- `docs/video/captions.srt` was out of scope; the beat 6 voiceover wording was kept so the captions still match.
- `docs/PLAN_*.md`, `docs/REVIEW*.md` and `docs/reviews/architecture.md` are dated records and were not edited.
- `docs/PLAN_v4_thinking.md` keeps reply-only numbers (24 vs 38 chars, fingerprint 0.07 vs 0.12) that are not in any
  committed JSON; README and deck no longer cite them. The 48% tagger ceiling and 36.8% guessing baseline are also
  only in that plan, and are cited from it.
- "8 sent emails and 11 handwritten essay pages" comes from the coordinator; it can't be checked without reading
  `data/`.
