"""Every model call must be recorded with latency, tokens and outcome."""
from datetime import datetime
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from helpers import FakeResp, count_rows, query, usage

import analytics as an
import core


def fake_client(fn):
    return SimpleNamespace(models=SimpleNamespace(generate_content=fn))


def test_successful_call_is_logged_with_tokens(monkeypatch):
    resp = FakeResp([("add_expenses", {"expenses": []})], usage=usage(1200, 15, 40))
    monkeypatch.setattr(core, "_client", fake_client(lambda **kw: resp))
    core._generate([], purpose="chat")
    row = query("SELECT purpose, status, prompt_tokens, output_tokens, thinking_tokens, "
                "total_tokens, tools_called, attempts FROM llm_calls")[0]
    assert row == ("chat", "ok", 1200, 15, 40, 1255, "add_expenses", 1)


def test_missing_usage_metadata_is_tolerated(monkeypatch):
    monkeypatch.setattr(core, "_client", fake_client(lambda **kw: FakeResp([("out_of_scope", {})])))
    core._generate([])
    assert query("SELECT total_tokens FROM llm_calls")[0][0] == 0


def test_generic_failure_is_logged_and_reraised(monkeypatch):
    def boom(**kw):
        raise ConnectionError("network down")
    monkeypatch.setattr(core, "_client", fake_client(boom))
    with pytest.raises(ConnectionError):
        core._generate([])
    assert query("SELECT status, error FROM llm_calls")[0] == ("error", "ConnectionError")


def test_daily_quota_is_logged_with_its_own_status(monkeypatch):
    def quota(**kw):
        raise genai_errors.ClientError(429, {"error": {
            "message": "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"}})
    monkeypatch.setattr(core, "_client", fake_client(quota))
    with pytest.raises(core.DailyQuotaExceeded):
        core._generate([])
    assert query("SELECT status FROM llm_calls")[0][0] == "quota_daily"


def test_evaluation_calls_are_tagged_eval(monkeypatch):
    resp = FakeResp([("add_expenses", {"expenses": [{"item": "chai"}]})], usage=usage())
    monkeypatch.setattr(core, "_client", fake_client(lambda **kw: resp))
    assert core.extract_expenses("chai 15", datetime(2026, 10, 4, 14, 30)) == [{"item": "chai"}]
    assert query("SELECT purpose FROM llm_calls")[0][0] == "eval"


def test_logging_works_even_if_table_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "never_initialised.db"))
    monkeypatch.setattr(core, "_client",
                        fake_client(lambda **kw: FakeResp([("out_of_scope", {})])))
    core._generate([])
    assert count_rows("llm_calls") == 1


def test_usage_summary_ignores_eval_runs_by_default(monkeypatch):
    resp = FakeResp([("out_of_scope", {})], usage=usage(1000, 10, 0))
    monkeypatch.setattr(core, "_client", fake_client(lambda **kw: resp))
    core._generate([], purpose="chat")
    core._generate([], purpose="chat")
    core._generate([], purpose="eval")
    summary = an.llm_summary(an.load_llm_calls())
    assert summary["calls"] == 2 and summary["calls_today"] == 2
    assert summary["tokens_today"] == 2020 and summary["success_rate"] == 100.0
    assert an.llm_summary(an.load_llm_calls(include_eval=True))["calls"] == 3


def test_usage_summary_on_empty_database():
    assert an.llm_summary(an.load_llm_calls())["calls"] == 0
    assert an.llm_daily(an.load_llm_calls()).empty
