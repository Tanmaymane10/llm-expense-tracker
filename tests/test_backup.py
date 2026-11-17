"""Backup: the copy must restore to the same data, and pruning must never touch other files."""
import gzip
import sqlite3
from contextlib import closing

from helpers import insert_expense

import backup


def test_backup_restores_to_the_same_rows(tmp_path):
    insert_expense("chai", 15)
    insert_expense("auto", 80, "transport")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    out = backup.make_backup(out_dir)

    assert out.name.startswith("expenses-") and out.name.endswith(".db.gz")
    assert [p.name for p in out_dir.iterdir()] == [out.name]  # temp snapshot cleaned up
    restored = tmp_path / "restored.db"
    restored.write_bytes(gzip.decompress(out.read_bytes()))
    with closing(sqlite3.connect(restored)) as conn:
        rows = conn.execute("SELECT item, amount_inr FROM expenses ORDER BY id").fetchall()
    assert rows == [("chai", 15), ("auto", 80)]


def test_prune_keeps_newest_and_ignores_other_files():
    names = [f"expenses-2026-11-{d:02d}.db.gz" for d in (3, 1, 5, 2, 4)] + ["notes.txt"]
    assert backup.to_delete(names, 3) == ["expenses-2026-11-01.db.gz",
                                          "expenses-2026-11-02.db.gz"]
    assert backup.to_delete(names[:2], 3) == []


def test_main_uploads_then_prunes_old_copies(monkeypatch):
    insert_expense()
    calls = []

    def fake_rclone(*args):
        calls.append(args)
        if args[0] == "lsf":
            return "\n".join(f"expenses-2026-11-{d:02d}.db.gz" for d in range(1, 5)) + "\n"
        return ""

    monkeypatch.setattr(backup, "_rclone", fake_rclone)
    monkeypatch.setenv("BACKUP_REMOTE", "gcrypt:expense-backups")
    monkeypatch.setenv("BACKUP_KEEP", "2")

    assert backup.main() == 0
    assert calls[0][0] == "copy" and calls[0][2] == "gcrypt:expense-backups"
    assert calls[2:] == [("deletefile", "gcrypt:expense-backups/expenses-2026-11-01.db.gz"),
                         ("deletefile", "gcrypt:expense-backups/expenses-2026-11-02.db.gz")]


def _no_rclone(*args):
    raise AssertionError("rclone must not be called")


def test_missing_db_path_fails_without_creating_a_file(tmp_path, monkeypatch):
    missing = tmp_path / "nope" / "expenses.db"
    monkeypatch.setattr(backup.core, "DB_PATH", str(missing))
    monkeypatch.setattr(backup, "_rclone", _no_rclone)
    monkeypatch.setenv("BACKUP_REMOTE", "gcrypt:expense-backups")
    assert backup.main() == 1
    assert not missing.exists()


def test_empty_database_is_not_uploaded(monkeypatch):
    monkeypatch.setattr(backup, "_rclone", _no_rclone)  # fixture DB has tables but 0 expenses
    monkeypatch.setenv("BACKUP_REMOTE", "gcrypt:expense-backups")
    assert backup.main() == 1


def test_main_refuses_bad_settings_without_calling_rclone(monkeypatch):
    monkeypatch.setattr(backup, "_rclone", lambda *a: (_ for _ in ()).throw(AssertionError))
    monkeypatch.delenv("BACKUP_REMOTE", raising=False)
    assert backup.main() == 1
    monkeypatch.setenv("BACKUP_REMOTE", "gcrypt:expense-backups")
    monkeypatch.setenv("BACKUP_KEEP", "0")
    assert backup.main() == 1
