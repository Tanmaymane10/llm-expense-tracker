"""Weekly digest: refunds are not purchases, invested money is not spent, day-to-day line."""
from datetime import date, timedelta

from helpers import insert_expense

import core
import weekly_digest

TODAY = date(2026, 11, 26)


def test_refunds_not_counted_and_day_to_day_line():
    day = f"{TODAY - timedelta(days=1)} 09:00"
    insert_expense("juice", 160, "food", day)
    insert_expense("bread", 124, "groceries", day)
    insert_expense("refund: juice", -130, "food", day)
    insert_expense("sip", 8400, "investment", day)
    core.set_d2d_limits(5000, 7000)
    msg = weekly_digest.build_message(TODAY)
    assert "Spent ₹154 in 2 purchases" in msg  # 160 + 124 - 130; the refund isn't a purchase
    assert "Invested ₹8,400 (not counted as spent)" in msg and "  sip  " not in msg
    assert "Day-to-day this month: ₹154 of ₹5,000–₹7,000 (on track)" in msg
