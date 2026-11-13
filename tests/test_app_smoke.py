"""Loads the real Streamlit app and clicks through every period option."""
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
    assert [t.label for t in at.tabs] == ["Chat", "Analytics", "LLM usage"]


def test_app_loads_with_empty_database():
    at = run_app()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Chat", "Analytics", "LLM usage"]


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
