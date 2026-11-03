"""Chat memory: the earlier turns of a chat thread (`previous`, up to 3 {request, answer}, oldest first).

The bug it fixes: the user asked for an email, then sent «на русском» in the same chat. Without memory the model got
only «на русском» as the notes, and wrote a brand-new email about nothing ("Детали обращения не были указаны").

  is_refinement(request, previous, mode)   whether the new request changes the last answer ("на русском", "shorter",
                                           "more formal", "add that I'm sick", "in English") or starts a new topic;
                                           a cheap heuristic, no model call (unit-tested in tests/test_memory.py)
  respond(...)                             a refinement → the last answer revised with that instruction, its content
                                           kept; a new topic → the route's own answer, with the earlier turns added to
                                           its Muse Spark calls only as context for consistency (NOTE, via with_note)
"""

import contextvars
import re

MAX_PREVIOUS = 3
NOTE_CHARS = 240
# Set while a route writes a new-topic answer; Writer.spark adds it to the user message (see with_note).
NOTE = contextvars.ContextVar("sayso_thread_note", default="")

# Change the language, length or tone of what is there: "на русском", "по-английски", "shorter", "более формально".
MODIFIER = re.compile(
    r"\b(?:на|по)[ -]?(?:русск|английск|англ|казахск|казах|каз|рус|немецк|французск|турецк)\w*|"
    r"\b(?:in|into|to) (?:english|russian|kazakh|german|french|turkish)\b|\btranslat\w*|\bперев(?:е|о)д\w*|"
    r"\b(?:english|russian|kazakh|английский|русский|казахский|орысша|ағылшынша|қазақша)\b|"
    r"\b(?:по)?короче\b|\bсократи\w*|\bсокращ\w*|\bкратк\w*|\b(?:по)?длиннее\b|\bподробн\w*|\bразверн\w*|"
    r"\bрасширь\w*|\bдлинн\w*|\bкоротк\w*|\bсложно\b|\bгрубо\b|\bсухо\b|\bзанудно\b|\bwordy\b|\bshort\w*|\blong\w*|\bbrief\w*|\bconcise\w*|\bdetail\w*|\bexpand\w*|\bfewer words\b|"
    r"\b(?:не)?формальн\w*|\bофициальн\w*|\bвежлив\w*|\bмягче\b|\bж[её]стче\b|\bстроже\b|\bпроще\b|\bдружелюбн\w*|"
    r"\bтеплее\b|\bхолоднее\b|\bгрубее\b|\bувереннее\b|\bсерь[её]зн\w*|\bвеселее\b|\bсмешнее\b|\bделов\w*|\bкультурн\w*|"
    r"\b(?:in)?formal\w*|\bcasual\w*|\bpolite\w*|\bfriendl\w*|\bsofter\b|\bwarmer\b|\bharsher\b|\bstricter\b|"
    r"\bsimpler\b|\bruder\b|\bprofessional\w*|\bconfident\w*|\bserious\w*|\bfunnier\b|\bnicer\b|\bkinder\b|"
    r"\bслишком\b|\btoo\b|\bне так\b|\bещ[её] раз\b|\bдругой вариант\b|\bagain\b|\banother (?:one|version|way)\b|"
    r"\bless\b|\bmore\b|\bменее\b|\bболее\b", re.I)
# Change what it says: "добавь что я болею", "add that I'm sick", "убери про деньги".
EDIT = re.compile(
    r"^(?:добавь|допиши|упомяни|укажи|убери|удали|вычеркни|замени|исправь|поменяй|измени|перепиши|переделай|"
    r"переформулируй|верни|оставь|скажи там|add|mention|include|remove|delete|drop|cut|replace|change|fix|rewrite|"
    r"rephrase|redo|reword|undo|keep|say that|also say)\b", re.I)
# Words that point back at the last answer ("make IT shorter", "в ЭТОМ письме").
REFERENCE = re.compile(r"\b(?:это|этом|его|е[её]|там|тут|текст\w*|письм\w*|сообщени\w*|ответ\w*|вариант\w*|"
                       r"эссе|it|this|that|there|the (?:text|email|message|answer|essay)|что)\b", re.I)
FILLER = set("""а и ну теперь давай можно сделай сделать сделайте пожалуйста плиз пж бы так же немного чуть слегка
это его её ее текст письмо сообщение ответ вариант напиши перепиши можешь можно ли надо нужно но да
please pls plz make it this that now a an the bit little bit just but and or same can could you write again
also do so""".split())
LEAD = {"а", "и", "ну", "теперь", "еще", "ещё", "также", "пожалуйста", "now", "and", "also", "please", "just"}
MAX_MODIFIER_WORDS, MAX_EDIT_WORDS = 8, 25

REVISE = """You already answered the user in this chat; now they ask you to change that answer.
Their request then: {request}
Your last answer:
{answer}
What they ask now: {instruction}
Change your last answer following ONLY what they ask now ("на русском" / "in English" = the same text in that language;
"shorter" = the same points in fewer words; "more formal" = the same text, more formal; "add that …" = the same answer
plus that). Keep everything else: every fact, request, date and amount, who it is addressed to, and the kind of text (an
email stays an email with its greeting and sign-off). Never start a new text from scratch, never write about the
request itself ("no details were given"), never add facts that are in neither the last answer nor what they ask now.
Never write placeholders like [Name] and never introduce the user (name, job, role, organization) unless they ask for it.
{format}{variants}
Return JSON only: {{"text": "<the changed answer>"{extra}}}."""


def turns(previous):
    """[{request, answer}] (dicts or models) → the last MAX_PREVIOUS with an answer, as plain dicts."""
    out = []
    for p in previous or []:
        p = p if isinstance(p, dict) else getattr(p, "model_dump", lambda: {})()
        request, answer = str(p.get("request") or "").strip(), str(p.get("answer") or "").strip()
        if answer:
            out.append({"request": request, "answer": answer})
    return out[-MAX_PREVIOUS:]


def _words(text):
    return re.findall(r"[\w'-]+", (text or "").casefold())


def is_refinement(request, previous, mode="write"):
    """Whether `request` changes the last answer of this thread instead of starting a new topic.
    A modifier with nothing else in it ("на русском", "сделай короче и вежливее", "more formal pls") → yes; an edit
    ("добавь что я болею", "add that I'm sick", "убери про деньги") → yes, except in rewrite mode, where the input is a
    draft and must point at the answer ("добавь в текст…", "add that…"); anything with content of its own → new topic."""
    if not turns(previous):
        return False
    text = " ".join((request or "").split())
    words = _words(text)
    if not words:
        return False
    rest = [w for w in _words(MODIFIER.sub(" ", text)) if w not in FILLER and len(w) > 2]
    if MODIFIER.search(text) and len(words) <= MAX_MODIFIER_WORDS and not rest:
        return True
    start = 0
    while start < len(words) - 1 and words[start] in LEAD:
        start += 1
    if EDIT.match(" ".join(words[start:])) and len(words) <= MAX_EDIT_WORDS:
        return mode != "rewrite" or bool(REFERENCE.search(" ".join(words[start + 1:start + 4])))
    return False


def _clean(text):
    import writer
    return writer.clean(text)


def note_for(previous):
    """Earlier turns as context for a new topic: for consistency only, never content to reuse."""
    previous = turns(previous)
    if not previous:
        return ""
    cut = lambda t: " ".join(_clean(t).split())[:NOTE_CHARS]
    lines = "\n".join(f"- they asked: «{cut(p['request'])}» → you wrote: «{cut(p['answer'])}»" for p in previous)
    return ("\n\nEarlier in this chat (context only, for consistency: who it is for, names, register; write about the "
            "NEW request above and never carry over facts from these):\n" + lines)


def with_note(user):
    """Writer.spark's hook: the thread note (if a new-topic answer is being written) appended to the user message."""
    note = NOTE.get()
    if not note:
        return user
    if isinstance(user, str):
        return user + note
    if isinstance(user, list) and user and isinstance(user[0], dict) and user[0].get("type") == "text":
        return [{**user[0], "text": user[0]["text"] + note}] + user[1:]
    return user


def _format_of(mode, format):
    return mode if mode in ("email", "essay") else format


async def revise(writer_, ctx, mode, request, previous, audience, format="message"):
    """The last answer changed as the new request asks → {text, parts, variants, subject?, words?}."""
    import guards
    import series
    import writer as w
    last = turns(previous)[-1]
    format = _format_of(mode, format)
    formal = format in w.FORMAL
    if formal:
        system = writer_.formal_system(ctx, f"{last['request']} {last['answer']}",
                                       kind="essay" if format == "essay" else "email") + guards.PROMPT_RULE
    else:
        format = series.choose(ctx, audience, last["answer"], format)  # a series answer stays a series
        system = w.STYLE_SYSTEM.format(style=ctx.style_text)
    extra = ', "subject": "<its subject line, in the language of the answer>"' if format == "email" else ""
    extra += ', "variants": ["...", ...]' if not formal else ""
    prompt = REVISE.format(request=_clean(last["request"])[:3000] or "(not shown)", answer=_clean(last["answer"])[:6000],
                           instruction=_clean(request)[:1000], format=writer_.format_line(format).strip(),
                           variants=w.VARIANTS if not formal else "", extra=extra)
    essay = format == "essay"
    label = await writer_.spark(system, prompt, "text", writes=not essay, max_tokens=6000 if essay else 3000,
                                timeout=90 if essay else 60)
    limit = w.FORMAT_WORDS.get(format, 40) * 2
    text, parts = w.shape(w.clip(_clean(label["text"]), limit), format)
    variants = label.get("variants") if isinstance(label.get("variants"), list) else []
    variants = [w.shape(w.clip(_clean(v), limit), format)[0] for v in variants if isinstance(v, str) and _clean(v)]
    out = {"text": text, "parts": parts, "format": format,
           "variants": [v for v in dict.fromkeys(variants) if v != text][:w.VARIANT_COUNT]}
    if format == "email":
        out["subject"] = _clean(str(label.get("subject") or "")) or None
    if essay:
        out["words"] = len(text.split())
    return out


def as_styled(out, audience):
    """The /rewrite and /compose shape."""
    return {"text": out["text"], "parts": out["parts"], "candidates": [out["text"]] + out["variants"],
            "styled": False, "audiences": [audience]}


def as_chat(out, mode, audience):
    """The /chat shape (with a subject for email, and the essay's fields for essay)."""
    result = {"text": out["text"], "parts": out["parts"], "alternatives": out["variants"][:2], "audience": audience,
              "audiences": [audience], "learned": None}
    if mode == "email":
        result["subject"] = out.get("subject")
    if mode == "essay":
        result.update(outline=[], questions=[], words=out.get("words", len(out["text"].split())), cliches=[])
    return result


def as_replies(out):
    """The /reply shape: the revised answer first, then its variants."""
    return [{"intent": "other", "tone": "neutral", "thought": "revised: the last answer, as asked", "styled": False,
             "text": text, "parts": parts}
            for text, parts in [(out["text"], out["parts"])] + [(v, [v]) for v in out["variants"][:2]]]


async def respond(writer_, ctx, mode, request, previous, audience, format, run, shape="chat"):
    """The route's answer with the thread in mind. Returns (result, format used): a refinement is the last answer
    revised (`shape` = "styled" | "chat" | "replies"); otherwise `run()` (the route's own call), with NOTE set."""
    previous = turns(previous)
    if previous and is_refinement(request, previous, mode):
        out = await revise(writer_, ctx, mode, request, previous, audience, format)
        if shape == "styled":
            return as_styled(out, audience), out["format"]
        if shape == "replies":
            return {"replies": as_replies(out)}, out["format"]
        return as_chat(out, mode, audience), out["format"]
    token = NOTE.set(note_for(previous))
    try:
        return await run(), format
    finally:
        NOTE.reset(token)
