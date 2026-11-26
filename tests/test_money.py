"""One money format everywhere: ₹, Indian digit grouping, paise only when not zero."""
from datetime import date

import pytest
from helpers import insert_expense

import core


@pytest.mark.parametrize("value, text", [
    (14.55, "₹14.55"), (14.5, "₹14.50"), (15, "₹15"), (15.0, "₹15"), (0, "₹0"),
    (999, "₹999"), (1000, "₹1,000"), (125000, "₹1,25,000"), (1000000, "₹10,00,000"),
    (12345678.9, "₹1,23,45,678.90"), (-130, "-₹130"), (-1250.5, "-₹1,250.50"),
    (0.1 + 0.2, "₹0.30"), (-0.001, "₹0"), (14.999, "₹15"),
])
def test_inr(value, text):
    assert core.inr(value) == text


def test_saved_reply_and_alerts_use_rupee_format():
    core.set_budget("food", 125000)
    reply = core.add_expenses([{"spent_at": f"{date.today()} 09:00", "item": "party",
                                "amount_inr": 100000.5, "category": "food"}], "t")
    assert "- party: ₹1,00,000.50 (food, " in reply
    assert "Food: 80% of ₹1,25,000 used" in reply


def test_weekly_digest_uses_rupee_format():
    import weekly_digest
    insert_expense("rent", 125000, "bills", f"{date.today()} 09:00")
    msg = weekly_digest.build_message()
    assert "Spent ₹1,25,000 in 1 purchases" in msg and "Rs" not in msg
