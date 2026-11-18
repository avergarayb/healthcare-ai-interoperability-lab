"""Copy one SQLite file to another directory and read its ledger schema version."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def copy_sqlite(source: Path, destination_dir: Path) -> Path:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    destination_dir.mkdir(parents=True, exist_ok=True)
    target = (destination_dir / source.name).resolve()
    if target == source or destination_dir.resolve() == source.parent:
        raise ValueError("backup_overlaps_source")
    source_uri = source.as_uri() + "?mode=ro"
    source_conn = sqlite3.connect(source_uri, uri=True)
    dest_conn = sqlite3.connect(target)
    try:
        source_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        source_conn.close()
    return target


def schema_version(path: Path) -> int:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA query_only=ON")
        row = connection.execute(
            "SELECT schema_version FROM aip_store WHERE singleton=1"
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise ValueError("schema_unreadable")
    return int(row[0])


def main() -> None:
    if len(sys.argv) == 4 and sys.argv[1] == "copy":
        print(copy_sqlite(Path(sys.argv[2]), Path(sys.argv[3])))
        return
    if len(sys.argv) == 3 and sys.argv[1] == "version":
        print(schema_version(Path(sys.argv[2])))
        return
    raise SystemExit("usage: sqlite_backup.py copy SOURCE DESTDIR | version PATH")


if __name__ == "__main__":
    main()
