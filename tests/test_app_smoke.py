"""Loads the real Streamlit app and clicks through every period option."""
from datetime import date
from pathlib import Path

import pytest
from helpers import insert_expense
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def run_app():
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["authed"] = True
    return at.run()

def test_pin_gate_blocks_until_correct(monkeypatch):
    monkeypatch.setenv("APP_PIN", "123456")
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.tabs  # nothing from the app is rendered
    at.text_input[0].set_value("000000")
    at.button[0].click().run()
    assert not at.tabs
    at.text_input[0].set_value("123456")
    at.button[0].click().run()
    assert [t.label for t in at.tabs] == ["Chat", "Analytics", "Plan", "LLM usage"]


def test_app_loads_with_empty_database():
    at = run_app()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Chat", "Analytics", "Plan", "LLM usage"]


@pytest.mark.parametrize("period", ["This month", "Last 30 days", "Last 90 days",
                                    "All time", "Custom"])
def test_every_period_renders_without_errors(period):
    from datetime import date, timedelta
    for days_ago in (0, 2, 10, 40):
        day = (date.today() - timedelta(days=days_ago)).isoformat()
        insert_expense("chai", 15, "food", f"{day} 09:00")
    at = run_app()
    at.radio[0].set_value(period).run()
    assert not at.exception


def test_llm_usage_tab_renders_with_recorded_calls():
    import time

    from helpers import FakeResp, usage

    import core
    started = time.perf_counter()
    core._log_llm_call("chat", "ok", started, 1, resp=FakeResp([("add_expenses", {})], usage()))
    core._log_llm_call("chat", "error", started, 2, error="ConnectionError")
    at = run_app()
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
    at = run_app()

    # update the amount through the form (the first "Amount (Rs)" is the subscription form's)
    _widget(at.selectbox, "Add or update").set_value("netflix").run()
    _widget(at.number_input, "Amount (Rs)").set_value(799.0)
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
    at = run_app()
    assert not at.exception and not fixed


def test_plan_remove_card_and_auto_tag():
    from helpers import query

    import core
    core.manage_subscription("add", "netflix", amount_inr=649, category="entertainment",
                             day=date.today().day, card_name="HDFC MoneyBack")  # posts today
    at = run_app()
    _widget(at.selectbox, "Add or update").set_value("netflix").run()
    _widget(at.selectbox, "Card").set_value("(remove card)")
    _widget(at.button, "Save subscription").click().run()
    assert query("SELECT card_id, payment_method FROM recurring") == [(None, None)]
    recent = at.tabs[0].dataframe[0].value
    assert list(recent["item"]) == ["netflix (auto)"]


def test_chat_input_is_on_top_and_newest_exchange_comes_first(monkeypatch):
    import core
    monkeypatch.setattr(core, "chat_turn", lambda history, text, key: f"reply to {text}")
    at = run_app()
    at.chat_input[0].set_value("first").run()
    at.chat_input[0].set_value("second").run()
    assert not at.exception

    column = at.tabs[0].columns[0]
    kinds = [type(child).__name__ for child in column.children.values()]
    assert kinds[0] == "ChatInput"  # the input box is the first thing in the chat column

    texts = [m.markdown[0].value for m in at.chat_message]
    assert texts == ["second", "reply to second", "first", "reply to first"]
