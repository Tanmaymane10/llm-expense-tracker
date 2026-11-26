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
    c = {"card": XSS, "statement_day": 1, "due_day": 20, "spent_cycle": 500.0,
         "limit": 10000.0, "utilisation": 25.0, "paid": False, "amount_due": 2000.0,
         "days_to_due": 3}
    return {**c, **over}


def test_card_row_escapes_and_shows_utilisation():
    out = ui.card_row(_card())
    _safe(out)
    assert "width:25.0%" in out and "incl. unpaid bill" in out and "Due in 3 days" in out
    paid = ui.card_row(_card(paid=True, utilisation=5.0))
    assert "incl. unpaid bill" not in paid and "width:5.0%" in paid
    assert ui.due_text(-2)[0] == "Overdue 2 days" and ui.due_text(9)[1] == ui.MUTED


def test_card_tile_color_by_name():
    assert ui.card_art("SBI Cashback") == "linear-gradient(135deg, #7B5CD6, #4A3590)"
    assert ui.card_art("swiggy HDFC") == ui.CARD_ART["swiggy hdfc"]  # any casing
    assert ui.card_art("Slice UPI") == ui.card_art("SLICE")
    assert ui.card_art("Amex Gold") == ui.card_art(None) == ui.CARD_ART_OTHER
    assert "#C8F25A" not in "".join(ui.CARD_ART.values()) + ui.CARD_ART_OTHER
    assert ui.CARD_ART["hdfc moneyback"] in ui.card_row(_card(card="HDFC MoneyBack"))


def test_all_cards_shown_sorted_with_quiet_and_undated_rows():
    rows = [
        _card(card="b quiet", spent_cycle=0, paid=True, days_to_due=2, utilisation=12.0),
        _card(card="Undated", statement_day=None, due_day=None, spent_cycle=None, paid=None,
              amount_due=None, days_to_due=None, utilisation=None),
        _card(card="late", days_to_due=9, spent_cycle=100.0),
        _card(card="big", days_to_due=4, spent_cycle=900.0),
        _card(card="small", days_to_due=4, spent_cycle=50.0),
        _card(card="A quiet", spent_cycle=0, paid=True, amount_due=0, days_to_due=1),
        _card(card="overdue", days_to_due=-1, spent_cycle=0),  # unpaid bill, no new spend
    ]
    order = [c["card"] for c in ui.sort_cards(rows)]
    assert order == ["overdue", "big", "small", "late", "A quiet", "b quiet", "Undated"]
    quiet = ui.card_row(rows[0])
    assert "No bill due" in quiet and "₹0 this cycle" in quiet and "width:12.0%" in quiet
    assert "Overdue 1 day" in ui.card_row(rows[6])
    undated = ui.card_row(rows[1])
    assert "No bill due" not in undated and "Due in" not in undated  # the app's button says it


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


def test_analytics_bars_and_payments_escape():
    out = ui.bars("Where it went", "vs budget",
                  [{"name": XSS, "spent": 4696, "of": "of ₹4,000", "pct": 117, "state": "over"}])
    _safe(out)
    assert "width:100.0%" in out and ui.DANGER in out  # capped at full width, red
    _safe(ui.by_payment([(XSS, 2060, 33.0)]))
    assert "Biggest day: Sun 22, ₹1,288" in ui.daily_foot(date(2026, 11, 1), TODAY,
                                                         (date(2026, 11, 22), 1288))
    assert "▲ ₹1,180 vs same days in Oct" in ui.daily_head(6240, 5060, "same days in Oct",
                                                          date(2026, 11, 1), TODAY)
