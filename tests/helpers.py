"""Shared test helpers: a scripted fake model and small database utilities."""
import itertools
import sqlite3
from contextlib import closing
from types import SimpleNamespace

from google.genai import types

import core

_counter = itertools.count()


class FakeResp:
    """Looks like a Gemini response: function_calls, candidates, usage_metadata."""

    def __init__(self, calls, usage=None):
        self.function_calls = [SimpleNamespace(name=n, args=a) for n, a in calls]
        self.candidates = [SimpleNamespace(content=types.Content(role="model", parts=[]))]
        self.usage_metadata = usage
        self.text = None


def usage(prompt=1200, output=15, thinking=40):
    return SimpleNamespace(prompt_token_count=prompt, candidates_token_count=output,
                           thoughts_token_count=thinking,
                           total_token_count=prompt + output + thinking)


def good_expense(**over):
    e = {"spent_at": "2026-10-03 09:00", "item": "chai", "amount_inr": 15, "category": "food"}
    e.update(over)
    return e


def query(sql, params=()):
    with closing(sqlite3.connect(core.DB_PATH)) as conn:
        return conn.execute(sql, params).fetchall()


def count_rows(table="expenses"):
    return query(f"SELECT COUNT(*) FROM {table}")[0][0]


def insert_expense(item="chai", amount=15, category="food", spent_at="2026-10-03 09:00"):
    with closing(sqlite3.connect(core.DB_PATH)) as conn:
        conn.execute(
            "INSERT INTO expenses (spent_at, item, amount_inr, category, raw_text) "
            "VALUES (?, ?, ?, ?, 'test')", (spent_at, item, amount, category))
        conn.commit()


def turn(text, history=None):
    """One chat turn from a brand-new user (so the rate limit never interferes)."""
    return core.chat_turn(history or [], text, f"user{next(_counter)}")
