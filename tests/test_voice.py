"""Voice notes (serving/writer.py): language detection, the English fix prompt, the guard that keeps the speaker's
words, the hints sent to Muse Voice Transcribe (languageBias, keywords), the iPhone's second hearing, and the audio
clean-up before recognition. Fake Spark and a fake HTTP client: no network, made-up texts only.

Usage: python3 -m pytest tests/test_voice.py
"""

import io
import json
import math
import struct
import sys
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "serving"), str(ROOT / "pipeline"), str(ROOT / "tests"), str(ROOT / "eval")]

import voice_samples  # noqa: E402
import writer  # noqa: E402
from test_writer_fakes import FakeResponse, WriterTestCase, run  # noqa: E402
from writer import Unavailable  # noqa: E402

try:
    import numpy  # noqa: F401
except ImportError:  # prepare_wav needs numpy (it comes with transformers in the server image)
    numpy = None


class Spark:
    """Stands in for Writer.spark: records the calls, answers {"text": ...} in turn (the last one repeats)."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    async def __call__(self, system, user, key, **kwargs):
        self.calls.append({"system": system, "user": user})
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return {"text": answer}


class Http:
    """Muse Voice Transcribe, faked: answers the given (status, transcript) in turn."""

    def __init__(self, *answers, error=None):
        self.answers, self.error, self.posts = list(answers) or [(200, "")], error, []

    async def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if self.error:
            raise self.error
        status, transcript = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        return FakeResponse(status, {"transcript": transcript})

    def request(self, n=0):
        return json.loads(self.posts[n][1]["files"]["request"][1])


def wav(seconds_silence=1.0, seconds_tone=1.0, rate=16_000, amplitude=3000, channels=1):
    """Silence, a quiet 220 Hz tone (stands in for speech), silence."""
    samples = [0] * int(rate * seconds_silence)
    samples += [int(amplitude * math.sin(2 * math.pi * 220 * i / rate)) for i in range(int(rate * seconds_tone))]
    samples += [0] * int(rate * seconds_silence)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as sink:
        sink.setnchannels(channels)
        sink.setsampwidth(2)
        sink.setframerate(rate)
        sink.writeframes(b"".join(struct.pack("<h", s) * channels for s in samples))
    return buffer.getvalue()


def read(data):
    with wave.open(io.BytesIO(data)) as source:
        frames = source.readframes(source.getnframes())
        return source.getnchannels(), source.getframerate(), list(struct.unpack(f"<{len(frames) // 2}h", frames))


class Language(unittest.TestCase):
    def test_by_letters(self):
        self.assertEqual(writer.transcript_language("Tell him I'll be there at nine"), "en")
        self.assertEqual(writer.transcript_language("скажи маме что буду в 9"), "ru")
        self.assertEqual(writer.transcript_language("скажи что meeting перенесли на завтра"), "ru")
        self.assertEqual(writer.transcript_language("сәлем, қалайсың"), "ru")  # Kazakh goes with the Russian prompt
        self.assertEqual(writer.transcript_language("ok, I'll call мама later"), "en")

    def test_no_letters_falls_back_to_the_app_language(self):
        self.assertEqual(writer.transcript_language("9 10", "en"), "en")
        self.assertEqual(writer.transcript_language("", "ru"), "ru")
        self.assertEqual(writer.transcript_language("", None), "ru")

    def test_words_ignore_case_and_apostrophes(self):
        self.assertEqual(writer.transcript_words("Don't wait, I'm OK"), {"dont", "wait", "im", "ok"})

    def test_names_skip_sentence_starts(self):
        self.assertEqual(writer.names_in("Tell Aigerim we meet at Dostyk Plaza. Then call Tom."),
                         ["Aigerim", "Dostyk", "Plaza", "Tom"])
        self.assertEqual(writer.names_in("Скажи Мире, что я в Алматы. Ок"), ["Мире", "Алматы"])
        self.assertEqual(writer.names_in("I think I can"), [])
        self.assertEqual(writer.names_in(""), [])


class FixPrompt(WriterTestCase):
    def use(self, *answers):
        self.writer.spark = Spark(*answers)
        return self.writer.spark

    def test_english_note_gets_the_english_prompt(self):
        spark = self.use("I'll be there in ten minutes, wait for me.")
        out = run(self.writer.fix_transcript("ill be their in ten minutes wait for me"))
        self.assertIs(spark.calls[0]["system"], writer.TRANSCRIPT_FIX_EN)
        self.assertEqual(out, "I'll be there in ten minutes, wait for me.")

    def test_russian_note_gets_the_russian_prompt(self):
        spark = self.use("Скажи маме, что буду на Абая в девять.")
        out = run(self.writer.fix_transcript("скажи маме что буду на бая. Абая в девять"))
        self.assertIs(spark.calls[0]["system"], writer.TRANSCRIPT_FIX)
        self.assertEqual(out, "Скажи маме, что буду на Абая в девять.")

    def test_the_language_comes_from_the_transcript_not_the_app(self):
        spark = self.use("I'm running late, sorry.")
        run(self.writer.fix_transcript("im running late sorry", language="ru"))
        self.assertIs(spark.calls[0]["system"], writer.TRANSCRIPT_FIX_EN)

    def test_context_is_given(self):
        spark = self.use("Tell Aigerim I'll be late.")
        run(self.writer.fix_transcript("tell I gearim ill be late", mode="rewrite", audience="friends",
                                       names=["Aigerim"], heard="Tell Aigerim I'll be late"))
        user = spark.calls[0]["user"]
        self.assertIn("the user's own draft of a chat message, for friends.", user)
        self.assertIn("Known names: Aigerim", user)
        self.assertIn("A second recognizer heard", user)
        self.assertIn("Tell Aigerim I'll be late", user)
        self.assertTrue(user.endswith("Voice note: tell I gearim ill be late"))

    def test_without_context_the_note_goes_alone(self):
        spark = self.use("Call me when you're free, ok?")
        run(self.writer.fix_transcript("call me when your free ok"))
        self.assertEqual(spark.calls[0]["user"], "call me when your free ok")

    def test_short_notes_are_not_sent(self):
        spark = self.use("x")
        self.assertEqual(run(self.writer.fix_transcript("ok see you")), "ok see you")
        self.assertEqual(spark.calls, [])
        run(self.writer.fix_transcript("ok see you", heard="ok, see you"))  # with a second hearing it's worth it
        self.assertEqual(len(spark.calls), 1)

    def test_spark_failing_keeps_the_transcript(self):
        self.use(Unavailable(502, "x"))
        self.assertEqual(run(self.writer.fix_transcript("call me when your free ok")), "call me when your free ok")


class Guard(WriterTestCase):
    def fix(self, answer, text, **kwargs):
        self.writer.spark = Spark(answer)
        return run(self.writer.fix_transcript(text, **kwargs))

    def test_a_rephrased_note_is_dropped(self):
        text = "can you send me the photos from yesterday please"
        self.assertEqual(self.fix("Could you share yesterday's pictures with me?", text), text)

    def test_an_answer_instead_of_a_fix_is_dropped(self):
        text = "what time does the shop close today"
        self.assertEqual(self.fix("The shop usually closes at 9 pm today.", text), text)

    def test_a_translation_is_dropped(self):
        text = "скажи что я опоздаю минут на двадцать"
        self.assertEqual(self.fix("Tell them I'll be about twenty minutes late.", text), text)

    def test_much_longer_or_shorter_is_dropped(self):
        text = "I will call you back in five minutes ok"
        self.assertEqual(self.fix("I will call.", text), text)
        self.assertEqual(self.fix(text + " and then we can talk about everything that happened today", text), text)

    def test_sound_alike_fixes_pass(self):
        out = self.fix("Your right, they're not coming, so let's meet there.",
                       "your right there not coming so lets meet their")
        self.assertEqual(out, "Your right, they're not coming, so let's meet there.")

    def test_words_from_the_second_hearing_count_as_said(self):
        # Muse misheard three words; the iPhone heard them right, and the fix takes them from there.
        out = self.fix("Can you pick up the kids at four?", "can you pick at the kits at for",
                       heard="Can you pick up the kids at four")
        self.assertEqual(out, "Can you pick up the kids at four?")

    def test_the_same_fix_without_the_second_hearing_is_dropped(self):
        text = "can you pick at the kits at for"
        self.assertEqual(self.fix("Can you pick up the kids at four?", text), text)


class Transcribe(WriterTestCase):
    def setUp(self):
        super().setUp()
        self.writer.meta_key = "k"
        self.writer.spark = Spark("I'll be there at nine, wait for me.")

    def test_english_sends_a_language_bias(self):
        self.writer.client = Http((200, "ill be there at nine wait for me"))
        out = run(self.writer.transcribe(b"RIFF", language="en"))
        self.assertEqual(self.writer.client.request()["languageBias"], ["English"])
        self.assertEqual(out, "I'll be there at nine, wait for me.")

    def test_russian_has_no_language_bias(self):  # Russian isn't on Muse Voice Transcribe's list
        self.writer.client = Http((200, "буду в девять"))
        run(self.writer.transcribe(b"RIFF", language="ru"))
        self.assertNotIn("languageBias", self.writer.client.request())
        run(self.writer.transcribe(b"RIFF"))
        self.assertEqual(set(self.writer.client.request(1)), {"mode", "model", "audioEncoding"})

    def test_names_from_the_context_become_keywords(self):
        self.writer.client = Http((200, "tell I gearim ill be late"))
        run(self.writer.transcribe(b"RIFF", context="Hey, tell Aigerim and Tom that the place is Dostyk."))
        self.assertEqual(self.writer.client.request()["keywords"], ["Aigerim", "Tom", "Dostyk"])

    def test_hints_refused_are_retried_without_them(self):
        self.writer.client = Http((400, None), (200, "ill be there at nine wait for me"))
        out = run(self.writer.transcribe(b"RIFF", language="en"))
        self.assertEqual(len(self.writer.client.posts), 2)
        self.assertIn("languageBias", self.writer.client.request(0))
        self.assertNotIn("languageBias", self.writer.client.request(1))
        self.assertEqual(out, "I'll be there at nine, wait for me.")

    def test_a_server_error_is_not_retried(self):
        self.writer.client = Http((500, None))
        with self.assertRaises(Unavailable):
            run(self.writer.transcribe(b"RIFF", language="en"))
        self.assertEqual(len(self.writer.client.posts), 1)

    def test_the_iphone_hearing_answers_when_muse_fails(self):
        self.writer.client = Http(error=TimeoutError())
        out = run(self.writer.transcribe(b"RIFF", language="en", heard="Ill be there at nine wait for me"))
        self.assertEqual(out, "I'll be there at nine, wait for me.")

    def test_the_iphone_hearing_in_the_wrong_language_is_ignored(self):
        self.writer.client = Http((200, "ill be there at nine wait for me"))
        run(self.writer.transcribe(b"RIFF", heard="ил би зэа эт найн"))
        self.assertNotIn("second recognizer", self.writer.spark.calls[0]["user"])

    def test_the_iphone_hearing_goes_to_the_fix_pass(self):
        self.writer.client = Http((200, "ill be their at nine wait for me"))
        run(self.writer.transcribe(b"RIFF", mode="write", heard="I'll be there at nine wait for me"))
        user = self.writer.spark.calls[0]["user"]
        self.assertIn("A second recognizer heard", user)
        self.assertIn("an instruction to SaySo", user)


@unittest.skipIf(numpy is None, "numpy is not installed")
class PrepareWav(unittest.TestCase):
    def test_silence_is_trimmed_and_quiet_speech_raised(self):
        channels, rate, samples = read(writer.prepare_wav(wav(seconds_silence=1.0, seconds_tone=1.0, amplitude=3000)))
        self.assertEqual((channels, rate), (1, 16_000))
        self.assertLess(len(samples) / rate, 1.8)  # 3 s in, about 1 s of tone + 2 × 0.3 s kept
        self.assertGreater(len(samples) / rate, 1.4)
        self.assertGreater(max(samples), 20_000)  # 3000 → about -3 dBFS

    def test_a_note_without_pauses_is_still_raised(self):
        channels, rate, samples = read(writer.prepare_wav(wav(seconds_silence=0.02, seconds_tone=5)))
        self.assertGreater(len(samples) / rate, 4.9)
        self.assertGreater(max(samples), 20_000)

    def test_the_gain_is_capped(self):  # a whisper or room noise isn't blown up into hiss
        _, _, samples = read(writer.prepare_wav(wav(amplitude=800)))
        self.assertLessEqual(max(samples), 8_000)

    def test_loud_speech_is_not_made_quieter(self):
        _, _, samples = read(writer.prepare_wav(wav(amplitude=30_000)))
        self.assertGreater(max(samples), 29_000)

    def test_stereo_48k_becomes_mono_24k(self):
        channels, rate, samples = read(writer.prepare_wav(wav(rate=48_000, channels=2)))
        self.assertEqual((channels, rate), (1, 24_000))
        self.assertGreater(len(samples), 24_000)

    def test_what_it_cannot_read_goes_out_unchanged(self):
        for data in (b"RIFF....WAVE", b"", wav(seconds_silence=1, seconds_tone=0)):
            self.assertEqual(writer.prepare_wav(data), data)


class WordErrorRate(unittest.TestCase):
    def test_edits(self):
        real = voice_samples.words("Tell Aigerim I'll be there at four.")
        self.assertEqual(voice_samples.edits(real, voice_samples.words("tell aigerim ill be there at four")), 0)
        self.assertEqual(voice_samples.edits(real, voice_samples.words("tell I gear rim ill be their at for")), 5)
        self.assertEqual(voice_samples.edits(real, []), len(real))

    def test_the_sentences_are_scored_in_their_language(self):
        for lang, sentences in voice_samples.SENTENCES.items():
            self.assertEqual({writer.transcript_language(s) for s in sentences}, {lang})


if __name__ == "__main__":
    unittest.main()
