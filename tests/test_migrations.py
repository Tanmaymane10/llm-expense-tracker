"""Migrations: init_db() must upgrade old databases in place and never change existing rows."""
import sqlite3
from contextlib import closing

import pytest
from helpers import query

import core

# The schema as it was before payment methods and cards (first release).
OLDEST = """
CREATE TABLE expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, spent_at TEXT NOT NULL,
    item TEXT NOT NULL, amount_inr REAL NOT NULL, category TEXT NOT NULL, raw_text TEXT);
INSERT INTO expenses (spent_at, item, amount_inr, category, raw_text) VALUES
    ('2026-10-01 09:00', 'chai', 15, 'food', 'chai 15'),
    ('2026-10-02 18:30', 'auto', 80, 'transport', 'auto 80');
"""

# The schema running on the server before this change (cards, before budgets/income/recurring).
CARDS_ERA = """
CREATE TABLE expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, spent_at TEXT NOT NULL,
    item TEXT NOT NULL, amount_inr REAL NOT NULL, category TEXT NOT NULL, raw_text TEXT,
    payment_method TEXT, card_id INTEGER REFERENCES credit_cards(id));
CREATE TABLE credit_cards (id INTEGER PRIMARY KEY AUTOINCREMENT, card_name TEXT NOT NULL UNIQUE);
INSERT INTO credit_cards (card_name) VALUES ('HDFC MoneyBack'), ('Axis Flipkart');
INSERT INTO expenses (spent_at, item, amount_inr, category, raw_text, payment_method, card_id)
VALUES ('2026-10-01 09:00', 'chai', 15, 'food', 'chai 15', NULL, NULL),
       ('2026-10-16 14:30', 'perfume', 3924, 'shopping', 'perfume', 'credit_card', 1),
       ('2026-10-17 11:00', 'lunch', 250, 'food', 'lunch upi', 'upi', NULL);
"""

NEW_TABLES = {"budgets", "income", "recurring", "llm_calls", "credit_cards", "card_payments"}


def _make_old_db(path, script):
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(script)
        conn.commit()


def _rows(table):
    return query(f"SELECT * FROM {table} ORDER BY id")


def _columns(table):
    return {r[1] for r in query(f"PRAGMA table_info({table})")}


@pytest.mark.parametrize("script", [OLDEST, CARDS_ERA], ids=["oldest", "cards_era"])
def test_old_database_is_upgraded_without_touching_rows(tmp_path, monkeypatch, script):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "old.db"))
    _make_old_db(core.DB_PATH, script)
    old_tables = {r[0] for r in query("SELECT name FROM sqlite_master WHERE type='table'")}
    before = {t: _rows(t) for t in old_tables & {"expenses", "credit_cards"}}

    core.init_db()
    core.init_db()  # running it again must be a no-op

    for table, rows in before.items():
        n_old_cols = len(rows[0])
        assert [r[:n_old_cols] for r in _rows(table)] == rows, table  # old values unchanged
    tables = {r[0] for r in query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert NEW_TABLES <= tables
    assert {"payment_method", "card_id", "recurring_id"} <= _columns("expenses")
    assert {"statement_day", "due_day", "credit_limit", "last_reminded_on",
            "paid_through"} <= _columns("credit_cards")
    assert query("SELECT recurring_id FROM expenses") == [(None,)] * len(before["expenses"])
    assert query("PRAGMA journal_mode")[0][0] == "wal"


def test_existing_cards_are_not_reseeded(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "old.db"))
    _make_old_db(core.DB_PATH, CARDS_ERA)
    core.init_db()
    assert core.list_cards() == ["HDFC MoneyBack", "Axis Flipkart"]


def test_unique_index_blocks_only_duplicate_recurring_posts():
    insert = ("INSERT INTO expenses (spent_at, item, amount_inr, category, recurring_id) "
              "VALUES ('2026-11-05 09:00', 'netflix', 649, 'entertainment', ?)")
    with closing(core.get_conn()) as conn:
        conn.execute(insert, (None,))
        conn.execute(insert, (None,))  # manual entries: same time is fine
        conn.execute(insert, (1,))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(insert, (1,))  # same rule, same date: rejected
        conn.commit()
    assert query("SELECT COUNT(*) FROM expenses")[0][0] == 3


def test_connections_wait_instead_of_failing_when_busy():
    with closing(core.get_conn()) as conn:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
