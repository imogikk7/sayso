"""Auto-series: a long "message" comes out as several short messages when that is how the user writes.

The user's own turns are consecutive messages merged with newlines, so their style already says how often they split a
thought into several messages and how long each one is. When they usually do and the content is long (a big pasted
text in Rewrite, a long instruction in Write), format "message" is asked as AUTO: the model writes one message, or 2 to
5 short ones if that is how the user would send it. "series" always splits; "official", "email" and "essay" never do.
"""

import re
import statistics

AUTO = "auto"  # an internal format: "message" that may come back as a series; never accepted from the app
MIN_PARTS, MAX_PARTS = 2, 5
SERIES_PARTS = 4  # explicit "series": 2 to 4 messages (writer.FORMATS["series"])
SPLITS = 0.25  # the share of the user's turns to this audience sent as several messages that makes it their habit
MIN_TURNS = 5
LONG_CHARS = 120  # shorter content stays one message whatever the habit
AUTO_FORMAT = ("the way this user sends it: they often split a longer thought into several quick messages, so if this "
               "content is long write it as 2 to 5 separate short chat messages, each on its own line, each about as "
               "long as their usual messages, every point kept; if it is short, as ONE message without line breaks")
AUTO_WORDS = 120  # writer.FORMAT_WORDS: a long rewrite is not clipped to a single message's length
SENTENCE = re.compile(r"(?<=[.!?…)])\s+")
CLAUSE = re.compile(r"(?<=[,;:—])\s+")


def habit(ctx, audience):
    """How the user sends to this audience, from their own turns: {turns, splits (share sent as several messages),
    lines (mean messages per turn), line_chars (median characters per message)}."""
    turns = [t for t in ctx.examples.get((audience, None), []) if t.strip()]
    if not turns:
        return {"turns": 0, "splits": 0.0, "lines": 1.0, "line_chars": 0}
    counts = [len([line for line in t.splitlines() if line.strip()]) or 1 for t in turns]
    lines = [len(line.strip()) for t in turns for line in t.splitlines() if line.strip()]
    return {"turns": len(turns), "splits": sum(n > 1 for n in counts) / len(turns),
            "lines": sum(counts) / len(turns), "line_chars": statistics.median(lines) if lines else 0}


def splits_habitually(h):
    return h["turns"] >= MIN_TURNS and h["splits"] >= SPLITS


def is_long(content, h):
    """Long for this user: well over what they put in one message (and never under LONG_CHARS)."""
    return len(" ".join((content or "").split())) > max(LONG_CHARS, 4 * h["line_chars"])


def choose(ctx, audience, content, format):
    """The format to ask the model for: AUTO for a long "message" to an audience the user writes to in series."""
    if format != "message" or ctx is None:
        return format
    h = habit(ctx, audience)
    return AUTO if splits_habitually(h) and is_long(content, h) else format


def split(text):
    """One line → its sentences (or, for one long sentence, its clauses): an explicit series always splits."""
    text = " ".join(text.split())
    pieces = [p for p in SENTENCE.split(text) if p.strip()]
    if len(pieces) < 2 and len(text) > 60:
        pieces = [p for p in CLAUSE.split(text) if p.strip()]
    return pieces or ([text] if text else [])


def cap(lines, limit):
    """At most `limit` messages without losing any: the shortest neighbouring pair is merged until it fits."""
    lines = list(lines)
    while len(lines) > limit:
        i = min(range(len(lines) - 1), key=lambda k: len(lines[k]) + len(lines[k + 1]))
        lines[i:i + 2] = [f"{lines[i]} {lines[i + 1]}"]
    return lines


def parts_of(text, format):
    """The messages to send one by one: the lines of a series (or an auto-series), else the text as one part."""
    if format in ("series", AUTO):
        lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
        if format == "series" and len(lines) == 1:
            lines = split(lines[0])
        return cap(lines, SERIES_PARTS if format == "series" else MAX_PARTS) if len(lines) > 1 else lines or [text]
    return [text]
