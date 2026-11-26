"""
Dry run of the local fast path against real data. Opens a COPY of the database read-only,
makes no writes and no API calls.

    sqlite3 expenses.db ".backup /tmp/replay.db"   # not cp: a WAL copy can miss rows
    .venv/bin/python scripts/replay_local_parser.py /tmp/replay.db

Messages are rows grouped by identical raw_text + spent_at minute, walked in the order they
were logged (by id). Each one is parsed using only the item history from rows logged before
it. If the parser would handle it, item, amount, category and payment details are compared
with what was actually saved. Auto-posted subscription rows are not messages and are skipped
(but still count as history, as they do in the app).
"""
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("GEMINI_API_KEY", "unused")  # importing core never calls the API
import core  # noqa: E402


def replay(db_path: str) -> dict:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cards = [r[0] for r in conn.execute("SELECT card_name FROM credit_cards")]
        rows = conn.execute("SELECT id, raw_text, substr(spent_at, 1, 16), item, amount_inr, "
                            "category, payment_method, card_id FROM expenses "
                            "ORDER BY id").fetchall()
    finally:
        conn.close()

    groups = {}  # (raw_text, minute) -> rows, in first-logged order
    for r in rows:
        if r[1] and r[1] != "auto: recurring":
            groups.setdefault((r[1], r[2]), []).append(r)

    handled, mismatches = 0, []
    for (text, _minute), saved in groups.items():
        first_id = saved[0][0]
        history, seen = {}, Counter()  # item -> latest earlier category / times saved
        for r in rows:
            if r[0] >= first_id:
                break
            if r[4] > 0:
                history[core._check_item(r[3])] = r[5]
                seen[core._check_item(r[3])] += 1
        pairs = core._parse_local(text, cards)
        if not pairs or any(seen[core._check_item(i)] < core.LOCAL_MIN_SEEN for i, _ in pairs):
            continue  # same rule as core._local_turn
        handled += 1
        local = Counter((core._check_item(i), float(a), history[core._check_item(i)], None, None)
                        for i, a in pairs)
        actual = Counter((r[3], float(r[4]), r[5], r[6], r[7]) for r in saved)
        if local != actual:
            mismatches.append({"text": text, "local": sorted(local.elements()),
                               "saved": sorted(actual.elements(), key=str)})
    return {"messages": len(groups), "handled": handled, "mismatches": mismatches}


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    if not path.exists():  # mode=ro would fail anyway; this message is clearer
        print(f"No such file: {path}")
        return 2
    r = replay(str(path))
    print(f"Messages: {r['messages']}")
    print(f"Would be handled locally: {r['handled']}")
    print(f"Mismatches: {len(r['mismatches'])}")
    for m in r["mismatches"]:
        print(f"\n  {m['text']!r}\n    local: {m['local']}\n    saved: {m['saved']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
