"""Add the user's train of thought to reply pairs: pairs_v2 + thoughts.jsonl → pairs_v4.

For reply pairs the assistant message gets `reasoning_content` ("act: … · tone: … · gist: …"),
which Glimmer's chat template writes into its own reasoning channel (`to=self`) before the reply.
The model learns to first decide what this user would think and do, then say it their way.
Rewrite and compose pairs stay as they are: their meaning is already given.

  python pipeline/add_thoughts.py
"""

import json

from parse_telegram import ROOT


def thought_text(t):
    return f"act: {t['act']} · tone: {t['tone']} · gist: {t['gist']}"


def main(src="pairs_v2", dst="pairs_v4"):
    thoughts = {}
    for line in (ROOT / "data" / "thoughts.jsonl").open(encoding="utf-8"):
        t = json.loads(line)
        thoughts[t["turn_id"]] = t
    (ROOT / "data" / dst).mkdir(exist_ok=True)
    for split in ("train", "test"):
        added = 0
        with (ROOT / "data" / dst / f"{split}.jsonl").open("w", encoding="utf-8") as out:
            for line in (ROOT / "data" / src / f"{split}.jsonl").open(encoding="utf-8"):
                row = json.loads(line)
                t = thoughts.get(row["meta"]["turn_id"])
                if row["meta"]["task"] == "reply" and t:
                    row["messages"][2]["reasoning_content"] = thought_text(t)
                    row["meta"].update(act=t["act"], tone=t["tone"])
                    added += 1
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{split}: {added} reply pairs with a thought")


if __name__ == "__main__":
    main()
