import os

os.environ.setdefault("GEMINI_API_KEY", "test-key")  # the real client is never created in tests

import pytest  # noqa: E402
import streamlit as st  # noqa: E402
from helpers import FakeResp  # noqa: E402

import core  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_state(tmp_path, monkeypatch):
    """Every test gets its own empty database and a clean rate limiter."""
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(core, "RATE_LIMIT_MESSAGES", 5)
    core._hits.clear()
    monkeypatch.setattr(core, "_thinking_idx", {})  # per-process memory of thinking configs
    core._on_backup.set(False)
    core.init_db()
    st.cache_data.clear()  # the app caches reads per process; start each test cold


@pytest.fixture
def script(monkeypatch):
    """script(r1, r2, ...) makes the model return those tool-call lists in order.
    Returns a log of the message lists it was called with."""
    def install(*responses):
        queue, log = list(responses), []

        def fake(contents, now=None, purpose="chat"):
            log.append(list(contents))  # snapshot: the app keeps appending to the real list
            return FakeResp(queue.pop(0)) if queue else FakeResp([])

        monkeypatch.setattr(core, "_generate", fake)
        return log
    return install
