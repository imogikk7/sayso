"""iOS WhatsApp exports put a narrow no-break space (U+202F) before AM/PM."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import parse_whatsapp


def test_narrow_space_before_pm(tmp_path):
    chat = tmp_path / "_chat.txt"
    chat.write_text("[11/4/26, 7:33:06 PM] Alex: привет\n[11/4/26, 7:34:10 PM] Me: ку\n", encoding="utf-8")
    messages = list(parse_whatsapp.read_messages(chat))
    assert [m["text"] for m in messages] == ["привет", "ку"]
    assert messages[0]["ts"] < messages[1]["ts"]
