"""Construction accounting rule service.

Business data loading stays here. Routes should stay thin.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_RULES: dict[str, Any] = {"version": "missing", "cost_groups": [], "reports": []}


def rules_file_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "construction_accounting_rules.json"


def load_construction_accounting_rules() -> dict[str, Any]:
    path = rules_file_path()
    if not path.exists():
        return DEFAULT_RULES.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {**DEFAULT_RULES, "version": "invalid"}
    data.setdefault("cost_groups", [])
    data.setdefault("reports", [])
    return data


def find_cost_group(code: str) -> dict[str, Any] | None:
    code = (code or "").strip().upper()
    for group in load_construction_accounting_rules().get("cost_groups", []):
        if str(group.get("code", "")).upper() == code:
            return group
    return None
