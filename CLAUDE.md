# CLAUDE.md

Personal INR expense tracker "QORVIAN": Streamlit UI + Gemini function calling + SQLite,
running on an Oracle free VM. One user. Read this first; deeper history is in
`docs/PLAN.md` and `docs/plan-*.md` (both gitignored, local only; consult only when relevant).

## Layout
- `core.py`: DB schema/migrations (`init_db`), validators, tools (`add_expenses`,
  `register_card`, `manage_subscription`, `get_status`, ...), card cycles, `chat_turn`.
- `app.py`: Streamlit views (Home, Analytics, Plan, Chat) and all CSS (`THEME_CSS`).
- `ui.py`: pure HTML builders for Home/Analytics cards. Escape every data value with `e()`.
- `analytics.py`, `api.py` (FastAPI), `auth.py` (6-digit PIN gate, fails closed),
  `backup.py` (rclone crypt to Google Drive), `weekly_digest.py` (Telegram), `eval.py`.
- `deploy/`: systemd units for backup (nightly 02:30 IST) and digest (Sun 23:00 IST).
- `tests/`: pytest, temp DBs per test; `test_app_smoke.py` drives Streamlit via AppTest.

## Commands (Windows laptop, Git Bash)
- Lint: `.venv/Scripts/ruff check .` (line length 100). Tests: `.venv/Scripts/python -m pytest -q`
  (~365 tests, ~2 min). CI runs `uv run ruff check .` and `uv run pytest`.
- Demo app: `EXPENSE_DB=<scratch copy>.db streamlit run app.py`. Never point it at the real
  `expenses.db`: `init_db` migrates whatever DB it opens. The PIN gate blocks headless
  screenshots; render `ui.*` HTML to a file and screenshot that with headless Chrome.

## Working rules (from the user)
- Run ruff + full pytest before every commit. Commit locally; push and deploy only when asked.
- Show the diff and stop before any deploy.
- Back up the DB before any schema change or deploy. Never edit live data unless asked;
  read-only queries (`file:...?mode=ro`) are fine.
- Migrations are additive only (`CREATE TABLE IF NOT EXISTS`, `_add_column`); never drop rows.

## Deploy (only when the user says go)
`ssh expense` (app dir `/home/ubuntu/app`, service `app`, port 8501 on localhost):
1. `sudo systemctl start expense-backup` and check `journalctl -u expense-backup -n 8`.
   Same-day uploads share one name (`expenses-YYYY-MM-DD.db.gz`) and overwrite each other.
2. For schema changes, also a named copy via Python's sqlite3 `backup()`, e.g.
   `expenses-pre-<change>.db`, then check its integrity and row count.
3. `git pull --ff-only`; `pip install` only if requirements changed.
4. `sudo systemctl restart app`; check `is-active` and HTTP 200.
5. `init_db` runs on the first browser session, not at startup. To apply a migration right
   away: `.venv/bin/python -c "import core; core.init_db()"` in the app dir (after backups).

## Credit card model (easy to misread)
- `credit_cards.statement_day` is the **last day included in a bill**; the bill is generated
  the next day. The UI labels it "Last day of billing cycle". Days 29-31 clamp to month-end.
- `card_cycle()`: closed cycle `[prev_start, prev_end]` inclusive, current cycle starts
  `prev_end + 1`. With a `due_day` set, due follows it (≤ statement day means next month).
  Without one, pay-by = last day of the month the bill is generated in.
- Paid flag = `paid_through >= prev_end` (or nothing due). Marking paid (Plan tab button or
  chat `register_card(bill_paid=True)`) sets `paid_through` and inserts into `card_payments`
  (card_id, cycle_start, cycle_end, amount, paid_on) in one transaction. Plan's "Undo paid"
  (`set_paid_through`) reverts both. Chat has no undo. `due_day=0` clears the due day.
- Home card row: "Statement due ₹X · pay by <date>" while unpaid, "Unbilled ₹Y since <bill
  date>", bar = X + Y vs limit. No Mark-paid button on Home (removed on purpose).

## Current state (2026-11-27)
- `main` at `a8d71d0`, pushed and deployed. Recent work: card statement/unbilled display,
  `card_payments` table, month-end pay-by, Plan cycle preview (commits `78890bb`, `31ee4fc`,
  `a8d71d0`). Before that: Phase 3 redesign, bottom nav fixes (`3350384`).
- Live DB after deploy: 78 expenses, integrity ok, `card_payments` created (empty).
  Backups: Drive `expenses-2026-11-27.db.gz`; VM `expenses-pre-card-payments.db` and
  `expenses-pre-phase3.db`.
- `systemctl daemon-reload` done; all units clean.

## Open items
- User to set card cycle days in Plan → Cards: HDFC MoneyBack 13, Swiggy HDFC 13, Slice UPI 20,
  SBI Cashback 21 (already), and tick "Pay by month-end" on each (all four still have a due
  day stored: 2, 2, 11, 2). SBI and Slice were marked paid through October, so November
  statements may show unpaid after the change.
- Deferred: Home card sort puts cards without dates above quiet (paid, no spend) cards.
- Not yet checked on a real phone: the new card rows and the Plan cycle preview.
- Older open items (eval runs, subscriptions to enter, cleanup) are listed in `docs/PLAN.md`.
