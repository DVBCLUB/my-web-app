"""Create a clean release zip without runtime locks or cache files."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sqlite3
import zipfile


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT.parent / f"{ROOT.name}_{datetime.now():%Y%m%d_%H%M%S}.zip"

EXCLUDED_DIRS = {
    '.vs',
    '__pycache__',
    '.git',
}

EXCLUDED_SUFFIXES = {
    '.pyc',
    '.pyo',
    '.tmp',
    '.log',
    '.zip',
    '.rar',
}

EXCLUDED_NAMES = {
    'accounting.db-wal',
    'accounting.db-shm',
    'Thumbs.db',
    'desktop.ini',
}


def should_skip(path: Path, include_data: bool) -> bool:
    rel = path.relative_to(ROOT)
    parts = set(rel.parts)
    if parts & EXCLUDED_DIRS:
        return True
    if path.name in EXCLUDED_NAMES:
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    if not include_data and rel.parts[:2] == ('PythonApplication1', 'data'):
        return True
    return False


def checkpoint_database() -> None:
    db_path = ROOT / 'PythonApplication1' / 'data' / 'accounting.db'
    if not db_path.exists():
        return
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('PRAGMA wal_checkpoint(FULL)')
        conn.close()
    except sqlite3.DatabaseError:
        # Another running app may still hold the DB; the zip excludes WAL/SHM,
        # and live data is excluded by default.
        pass


def create_zip(output: Path, include_data: bool = False) -> Path:
    checkpoint_database()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in ROOT.rglob('*'):
            if path == output or path.is_dir() or should_skip(path, include_data):
                continue
            zf.write(path, path.relative_to(ROOT))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description='Create clean FasTrack ERP release zip.')
    parser.add_argument('-o', '--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--include-data', action='store_true', help='Include PythonApplication1/data files.')
    args = parser.parse_args()
    output = create_zip(args.output, include_data=args.include_data)
    print(output)


if __name__ == '__main__':
    main()
