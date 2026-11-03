"""Guards on everything SaySo writes: no template placeholders, no self-introduction the user didn't ask for, no
remarks about the request itself.

Why: the user's own emails are stored with other people's names replaced by "[Name]" (serving/documents.py), and the
model copied that ("Уважаемая команда [Name]"); their formal writing also mentions their job, and the model put it into
an email the user never asked to introduce themselves in. The formal profile is for tone only: it must never inject
facts about the user.

  for_prompt(text)            the user's formal writing as shown to the model: placeholders and self-introductions cut
  problems(text, request)     what is wrong with an answer: ["placeholder", "introduction", "meta"]
  fix(text, request, format)  the answer with those removed (line structure kept: series, emails, essays)
  apply(result, request, ...) one route result: the main answer (and each reply) fixed, alternatives that break a rule
                              dropped, the subject cleaned
"""

import re

PROMPT_RULE = ("\nNever write template placeholders like [Name], [Your name], <company> or (date): use what the request "
               "gives or leave it out. Never introduce the user (their name, job, role, school or organization) unless "
               "the request asks for it: their formal writing above shows how they write, not facts to repeat.")

# [Name], [Your name], [Компания], <name>, <your company>, {name}, (Ваше имя), (Name): a slot left for someone to fill.
PLACEHOLDER = re.compile(
    r"\[[^\[\]\n]{1,40}\]|<(?!3)[^<>\n]{1,40}>|\{[^{}\n]{1,40}\}|"
    r"\((?:ваш[еаи]? |your )?(?:имя|фамилия|фио|name|full name|компания|организация|company|должность|position|"
    r"title|role|дата|date|номер|number|телефон|phone|email|адрес|address)[^()\n]{0,20}\)", re.I)

TRAILING = re.compile(r",\s*(?:" + PLACEHOLDER.pattern + r")\s*$", re.I)

# A sentence where the user presents themself: name, job, role, organization.
INTRODUCTION = re.compile(
    r"\bменя зовут\b|\bмоё имя\b|\bмое имя\b|\bя являюсь\b|\bявляюсь (?:сотрудни|студент|менеджер|руководител|"
    r"специалист|разработчик|представител|основател|директор)|\bработаю (?:в|на|как|в качестве)\b|"
    r"\bв должности\b|\bзанимаю должность\b|\bмоя должность\b|\bпишу (?:вам )?(?:как|в качестве)\b|"
    r"\bобращаюсь (?:к вам )?(?:как|в качестве)\b|\bот лица (?:компании|команды|организации)\b|"
    r"\bя\s*[—–-]?\s*(?:студент\w*|сотрудни\w*|менеджер\w*|разработчи\w*|инженер\w*|преподавател\w*|учител\w*|"
    r"директор\w*|руководител\w*|специалист\w*|аналитик\w*|дизайнер\w*|основател\w*|программист\w*|"
    r"маркетолог\w*|бухгалтер\w*|юрист\w*|врач\w*|магистрант\w*|аспирант\w*)\b|"
    r"\bmy name is\b|\bi am (?:a|an|the) [\w -]{0,40}\b(?:at|of|from|in)\b|\bi'm (?:a|an|the) [\w -]{0,40}\b(?:at|of|"
    r"from|in)\b|\bi work (?:as|at|for|in)\b|\bi(?:'m| am) writing (?:to you )?as\b|\bas (?:a|an|the) (?:student|"
    r"manager|developer|engineer|teacher|director|founder|lead|head|specialist|analyst|designer|employee|member)\b|"
    r"\bon behalf of (?:the |our )?(?:company|team|organi[sz]ation)\b", re.I)
# The request asks the user to be presented (or is a text that is about them by nature).
ASKS_INTRO = re.compile(
    r"представ|познаком|кто я|о себе|обо мне|моё имя|мое имя|меня зовут|подпиш|подпис|резюме|сопроводит|"
    r"мотивационн|автобиограф|introduc|about me|about myself|who i am|my name|sign (?:it|with)|signature|"
    r"cover letter|resume|résumé|\bcv\b|\bbio\b|personal statement|motivation letter|кто ты|кто вы|"
    r"как (?:тебя|вас) зовут|who (?:you are|the user is|are you)|your name|their name", re.I)
# Remarks about the request instead of the text ("Детали обращения не были указаны", "No details were provided").
META = re.compile(
    r"детал\w* (?:обращения |запроса |письма )?не (?:были )?(?:указан|уточнен|предоставлен)|"
    r"(?:информаци\w*|подробност\w*) не (?:была |были )?(?:указан|предоставлен)|"
    r"\b(?:no |the )?details (?:were|are|have been) (?:not )?(?:provided|given|specified)\b|"
    r"\byou (?:didn't|did not) (?:specify|provide|mention)\b|\bas an ai\b|как (?:ии|ai|языковая модель)", re.I)

SIGN_OFF = re.compile(r"^\s*(?:с уважением|с наилучшими пожеланиями|всего доброго|best(?: regards| wishes)?|"
                      r"kind regards|regards|sincerely|yours(?: sincerely| truly)?|respectfully|cheers|құрметпен)"
                      r"\s*[,.!]?\s*$", re.I)
PS = re.compile(r"^\s*(?:p\.?\s?s\.?|п\.?\s?с\.?)", re.I)
SENTENCE = re.compile(r"(?<=[.!?…])\s+")
WORD = re.compile(r"\w{4,}", re.U)
FORMAL_FORMATS = {"official", "email", "essay"}


def _allowed(text, request):
    """The placeholders the request itself contains (a draft with "[link]" keeps it)."""
    return {m.group(0).casefold() for m in PLACEHOLDER.finditer(request or "")}


def placeholders(text, request=""):
    allowed = _allowed(text, request)
    return [m.group(0) for m in PLACEHOLDER.finditer(text or "") if m.group(0).casefold() not in allowed]


def _stems(text):
    return {w[:4] for w in WORD.findall((text or "").casefold())}


def introduces(sentence, request="", format="message"):
    """The sentence presents the user, and the request neither asked for that nor gave those facts (half of them; in
    an essay, which speaks as "I" from the user's notes, any of them)."""
    if not INTRODUCTION.search(sentence or "") or ASKS_INTRO.search(request or ""):
        return False
    facts = _stems(INTRODUCTION.sub(" ", sentence))
    given = len(facts & _stems(request))
    return not facts or (given == 0 if format == "essay" else given < 0.5 * len(facts))


def _sentences(text):
    return [s for line in (text or "").splitlines() for s in SENTENCE.split(line) if s.strip()]


def problems(text, request="", format="message"):
    found = []
    if placeholders(text, request):
        found.append("placeholder")
    if any(introduces(s, request, format) for s in _sentences(text)):
        found.append("introduction")
    if any(META.search(s) and not META.search(request or "") for s in _sentences(text)):
        found.append("meta")
    return found


def _tidy(line):
    line = re.sub(r"[ \t]{2,}", " ", line)
    line = re.sub(r"\s+([,.!?;:])", r"\1", line)
    line = re.sub(r",\s*([,.!?;:])", r"\1", line)  # "Здравствуйте, !" → "Здравствуйте!"
    line = re.sub(r"^[\s,;:]+", "", line)  # "[Name], добрый день" → "добрый день" (list dashes stay)
    line = re.sub(r"^(dear|уважаем\w*)([,!:]?)$", lambda m: "Hello," if m.group(1).lower() == "dear" else "Здравствуйте,",
                  line.strip(), flags=re.I)  # "Dear [Name]," with the name gone
    return line.strip()


def _fix_line(line, request, allowed, format="message"):
    kept = []
    for sentence in SENTENCE.split(line):
        if introduces(sentence, request, format) or (META.search(sentence) and not META.search(request or "")):
            continue
        end = TRAILING.search(sentence)  # "Спасибо, (Ваше имя)": the comma before a closing slot goes with it
        if end and PLACEHOLDER.search(end.group(0)).group(0).casefold() not in allowed:
            sentence = sentence[:end.start()]
        sentence = PLACEHOLDER.sub(lambda m: m.group(0) if m.group(0).casefold() in allowed else "", sentence)
        sentence = _tidy(sentence)
        if re.search(r"\w", sentence):
            kept.append(sentence)
    return " ".join(kept)


def fix(text, request="", format="message"):
    """The answer with placeholders, unasked self-introductions and remarks about the request removed. Lines (and the
    blank lines of emails and essays) are kept; a line left empty is dropped; in an email or official message, a name
    or role under the sign-off is dropped (the sign-off goes without a name)."""
    if not text:
        return text
    allowed = _allowed(text, request)
    out, signed = [], False
    for line in text.split("\n"):
        if not line.strip():
            out.append("")
            continue
        if signed and format in FORMAL_FORMATS and len(line.split()) <= 6 and not PS.match(line) \
                and not ASKS_INTRO.search(request or ""):
            continue  # "Иван П." / "Project manager, Company" under "С уважением": the sign-off goes without a name
        fixed = _fix_line(line, request, allowed, format)
        if fixed:
            out.append(fixed)
            signed = signed or bool(SIGN_OFF.match(fixed))
    joined = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    return joined


def for_prompt(text):
    """The user's own writing as an example of their voice: no placeholder slots to copy, no facts about them."""
    lines = []
    for line in (text or "").split("\n"):
        kept = [_tidy(PLACEHOLDER.sub("", s)) for s in SENTENCE.split(line) if not INTRODUCTION.search(s)]
        lines.append(" ".join(s for s in kept if re.search(r"\w", s)) if line.strip() else line)
    return "\n".join(lines)


def ok(text, request="", format="message"):
    return bool((text or "").strip()) and not problems(text, request, format)


def apply(result, request="", format="message", parts_of=None):
    """A route result, guarded in place and returned: `text` and every reply fixed (their `parts` rebuilt with
    parts_of(text, format)), `alternatives` / `candidates` that break a rule dropped, `subject` cleaned."""
    parts_of = parts_of or (lambda text, _format: [text])
    if isinstance(result.get("text"), str):
        fixed = fix(result["text"], request, format)
        if fixed != result["text"] or not fixed:
            usable = [a for a in result.get("alternatives") or result.get("candidates") or []
                      if isinstance(a, str) and ok(a, request, format) and a != result["text"]]
            result["text"] = fixed or (usable[0] if usable else result["text"])
            result["parts"] = parts_of(result["text"], format)
    for key in ("alternatives", "candidates"):
        if isinstance(result.get(key), list):
            kept = [a for a in result[key] if isinstance(a, str) and ok(a, request, format)]
            if key == "candidates" and result.get("text"):
                kept = [result["text"]] + [a for a in kept if a != result["text"]]
            result[key] = list(dict.fromkeys(kept))
    if isinstance(result.get("subject"), str):
        result["subject"] = _tidy(PLACEHOLDER.sub("", result["subject"])) or None
    for reply in result.get("replies") or []:
        if isinstance(reply, dict) and isinstance(reply.get("text"), str):
            fixed = fix(reply["text"], request, format)
            if fixed and fixed != reply["text"]:
                reply["text"], reply["parts"] = fixed, parts_of(fixed, format)
    return result
