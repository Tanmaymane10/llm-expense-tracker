"""Loads the real Streamlit app and clicks through every period option."""
from datetime import date
from pathlib import Path

import pytest
from helpers import insert_expense
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


VIEWS = ["Chat", "Analytics", "Plan", "LLM usage"]


def run_app(view="Chat"):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["authed"] = True
    at.run()
    return go(at, view) if view != "Chat" else at


def go(at, view):
    nav(at).set_value(view).run()
    return at


def nav(at):
    return at.button_group[0]

def test_pin_gate_blocks_until_correct(monkeypatch):
    monkeypatch.setenv("APP_PIN", "123456")
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.button_group  # nothing from the app is rendered
    at.text_input[0].set_value("000000")
    at.button[0].click().run()
    assert not at.button_group
    at.text_input[0].set_value("123456")
    at.button[0].click().run()
    assert nav(at).options == VIEWS and nav(at).value == "Chat"


def test_app_loads_with_empty_database():
    at = run_app()
    assert not at.exception
    assert nav(at).options == VIEWS and nav(at).value == "Chat"
    for view in VIEWS:
        assert not go(at, view).exception


@pytest.mark.parametrize("period", ["This month", "Last 30 days", "Last 90 days",
                                    "All time", "Custom"])
def test_every_period_renders_without_errors(period):
    from datetime import date, timedelta
    for days_ago in (0, 2, 10, 40):
        day = (date.today() - timedelta(days=days_ago)).isoformat()
        insert_expense("chai", 15, "food", f"{day} 09:00")
    at = run_app("Analytics")
    at.radio[0].set_value(period).run()
    assert not at.exception


def test_llm_usage_tab_renders_with_recorded_calls():
    import time

    from helpers import FakeResp, usage

    import core
    started = time.perf_counter()
    core._log_llm_call("chat", "ok", started, 1, resp=FakeResp([("add_expenses", {})], usage()))
    core._log_llm_call("chat", "error", started, 2, error="ConnectionError")
    at = run_app("LLM usage")
    assert not at.exception
    labels = [m.label for m in at.metric]
    assert "Calls today" in labels and "Success rate" in labels


def _widget(items, label, nth=0):
    return [w for w in items if w.label == label][nth]


def test_plan_subscriptions_click_through():
    from helpers import query

    import core
    core.manage_subscription("add", "netflix", amount_inr=649, category="entertainment", day=5,
                             card_name="HDFC MoneyBack")
    status = lambda: query("SELECT amount_inr, status, card_id FROM recurring")[0]  # noqa: E731
    at = run_app("Plan")

    # update the amount through the form (the first "Amount (₹)" is the subscription form's)
    _widget(at.selectbox, "Add or update").set_value("netflix").run()
    _widget(at.number_input, "Amount (₹)").set_value(799.0)
    _widget(at.button, "Save subscription").click().run()
    assert not at.exception and status() == (799.0, "active", 1)

    _widget(at.button, "Pause").click().run()
    assert status()[1] == "paused"
    _widget(at.button, "Resume").click().run()
    assert status()[1] == "active"

    # cancel needs a confirm; "Keep it" leaves the rule alone
    _widget(at.button, "Cancel subscription").click().run()
    assert any("Cancel netflix?" in w.value for w in at.warning)
    _widget(at.button, "Keep it").click().run()
    assert status()[1] == "active" and not [b for b in at.button if b.label == "Keep it"]
    _widget(at.button, "Cancel subscription").click().run()
    _widget(at.button, "Yes, cancel it").click().run()
    assert status()[1] == "cancelled" and not at.exception


def test_plan_renders_paused_subscription_without_arrow_fallback(monkeypatch):
    import streamlit.dataframe_util as du

    import core
    core.manage_subscription("add", "netflix", amount_inr=649, category="entertainment", day=5)
    core.manage_subscription("add", "gym", amount_inr=500, category="health", day=1)
    core.manage_subscription("pause", "gym")  # paused rules have no next_due
    fixed = []  # Streamlit only calls this after Arrow rejects a mixed-type column
    real = du.fix_arrow_incompatible_column_types
    monkeypatch.setattr(du, "fix_arrow_incompatible_column_types",
                        lambda df, *a, **k: fixed.append(list(df.columns)) or real(df, *a, **k))
    at = run_app("Plan")
    assert not at.exception and not fixed


def test_plan_remove_card_and_auto_tag():
    from helpers import query

    import core
    core.manage_subscription("add", "netflix", amount_inr=649, category="entertainment",
                             day=date.today().day, card_name="HDFC MoneyBack")  # posts today
    at = run_app("Plan")
    _widget(at.selectbox, "Add or update").set_value("netflix").run()
    _widget(at.selectbox, "Card").set_value("(remove card)")
    _widget(at.button, "Save subscription").click().run()
    assert query("SELECT card_id, payment_method FROM recurring") == [(None, None)]
    recent = go(at, "Chat").dataframe[0].value  # the editable recent-entries table
    assert list(recent["item"]) == ["netflix"] and list(recent["auto"]) == [True]


def test_chat_input_is_on_top_and_newest_exchange_comes_first(monkeypatch):
    import core
    monkeypatch.setattr(core, "chat_turn", lambda history, text, key: f"reply to {text}")
    at = run_app()
    at.chat_input[0].set_value("first").run()
    at.chat_input[0].set_value("second").run()
    assert not at.exception

    column = at.columns[0]
    kinds = [type(child).__name__ for child in column.children.values()]
    assert kinds[0] == "ChatInput"  # the input box is the first thing in the chat column

    texts = [m.markdown[0].value for m in at.chat_message]
    assert texts == ["second", "reply to second", "first", "reply to first"]


def test_only_the_selected_view_runs(monkeypatch):
    import analytics as an
    loads = []
    real = an.load_expenses
    monkeypatch.setattr(an, "load_expenses", lambda: loads.append(1) or real())
    insert_expense("chai", 15, "food", f"{date.today()} 09:00")
    at = run_app()
    assert not at.radio and not loads  # Chat view: no Period radio, no expense load
    go(at, "Analytics")
    assert at.radio and loads


def test_chat_save_clears_the_cache_so_analytics_is_fresh(monkeypatch):
    import core
    insert_expense("chai", 15, "food", f"{date.today()} 09:00")
    at = run_app("Analytics")
    total = lambda: _widget(at.metric, "Total spent").value  # noqa: E731

    assert total() == "₹15"
    insert_expense("auto", 80, "transport", f"{date.today()} 10:00")  # cached: not seen yet
    assert go(at, "Chat") and go(at, "Analytics") and total() == "₹15"

    monkeypatch.setattr(core, "chat_turn", lambda history, text, key: "Saved")
    go(at, "Chat").chat_input[0].set_value("auto 80").run()
    assert go(at, "Analytics") and total() == "₹95"


def test_plan_write_clears_the_cache():
    from helpers import query
    at = run_app("Plan")
    _widget(at.number_input, "Amount (₹)", 1).set_value(5000.0)  # the income form's
    _widget(at.button, "Add income").click().run()
    assert query("SELECT amount_inr FROM income") == [(5000.0,)]
    assert at.dataframe[-1].value["amount_inr"].tolist() == [5000.0]  # redrawn from fresh data


def test_analytics_period_survives_a_view_switch():
    from datetime import timedelta
    insert_expense("chai", 15, "food", f"{date.today()} 09:00")
    at = run_app("Analytics")
    at.radio[0].set_value("Last 90 days").run()
    go(go(at, "Plan"), "Analytics")
    assert at.radio[0].value == "Last 90 days"

    at.radio[0].set_value("Custom").run()
    picked = (date.today() - timedelta(days=5), date.today())
    at.date_input[0].set_value(picked).run()
    go(go(at, "Chat"), "Analytics")
    assert at.radio[0].value == "Custom" and tuple(at.date_input[0].value) == picked
    assert not at.exception
