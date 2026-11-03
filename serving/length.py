"""Essay length: the asked number of words, within ±10 %.

Essays came out noticeably shorter than asked ("up to about N words"). The prompt now states
the target and the allowed range; after writing, the words are counted: under 90 % of the target, an "expand to N
words" pass (at most two), over 115 %, a trim pass (at most one). A pass that makes it worse is not kept. Expanding
explains and connects the user's own facts; it never invents new ones.
"""

LOW, HIGH = 0.9, 1.1  # the range the prompt asks for
TRIM_ABOVE = 1.15  # a little over is fine; more is cut
MAX_EXPANDS, MAX_TRIMS = 2, 1

EXPAND = """This essay has {count} words; it must have about {words} words (between {low} and {high}).
Expand it to about {words} words: keep its plan, order, facts and voice; for each point, explain more fully what the
user did, how and why it mattered, and connect the points, using ONLY the facts in the essay and the user's notes below.
Never invent experiences, names, numbers or feelings, never repeat a sentence or a fact, never pad with general
statements.{problems}
The user's notes: {notes}
Essay:
{text}
Return JSON only: {{"text": "<the essay, paragraphs separated by blank lines>"}}."""

TRIM = """This essay has {count} words; it must have about {words} words (between {low} and {high}).
Cut it to about {words} words: keep its plan, every key fact and its voice; remove repetition and the least important
details first.{problems}
Essay:
{text}
Return JSON only: {{"text": "<the essay, paragraphs separated by blank lines>"}}."""


def count(text):
    return len((text or "").split())


def bounds(words):
    return round(words * LOW), round(words * HIGH)


def target(words):
    """The length line of the essay prompt."""
    low, high = bounds(words)
    return (f"about {words} words (allowed: {low} to {high} words, ±10%; count them, an essay much shorter than "
            f"{low} words is a failure)")


def distance(text, words):
    """How far from the allowed range (0 inside it)."""
    low, high = bounds(words)
    n = count(text)
    return max(low - n, n - high, 0)


async def fit(call, text, words, notes="", problems_of=None, clean=lambda t: t.strip()):
    """→ (text, passes). call(prompt) → {"text": ...} is the writer's Muse Spark call (same system as the essay).
    problems_of(text) → a list of other things to fix in the same pass (AI clichés); with none and the length fine,
    nothing is called. The text closest to the allowed range is kept."""
    problems_of = problems_of or (lambda _text: [])
    low, high = bounds(words)
    best, passes, expands, trims = text, 0, 0, 0
    while True:
        current = best  # the next pass starts from the best text so far
        n = count(current)
        if n < low and expands < MAX_EXPANDS:
            template, expands = EXPAND, expands + 1
        elif n > round(words * TRIM_ABOVE) and trims < MAX_TRIMS:
            template, trims = TRIM, trims + 1
        else:
            break
        found = problems_of(current)
        extra = (" Also " + "; ".join(found) + ".") if found else ""
        label = await call(template.format(count=n, words=words, low=low, high=high, problems=extra,
                                           notes=notes or "(none)", text=current))
        passes += 1
        current = clean(str(label.get("text") or "")) or current
        if distance(current, words) < distance(best, words) or (
                distance(current, words) == distance(best, words) and len(problems_of(current)) < len(problems_of(best))):
            best = current
    return best, passes
