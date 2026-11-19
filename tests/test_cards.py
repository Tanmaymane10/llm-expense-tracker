"""Cards: register_card settings and bill_paid, card_cycle, card_status, due notes, get_status."""
from datetime import date, datetime, timedelta

import pytest
from helpers import count_rows, good_expense, query, turn

import core

TODAY = date.today()


def D(s):
    return date.fromisoformat(s)


def cycle(sday, dday, today):
    c = core.card_cycle(sday, dday, D(today))
    return tuple(str(c[k]) for k in ("prev_start", "prev_end", "cur_start", "cur_end",
                                     "due_date"))


# ---------------------------------------------------------------- card_cycle
@pytest.mark.parametrize("sday, dday, today, expected", [
    # the two worked examples (due_day <= statement_day: due next month)
    (15, 5, "2026-11-19", ("2026-10-16", "2026-11-15", "2026-11-16", "2026-12-15", "2026-12-05")),
    (15, 5, "2026-12-03", ("2026-10-16", "2026-11-15", "2026-11-16", "2026-12-15", "2026-12-05")),
    # statement day itself closes the cycle
    (15, 5, "2026-11-15", ("2026-10-16", "2026-11-15", "2026-11-16", "2026-12-15", "2026-12-05")),
    # due_day > statement_day: due in the same month
    (5, 25, "2026-11-19", ("2026-10-06", "2026-11-05", "2026-11-06", "2026-12-05", "2026-11-25")),
    (5, 25, "2026-11-03", ("2026-09-06", "2026-10-05", "2026-10-06", "2026-11-05", "2026-10-25")),
    # Dec -> Jan
    (15, 5, "2026-12-20", ("2026-11-16", "2026-12-15", "2026-12-16", "2027-01-15", "2027-01-05")),
    (15, 5, "2027-01-03", ("2026-11-16", "2026-12-15", "2026-12-16", "2027-01-15", "2027-01-05")),
    # Feb clamping (statement 31, due 30)
    (31, 30, "2027-02-28", ("2027-02-01", "2027-02-28", "2027-03-01", "2027-03-31", "2027-03-30")),
    (31, 30, "2027-02-27", ("2027-01-01", "2027-01-31", "2027-02-01", "2027-02-28", "2027-02-28")),
    (31, 30, "2028-02-29", ("2028-02-01", "2028-02-29", "2028-03-01", "2028-03-31", "2028-03-30")),
    # no due day
    (10, None, "2026-11-19", ("2026-10-11", "2026-11-10", "2026-11-11", "2026-12-10", "None")),
])
def test_card_cycle(sday, dday, today, expected):
    assert cycle(sday, dday, today) == expected


# ---------------------------------------------------------------- register_card
def test_settings_update_existing_card_and_new_card_still_registers():
    assert "Registered" in core.register_card("Axis Flipkart")
    reply = core.register_card("axis flipkart", statement_day=15, due_day=5, credit_limit=30000)
    assert reply == "Axis Flipkart: statement day 15, due day 5, credit limit Rs 30,000."
    assert query("SELECT statement_day, due_day, credit_limit FROM credit_cards "
                 "WHERE card_name = 'Axis Flipkart'") == [(15, 5, 30000.0)]
    assert "already registered" in core.register_card("AXIS FLIPKART")


def test_settings_for_unknown_card_do_not_register_it():
    before = count_rows("credit_cards")
    with pytest.raises(ValueError, match="Unknown card. Known cards: HDFC MoneyBack"):
        core.register_card("Axis Flipkart", statement_day=10)
    with pytest.raises(ValueError, match="Unknown card"):
        core.register_card("Axis Flipkart", bill_paid=True)
    assert count_rows("credit_cards") == before


def test_partial_match_unique_and_ambiguous():
    assert core.register_card("moneyback", due_day=5).startswith("HDFC MoneyBack:")
    with pytest.raises(ValueError, match="HDFC MoneyBack, Swiggy HDFC"):
        core.register_card("HDFC", statement_day=15)
    assert query("SELECT statement_day FROM credit_cards WHERE statement_day IS NOT NULL") == []


@pytest.mark.parametrize("field, value", [("statement_day", 0), ("statement_day", 32),
                                          ("due_day", 4.5), ("due_day", "x"),
                                          ("credit_limit", 0), ("credit_limit", -1)])
def test_bad_settings_rejected(field, value):
    with pytest.raises(ValueError):
        core.register_card("HDFC MoneyBack", **{field: value})


def test_bill_paid_needs_statement_day():
    with pytest.raises(ValueError, match="Set a statement day for HDFC MoneyBack first"):
        core.register_card("HDFC MoneyBack", bill_paid=True)


# ---------------------------------------------------------------- card_status / due notes
def card_id(name="HDFC MoneyBack"):
    return query("SELECT id FROM credit_cards WHERE card_name = ?", (name,))[0][0]


def spend(day: date, amount, card="HDFC MoneyBack"):
    core.add_expenses([good_expense(spent_at=f"{day} 10:00", amount_inr=amount,
                                    card_name=card)], "test")


def setup_due_soon():
    """Statement yesterday, due in 2 days: the closed cycle ends yesterday."""
    stmt, due = TODAY - timedelta(days=1), TODAY + timedelta(days=2)
    core.register_card("HDFC MoneyBack", statement_day=stmt.day, due_day=due.day,
                       credit_limit=20000)
    c = core.card_cycle(stmt.day, due.day, TODAY)
    if c["prev_end"] != stmt or c["due_date"] != due:
        pytest.skip("month-end clamping changes the dates today")
    return c


def test_amount_due_is_closed_cycle_only():
    c = setup_due_soon()
    spend(c["prev_start"], 1000)
    spend(c["prev_end"], 500)
    spend(c["prev_start"] - timedelta(days=1), 9999)  # older cycle
    spend(TODAY, 300)                                 # current cycle
    spend(TODAY, 7777, card="Swiggy HDFC")            # other card
    s = core.card_status()[0]
    assert (s["amount_due"], s["spent_cycle"], s["paid"]) == (1500, 300, False)
    assert s["utilisation"] == pytest.approx(100 * 1800 / 20000)


def test_due_note_once_per_day_and_bill_paid_silences_it():
    c = setup_due_soon()
    spend(c["prev_end"], 8420)
    spend(TODAY, 1200)
    expected = (f"HDFC MoneyBack: Rs 8,420 due on {c['due_date'].day} {c['due_date']:%b} "
                "(Rs 1,200 spent this cycle)")
    assert core.due_notes() == [expected]
    assert core.due_notes() == []  # stamped for today
    expenses, income = count_rows(), count_rows("income")
    assert "marked paid" in core.register_card("hdfc moneyback", bill_paid=True)
    assert (count_rows(), count_rows("income")) == (expenses, income)
    s = core.card_status()[0]
    assert s["paid"] is True and core.due_line(s, TODAY) is None
    assert query("SELECT paid_through FROM credit_cards WHERE id = ?",
                 (card_id(),)) == [(str(c["prev_end"]),)]


def test_overdue_line_and_far_due_has_none():
    core.register_card("HDFC MoneyBack", statement_day=15, due_day=5)
    with core.get_conn() as conn:
        conn.execute("INSERT INTO expenses (spent_at, item, amount_inr, category, card_id) "
                      "VALUES ('2026-11-01 10:00', 'tv', 8420, 'shopping', ?)", (card_id(),))
    s = core.card_status(D("2026-12-10"))[0]
    assert core.due_line(s, D("2026-12-10")).startswith(
        "HDFC MoneyBack: Rs 8,420 overdue since 5 Dec")
    s = core.card_status(D("2026-11-19"))[0]
    assert s["amount_due"] == 8420 and core.due_line(s, D("2026-11-19")) is None


def test_cards_without_statement_day_dont_crash():
    assert core.due_notes() == []
    assert core.get_status("cards").splitlines()[0] == "HDFC MoneyBack: no statement day set."


def test_get_status_cards_line():
    c = setup_due_soon()
    spend(c["prev_end"], 8420)
    line = core.get_status("cards").splitlines()[0]
    assert line == (f"HDFC MoneyBack: Rs 8,420 due {c['due_date'].day} {c['due_date']:%b}, "
                    "unpaid; Rs 0 spent this cycle; 42% of Rs 20,000 limit.")


# ---------------------------------------------------------------- chat wiring
def test_bill_paid_is_one_call_local_reply_with_no_rows(script):
    setup_due_soon()
    log = script([("register_card", {"card_name": "HDFC MoneyBack", "bill_paid": True})])
    reply = turn("paid my HDFC MoneyBack bill 12000")
    assert "marked paid" in reply and len(log) == 1
    assert count_rows() == 0 and count_rows("income") == 0


def test_new_card_keeps_two_call_flow(script):
    log = script([("register_card", {"card_name": "Axis Flipkart"})],
                 [("add_expenses", {"expenses": [good_expense(card_name="Axis Flipkart")]})])
    assert turn("yes register it").startswith("Saved:")
    assert len(log) == 2 and count_rows() == 1


def test_ambiguous_card_error_goes_back_to_model(script):
    log = script([("register_card", {"card_name": "HDFC", "bill_paid": True})],
                 [("reply_to_user", {"message": "Which HDFC card?"})])
    assert turn("paid my hdfc bill") == "Which HDFC card?"
    assert len(log) == 2


def test_due_notes_appended_to_chat_reply_once(script):
    c = setup_due_soon()
    spend(c["prev_end"], 500)
    script([("reply_to_user", {"message": "Hi!"})], [("reply_to_user", {"message": "Hi!"})])
    first, second = turn("hi"), turn("hi")
    assert first.startswith("Hi!\n\nHDFC MoneyBack: Rs 500 due on") and second == "Hi!"


def test_quota_reply_gets_no_notes(script, monkeypatch):
    c = setup_due_soon()
    spend(c["prev_end"], 500)

    def boom(*a, **k):
        raise core.DailyQuotaExceeded("x")
    monkeypatch.setattr(core, "_generate", boom)
    assert turn("hi") == core.QUOTA_MSG


# ---------------------------------------------------------------- shared resolver
def test_add_expenses_and_summary_use_the_card_resolver():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    assert "HDFC MoneyBack" in core.add_expenses(
        [good_expense(spent_at=now, amount_inr=100, card_name="moneyback")], "test")
    with pytest.raises(ValueError, match="HDFC MoneyBack, Swiggy HDFC"):
        core.add_expenses([good_expense(spent_at=now, card_name="hdfc")], "test")
    assert count_rows() == 1
    out = core.get_summary(str(TODAY), str(TODAY), card_name="MoneyBack")
    assert out.endswith("Grand total: Rs 100.00")
    with pytest.raises(ValueError, match="matches several cards"):
        core.get_summary(str(TODAY), str(TODAY), card_name="HDFC")
    assert "No registered card" in core.get_summary(str(TODAY), str(TODAY), card_name="Amex")


# ---------------------------------------------------------------- Plan tab: confirm + undo
def test_plan_mark_paid_needs_confirm_and_undo_restores():
    from test_app_smoke import run_app
    c = setup_due_soon()
    spend(c["prev_end"], 500)
    core.set_paid_through(card_id(), "2020-01-01")  # an earlier value Undo must restore

    def paid_through():
        return query("SELECT paid_through FROM credit_cards WHERE id = ?", (card_id(),))[0][0]

    def click(at, label):
        next(b for b in at.button if b.label == label).click().run()
        assert not at.exception

    at = run_app()
    click(at, "Mark bill paid")
    assert any("as paid?" in w.value for w in at.warning) and paid_through() == "2020-01-01"
    click(at, "Cancel")
    assert paid_through() == "2020-01-01"
    click(at, "Mark bill paid")
    click(at, "Yes, mark paid")
    assert paid_through() == str(c["prev_end"])
    assert "Mark bill paid" not in [b.label for b in at.button]
    click(at, "Undo paid")
    assert paid_through() == "2020-01-01" and core.card_status()[0]["paid"] is False
    assert "Undo paid" not in [b.label for b in at.button]


# ---------------------------------------------------------------- regression
def test_summary_for_one_card_sums_only_that_card():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    core.add_expenses([good_expense(spent_at=now, amount_inr=100, card_name="HDFC MoneyBack"),
                       good_expense(spent_at=now, amount_inr=40, card_name="HDFC MoneyBack"),
                       good_expense(spent_at=now, amount_inr=900, card_name="Swiggy HDFC"),
                       good_expense(spent_at=now, amount_inr=70)], "test")
    out = core.get_summary(str(TODAY), str(TODAY), card_name="HDFC MoneyBack")
    assert out.endswith("Grand total: Rs 140.00")
