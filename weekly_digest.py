"""
Weekly Telegram digest: last 7 days of spending vs the 7 before, budgets at risk, month pace.

    python weekly_digest.py             # send (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID in .env)
    python weekly_digest.py --dry-run   # print the message instead of sending

Runs from the expense-digest systemd timer (see deploy/).
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta

import analytics as an
import core  # loads .env and DB_PATH


def build_message(today: date = None) -> str:
    today = today or date.today()
    df = an.load_expenses()
    if df.empty:
        return "No expenses logged yet."

    start, prev_end = today - timedelta(days=6), today - timedelta(days=7)
    cur = an.filter_range(df, start, today)
    prev = an.filter_range(df, today - timedelta(days=13), prev_end)
    k = an.kpis(cur, start, today)
    prev_total = float(prev["amount_inr"].sum())

    lines = [
        f"Week {start:%d %b} to {today:%d %b}",
        f"Spent Rs {k['total']:,.0f} in {k['transactions']} purchases "
        f"(Rs {k['avg_per_day']:,.0f}/day)",
    ]
    if prev_total:
        d = k["total"] - prev_total
        word = "Up" if d > 0 else "Down"
        pct = 100 * d / prev_total
        lines.append(f"{word} Rs {abs(d):,.0f} ({pct:+.0f}%) vs the week before")
    if k["transactions"]:
        lines.append(f"Top category: {k['top_category']} (Rs {k['top_category_amount']:,.0f})")
        big = an.biggest_expenses(cur, 1)
        if not big.empty:
            lines.append(f"Biggest: {big.iloc[0]['item']} (Rs {big.iloc[0]['amount_inr']:,.0f})")
        rows = list(cur.sort_values("spent_at").itertuples())
        lines += ["", "All purchases:"]
        # Telegram caps a message at 4096 chars
        lines += [f"{r.spent_at:%a %d}  {r.item}  Rs {r.amount_inr:,.0f}" for r in rows[:60]]
        if len(rows) > 60:
            lines.append(f"...and {len(rows) - 60} more")
        lines.append(f"Total: Rs {k['total']:,.0f}")

    risky = [b for b in core.budget_status(today) if b["pct"] >= 80]
    if risky:
        lines.append("")
        lines.append("Budgets at 80% or more this month:")
        lines += [
            f"  {b['category']}: Rs {b['spent']:,.0f} of {b['budget']:,.0f} ({b['pct']:.0f}%)"
            for b in risky
        ]

    lines += ["", f"Month-end pace: Rs {an.month_projection(df, today):,.0f}"]
    return "\n".join(lines)


def send(text: str):
    url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"
    body = json.dumps({"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text}).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    # raises on HTTP errors, so systemd shows a failure
    urllib.request.urlopen(req, timeout=15).read()


if __name__ == "__main__":
    msg = build_message()
    if "--dry-run" in sys.argv:
        print(msg)
    else:
        send(msg)
