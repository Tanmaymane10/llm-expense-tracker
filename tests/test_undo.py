"""Undo removes exactly the rows one save created, and never an edited row silently."""
from helpers import count_rows, good_expense, insert_expense, query, turn

import core


def _save(*items):
    ids = []
    token = core.saved_ids.set(ids)
    try:
        core.add_expenses([good_expense(item=i) for i in items], "t")
    finally:
        core.saved_ids.reset(token)
    return core.expense_snapshot(ids)


def test_undo_deletes_only_its_own_ids():
    insert_expense("older")
    first = _save("chai", "tea")
    second = _save("samosa", "auto")
    assert [r[0] for r in second] == [4, 5]
    assert core.undo_expenses(second) == (2, 0, 0)
    assert query("SELECT id, item FROM expenses ORDER BY id") == [
        (1, "older"), (2, "chai"), (3, "tea")]
    assert [r[0] for r in first] == [2, 3]


def test_edited_row_is_kept_and_reported():
    snap = _save("chai", "tea")
    core.update_expense(snap[0][0], amount_inr=99)
    assert core.undo_expenses(snap) == (1, 1, 0)
    assert query("SELECT item, amount_inr FROM expenses") == [("chai", 99.0)]


def test_already_deleted_row_is_reported_as_gone():
    snap = _save("chai", "tea")
    core.delete_expense(snap[1][0])
    assert core.undo_expenses(snap) == (1, 0, 1) and count_rows() == 0


def test_failed_save_collects_no_ids():
    ids = []
    token = core.saved_ids.set(ids)
    try:
        core.add_expenses([good_expense(), good_expense(amount_inr=0)], "t")
    except ValueError:
        pass
    finally:
        core.saved_ids.reset(token)
    assert ids == [] and count_rows() == 0


def test_model_and_local_saves_fill_saved_ids(script):
    script([("add_expenses", {"expenses": [good_expense(item="perfume")]})])
    ids = []
    token = core.saved_ids.set(ids)
    try:
        turn("perfume 3924")
        insert_expense("chai", 20, "food")
        insert_expense("chai", 20, "food")
        turn("chai 15")  # local fast path
    finally:
        core.saved_ids.reset(token)
    assert ids == [1, 4]


def test_unset_collector_changes_nothing():
    core.add_expenses([good_expense()], "t")
    assert core.saved_ids.get() is None and count_rows() == 1


# ---------------------------------------------------------------- in the app
def test_undo_button_after_a_chat_save(monkeypatch):
    from test_app_smoke import _widget, run_app

    def fake_turn(history, text, key):
        return core.add_expenses([good_expense(item=text)], text)
    monkeypatch.setattr(core, "chat_turn", fake_turn)
    insert_expense("older")
    at = run_app()
    at.chat_input[0].set_value("chai").run()
    at.chat_input[0].set_value("tea").run()  # a new save replaces the first Undo
    undo = [b for b in at.button if b.label.startswith("Undo")]
    assert [b.label for b in undo] == ["Undo (1 entry)"]
    undo[0].click().run()
    assert query("SELECT item FROM expenses ORDER BY id") == [("older",), ("chai",)]
    assert not [b for b in at.button if b.label.startswith("Undo")]
    assert not at.exception
    assert _widget(at.button_group, "Quick add")  # the panel is still there


def test_undo_disappears_after_two_minutes(monkeypatch):
    from test_app_smoke import run_app
    monkeypatch.setattr(core, "chat_turn",
                        lambda h, text, key: core.add_expenses([good_expense()], text))
    at = run_app()
    at.chat_input[0].set_value("chai").run()
    at.session_state["undo"] = {**at.session_state["undo"], "at": 0}  # saved long ago
    at.run()
    assert not [b for b in at.button if b.label.startswith("Undo")] and count_rows() == 1
