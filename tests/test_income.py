"""Income: add_income, savings status (incl. negative rate), analytics and the chat wiring."""
from datetime import date, datetime, timedelta

import pandas as pd
import pytest
from helpers import count_rows, good_expense, query, turn

import analytics as an
import core

TODAY = date.today()
MONTH = TODAY.strftime("%Y-%m")
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")


def spend(amount, **extra):
    core.add_expenses([good_expense(spent_at=NOW, amount_inr=amount, **extra)], "test")


def test_add_income_saves_validated_row():
    reply = core.add_income("50000", "salary", "2026-11-01", "  Nov   pay ", "got salary 50000")
    assert reply == "Saved income: salary ₹50,000 on 1 Nov."
    assert query("SELECT received_at, source, amount_inr, note, raw_text FROM income") == [
        ("2026-11-01 00:00", "salary", 50000.0, "Nov pay", "got salary 50000")]


@pytest.mark.parametrize("amount, source, when", [
    (0, "salary", None), (-5, "salary", None), (core.MAX_AMOUNT_INR + 1, "salary", None),
    ("lots", "salary", None), (100, "refund", None), (100, "salary", "2999-01-01"),
    (100, "salary", "yesterday")])
def test_add_income_rejects_bad_values(amount, source, when):
    with pytest.raises(ValueError):
        core.add_income(amount, source, when)
    assert count_rows("income") == 0


def test_delete_income():
    core.add_income(100, "other")
    assert core.delete_income(1) is True
    assert core.delete_income(1) is False and count_rows("income") == 0


# ---------------------------------------------------------------- savings status
def test_savings_rate_is_na_without_income():
    spend(500)
    assert core.get_status("savings") == (f"{TODAY:%B %Y}: income ₹0, expenses ₹500, "
                                          "net -₹500, savings rate n/a.")


def test_savings_rate_goes_negative_when_spending_exceeds_income():
    core.add_income(1000, "freelance")
    spend(1120)
    assert core.savings(MONTH)["rate"] == pytest.approx(-12)
    assert core.get_status("savings").endswith("net -₹120, savings rate -12%.")


def test_refunds_net_out_and_month_filter_applies():
    core.add_income(10000, "salary")
    spend(3000)
    spend(500, is_refund=True)
    core.add_expenses([good_expense(spent_at="2020-01-05 10:00", amount_inr=999)], "test")
    assert core.savings(MONTH) == {"income": 10000, "expenses": 2500, "net": 7500,
                                     "invested": 0, "rate": 75}
    assert core.get_status("savings", "2020-01").startswith("January 2020: income ₹0, "
                                                            "expenses ₹999")
    with pytest.raises(ValueError):
        core.get_status("savings", "Nov 2026")


def test_savings_by_month():
    last = (TODAY.replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
    core.add_income(1000, "salary", last)
    core.add_income(2000, "salary")
    spend(500)
    df = an.savings_by_month(an.load_expenses(), an.load_income())
    assert list(df.columns) == ["Income", "Expenses", "Savings"]
    assert df["Savings"].tolist() == [1000.0, 1500.0]
    assert df.index[-1] == pd.Timestamp(TODAY.replace(day=1))
    no_income = an.savings_by_month(an.load_expenses(), an.load_income().iloc[0:0])
    assert no_income["Income"].tolist() == [0.0] and no_income["Savings"].tolist() == [-500.0]


# ---------------------------------------------------------------- chat wiring
def test_got_salary_saves_income_not_an_expense(script):
    log = script([("add_income", {"amount_inr": 50000, "source": "salary"})])
    assert turn("got salary 50000").startswith("Saved income: salary ₹50,000")
    assert count_rows() == 0 and count_rows("income") == 1 and len(log) == 1
    assert query("SELECT raw_text FROM income") == [("got salary 50000",)]


def test_income_text_survives_a_failed_tool_in_the_same_turn(script):
    log = script([("add_income", {"amount_inr": 50000, "source": "salary"}),
                  ("get_status", {"topic": "savings", "month": "bad"})],
                 [("reply_to_user", {"message": "Which month?"})])
    reply = turn("got salary 50000, how much did I save")
    assert reply.startswith("Saved income:") and reply.endswith("Which month?")
    assert len(log) == 2


def test_savings_status_answers_locally(script):
    log = script([("get_status", {"topic": "savings"})])
    assert "savings rate n/a" in turn("how much did I save this month?")
    assert len(log) == 1
