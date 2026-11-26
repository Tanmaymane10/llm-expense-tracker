"""Loads the real Streamlit app and clicks through every period option."""
from datetime import date
from pathlib import Path

import pytest
from helpers import insert_expense
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


VIEWS = ["Home", "Analytics", "Plan", "Usage"]


def run_app(view="Home"):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["authed"] = True
    at.run()
    return go(at, view) if view != "Home" else at


def go(at, view):
    """Switch view like a user: the bottom nav, or Home's "View all" for the full list."""
    if view == "All":
        go(at, "Home").button(key="view_all").click().run()
    else:
        at.button(key=f"nav_{view}").click().run()
    return at


def nav_keys(at):
    return [b.key for b in at.button if b.key and b.key.startswith("nav_")]


def active_view(at):
    return [b.label for b in at.button if b.key and b.key.startswith("nav_")
            and b.proto.type == "primary"]

def test_pin_gate_blocks_until_correct(monkeypatch):
    monkeypatch.setenv("APP_PIN", "123456")
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not nav_keys(at)  # nothing from the app is rendered
    at.text_input[0].set_value("000000")
    at.button[0].click().run()
    assert not nav_keys(at)
    at.text_input[0].set_value("123456")
    at.button[0].click().run()
    assert active_view(at) == ["Home"]


def test_app_loads_with_empty_database():
    at = run_app()
    assert not at.exception
    assert nav_keys(at) == ["nav_Home", "nav_Analytics", "nav_add", "nav_Plan", "nav_Usage"]
    assert active_view(at) == ["Home"]
    for view in VIEWS:
        assert not go(at, view).exception and active_view(at) == [view]


@pytest.mark.parametrize("period", ["Month", "30 days", "90 days", "Custom"])
def test_every_period_renders_without_errors(period):
    from datetime import date, timedelta
    for days_ago in (0, 2, 10, 40):
        day = (date.today() - timedelta(days=days_ago)).isoformat()
        insert_expense("chai", 15, "food", f"{day} 09:00")
    at = run_app("Analytics")
    period_control(at).set_value(period).run()
    assert not at.exception


def test_llm_usage_tab_renders_with_recorded_calls():
    import time

    from helpers import FakeResp, usage

    import core
    started = time.perf_counter()
    core._log_llm_call("chat", "ok", started, 1, resp=FakeResp([("add_expenses", {})], usage()))
    core._log_llm_call("chat", "error", started, 2, error="ConnectionError")
    at = run_app("Usage")
    assert not at.exception
    labels = [m.label for m in at.metric]
    assert "Calls today" in labels and "Success rate" in labels


def period_control(at):
    return at.button_group(key="period")


def _walk(node):
    """Every element under node, in page order."""
    for child in getattr(node, "children", {}).values():
        yield child
        yield from _walk(child)


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
    recent = go(at, "All").dataframe[0].value  # the editable recent-entries table
    assert list(recent["item"]) == ["netflix"] and list(recent["auto"]) == [True]


def test_chat_input_is_on_top_and_newest_exchange_comes_first(monkeypatch):
    import core
    monkeypatch.setattr(core, "chat_turn", lambda history, text, key: f"reply to {text}")
    at = run_app()
    at.chat_input[0].set_value("first").run()
    at.chat_input[0].set_value("second").run()
    assert not at.exception

    order = [type(n).__name__ for n in _walk(at.main)]
    assert order.index("ChatInput") < order.index("ChatMessage")  # input above the replies

    texts = [m.markdown[0].value for m in at.chat_message]
    assert texts == ["second", "reply to second", "first", "reply to first"]


def test_only_the_selected_view_runs(monkeypatch):
    import analytics as an
    loads = []
    real = an.load_expenses
    monkeypatch.setattr(an, "load_expenses", lambda: loads.append(1) or real())
    insert_expense("chai", 15, "food", f"{date.today()} 09:00")
    at = run_app()
    assert "period" not in [b.key for b in at.button_group] and not loads  # Home: no full load
    go(at, "Analytics")
    assert at.button_group(key="period") and loads


def test_chat_save_clears_the_cache_so_analytics_is_fresh(monkeypatch):
    import core
    insert_expense("chai", 15, "food", f"{date.today()} 09:00")
    at = run_app("Analytics")
    total = lambda: _widget(at.metric, "Total out").value  # noqa: E731

    assert total() == "₹15"
    insert_expense("auto", 80, "transport", f"{date.today()} 10:00")  # cached: not seen yet
    assert go(at, "Home") and go(at, "Analytics") and total() == "₹15"

    monkeypatch.setattr(core, "chat_turn", lambda history, text, key: "Saved")
    go(at, "Home").chat_input[0].set_value("auto 80").run()
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
    period_control(at).set_value("90 days").run()
    go(go(at, "Plan"), "Analytics")
    assert period_control(at).value == "90 days"

    period_control(at).set_value("Custom").run()
    picked = (date.today() - timedelta(days=5), date.today())
    at.date_input[0].set_value(picked).run()
    go(go(at, "Home"), "Analytics")
    assert period_control(at).value == "Custom" and tuple(at.date_input[0].value) == picked
    assert not at.exception


XSS = "<script>alert(1)</script>"


def test_home_escapes_data_in_html():
    import core
    core.register_card("HDFC MoneyBack", statement_day=1, due_day=20, credit_limit=1000)
    core.add_expenses([{"spent_at": f"{date.today()} 09:00", "item": XSS, "amount_inr": 15,
                        "category": "food", "payment_method": "credit_card",
                        "card_name": "HDFC MoneyBack"}], "t")
    at = run_app()
    bodies = " ".join(h.proto.body for h in at.get("html"))
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in bodies and "<script" not in bodies
    assert not at.exception


def test_lock_button_relocks(monkeypatch):
    monkeypatch.setenv("APP_PIN", "123456")
    at = run_app()
    at.button(key="lock").click().run()
    assert not nav_keys(at) and at.text_input[0].label == "Enter your 6-digit PIN"


def test_plan_saves_day_to_day_target_and_limit():
    import core
    at = run_app("Plan")
    assert any("applies to past months" in c.value for c in at.caption)
    _widget(at.number_input, "Target (₹)").set_value(7000.0)
    _widget(at.button, "Save target and limit").click().run()  # target must be below limit
    assert at.error and core.get_d2d_limits() == (5000, 7000)
    _widget(at.number_input, "Target (₹)").set_value(6000.0)
    _widget(at.number_input, "Limit (₹)").set_value(9000.0)
    _widget(at.button, "Save target and limit").click().run()
    assert core.get_d2d_limits() == (6000, 9000) and not at.exception
    labels = at.dataframe[0].value["label"].tolist()
    assert labels[-1] == "Total out budget" and "Investment" in labels
