"""Pure-pandas analytics checks on a small, hand-computed dataset."""
from datetime import date

import pandas as pd
from helpers import insert_expense

import analytics as an


def seed():
    # Mon 2026-09-28 .. Sun 2026-10-04
    insert_expense("chai", 20, "food", "2026-09-28 09:00")      # Mon
    insert_expense("lunch", 100, "food", "2026-09-29 13:00")    # Tue
    insert_expense("auto", 80, "transport", "2026-10-03 10:00")  # Sat
    insert_expense("movie", 300, "entertainment", "2026-10-04 20:00")  # Sun
    return date(2026, 9, 28), date(2026, 10, 4)


def test_kpis():
    start, end = seed()
    df = an.filter_range(an.load_expenses(), start, end)
    k = an.kpis(df, start, end)
    assert k["total"] == 500 and k["transactions"] == 4
    assert k["avg_per_day"] == 500 / 7
    assert k["top_category"] == "entertainment"


def test_category_table_shares_sum_to_100():
    start, end = seed()
    t = an.category_table(an.filter_range(an.load_expenses(), start, end))
    assert round(t["share_pct"].sum()) == 100 and t.iloc[0]["category"] == "entertainment"


def test_daily_series_counts_zero_days():
    start, end = seed()
    daily = an.daily_series(an.filter_range(an.load_expenses(), start, end), start, end)
    assert len(daily) == 7 and daily["Daily"].sum() == 500
    assert daily.loc[pd.Timestamp("2026-09-30"), "Daily"] == 0


def test_weekday_vs_weekend_uses_all_days_in_range():
    start, end = seed()
    w = an.weekday_vs_weekend(an.filter_range(an.load_expenses(), start, end), start, end)
    assert w["weekday_avg"] == 120 / 5 and w["weekend_avg"] == 380 / 2


def test_by_weekday_keeps_calendar_order():
    start, end = seed()
    by = an.by_weekday(an.filter_range(an.load_expenses(), start, end), start, end)
    assert list(by.index)[:2] == ["1 Mon", "2 Tue"] and by.loc["1 Mon", "Avg spend"] == 20


def test_month_comparison_uses_same_number_of_days():
    insert_expense("a", 100, "food", "2026-09-02 09:00")   # within first 4 days of Sept
    insert_expense("b", 900, "food", "2026-09-20 09:00")   # after day 4, must be ignored
    insert_expense("c", 150, "food", "2026-10-03 09:00")
    mc = an.month_comparison(an.load_expenses(), date(2026, 10, 4))
    assert mc["this"] == 150 and mc["prev_same_days"] == 100



def test_credit_card_spending_summarizes_each_card():
    import core
    import analytics as an

    core.add_expenses(
        [
            {
                "spent_at": "2026-10-10 12:00",
                "item": "Perfume",
                "amount_inr": 3924,
                "category": "Shopping",
                "payment_method": "credit_card",
                "card_name": "HDFC MoneyBack",
            },
            {
                "spent_at": "2026-10-11 13:00",
                "item": "Headphones",
                "amount_inr": 2000,
                "category": "Shopping",
                "payment_method": "credit_card",
                "card_name": "SBI Cashback",
            },
            {
                "spent_at": "2026-10-12 14:00",
                "item": "Shirt",
                "amount_inr": 1000,
                "category": "Shopping",
                "payment_method": "credit_card",
                "card_name": "HDFC MoneyBack",
            },
        ],
        "test credit card purchases",
    )

    df = an.load_expenses()
    summary, transactions = an.credit_card_spending(df)

    totals = dict(zip(summary["card_name"], summary["total_spend"]))

    assert totals == {
        "HDFC MoneyBack": 4924,
        "SBI Cashback": 2000,
    }
    assert len(transactions) == 3
    assert transactions.iloc[0]["item"] == "shirt"


def test_credit_card_spending_excludes_unknown_payment_method():
    import core
    import analytics as an

    core.add_expenses(
        [
            {
                "spent_at": "2026-10-10 12:00",
                "item": "Lunch",
                "amount_inr": 250,
                "category": "Food",
            }
        ],
        "lunch 250",
    )

    df = an.load_expenses()
    summary, transactions = an.credit_card_spending(df)

    assert summary.empty
    assert transactions.empty
