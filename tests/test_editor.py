"""Chat-view editor: edits go through update_expense validation; deletes need a confirm."""
from datetime import date

from helpers import count_rows, good_expense, insert_expense, query

import core


def _row(eid=1):
    return query("SELECT spent_at, item, amount_inr, category, payment_method, card_id "
                 "FROM expenses WHERE id = ?", (eid,))[0]


def test_valid_changes_are_saved():
    insert_expense("chai", 15, "food", "2026-10-03 09:00")
    errors = core.apply_edits({1: {"amount_inr": 20.0, "item": "Masala Chai",
                                   "spent_at": "2026-10-03T10:30:00.000",
                                   "category": "groceries", "payment": "SBI Cashback"}})
    assert errors == {}
    assert _row() == ("2026-10-03 10:30", "masala chai", 20.0, "groceries", "credit_card", 3)


def test_only_changed_cells_are_written():
    with core.get_conn() as conn:
        conn.execute("INSERT INTO expenses (spent_at, item, amount_inr, category, recurring_id) "
                     "VALUES ('2026-10-03 09:00', 'netflix', 649, 'entertainment', 1)")
    assert core.apply_edits({1: {"amount_inr": 799.0}}) == {}
    assert _row()[1:3] == ("netflix", 799.0)


def test_bad_values_return_errors_and_save_nothing_for_that_row():
    insert_expense("chai", 15)
    insert_expense("tea", 10)
    bad = {"amount_inr": 0.0}
    errors = core.apply_edits({1: bad, 2: {"amount_inr": 12.0}})
    assert set(errors) == {1} and "Amount must be above 0" in errors[1]
    assert _row(1)[2] == 15.0 and _row(2)[2] == 12.0  # the valid row was still saved

    for change, words in [
        ({"amount_inr": -5.0}, "Amount must be above 0"),
        ({"amount_inr": None}, "Amount can't be empty"),
        ({"item": "  "}, "Item can't be empty"),
        ({"spent_at": "2099-01-01T10:00:00"}, "future"),
        ({"payment": "Nope Card"}, "Unknown payment method"),
        ({"amount_inr": core.MAX_AMOUNT_INR * 2}, "at most"),
    ]:
        err = core.apply_edits({1: change})
        assert words in err[1], change
    assert _row(1) == ("2026-10-03 09:00", "chai", 15.0, "food", None, None)


def test_refund_stays_negative():
    insert_expense("refund: swiggy", -130, "food")
    assert core.apply_edits({1: {"amount_inr": -150.0}}) == {}
    assert _row()[2] == -150.0
    assert core.apply_edits({1: {"amount_inr": 120.0}}) == {}
    assert _row()[2] == -120.0


def test_payment_can_be_cleared_or_set_to_a_method():
    core.add_expenses([good_expense(payment_method="credit_card", card_name="SBI Cashback")], "t")
    core.add_expenses([good_expense(payment_method="upi")], "t")  # makes "upi" an option
    assert core.apply_edits({1: {"payment": None}}) == {}
    assert _row()[4:] == (None, None)
    assert core.apply_edits({1: {"payment": "upi"}}) == {}
    assert _row()[4:] == ("upi", None)


def test_missing_row_is_an_error():
    assert "No expense" in core.apply_edits({99: {"amount_inr": 5.0}})[99]


def test_model_update_cannot_set_payment_fields(script):
    insert_expense()
    script([("list_recent_expenses", {})],
           [("update_expense", {"expense_id": 1, "amount_inr": 20, "payment_method": "cash"})],
           [("reply_to_user", {"message": "Updated."})])
    from helpers import turn
    turn("make the chai 20")
    assert _row()[2] == 20.0 and _row()[4] is None


# ---------------------------------------------------------------- in the app
def test_editor_shows_recent_rows_with_payment_label():
    from test_app_smoke import run_app
    core.add_expenses([good_expense(spent_at=f"{date.today()} 09:00", payment_method="credit_card",
                                    card_name="SBI Cashback")], "t")
    at = run_app()
    df = at.dataframe[0].value
    assert list(df["payment"]) == ["SBI Cashback"] and list(df["delete"]) == [False]


def test_delete_needs_confirm():
    from test_app_smoke import _widget, run_app
    insert_expense("chai")
    insert_expense("tea")
    at = run_app()
    at.session_state["confirm_delete"] = [2]  # as if the box was ticked and Delete pressed
    at.run()
    assert any("Delete #2 tea?" in w.value for w in at.warning)
    _widget(at.button, "Cancel").click().run()
    assert count_rows() == 2 and not at.warning

    at.session_state["confirm_delete"] = [2]
    at.run()
    _widget(at.button, "Yes, delete").click().run()
    assert query("SELECT item FROM expenses") == [("chai",)] and not at.exception
