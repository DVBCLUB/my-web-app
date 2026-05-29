"""Lightweight repository audit for FT ERP.

Run from repository root:
    python tools/repo_audit.py

This script reports large files and large Python modules so refactor work can
stay focused. It uses only the Python standard library.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules"}
LARGE_FILE_BYTES = 1_000_000
LARGE_PY_LINES = 800


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


def main() -> int:
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
            print(f"- {path.relative_to(ROOT)}: {size / 1024 / 1024:.2f} MB")
    else:
        print("- None")

    print("\nLarge Python modules >= 800 lines:")
    if large_python:
        for path, lines in large_python[:30]:
            print(f"- {path.relative_to(ROOT)}: {lines} lines")
    else:
        print("- None")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
