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
# Section labels of the user's old assignments ("Argument 2:", "Thesis:", "Q3:"): cut off, so a new essay takes their
# voice, never the structure of their homework.
LABEL = re.compile(r"^\s*(thesis|argument\s*\d*|counter-?argument|conclusion|introduction|body|q\s*\d+|prep\s*\d*|"
                   r"test\s*\d*|тезис|аргумент\s*\d*|контраргумент|вывод|заключение|введение|вопрос\s*\d*)\s*[:.\-–—]\s*",
                   re.I)
IMAGES = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
# Where an email starts quoting the message it answers (someone else's text): everything after it is dropped.
QUOTE = re.compile(r"^\s*(>|On .{5,120} wrote:|.{0,80}(написал|написала|писал)\(?а?\)?:\s*$|-{2,}\s*Original Message|"
                   r"-{2,}\s*Пересылаемое|-{2,}\s*Forwarded message|From:|От:|Sent from my|Отправлено с)", re.I | re.M)
# The mail headers at the very top of a printed or pasted email (Apple Mail's PDF starts with them): not a quote.
LEADING_HEADERS = re.compile(r"\A(?:[ \t]*(?:From|To|Cc|Bcc|Subject|Date|Sent|От|Кому|Копия|Тема|Дата|Отправлено)"
                             r"[ \t]*:.*\n|[ \t]*\n)+", re.I)
# Greetings keep their word, not the name ("Hi Tom," → "Hi [Name],"); a sign-off that is only a name is the user's name.
GREETING = re.compile(r"^((?:hi|hello|hey|dear|good (?:morning|afternoon|evening)|your excellency|здравствуй(?:те)?|"
                      r"привет|добрый (?:день|вечер)|доброе утро|уважаем\w*(?: команда)?|сәлем\w*|құрметті)[ ,!]+)(.+?)([,!.]?)$",
                      re.I)
SIGN_OFF = re.compile(r"(best|regards|thanks|thank you|cheers|sincerely|yours|respectfully|с уважением|спасибо|"
                      r"всего доброго|хорошего дня|құрметпен|рахмет)", re.I)
JUST_A_NAME = re.compile(r"^[A-ZА-ЯЁӘҒҚҢӨҰҮҺІ][\w.-]*(?: [A-ZА-ЯЁӘҒҚҢӨҰҮҺІ][\w.-]*){0,2}$")

READ_SYSTEM = """You transcribe the user's own writing from a photo or a screenshot: a page of an essay or paper, or an
email the user SENT. Return JSON only: {"text": "<the text>"}.
Keep the user's text exactly as written (wording, spelling). A handwritten or printed line break is NOT a new
paragraph: join the lines of one paragraph into one line, and separate paragraphs (a new indent, a heading like
"Argument 2:", a gap) with a blank line. Leave out crossed-out words and scribbles. Replace the names of other people
and companies (the recipient in the greeting, people or firms mentioned) with [Name]. For an email: keep
the greeting, body and sign-off; skip the mail app's interface, headers (to, from, date, subject line), the signature block
(logo, address, links, confidentiality notice) after the sign-off, and any quoted earlier message from someone else. For a page: skip page numbers and headers. If there is no text
by the user, return {"text": ""}."""


def own_email(text):
    """An email the user sent → only their own part: the mail headers at the top are dropped, and everything from the
    first quote marker after the user's text ("On … wrote:", "> …", an Outlook "From:" block, "Sent from my iPhone")
    is cut off."""
    text = LEADING_HEADERS.sub("", text)
    match = QUOTE.search(text)
    return text[:match.start()] if match else text


def mask_edge(line, opening):
    """Other people's names out of a greeting; a sign-off that is only a name (the user's own) is dropped."""
    if not line:
        return None
    if opening:
        match = GREETING.match(line)
        return f"{match.group(1).rstrip()} [Name]{match.group(3)}" if match and "[Name]" not in line else line
    if SIGN_OFF.search(line):
        return line
    return None if JUST_A_NAME.match(line.rstrip(",.")) else line


def mbox_texts(raw, limit=300):
    """A Google Takeout .mbox (the Sent label) → the bodies of the user's emails, quotes cut off."""
    out = []
    with tempfile.NamedTemporaryFile(suffix=".mbox") as f:
        f.write(raw)
        f.flush()
        for message in mailbox.mbox(f.name):
            labels = (message.get("X-Gmail-Labels") or "").casefold()
            if labels and "sent" not in labels and "отправлен" not in labels:
                continue  # an "All mail" export: other people's emails are not the user's writing
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
                if archive.getinfo("word/document.xml").file_size > 50 * 1024 * 1024:
                    return ""  # not a real essay: a zip bomb
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
        while LABEL.match(cleaned):  # "Q3: Thesis: ..." → "..."
            cleaned = LABEL.sub("", cleaned, count=1)
        if len(cleaned) >= MIN_CHARS:
            out.append(cleaned[:2000])
    return out


def edges(text):
    """The opening and closing lines of one document (how the user greets and signs off in emails)."""
    lines = [" ".join(line.split()) for line in text.replace("\r", "").split("\n") if line.strip()]
    short = lambda line: 0 < len(line.split()) <= 6
    opening = lines[0] if lines and short(lines[0]) else None
    closing = None
    for line in reversed(lines[1:][-3:]):  # the sign-off, skipping the user's name under it
        if short(line) and not re.search(r"\d{3,}", line) and mask_edge(line, False):
            closing = line
            break
    return mask_edge(opening, True), closing


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
        lines.append("- linking words they sometimes use (never force them, never misuse them): " + ", ".join(p["connectors"]))
    if p.get("openings"):
        lines.append("- opens emails with: " + " / ".join(p["openings"]))
    if p.get("closings"):
        lines.append("- signs off with: " + " / ".join(p["closings"]))
    return "\n".join(lines)
