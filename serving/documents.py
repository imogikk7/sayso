"""The user's formal writing (emails, essays, papers they wrote themselves) → paragraphs and a formal profile.

Chats teach how the user writes to friends; this teaches how they write when it's official, so emails and essays come
out in their formal voice instead of a generic polite one. Two kinds, kept apart: "email" (how they greet, ask and
sign off) and "essay" (longer texts, papers). Sources: .txt / .md, .docx, .pdf, .mbox (Google Takeout, Sent only),
pasted text, and photos or screenshots (read by Muse Spark in serving/writer.py). In emails, quoted earlier messages
(other people's text) are cut off. Links, emails, phone and card numbers are removed; only paragraphs are kept.
"""

import io
import mailbox
import re
import tempfile
import statistics
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

from parse_telegram import clean as scrub  # noqa: E402

MIN_CHARS = 40  # shorter lines are headings, signatures, page numbers
MAX_PARAGRAPHS = 300
SENTENCE = re.compile(r"(?<=[.!?…])\s+")
# How a writer links ideas: the profile notes which of these the user actually uses.
CONNECTORS = [
    "однако", "кроме того", "поэтому", "таким образом", "в частности", "например", "во-первых", "во-вторых",
    "в итоге", "в результате", "тем не менее", "при этом", "также", "именно", "потому что", "так как", "хотя",
    "however", "moreover", "therefore", "for example", "for instance", "in addition", "as a result", "although",
    "because", "while", "first", "finally", "in fact", "that is why", "this is why",
]


KINDS = ("email", "essay")
IMAGES = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
# Where an email starts quoting the message it answers (someone else's text): everything after it is dropped.
QUOTE = re.compile(r"^\s*(>|On .{5,120} wrote:|.{0,80}(написал|написала|писал)\(?а?\)?:\s*$|-{2,}\s*Original Message|"
                   r"-{2,}\s*Пересылаемое|From:|От:|Sent from my|Отправлено с)", re.I | re.M)

READ_SYSTEM = """You transcribe the user's own writing from a photo or a screenshot: a page of an essay or paper, or an
email the user SENT. Return JSON only: {"text": "<the text>"}.
Keep the user's text exactly as written (wording, spelling). A handwritten or printed line break is NOT a new
paragraph: join the lines of one paragraph into one line, and separate paragraphs (a new indent, a heading like
"Argument 2:", a gap) with a blank line. Leave out crossed-out words and scribbles. For an email: keep
the greeting, body and sign-off; skip the mail app's interface, headers (to, from, date, subject line), and any quoted
earlier message or reply from someone else below it. For a page: skip page numbers and headers. If there is no text
by the user, return {"text": ""}."""


def own_email(text):
    """An email the user sent → only their own part (the quoted message they answered is cut off)."""
    match = QUOTE.search(text)
    return text[:match.start()] if match else text


def mbox_texts(raw, limit=300):
    """A Google Takeout .mbox (the Sent label) → the bodies of the user's emails, quotes cut off."""
    out = []
    with tempfile.NamedTemporaryFile(suffix=".mbox") as f:
        f.write(raw)
        f.flush()
        for message in mailbox.mbox(f.name):
            body = ""
            for part in message.walk() if message.is_multipart() else [message]:
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True) or b""
                    body = payload.decode(part.get_content_charset() or "utf-8", "ignore")
                    break
            body = own_email(body).strip()
            if body:
                out.append(body)
            if len(out) >= limit:
                break
    return out


def text_of(name, raw):
    """One uploaded file → its text ("" if it can't be read)."""
    suffix = Path(name).suffix.lower()
    try:
        if suffix == ".docx":
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                xml = archive.read("word/document.xml").decode("utf-8", "ignore")
            xml = re.sub(r"</w:p>", "\n", xml)
            return re.sub(r"<[^>]+>", "", xml).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        if suffix == ".pdf":
            from pypdf import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
        return raw.decode("utf-8", "ignore")
    except Exception:
        return ""


def paragraphs(text):
    """Text → the user's paragraphs, cleaned. Paragraphs are separated by blank lines; without them (a pdf, a page
    read line by line), lines are joined until one ends a sentence, so a wrapped line doesn't become a paragraph."""
    blocks = re.split(r"\n\s*\n", text.replace("\r", ""))
    if len(blocks) < 3:
        blocks, current = [], []
        for line in text.replace("\r", "").split("\n"):
            if line.strip():
                current.append(line.strip())
                if re.search(r"[.!?…:]\s*$", line) and len(" ".join(current)) >= MIN_CHARS:
                    blocks.append(" ".join(current))
                    current = []
        if current:
            blocks.append(" ".join(current))
    out = []
    for block in blocks:
        joined = " ".join(line.strip() for line in block.split("\n") if line.strip())
        cleaned = " ".join(scrub(joined).split())
        if len(cleaned) >= MIN_CHARS:
            out.append(cleaned[:2000])
    return out


def edges(text):
    """The opening and closing lines of one document (how the user greets and signs off in emails)."""
    lines = [" ".join(line.split()) for line in text.replace("\r", "").split("\n") if line.strip()]
    short = lambda line: 0 < len(line.split()) <= 6
    opening = lines[0] if lines and short(lines[0]) else None
    closing = lines[-1] if len(lines) > 1 and short(lines[-1]) and not re.search(r"\d{3,}", lines[-1]) else None
    return opening, closing


def profile(texts, ends):
    """texts: the user's formal paragraphs; ends: (opening, closing) of each document (greetings and sign-offs)."""
    sentences = [s for t in texts for s in SENTENCE.split(t) if s.strip()]
    lower = " ".join(texts).lower()
    used = Counter({c: len(re.findall(rf"(?<!\w){re.escape(c)}(?!\w)", lower)) for c in CONNECTORS})
    openings, closings = Counter(), Counter()
    for o, c in ends:
        if o:
            openings[o.rstrip(",:!")] += 1
        if c:
            closings[c.rstrip(",.")] += 1
    return {
        "paragraphs": len(texts),
        "sentence_words": round(statistics.median(len(s.split()) for s in sentences), 1) if sentences else None,
        "paragraph_words": round(statistics.median(len(t.split()) for t in texts), 1) if texts else None,
        "connectors": [c for c, n in used.most_common(8) if n],
        "first_person": round(len(re.findall(r"(?<!\w)(я|мне|меня|мой|моя|мои|i|my|me)(?!\w)", lower))
                              / max(len(lower.split()), 1), 3),
        "openings": [o for o, _ in openings.most_common(3)],
        "closings": [c for c, _ in closings.most_common(3)],
    }


def profile_text(p):
    if not p or not p.get("paragraphs"):
        return ""
    lines = [f"- sentences of about {p['sentence_words']} words, paragraphs of about {p['paragraph_words']} words"]
    if p.get("connectors"):
        lines.append("- linking words they use (only where natural): " + ", ".join(p["connectors"]))
    lines.append(f"- first person (I/my) in {p['first_person']:.0%} of words")
    if p.get("openings"):
        lines.append("- opens emails with: " + " / ".join(p["openings"]))
    if p.get("closings"):
        lines.append("- signs off with: " + " / ".join(p["closings"]))
    return "\n".join(lines)
