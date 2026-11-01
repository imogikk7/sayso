"""The user's formal writing (emails, essays, papers they wrote themselves) → paragraphs and a formal profile.

Chats teach how the user writes to friends; this teaches how they write when it's official, so emails and essays come
out in their formal voice instead of a generic polite one. Files: .txt / .md, .docx, .pdf, or pasted text. Links,
emails, phone and card numbers are removed; only the paragraphs are kept (on the private volume).
"""

import io
import re
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
    """Text → the user's paragraphs, cleaned; a pdf's hard line breaks inside a paragraph are joined back."""
    blocks = re.split(r"\n\s*\n", text.replace("\r", ""))
    if len(blocks) < 3:  # no blank lines between paragraphs (pdf, plain paste): one line = one paragraph
        blocks = text.split("\n")
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
