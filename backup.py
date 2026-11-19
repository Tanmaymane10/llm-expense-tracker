"""
Nightly backup: consistent SQLite copy -> gzip -> rclone remote, keeping the newest N copies.

    python backup.py      # needs BACKUP_REMOTE (e.g. gcrypt:expense-backups) in .env

Runs from the expense-backup systemd timer (see deploy/). Setup and restore: README.md.
"""
import gzip
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import core  # loads .env and DB_PATH; never creates a Gemini client

PREFIX, SUFFIX = "expenses-", ".db.gz"


def make_backup(out_dir) -> Path:
    """Gzipped, date-stamped copy of the live database. The sqlite backup API gives a
    consistent snapshot even while the app is writing."""
    out_dir = Path(out_dir)
    snapshot = out_dir / "snapshot.db"
    # Read-only: a missing or wrong path fails instead of silently creating an empty DB.
    src = sqlite3.connect(f"file:{core.DB_PATH}?mode=ro", uri=True)
    dst = sqlite3.connect(snapshot)
    try:
        src.backup(dst)
        rows = dst.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        dst.close()
        src.close()
    if rows == 0:  # never rotate good backups out with an empty one
        raise ValueError(f"{core.DB_PATH} has 0 expenses; refusing to back it up.")
    out = out_dir / f"{PREFIX}{date.today():%Y-%m-%d}{SUFFIX}"
    with open(snapshot, "rb") as f, gzip.open(out, "wb") as g:
        shutil.copyfileobj(f, g)
    snapshot.unlink()
    return out


def to_delete(names: list, keep: int) -> list:
    """Our backups beyond the newest `keep`. Date-stamped names sort oldest first."""
    ours = sorted(n for n in names if n.startswith(PREFIX) and n.endswith(SUFFIX))
    return ours[:-keep]


def _rclone(*args) -> str:
    # stderr is not captured, so rclone's own error message lands in the systemd journal
    return subprocess.run(["rclone", *args], check=True, stdout=subprocess.PIPE,
                          text=True).stdout


def main() -> int:
    remote = os.environ.get("BACKUP_REMOTE", "").strip()
    keep = int(os.environ.get("BACKUP_KEEP", "14"))
    if not remote:
        print("BACKUP_REMOTE is not set (e.g. gcrypt:expense-backups).", file=sys.stderr)
        return 1
    if keep < 1:  # never let a bad setting delete every backup
        print("BACKUP_KEEP must be at least 1.", file=sys.stderr)
        return 1
    # Log due subscriptions first, so the snapshot has them. Never blocks the backup, and
    # skipped for a missing file (connecting would create an empty DB).
    if Path(core.DB_PATH).exists():
        try:
            print(f"[backup] posted {core.post_due_recurring()} recurring payment(s)")
        except sqlite3.Error as exc:
            print(f"[backup] recurring catch-up failed: {exc}", file=sys.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        try:
            path = make_backup(tmp)
        except (sqlite3.Error, ValueError) as exc:
            print(f"[backup] not uploaded: {exc}", file=sys.stderr)
            return 1
        _rclone("copy", str(path), remote)
    sep = "" if remote.endswith((":", "/")) else "/"
    old = to_delete(_rclone("lsf", remote).splitlines(), keep)
    for name in old:
        _rclone("deletefile", f"{remote}{sep}{name}")
    print(f"[backup] uploaded {path.name} to {remote}, removed {len(old)} old copies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
