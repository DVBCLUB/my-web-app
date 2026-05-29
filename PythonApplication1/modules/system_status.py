"""System status service for FT ERP.

Operational checks live here so system routes stay thin.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from database import get_connection


STATUS_TABLES = ["users", "projects", "expenses", "documents", "materials", "inventory_transactions"]


def health_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "FT ERP",
        "time": datetime.now().isoformat(timespec="seconds"),
        "revision": os.environ.get("K_REVISION", "local"),
    }


def table_counts() -> dict[str, int | None]:
    conn = get_connection()
    cursor = conn.cursor()
    counts: dict[str, int | None] = {}
    for table in STATUS_TABLES:
        try:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            counts[table] = int(cursor.fetchone()[0] or 0)
        except Exception:
            counts[table] = None
    return counts


def system_status_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "FT ERP",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "runtime": {
            "cloud_run_service": os.environ.get("K_SERVICE", "local"),
            "cloud_run_revision": os.environ.get("K_REVISION", "local"),
            "database_path": os.environ.get("ACCOUNTING_DB_PATH", "data/accounting.db"),
        },
        "counts": table_counts(),
        "checks": {
            "database": "connected",
            "auth": "enabled",
            "recovery_login_env": bool(os.environ.get("FASTRACK_RECOVERY_KEY")),
        },
    }
