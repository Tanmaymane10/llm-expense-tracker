"""API tests: authentication, validation, behaviour and error handling."""
import pytest
from fastapi.testclient import TestClient
from helpers import FakeResp, good_expense, insert_expense

import api
import core

AUTH = {"X-API-Key": "secret-token"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "secret-token")
    with TestClient(api.app) as c:
        yield c


def post_chat(client, message, **extra):
    return client.post("/chat", json={"message": message, **extra}, headers=AUTH)


# ---------------------------------------------------------------- auth
def test_health_needs_no_auth_and_reports_ok(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert "X-Request-ID" in r.headers


@pytest.mark.parametrize("path", ["/expenses", "/analytics/summary", "/llm/usage"])
def test_protected_get_endpoints_reject_missing_key(client, path):
    assert client.get(path).status_code == 401


def test_chat_rejects_missing_and_wrong_key(client):
    assert client.post("/chat", json={"message": "hi"}).status_code == 401
    r = client.post("/chat", json={"message": "hi"}, headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_api_fails_closed_when_token_not_configured(client, monkeypatch):
    monkeypatch.delenv("API_TOKEN")
    assert client.get("/expenses", headers=AUTH).status_code == 503


# ---------------------------------------------------------------- chat
def test_chat_off_topic_gets_fixed_reply(client, script):
    script([("out_of_scope", {})])
    r = post_chat(client, "who is virat kohli?")
    assert r.status_code == 200 and r.json()["reply"] == core.OUT_OF_SCOPE_MSG


def test_chat_logs_expense_and_it_is_listed(client, script):
    script([("add_expenses", {"expenses": [good_expense(item="vada pav", amount_inr=30)]})])
    assert "Saved" in post_chat(client, "vada pav 30").json()["reply"]
    rows = client.get("/expenses", headers=AUTH).json()
    assert len(rows) == 1 and rows[0]["item"] == "vada pav" and rows[0]["amount_inr"] == 30


def test_chat_validates_input_size(client):
    assert post_chat(client, "").status_code == 422
    assert post_chat(client, "a" * 2001).status_code == 422


def test_long_distress_message_still_gets_support(client):
    r = post_chat(client, "i want to die. " + "x" * 600)
    assert r.status_code == 200 and r.json()["reply"] == core.CRISIS_MSG


def test_chat_returns_502_when_the_model_is_down(client, monkeypatch):
    def broken(*a, **k):
        raise ConnectionError("network down")
    monkeypatch.setattr(core, "_generate", broken)
    r = post_chat(client, "chai 15")
    assert r.status_code == 502 and "network down" not in r.text  # no internals leaked


# ---------------------------------------------------------------- data endpoints
def test_expenses_and_summary_on_empty_database(client):
    assert client.get("/expenses", headers=AUTH).json() == []
    body = client.get("/analytics/summary", headers=AUTH).json()
    assert body["total"] == 0 and body["by_category"] == []


def test_summary_with_data(client):
    insert_expense("chai", 15, "food", "2026-10-03 09:00")
    insert_expense("auto", 80, "transport", "2026-10-03 10:00")
    body = client.get("/analytics/summary?start=2026-10-01&end=2026-10-05", headers=AUTH).json()
    assert body["total"] == 95 and body["transactions"] == 2
    assert {c["category"] for c in body["by_category"]} == {"food", "transport"}
    assert body["monthly"][0]["month"] == "2026-10"


def test_summary_rejects_reversed_dates(client):
    r = client.get("/analytics/summary?start=2026-10-05&end=2026-10-01", headers=AUTH)
    assert r.status_code == 422


def test_expenses_filters_and_limits(client):
    for day in range(1, 6):
        insert_expense("chai", 10, "food", f"2026-10-0{day} 09:00")
    r = client.get("/expenses?limit=2&start=2026-10-02", headers=AUTH).json()
    assert len(r) == 2 and r[0]["spent_at"].startswith("2026-10-05")
    assert client.get("/expenses?limit=0", headers=AUTH).status_code == 422


def test_llm_usage_endpoint(client, script, monkeypatch):
    resp = FakeResp([("out_of_scope", {})])
    monkeypatch.setattr(core, "_client", type("C", (), {"models": type(
        "M", (), {"generate_content": staticmethod(lambda **kw: resp)})()})())
    post_chat(client, "who is virat kohli?")
    body = client.get("/llm/usage?days=7", headers=AUTH).json()
    assert body["calls"] == 1 and body["success_rate"] == 100.0
