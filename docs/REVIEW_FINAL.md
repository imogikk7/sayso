# Pre-submission review, Nov 1

An independent read-only pass over `serving/`, `ios/`, `pipeline/` and the git history, through five lenses: security,
privacy, correctness, iOS, and public-repo hygiene. No code in `serving/` or `ios/` was changed. Line numbers are for
commit `be2ae8e`.

New tests on fakes (no GPU, no network, no private data):

- `tests/test_writer_fakes.py`: 52 tests. `Writer` with gpu="off" and a fake async Muse Spark covers rewrite and
  compose in all four formats, chat revision that adds a preference, feedback and learn cleaning, and `read()`
  validation. A fake HTTP client drives the real `Writer.spark` through bad JSON, prose around the JSON, retries and
  HTTP errors.
- `tests/test_api_auth.py`: 18 tests. It builds the real FastAPI app from `modal_app.api()` without Modal: a fake
  `modal` module (pass-through decorators, an in-memory Dict, a no-op Volume) and a fake `transformers` go into
  `sys.modules` first. It checks auth on every route (13 routes × 5 bad headers), input limits, 413/422/404/409, the
  upload spawn, and that `/latest` keeps only the user's side. It needs `fastapi httpx python-multipart`, which is the
  API image's own stack and not the pipeline's, so it is skipped when they are missing.

Tests marked `@unittest.expectedFailure` pin the bugs below; their IDs are in the decorator comments. They pass while
the bug is there. Once a bug is fixed, its test reports "unexpected success", which fails the run on Python ≥ 3.11.
When that happens, remove the decorator.

```
python3 -m unittest discover -s tests                     # 87 tests, API ones skipped without fastapi
python3 -m venv /tmp/venv && /tmp/venv/bin/pip install fastapi httpx python-multipart pytest
/tmp/venv/bin/python -m pytest -q tests                   # 75 passed, 4 skipped, 8 xfailed
```

## Fix before the freeze (Nov 2), in this order

| # | ID | Effort | Change |
|---|---|---|---|
| 1 | C1 | 1 line | `max_containers=1` on `api` (`serving/modal_app.py:131`). Stops lost updates and deletions that come back |
| 2 | P2 | ~20 lines Swift | Keyboard learning off by default, and pasted text is never learned |
| 3 | S2 | ~15 lines | Check the token in ASGI middleware before any body is read |
| 4 | C2, C3 | ~15 lines | `read_jsonl` skips torn lines and `write_jsonl` writes atomically; harden the Spark output shapes |
| 5 | P1 | text only | Privacy screen and README say that uploaded chats are read by Muse Spark (Meta Model API) during a build |
| 6 | S3 | ~10 lines | Size limits on zip members before extracting or reading them |
| 7 | S1 | ops | Rotate `SAYSO_API_TOKEN` after filming. Give any build that leaves your hands a limited demo token |

---

## 1. Security

### S1 · High · One bearer token in the app binary opens all of the user's data
`ios/scripts/gen_secrets.sh:17`, `ios/Shared/API.swift:353`, `serving/modal_app.py:169-175`

Anyone can pull the token out of the IPA with `strings`. With it they get more than generation:
- `GET /styles/main` returns the last 30 learned keyboard messages, examples of the user's real messages, and the
  profile.
- `GET /latest` returns the last screenshot replies.
- `PATCH`/`DELETE /styles/*`.
- `POST /chat` with feedback adds a permanent rule to every future prompt (see S4).
- `/warmup` wakes the H100, and `/styles` uploads spend Meta credits.

This item was already in `docs/REVIEW.md` as "Rotate `SAYSO_API_TOKEN`" and is still open.

**Fix:**
- For the hackathon, the IPA does not leave your devices; any TestFlight build for judges gets its own token.
- Rotate the token after filming: `modal secret create sayso SAYSO_API_TOKEN=... --force`, then run
  `gen_secrets.sh`.
- Better: a second secret `SAYSO_DEMO_TOKEN` that only allows generation routes:
  ```python
  OWNER_ONLY = {"/styles", "/learn", "/feedback", "/latest"}  # prefixes
  def check(request: Request, authorization: str | None = Header(None)):
      token = (authorization or "").encode()
      if secrets.compare_digest(token, f"Bearer {os.environ['SAYSO_API_TOKEN']}".encode()):
          return
      demo = os.environ.get("SAYSO_DEMO_TOKEN")
      if demo and secrets.compare_digest(token, f"Bearer {demo}".encode()) \
              and not request.url.path.startswith(tuple(OWNER_ONLY)):
          return
      raise HTTPException(401)
  ```
- After the hackathon: per-device tokens (App Attest / Sign in with Apple), as `docs/REVIEW.md` already plans.

### S2 · Medium · The token is checked after FastAPI has parsed the body (the comment says the opposite)
`serving/modal_app.py:174-175`, confirmed by `tests/test_api_auth.py::test_bad_body_is_401_before_parsing` and
`::test_unauthenticated_upload_is_not_parsed`

FastAPI reads and decodes a JSON body, and parses a multipart body (spooling files to disk), before it resolves even
app-wide dependencies. Two consequences:
- An unauthenticated request with broken JSON gets **422, not 401**.
- An unauthenticated `POST /styles` gets fully parsed. The 50 MB check (`:390`) runs only inside the handler, after
  Starlette has already spooled everything.

So anyone who knows the URL can make the API container read arbitrarily large bodies. `/reply` is fine: it reads the
body itself.

**Fix:** check the token as pure ASGI middleware, before the body exists, and cap Content-Length there too. Keep
`Depends(check)` as a second line.
```python
class Guard:
    def __init__(self, app, limit=55 * 1024 * 1024):
        self.app, self.limit = app, limit
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            expected = f"Bearer {os.environ['SAYSO_API_TOKEN']}".encode()
            if not secrets.compare_digest(headers.get(b"authorization", b""), expected):
                return await JSONResponse({"detail": "Unauthorized"}, 401)(scope, receive, send)
            if int(headers.get(b"content-length", b"0") or 0) > self.limit:
                return await JSONResponse({"detail": "too large"}, 413)(scope, receive, send)
        await self.app(scope, receive, send)
web.add_middleware(Guard)
```
Chunked bodies have no Content-Length. Modal's proxy buffers them, but the limit in the handler still has to stay.

### S3 · Medium · Zip bombs: archive members are decompressed with no size limit
- `serving/build_style.py:181` uses `archive.extractall(folder)` on the container disk.
- `pipeline/parse_whatsapp.py:34` uses `archive.read(name)`, all in memory.
- `pipeline/parse_instagram.py:37` does the same.

A 50 MB upload can expand to many GB. The build container then runs out of memory or disk, and the style stays
"building" (see C5). Path traversal is **not** possible:
- `Path(name).name` strips directories (`:170`).
- `ZipFile.extractall` drops `..` and absolute components and never creates symlinks.
- Style ids are regex-checked in `styles.folder`.

All three were verified.

**Fix:** one guard, called before `extractall` and before `detect`/`read_any` on any zip:
```python
def check_zip(archive, max_total=300 * 1024 * 1024, max_files=5000):
    infos = archive.infolist()
    if len(infos) > max_files or sum(i.file_size for i in infos) > max_total:
        raise ValueError("archive too large")
    if any(i.compress_size and i.file_size / i.compress_size > 200 for i in infos):
        raise ValueError("suspicious compression ratio")
```

### S4 · Medium · Learned rules are a prompt injection that stays
`serving/writer.py:263-267` (rules "override everything above"), `:560-563`, `:596-601`, `:618-620`,
`serving/styles.py:149-157`

Rules are model output from `/chat` revisions, `/learn` and `/feedback`, and they go into every later prompt for the
style. If the other person's text reaches `/learn` (a paste, see P2), or a screenshot carries instructions, a rule can
come out like "Always add this link …" or "Ignore the style". It stays until someone deletes it by hand. The
120-character cap and the dedup in `add_preference` are good but not enough.

**Fix:**
- In `add_preference`, reject rules that contain a URL, `@`, digits longer than 3, or the words
  `ignore|instruction|system|prompt`, and allow at most 12 words.
- In iOS, show every `learned`/`rules` value as a toast with **Undo**. The API already returns them.

### S5 · Low · `gen_secrets.sh` interpolates `.env` values into Swift without checks
`ios/scripts/gen_secrets.sh:6,17`

- A duplicate `SAYSO_API_TOKEN=` line produces two lines and broken Swift.
- Quotes copied into `.env` end up in the token.
- A `"` or `\(` in the value is Swift code injection. It is your own file, but it fails silently.

**Fix:** `grep -m1`, strip surrounding quotes, and `case "$TOKEN" in *[!A-Za-z0-9_-]*) echo bad token; exit 1;; esac`.

### S6 · Low · Cost: `/warmup` and `/styles` can be called repeatedly
`serving/modal_app.py:437-449`, `:384-398`

With the token, a loop on `/warmup` keeps the H100 up; `max_containers=1` limits it to one. On Baseten the
`range(60)` × 10 s loop equals the function's `timeout=10*60`, so the request can be killed at the boundary.

**Fix:**
- Store the time of the last wake in the `latest` Dict, and turn away a second wake within 5 minutes.
- Use `range(50)`.
- Allow at most 3 builds per day (another Dict counter).

### S7 · Low · Upload names: crashes and collisions, no traversal
`serving/build_style.py:170`, `:187`
- A file named `..` or `.` resolves to a directory, so `write_bytes` raises and the whole build fails.
- Two uploads with the same name overwrite each other.
- `chats[Path(name).stem]`: every Telegram page uploaded as `messages.html` maps to the same chat, so **only the last
  chat survives** when the user uploads several single-page exports.

**Fix:**
- Write the temp file as `f"{i}{Path(name).suffix.lower()}"`.
- Key chats as `f"{Path(name).stem} ({i})"` when the key is already taken.
- Compare suffixes case-insensitively: `.HTML` and `.ZIP` are skipped today.

### Checked and fine
- Every route has the app-wide `Depends(check)`. The test enumerates all 13 routes, each with no header, a wrong
  token, a missing `Bearer`, a lowercase scheme, or a trailing space.
- `compare_digest` works on bytes, so a non-ASCII header gets 401, not 500.
- Docs and OpenAPI are off.
- vLLM's key (`GLIMMER_KEY`) never ships in the app.
- Control tokens are stripped from every field before it enters a Glimmer prompt.
- Screenshots are capped at 4 MB (header and body), with 422 on bad base64.

---

## 2. Privacy

### P1 · High · Building a style sends other people's raw messages to a third party in batch, against the project's own rules
`serving/build_style.py:206-231` (TAG: "Other person: …" up to 600 characters per turn, about 2,000 turns), `:363-368`
(audience guess from the last 40 messages of **both** sides), `:324-331` (self-check baseline and judge with the other
person's messages), `:136-160` (screenshots and up to 60 screen-recording frames).

CLAUDE.md says other people's messages are "never sent to third-party APIs in raw form for batch processing" and
that "situation tagging … runs on our own hosted base Glimmer, not on third-party APIs". The build does exactly this
through the Meta Model API. With GPU credits running out, this may be the right trade-off, but it has to be stated,
not hidden: a judge who reads the privacy screen and then the code will see the gap.

**Fix:**
- For submission: one sentence on the privacy screen, in the README and in the video. For example: "While a style is
  built, the chats you upload are read by Muse Spark (Meta Model API) to label your replies. SaySo stores only your own
  messages." Also update CLAUDE.md's rule to match reality.
- In code, a few lines: send `parse_telegram.clean()` of the context (no links, phones, emails or card numbers) and
  cut it to 300 characters at `:211`. For the audience guess (`:365`), send only the user's own lines plus a count of
  the other side's lines.

### P2 · High · The keyboard learns by default and can learn other people's text
`ios/Shared/Settings.swift:54` (`learnsFromTyping ?? true`), `ios/SaySoKeyboard/PanelModel.swift:100-110`,
`:123-131`

- **Default on.** CLAUDE.md describes an *optional* training mode, and App Review 4.4.1 / 5.1.1 expect collection
  from keyboard input to be opt-in.
- **Pastes count as the user's own.** If the user pastes a friend's message (a quote, a forward, an address) and sends
  it, `fieldChanged` sees "field had text → field is empty" and queues it. It then goes into `learned.jsonl` and into
  Spark prompts as one of "their real messages".
- **Mail composers.** `lastText` includes `documentContextAfterInput`. In Mail and Gmail composers that is the quoted
  original email from someone else.

**Fix:**
```swift
var learnsFromTyping: Bool? = nil
var learns: Bool { get { learnsFromTyping ?? false } ... }        // opt-in, asked in onboarding

private var foreign = false   // the field got text that our keys didn't type (paste, autofill, quote)
func fieldChanged() {
    let now = ...
    if now.count > lastText.count + 1 { foreign = true }           // grew by more than one char from outside
    if now.isEmpty && !sent.isEmpty && !userDeleted && !foreign { remember(sent) }
    if now.isEmpty { userDeleted = false; foreign = false }
    ...
}
```
Learn only `documentContextBeforeInput`, never the text after the cursor.

### P3 · Medium · Other people's names are stored and served
`serving/build_style.py:370` (`participants`, up to 12 sender display names, in `meta.json`), `modal_app.py:338-341`
(`participants`, `chats` returned by `GET /styles`), `writer.py:235`

- `participants` is cleared at "reading", but it stays forever when the build fails or times out at `needs_me`.
- `chats` keys are chat titles, which in one-to-one chats are the other person's name. They are kept for good to map
  a screenshot's title to an audience.

**Fix:**
- Clear `participants` in every terminal `stage(...)`, the failed ones included.
- Store the mapping as `sha256(title.casefold().strip())[:16] → audience`, and look it up with the same hash at
  `writer.py:530`. Keep display names only on the device.

### P4 · Medium · `/feedback` stores links and phone numbers that `/learn` removes
`serving/writer.py:609-613`, pinned by `test_writer_fakes.py::test_feedback_is_scrubbed_like_learn`

An answer the user liked in Chat's **reply** mode often repeats facts from the other person's message (an address,
a phone number, a link). It goes into `feedback.jsonl` and into later prompts.

**Fix:** `text = scrub(clean(edited or answer))`, with `scrub` being the same `parse_telegram.clean` that `learn()`
uses. Skip the item if `PASTED_CODE` matches.

### P5 · Medium · "Delete" is incomplete: learned data can't be fully deleted
`serving/modal_app.py:350` (only the last 30 of up to 3,000 learned messages are listed, so older ones can't be
deleted from the app), `serving/styles.py:171-178` (`feedback.jsonl` has no delete at all), `styles.py:118-120` (the
main style can't be deleted, which is right, but its learned, feedback and preferences files can't be wiped either)

This contradicts the "delete everything" privacy screen in CLAUDE.md. C1 makes it worse: a deletion handled by one
container can be overwritten by the other.

**Fix:** `DELETE /styles/{id}/learning` → remove `learned.jsonl`, `feedback.jsonl` and `preferences.json` (main style
included), then `data.commit()`. Paginate `recent` (`?offset=`).

### P6 · Low · `/latest` is global and kept indefinitely
`serving/modal_app.py:317-318`, `:433-435`

Correctly, it holds only the user's side and no summary (verified by `test_api_auth.py::
test_reply_from_messages_stores_only_the_users_side`). But the replies can repeat facts from the other person's
messages, they stay in the Modal Dict until overwritten, and every style and device shares them.

**Fix:** on `GET /latest`, return `{}` and delete the entry when `at` is older than 15 minutes.

### P7 · Low · Logs
- **vLLM prompts.** They contain the summary of the other person's messages. Confirm vLLM 0.28 has request logging
  off by default, or pin it explicitly with `--disable-log-requests` / no `--enable-log-requests` (`modal_app.py:58`).
  Check with `modal app logs sayso` after one `/reply`. This was already an open item in `docs/REVIEW.md`.
- **Build failures.** `build_style.py:409-411` re-raises, so Modal logs the traceback. Parser exception messages
  (`strptime`, `JSONDecodeError`) can quote input. Log `type(error).__name__` only and do not re-raise.

### P8 · Info · Where raw uploads live
`POST /styles` hands the raw exports to `build_style.spawn` as function arguments (`modal_app.py:397`). They sit in
Modal's input storage until the call finishes, which can be up to 30 minutes in `needs_me`. That is fine, but the
privacy screen should say it: "kept in memory on our server only while the style is built".

### Checked and fine
- `turns.jsonl`, `profile.json` and `pairs/` contain only the user's turns; `context` is popped before writing.
  `tests/test_styles.py` checks this, and the self-check `samples` are both the user's side.
- `/reply` stores no summary. iOS `ReplyStore` drops the summary.
- The keyboard skips email, URL, number, phone, web-search and any `textContentType` field (one-time codes,
  addresses), as well as secure fields and search return keys (`PanelModel.swift:112-121`).
- The server scrubs `/learn` (links, emails, phones, cards) and drops pasted code and texts over 1,000 characters
  (tests in `test_writer_fakes.py::Learning`).

---

## 3. Correctness

### C1 · High · Two API containers and the build container overwrite each other's files on the volume
`serving/modal_app.py:131` (`max_containers=2`), `writer.py:317-320` (reloads only when a style is missing),
`modal_app.py:362-371` (`style_or_404` reloads only when missing), `styles.py:94-98`, `:171-192`
(read-modify-write of whole files)

Modal Volumes are last-writer-wins per file, and a container sees others' commits only after `reload()`. The API
containers never reload for a style they already know. Three ways this goes wrong:

- **Lost updates.** Container A appends to `learned.jsonl` and commits. Container B still has the old file, appends
  its own row, and commits. A's rows are gone. The same happens to `preferences.json` and `feedback.jsonl`.
- **A deletion that comes back.** The user deletes a learned message or a rule in A. B later writes its stale copy
  with the item still in it. This is a privacy bug too (P5).
- **Stale reads.** Rules learned in A aren't used by B until B restarts.

The same pattern affects the build: `stage()` (`build_style.py:348-350`) writes the whole `meta.json` from the build
container's view. A rename (`PATCH name`) made during a build is overwritten at the next stage.

**Fix:**
- For the hackathon: `max_containers=1` on `api`. There is one user, and 32 concurrent inputs are plenty.
- Also call `await asyncio.to_thread(data.reload)` at the top of `patch_style`, `/learn`, `/feedback`, and `/chat`
  with feedback.
- In the build, re-read meta after `data.reload()` inside `stage()`, so fields the API wrote survive.
- Later: append-only per-record files (`learned/<id>.json`), or a `modal.Dict` for learned rows.

### C2 · Medium · One torn line in a `.jsonl` file makes the style unusable until someone fixes it by hand
`serving/styles.py:65-70` (`json.loads` per line, no try), `:73-78` (writes in place, not atomically). Pinned by
`test_writer_fakes.py::test_a_torn_jsonl_line_does_not_break_the_style`.

If a container is killed mid-write, or two writers race (C1), `learned.jsonl` or `feedback.jsonl` is left with half
a line. After that, every `Context(style_id)` raises `JSONDecodeError`: rewrite, compose, reply and chat all return
500 for that style.

**Fix:**
```python
def read_jsonl(path):
    rows = []
    try:
        with Path(path).open(encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return rows
```
Have `write_jsonl` write to `.tmp` and then `replace()`, as `write_json` already does.

### C3 · Medium · Unexpected Spark output shapes cause 500s or garbage
Each case is pinned by a test in `test_writer_fakes.py`:

| Case | Where | Result |
|---|---|---|
| `"variants": "давай в 8"` (a string, not a list) | `writer.py:454` | candidates `['го в 8', 'д', 'а', 'в']`: single letters on the ✨ strip |
| `"options": 3` | `writer.py:532` | `TypeError` → 500 on `/reply` and `/chat` reply |
| `"text": "<\|eot\|>"` (only template tokens) | `writer.py:455-456` | `candidates[0]` raises `IndexError` → 500 |

**Fix:**
```python
variants = label.get("variants") if isinstance(label.get("variants"), list) else []
written = [label["text"]] + [v for v in variants if isinstance(v, str)][:VARIANT_COUNT]
candidates = ...
if not candidates:
    raise Unavailable(502, "Muse Spark gave an empty answer, try again")
...
raw = label.get("options")
for option in raw if isinstance(raw, list) else []:
```

### C4 · Medium · With the GPU off, "no drafts" tells the user the model is waking up
`serving/writer.py:489-491` → `ensure_warm` → `Unavailable(503, "the user's model is offline")` (`:337-338`) → iOS
maps every 503 to "Your model is waking up (about 2 minutes)" (`ios/Shared/API.swift:358`).

When Spark's read for the **main** style returns no valid options (C3 or a weak answer), `/reply` with GPU off
returns 503. The app then asks the user to wait for a GPU that will never wake. The iOS restyle (`API.swift:221`)
sends `options: response.options ?? []` and hits the same path.

**Fix:** `if not options and self.gpu == "off": raise Unavailable(502, "Couldn't write replies, try again")`, or retry
`read()` once. In iOS, show the server's `detail` for 503 instead of a fixed string.

### C5 · Medium · Build lifecycle: a failed LoRA fails a ready style, and a killed build stays "building" forever
- `build_style.py:404-408`: if `train()` raises (no H100 credits, or `sayso-train` is missing), the outer `except`
  marks the style `failed`. It already has a profile, pairs and scores and was usable as a Spark style.
- `modal_app.py:92` (`timeout=3h`): `run.remote` training (`:118`), on top of up to 30 minutes of `needs_me` and
  tagging, can go past 3 hours. A timeout or preemption kills the process without reaching `except`, so `status`
  stays `building` or `training`. The app polls forever, because `Style.isBuilding` is true.

**Fix:**
- Wrap `train()` in `try/except Exception: stage("ready", 1.0, lora="failed")`.
- In `style_view`, when `status == "building"` or `stage == "training"` and `updated` is more than 3.5 hours old,
  report `failed` with "The build stopped. Try again".

### C6 · Low · `learn()` compares the unscrubbed suggestion with the scrubbed text
`serving/writer.py:589-592`, pinned by `test_no_rule_call_when_only_a_link_was_scrubbed`

Two effects:
- If the suggestion and the sent text are identical but contain a link, a Spark rule call still happens, and Spark
  sees the link that was removed from the text.
- `kind` is `"edited"` even when `suggested == text`. iOS filters that case today, but the API doesn't.

**Fix:** `suggested = scrub(clean(...)) or None`; set `kind = "edited" if suggested and suggested != text else "typed"`.

### C7 · Medium (latency) · Every `/learn` rebuilds the main style's whole context
`serving/styles.py:125-130` (`version` includes `learned.jsonl`, `feedback.jsonl` and `preferences.json`),
`writer.py:222-226`

After each keyboard flush (every 3 messages) or feedback, the next request re-reads `pairs_v4/train.jsonl` and
rebuilds `StyleStats.from_pairs("pairs_v2")` with the lexicon, which means thousands of rows. That request comes from
the keyboard's ✨ and has a latency budget under 3 seconds.

**Fix:** split `Context` into a heavy part (turns, stats, profile), cached by the mtime of `meta.json` and
`profile.json`, and a light part (preferences, feedback, learned) re-read on the small version.

### C8 · Low · Smaller items
- `read_exports` (`build_style.py:186-187`): `read_any` sits outside the `try`. One non-UTF-8 WhatsApp export
  (`UnicodeDecodeError`), a bad zip or bad JSON fails the whole build instead of skipping that file. Catch
  `(ValueError, zipfile.BadZipFile, KeyError)` per file.
- `read_images` (`build_style.py:140`): HEIC and WebP are sent as `image/jpeg`. Use
  `mimetypes.guess_type(name)[0] or "image/jpeg"`.
- Blocking calls in `async` routes: `data.reload()` and `data.commit()` (`modal_app.py:366,376,381,396,428`, and
  `styles.on_write` from `writer.learn/feedback/chat`) block the event loop for all 32 concurrent requests. Use
  `await asyncio.to_thread(...)`.
- `/reply` builds `writer.context(style)` (`:293`) before checking that the body has an image, messages or a summary.
  An empty request costs a full context build.
- The `/reply` summary path (`:303-307`) passes the client's `summary` uncapped. It is still cleaned in the prompt.
  For symmetry with `read()`, cap it to `SUMMARY_WORDS`.
- `shape(..., "series")` keeps at most 4 lines and silently drops the rest (`writer.py:179-181`). Join any extra lines
  into the last part instead, so no content is lost.

### Checked and fine (with tests)
- All four formats in rewrite and compose: message is one line; series has 2–4 parts; official is capitalized with
  one part; email has `\n\n` paragraphs in one part. `shape` is idempotent, which matters because `styled()` shapes
  twice.
- `clip` keeps the line structure, and answers are clipped to `FORMAT_WORDS × 2`.
- The formal formats get no casual examples.
- Chat revision sends all feedback so far plus the last answer. A general rule is cleaned and deduplicated, capped at
  `MAX_PREFERENCES`, committed, and seen by the next request: `version()` changes, so the context is rebuilt.
- `learn` keeps the message when Spark is down, learns at most 2 rules per batch, and the learned text becomes an
  example at once.
- `read()`: the summary has template tokens stripped and is capped at 45 words; unknown situations become `other`;
  the chat title maps to the confirmed audience, and the user's choice beats both; options are deduplicated by act and
  capped at 3; series drafts keep their lines.
- The real `Writer.spark`: bad JSON is retried once and then returns 502; JSON wrapped in prose is parsed; a 429
  returns 502; a JSON array returns 502; an empty `rule` is a valid answer.

---

## 4. iOS (keyboard extension)

### I1 · Medium · Rewrite of a long draft leaves part of it behind
`ios/SaySoKeyboard/PanelModel.swift:318` (deletes `documentContextBeforeInput.count` characters), `:94-95` (the draft
is `documentContextBeforeInput`)

iOS gives the keyboard only part of a long field, often the current paragraph or a few hundred characters. For a
multi-paragraph draft, ✨ rewrites the visible tail only. `insert()` then deletes that tail and inserts the rewrite,
so the earlier text stays in front of it, duplicated in meaning.

**Fix:** delete in a loop, `while let before = proxy.documentContextBeforeInput, !before.isEmpty, n < 50 { ... }`.
When the context is cut at a non-boundary, warn: "Only the last part was rewritten".

### I2 · Medium (data quality) · Learned messages are labeled with whichever audience chip was last picked
`PanelModel.swift:128`

The chip persists across apps and chats: `UserDefaults` at `:28-29`. A message to family, typed while the chip still
says Friends, is learned as Friends and then used as a Friends example.

**Fix:** send the audience only if the user touched the chip in this field session, or ✨ suggested it for this text.
Otherwise send `"unknown"`. The server already drops audiences it doesn't know (`writer.py:587`). Later: let Spark
label it from the text.

### I3 · Low · Learned items can be lost when the keyboard closes
`PanelModel.swift:134-146`

`flush()` clears the queue before the request. It is called from `viewWillDisappear`, and an extension that is
suspended or killed right then loses the items.

**Fix:** keep the items until the request succeeds. Send a snapshot, then on success
`queue.removeFirst(min(sent.count, queue.count))`. Deduplicate on the server by a client-side `id` per item.

### I4 · Low · The sent-message heuristic has false positives and negatives
`PanelModel.swift:100-110`

**False positives** ("text → empty" without a send):
- Select All → Cut.
- `textDidChange` when the user moves to another, empty field.
- Cancelling Telegram's "edit message", which clears a pre-filled field, so an old message is learned again.

These are mostly the user's own text, so the risk is noise, not privacy. P2 covers the paste case.

**False negatives:** `userDeleted` is set by ⌫ and reset only by `type()` and an empty field. After one ⌫, a message
finished with `space()`, `newline()` or `typeAlternate()` is never learned.

**Fix:**
- Reset `userDeleted` in `afterTyping()` whenever text was added.
- Only learn when the field empties within about 2 seconds of the user's last keystroke on our keys (a send follows
  typing), not after a long idle period.
- Deduplicate on the server against the last 20 learned texts.

### I5 · Low · App Group and Full Access
- Without Full Access the App Group can't be read, so the keyboard uses defaults and style `main`. Correct, since
  generation needs network, which also needs Full Access.
- The learn queue is in the extension's own `UserDefaults.standard` (`:58-61`). "Delete everything" in the app can't
  clear pending items. Move it to `SharedStore.defaults`: learning already requires Full Access, so the App Group is
  readable.

### Memory and main thread: fine
- The extension holds a SwiftUI tree, a few strings and a queue of at most 200 items. No images are decoded in the
  keyboard, since screenshots go through the app's intent. That is far under the roughly 48–70 MB extension limit.
- `PanelModel` is `@MainActor`, and network awaits suspend without blocking. `insert()` calls `deleteBackward()` once
  per character on the main thread, which is fine for chat-length text but slow for multi-kilobyte fields (see I1's
  cap).
- `perform` and Full Access: generation is refused cleanly without Full Access, with a message pointing to Settings.
  Haptics only fire with Full Access, as the system requires.

---

## 5. Public-repo hygiene

Scanned: 36 commits on all branches, every added path, every added line of history (`git log --all -p`), and commit
messages.

- **No keys.** Searched for `sk-`/`pk-` keys, long base64 or hex strings, `Bearer …`, `api_key=`, emails, and
  Kazakhstan phone numbers. The only hits are Xcode object IDs and benchmark floats.
- **No `.env`, no `data/`, no adapters** in any commit. `.gitignore` covers `.env*` (except `.env.example`, which is
  empty), `data/`, exports, `*.safetensors`, `ios/Shared/Generated/`, and `serving/baseten/data/`.
- **`eval/results/*.json`** contain numbers only: no string over 25 characters in any file.
- **Fixtures.** `tests/fixtures/whatsapp_fake.txt` and `tests/fixtures/chat.png` look synthetic (the screenshot
  shows a contact named "Дима"). `docs/PLAN_v4_thinking.md:17` has one example message ("го / только ты опять
  опоздаешь 😏"). **Confirm that all three are invented**; if any is real, replace it. History would need a rewrite,
  so it is cheaper to accept a made-up example.
- **Metadata.** The commit author is `leo <leo@MacBook-Pro-leo.local>`: a first name and a hostname, no email.
  `DEVELOPMENT_TEAM = WL5B45CYV9` in the pbxproj is a public Apple Team ID. The bundle ids contain the GitHub
  handle. All acceptable for a public hackathon repo.
- **Guard for the last days.** Before each commit, `git diff --cached --name-only | grep -E '(^data/|\.env$|\.jsonl$|ChatExport_)'`
  must print nothing. `tests/test_privacy.py` runs against `data/` and is skipped in a clean clone.

---

## Severity index

| ID | Severity | Lens | One line |
|---|---|---|---|
| S1 | High | Security | One token in the binary gives full read and write access to the user's data |
| P1 | High | Privacy | The build sends other people's raw messages to the Meta API in batch, against CLAUDE.md's rule |
| P2 | High | Privacy | Keyboard learning is on by default; pasted or quoted text from others is learned as the user's |
| C1 | High | Correctness | 2 API containers + build: lost updates, deletions that come back, stale rules |
| S2 | Medium | Security | Body parsed before the token is checked (422 before 401; multipart spooled unauthenticated) |
| S3 | Medium | Security | No size limits on zip members: memory or disk exhaustion |
| S4 | Medium | Security | Learned rules stay in every prompt and "override everything" |
| P3 | Medium | Privacy | Participant names and chat titles stored in `meta.json` and served |
| P4 | Medium | Privacy | `/feedback` isn't scrubbed like `/learn` |
| P5 | Medium | Privacy | Learned data can't be fully deleted (30 of 3,000 visible, no feedback delete) |
| C2 | Medium | Correctness | A torn `.jsonl` line → every request for the style returns 500 |
| C3 | Medium | Correctness | Spark output shapes: letters as candidates, 500s |
| C4 | Medium | Correctness | GPU off + no drafts → "model is waking up" that never ends |
| C5 | Medium | Correctness | A failed LoRA fails a ready style; a killed build stays "building" |
| C7 | Medium | Correctness | Every `/learn` makes the main context rebuild (latency on ✨) |
| I1 | Medium | iOS | Rewrite of a long draft leaves the beginning behind |
| I2 | Medium | iOS | Learned messages labeled with a stale audience chip |
| S5–S7 | Low | Security | `gen_secrets.sh` checks, `/warmup` cost, upload name collisions |
| P6–P8 | Low/Info | Privacy | `/latest` TTL, logs, raw uploads held as Modal function input |
| C6, C8 | Low | Correctness | Scrub before comparing in `learn`, per-file parse errors, MIME types, blocking calls |
| I3–I5 | Low | iOS | Flush loss, sent-detection edge cases, learn queue outside the App Group |
