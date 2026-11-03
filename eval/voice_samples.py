"""Voice notes before and after the transcription changes: word error rate (WER) of Muse Voice Transcribe and of the
Muse Spark fix pass, on English and Russian samples whose real text is known. Run it on your Mac with the keys in .env
(the cloud session that wrote it had no keys).

Samples live in data/voice_samples/ (gitignored: your own voice is personal data): <name>.wav + <name>.txt (what was
really said). Make them either way:

  python3 eval/voice_samples.py make                 # macOS `say`: the made-up sentences below, English + Russian voices
  python3 eval/voice_samples.py make --print         # just print the sentences, to read them aloud yourself

To use your own voice (the real test: accented English is where it goes wrong), record each sentence in Voice Memos,
then convert:  afconvert -f WAVE -d LEI16@24000 -c 1 memo.m4a data/voice_samples/en_01_me.wav  and copy the sentence
into data/voice_samples/en_01_me.txt. Any WAV works (44.1/48 kHz, stereo): the server's prepare_wav converts it.

  .venv/bin/python eval/voice_samples.py run [--only en] [--show]

Four steps per sample, each scored against the real text (WER: word edits / words said; case, punctuation and
apostrophes ignored):
  asr_before   the WAV as the old app sent it (16 kHz), no hints: Muse Voice Transcribe as it was
  fix_before   + the old fix pass (one prompt for every language, the old guard): what the app showed before
  asr_after    the 24 kHz WAV through prepare_wav (silence trimmed, level raised) + languageBias for English
  fix_after    + the new fix pass (the English prompt for English notes, the new guard): what the app shows now
The iPhone's on-device second hearing can't run here; it only adds to fix_after on the phone.

Only aggregated numbers are written (eval/results/voice_samples.json); transcripts stay in the terminal (--show).
"""

import argparse
import asyncio
import io
import json
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline"), str(ROOT / "eval")]

import writer  # noqa: E402

SAMPLES = ROOT / "data" / "voice_samples"
RESULTS = ROOT / "eval" / "results" / "voice_samples.json"

# Made-up sentences (nobody's real messages) with what trips recognizers: sound-alike words, names, apostrophes,
# numbers, English inside Russian.
SENTENCES = {
    "en": [
        "Tell Aigerim I'll be there at four, their car broke down near Dostyk Plaza.",
        "Can you pick up the kids after school? I'm stuck in a meeting until six.",
        "I don't know whether we should meet there or at your place, it's up to you.",
        "Write me when you're free, I want to hear about the trip to Almaty.",
        "We'll need two more chairs for the party, could you buy them on the way?",
        "Sorry I missed your call, my phone was on silent the whole morning.",
        "Let's move the deadline to Friday, the report isn't ready yet.",
        "Happy birthday Daniyar! Hope this year brings you everything you wanted.",
        "I'm gonna be a bit late, the traffic on Abay avenue is crazy right now.",
        "Could you send me the photos from yesterday? The one with the dog was great.",
        "No worries, I already paid for the tickets, you can give me the money later.",
        "Their flight lands at eight forty, so we should leave the house by eight.",
    ],
    "ru": [
        "Скажи Айгерим, что я буду на Абая в девять.",
        "Купи, пожалуйста, хлеб и молоко по дороге домой.",
        "Я опоздаю минут на двадцать, тут пробка на Аль-Фараби.",
        "Давай перенесём meeting на пятницу, отчёт ещё не готов.",
        "Мам, я доехал, всё хорошо, позвоню вечером.",
        "Ты видел фотки с субботы? Там Данияр смешной получился.",
    ],
}
VOICES = {"en": ["Samantha", "Daniel"], "ru": ["Milena"]}

# The fix pass as it was before (one prompt for every language, kept if ≥70% of the words stayed).
OLD_FIX = """You fix speech-recognition mistakes in a voice note, nothing else.
Fix: repeated or broken words ("на бая. Абая" → "на Абая"), punctuation, capital letters of names and places.
Keep every word the speaker said, in their language and order; never rephrase, shorten, translate, answer or add anything.
Return JSON only: {"text": "<the fixed voice note>"}."""

try:  # python.org builds on macOS ship without root certificates
    import certifi
    VERIFY = certifi.where()
except ImportError:
    VERIFY = True


def words(text):
    return re.findall(r"\w+", (text or "").replace("'", "").replace("’", "").casefold())


def edits(reference, hypothesis):
    """Word-level Levenshtein distance."""
    row = list(range(len(hypothesis) + 1))
    for i, ref in enumerate(reference, 1):
        previous, row[0] = row[0], i
        for j, hyp in enumerate(hypothesis, 1):
            previous, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, previous + (ref != hyp))
    return row[-1]


def resample16(wav):
    """The WAV as the old app recorded it: 16 kHz mono (prepare_wav's resampler, then a plain 3:2 decimation)."""
    import numpy as np
    with wave.open(io.BytesIO(wav)) as source:
        channels, rate = source.getnchannels(), source.getframerate()
        samples = np.frombuffer(source.readframes(source.getnframes()), "<i2").astype(np.float32)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if rate != 16_000:
        smooth = max(1, round(rate / 16_000))
        samples = np.convolve(samples, np.ones(smooth) / smooth, mode="same") if rate > 16_000 else samples
        samples = np.interp(np.linspace(0, len(samples) - 1, int(len(samples) * 16_000 / rate)),
                            np.arange(len(samples)), samples)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as sink:
        sink.setnchannels(1)
        sink.setsampwidth(2)
        sink.setframerate(16_000)
        sink.writeframes(np.clip(samples, -32768, 32767).astype("<i2").tobytes())
    return buffer.getvalue()


def make(print_only):
    if print_only:
        for lang, sentences in SENTENCES.items():
            for n, sentence in enumerate(sentences, 1):
                print(f"{lang}_{n:02d}  {sentence}")
        return
    if not shutil.which("say"):
        sys.exit("`say` is macOS only: record the sentences yourself (make --print) and convert them with afconvert")
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for lang, sentences in SENTENCES.items():
        for voice in VOICES[lang]:
            for n, sentence in enumerate(sentences, 1):
                name = SAMPLES / f"{lang}_{n:02d}_{voice.lower()}"
                result = subprocess.run(["say", "-v", voice, "--data-format=LEI16@24000", "-o", f"{name}.wav",
                                         sentence], capture_output=True)
                if result.returncode:
                    print(f"voice {voice} is missing (System Settings → Accessibility → Spoken Content): skipped")
                    break
                name.with_suffix(".txt").write_text(sentence + "\n", encoding="utf-8")
    print(f"samples in {SAMPLES}")


async def old_fix(w, text):
    """The production fix pass before this change, verbatim."""
    if len(text.split()) < 4:
        return text
    try:
        fixed = writer.clean(str((await w.spark(OLD_FIX, text, "text", max_tokens=2000, timeout=15))["text"]))
    except Exception:
        return text
    said, got = set(re.findall(r"\w+", text.casefold())), set(re.findall(r"\w+", fixed.casefold()))
    if not fixed or not 0.7 <= len(fixed) / len(text) <= 1.3 or len(said & got) < 0.7 * len(said):
        return text
    return fixed


async def run(only, show):
    import httpx
    env = dict(line.strip().split("=", 1) for line in (ROOT / ".env").open() if "=" in line and not line.startswith("#"))
    paths = sorted(p for p in SAMPLES.glob("*.wav") if p.with_suffix(".txt").exists())
    rows = []
    for path in paths:
        real = path.with_suffix(".txt").read_text(encoding="utf-8").strip()
        lang = writer.transcript_language(real)
        if only in (None, lang):
            rows.append((path, real, lang))
    if not rows:
        sys.exit(f"no samples in {SAMPLES}: run `python3 eval/voice_samples.py make` first")
    steps = ("asr_before", "fix_before", "asr_after", "fix_after")
    totals = {lang: {step: [0, 0] for step in steps} for lang in ("en", "ru")}
    async with httpx.AsyncClient(verify=VERIFY, timeout=60) as client:
        w = writer.Writer(client, "http://unused", "", None, env["META_API_KEY"], gpu="off",
                          fallback_key=env.get("BASETEN_API_KEY"))
        gate = asyncio.Semaphore(4)

        async def one(path, real, lang):
            audio = path.read_bytes()
            hints = {"languageBias": [writer.ASR_LANGUAGES[lang]]} if lang in writer.ASR_LANGUAGES else {}

            async def heard(wav, extra):
                try:
                    return writer.tidy_transcript(await w.recognize(wav, extra))
                except writer.Unavailable:
                    print(f"{path.name}: Muse Voice Transcribe did not answer (counted as empty)")
                    return ""
            async with gate:
                before = await heard(resample16(audio), {})
                fixed_before = await old_fix(w, before)
                after = await heard(writer.prepare_wav(audio), hints)
                fixed_after = await w.fix_transcript(after, language=lang)
            return path, real, lang, dict(zip(steps, (before, fixed_before, after, fixed_after)))

        for path, real, lang, out in await asyncio.gather(*(one(*row) for row in rows)):
            reference = words(real)
            for step, text in out.items():
                totals[lang][step][0] += edits(reference, words(text))
                totals[lang][step][1] += len(reference)
            if show:
                print(f"\n{path.name}\n  real        {real}")
                for step, text in out.items():
                    print(f"  {step:<11} {text}   (WER {edits(reference, words(text)) / max(1, len(reference)):.2f})")
    result = {"samples": {lang: sum(1 for r in rows if r[2] == lang) for lang in ("en", "ru")},
              "wer": {lang: {step: round(e / n, 3) for step, (e, n) in totals[lang].items()}
                      for lang in ("en", "ru") if totals[lang]["asr_before"][1]}}
    print("\nWER (lower is better)")
    for lang, scores in result["wer"].items():
        print(f"  {lang} ({result['samples'][lang]} samples): " + "  ".join(f"{s} {v:.3f}" for s, v in scores.items()))
    RESULTS.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"written: {RESULTS.relative_to(ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    make_parser = sub.add_parser("make", help="make samples with macOS `say` (or --print the sentences)")
    make_parser.add_argument("--print", action="store_true", dest="print_only")
    run_parser = sub.add_parser("run", help="transcribe every sample before and after, score WER")
    run_parser.add_argument("--only", choices=["en", "ru"])
    run_parser.add_argument("--show", action="store_true", help="print each transcript (stays in the terminal)")
    args = parser.parse_args()
    if args.command == "make":
        make(args.print_only)
    else:
        asyncio.run(run(args.only, args.show))
