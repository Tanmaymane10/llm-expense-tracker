"""Spending groups, the day-to-day target/limit, month figures and card-cycle figures."""
import sqlite3
from contextlib import closing
from datetime import date

import pytest
from helpers import good_expense, query

import core

TODAY = date(2026, 11, 26)


def add(item, amount, category="food", day="2026-11-10", recurring=None, d2d=None,
        method=None, card_id=None):
    with closing(sqlite3.connect(core.DB_PATH)) as conn:
        conn.execute("INSERT INTO expenses (spent_at, item, amount_inr, category, raw_text, "
                     "recurring_id, counts_d2d, payment_method, card_id) "
                     "VALUES (?, ?, ?, ?, 'test', ?, ?, ?, ?)",
                     (f"{day} 10:00", item, amount, category, recurring, d2d, method, card_id))
        conn.commit()


def groups():
    return dict(query(f"SELECT item, {core.GROUP_SQL} FROM expenses"))


def test_group_defaults():
    add("chai", 15)
    add("electricity", 2000, "bills")
    add("netflix", 649, "entertainment", recurring=1)
    add("to parents", 10000, "family", recurring=2)
    add("sip", 8400, "investment", recurring=3)
    add("gift for mom", 500, "family")
    assert groups() == {"chai": "day-to-day", "electricity": "fixed", "netflix": "fixed",
                        "to parents": "family", "sip": "invested", "gift for mom": "family"}


def test_group_override():
    add("insurance", 12000, "health", d2d=0)    # no -> fixed
    add("cake for mom", 400, "family", d2d=1)   # yes beats the category
    add("gym", 500, "health", recurring=1, d2d=1)
    add("dinner", 900, d2d=None)                # default
    assert groups() == {"insurance": "fixed", "cake for mom": "day-to-day",
                        "gym": "day-to-day", "dinner": "day-to-day"}


@pytest.mark.parametrize("spent, status", [(4999, "on track"), (5000, "near limit"),
                                           (7000, "near limit"), (7001, "over limit")])
def test_status_thresholds(spent, status):
    assert core.d2d_status(spent, 5000, 7000) == status


def test_pace():
    assert core.month_pace(2600, date(2026, 11, 26)) == 3000       # 100/day x 30 days
    assert core.month_pace(300, date(2026, 12, 1)) == 300 * 31      # day 1 counts as one day
    assert core.month_pace(0, date(2026, 2, 1)) == 0


def test_month_figures():
    core.set_budget("food", 100)
    add("chai", 100, method="upi")
    add("auto", 40, "transport", day="2026-11-26", method="cash")
    add("refund: juice", -30)
    add("to parents", 10000, "family", recurring=2, method="upi")  # not day-to-day: not counted
    add("sip", 8400, "investment", recurring=3, method="bank_transfer")
    add("rent", 9000, "bills")
    add("insurance", 50, d2d=0)
    add("old", 999, day="2026-10-31")
    f = core.month_figures(TODAY)
    assert f["d2d"] == 110 and f["today"] == 40 and f["non_card"] == 110  # refund: NULL method
    assert f["groups"] == {"day-to-day": 110, "fixed": 9050, "family": 10000, "invested": 8400}
    assert f["total_out"] == 110 + 9050 + 10000 + 8400
    assert f["status"] == "on track" and f["left"] == 7000 - 110
    assert f["pace"] == pytest.approx(110 / 26 * 30)
    assert [b["category"] for b in f["near"]] == ["food"]  # 120 of 100 (category budget)


def test_settings_round_trip_and_validation():
    assert core.get_d2d_limits() == (5000, 7000)
    core.set_d2d_limits(6000, 8000)
    assert core.get_d2d_limits() == (6000, 8000)
    for target, limit in [(7000, 7000), (8000, 7000), (0, 7000), (5000, "x")]:
        with pytest.raises(ValueError):
            core.set_d2d_limits(target, limit)
    assert core.get_d2d_limits() == (6000, 8000)
    add("chai", 6500)
    assert core.month_figures(TODAY)["status"] == "near limit"


def test_non_card_spending_counts_every_day_to_day_method_but_credit_cards():
    for i, method in enumerate(["upi", "CASH", "debit_card", "Bank_Transfer", None]):
        add(f"d2d {i}", 10 ** i, method=method)  # 1 + 10 + 100 + 1000 + 10000
    add("card", 7, method="credit_card")
    add("card caps", 70, method="CREDIT_CARD")
    add("parents", 500, "family", method="upi")
    add("sip", 600, "investment", method="bank_transfer")
    add("rent", 700, "bills", method="upi")
    assert core.month_figures(TODAY)["non_card"] == 11111


def test_card_cycle_sums_across_the_statement_day(monkeypatch):
    core.register_card("HDFC MoneyBack", statement_day=15, due_day=5, credit_limit=40000)
    for day, amount in [("2026-11-15", 1000), ("2026-11-16", 200), ("2026-11-26", 300),
                        ("2026-10-15", 7777)]:  # 15 Oct closes the cycle before
        add("x", amount, day=day, method="credit_card", card_id=1)
    c = core.card_status(TODAY)[0]
    assert (c["amount_due"], c["spent_cycle"], c["paid"]) == (1000, 500, False)
    assert c["utilisation"] == pytest.approx(100 * 1500 / 40000)
    assert c["next_due"] == date(2026, 12, 5) and c["days_to_due"] == 9

    core.set_paid_through(1, "2026-11-15")  # bill paid: the next due date is the next bill's
    c = core.card_status(TODAY)[0]
    assert c["paid"] and c["next_due"] == date(2027, 1, 5) and c["days_to_due"] == 40
    assert c["utilisation"] == pytest.approx(100 * 500 / 40000)


def test_card_without_cycle_settings_has_no_due():
    c = core.card_status(TODAY)[0]
    assert c["next_due"] is None and c["days_to_due"] is None


def test_overdue_card_shows_negative_days():
    core.register_card("SBI Cashback", statement_day=1, due_day=20)
    add("x", 500, day="2026-10-20", method="credit_card", card_id=3)
    c = [c for c in core.card_status(TODAY) if c["card"] == "SBI Cashback"][0]
    assert c["next_due"] == date(2026, 11, 20) and c["days_to_due"] == -6


def test_model_cannot_set_the_override(script):
    script([("add_expenses", {"expenses": [good_expense(counts_d2d=0)]})])
    core.chat_turn([], "chai 15", "u1")
    core.add_expenses([good_expense(counts_d2d=0)], "test")
    assert query("SELECT counts_d2d FROM expenses") == [(None,), (None,)]


def test_quick_add_and_editor_set_the_override():
    core.quick_add("insurance", 12000, "health", counts_d2d=False)
    (eid,), = query("SELECT id FROM expenses")
    assert query("SELECT counts_d2d FROM expenses") == [(0,)]
    assert core.apply_edits({eid: {"counts_d2d": "yes"}}) == {}
    assert query("SELECT counts_d2d FROM expenses") == [(1,)]
    core.update_expense(eid, counts_d2d="default")
    assert query("SELECT counts_d2d FROM expenses") == [(None,)]
    assert core.apply_edits({eid: {"counts_d2d": "maybe"}})  # rejected


def test_undo_keeps_a_row_whose_override_changed():
    ids = []
    token = core.saved_ids.set(ids)
    core.add_expenses([good_expense()], "test")
    core.saved_ids.reset(token)
    snap = core.expense_snapshot(ids)
    core.update_expense(ids[0], counts_d2d="no")
    assert core.undo_expenses(snap) == (0, 1, 0)


def test_invested_counts_as_saved():
    core.add_income(50000, "salary", "2026-11-01")
    add("sip", 8400, "investment")
    add("chai", 1000)
    s = core.savings("2026-11")
    assert (s["expenses"], s["invested"], s["net"]) == (1000, 8400, 49000)
    assert "invested ₹8,400, net ₹49,000" in core.get_status("savings", "2026-11")


def test_total_out_budget_counts_investments_and_alerts_once():
    core.set_budget("overall", 1000)
    core.set_budget("investment", 500)
    reply = core.add_expenses([good_expense(spent_at=f"{date.today()} 09:00", item="sip",
                                            amount_inr=1200, category="investment")], "test")
    lines = [ln for ln in reply.splitlines() if "budget" in ln.lower()]
    assert [ln.split(":")[0] for ln in lines] == ["Investment", "Total out budget"]
    assert "Overall" not in reply


def test_python_default_matches_group_sql():
    for cat in core.CATEGORIES:
        add(cat, 1, cat)
    got = groups()
    expected = {c: core.counts_by_default(c) for c in core.CATEGORIES}
    assert {c: got[c] == "day-to-day" for c in core.CATEGORIES} == expected
