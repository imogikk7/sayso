# SaySo pitch deck

Marp slides for the video intro, the submission page and judge Q&A.

- `sayso.md` — the slides (Marp markdown)
- `theme/sayso.css` — the theme; **recolor by editing the variables in `:root`** at the top
- `sayso.pdf` — exported deck
- `img/` — put screenshots here

## Screenshots
The repo has no app screenshots yet, so the deck uses none (the title slide shows the app icon from
`ios/SaySoApp/Assets.xcassets`). To add real ones later, drop them in `img/` and reference them from `sayso.md`, e.g.
`![h:400](img/keyboard.png)`. Never put a mock-up in place of a screenshot.

## Rebuild the PDF
```bash
docs/deck/build.sh
```
Needs Node (`npx` fetches marp-cli). If Chrome isn't found, set `CHROME_PATH` to a Chrome/Chromium binary.
For a live preview run `npx @marp-team/marp-cli@4 -s docs/deck --config-file docs/deck/.marprc.yml --theme-set docs/deck/theme/sayso.css --html`.

## Numbers
Every number comes from the repo: `eval/results/style_gain.json` and `style_gain_open.json` (slide 6, "Results · the
live path"), `eval/results/style_gain_lora.json` (slide 7, the LoRA vs Muse Spark Open), `eval/results/bench_v4.json` (slides 2,
7; slide 7's intent ceiling and guessing baseline come from `docs/PLAN_v4_thinking.md`), `eval/results/blind_test.json` (slide 8, "Results · blind test"). Cost and price on the
scaling slide are estimates.
`sayso.pdf` must be rebuilt after any change to `sayso.md`.
