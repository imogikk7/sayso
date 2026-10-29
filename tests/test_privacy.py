"""Other people's messages must never end up in files under data/.

Runs on the real exports from data/config.json (skips if there is no config).
Usage: python3 -m unittest tests/test_privacy.py
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

CONFIG = ROOT / "data" / "config.json"


@unittest.skipUnless(CONFIG.exists(), "no data/config.json")
class NoIncomingOnDisk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from parse_telegram import load_config, load_turns
        config, audiences = load_config(CONFIG)
        cls.rows, _ = load_turns(config, audiences, with_context=True)
        own = "\n".join(r["text"] for r in cls.rows)
        # Distinctive incoming lines that the user never typed themselves.
        cls.incoming = {
            line for r in cls.rows for msg in r["context"] for line in msg.split("\n")
            if len(line) >= 25 and len(set(line.lower())) >= 8  # "ахахахах…" isn't anyone's text
            and not line.startswith("[") and line not in own
        }

    def data_files(self):
        return [p for p in (ROOT / "data").rglob("*") if p.is_file() and p.suffix in {".jsonl", ".json"}]

    def test_has_incoming_sample(self):
        self.assertGreater(len(self.incoming), 100)

    def test_no_context_field_on_disk(self):
        for path in self.data_files():
            if path.suffix != ".jsonl":
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                self.assertNotIn("context", json.loads(line), path.name)

    def test_no_incoming_text_on_disk(self):
        # data/bench holds generations of models trained on the user's own turns only; a stock phrase there can
        # coincide with something the other person once wrote, which is not stored input.
        for path in self.data_files():
            if "bench" in path.parts:
                continue
            content = path.read_text(encoding="utf-8")
            leaked = [s for s in self.incoming if s in content]
            self.assertEqual(leaked, [], f"{path.name} contains {len(leaked)} incoming lines")

    def test_turn_ids_unique(self):
        ids = [r["turn_id"] for r in self.rows]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
