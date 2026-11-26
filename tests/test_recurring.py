"""Recurring: manage_subscription, post_due_recurring catch-up, status, projection, wiring."""
from datetime import date

import pandas as pd
import pytest
from helpers import count_rows, insert_expense, query, turn

import analytics as an
import backup
import core


def D(s):
    return date.fromisoformat(s)


def sub(action, item, today="2026-11-19", **kw):
    return core.manage_subscription(action, item, today=D(today), **kw)


def posts(item=None):
    sql = "SELECT spent_at, amount_inr FROM expenses WHERE recurring_id IS NOT NULL"
    return query(sql + (" AND item = ?" if item else "") + " ORDER BY spent_at",
                 (item,) if item else ())


def run(today):
    return core.post_due_recurring(D(today))


NETFLIX = {"amount_inr": 649, "category": "entertainment", "day": 5}


# ---------------------------------------------------------------- the worked examples
def test_monthly_example_on_time():
    assert sub("add", "Netflix", **NETFLIX) == ("Added netflix: ₹649 monthly on the 5th "
                                                "(entertainment). Next: 5 Dec.")
    assert posts() == []                       # 5 Nov is before created_on
    assert run("2026-12-05") == 1
    assert posts() == [("2026-12-05 09:00", 649.0)]
    assert run("2026-12-05") == 0              # second run the same day posts nothing


def test_monthly_example_catch_up_after_a_gap():
    sub("add", "netflix", **NETFLIX)
    assert run("2027-02-10") == 3
    assert [p[0] for p in posts()] == ["2026-12-05 09:00", "2027-01-05 09:00",
                                       "2027-02-05 09:00"]
    assert run("2027-02-10") == 0


def test_yearly_example():
    sub("add", "domain", amount_inr=899, category="bills", frequency="yearly",
        start_date="2026-12-01")
    assert run("2026-11-19") == 0
    assert run("2027-02-10") == 1
    assert posts() == [("2026-12-01 09:00", 899.0)]
    rule = core.subscription_status(D("2027-02-10"))[0]
    assert rule["next_due"] == D("2027-12-01")


def test_day_31_example_clamps_each_month():
    sub("add", "rent", amount_inr=15000, category="bills", day=31)
    assert run("2026-12-05") == 1
    assert run("2027-02-10") == 2
    assert [p[0][:10] for p in posts()] == ["2026-11-30", "2026-12-31", "2027-01-31"]
    assert core.subscription_status()[0]["next_due"] == D("2027-02-28")
    assert run("2027-03-31") == 2               # back to the 31st after February
    assert posts()[-1][0] == "2027-03-31 09:00"


def test_yearly_29_feb_posts_28_feb_in_other_years():
    rule = {"frequency": "yearly", "start_date": "2028-02-29"}
    assert core.due_dates(rule, D("2027-01-01"), D("2028-12-31")) == [D("2027-02-28"),
                                                                       D("2028-02-29")]


def test_weekly():
    sub("add", "gym", amount_inr=500, category="health", frequency="weekly",
        start_date="2026-11-16")               # a Monday
    assert run("2026-12-08") == 3               # 23 Nov, 30 Nov, 7 Dec
    assert [p[0][:10] for p in posts()] == ["2026-11-23", "2026-11-30", "2026-12-07"]


# ---------------------------------------------------------------- add
def test_add_on_the_due_day_posts_today():
    reply = sub("add", "spotify", amount_inr=119, day=19)
    assert "Logged today's ₹119." in reply and reply.endswith("Next: 19 Dec.")
    assert posts() == [("2026-11-19 09:00", 119.0)]


@pytest.mark.parametrize("kw, msg", [
    ({"amount_inr": 649}, "Which day of the month"),
    ({"amount_inr": 649, "frequency": "yearly"}, "Which date does it renew"),
    ({"amount_inr": 649, "frequency": "weekly", "day": 3}, "Which date does it renew"),
    ({"day": 5}, "Invalid amount"),
    ({"amount_inr": 649, "day": 32}, "Day must be"),
    ({"amount_inr": 649, "frequency": "daily", "day": 5}, "Unknown frequency"),
    ({"amount_inr": 649, "frequency": "yearly", "start_date": "12 March"}, "Invalid date"),
])
def test_add_validation(kw, msg):
    with pytest.raises(ValueError, match=msg):
        sub("add", "netflix", **kw)
    assert count_rows("recurring") == 0


def test_add_twice_is_an_error():
    sub("add", "netflix", **NETFLIX)
    with pytest.raises(ValueError, match="already exists"):
        sub("add", "NETFLIX", **NETFLIX)


def test_card_uses_shared_resolver():
    sub("add", "netflix", card_name="moneyback", **NETFLIX)
    assert query("SELECT payment_method, card_id FROM recurring") == [("credit_card", 1)]
    run("2026-12-05")
    assert query("SELECT payment_method, card_id FROM expenses") == [("credit_card", 1)]
    with pytest.raises(ValueError, match="matches several cards"):
        sub("add", "prime", amount_inr=1499, day=1, card_name="hdfc")
    with pytest.raises(ValueError, match="not registered"):
        sub("add", "prime", amount_inr=1499, day=1, card_name="Axis")


# ---------------------------------------------------------------- update
def test_update_amount_changes_later_posts_only():
    sub("add", "netflix", **NETFLIX)
    run("2026-12-05")
    sub("update", "netflix", today="2026-12-06", amount_inr=799)
    run("2027-01-05")
    assert [p[1] for p in posts()] == [649.0, 799.0]


def test_update_day_after_posting_this_period_does_not_repost():
    sub("add", "netflix", **NETFLIX)
    run("2026-12-05")
    reply = sub("update", "netflix", today="2026-12-06", day=20)
    assert reply.endswith("Next: 20 Jan.")
    assert run("2026-12-31") == 0               # no second December payment
    assert run("2027-01-20") == 1
    assert [p[0][:10] for p in posts()] == ["2026-12-05", "2027-01-20"]


def test_update_day_before_posting_this_period_posts_on_new_day():
    sub("add", "netflix", **NETFLIX)
    run("2026-12-03")
    sub("update", "netflix", today="2026-12-03", day=20)
    assert run("2026-12-20") == 1
    assert [p[0][:10] for p in posts()] == ["2026-12-20"]


def test_update_frequency_needs_its_anchor():
    sub("add", "netflix", **NETFLIX)
    with pytest.raises(ValueError, match="Pass start_date"):
        sub("update", "netflix", frequency="yearly")
    with pytest.raises(ValueError, match="Nothing to update"):
        sub("update", "netflix")


def test_ambiguous_and_unknown_rule():
    sub("add", "spotify premium", amount_inr=119, day=1)
    sub("add", "spotify family", amount_inr=179, day=1)
    with pytest.raises(ValueError, match="matches several subscriptions"):
        sub("pause", "spotify")
    with pytest.raises(ValueError, match="No subscription called 'hotstar'"):
        sub("pause", "hotstar")
    assert sub("pause", "family").startswith("Paused spotify family")


# ---------------------------------------------------------------- pause / resume / cancel
def test_pause_and_resume_do_not_back_fill():
    sub("add", "netflix", **NETFLIX)
    run("2026-12-05")
    sub("pause", "netflix", today="2026-12-10")
    assert run("2027-02-09") == 0
    assert sub("resume", "netflix", today="2027-02-10").endswith("Next: 5 Mar.")
    assert run("2027-03-05") == 1
    assert [p[0][:10] for p in posts()] == ["2026-12-05", "2027-03-05"]


def test_resume_on_the_due_day_posts_it():
    sub("add", "netflix", **NETFLIX)
    sub("pause", "netflix", today="2026-11-20")
    assert "Logged today's ₹649." in sub("resume", "netflix", today="2026-12-05")
    assert [p[0][:10] for p in posts()] == ["2026-12-05"]


def test_cancel_keeps_rule_and_past_payments():
    sub("add", "netflix", **NETFLIX)
    run("2026-12-05")
    sub("cancel", "netflix", today="2026-12-06")
    assert run("2027-03-01") == 0
    assert query("SELECT status FROM recurring") == [("cancelled",)]
    assert len(posts()) == 1
    with pytest.raises(ValueError, match="No subscription"):
        sub("resume", "netflix")
    sub("add", "netflix", **NETFLIX)            # a new rule may reuse the name
    assert count_rows("recurring") == 2


def test_deleted_auto_post_is_not_reposted():
    sub("add", "netflix", **NETFLIX)
    run("2026-12-05")
    core.delete_expense(query("SELECT id FROM expenses")[0][0])
    assert run("2026-12-20") == 0


def test_unique_index_blocks_duplicates_from_a_racing_run():
    sub("add", "netflix", **NETFLIX)
    run("2026-12-05")
    core.get_conn().execute("UPDATE recurring SET last_posted_on = NULL").connection.commit()
    assert run("2026-12-05") == 0               # same (rule, date) already there
    assert len(posts()) == 1


# ---------------------------------------------------------------- status, projection
def test_get_status_subscriptions():
    assert "No subscriptions yet" in core.get_status("subscriptions")
    sub("add", "netflix", **NETFLIX)
    sub("add", "prime", amount_inr=1500, frequency="yearly", start_date="2027-03-12")
    sub("add", "gym", amount_inr=600, frequency="weekly", start_date="2026-11-23")
    sub("add", "spotify", amount_inr=119, day=1)
    sub("pause", "spotify")
    text = core.get_status("subscriptions")
    assert text.splitlines()[0] == "Fixed costs: ₹3,374/month (3 active)."  # 649+125+2600
    assert "- prime: ₹1,500 yearly on 12 Mar, next 12 Mar (₹125/month)" in text
    assert "- gym: ₹600 weekly on Mon" in text
    assert text.splitlines()[-1] == "- spotify: ₹119 monthly on the 1st, paused"


def test_month_projection():
    today = date.today()
    sub("add", "rent", today=today.isoformat(), amount_inr=10000, category="bills",
        day=today.day)                                    # posts today
    insert_expense("chai", 100, spent_at=f"{today:%Y-%m}-01 09:00")
    df = an.load_expenses()
    last = core._month_day(today.year, today.month, 31).day
    expected = 100 / today.day * last + 10000
    assert an.month_projection(df, today) == pytest.approx(expected)
    assert isinstance(df, pd.DataFrame) and df["recurring_id"].notna().sum() == 1


# ---------------------------------------------------------------- wiring
def test_chat_add_subscription_is_one_model_call(script):
    log = script([("manage_subscription", {"action": "add", "item": "netflix",
                                           "amount_inr": 649, "category": "entertainment",
                                           "day": 5})])
    reply = turn("netflix 649 every month on the 5th")
    assert reply.startswith("Added netflix: ₹649 monthly on the 5th")
    assert len(log) == 1 and count_rows("recurring") == 1


def test_chat_missing_day_goes_back_to_the_model(script):
    log = script([("manage_subscription", {"action": "add", "item": "netflix",
                                           "amount_inr": 649})],
                 [("reply_to_user", {"message": "Which day does it renew?"})])
    assert turn("netflix 649 monthly") == "Which day does it renew?"
    assert len(log) == 2 and count_rows("recurring") == 0


def test_chat_turn_runs_the_catch_up(script):
    sub("add", "netflix", today="2026-01-01", **NETFLIX)  # due dates up to today are pending
    script([("reply_to_user", {"message": "hi"})])
    turn("hi")
    assert len(posts()) >= 1


def test_backup_posts_due_payments_before_the_snapshot(monkeypatch):
    sub("add", "netflix", today="2026-01-01", **NETFLIX)
    monkeypatch.setattr(backup, "_rclone", lambda *a: "")
    monkeypatch.setenv("BACKUP_REMOTE", "gcrypt:expense-backups")
    assert backup.main() == 0                   # 0 manual rows, but the auto-posts count
    assert len(posts()) >= 1
