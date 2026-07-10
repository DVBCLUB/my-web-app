"""ERP security, approval workflow and BI helpers.

Self-contained Flask/SQLite extension for:
- Dynamic RBAC permission matrix.
- HTTP audit/activity log.
- Temporary-password and TOTP 2FA helpers.
- Construction approval workflow.
- Project + cost-code expense control.
- BI dashboard datasets.

Register from ``web_app.create_app`` with::

    from modules.erp_security_workflow_bi import register_erp_upgrade
    register_erp_upgrade(app)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from datetime import datetime
from typing import Any, Iterable
from urllib.parse import quote

try:  # Keep desktop app imports safe when Flask is not installed.
    from flask import Blueprint, jsonify, request, session
except Exception:  # pragma: no cover
    Blueprint = None
    jsonify = request = session = None

from database import get_connection

APPROVAL_STATUSES = ("Draft", "Pending_Manager", "Pending_Accountant", "Approved", "Rejected")
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
WORKFLOW_TABLES = {
    "expense": "expenses",
    "document": "documents",
    "inventory": "inventory_transactions",
    "advance_request": "advance_requests",
    "advance_settlement": "advance_settlements",
}
WORKFLOW_TRANSITIONS = {
    "Draft": {"Pending_Manager", "Rejected"},
    "Pending_Manager": {"Pending_Accountant", "Rejected"},
    "Pending_Accountant": {"Approved", "Rejected"},
    "Approved": set(),
    "Rejected": {"Draft"},
}
ROLE_LABELS = {
    "admin": "Quản trị viên",
    "manager": "Chỉ huy trưởng / Quản lý",
    "accountant": "Kế toán",
    "employee": "Nhân viên công trường",
    "viewer": "Chỉ xem",
}
DEFAULT_PERMISSION_MATRIX: dict[str, dict[str, list[str]]] = {
    "admin": {
        "bao_mat": ["create", "read", "update", "delete", "approve"],
        "chi_phi": ["create", "read", "update", "delete", "approve"],
        "ke_toan_cong_trinh": ["create", "read", "update", "delete", "approve"],
        "kho": ["create", "read", "update", "delete", "approve"],
        "bao_cao": ["read"],
    },
    "manager": {
        "bao_mat": [],
        "chi_phi": ["create", "read", "update", "approve"],
        "ke_toan_cong_trinh": ["read", "approve"],
        "kho": ["create", "read", "update", "approve"],
        "bao_cao": ["read"],
    },
    "accountant": {
        "bao_mat": [],
        "chi_phi": ["create", "read", "update", "approve"],
        "ke_toan_cong_trinh": ["create", "read", "update", "approve"],
        "kho": ["read", "approve"],
        "bao_cao": ["read"],
    },
    "employee": {
        "bao_mat": [],
        "chi_phi": ["create", "read"],
        "ke_toan_cong_trinh": ["read"],
        "kho": ["create", "read"],
        "bao_cao": [],
    },
    "viewer": {
        "bao_mat": [],
        "chi_phi": ["read"],
        "ke_toan_cong_trinh": ["read"],
        "kho": ["read"],
        "bao_cao": ["read"],
    },
}

CREATE_SQL = (
    """
    CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_code TEXT UNIQUE NOT NULL,
        role_name TEXT NOT NULL,
        description TEXT,
        active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS role_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_code TEXT NOT NULL,
        module_code TEXT NOT NULL,
        actions TEXT NOT NULL DEFAULT '[]',
        active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(role_code, module_code),
        FOREIGN KEY(role_code) REFERENCES roles(role_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cost_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        budget_amount REAL DEFAULT 0,
        active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(project_id, code),
        FOREIGN KEY(project_id) REFERENCES projects(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS approval_workflow_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        from_status TEXT,
        to_status TEXT NOT NULL,
        actor_id INTEGER,
        actor_role TEXT,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS http_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        url_endpoint TEXT NOT NULL,
        payload_old TEXT,
        payload_new TEXT,
        ip_address TEXT,
        status_code INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT,
        entity_id INTEGER,
        action TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        actor_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
)

AUDIT_COLUMNS = (
    "user_id INTEGER",
    "url_endpoint TEXT",
    "payload_old TEXT",
    "payload_new TEXT",
    "ip_address TEXT",
    "status_code INTEGER",
)
USER_COLUMNS = (
    "must_change_password INTEGER DEFAULT 0",
    "is_temporary_password INTEGER DEFAULT 0",
    "password_changed_at TIMESTAMP",
    "totp_secret TEXT",
    "totp_enabled INTEGER DEFAULT 0",
    "last_login_at TIMESTAMP",
)
WORKFLOW_COLUMNS = (
    "workflow_status TEXT DEFAULT 'Draft'",
    "approved_by_manager INTEGER",
    "approved_by_accountant INTEGER",
    "approved_at TIMESTAMP",
    "rejected_reason TEXT",
)
EXPENSE_COLUMNS = ("cost_code_id INTEGER", "cost_code TEXT")
_SCHEMA_READY = False


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _row(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def _table_exists(cursor: Any, table: str) -> bool:
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,))
    return cursor.fetchone() is not None


def _columns(cursor: Any, table: str) -> set[str]:
    cursor.execute(f'PRAGMA table_info("{table}")')
    return {row["name"] for row in cursor.fetchall()}


def _add_columns(cursor: Any, table: str, definitions: Iterable[str]) -> None:
    if not _table_exists(cursor, table):
        return
    existing = _columns(cursor, table)
    for definition in definitions:
        name = definition.split()[0]
        if name not in existing:
            cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN {definition}')
            existing.add(name)


def _seed_default_roles(cursor: Any) -> None:
    for role_code, permissions in DEFAULT_PERMISSION_MATRIX.items():
        cursor.execute(
            """
            INSERT INTO roles (role_code, role_name, description, active)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(role_code) DO UPDATE SET
                role_name = excluded.role_name,
                description = excluded.description,
                updated_at = CURRENT_TIMESTAMP
            """,
            (role_code, ROLE_LABELS.get(role_code, role_code), "Migrated from static roles"),
        )
        for module_code, actions in permissions.items():
            cursor.execute(
                """
                INSERT INTO role_permissions (role_code, module_code, actions, active)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(role_code, module_code) DO UPDATE SET
                    actions = excluded.actions,
                    active = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (role_code, module_code, _json(sorted(set(actions)))),
            )


def ensure_erp_upgrade_schema(force: bool = False) -> None:
    """Create/upgrade the small schema used by this module."""
    global _SCHEMA_READY
    if _SCHEMA_READY and not force:
        return

    conn = get_connection()
    cursor = conn.cursor()
    try:
        for sql in CREATE_SQL:
            cursor.execute(sql)
        _add_columns(cursor, "audit_log", AUDIT_COLUMNS)
        _add_columns(cursor, "users", USER_COLUMNS)
        _add_columns(cursor, "expenses", EXPENSE_COLUMNS)
        for table in WORKFLOW_TABLES.values():
            _add_columns(cursor, table, WORKFLOW_COLUMNS)
        _seed_default_roles(cursor)
        conn.commit()
        _SCHEMA_READY = True
    finally:
        conn.close()


def permission_matrix() -> list[dict[str, Any]]:
    ensure_erp_upgrade_schema()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT r.role_code, r.role_name, r.description, p.module_code, p.actions
            FROM roles r
            LEFT JOIN role_permissions p ON p.role_code = r.role_code AND p.active = 1
            WHERE r.active = 1
            ORDER BY r.role_code, p.module_code
            """
        )
        roles: dict[str, dict[str, Any]] = {}
        for row in cursor.fetchall():
            role = roles.setdefault(
                row["role_code"],
                {"role": row["role_code"], "role_name": row["role_name"], "description": row["description"], "permissions": {}},
            )
            if row["module_code"]:
                role["permissions"][row["module_code"]] = json.loads(row["actions"] or "[]")
        return list(roles.values())
    finally:
        conn.close()


def set_role_permissions(role_code: str, permissions: dict[str, Iterable[str]], role_name: str | None = None) -> dict[str, Any]:
    ensure_erp_upgrade_schema()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO roles (role_code, role_name, active)
            VALUES (?, ?, 1)
            ON CONFLICT(role_code) DO UPDATE SET
                role_name = COALESCE(excluded.role_name, roles.role_name),
                updated_at = CURRENT_TIMESTAMP
            """,
            (role_code, role_name or role_code),
        )
        for module_code, actions in permissions.items():
            clean = sorted({str(action).strip() for action in actions if str(action).strip()})
            cursor.execute(
                """
                INSERT INTO role_permissions (role_code, module_code, actions, active)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(role_code, module_code) DO UPDATE SET
                    actions = excluded.actions,
                    active = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (role_code, module_code, _json(clean)),
            )
        conn.commit()
        return {"role": role_code, "permissions": permissions}
    finally:
        conn.close()


def user_can(user: dict[str, Any] | None, module_code: str, action: str) -> bool:
    if not user:
        return False
    role = user.get("role") or user.get("role_code") or "viewer"
    if role == "admin":
        return True
    matrix = {item["role"]: item["permissions"] for item in permission_matrix()}
    return action in matrix.get(role, {}).get(module_code, [])


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _totp(secret: str, for_time: int | None = None, interval: int = 30, digits: int = 6) -> str:
    normalized = secret.replace(" ", "").upper()
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    key = base64.b32decode(normalized + padding)
    counter = int((for_time or int(time.time())) // interval)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def verify_totp(secret: str | None, token: str, allowed_drift: int = 1) -> bool:
    token = str(token or "").strip().replace(" ", "")
    if not secret or not token.isdigit():
        return False
    now = int(time.time())
    return any(hmac.compare_digest(_totp(secret, now + offset * 30), token) for offset in range(-allowed_drift, allowed_drift + 1))


def totp_uri(username: str, secret: str, issuer: str = "FasTrack ERP") -> str:
    label = f"{quote(issuer)}:{quote(username)}"
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"


def mark_temporary_password(user_id: int) -> None:
    ensure_erp_upgrade_schema()
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE users
            SET must_change_password = 1, is_temporary_password = 1, password_changed_at = NULL
            WHERE id = ?
            """,
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def complete_password_change(user_id: int) -> None:
    ensure_erp_upgrade_schema()
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE users
            SET must_change_password = 0, is_temporary_password = 0, password_changed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def log_http_activity(
    user_id: int | None,
    action: str,
    url_endpoint: str,
    payload_old: Any,
    payload_new: Any,
    ip_address: str | None,
    status_code: int | None = None,
) -> None:
    ensure_erp_upgrade_schema()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        old_json, new_json = _json(payload_old), _json(payload_new)
        cursor.execute(
            """
            INSERT INTO http_audit_log (user_id, action, url_endpoint, payload_old, payload_new, ip_address, status_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, action, url_endpoint, old_json, new_json, ip_address, status_code),
        )
        cursor.execute(
            """
            INSERT INTO audit_log (entity_type, action, actor_id, user_id, url_endpoint, payload_old, payload_new, ip_address, status_code)
            VALUES ('http_request', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (action, user_id, user_id, url_endpoint, old_json, new_json, ip_address, status_code),
        )
        conn.commit()
    finally:
        conn.close()


def audit_log_rows(limit: int = 200) -> list[dict[str, Any]]:
    ensure_erp_upgrade_schema()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT a.id, COALESCE(a.user_id, a.actor_id) AS user_id, u.username, a.action,
                   COALESCE(a.url_endpoint, '') AS url_endpoint,
                   COALESCE(a.payload_old, a.old_value) AS payload_old,
                   COALESCE(a.payload_new, a.new_value) AS payload_new,
                   a.ip_address, a.status_code, a.created_at
            FROM audit_log a
            LEFT JOIN users u ON u.id = COALESCE(a.user_id, a.actor_id)
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT ?
            """,
            (max(1, min(int(limit or 200), 1000)),),
        )
        return [_row(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def submit_for_approval(entity_type: str, entity_id: int, actor_id: int | None = None) -> dict[str, Any]:
    return transition_workflow(entity_type, entity_id, "Pending_Manager", actor_id, "employee_submit")


def transition_workflow(
    entity_type: str,
    entity_id: int,
    next_status: str,
    actor_id: int | None = None,
    actor_role: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    table = WORKFLOW_TABLES.get(entity_type)
    if not table:
        raise ValueError("Unsupported workflow entity_type")
    if next_status not in APPROVAL_STATUSES:
        raise ValueError(f"Invalid workflow status: {next_status}")

    ensure_erp_upgrade_schema()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f'SELECT id, workflow_status FROM "{table}" WHERE id = ?', (entity_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Document not found")
        old_status = row["workflow_status"] or "Draft"
        if next_status != old_status and next_status not in WORKFLOW_TRANSITIONS.get(old_status, set()):
            raise ValueError(f"Transition {old_status} -> {next_status} is not allowed")

        set_parts = ["workflow_status = ?"]
        params: list[Any] = [next_status]
        if next_status == "Pending_Accountant":
            set_parts.append("approved_by_manager = ?")
            params.append(actor_id)
        elif next_status == "Approved":
            set_parts.extend(["approved_by_accountant = ?", "approved_at = CURRENT_TIMESTAMP"])
            params.append(actor_id)
        elif next_status == "Rejected":
            set_parts.append("rejected_reason = ?")
            params.append(note)

        cursor.execute(f'UPDATE "{table}" SET {", ".join(set_parts)} WHERE id = ?', [*params, entity_id])
        cursor.execute(
            """
            INSERT INTO approval_workflow_events (entity_type, entity_id, from_status, to_status, actor_id, actor_role, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (entity_type, entity_id, old_status, next_status, actor_id, actor_role, note),
        )
        conn.commit()
        return {"entity_type": entity_type, "entity_id": entity_id, "from_status": old_status, "to_status": next_status}
    finally:
        conn.close()


def validate_expense_cost_code(project_id: Any, cost_code_id: Any) -> None:
    if not project_id:
        raise ValueError("Chi phí bắt buộc phải chọn Mã Dự án")
    if not cost_code_id:
        raise ValueError("Chi phí bắt buộc phải chọn Mã Hạng mục/Mã Định mức")
    ensure_erp_upgrade_schema()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM cost_codes WHERE id = ? AND project_id = ? AND active = 1", (cost_code_id, project_id))
        if cursor.fetchone() is None:
            raise ValueError("Mã định mức không thuộc dự án hoặc đã ngưng dùng")
    finally:
        conn.close()


def create_expense_with_controls(data: dict[str, Any], actor_id: int | None = None) -> int:
    validate_expense_cost_code(data.get("project_id"), data.get("cost_code_id"))
    ensure_erp_upgrade_schema()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO expenses (
                expense_date, project_id, category_id, cost_code_id, cost_code, description,
                amount, paid_by, payment_method, status, workflow_status, notes, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'Draft', ?, ?)
            """,
            (
                data.get("expense_date") or datetime.now().date().isoformat(),
                data.get("project_id"),
                data.get("category_id"),
                data.get("cost_code_id"),
                data.get("cost_code"),
                data.get("description"),
                float(data.get("amount") or 0),
                data.get("paid_by"),
                data.get("payment_method"),
                data.get("notes"),
                actor_id,
            ),
        )
        expense_id = int(cursor.lastrowid)
        cursor.execute(
            """
            INSERT INTO approval_workflow_events (entity_type, entity_id, from_status, to_status, actor_id, actor_role, note)
            VALUES ('expense', ?, NULL, 'Draft', ?, 'employee', 'created with cost-code controls')
            """,
            (expense_id, actor_id),
        )
        conn.commit()
        return expense_id
    finally:
        conn.close()


def bi_dashboard_snapshot() -> dict[str, Any]:
    """Return KPI and chart datasets. Subqueries prevent join double-counting."""
    ensure_erp_upgrade_schema()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            WITH actual AS (
                SELECT project_id, SUM(amount) AS amount
                FROM expenses
                WHERE status IN ('approved','posted','paid') OR workflow_status = 'Approved'
                GROUP BY project_id
            ), budget AS (
                SELECT project_id, SUM(budget_amount) AS amount
                FROM cost_codes
                WHERE active = 1
                GROUP BY project_id
            )
            SELECT p.id, p.code, p.name,
                   COALESCE(NULLIF(b.amount, 0), p.budget, 0) AS budget,
                   COALESCE(a.amount, 0) AS actual_cost
            FROM projects p
            LEFT JOIN actual a ON a.project_id = p.id
            LEFT JOIN budget b ON b.project_id = p.id
            ORDER BY p.code
            """
        )
        variance = []
        for row in cursor.fetchall():
            budget = float(row["budget"] or 0)
            actual = float(row["actual_cost"] or 0)
            variance.append({
                "project_id": row["id"],
                "code": row["code"],
                "name": row["name"],
                "budget": budget,
                "actual_cost": actual,
                "variance": budget - actual,
                "variance_percent": (budget - actual) / budget * 100 if budget else None,
            })

        cursor.execute(
            """
            SELECT COALESCE(p.code, 'Kho chung') AS project_code,
                   COALESCE(m.category, 'Vật tư') AS cost_type,
                   SUM(ABS(it.quantity) * COALESCE(m.average_cost, m.unit_price, 0)) AS amount
            FROM inventory_transactions it
            JOIN materials m ON m.id = it.material_id
            LEFT JOIN projects p ON p.id = it.project_id
            WHERE LOWER(it.transaction_type) IN ('xuat', 'issue', 'export', 'out')
            GROUP BY COALESCE(p.code, 'Kho chung'), COALESCE(m.category, 'Vật tư')
            ORDER BY project_code, cost_type
            """
        )
        stacked_cost = [_row(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT substr(expense_date, 1, 7) AS period, SUM(amount) AS amount
            FROM expenses
            WHERE expense_date IS NOT NULL
            GROUP BY substr(expense_date, 1, 7)
            ORDER BY period
            """
        )
        expense_trend = [_row(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT m.id, m.code, m.name, m.unit,
                   COALESCE(m.quantity, 0) AS current_qty,
                   COALESCE(AVG(CASE WHEN LOWER(it.transaction_type) IN ('xuat','issue','export','out') THEN ABS(it.quantity) END), 0) AS avg_consumption,
                   7 AS lead_time_days,
                   COALESCE(AVG(CASE WHEN LOWER(it.transaction_type) IN ('xuat','issue','export','out') THEN ABS(it.quantity) END), 0) * 7 AS s_min
            FROM materials m
            LEFT JOIN inventory_transactions it ON it.material_id = m.id
            GROUP BY m.id, m.code, m.name, m.unit, m.quantity
            HAVING current_qty <= s_min AND s_min > 0
            ORDER BY (s_min - current_qty) DESC
            LIMIT 50
            """
        )
        min_stock_alerts = [_row(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            WITH revenue AS (
                SELECT project_id, SUM(amount) AS amount FROM project_revenues GROUP BY project_id
            ), expense AS (
                SELECT project_id, SUM(amount) AS amount FROM expenses GROUP BY project_id
            )
            SELECT p.id, p.code, p.name,
                   COALESCE(r.amount, 0) AS actual_revenue,
                   COALESCE(e.amount, 0) AS actual_expense,
                   COALESCE(r.amount, 0) - COALESCE(e.amount, 0) AS cash_flow
            FROM projects p
            LEFT JOIN revenue r ON r.project_id = p.id
            LEFT JOIN expense e ON e.project_id = p.id
            ORDER BY p.code
            """
        )
        project_cash_flow = [_row(row) for row in cursor.fetchall()]

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "kpis": {
                "variance": variance,
                "min_stock_alerts": min_stock_alerts,
                "project_cash_flow": project_cash_flow,
            },
            "charts": {
                "stacked_cost_by_project": stacked_cost,
                "expense_trend": expense_trend,
            },
        }
    finally:
        conn.close()


def register_erp_upgrade(app: Any) -> Any:
    """Register migration, audit middleware and JSON APIs on a Flask app."""
    ensure_erp_upgrade_schema()
    if Blueprint is None:
        return app

    bp = Blueprint("erp_upgrade", __name__, url_prefix="/api/erp-upgrade")

    @app.after_request
    def _audit_write_request(response):  # type: ignore[no-untyped-def]
        try:
            if request.method in WRITE_METHODS and not request.path.startswith("/static"):
                payload = request.get_json(silent=True) if request.is_json else request.form.to_dict(flat=True)
                log_http_activity(
                    session.get("user_id") if session else None,
                    request.method,
                    request.path,
                    None,
                    payload,
                    request.headers.get("X-Forwarded-For", request.remote_addr),
                    response.status_code,
                )
        except Exception:
            pass
        return response

    @bp.get("/permission-matrix")
    def api_permission_matrix():  # type: ignore[no-untyped-def]
        return jsonify(permission_matrix())

    @bp.post("/permission-matrix")
    def api_save_permission_matrix():  # type: ignore[no-untyped-def]
        data = request.get_json(force=True)
        return jsonify(set_role_permissions(data["role"], data.get("permissions") or {}, data.get("role_name")))

    @bp.get("/audit-log")
    def api_audit_log():  # type: ignore[no-untyped-def]
        return jsonify(audit_log_rows(request.args.get("limit", 200)))

    @bp.post("/totp/setup")
    def api_totp_setup():  # type: ignore[no-untyped-def]
        user_id = session.get("user_id") if session else None
        username = session.get("username", "user") if session else "user"
        if not user_id:
            return jsonify({"error": "not_authenticated"}), 401
        secret = generate_totp_secret()
        conn = get_connection()
        try:
            conn.execute("UPDATE users SET totp_secret = ?, totp_enabled = 0 WHERE id = ?", (secret, user_id))
            conn.commit()
        finally:
            conn.close()
        return jsonify({"secret": secret, "uri": totp_uri(username, secret)})

    @bp.post("/totp/verify")
    def api_totp_verify():  # type: ignore[no-untyped-def]
        user_id = session.get("user_id") if session else None
        token = (request.get_json(silent=True) or {}).get("token")
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT totp_secret FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if not row or not verify_totp(row["totp_secret"], token):
                return jsonify({"ok": False, "error": "invalid_token"}), 400
            conn.execute("UPDATE users SET totp_enabled = 1 WHERE id = ?", (user_id,))
            conn.commit()
            return jsonify({"ok": True})
        finally:
            conn.close()

    @bp.post("/workflow/<entity_type>/<int:entity_id>/submit")
    def api_submit_workflow(entity_type: str, entity_id: int):  # type: ignore[no-untyped-def]
        return jsonify(submit_for_approval(entity_type, entity_id, session.get("user_id") if session else None))

    @bp.post("/workflow/<entity_type>/<int:entity_id>/transition")
    def api_transition_workflow(entity_type: str, entity_id: int):  # type: ignore[no-untyped-def]
        data = request.get_json(force=True)
        return jsonify(transition_workflow(
            entity_type,
            entity_id,
            data["status"],
            session.get("user_id") if session else None,
            data.get("actor_role"),
            data.get("note", ""),
        ))

    @bp.post("/expenses")
    def api_create_controlled_expense():  # type: ignore[no-untyped-def]
        expense_id = create_expense_with_controls(request.get_json(force=True), session.get("user_id") if session else None)
        return jsonify({"id": expense_id, "workflow_status": "Draft"}), 201

    @bp.get("/dashboard")
    def api_bi_dashboard():  # type: ignore[no-untyped-def]
        return jsonify(bi_dashboard_snapshot())

    app.register_blueprint(bp)
    return app
