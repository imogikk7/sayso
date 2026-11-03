"""Official messages and emails on the real Muse Spark: prints a few samples (Russian and English, Official and Email,
vague and specific) with the checks of serving/writer.py, to see by eye that each answer is in one language, has one
sign-off and adds nothing. Made-up requests only; nothing is saved.

Needs META_API_KEY (and BASETEN_API_KEY for Muse Spark Open) in .env and the style's data in data/ (the main style by
default). Usage:
  .venv/bin/python eval/official_samples.py [--style main] [--writer open|meta] [--only official|email]
"""

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline"), str(ROOT / "eval")]

import httpx  # noqa: E402

import writer  # noqa: E402

try:  # python.org builds on macOS ship without root certificates
    import certifi
    VERIFY = certifi.where()
except ImportError:
    VERIFY = True

# (format, audience chip, request): Russian and English, vague and specific. The first one is the Nov 3 bug report.
SAMPLES = [
    ("official", "friends", "Спроси у профессора, будет ли керф по физике."),
    ("official", "friends", "напиши преподу что я заболел"),
    ("official", "family", "Напиши куратору, что я не смогу прийти на пару в четверг 14 ноября, потому что у меня "
                           "запись к врачу на 10:00, и спроси, можно ли сдать лабу в пятницу."),
    ("official", "friends", "ask the professor if the midterm is open book"),
    ("official", "friends", "tell my manager I'll be 15 minutes late to the 10am standup because of a dentist "
                            "appointment"),
    ("official", "friends", "Напиши профессору на английском, что я пропущу семинар"),
    ("email", None, "спроси у декана про стипендию"),
    ("email", None, "Напиши преподавателю, что прикрепляю курсовую по истории, и попроси подтвердить, что файл "
                    "открывается. Срок сдачи был вчера, я сдаю на день позже из-за болезни, справка есть."),
    ("email", None, "ask the professor about the internship"),
    ("email", None, "Write to Professor Lee that I attached my lab report for week 6 and ask whether the graphs "
                    "should be in the appendix or in the main text."),
]


async def main(style, who, only):
    env = dict(line.strip().split("=", 1) for line in (ROOT / ".env").open() if "=" in line and not line.startswith("#"))
    async with httpx.AsyncClient(verify=VERIFY, timeout=90) as client:
        w = writer.Writer(client, "http://unused", "", None, env["META_API_KEY"], gpu="off",
                          fallback_key=env.get("BASETEN_API_KEY"), writer=who)
        ctx = w.context(style)
        for format, audience, request in SAMPLES:
            if only and format != only:
                continue
            lang = writer.language(request)
            try:
                if format == "email":
                    out = await w.chat(ctx, "email", request, "elder_informal")
                    shown = [f"Subject: {out['subject']}\n{out['text']}"]
                    checked = f"{out['subject'] or ''}\n{out['text']}"
                else:
                    out = await w.chat(ctx, "write", request, audience, format=format)
                    shown = [out["text"]] + out["alternatives"]
                    checked = out["text"]
            except writer.Unavailable as error:
                print(f"\n=== {format} · {request}\n!! {error.detail}")
                continue
            print(f"\n=== {format} · chip {audience or '-'} · language {lang} · audiences {out['audiences']}")
            print(f">>> {request}")
            for i, text in enumerate(shown):
                problems = writer.formal_problems(text if i else checked, lang, request)
                print(("--- answer" if not i else f"--- alternative {i}") + (f"  [!] {problems}" if problems else "  [ok]"))
                print(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", default="main")
    parser.add_argument("--writer", default="open", choices=["open", "meta"])
    parser.add_argument("--only", choices=["official", "email"])
    args = parser.parse_args()
    asyncio.run(main(args.style, args.writer, args.only))
