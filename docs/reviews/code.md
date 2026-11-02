# Code review: Oct 31 – Nov 2 changes

Reviewer: `code-reviewer` agent (everything-claude-code), checklist from `.claude/agents/code-reviewer.md` and
`.claude/skills/coding-standards/SKILL.md`, adapted to Python and Swift. Read-only review (feature freeze): no code was
changed.

Scope: `git log --since=2026-10-31`. Files: serving/writer.py, documents.py, styles.py, build_style.py, modal_app.py;
ios/SaySoApp (ChatView, StylesView, AddStyleView, FormalImportView, StyleCardView, SetupView, VoiceRecorder,
SourceGuides); ios/SaySoKeyboard (PanelModel, PanelView, LetterKeys, ResultStack, Layouts); ios/Shared; eval/blind_test.py,
eval/style_gain.py. SetupView, Layouts and ResultStack did not change in this window. I read them and found nothing new
in them.

Baseline: the committed suite passes (`pytest -q tests --ignore=tests/test_cov_writer.py`: 147 passed, 6 xfailed). An
untracked `tests/test_cov_writer.py` showed up while I was reviewing (another agent is writing it). It failed on the
first run and passed on the second.

How I checked: I read every file in scope. I ran the edge cases marked "reproduced" against the real functions with
fakes, so no network calls were made. The rest comes from reading the code, and the reasoning is given each time.

Earlier findings in `docs/REVIEW_FINAL.md` (S1–S7, P1–P8, C1–C8, I1–I5) are not repeated here unless the new code
changed them.

## Verdict

**Block until M1–M6 are fixed.** Each one is a small fix (1–15 lines). Most are in the Email/Essay and formal-voice
features that the video and deck show, so a judge could see them break.

| Rank | Count |
|---|---|
| Must-fix before submission | 6 |
| Should-fix | 18 |
| Nice-to-have | 14 |

---

## Must-fix before submission

### M1 · High · An email loses its subject whenever the cliché check rewrites it, and a revised email always loses it
`serving/writer.py:745-751` (also `:709-715`)

`email()` overwrites `label` with the result of the `ESSAY_FIX` call, and that result only has `{"text"}`. The
`label.get("subject")` on line 750 then reads the second response, so `subject` is `None`. The "Copy subject" button
disappears exactly when the first draft sounded like AI. **Reproduced** with a fake Spark: the subject came back as
`None`. The revise path (`chat()` with feedback) never asks for or returns a subject either, so after any fix (a 👎 chip
in Email mode) the subject is gone. The fixed text also skips `clip()`.

```diff
-        text, parts = shape(clip(clean(label["text"]), FORMAT_WORDS["email"] * 2), "email")
+        subject = clean(str(label.get("subject") or "")) or None
+        text, parts = shape(clip(clean(label["text"]), FORMAT_WORDS["email"] * 2), "email")
         if CLICHES.search(text):
-            label = await self.spark(self.formal_system(ctx, notes), ESSAY_FIX.format(
+            fixed = await self.spark(self.formal_system(ctx, notes), ESSAY_FIX.format(
                 problems=..., text=text), "text", timeout=60)
-            text, parts = shape(clean(label["text"]), "email")
-        return {"text": text, "parts": parts, "subject": clean(str(label.get("subject") or "")) or None,
+            text, parts = shape(clip(clean(fixed["text"]), FORMAT_WORDS["email"] * 2), "email")
+        return {"text": text, "parts": parts, "subject": subject,
```
For the revise path, the smallest fix is on the client. In `ChatView.run()`, when `mode == .email` and the new answer has
no subject, carry over the previous answer's subject. A server-side alternative is to send the subject in `history`.

### M2 · High · `own_email()` cuts at the first header line, so Apple Mail PDFs give nothing and pasting several emails keeps only the first
`serving/documents.py:45-62`; the guides that send users down this path are in `ios/SaySoApp/SourceGuides.swift:43-55`

`QUOTE` matches `From:`, `От:` and `Sent from my` at the start of any line, and `own_email` keeps only
`text[:match.start()]`. That causes two problems:
* **Apple Mail → Print → PDF** (the "Apple Mail as PDF" guide) starts with a `From: … / Subject: … / To: …` header, so
  the whole email becomes `""`. **Reproduced**: `own_email(apple_mail_pdf_text) == ''`. The user then sees "Learned from
  0 of your emails" with no error.
* The **"Copy and paste"** email guide says "Add a blank line between emails". The whole paste is one upload, so the
  first `Sent from my iPhone` or `On … wrote:` drops every email after it. **Reproduced**: two pasted emails → only the
  first one is kept.

Fix: skip a leading header block before looking for a quote, and split a paste into separate emails.
```diff
+HEADER = re.compile(r"^\s*(From|To|Cc|Subject|Date|Sent|От|Кому|Тема|Дата)\s*:.*$", re.I)
 def own_email(text):
-    match = QUOTE.search(text)
+    lines = text.replace("\r", "").split("\n")
+    while lines and (not lines[0].strip() or HEADER.match(lines[0])):   # the mail app's own header block
+        lines.pop(0)
+    text = "\n".join(lines)
+    match = QUOTE.search(text)
     return text[:match.start()] if match else text
```
In `modal_app.add_documents`, for `kind == "email"` and pasted text, split on `Sent from my…` / sign-off + blank line, or
change the guide to "paste one email at a time". The second option needs no server change.

### M3 · High (privacy, visible in the UI) · Email "openings" keep the recipient's name, and "closings" are usually the user's own name
`serving/documents.py:130-136`, `serving/styles.py:234-235`; shown in `FormalImportView.swift:147-149` and `StyleCardView.swift` ("Opens with: …")

`edges()` takes the raw first and last short lines and never scrubs them. **Reproduced** on a normal email: the result is
`('Hi Tom,', 'Leo')`. That has two effects:
1. Other people's names ("Hi Tom", "Dear Professor Lee") are stored in `formal.json` and sent to Spark in every email
   prompt (`opens emails with: Hi Tom / Dear Professor Lee`). They also appear on screen in the import result and in
   the style card, which would show up in a recorded demo. Commit 8ce9436 says names become `[Name]`, but that only
   happens in the photo-reading prompt (`READ_SYSTEM`), not for files, pastes or .mbox.
2. The "sign-off" is the signature name, not "Best regards". So the profile says "signs off with: Leo" while
   `FORMATS["email"]` asks for a sign-off "without a name".

```diff
 def edges(text):
     lines = [...]
+    if len(lines) > 1 and re.fullmatch(r"[A-ZА-ЯЁ][\w.-]*( [A-ZА-ЯЁ][\w.-]*)?", lines[-1]):
+        lines = lines[:-1]                       # a bare signature name, not the sign-off
     short = lambda line: 0 < len(line.split()) <= 6
-    opening = lines[0] if lines and short(lines[0]) else None
+    opening = greeting_only(lines[0]) if lines and short(lines[0]) else None
 ...
+def greeting_only(line):
+    """'Dear Professor Lee,' → 'Dear [Name],'  ·  'Здравствуйте, Анна Сергеевна!' → 'Здравствуйте, [Name]!'"""
+    word, sep, rest = line.partition(" ")
+    return word + (" [Name]" + (rest[-1] if rest[-1:] in ",!:" else "")) if rest.strip() else line
```
Existing `formal.json` files need `ends` recomputed, or cleared and uploaded again.

### M4 · High · Liking or editing an email or essay turns it into a casual "friends" example, and rules learned from it apply to every chat
`serving/writer.py:309-312` (`Context.approved`), `:829-844` (`feedback`), `:710-713` (revise rule); `ios/SaySoApp/ChatView.swift:161, 329`

In Email/Essay mode the audience picker is hidden, but `like()` and `saveEdit()` still send `audience` (default
`friends`). `writer.feedback` stores the text with `format: "email"`. `Context.__init__` ignores `format`, and unlike every
other example source it has no length limit. `sample()` and `examples()` put `approved[-3:]` **first** in every casual
prompt for that audience. One 👍 on an email therefore makes a 200-word formal email the top "real message" example
for every Friends rewrite, reply and ✨, and `one_message()` collapses it into one line. The same applies to rules: an
edit or 👎 on an essay ("Shorter", "More personal") goes through `LEARN_SYSTEM`/`REVISE_SYSTEM`, and the resulting rule
is added to `preferences.json`, which applies to all chat messages.

There is also a client bug: an essay longer than 3000 characters fails `FeedbackBody` validation (422). `try?` swallows
the error, but the toast still says "Saved as an example of your style".

```diff
         for f in styles.feedback(style_id):
-            if f.get("audience") in AUDIENCES and f.get("text"):
+            if (f.get("audience") in AUDIENCES and f.get("text") and len(f["text"]) <= 300
+                    and f.get("format", "message") not in FORMAL):
                 self.approved[f["audience"]].append(f["text"])
```
```diff
 # writer.chat (revise) and writer.feedback: don't turn formal feedback into chat-wide rules
-            if rule:
+            if rule and format not in FORMAL:
                 styles.add_preference(ctx.id, rule)
```
(A better fix keeps formal rules in their own list and adds them only in `formal_system`, but that is a feature.) On the
client, show the toast only after the call succeeds.

### M5 · High · A voice note longer than 2 minutes is lost, and the timer is never invalidated
`ios/SaySoApp/VoiceRecorder.swift:25, 31-37`; `ios/SaySoApp/ChatView.swift:258-263`

`record(forDuration: 120)` stops the recorder by itself. The timer then sets `isRecording = false` but keeps running.
The UI shows the mic again, and the user's next tap calls `voice()`, which sees `!recorder.isRecording` and **starts a
new recording over the same file**, so the first 2 minutes are gone. Essay mode tells people "🎙 works great here", and
long dictation is exactly that use. The server accepts ≤10 MB (about 5 minutes at 16 kHz mono). Every later `start()`
also adds another repeating timer.

```diff
-            guard recorder?.record(forDuration: 120) == true else { return false }  // at most 2 minutes
+            guard recorder?.record(forDuration: 300) == true else { return false }  // ≤ 10 MB at 16 kHz mono
 ...
+    @Published private(set) var finished = false   // stopped by the time limit; the recording is still on disk
         timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
             Task { @MainActor in
                 guard let self else { return }
                 self.seconds += 1
-                if self.recorder?.isRecording == false { self.isRecording = false }
+                if self.recorder?.isRecording == false {
+                    self.timer?.invalidate()
+                    self.isRecording = false
+                    self.finished = true
+                }
             }
         }
```
```diff
 // ChatView.voice()
-        if !recorder.isRecording {
+        if !recorder.isRecording && !recorder.finished {
```
In `stop()`, reset `finished = false`. Alternatively, use `AVAudioRecorderDelegate.audioRecorderDidFinishRecording` to
send the note automatically.

### M6 · Medium (stuck for good) · Once more than 50 learned messages are queued, keyboard learning fails forever
`ios/SaySoKeyboard/PanelModel.swift:61, 139-149`; `serving/modal_app.py:262`

The queue keeps up to 200 items (`suffix(200)`), but `LearnBody.items` has `max_length=50`. `flush()` sends the whole
queue. If the keyboard was used offline, or the API was down for a while, the queue grows past 50. Every flush then gets
422, the `catch` puts the items back, and the next flush fails the same way. Nothing reaches the server again, and the
user is never told.

```diff
     func flush() {
-        let items = queue
+        let all = queue
+        let items = Array(all.prefix(50))         // the server takes at most 50 per call
         guard !items.isEmpty, hasFullAccess else { return }
-        queue = []
+        queue = Array(all.dropFirst(items.count))
         Task {
             do {
                 try await SaySoAPI.learn(items)
+                if !queue.isEmpty { flush() }
             } catch {
                 queue = items + queue
             }
         }
     }
```

---

## Should-fix

### S1 · Medium · `essay()` iterates a string outline or questions character by character
`serving/writer.py:759-760`. **Reproduced**: `{"outline": "a plan…"}` → `['a', 'p', 'l', 'a', 'n', …]`; questions `"why?"` →
`['w', 'h', 'y']`. These then show up as three one-letter question buttons in Chat.
```diff
-        outline = [clean(str(point)) for point in label.get("outline") or [] if clean(str(point))][:8]
-        questions = [clean(str(q)) for q in label.get("questions") or [] if clean(str(q))][:3]
+        as_list = lambda v: v if isinstance(v, list) else ([v] if isinstance(v, str) and v.strip() else [])
+        outline = [clean(str(p)) for p in as_list(label.get("outline")) if clean(str(p))][:8]
+        questions = [clean(str(q)) for q in as_list(label.get("questions")) if clean(str(q))][:3]
```

### S2 · Medium · `spark()` hides every failure, and its worst-case time is longer than the app's timeouts
`serving/writer.py:536-560`, `ios/Shared/API.swift:238-297`

`except Exception` also swallows programming errors (a `KeyError` in parsing, for example) and logs nothing, so a 502
in the demo can't be diagnosed from the Modal logs. The loop also sleeps 1 s after the last try. The worst case adds up
to 3 tries × `timeout`:

| call | server worst case | app timeout |
|---|---|---|
| rewrite / compose (Spark path) | 3 × 30 s (+ a second call if ECHO matches) | 20 s |
| reply (screenshot) | 3 × 30 s | 25 s |
| email | 3 × 60 s + cliché fix 3 × 60 s | 45 s |
| essay | 3 × 90 s + fix 3 × 90 s | 120 s |

When the app gives up first, it shows "The request timed out" while the server keeps spending tokens. The keyboard and
Chat then retry, and `/learn` and `/feedback` write twice.
```diff
-            except Exception:  # 429/5xx, timeout, non-JSON
+            except (httpx.HTTPError, ValueError, KeyError, IndexError) as error:  # 429/5xx, timeout, non-JSON
+                print(f"spark: {url.split('/')[2]} failed: {type(error).__name__}", flush=True)  # no content logged
                 label = {}
 ...
-            await asyncio.sleep(1)
+            if (url, api_key, model) != tries[-1]:
+                await asyncio.sleep(1)
```
Also add an overall deadline, so the total stays under the client's timeout:
`deadline = time.monotonic() + budget` and `timeout=min(timeout, deadline - time.monotonic())`.

### S3 · Medium · The app shows "Server error 502." instead of the server's message
`ios/Shared/API.swift:431-432`. Every Spark failure is a 502 with a useful `detail` ("Muse Spark did not answer, try
again", "Muse Voice Transcribe did not answer"), but the client only reads `detail` for 404/409/413/422.
```diff
-        case 404, 409, 413, 422: throw SaySoError.invalid(detail(data) ?? "The request was rejected.")
+        case 404, 409, 413, 422, 502: throw SaySoError.invalid(detail(data) ?? "The request was rejected.")
```

### S4 · Medium · The formal system prompt tells essays to use the user's fillers, laughter, swearing and emoji
`serving/writer.py:181-194, 733-736`. `formal_system` reuses `STYLE_SYSTEM` up to "Return JSON only". Since f1c0fe5,
that part includes "Their habits ARE their voice: their fillers and slang, laughter, swearing, emoji and splitting a
thought into several short messages … Their usual length is for short thoughts". The override sentence below it only
covers "An official message or an email", not essays. This contradicts `ESSAY_TASK`, and the model may follow it.
```diff
+FORMAL_SYSTEM = """You write for one specific user, in their own formal voice, so that people who know their writing
+could not tell it was not them. Keep every fact and request; never invent. Capitalized sentences, proper punctuation, no
+slang, swearing or emoji. Write in the language of the input.
+"""
 def formal_system(self, ctx, query, kind="email"):
-        return (STYLE_SYSTEM.split("Return JSON only")[0].format(style="")
+        return (FORMAL_SYSTEM
```
Use the same `FORMAL_SYSTEM` in the revise path for formal modes (`writer.py:701-704`).

### S5 · Medium · The LoRA path can return `200` with empty text
`serving/writer.py:600-603, 624`. When all candidates are blank, `best()` returns `""`, and `styled()` and `reply()`
send back `{"text": ""}`. `styled()` also returns the blank and Kazakh-drifted candidates as `candidates`. This doesn't
happen with the GPU off, but it will when the GPU is turned on for filming.
```diff
         out, parts = shape(self.best(ctx, candidates, audience, situation), format)
+        if not out:
+            raise Unavailable(502, "the model gave an empty answer, try again")
-        return {..., "candidates": [shape(c, format)[0] for c in candidates], ...}
+        return {..., "candidates": [shape(c, format)[0] for c in candidates if c.strip() and not KAZAKH.search(c)], ...}
```

### S6 · Medium · `feedback()` writes the example, then a Spark failure skips `commit()` and returns 502
`serving/writer.py:835-844`. `learn()` catches `Unavailable` around the rule call, but `feedback()` doesn't. The example
is written to the volume but not committed, the app reports an error (which `try?` swallows), and the user saves again,
so the example is stored twice.
```diff
         if edited and clean(answer) != text:
-            label = await self.spark(LEARN_SYSTEM, ..., "rule")
-            rule = clean(str(label.get("rule") or "")) or None
+            try:
+                label = await self.spark(LEARN_SYSTEM, ..., "rule")
+                rule = clean(str(label.get("rule") or "")) or None
+            except Unavailable:
+                rule = None
```
Duplication: `learn()` and `feedback()` both run "scrub → store → maybe learn a rule". A shared
`_learn_rule(ctx, audience, suggested, text)` would remove the copy (DRY).

### S7 · Medium · `/learn` can make up to 50 Spark calls in a row
`serving/writer.py:791`. The guard is `len(rules) < 2`, which counts rules found, not attempts. If Spark returns an
empty rule (the common case for edits that change content), every edited item in the batch triggers another call (up
to 50 × 3 tries × 30 s). The app gives up after 30 s and puts the items back in the queue, so they are sent again (see
M6).
```diff
-        rows, rules = [], []
+        rows, rules, asked = [], [], 0
 ...
-            if suggested and suggested != text and len(rules) < 2:
+            if suggested and suggested != text and asked < 2:
+                asked += 1
```

### S8 · Medium · `/styles/{id}/documents` drops input silently, blocks the event loop, and reports a Spark outage as "nothing readable"
`serving/modal_app.py:365-387`
* `f.read(20 MB + 1)` truncates a larger file with no error, since only the 25 MB total is checked. A Takeout .mbox is
  often bigger than 20 MB, and a truncated PDF fails to parse with no message. `files[:40]` and `images[:30]` drop the
  rest without saying so.
* `parse.text_of` (pypdf), `parse.mbox_texts` and `styles.add_documents` are CPU and disk work inside `async def`.
  On the single API container (`max_containers=1`, 32 concurrent inputs), a 300-page PDF stalls every keyboard request
  until it finishes.
* `read_page` returns `""` when Spark is down. If every upload was a photo, the user gets 422 "nothing readable" when
  the real error is a 502.
```diff
-            raw = await f.read(20 * 1024 * 1024 + 1)
+            raw = await f.read(20 * 1024 * 1024 + 1)
+            if len(raw) > 20 * 1024 * 1024:
+                raise HTTPException(413, f"{f.filename} is larger than 20 MB")
 ...
-                uploads += [(f"{name}#{i}", body) for i, body in enumerate(parse.mbox_texts(raw))]
+                uploads += [(f"{name}#{i}", body) for i, body in enumerate(await aio.to_thread(parse.mbox_texts, raw))]
             else:
-                uploads.append((name, parse.text_of(name, raw)))
+                uploads.append((name, await aio.to_thread(parse.text_of, name, raw)))
 ...
+        if len(files) > 40 or len(images) > 30:
+            raise HTTPException(413, "at most 40 files and 30 photos at once")
-        formal = styles.add_documents(style_id, uploads, kind)
+        formal = await aio.to_thread(styles.add_documents, style_id, uploads, kind)
```
To fix the misleading error, have `read_page` re-raise `Unavailable` when every image failed.

### S9 · Medium (privacy) · `mbox_texts` doesn't check for the Sent label, so a full "All Mail" export teaches other people's emails as the user's voice
`serving/documents.py:65-83`. The module docstring and the guide both say "Sent only", but nothing enforces it. Takeout
marks each message with `X-Gmail-Labels`. The function also takes the first 300 messages, which are the oldest.
```diff
         for message in mailbox.mbox(f.name):
+            labels = (message.get("X-Gmail-Labels") or "").casefold()
+            if labels and "sent" not in labels and "отправленные" not in labels:
+                continue  # someone else's email
```

### S10 · Medium · One big email upload pushes all of the user's essays out
`serving/styles.py:236`. `rows[-MAX_PARAGRAPHS:]` caps both kinds together at 300 paragraphs, so a Takeout .mbox
removes every essay paragraph and `counts["essay"]` drops to 0.
```diff
-    rows = rows[-parse.MAX_PARAGRAPHS:]
+    rows = [r for k in parse.KINDS for r in [x for x in rows if x.get("kind", "essay") == k][-parse.MAX_PARAGRAPHS:]]
```

### S11 · Low · .docx text keeps `&quot;` and `&#…;`, and glues words around tabs and line breaks
`serving/documents.py:95-96`.
```diff
-            xml = re.sub(r"</w:p>", "\n", xml)
-            return re.sub(r"<[^>]+>", "", xml).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
+            xml = re.sub(r"</w:p>", "\n\n", xml)                       # a Word paragraph is a paragraph
+            xml = re.sub(r"<w:(tab|br)\b[^>]*/>", " ", xml)
+            return html.unescape(re.sub(r"<[^>]+>", "", xml))
```
(`"\n\n"` also helps `paragraphs()`: right now a .docx always takes the "fewer than 3 blocks" path, which joins lines.)

### S12 · Medium · "Remove all formal writing" has no confirmation, and any error blanks the style card
`ios/SaySoApp/StyleCardView.swift:61, 133-139`. `style = try? await …` sets `style` to `nil` on any error, so the whole
card disappears. `forgetLearned` has the same pattern.
```diff
-    private func clearFormal() async {
-        style = try? await SaySoAPI.updateStyle(styleID, clearDocuments: true)
-    }
+    private func clearFormal() async {
+        do { style = try await SaySoAPI.updateStyle(styleID, clearDocuments: true) }
+        catch { self.error = error.localizedDescription }
+    }
```
Put the button behind `.confirmationDialog("Remove all formal writing?", …)`.

### S13 · Medium (honesty) · The "Muse Spark Open writes in this style" label is attached to the wrong condition
`ios/SaySoApp/StylesView.swift:129`. `adapterReady` means the style's own LoRA (Muse Glimmer) is trained. Spark Open
writes for **every** style while `SAYSO_GPU=off`, and the LoRA writes chat formats when the GPU is on. As it is, styles
without a LoRA say nothing, and styles with one claim Spark Open writes. Judges read this row.
```diff
-        else if style.adapterReady == true { parts.append("Muse Spark Open writes in this style") }
+        else if style.adapterReady == true { parts.append("own model trained") }
```
Add a single line elsewhere (Setup or the footer) saying that Muse Spark Open writes in your style.

### S14 · Medium · The delete key can keep deleting after the finger is lifted
`ios/SaySoKeyboard/LetterKeys.swift:124-141`. The repeat `Task` is cancelled only in `DragGesture.onEnded`. SwiftUI does
not call `onEnded` when the system cancels the gesture (a notification banner, Control Center, the host app dismissing
the keyboard). The view also has no `onDisappear`, so a held ⌫ can keep deleting the field every 40 ms.
```diff
     @State private var repeating: Task<Void, Never>?
+    @GestureState private var pressing = false
 ...
-            .gesture(DragGesture(minimumDistance: 0)
+            .gesture(DragGesture(minimumDistance: 0).updating($pressing) { _, state, _ in state = true }
                 .onChanged { … }
                 .onEnded { … })
+            .onChange(of: pressing) { _, down in if !down { repeating?.cancel(); repeating = nil } }
+            .onDisappear { repeating?.cancel(); repeating = nil }
```

### S15 · Medium (eval validity) · `style_gain.py` compares the outputs with all real messages, not with their matched pairs
`eval/style_gain.py:86-87`. Failed rows are dropped from `pairs`, but `similarity(...)` is still called with the full
`real` list. When some calls fail, "form" compares two different sets, and `n` in the JSON doesn't describe the form
score.
```diff
-            results[how] = {"form": similarity([o for o, _ in pairs], real),
+            results[how] = {"form": similarity([o for o, _ in pairs], [t for _, t in pairs]),
```
Also, `--only` overwrites the whole results file with just that subset. Merge with the existing file instead.

### S16 · Medium (stats honesty) · The blind test counts duplicate codes and treats every answer as independent
`eval/blind_test.py:391-398, 422`. The same code pasted twice, or a friend who resubmits, is counted twice. The binomial
test also uses n = people × questions as independent trials, but answers from the same person and to the same question
are correlated, so p is too small. The submission quotes these p-values.
```diff
-    for code in codes:
+    for code in dict.fromkeys(re.sub(r"\s+", "", c) for c in codes):   # the same code once
```
Also report a per-person test, for example the count of people whose found-me rate is above 1/3 against Binomial(people,
½), or state the caveat next to the p-value in README/SUBMISSION.

### S17 · Low (privacy) · A style deleted mid-build comes back as a folder with no meta.json
`serving/build_style.py:394-401`. `write_jsonl`/`write_json` call `mkdir(parents=True)`, so when the user deletes the
style during "reading" or "profile", the build writes `turns.jsonl`, `profile.json` and `pairs/` into a new orphan
folder. `all_styles()` hides it, and nothing deletes it. The `except styles.Gone` added this week only covers
`stage()`.
```diff
+    def alive():
+        if styles.meta(style_id) is None:
+            raise styles.Gone(style_id)
 ...
+        alive()
         styles.write_jsonl(styles.folder(style_id) / "turns.jsonl", ...)
```
Call `alive()` before each write, and `shutil.rmtree` the folder in `except styles.Gone`.

### S18 · Low · The 👍 toast shows before the save, and failures are hidden
`ios/SaySoApp/ChatView.swift:317-320`. `show("Saved as an example of your style")` runs before the request, and `try?`
drops errors (including the 422 for essays over 3000 characters, see M4). Show the toast only after the call succeeds.

---

## Nice-to-have

| id | where | what | fix |
|---|---|---|---|
| N1 | `serving/writer.py:17-18`, `:567-568`; `serving/modal_app.py:136-149`; `serving/documents.py:5` | Docstrings no longer match the code. The module "Formats" list leaves out essay. `examples()` says "none for official messages and emails" but returns `formal_block`. The `api()` docstring leaves out modes email/essay, the `question/words/reply_to` fields, `/learn`, `/styles/{id}/documents` and format `essay`. documents.py says "Sent only" (see S9). | Update the text. |
| N2 | `serving/writer.py:244-246` | `shape(..., "series")` keeps 4 lines and drops the 5th and later with no warning. Reproduced: `a…e` → `a…d`. | Join the extra lines into the 4th. |
| N3 | `serving/writer.py:234-236` | `capitalize` uppercases after abbreviations. Reproduced: "e.g. this" → "e.g. This". | Require `[.!?]\s+` not preceded by a one-letter token. |
| N4 | `serving/documents.py:40-42` | `LABEL` removes real words. Reproduced: "Test-driven development…" → "driven development…". | Require `\s*[:]` or a digit for `test`/`body`/`prep`. |
| N5 | `ios/SaySoApp/FormalImportView.swift:127` | Photo names skip numbers (`files.count + index + 1` while `files` grows): page01, page03, page05. Every paste is named `"pasted"`, so `counts` (distinct `doc`) counts all pastes as one document and page01.jpg from two sessions as one. | Use `files.count + 1` after each append. On the server, add a short hash to `doc`. |
| N6 | `ios/SaySoKeyboard/PanelModel.swift:346-357` | `insertNextPart` appends to whatever is in the field, so tapping Next before sending the previous part glues the two together. | Skip the insert, or show a message, when `documentContextBeforeInput` isn't empty. |
| N7 | `serving/writer.py:585-586` | The ECHO retry "with Muse Spark 1.3" sends the same request to the same model when `writer == "meta"`. | Retry only when `self.writer == "open"`. |
| N8 | `serving/writer.py:701-705` | In formal revise, the formal block appears twice: in the system prompt (`voice`) and again through `self.examples(...)`. | Leave out the examples when `format in FORMAL`. |
| N9 | `serving/modal_app.py:244`, `writer.py:755`, `ChatView.swift:94` | Three different essay-length ranges: API 50–900, writer clamps to 80–900, app 100–650. | Pick one range. |
| N10 | `ios/Shared/API.swift:301-319, 335-344, 368-383` | Three hand-written multipart builders, two using `.data(using:)!` and one `Data(_.utf8)` (DRY). | Use one `multipart(fields:files:)` helper. |
| N11 | `ios/SaySoApp/ChatView.swift:381, 393, 402` | `ForEach(..., id: \.self)` on Spark-generated questions and alternatives: duplicates break SwiftUI identity. `answer.parts!` is force-unwrapped. | Use `enumerated()` with `\.offset`, and `answer.parts ?? []`. |
| N12 | `serving/writer.py` (845 lines) | Above the 800-line guideline. The formal pipeline (`formal_block`, `formal_system`, `email`, `essay`, `ESSAY_*`, `CLICHES`) would fit in its own `formal_writer.py`. | After the freeze. |
| N13 | `serving/build_style.py:179` | `path.suffix == ".zip"` is case-sensitive, but the filter uses `.lower()`, so `Chat.ZIP` is never unpacked. | Use `path.suffix.lower()`. |
| N14 | `serving/documents.py:155-156` | `first_person` is computed and stored but never used (`profile_text` ignores it). The "i" match also counts Roman numerals and list markers. | Remove it, or use it in `profile_text`. |

## Checked and fine
* `nearest()` (local TF-IDF): an empty pool or a query with nothing in common returns `[]`, and the caller falls back to
  random examples. The index is cached per `Context` and rebuilt when `styles.version` changes. Postings are filtered by
  audience at query time, which is O(postings of the query's grams), fine at the main style's size. No data leaves the
  server.
* The fallback order in `spark()`: `writes=True` and `writer == "open"` → Open, then Meta ×2. Reads and images → Meta
  ×2, then Open. With no `fallback_key`, Meta only. `rule` is the only key where an empty string is accepted. This
  matches the docstring.
* `clip()` keeps line structure and handles empty lines and limit 0. `shape()` for email/essay is idempotent (applying it
  twice gives the same result).
* Prompt-template injection: `.format()` is only applied to the templates, never to user text, and `clean()` removes
  `<|…|>` tokens before user text goes into LoRA prompts.
* `TokenGate`: the token and Content-Length are checked before any body is read. `/transcribe` checks the RIFF header and
  size.
* Keyboard memory: no images or large buffers are kept. The learn queue is capped at 200 in UserDefaults, and
  `PanelOption`s are small.
* No hard-coded secrets in the files reviewed. `.env` and `data/` were not opened.
