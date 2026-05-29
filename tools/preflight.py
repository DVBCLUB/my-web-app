"""Preflight checks before pushing larger FT ERP changes.

Run from repository root:
    python tools/preflight.py

This intentionally stays local/dev-only. It does not deploy anything.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_step(name: str, command: list[str]) -> int:
    print(f"\n==> {name}")
    print("$ " + " ".join(command))
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        print(f"FAILED: {name}")
    return result.returncode


def main() -> int:
    steps = [
        ("Repository audit", [sys.executable, "tools/repo_audit.py", "--fail-on-large"]),
        ("Smoke tests", [sys.executable, "-m", "pytest", "PythonApplication1/tests/test_smoke_app.py", "-q"]),
    ]
    for name, command in steps:
        code = run_step(name, command)
        if code != 0:
            return code
    print("\nPreflight passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
