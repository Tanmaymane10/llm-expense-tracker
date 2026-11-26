"""Budgets: set_budget, batch-summed alerts, refunds, get_status, and the chat wiring."""
from datetime import date, datetime, timedelta

import pytest
from helpers import count_rows, good_expense, query, turn

import analytics as an
import core

NOW = datetime.now().strftime("%Y-%m-%d %H:%M")


def spend(*amounts, category="food", **extra):
    return core.add_expenses([good_expense(spent_at=NOW, amount_inr=a, category=category, **extra)
                              for a in amounts], "test")


def alert_lines(reply):
    return [ln for ln in reply.splitlines() if "budget" in ln or "% of" in ln]


# ---------------------------------------------------------------- set_budget
def test_set_budget_upserts_and_zero_removes():
    assert core.set_budget("food", 6000) == "Budget set: food ₹6,000/month."
    core.set_budget("food", 7000)
    assert query("SELECT category, amount_inr FROM budgets") == [("food", 7000.0)]
    assert core.set_budget("food", 0) == "Budget removed: food."
    assert core.set_budget("food", 0) == "There was no food budget to remove."
    assert count_rows("budgets") == 0


@pytest.mark.parametrize("category, amount", [
    ("food", -5), ("food", core.MAX_AMOUNT_INR + 1), ("food", "lots"), ("rent", 100)])
def test_set_budget_rejects_bad_values(category, amount):
    with pytest.raises(ValueError):
        core.set_budget(category, amount)
    assert count_rows("budgets") == 0


# ---------------------------------------------------------------- alerts
def test_two_items_in_one_batch_give_a_single_step_line():
    core.set_budget("food", 6000)
    reply = spend(2000, 1500)
    assert alert_lines(reply) == [f"Food: 58% of ₹6,000 used, {core._days_left(date.today())} "
                                  "days left"]


def test_steps_fire_once_then_over_budget_repeats():
    core.set_budget("food", 6000)
    assert len(alert_lines(spend(3000))) == 1          # crosses 50
    assert alert_lines(spend(100)) == []                # still between 50 and 80
    assert "82% of" in spend(1800)                      # crosses 80 (4,900 of 6,000)
    assert "100% of" in spend(1100)                     # exactly 6,000
    assert alert_lines(spend(10)) == ["Food: over budget by ₹10 (₹6,010 of ₹6,000)"]
    assert alert_lines(spend(5)) == ["Food: over budget by ₹15 (₹6,015 of ₹6,000)"]


def test_no_budget_and_backdated_rows_give_no_alert():
    assert alert_lines(spend(5000)) == []
    core.set_budget("food", 100)
    last_month = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d 10:00")
    reply = core.add_expenses([good_expense(spent_at=last_month, amount_inr=500)], "test")
    assert alert_lines(reply) == []


def test_overall_budget_counts_every_category():
    core.set_budget("overall", 1000)
    reply = spend(300, category="food") and spend(300, category="transport")
    assert alert_lines(reply) == [f"Overall: 60% of ₹1,000 used, "
                                  f"{core._days_left(date.today())} days left"]


def test_refund_is_negative_lowers_spend_and_never_alerts():
    core.set_budget("food", 1000)
    spend(1200)
    reply = spend(500, is_refund=True, item="Pizza")
    assert alert_lines(reply) == []
    assert "refund: pizza: -₹500" in reply
    assert query("SELECT item, amount_inr FROM expenses WHERE amount_inr < 0") == [
        ("refund: pizza", -500.0)]
    assert core.budget_status()[0]["spent"] == 700


@pytest.mark.parametrize("given", ["swiggy order refund", "Refund: swiggy order"])
def test_refund_item_is_prefixed_once(given):
    assert "- refund: swiggy order: -₹50" in spend(50, is_refund=True, item=given)


def test_update_keeps_refund_negative():
    spend(500, is_refund=True)
    core.update_expense(1, amount_inr=450)
    assert query("SELECT amount_inr FROM expenses") == [(-450.0,)]


# ---------------------------------------------------------------- status and analytics
def test_get_status_budgets_text():
    assert core.get_status("budgets").startswith("No budgets set yet")
    core.set_budget("food", 1000)
    core.set_budget("overall", 500)
    spend(600)
    text = core.get_status("budgets")
    assert "- Food: ₹600 of ₹1,000 (60%), ₹400 left" in text
    assert "- Overall: ₹600 of ₹500 (120%), over by ₹100" in text
    with pytest.raises(ValueError):
        core.get_status("weather")


def test_budget_progress_states():
    for cat in ("food", "transport", "shopping"):
        core.set_budget(cat, 100)
    spend(50, category="food")
    spend(85, category="transport")
    spend(100, category="shopping")
    df = an.budget_progress()
    assert dict(zip(df["category"], df["state"], strict=True)) == {
        "food": "ok", "transport": "warn", "shopping": "over"}


# ---------------------------------------------------------------- chat wiring
def test_set_budget_and_expense_in_one_response_both_run(script):
    log = script([("set_budget", {"category": "food", "amount_inr": 1000}),
                  ("add_expenses", {"expenses": [good_expense(spent_at=NOW, amount_inr=600)]})])
    reply = turn("food budget 1000, and lunch 600")
    assert "Budget set: food ₹1,000/month." in reply
    assert "Saved:" in reply and "Food: 60% of ₹1,000 used" in reply
    assert count_rows() == 1 and count_rows("budgets") == 1 and len(log) == 1


def test_saved_text_survives_a_failed_tool_in_the_same_turn(script):
    core.set_budget("food", 1000)
    log = script([("add_expenses", {"expenses": [good_expense(spent_at=NOW, amount_inr=600)]}),
                  ("set_budget", {"category": "food", "amount_inr": -10})],
                 [("reply_to_user", {"message": "Budgets must be above 0."})])
    reply = turn("lunch 600, and food budget -10")
    assert "Saved:" in reply and "Food: 60% of ₹1,000 used" in reply
    assert reply.endswith("Budgets must be above 0.")
    assert count_rows() == 1 and len(log) == 2


def test_saved_text_survives_when_model_then_returns_nothing(script):
    script([("add_expenses", {"expenses": [good_expense()]}),
            ("get_spending_summary", {"start_date": "x", "end_date": "y"})])  # 2nd step: no call
    reply = turn("chai 15 and how much this week")
    assert reply.startswith("Saved:") and reply.endswith(core.FALLBACK_MSG)


def test_get_status_answers_locally(script):
    log = script([("get_status", {"topic": "budgets"})])
    assert turn("how much budget is left?").startswith("No budgets set yet")
    assert len(log) == 1


def test_bad_budget_goes_back_to_model(script):
    log = script([("set_budget", {"category": "food", "amount_inr": -10})],
                 [("reply_to_user", {"message": "Budgets must be above 0."})])
    assert turn("food budget -10") == "Budgets must be above 0."
    assert len(log) == 2 and count_rows("budgets") == 0


def test_confirmation_shows_validated_values(script):
    script([("add_expenses", {"expenses": [good_expense(
        item="  Chai   Latte ", amount_inr="15", category="nonsense",
        card_name="hdfc moneyback")]})])
    reply = turn("chai latte 15 on hdfc moneyback")
    assert "- chai latte: ₹15 (other, 2026-10-03 09:00, HDFC MoneyBack)" in reply
