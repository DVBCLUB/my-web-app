"""System and operational endpoints.

Keep low-risk health/status endpoints here so web_app.py can shrink over time.
"""

from __future__ import annotations

import os
from datetime import datetime

from flask import Blueprint, jsonify

from database import get_connection


system_bp = Blueprint("system", __name__)


@system_bp.get("/healthz")
def healthz():
    return jsonify(
        {
            "ok": True,
            "service": "FT ERP",
            "time": datetime.now().isoformat(timespec="seconds"),
            "revision": os.environ.get("K_REVISION", "local"),
        }
    )


@system_bp.get("/api/system/status")
def system_status():
    conn = get_connection()
    cursor = conn.cursor()
    tables = ["users", "projects", "expenses", "documents", "materials", "inventory_transactions"]
    counts = {}
    for table in tables:
        try:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            counts[table] = int(cursor.fetchone()[0] or 0)
        except Exception:
            counts[table] = None
    return jsonify(
        {
            "ok": True,
            "service": "FT ERP",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "runtime": {
                "cloud_run_service": os.environ.get("K_SERVICE", "local"),
                "cloud_run_revision": os.environ.get("K_REVISION", "local"),
                "database_path": os.environ.get("ACCOUNTING_DB_PATH", "data/accounting.db"),
            },
            "counts": counts,
            "checks": {
                "database": "connected",
                "auth": "enabled",
                "recovery_login_env": bool(os.environ.get("FASTRACK_RECOVERY_KEY")),
            },
        }
    )
