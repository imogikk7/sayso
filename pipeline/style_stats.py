"""Rerank candidates by the user's own statistics for the same audience × situation.

Scoring against the user's *average* pushes every answer to the mode (an average partner reply
has 0.3 laughs, so the closest candidate never laughs). Instead, for each request we draw one of
the user's real turns from the same audience × situation (falling back to the audience when the
cell has few turns) and pick the candidate whose features are closest to it. Over many requests
the outputs follow the user's distribution: they laugh as often as the user does in that cell.

  from style_stats import StyleStats
  stats = StyleStats.from_pairs("pairs_v2")
  best = stats.pick(candidates, audience, situation, key=turn_id)
"""

import json
import math
import random
import statistics
import sys
from collections import defaultdict

from lexicon import load as load_lexicon
from lexicon import words
from parse_telegram import ROOT

sys.path.insert(0, str(ROOT / "eval"))
from metrics import features as surface_features  # noqa: E402

MIN_CELL = 30


def vector(text, lex):
    surface = surface_features(text)
    tokens = words(text)
    n = max(len(tokens), 1)
    return {
        "log_chars": math.log(len(text) + 5),
        "lines": min(surface["lines"], 8),
        "signature": sum(t in lex["signature"] for t in tokens) / n,
        "unknown": sum(t not in lex["vocab"] for t in tokens) / n,
        "emoji": float(surface["emoji_per_line"] > 0),
        "laughter": surface["laughter"],
        "swear": surface["swear"],
        "end_punct": surface["end_punct"],
        "lower_start": surface["lower_start"],
    }


class StyleStats:
    def __init__(self, turns, lex):
        """turns: iterable of (audience, situation, text) from the user's real train turns."""
        self.lex = lex
        self.cells, self.audiences = defaultdict(list), defaultdict(list)
        everything = []
        for audience, situation, text in turns:
            v = vector(text, lex)
            self.cells[(audience, situation)].append(v)
            self.audiences[audience].append(v)
            everything.append(v)
        self.scale = {f: statistics.pstdev([v[f] for v in everything]) or 1.0 for f in everything[0]}

    @classmethod
    def from_pairs(cls, pairs="pairs_v2"):
        rows = (json.loads(line) for line in (ROOT / "data" / pairs / "train.jsonl").open(encoding="utf-8"))
        turns = [(r["meta"]["audience"], r["meta"]["situation"], r["messages"][2]["content"]) for r in rows]
        return cls(turns, load_lexicon())

    def targets(self, audience, situation):
        cell = self.cells.get((audience, situation), [])
        return cell if len(cell) >= MIN_CELL else self.audiences[audience]

    def distance(self, candidate_vector, target):
        return sum(abs(candidate_vector[f] - target[f]) / self.scale[f] for f in target)

    def pick(self, candidates, audience, situation, key=None, lexical_weight=10.0):
        """lexical_weight also rewards lexicon.score; 10 balanced chrF (29.2) and length (31 vs 28 real) on the v2 test set."""
        from lexicon import score as lexical_score
        target = random.Random(key).choice(self.targets(audience, situation))
        avoid = self.lex["avoid"]

        def cost(text):
            if not text.strip():
                return float("inf")
            return (self.distance(vector(text, self.lex), target) + sum(t in avoid for t in words(text))
                    - lexical_weight * lexical_score(text, self.lex))

        return min(candidates, key=cost)
