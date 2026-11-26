"""Backup model: only after 503 on every main attempt or a daily-quota error, chat only, and
bounded per message."""
import time
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from helpers import FakeResp, count_rows, good_expense, query, turn

import analytics as an
import core

MAIN, BACKUP = "main-model", "backup-model"
REAL_SLEEP = time.sleep  # core.time is the global time module; AppTest needs the real one


def busy():
    return genai_errors.ServerError(503, {"error": {"message": "overloaded"}})


def limited():
    return genai_errors.ClientError(429, {"error": {"message": "per minute"}})


def daily():
    return genai_errors.ClientError(429, {"error": {
        "message": "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"}})


def bad_request():
    return genai_errors.ClientError(400, {"error": {"message": "invalid argument"}})


@pytest.fixture
def models(monkeypatch):
    """models(main=[...], backup=[...]): each list is what that model does per call, in order:
    an exception to raise or a list of tool calls to answer with (the last one repeats).
    Returns the list of models called, in order."""
    monkeypatch.setattr(core, "MODEL", MAIN)
    monkeypatch.setattr(core, "FALLBACK_MODEL", BACKUP)
    monkeypatch.setattr(core.time, "sleep", lambda s: None)
    called = []

    def install(main, backup=()):
        plans = {MAIN: list(main), BACKUP: list(backup)}

        def generate_content(model, contents, config):
            called.append(model)
            plan = plans[model]
            step = plan.pop(0) if len(plan) > 1 else (plan[0] if plan else [])
            if isinstance(step, Exception):
                raise step
            return FakeResp(step)
        monkeypatch.setattr(core, "_client", SimpleNamespace(
            models=SimpleNamespace(generate_content=generate_content)))
        return called
    return install


SAVE = [("add_expenses", {"expenses": [good_expense()]})]


def test_three_503s_then_backup_answers(models):
    notes = []
    token = core.status_hook.set(notes.append)
    try:
        called = models([busy(), busy(), busy()], [SAVE])
        assert turn("chai 15").startswith("Saved:")
    finally:
        core.status_hook.reset(token)
    assert called == [MAIN, MAIN, MAIN, BACKUP] and count_rows() == 1
    assert query("SELECT model, status, attempts FROM llm_calls ORDER BY id") == [
        (MAIN, "error", 3), (BACKUP, "ok", 1)]
    assert notes[-1] == f"Gemini is busy, trying the backup model ({BACKUP})..."


def test_daily_quota_goes_to_backup_at_once(models):
    called = models([daily()], [SAVE])
    assert turn("chai 15").startswith("Saved:")
    assert called == [MAIN, BACKUP]
    assert query("SELECT model, status FROM llm_calls ORDER BY id") == [
        (MAIN, "quota_daily"), (BACKUP, "ok")]


def test_backup_daily_quota_gives_the_quota_reply(models):
    called = models([daily()], [daily()])
    assert turn("chai 15") == core.QUOTA_MSG and called == [MAIN, BACKUP]


def test_backup_retries_once_then_gives_up(models):
    called = models([busy()], [busy()])
    with pytest.raises(genai_errors.ServerError):
        turn("chai 15")
    assert called == [MAIN] * 3 + [BACKUP] * 2 and count_rows() == 0


@pytest.mark.parametrize("main", [
    [bad_request()],                      # 400
    [limited(), limited(), limited()],    # per-minute 429 on every attempt
    [limited(), busy(), busy()],          # a 429/503 mix is not "503 on all 3"
    [busy(), busy(), bad_request()],
    [ConnectionError("down")],            # network error
])
def test_backup_is_never_called_for_other_errors(models, main):
    called = models(main, [SAVE])
    with pytest.raises((genai_errors.APIError, ConnectionError)):
        turn("chai 15")
    assert BACKUP not in called


@pytest.mark.parametrize("answer", [
    [("out_of_scope", {})],
    [("add_expenses", {"expenses": [good_expense(amount_inr=-5)]})],  # validation error
])
def test_backup_is_never_called_when_the_main_model_answers(models, answer):
    called = models([answer, [("reply_to_user", {"message": "That amount looks wrong."})]],
                    [SAVE])
    turn("hello")
    assert BACKUP not in called and count_rows() == 0


def test_backup_is_never_called_for_eval(models):
    from datetime import datetime
    called = models([busy()], [SAVE])
    with pytest.raises(genai_errors.ServerError):
        core.extract_expenses("chai 15", datetime(2026, 10, 4, 14, 30))
    assert called == [MAIN] * 3


def test_backup_is_never_called_when_it_is_the_main_model(models, monkeypatch):
    called = models([busy()], [SAVE])
    monkeypatch.setattr(core, "FALLBACK_MODEL", MAIN)
    with pytest.raises(genai_errors.ServerError):
        turn("chai 15")
    assert called == [MAIN] * 3


def test_next_message_starts_on_the_main_model_again(models):
    called = models([busy(), busy(), busy(), SAVE], [SAVE])
    turn("chai 15")
    turn("tea 10")
    assert called == [MAIN] * 3 + [BACKUP, MAIN]


def test_worst_case_calls_per_message_is_bounded(models):
    """Main always 503; the backup keeps asking for more tool steps until the step cap."""
    loop = [("list_recent_expenses", {})]
    called = models([busy()], [loop])
    assert "too many steps" in turn("loop forever")
    assert called == [MAIN] * 3 + [BACKUP] * core.MAX_TOOL_STEPS  # sticky after step 1
    assert len(called) <= core.MAX_CALLS_PER_MESSAGE


def _think():
    return genai_errors.ClientError(400, {"error": {"message": "thinking not supported"}})


def test_early_switch_with_retries_stays_under_the_bound(models):
    loop = [("list_recent_expenses", {})]
    # step 1 switches; every backup step needs its retry; both reject two thinking configs
    backup = [_think(), _think()] + [busy(), loop] * core.MAX_TOOL_STEPS
    called = models([_think(), _think(), busy(), busy(), busy()], backup)
    assert "too many steps" in turn("loop forever")
    assert len(called) == 5 + 4 + 2 * (core.MAX_TOOL_STEPS - 1) == 17
    assert len(called) <= core.MAX_CALLS_PER_MESSAGE


def test_late_switch_is_the_worst_case_and_equals_the_bound(models):
    """Main answers only on its 3rd attempt for steps 1-4, then fails step 5 completely."""
    loop = [("list_recent_expenses", {})]
    main = [_think(), _think(), busy(), busy(), loop] + [busy(), busy(), loop] * 3 + [busy()]
    called = models(main, [_think(), _think(), busy(), loop])
    assert "too many steps" in turn("loop forever")
    assert len(called) == core.MAX_CALLS_PER_MESSAGE == 21
    assert called[-4:] == [BACKUP] * 4
    assert core.THINKING_BUMPS == len(core._thinking_candidates()) - 1


def test_usage_view_counts_backup_calls(models, monkeypatch):
    from test_app_smoke import _widget, run_app
    models([busy(), busy(), busy()], [SAVE])
    turn("chai 15")
    df = an.load_llm_calls()
    assert list(df["model"]) == [MAIN, BACKUP]
    monkeypatch.setattr(core.time, "sleep", REAL_SLEEP)
    at = run_app("Usage")
    assert _widget(at.metric, "Backup model calls").value == "1"


def test_usage_view_shows_no_backup_calls_when_backup_is_the_main_model(models, monkeypatch):
    from test_app_smoke import _widget, run_app
    models([SAVE])
    monkeypatch.setattr(core, "FALLBACK_MODEL", MAIN)
    turn("chai 15")
    monkeypatch.setattr(core.time, "sleep", REAL_SLEEP)
    assert _widget(run_app("Usage").metric, "Backup model calls").value == "0"


def test_local_and_quick_add_rows_log_no_model():
    core.quick_add("chai", 15, "food")
    assert query("SELECT model FROM llm_calls") == [("none",)]
