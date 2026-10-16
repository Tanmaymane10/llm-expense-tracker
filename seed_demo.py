"""
Fill a SEPARATE demo database with fake spending, so you can try the analytics page
and take README screenshots without exposing your real data.

    python seed_demo.py
    $env:EXPENSE_DB="demo.db"; streamlit run app.py      # PowerShell
    EXPENSE_DB=demo.db streamlit run app.py              # Mac/Linux
"""
import os
import random
from datetime import date, datetime, timedelta

os.environ["EXPENSE_DB"] = "demo.db"  # must be set before importing core
import core  # noqa: E402

DAYS = 120
random.seed(7)

# category -> (item, min Rs, max Rs)
ITEMS = {
    "food": [("chai", 10, 30), ("vada pav", 20, 40), ("lunch", 80, 200),
             ("dinner", 150, 500), ("swiggy order", 200, 500), ("coffee", 60, 180)],
    "transport": [("auto ride", 40, 150), ("metro", 20, 60), ("petrol", 200, 600),
                  ("cab", 150, 450)],
    "groceries": [("vegetables", 100, 350), ("milk and bread", 60, 150),
                  ("dmart groceries", 800, 2500)],
    "shopping": [("t-shirt", 500, 1200), ("earphones", 600, 1800), ("shoes", 1500, 3500)],
    "entertainment": [("movie ticket", 200, 400), ("gaming", 100, 500)],
    "health": [("medicines", 100, 500)],
}


def pick(cat):
    item, lo, hi = random.choice(ITEMS[cat])
    return cat, item, round(random.uniform(lo, hi) / 5) * 5


def when(day, lo=8, hi=22):
    return datetime(day.year, day.month, day.day, random.randint(lo, hi),
                    random.choice([0, 10, 20, 30, 40, 50]))


rows = []
today = date.today()
for i in range(DAYS):
    d = today - timedelta(days=DAYS - 1 - i)
    weekend = d.weekday() >= 5
    n_food = random.randint(3, 4) if weekend else random.randint(2, 3)
    todays = [pick("food") for _ in range(n_food)]
    if not weekend and random.random() < 0.8:
        todays += [pick("transport") for _ in range(random.randint(1, 2))]
    if weekend and random.random() < 0.4:
        todays.append(pick("entertainment"))
    if weekend and random.random() < 0.15:
        todays.append(pick("shopping"))
    if d.weekday() == 6 and random.random() < 0.7:
        todays.append(pick("groceries"))
    if random.random() < 0.05:
        todays.append(pick("health"))
    if d.day == 3:
        todays += [("bills", "electricity bill", random.randint(1200, 2200)),
                   ("bills", "phone recharge", 299)]
    if d.day == 12:
        todays.append(("entertainment", "netflix", 649))
    if d.day == 5:
        todays.append(("health", "gym", 500))
    for cat, item, amt in todays:
        rows.append((when(d).strftime("%Y-%m-%d %H:%M"), item, float(amt), cat, "demo data"))

core.init_db()
with core.get_conn() as conn:
    conn.execute("DELETE FROM expenses")
    conn.executemany("INSERT INTO expenses (spent_at, item, amount_inr, category, raw_text) "
                     "VALUES (?, ?, ?, ?, ?)", rows)
print(f"Wrote {len(rows)} fake expenses to demo.db")
