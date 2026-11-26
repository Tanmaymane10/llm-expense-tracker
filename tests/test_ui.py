"""ui.py builders: every value from data is escaped, and the Home rules for cards and days."""
from datetime import date, datetime

import pandas as pd

import ui

XSS = "<script>alert(1)</script>"
TODAY = date(2026, 11, 26)


def _safe(out):
    assert "&lt;script&gt;" in out and "<script" not in out


def test_recent_escapes_item_category_and_payment():
    df = pd.DataFrame([{"id": 1, "spent_at": datetime(2026, 11, 26, 19, 5), "item": XSS,
                        "amount_inr": -130.0, "category": XSS, "payment": XSS, "auto": False}])
    out = ui.recent(df, TODAY)
    _safe(out)
    assert "&lt;s" in out  # the 2-letter tile is escaped too
    assert "+₹130" in out and "Today" in out and "7:05 pm" in out


def _card(**over):
    c = {"card": XSS, "statement_day": 1, "spent_cycle": 500.0, "limit": 10000.0,
         "utilisation": 25.0, "paid": False, "amount_due": 2000.0, "days_to_due": 3}
    return {**c, **over}


def test_cards_escape_and_show_utilisation():
    out = ui.cards([_card()], 140)
    _safe(out)
    assert "width:25.0%" in out and "incl. unpaid bill" in out and "Due in 3 days" in out
    paid = ui.cards([_card(paid=True, utilisation=5.0)], 0)
    assert "incl. unpaid bill" not in paid and "width:5.0%" in paid


def test_cards_listed_only_with_spend_or_due_soon():
    assert ui.show_card(_card(spent_cycle=0, days_to_due=7))
    assert not ui.show_card(_card(spent_cycle=0, days_to_due=8))
    assert not ui.show_card(_card(statement_day=None))
    assert ui.due_text(-2)[0] == "Overdue 2 days" and ui.due_text(9)[1] == ui.MUTED


def test_hero_escapes_category_alert():
    fig = {"status": "near limit", "target": 5000, "limit": 7000, "d2d": 6240, "today": 290,
           "pace": 7200, "left": 760,
           "near": [{"category": XSS, "spent": 4695, "budget": 4000, "pct": 117}]}
    out = ui.hero(fig, TODAY)
    _safe(out)
    assert "Near limit" in out and "₹5k target" in out and "left:62.5%" in out


def test_day_labels():
    assert ui.day_label(date(2026, 11, 25), TODAY) == "Yesterday · Wed 25 Nov"
    assert ui.day_label(date(2026, 11, 22), TODAY) == "Sun 22 Nov"
