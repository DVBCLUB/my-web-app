"""Lightweight repository audit for FT ERP.

Run from repository root:
    python tools/repo_audit.py
    python tools/repo_audit.py --fail-on-large

This script reports large files and large Python modules so refactor work can
stay focused. It uses only the Python standard library.
"""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules"}
LARGE_FILE_BYTES = 1_000_000
LARGE_PY_LINES = 800
ALLOWED_LARGE_PY = {
    # Legacy monolith. Target: shrink gradually via routes/ and modules/.
    "PythonApplication1/web_app.py",
}
ALLOWED_LARGE_FILES = {
    # Seed/demo database. Do not delete without a data migration plan.
    "PythonApplication1/data/accounting.db",
}


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def iter_files():
    for path in ROOT.rglob("*"):
        if path.is_file() and not should_skip(path.relative_to(ROOT)):
            yield path


def count_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    except Exception:
        return 0


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit FT ERP repository size and module growth.")
    parser.add_argument("--fail-on-large", action="store_true", help="Exit non-zero when new oversized files/modules are found.")
    args = parser.parse_args()

    files = list(iter_files())
    large_files = sorted(
        [(p, p.stat().st_size) for p in files if p.stat().st_size >= LARGE_FILE_BYTES],
        key=lambda item: item[1],
        reverse=True,
    )
    large_python = sorted(
        [(p, count_lines(p)) for p in files if p.suffix == ".py" and count_lines(p) >= LARGE_PY_LINES],
        key=lambda item: item[1],
        reverse=True,
    )

    print("FT ERP repo audit")
    print(f"Root: {ROOT}")
    print(f"Files scanned: {len(files)}")

    print("\nLarge files >= 1MB:")
    if large_files:
        for path, size in large_files[:30]:
            marker = "allowed" if rel(path) in ALLOWED_LARGE_FILES else "review"
            print(f"- {rel(path)}: {size / 1024 / 1024:.2f} MB [{marker}]")
    else:
        print("- None")

    print("\nLarge Python modules >= 800 lines:")
    if large_python:
        for path, lines in large_python[:30]:
            marker = "legacy" if rel(path) in ALLOWED_LARGE_PY else "review"
            print(f"- {rel(path)}: {lines} lines [{marker}]")
    else:
        print("- None")

    if args.fail_on_large:
        unexpected_files = [path for path, _ in large_files if rel(path) not in ALLOWED_LARGE_FILES]
        unexpected_py = [path for path, _ in large_python if rel(path) not in ALLOWED_LARGE_PY]
        if unexpected_files or unexpected_py:
            print("\nAudit failed: unexpected oversized files/modules found.")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
