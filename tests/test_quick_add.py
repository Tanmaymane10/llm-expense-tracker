"""Quick-add panel: frequent-item chips saved through add_expenses with no model call."""
from datetime import date, datetime, timedelta

import pytest
from helpers import count_rows, insert_expense, query, turn

import analytics as an
import core


def _no_model(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("the model must not be called")
    monkeypatch.setattr(core, "_generate", fail)


def _day(n=0):
    return f"{date.today() - timedelta(days=n)} 09:00"


def test_quick_items_ranked_by_count_with_last_used_values():
    core.add_expenses([{"spent_at": _day(3), "item": "chai", "amount_inr": 15,
                        "category": "food", "payment_method": "cash"}], "t")
    core.add_expenses([{"spent_at": _day(1), "item": "chai", "amount_inr": 20, "category": "food",
                        "payment_method": "credit_card", "card_name": "SBI Cashback"}], "t")
    insert_expense("chai", 25, "food", _day(2))  # older id order: id 3 is the latest
    insert_expense("auto", 80, "transport", _day(0))
    insert_expense("old", 10, "food", _day(100))  # outside 90 days
    insert_expense("refund: chai", -15, "food", _day(0))  # refunds never become chips
    with core.get_conn() as conn:
        conn.execute("INSERT INTO expenses (spent_at, item, amount_inr, category, recurring_id) "
                     "VALUES (?, 'netflix', 649, 'entertainment', 1)", (_day(0),))
    items = core.quick_items()
    assert [(r["item"], r["n"]) for r in items] == [("chai", 3), ("auto", 1)]
    assert items[0]["amount_inr"] == 25 and items[0]["payment_method"] is None


def test_quick_items_caps_at_n():
    for i in range(10):
        insert_expense(f"item{i}", 10, "food", _day(0))
    assert len(core.quick_items(n=8)) == 8


def test_payment_options_come_from_the_db():
    core.add_expenses([{"spent_at": _day(), "item": "chai", "amount_inr": 15, "category": "food",
                        "payment_method": "debit_card"}], "t")
    opts = core.payment_options()
    assert opts["SBI Cashback"] == ("credit_card", "SBI Cashback")
    assert opts["debit card"] == ("debit_card", None)
    assert "upi" not in opts  # never used, so not offered


def test_quick_add_saves_with_no_model_call(monkeypatch):
    _no_model(monkeypatch)
    reply = core.quick_add("Vada Pav", 20, "food", "upi", None, datetime.now())
    assert reply.startswith("Saved:\n- vada pav: ₹20 (food, ")
    assert query("SELECT item, amount_inr, payment_method, raw_text FROM expenses") == [
        ("vada pav", 20.0, "upi", "quick add")]
    assert query("SELECT purpose, status, total_tokens, attempts FROM llm_calls") == [
        ("quick_add", "ok", 0, 0)]


def test_quick_add_gives_the_same_budget_alert_as_add_expenses():
    core.set_budget("food", 100)
    reply = core.quick_add("thali", 90, "food")
    assert "Food: 90% of ₹100 used" in reply


def test_quick_add_saves_card_purchase():
    core.quick_add("towel", 504, "shopping", "credit_card", "SBI Cashback")
    assert query("SELECT payment_method, card_id FROM expenses") == [("credit_card", 3)]


@pytest.mark.parametrize("kwargs", [
    {"amount_inr": 0}, {"amount_inr": core.MAX_AMOUNT_INR + 1}, {"item": "  "},
    {"payment_method": "credit_card", "card_name": "Nope Card"},
    {"payment_method": "crypto"},
])
def test_quick_add_validation_saves_nothing(kwargs):
    args = {"item": "chai", "amount_inr": 15, "category": "food", **kwargs}
    with pytest.raises(ValueError):
        core.quick_add(**args)
    assert count_rows() == 0 and count_rows("llm_calls") == 0


def test_quick_add_is_not_counted_as_a_model_call():
    core.quick_add("chai", 15, "food")
    assert an.llm_summary(an.load_llm_calls())["calls"] == 0
    assert an.local_saves() == 1


def test_quick_add_history_is_never_sent_to_the_model(script):
    log = script([("reply_to_user", {"message": "Hi!"})])
    history = [{"role": "user", "content": "Quick add: chai", "source": "quick_add"},
               {"role": "assistant", "content": "Saved:\n- chai: ₹15", "source": "quick_add"}]
    turn("hello", history)
    sent = [p.text for c in log[0] for p in c.parts]
    assert sent == ["hello"]


# ---------------------------------------------------------------- the panel in the app
def test_panel_tap_save_with_no_model_call(monkeypatch):
    from test_app_smoke import _widget, run_app
    insert_expense("chai", 15, "food", _day(1))
    _no_model(monkeypatch)
    at = run_app()
    chips = _widget(at.button_group, "Quick add")
    assert chips.options == ["chai · ₹15", "+ Other"]
    chips.set_value("chai · ₹15").run()
    assert _widget(at.text_input, "Item").value == "chai"  # the sheet is prefilled
    assert any(c.value == "Last time: ₹15 · food" for c in at.caption)
    _widget(at.number_input, "Amount (₹)").set_value(18.0).run()
    _widget(at.button, "Save ₹18").click().run()
    assert not at.exception
    assert query("SELECT item, amount_inr, category, counts_d2d FROM expenses WHERE id = 2") == [
        ("chai", 18.0, "food", None)]
    assert at.chat_message[0].markdown[0].value == "Quick add: chai"
    assert _widget(at.button_group, "Quick add").value is None  # chips reset after a save
    assert not [b for b in at.button if b.label.startswith("Save")]  # the sheet closed


def test_panel_other_item_and_error(monkeypatch):
    from test_app_smoke import _widget, run_app
    _no_model(monkeypatch)
    at = run_app()
    _widget(at.button_group, "Quick add").set_value("+ Other").run()
    _widget(at.button, "Save ₹0").click().run()  # empty item, zero amount
    assert at.error and count_rows() == 0
    _widget(at.text_input, "Item").set_value("bath towel")
    _widget(at.number_input, "Amount (₹)").set_value(504.0).run()
    _widget(at.button, "Save ₹504").click().run()
    assert query("SELECT item, category FROM expenses") == [("bath towel", "other")]


def test_sheet_from_nav_and_day_to_day_switch(monkeypatch):
    from test_app_smoke import _widget, run_app
    _no_model(monkeypatch)
    at = run_app("Usage")
    at.button(key="nav_add").click().run()  # the "+" opens the sheet on any view
    _widget(at.text_input, "Item").set_value("insurance")
    _widget(at.number_input, "Amount (₹)").set_value(12000.0)
    _widget(at.button_group, "Category").set_value("health").run()
    assert _widget(at.toggle, "Counts toward day-to-day budget").value is True  # default
    _widget(at.toggle, "Counts toward day-to-day budget").set_value(False).run()
    _widget(at.button, "Save ₹12,000").click().run()

    at.button(key="nav_add").click().run()
    _widget(at.text_input, "Item").set_value("sip")
    _widget(at.number_input, "Amount (₹)").set_value(8400.0)
    _widget(at.button_group, "Category").set_value("investment").run()
    assert _widget(at.toggle, "Counts toward day-to-day budget").value is False  # default
    _widget(at.button, "Save ₹8,400").click().run()
    assert query("SELECT item, counts_d2d FROM expenses") == [("insurance", 0), ("sip", None)]
    assert not at.exception
