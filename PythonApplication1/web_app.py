"""Flask web edition for FasTrack ERP.

Run with:
    python web_app.py
Then open:
    http://127.0.0.1:5000
"""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import date, datetime, timedelta
from functools import wraps
from typing import Any
from urllib.parse import quote
from urllib import request as url_request

try:
    from flask import Flask, Response, current_app, jsonify, request, session
    from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
except ImportError:  # pragma: no cover - lets the desktop app import safely.
    Flask = None

from database import get_connection, init_database
from modules.accounting import ExpenseManager
from modules.advance_workflow import AdvanceWorkflowManager
from modules.auth import AuthManager, PermissionManager
from modules.backup import BackupManager
from modules.bank_reconciliation import BankReconciliationManager
from modules.construction import ConstructionManager
from modules.controls import ApprovalThresholdManager, AuditLogManager
from modules.fiscal_lock import FiscalPeriodLockManager
from modules.invoices import DocumentManager
from modules.material_controls import MaterialControlManager
from modules.materials import MaterialManager
from modules.notification_center import NotificationCenter
from modules.project_accounting import ProjectAccountingManager
from modules.purchase_orders import PurchaseOrderManager
from modules.template_renderer import TemplateRenderer
from modules.utilities import UtilityManager


def row_to_dict(row: Any, keys: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
    """Convert sqlite rows or positional tuples into JSON-friendly dictionaries."""
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    if keys:
        return {key: row[index] if index < len(row) else None for index, key in enumerate(keys)}
    return {str(index): value for index, value in enumerate(row)}


def row_to_named_dict(row: Any, keys: list[str] | tuple[str, ...]) -> dict[str, Any]:
    return {key: row[index] if index < len(row) else None for index, key in enumerate(keys)}


OFFLINE_DATA_TABLES = {
    "accounts": "He thong tai khoan",
    "projects": "Du an",
    "expense_categories": "Danh muc chi phi",
    "expenses": "Chi phi",
    "documents": "Chung tu",
    "materials": "Vat tu",
    "project_contracts": "Hop dong cong trinh",
    "contract_billings": "Nghiem thu / billing",
    "project_revenues": "Doanh thu cong trinh",
    "project_cost_plans": "Du toan chi phi",
    "journal_entries": "But toan",
    "ar_ap_items": "Cong no phai thu/phai tra",
    "fiscal_calendar": "Ky ke toan",
    "approval_thresholds": "Han muc phe duyet",
    "approval_logs": "Lich su phe duyet",
    "audit_log": "Audit log",
    "form_templates": "Thu vien bieu mau",
    "form_template_fields": "Truong bieu mau",
    "form_field_mappings": "Mapping bieu mau",
    "document_requirements": "Yeu cau chung tu",
    "compliance_rules": "Quy tac tuan thu",
    "category_account_mappings": "Mapping tai khoan",
    "policy_limits": "Han muc chinh sach",
    "process_steps": "Quy trinh",
    "recurring_tasks": "Tac vu dinh ky",
    "simple_catalogs": "Danh muc dung chung",
    "app_settings": "Cau hinh cong ty",
    "powerbi_sync_log": "Log PowerBI",
}


def offline_table_columns(table_name: str) -> list[str]:
    if table_name not in OFFLINE_DATA_TABLES:
        raise ValueError("Bang du lieu khong duoc phep truy cap")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    return [row["name"] for row in cursor.fetchall()]


def offline_table_rows(table_name: str, limit: int = 50, offset: int = 0, q: str = "") -> dict[str, Any]:
    if table_name not in OFFLINE_DATA_TABLES:
        raise ValueError("Bang du lieu khong duoc phep truy cap")
    limit = max(1, min(int(limit or 50), 1000))
    offset = max(0, int(offset or 0))
    conn = get_connection()
    cursor = conn.cursor()
    columns = offline_table_columns(table_name)
    where = ""
    params: list[Any] = []
    if q and columns:
        where = " WHERE " + " OR ".join([f'CAST("{column}" AS TEXT) LIKE ?' for column in columns])
        params = [f"%{q}%"] * len(columns)
    cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"{where}', params)
    total = int(cursor.fetchone()[0] or 0)
    cursor.execute(f'SELECT * FROM "{table_name}"{where} LIMIT ? OFFSET ?', [*params, limit, offset])
    rows = [row_to_dict(row) for row in cursor.fetchall()]
    return {"columns": columns, "rows": rows, "total": total, "limit": limit, "offset": offset, "q": q}


def offline_data_snapshot() -> dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    tables = []
    for table_name, label in OFFLINE_DATA_TABLES.items():
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table_name,))
        if not cursor.fetchone():
            tables.append({"name": table_name, "label": label, "count": 0, "columns": [], "sample": []})
            continue
        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        count = int(cursor.fetchone()[0] or 0)
        cursor.execute(f'PRAGMA table_info("{table_name}")')
        columns = [row["name"] for row in cursor.fetchall()]
        sample = offline_table_rows(table_name, 5)["rows"] if count else []
        tables.append({"name": table_name, "label": label, "count": count, "columns": columns, "sample": sample})
    active_tables = [table for table in tables if table["count"]]
    return {
        "summary": {
            "table_count": len(tables),
            "active_table_count": len(active_tables),
            "record_count": sum(table["count"] for table in tables),
        },
        "tables": tables,
    }


def offline_data_bundle(limit_per_table: int = 1000) -> dict[str, Any]:
    snapshot = offline_data_snapshot()
    bundle = {"summary": snapshot["summary"], "tables": []}
    for table in snapshot["tables"]:
        rows = offline_table_rows(table["name"], limit_per_table) if table["count"] else {"rows": [], "columns": table["columns"]}
        bundle["tables"].append({**table, "rows": rows["rows"], "exported_rows": len(rows["rows"])})
    return bundle


def rows_to_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def inventory_workspace_snapshot() -> dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, code, name, unit, quantity, unit_price,
               COALESCE(average_cost, unit_price, 0) AS average_cost,
               COALESCE(min_quantity, 0) AS min_quantity,
               category, supplier, status,
               COALESCE(quantity, 0) * COALESCE(average_cost, unit_price, 0) AS stock_value
        FROM materials
        ORDER BY category, name
        """
    )
    materials = [row_to_dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT w.id, w.project_id, COALESCE(p.code, '') AS project_code,
               COALESCE(p.name, '') AS project_name, w.item_code, w.item_name,
               w.unit, w.planned_quantity, w.completed_quantity,
               COALESCE(w.percent_complete, 0) AS percent_complete, w.status
        FROM construction_work_items w
        LEFT JOIN projects p ON p.id = w.project_id
        ORDER BY p.code, w.item_code, w.id
        """
    )
    work_items = [row_to_dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT s.id, s.work_item_id, s.material_id, COALESCE(p.code, '') AS project_code,
               COALESCE(p.name, '') AS project_name, COALESCE(w.item_code, '') AS item_code,
               COALESCE(w.item_name, 'Chung') AS item_name, m.code AS material_code,
               m.name AS material_name, m.unit, s.basis_unit, s.standard_qty_per_unit,
               s.tolerance_percent, s.notes, s.active
        FROM material_standards s
        JOIN materials m ON m.id = s.material_id
        LEFT JOIN construction_work_items w ON w.id = s.work_item_id
        LEFT JOIN projects p ON p.id = w.project_id
        WHERE s.active = 1
        ORDER BY p.code, w.item_code, m.name
        """
    )
    standards = [row_to_dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT it.id, it.transaction_date, it.transaction_type, it.quantity,
               it.project_id, COALESCE(p.code, '') AS project_code,
               COALESCE(p.name, '') AS project_name, m.code AS material_code,
               m.name AS material_name, m.unit, it.notes
        FROM inventory_transactions it
        JOIN materials m ON m.id = it.material_id
        LEFT JOIN projects p ON p.id = it.project_id
        ORDER BY it.transaction_date DESC, it.id DESC
        LIMIT 80
        """
    )
    history = [row_to_dict(row) for row in cursor.fetchall()]

    material_by_id = {int(row["id"]): row for row in materials}
    smart_alerts: list[dict[str, Any]] = []
    for standard in standards:
        work_item = next((w for w in work_items if w["id"] == standard["work_item_id"]), {})
        material = material_by_id.get(int(standard["material_id"] or 0), {})
        remaining_basis = max(
            0.0,
            float(work_item.get("planned_quantity") or 0)
            - float(work_item.get("completed_quantity") or 0),
        )
        needed_qty = remaining_basis * float(standard["standard_qty_per_unit"] or 0)
        available_qty = float(material.get("quantity") or 0)
        min_qty = float(material.get("min_quantity") or 0)
        shortage_qty = max(0.0, needed_qty - available_qty, min_qty - available_qty)
        if shortage_qty <= 0:
            continue
        progress = float(work_item.get("percent_complete") or 0)
        smart_alerts.append(
            {
                "project_id": work_item.get("project_id"),
                "project_code": standard.get("project_code") or "",
                "project_name": standard.get("project_name") or "",
                "work_item_id": standard.get("work_item_id"),
                "item_code": standard.get("item_code") or "",
                "item_name": standard.get("item_name") or "Chung",
                "material_id": standard.get("material_id"),
                "material_code": standard.get("material_code"),
                "material_name": standard.get("material_name"),
                "unit": standard.get("unit"),
                "available_qty": available_qty,
                "needed_qty": needed_qty,
                "min_quantity": min_qty,
                "shortage_qty": shortage_qty,
                "progress": progress,
                "priority": "critical" if progress >= 70 or available_qty <= 0 else "warning",
                "suggestion": "Tao don mua hang",
            }
        )
    smart_alerts.sort(key=lambda row: (row["priority"] != "critical", -float(row["shortage_qty"] or 0)))
    low_stock = [
        {
            **row,
            "shortage_qty": max(0.0, float(row.get("min_quantity") or 0) - float(row.get("quantity") or 0)),
            "priority": "warning",
            "suggestion": "Bo sung dinh muc ton kho",
        }
        for row in materials
        if float(row.get("min_quantity") or 0) > 0
        and float(row.get("quantity") or 0) <= float(row.get("min_quantity") or 0)
    ]
    return {
        "summary": {
            "material_count": len(materials),
            "stock_value": sum(float(row.get("stock_value") or 0) for row in materials),
            "low_stock_count": len(low_stock),
            "smart_alert_count": len(smart_alerts),
            "standard_count": len(standards),
        },
        "materials": materials,
        "work_items": work_items,
        "standards": standards,
        "history": history,
        "alerts": smart_alerts + low_stock,
        "purchase_orders": PurchaseOrderManager().get_open_purchase_orders(),
        "valuation_methods": [
            {"code": "weighted_average", "name": "Binh quan gia quyen", "status": "active"},
            {"code": "fifo", "name": "FIFO", "status": "planned"},
            {"code": "specific", "name": "Dich danh theo lo", "status": "planned"},
            {"code": "periodic_average", "name": "Binh quan cuoi ky", "status": "planned"},
        ],
    }


def offline_schema_snapshot() -> dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )
    tables = []
    relationships = []
    for table in cursor.fetchall():
        table_name = table["name"]
        cursor.execute(f'PRAGMA table_info("{table_name}")')
        columns = [row_to_dict(row) for row in cursor.fetchall()]
        cursor.execute(f'PRAGMA foreign_key_list("{table_name}")')
        foreign_keys = [row_to_dict(row) for row in cursor.fetchall()]
        for fk in foreign_keys:
            relationships.append(
                {
                    "from_table": table_name,
                    "from_column": fk.get("from"),
                    "to_table": fk.get("table"),
                    "to_column": fk.get("to"),
                }
            )
        indexes = []
        cursor.execute(f'PRAGMA index_list("{table_name}")')
        for index in cursor.fetchall():
            index_data = row_to_dict(index)
            index_name = index_data.get("name")
            cursor.execute(f'PRAGMA index_info("{index_name}")')
            index_data["columns"] = [row["name"] for row in cursor.fetchall()]
            indexes.append(index_data)
        try:
            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            row_count = int(cursor.fetchone()[0] or 0)
        except Exception:
            row_count = 0
        tables.append(
            {
                "name": table_name,
                "label": OFFLINE_DATA_TABLES.get(table_name, table_name),
                "row_count": row_count,
                "column_count": len(columns),
                "columns": columns,
                "foreign_keys": foreign_keys,
                "indexes": indexes,
                "sql": table["sql"],
                "data_exposed": table_name in OFFLINE_DATA_TABLES,
            }
        )
    return {
        "summary": {
            "table_count": len(tables),
            "column_count": sum(table["column_count"] for table in tables),
            "relationship_count": len(relationships),
            "index_count": sum(len(table["indexes"]) for table in tables),
            "record_count": sum(table["row_count"] for table in tables),
            "web_exposed_table_count": sum(1 for table in tables if table["data_exposed"]),
        },
        "tables": tables,
        "relationships": relationships,
    }


def public_user(user: dict[str, Any] | None) -> dict[str, Any]:
    if not user:
        return {}
    clean = dict(user)
    clean.pop("password", None)
    clean["permissions"] = PermissionManager.get_role_permissions(clean.get("role"))
    return clean


def current_user() -> dict[str, Any] | None:
    user_id = session.get("user_id") or token_user_id()
    if not user_id:
        return None
    return AuthManager().get_user(user_id)


def make_auth_token(user_id: int) -> str:
    serializer = URLSafeTimedSerializer(current_app.secret_key, salt="fastrack-web-auth")
    return serializer.dumps({"user_id": int(user_id)})


def token_user_id() -> int | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None
    serializer = URLSafeTimedSerializer(current_app.secret_key, salt="fastrack-web-auth")
    try:
        payload = serializer.loads(token, max_age=7 * 24 * 3600)
        return int(payload.get("user_id") or 0) or None
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return None


def ensure_web_admin():
    """Create a first admin account for web deployments when the DB is empty."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    if int(cursor.fetchone()[0] or 0):
        return
    username = os.environ.get("FASTRACK_BOOTSTRAP_USER", "admin")
    password = os.environ.get("FASTRACK_BOOTSTRAP_PASSWORD", "Admin@2026!")
    full_name = os.environ.get("FASTRACK_BOOTSTRAP_NAME", "Quan tri he thong")
    email = os.environ.get("FASTRACK_BOOTSTRAP_EMAIL", "admin@fastrack.local")
    hashed = AuthManager.hash_password(password)
    cursor.execute(
        """
        INSERT OR IGNORE INTO users (username, password, full_name, email, role, active, password_changed_at, must_change_password)
        VALUES (?, ?, ?, ?, 'admin', 1, CURRENT_TIMESTAMP, 1)
        """,
        (username, hashed, full_name, email),
    )
    conn.commit()


class WebReportGenerator:
    """Report queries for the web runtime without importing desktop Tk widgets."""

    def __init__(self):
        self.conn = get_connection()

    def get_expense_summary(self, start_date=None, end_date=None):
        cursor = self.conn.cursor()
        query = """
            SELECT ec.name, SUM(e.amount) as total, COUNT(e.id) as count
            FROM expenses e
            JOIN expense_categories ec ON e.category_id = ec.id
        """
        params = []
        if start_date and end_date:
            query += " WHERE e.expense_date BETWEEN ? AND ?"
            params = [start_date, end_date]
        query += " GROUP BY e.category_id ORDER BY total DESC"
        cursor.execute(query, params)
        return cursor.fetchall()

    def get_project_expense_summary(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT p.name, SUM(e.amount) as total, COUNT(e.id) as count
            FROM expenses e
            LEFT JOIN projects p ON e.project_id = p.id
            GROUP BY e.project_id
            ORDER BY total DESC
            """
        )
        return cursor.fetchall()

    def get_monthly_expense_summary(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT strftime('%Y-%m', expense_date) AS month, SUM(amount) AS total
            FROM expenses
            GROUP BY strftime('%Y-%m', expense_date)
            ORDER BY month
            """
        )
        return cursor.fetchall()

    def get_material_stock_summary(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT name, quantity, unit_price, quantity * COALESCE(unit_price, 0) AS total_value
            FROM materials
            WHERE status = 'active'
            ORDER BY total_value DESC
            LIMIT 12
            """
        )
        return cursor.fetchall()


class WebFinanceCenter:
    """Finance-control queries that are safe to run in the web container."""

    def __init__(self):
        self.conn = get_connection()

    def month_range(self):
        today = date.today()
        start = today.replace(day=1)
        next_month = (start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1))
        return start.isoformat(), (next_month - timedelta(days=1)).isoformat()

    def vat_declaration(self, start_date=None, end_date=None):
        start_date, end_date = start_date or self.month_range()[0], end_date or self.month_range()[1]
        input_rows = self._input_vat_rows(start_date, end_date)
        output_rows = self._output_vat_rows(start_date, end_date)
        input_vat = sum(row["vat_amount"] for row in input_rows)
        output_vat = sum(row["vat_amount"] for row in output_rows)
        return {
            "period": f"{start_date} - {end_date}",
            "input_rows": input_rows,
            "output_rows": output_rows,
            "input_taxable": sum(row["taxable_amount"] for row in input_rows),
            "input_vat": input_vat,
            "output_taxable": sum(row["taxable_amount"] for row in output_rows),
            "output_vat": output_vat,
            "vat_payable": max(output_vat - input_vat, 0),
            "vat_credit": max(input_vat - output_vat, 0),
        }

    def _input_vat_rows(self, start_date, end_date):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT d.doc_date, d.doc_number, d.supplier_name,
                   COALESCE(s.tax_code, '') AS tax_code,
                   COALESCE(d.amount, 0) AS total_amount,
                   COALESCE(d.vat_rate, 10) AS vat_rate
            FROM documents d
            LEFT JOIN suppliers s ON s.id = d.supplier_id
            WHERE d.doc_date BETWEEN ? AND ?
              AND COALESCE(d.amount, 0) > 0
            ORDER BY d.doc_date DESC, d.id DESC
            LIMIT 100
            """,
            (start_date, end_date),
        )
        rows = []
        for row in cursor.fetchall():
            total = float(row["total_amount"] or 0)
            rate = max(float(row["vat_rate"] or 10), 0) / 100
            taxable = total / (1 + rate) if rate else total
            rows.append(
                {
                    "invoice_date": row["doc_date"],
                    "invoice_number": row["doc_number"],
                    "partner_name": row["supplier_name"],
                    "tax_code": row["tax_code"],
                    "taxable_amount": taxable,
                    "vat_amount": total - taxable,
                    "total_amount": total,
                }
            )
        return rows

    def _output_vat_rows(self, start_date, end_date):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT r.revenue_date, COALESCE(c.contract_no, '') AS contract_no,
                   COALESCE(c.partner_name, '') AS partner_name,
                   COALESCE(r.amount, 0) AS amount,
                   COALESCE(r.vat_amount, 0) AS vat_amount,
                   COALESCE(r.description, '') AS description
            FROM project_revenues r
            LEFT JOIN project_contracts c ON c.id = r.contract_id
            WHERE r.revenue_date BETWEEN ? AND ?
            ORDER BY r.revenue_date DESC, r.id DESC
            LIMIT 100
            """,
            (start_date, end_date),
        )
        return [
            {
                "invoice_date": row["revenue_date"],
                "invoice_number": row["contract_no"],
                "partner_name": row["partner_name"],
                "tax_code": "",
                "taxable_amount": float(row["amount"] or 0),
                "vat_amount": float(row["vat_amount"] or 0),
                "total_amount": float(row["amount"] or 0) + float(row["vat_amount"] or 0),
                "description": row["description"],
            }
            for row in cursor.fetchall()
        ]

    def payroll_summary(self, period=None):
        period = period or date.today().strftime("%Y-%m")
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT pp.period, pp.gross_amount, pp.insurance_amount, pp.pit_amount,
                   pp.net_amount, pp.status, COUNT(pl.id) AS line_count
            FROM payroll_periods pp
            LEFT JOIN payroll_lines pl ON pl.payroll_period_id = pp.id
            WHERE pp.period = ?
            GROUP BY pp.id
            """,
            (period,),
        )
        current = cursor.fetchone()
        cursor.execute(
            """
            SELECT pp.period, pp.gross_amount, pp.pit_amount, pp.net_amount,
                   pp.status, COUNT(pl.id) AS line_count
            FROM payroll_periods pp
            LEFT JOIN payroll_lines pl ON pl.payroll_period_id = pp.id
            GROUP BY pp.id
            ORDER BY pp.period DESC
            LIMIT 12
            """
        )
        return {
            "period": period,
            "current": row_to_dict(current) if current else {},
            "recent": [row_to_dict(row) for row in cursor.fetchall()],
        }


class WebAccountingWorkspace:
    """Core accounting books and statements for the web workspace."""

    def __init__(self):
        self.conn = get_connection()

    def account_balances_as_of(self, as_of_date=None):
        as_of_date = as_of_date or date.today().isoformat()
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT account_code,
                   SUM(debit_amount) AS debit,
                   SUM(credit_amount) AS credit
            FROM (
                SELECT debit_account AS account_code, amount AS debit_amount, 0 AS credit_amount
                FROM journal_entries
                WHERE COALESCE(debit_account, '') <> ''
                  AND entry_date <= ?
                  AND COALESCE(is_reversed, 0) = 0
                UNION ALL
                SELECT credit_account AS account_code, 0 AS debit_amount, amount AS credit_amount
                FROM journal_entries
                WHERE COALESCE(credit_account, '') <> ''
                  AND entry_date <= ?
                  AND COALESCE(is_reversed, 0) = 0
                UNION ALL
                SELECT l.account_code, l.debit_amount, l.credit_amount
                FROM journal_entry_lines l
                JOIN journal_entries j ON j.id = l.journal_entry_id
                WHERE j.entry_date <= ?
                  AND COALESCE(j.is_reversed, 0) = 0
            )
            GROUP BY account_code
            """,
            (as_of_date, as_of_date, as_of_date),
        )
        balances = {
            row["account_code"]: {
                "account_code": row["account_code"],
                "debit": float(row["debit"] or 0),
                "credit": float(row["credit"] or 0),
            }
            for row in cursor.fetchall()
        }

        cursor.execute(
            """
            SELECT account_code, account_name, account_type, account_level,
                   parent_code, COALESCE(account_class, '') AS account_class,
                   COALESCE(normal_balance, '') AS normal_balance,
                   COALESCE(is_cost_account, 0) AS is_cost_account,
                   COALESCE(active, 1) AS active
            FROM accounts
            ORDER BY account_code
            """
        )
        accounts = []
        for row in cursor.fetchall():
            debit = balances.get(row["account_code"], {}).get("debit", 0)
            credit = balances.get(row["account_code"], {}).get("credit", 0)
            normal_balance = (row["normal_balance"] or "").lower()
            if not normal_balance:
                normal_balance = "credit" if str(row["account_code"])[:1] in ("3", "4", "5", "7") else "debit"
            balance = credit - debit if normal_balance == "credit" else debit - credit
            accounts.append(
                {
                    **row_to_dict(row),
                    "debit": debit,
                    "credit": credit,
                    "balance": balance,
                }
            )
        return accounts

    def trial_balance(self, as_of_date=None):
        return [row for row in self.account_balances_as_of(as_of_date) if row["debit"] or row["credit"] or row["balance"]]

    def balance_sheet(self, as_of_date=None):
        rows = []
        for account in self.account_balances_as_of(as_of_date):
            code = str(account.get("account_code") or "")
            acc_type = (account.get("account_type") or account.get("account_class") or "").lower()
            if code[:1] in ("1", "2") or "tai san" in acc_type or "tài sản" in acc_type:
                group = "Tai san"
            elif code[:1] in ("3", "4") or "no phai tra" in acc_type or "nợ phải trả" in acc_type or "von" in acc_type or "vốn" in acc_type:
                group = "Nguon von"
            else:
                continue
            if account["balance"] == 0:
                continue
            rows.append({**account, "group": group})
        totals = {
            "assets": sum(row["balance"] for row in rows if row["group"] == "Tai san"),
            "capital": sum(row["balance"] for row in rows if row["group"] == "Nguon von"),
        }
        totals["difference"] = totals["assets"] - totals["capital"]
        return {"as_of_date": as_of_date or date.today().isoformat(), "rows": rows, "totals": totals}

    def account_summary(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(account_type, 'Khac') AS account_type,
                   COUNT(*) AS account_count,
                   SUM(CASE WHEN COALESCE(active, 1) = 1 THEN 1 ELSE 0 END) AS active_count
            FROM accounts
            GROUP BY COALESCE(account_type, 'Khac')
            ORDER BY account_type
            """
        )
        return [row_to_dict(row) for row in cursor.fetchall()]

    def journal_entries(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT j.id, j.entry_date, j.entry_number, j.description,
                   j.debit_account, da.account_name AS debit_name,
                   j.credit_account, ca.account_name AS credit_name,
                   COALESCE(j.amount, 0) AS amount,
                   COALESCE(p.code, '') AS project_code,
                   COALESCE(p.name, '') AS project_name,
                   j.reference_type, j.fiscal_period, j.created_at
            FROM journal_entries j
            LEFT JOIN accounts da ON da.account_code = j.debit_account
            LEFT JOIN accounts ca ON ca.account_code = j.credit_account
            LEFT JOIN projects p ON p.id = j.project_id
            WHERE COALESCE(j.is_reversed, 0) = 0
            ORDER BY j.entry_date DESC, j.id DESC
            LIMIT 120
            """
        )
        return [row_to_dict(row) for row in cursor.fetchall()]

    def ar_ap_items(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT a.id, a.partner_type, a.partner_name,
                   COALESCE(p.code, '') AS project_code,
                   COALESCE(p.name, '') AS project_name,
                   a.due_date, COALESCE(a.amount, 0) AS amount,
                   COALESCE(a.paid_amount, 0) AS paid_amount,
                   COALESCE(a.amount, 0) - COALESCE(a.paid_amount, 0) AS remaining_amount,
                   a.status, a.source_type, a.created_at
            FROM ar_ap_items a
            LEFT JOIN projects p ON p.id = a.project_id
            ORDER BY CASE WHEN a.status = 'open' THEN 0 ELSE 1 END, a.due_date, a.id DESC
            LIMIT 120
            """
        )
        return [row_to_dict(row) for row in cursor.fetchall()]

    def ar_ap_summary(self):
        rows = self.ar_ap_items()
        open_rows = [row for row in rows if row.get("status") == "open"]
        return {
            "item_count": len(rows),
            "open_count": len(open_rows),
            "total_amount": sum(float(row.get("amount") or 0) for row in rows),
            "open_amount": sum(float(row.get("remaining_amount") or 0) for row in open_rows),
        }

    def project_cost_collection(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(p.code, '') AS project_code,
                   COALESCE(p.name, 'Khong gan du an') AS project_name,
                   COALESCE(ec.name, 'Khac') AS category_name,
                   COUNT(e.id) AS line_count,
                   COALESCE(SUM(e.amount), 0) AS amount
            FROM expenses e
            LEFT JOIN projects p ON p.id = e.project_id
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            GROUP BY e.project_id, e.category_id
            ORDER BY amount DESC
            LIMIT 80
            """
        )
        return [row_to_dict(row) for row in cursor.fetchall()]

    def fiscal_status(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT fiscal_year,
                   COUNT(*) AS period_count,
                   SUM(CASE WHEN COALESCE(is_locked, 0) = 1 THEN 1 ELSE 0 END) AS locked_count,
                   SUM(CASE WHEN COALESCE(is_closed, 0) = 1 THEN 1 ELSE 0 END) AS closed_count
            FROM fiscal_calendar
            GROUP BY fiscal_year
            ORDER BY fiscal_year DESC
            LIMIT 5
            """
        )
        return [row_to_dict(row) for row in cursor.fetchall()]

    def snapshot(self, as_of_date=None):
        as_of_date = as_of_date or date.today().isoformat()
        accounts = self.account_balances_as_of(as_of_date)
        trial = [row for row in accounts if row["debit"] or row["credit"] or row["balance"]]
        journals = self.journal_entries()
        ar_ap = self.ar_ap_items()
        return {
            "as_of_date": as_of_date,
            "kpis": {
                "account_count": len(accounts),
                "active_account_count": sum(1 for row in accounts if row.get("active")),
                "journal_count": len(journals),
                "journal_amount": sum(float(row.get("amount") or 0) for row in journals),
                "trial_debit": sum(float(row.get("debit") or 0) for row in trial),
                "trial_credit": sum(float(row.get("credit") or 0) for row in trial),
                "open_ar_ap": sum(float(row.get("remaining_amount") or 0) for row in ar_ap if row.get("status") == "open"),
            },
            "accounts": accounts,
            "account_summary": self.account_summary(),
            "trial_balance": trial,
            "balance_sheet": self.balance_sheet(as_of_date),
            "journal_entries": journals,
            "ar_ap_items": ar_ap,
            "ar_ap_summary": self.ar_ap_summary(),
            "project_cost_collection": self.project_cost_collection(),
            "fiscal_status": self.fiscal_status(),
        }


class WebGoogleExportCenter:
    """Monthly accounting export for CSV and Google Sheets."""

    def __init__(self):
        self.conn = get_connection()

    def month_range(self, month: str | None):
        month = (month or date.today().strftime("%Y-%m"))[:7]
        year, month_no = [int(part) for part in month.split("-")]
        start = date(year, month_no, 1)
        if month_no == 12:
            end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(year, month_no + 1, 1) - timedelta(days=1)
        return month, start.isoformat(), end.isoformat()

    def monthly_report(self, month: str | None = None):
        month, start_date, end_date = self.month_range(month)
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT e.expense_date, COALESCE(p.code, '') AS project_code,
                   COALESCE(p.name, '') AS project_name,
                   COALESCE(ec.name, '') AS category_name,
                   e.description, COALESCE(e.amount, 0) AS amount,
                   e.paid_by, e.payment_method, e.status
            FROM expenses e
            LEFT JOIN projects p ON p.id = e.project_id
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            WHERE e.expense_date BETWEEN ? AND ?
            ORDER BY e.expense_date, e.id
            """,
            (start_date, end_date),
        )
        expenses = [row_to_dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT COALESCE(ec.name, 'Khac') AS category_name,
                   COUNT(e.id) AS line_count,
                   COALESCE(SUM(e.amount), 0) AS amount
            FROM expenses e
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            WHERE e.expense_date BETWEEN ? AND ?
            GROUP BY e.category_id
            ORDER BY amount DESC
            """,
            (start_date, end_date),
        )
        by_category = [row_to_dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT COALESCE(p.code, '') AS project_code,
                   COALESCE(p.name, 'Khong gan du an') AS project_name,
                   COUNT(e.id) AS line_count,
                   COALESCE(SUM(e.amount), 0) AS amount
            FROM expenses e
            LEFT JOIN projects p ON p.id = e.project_id
            WHERE e.expense_date BETWEEN ? AND ?
            GROUP BY e.project_id
            ORDER BY amount DESC
            """,
            (start_date, end_date),
        )
        by_project = [row_to_dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT COALESCE(supplier_name, 'Khac') AS supplier_name,
                   COUNT(id) AS document_count,
                   COALESCE(SUM(amount), 0) AS amount
            FROM documents
            WHERE doc_date BETWEEN ? AND ?
            GROUP BY supplier_name
            ORDER BY amount DESC
            LIMIT 20
            """,
            (start_date, end_date),
        )
        suppliers = [row_to_dict(row) for row in cursor.fetchall()]
        return {
            "month": month,
            "start_date": start_date,
            "end_date": end_date,
            "summary": {
                "expense_count": len(expenses),
                "expense_total": sum(float(row.get("amount") or 0) for row in expenses),
                "category_count": len(by_category),
                "project_count": len(by_project),
            },
            "expenses": expenses,
            "by_category": by_category,
            "by_project": by_project,
            "top_suppliers": suppliers,
        }

    def report_to_csv(self, report: dict[str, Any]):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Bao cao thang", report["month"], report["start_date"], report["end_date"]])
        writer.writerow([])
        writer.writerow(["Tong chi phi", report["summary"]["expense_total"], "So dong", report["summary"]["expense_count"]])
        writer.writerow([])
        writer.writerow(["Chi tiet chi phi"])
        writer.writerow(["Ngay", "Ma du an", "Du an", "Danh muc", "Dien giai", "So tien", "Nguoi chi", "Phuong thuc", "Trang thai"])
        for row in report["expenses"]:
            writer.writerow(
                [
                    row.get("expense_date"),
                    row.get("project_code"),
                    row.get("project_name"),
                    row.get("category_name"),
                    row.get("description"),
                    row.get("amount"),
                    row.get("paid_by"),
                    row.get("payment_method"),
                    row.get("status"),
                ]
            )
        writer.writerow([])
        writer.writerow(["Tong hop theo danh muc"])
        writer.writerow(["Danh muc", "So dong", "So tien"])
        for row in report["by_category"]:
            writer.writerow([row.get("category_name"), row.get("line_count"), row.get("amount")])
        writer.writerow([])
        writer.writerow(["Tong hop theo du an"])
        writer.writerow(["Ma du an", "Du an", "So dong", "So tien"])
        for row in report["by_project"]:
            writer.writerow([row.get("project_code"), row.get("project_name"), row.get("line_count"), row.get("amount")])
        writer.writerow([])
        writer.writerow(["Top nha cung cap/chung tu"])
        writer.writerow(["Nha cung cap", "So chung tu", "So tien"])
        for row in report["top_suppliers"]:
            writer.writerow([row.get("supplier_name"), row.get("document_count"), row.get("amount")])
        return output.getvalue()

    def sheets_values(self, report: dict[str, Any]):
        rows = [
            ["Bao cao thang", report["month"], report["start_date"], report["end_date"]],
            ["Tong chi phi", report["summary"]["expense_total"], "So dong", report["summary"]["expense_count"]],
            [],
            ["Chi tiet chi phi"],
            ["Ngay", "Ma du an", "Du an", "Danh muc", "Dien giai", "So tien", "Nguoi chi", "Phuong thuc", "Trang thai"],
        ]
        rows.extend(
            [
                row.get("expense_date"),
                row.get("project_code"),
                row.get("project_name"),
                row.get("category_name"),
                row.get("description"),
                row.get("amount"),
                row.get("paid_by"),
                row.get("payment_method"),
                row.get("status"),
            ]
            for row in report["expenses"]
        )
        rows.extend([[], ["Tong hop theo danh muc"], ["Danh muc", "So dong", "So tien"]])
        rows.extend([[row.get("category_name"), row.get("line_count"), row.get("amount")] for row in report["by_category"]])
        rows.extend([[], ["Tong hop theo du an"], ["Ma du an", "Du an", "So dong", "So tien"]])
        rows.extend([[row.get("project_code"), row.get("project_name"), row.get("line_count"), row.get("amount")] for row in report["by_project"]])
        return rows

    def export_to_sheets(self, report: dict[str, Any], spreadsheet_id: str | None = None, sheet_title: str | None = None):
        spreadsheet_id = spreadsheet_id or os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID")
        sheet_title = sheet_title or f"Bao cao {report['month']}"
        if not spreadsheet_id:
            return {
                "ok": False,
                "setup_needed": True,
                "message": "Can spreadsheet_id hoac bien moi truong GOOGLE_SHEETS_SPREADSHEET_ID.",
            }
        try:
            import google.auth
            from google.auth.transport.requests import Request
        except ImportError as exc:
            return {"ok": False, "setup_needed": True, "message": f"Thieu google-auth: {exc}"}

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
        credentials.refresh(Request())
        token = credentials.token
        base = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
        self._sheets_request(
            f"{base}:batchUpdate",
            token,
            {
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": sheet_title,
                            }
                        }
                    }
                ]
            },
            ignore_statuses={400},
        )
        values = {"range": f"'{sheet_title}'!A1", "majorDimension": "ROWS", "values": self.sheets_values(report)}
        result = self._sheets_request(
            f"{base}/values/{quote(sheet_title + '!A1', safe='!')}:update?valueInputOption=USER_ENTERED",
            token,
            values,
        )
        return {
            "ok": True,
            "spreadsheet_id": spreadsheet_id,
            "sheet_title": sheet_title,
            "updated_cells": result.get("updatedCells", 0),
            "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
        }

    def _sheets_request(self, url: str, token: str, payload: dict[str, Any], ignore_statuses: set[int] | None = None):
        body = json.dumps(payload).encode("utf-8")
        req = url_request.Request(
            url,
            data=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST" if ":batchUpdate" in url else "PUT",
        )
        try:
            with url_request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            if ignore_statuses and getattr(getattr(exc, "fp", None), "status", None) in ignore_statuses:
                return {}
            raise


class WebGoogleDriveBackup:
    """Create a verified SQLite backup and upload it to Google Drive."""

    def create_and_upload(self, folder_id: str | None = None):
        folder_id = folder_id or os.environ.get("GOOGLE_DRIVE_BACKUP_FOLDER_ID")
        if not folder_id:
            return {
                "ok": False,
                "setup_needed": True,
                "message": "Can folder_id hoac bien moi truong GOOGLE_DRIVE_BACKUP_FOLDER_ID.",
            }
        manager = BackupManager()
        backup_name = f"fastrack_backup_{date.today().isoformat()}.db"
        ok, message = manager.create_backup(backup_name)
        if not ok:
            return {"ok": False, "message": message}
        backup_path = os.path.join(manager.backup_dir, backup_name)
        return self.upload_file(backup_path, folder_id, message)

    def upload_file(self, path: str, folder_id: str, backup_message: str = ""):
        if not os.path.exists(path):
            return {"ok": False, "message": "File backup khong ton tai."}
        try:
            import google.auth
            from google.auth.transport.requests import Request
        except ImportError as exc:
            return {"ok": False, "setup_needed": True, "message": f"Thieu google-auth: {exc}"}

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive.file"])
        credentials.refresh(Request())
        token = credentials.token
        metadata = {
            "name": os.path.basename(path),
            "parents": [folder_id],
            "description": "FasTrack ERP SQLite verified backup",
        }
        boundary = "fastrack-drive-backup"
        with open(path, "rb") as handle:
            file_bytes = handle.read()
        body = b"\r\n".join(
            [
                f"--{boundary}".encode(),
                b"Content-Type: application/json; charset=UTF-8",
                b"",
                json.dumps(metadata).encode("utf-8"),
                f"--{boundary}".encode(),
                b"Content-Type: application/x-sqlite3",
                b"",
                file_bytes,
                f"--{boundary}--".encode(),
            ]
        )
        req = url_request.Request(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink,size",
            data=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": f"multipart/related; boundary={boundary}"},
            method="POST",
        )
        with url_request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        return {
            "ok": True,
            "message": backup_message,
            "file": result,
            "local_backup": path,
        }


def api_error(handler):
    @wraps(handler)
    def wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised through Flask runtime.
            return jsonify({"error": str(exc)}), 400

    return wrapper


def require_permission(permission: str):
    def decorator(handler):
        @wraps(handler)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({"error": "Can dang nhap"}), 401
            if not PermissionManager.has_permission(user.get("role"), permission):
                return jsonify({"error": "Khong du quyen"}), 403
            return handler(*args, **kwargs)

        return wrapper

    return decorator


def create_app():
    if Flask is None:
        raise RuntimeError("Cần cài Flask để chạy bản web: pip install flask")

    init_database()
    ensure_web_admin()
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fastrack-dev-session-key-change-me")
    app.config["JSON_AS_ASCII"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_COOKIE_SECURE", "0") in ("1", "true", "yes")

    @app.before_request
    def require_api_session():
        public_paths = ("/api/health", "/api/auth/login", "/api/auth/logout", "/api/auth/me")
        if request.path.startswith("/api/") and request.path not in public_paths and not current_user():
            return jsonify({"error": "Can dang nhap"}), 401

    @app.get("/")
    def index():
        return Response(INDEX_HTML, mimetype="text/html; charset=utf-8")

    @app.get("/manifest.json")
    def manifest():
        return jsonify(
            {
                "name": "FasTrack ERP Web",
                "short_name": "FasTrack",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#f4f6f8",
                "theme_color": "#1e3a5f",
                "icons": [],
            }
        )

    @app.get("/service-worker.js")
    def service_worker():
        return Response(SERVICE_WORKER, mimetype="text/javascript; charset=utf-8")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "date": date.today().isoformat()})

    @app.get("/api/auth/me")
    def auth_me():
        user = current_user()
        return jsonify({"authenticated": bool(user), "user": public_user(user)})

    @app.post("/api/auth/login")
    @api_error
    def auth_login():
        data = request.get_json(force=True)
        ok, user = AuthManager().authenticate(data.get("username", ""), data.get("password", ""))
        if not ok:
            return jsonify({"error": "Sai tai khoan hoac mat khau"}), 401
        session.clear()
        session["user_id"] = user["id"]
        session["role"] = user.get("role")
        AuditLogManager().log("user", user["id"], "login", user["id"], new_value="Dang nhap web")
        return jsonify({"authenticated": True, "token": make_auth_token(user["id"]), "user": public_user(user)})

    @app.post("/api/auth/logout")
    def auth_logout():
        user_id = session.get("user_id")
        if user_id:
            try:
                AuditLogManager().log("user", user_id, "logout", user_id, new_value="Dang xuat web")
            except Exception:
                pass
        session.clear()
        return jsonify({"authenticated": False})

    @app.post("/api/auth/change-password")
    @api_error
    def change_password():
        user = current_user()
        if not user:
            return jsonify({"error": "Can dang nhap"}), 401
        data = request.get_json(force=True)
        ok, message = AuthManager().change_password(user["id"], data.get("old_password", ""), data.get("new_password", ""))
        if not ok:
            return jsonify({"error": message}), 400
        AuditLogManager().log("user", user["id"], "change_password", user["id"], new_value="Doi mat khau web")
        return jsonify({"status": "saved", "message": message})

    @app.get("/api/users")
    @require_permission("manage_users")
    @api_error
    def users():
        return jsonify([public_user(row_to_dict(row)) for row in AuthManager().get_all_users()])

    @app.post("/api/users")
    @require_permission("manage_users")
    @api_error
    def create_user():
        data = request.get_json(force=True)
        ok, message = AuthManager().create_user(
            data["username"],
            data["password"],
            data.get("full_name", ""),
            data.get("email", ""),
            data.get("role", "employee"),
        )
        if not ok:
            return jsonify({"error": message}), 400
        AuditLogManager().log("user", None, "create_user", session.get("user_id"), new_value=data["username"])
        return jsonify({"status": "created", "message": message})

    @app.post("/api/users/<int:user_id>")
    @require_permission("manage_users")
    @api_error
    def update_user(user_id):
        data = request.get_json(force=True)
        ok, message = AuthManager().update_user(
            user_id,
            full_name=data.get("full_name", ""),
            email=data.get("email", ""),
            role=data.get("role", "employee"),
            active=int(data.get("active", 1)),
        )
        if not ok:
            return jsonify({"error": message}), 400
        AuditLogManager().log("user", user_id, "update_user", session.get("user_id"), new_value=data)
        return jsonify({"status": "saved", "message": message})

    @app.get("/api/dashboard")
    @api_error
    def dashboard():
        expenses = ExpenseManager()
        materials = MaterialManager()
        construction = ConstructionManager()
        report = WebReportGenerator()
        stats = expenses.get_statistics()
        conn = get_connection()
        cursor = conn.cursor()
        today = date.today()
        this_month_start = today.replace(day=1)
        previous_month_end = this_month_start - timedelta(days=1)
        previous_month_start = previous_month_end.replace(day=1)
        cursor.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
            """,
            (previous_month_start.isoformat(), previous_month_end.isoformat()),
        )
        previous_month_expenses = float(cursor.fetchone()[0] or 0)
        current_month_expenses = float(stats.get("monthly_expenses") or 0)
        month_delta = current_month_expenses - previous_month_expenses
        month_delta_percent = (month_delta / previous_month_expenses * 100) if previous_month_expenses else (100 if current_month_expenses else 0)
        categories = [
            {"name": row[0] or "Chưa phân loại", "total": row[1] or 0}
            for row in expenses.get_expenses_by_category()
        ]
        projects = [
            {"name": row[0] or "Không có dự án", "total": row[1] or 0}
            for row in expenses.get_expenses_by_project()
        ]
        cursor.execute(
            """
            SELECT p.id, p.code, p.name, p.location, COALESCE(p.budget, 0) AS budget,
                   COALESCE(SUM(e.amount), 0) AS spent,
                   COALESCE(AVG(w.percent_complete), 0) AS progress,
                   COUNT(DISTINCT w.id) AS work_item_count
            FROM projects p
            LEFT JOIN expenses e ON e.project_id = p.id
            LEFT JOIN construction_work_items w ON w.project_id = p.id
            WHERE p.status = 'active'
            GROUP BY p.id
            ORDER BY p.code
            LIMIT 8
            """
        )
        active_projects = []
        for row in cursor.fetchall():
            budget = float(row["budget"] or 0)
            spent = float(row["spent"] or 0)
            active_projects.append(
                {
                    "id": row["id"],
                    "code": row["code"],
                    "name": row["name"],
                    "location": row["location"],
                    "budget": budget,
                    "spent": spent,
                    "budget_used_percent": (spent / budget * 100) if budget else 0,
                    "progress": float(row["progress"] or 0),
                    "work_item_count": row["work_item_count"],
                }
            )
        cursor.execute("SELECT MAX(updated_at) FROM expenses")
        last_expense_update = cursor.fetchone()[0]
        cursor.execute("SELECT MAX(created_at) FROM documents")
        last_document_update = cursor.fetchone()[0]
        stock_value = sum(float(row[3] or 0) for row in report.get_material_stock_summary())
        low_stock = [
            row_to_dict(row, ("id", "code", "name", "unit", "quantity", "min_quantity", "category"))
            for row in materials.check_low_stock()
        ]
        return jsonify(
            {
                "stats": stats,
                "trend": {
                    "previous_month_expenses": previous_month_expenses,
                    "month_delta": month_delta,
                    "month_delta_percent": month_delta_percent,
                },
                "categories": categories[:8],
                "projects": projects[:8],
                "active_projects": active_projects,
                "construction": construction.get_dashboard(),
                "stock_value": stock_value,
                "low_stock": low_stock,
                "sync": {
                    "mode": "SQLite shared desktop/web",
                    "last_expense_update": last_expense_update,
                    "last_document_update": last_document_update,
                    "refreshed_at": date.today().isoformat(),
                },
            }
        )

    @app.get("/api/projects")
    @api_error
    def projects():
        return jsonify([row_to_dict(row) for row in UtilityManager().list_projects()])

    @app.post("/api/projects")
    @api_error
    def save_project():
        data = request.get_json(force=True)
        UtilityManager().save_project(
            data["code"],
            data["name"],
            data.get("location", ""),
            float(data.get("budget") or 0),
            data.get("status", "active"),
        )
        return jsonify({"status": "saved"})

    @app.get("/api/categories")
    @api_error
    def categories():
        return jsonify([row_to_dict(row) for row in UtilityManager().list_categories()])

    @app.post("/api/categories")
    @api_error
    def save_category():
        data = request.get_json(force=True)
        UtilityManager().save_category(data["code"], data["name"], data.get("description", ""))
        return jsonify({"status": "saved"})

    @app.get("/api/expenses")
    @api_error
    def expenses():
        rows = ExpenseManager().get_all_expenses()
        keys = (
            "id",
            "expense_date",
            "project_name",
            "category_name",
            "description",
            "amount",
            "status",
            "document_count",
            "attachment_count",
        )
        return jsonify([row_to_dict(row, keys) for row in rows])

    @app.post("/api/expenses")
    @api_error
    def create_expense():
        data = request.get_json(force=True)
        expense_id = ExpenseManager().add_expense(
            data.get("expense_date") or date.today().isoformat(),
            data.get("project_id") or None,
            int(data["category_id"]),
            data.get("description", ""),
            float(data.get("amount") or 0),
            data.get("paid_by", ""),
            data.get("payment_method", "Tiền mặt"),
            data.get("notes", ""),
            int(data.get("created_by") or session.get("user_id") or 1),
        )
        return jsonify({"id": expense_id, "status": "created"})

    @app.get("/api/inventory")
    @api_error
    def inventory():
        keys = ("id", "code", "name", "unit", "quantity", "unit_price", "category", "status")
        return jsonify([row_to_dict(row, keys) for row in MaterialManager().get_all_materials()])

    @app.get("/api/inventory/history")
    @api_error
    def inventory_history():
        keys = ("id", "code", "name", "transaction_type", "quantity", "transaction_date", "project_name", "notes")
        return jsonify([row_to_dict(row, keys) for row in MaterialManager().get_inventory_history(limit=50)])

    @app.get("/api/inventory-workspace")
    @api_error
    def inventory_workspace():
        return jsonify(inventory_workspace_snapshot())

    @app.post("/api/inventory/transactions")
    @api_error
    def create_inventory_transaction():
        data = request.get_json(force=True)
        manager = MaterialManager()
        transaction_type = data["transaction_type"]
        if transaction_type == "import":
            transaction_id = manager.receive_material(
                int(data["material_id"]),
                float(data.get("quantity") or 0),
                float(data.get("unit_price") or data.get("price") or 0),
                received_by=int(data.get("created_by") or session.get("user_id") or 1),
                notes=data.get("notes", ""),
            )
        elif transaction_type == "export":
            transaction_id = manager.issue_material(
                int(data["material_id"]),
                float(data.get("quantity") or 0),
                data.get("project_id") or None,
                data.get("work_item_id") or None,
                issued_by=int(data.get("created_by") or session.get("user_id") or 1),
                notes=data.get("notes", ""),
            )
        else:
            raise ValueError("Loai giao dich kho khong hop le")
        return jsonify({"id": transaction_id, "status": "created"})

    @app.post("/api/material-standards")
    @api_error
    def create_material_standard():
        data = request.get_json(force=True)
        MaterialControlManager().save_standard(
            int(data["material_id"]),
            int(data["work_item_id"]) if data.get("work_item_id") else None,
            data.get("basis_unit") or "m2",
            float(data.get("standard_qty_per_unit") or 0),
            float(data.get("tolerance_percent") or 15),
            data.get("notes", ""),
        )
        return jsonify({"status": "saved"})

    @app.post("/api/purchase-orders/from-alert")
    @api_error
    def create_purchase_order_from_alert():
        data = request.get_json(force=True)
        po_number = data.get("po_number") or f"PO-WEB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        quantity = float(data.get("quantity") or data.get("shortage_qty") or 0)
        material_id = int(data["material_id"]) if data.get("material_id") else None
        material_name = data.get("material_name") or "Vat tu can mua"
        unit_price = float(data.get("unit_price") or 0)
        po_id = PurchaseOrderManager().create_purchase_order(
            po_number,
            supplier_name=data.get("supplier_name", ""),
            expected_date=data.get("expected_date"),
            notes=data.get("notes") or "Tao tu canh bao ton kho web",
            lines=[
                {
                    "material_id": material_id,
                    "description": material_name,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "project_id": data.get("project_id") or None,
                }
            ],
        )
        return jsonify({"id": po_id, "status": "draft"})

    @app.post("/api/inventory/materials")
    @api_error
    def create_material():
        data = request.get_json(force=True)
        material_id = MaterialManager().add_material(
            data["code"],
            data["name"],
            data.get("unit", ""),
            float(data.get("unit_price") or 0),
            data.get("category", ""),
            data.get("supplier", ""),
            float(data.get("min_quantity") or 0),
        )
        return jsonify({"id": material_id, "status": "created"})

    @app.get("/api/documents")
    @api_error
    def documents():
        keys = (
            "id",
            "doc_type",
            "doc_number",
            "doc_date",
            "supplier_name",
            "description",
            "amount",
            "project_name",
            "status",
            "expense_id",
            "vat_rate",
        )
        return jsonify([row_to_dict(row, keys) for row in DocumentManager().get_all_documents()])

    @app.post("/api/documents")
    @api_error
    def create_document():
        data = request.get_json(force=True)
        document_id = DocumentManager().add_document(
            data.get("doc_type", "Hóa đơn"),
            data.get("doc_number", ""),
            data.get("doc_date") or date.today().isoformat(),
            data.get("supplier_name", ""),
            data.get("description", ""),
            float(data.get("amount") or 0),
            data.get("project_id") or None,
            data.get("category_id") or None,
            data.get("file_path", ""),
            int(data.get("created_by") or session.get("user_id") or 1),
            expense_id=data.get("expense_id") or None,
            status=data.get("status", "draft"),
            vat_rate=float(data.get("vat_rate") or 10),
        )
        return jsonify({"id": document_id, "status": "created"})

    @app.post("/api/documents/<int:document_id>/status")
    @api_error
    def update_document_status(document_id):
        data = request.get_json(force=True)
        DocumentManager().update_document_status(document_id, data.get("status", "draft"))
        return jsonify({"status": "saved"})

    @app.get("/api/documents/<int:document_id>/validation")
    @api_error
    def validate_document(document_id):
        return jsonify(DocumentManager().validate_invoice_compliance(document_id))

    @app.get("/api/construction/work-items")
    @api_error
    def construction_work_items():
        keys = (
            "id",
            "project_code",
            "project_name",
            "item_code",
            "item_name",
            "unit",
            "planned_quantity",
            "completed_quantity",
            "percent_complete",
            "unit_price",
            "planned_value",
            "completed_value",
            "actual_expense",
            "status",
            "notes",
        )
        return jsonify([row_to_dict(row, keys) for row in ConstructionManager().get_work_items()])

    @app.get("/api/construction/diaries")
    @api_error
    def construction_diaries():
        keys = ("id", "diary_date", "project_code", "project_name", "weather", "manpower", "equipment", "work_content", "issues", "reporter")
        return jsonify([row_to_dict(row, keys) for row in ConstructionManager().get_site_diaries()])

    @app.post("/api/construction/diaries")
    @api_error
    def create_construction_diary():
        data = request.get_json(force=True)
        diary_id = ConstructionManager().add_site_diary(
            data.get("diary_date") or date.today().isoformat(),
            data.get("project_id") or None,
            data.get("weather", ""),
            data.get("manpower", ""),
            data.get("equipment", ""),
            data.get("work_content", ""),
            data.get("issues", ""),
            data.get("reporter", ""),
        )
        return jsonify({"id": diary_id, "status": "created"})

    @app.get("/api/reports/monthly-expenses")
    @api_error
    def monthly_expenses():
        return jsonify(
            [
                {"month": row[0] or "N/A", "total": row[1] or 0}
                for row in WebReportGenerator().get_monthly_expense_summary()
            ]
        )

    @app.get("/api/reports/summary")
    @api_error
    def report_summary():
        report = WebReportGenerator()
        return jsonify(
            {
                "expense_summary": [
                    {"category": row[0] or "N/A", "total": row[1] or 0, "count": row[2] or 0}
                    for row in report.get_expense_summary()
                ],
                "project_expenses": [
                    {"project": row[0] or "Không có dự án", "total": row[1] or 0, "count": row[2] or 0}
                    for row in report.get_project_expense_summary()
                ],
                "monthly_expenses": [
                    {"month": row[0] or "N/A", "total": row[1] or 0}
                    for row in report.get_monthly_expense_summary()
                ],
                "stock": [
                    {"name": row[0] or "", "quantity": row[1] or 0, "unit_price": row[2] or 0, "total_value": row[3] or 0}
                    for row in report.get_material_stock_summary()
                ],
            }
        )

    @app.get("/api/export/monthly-report")
    @api_error
    def monthly_report_export():
        return jsonify(WebGoogleExportCenter().monthly_report(request.args.get("month")))

    @app.get("/api/export/monthly-report.csv")
    @api_error
    def monthly_report_csv():
        exporter = WebGoogleExportCenter()
        report = exporter.monthly_report(request.args.get("month"))
        csv_text = exporter.report_to_csv(report)
        filename = f"fastrack-monthly-report-{report['month']}.csv"
        return Response(
            "\ufeff" + csv_text,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.post("/api/export/sheets")
    @api_error
    def monthly_report_sheets():
        data = request.get_json(silent=True) or {}
        exporter = WebGoogleExportCenter()
        report = exporter.monthly_report(data.get("month") or request.args.get("month"))
        result = exporter.export_to_sheets(
            report,
            data.get("spreadsheet_id") or request.args.get("spreadsheet_id"),
            data.get("sheet_title") or request.args.get("sheet_title"),
        )
        return jsonify(result), 200 if result.get("ok") else 400

    @app.get("/api/accounting-workspace")
    @api_error
    def accounting_workspace():
        return jsonify(WebAccountingWorkspace().snapshot(request.args.get("as_of_date")))

    @app.get("/api/forms")
    @api_error
    def forms():
        keys = ("id", "form_code", "form_name", "scope", "file_path", "source_workbook")
        return jsonify([row_to_dict(row, keys) for row in TemplateRenderer().get_forms(request.args.get("q"))])

    @app.get("/api/settings")
    @api_error
    def settings():
        util = UtilityManager()
        return jsonify(
            {
                "settings": util.get_app_settings(),
                "backup_health": util.backup_health(),
                "linkage_checks": [
                    row_to_dict(row, ("group", "issue", "status", "count", "detail", "action"))
                    for row in util.get_linkage_checks()
                ],
                "database": BackupManager().get_database_statistics(),
                "backups": BackupManager().get_backup_list(),
            }
        )

    @app.get("/api/offline-data")
    @api_error
    def offline_data():
        return jsonify(offline_data_snapshot())

    @app.get("/api/offline-data/export.json")
    @api_error
    def offline_data_export_json():
        limit = int(request.args.get("limit_per_table") or 1000)
        payload = json.dumps(offline_data_bundle(limit), ensure_ascii=False, default=str)
        return Response(
            payload,
            mimetype="application/json; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=fastrack-offline-data.json"},
        )

    @app.get("/api/offline-schema")
    @api_error
    def offline_schema():
        return jsonify(offline_schema_snapshot())

    @app.get("/api/offline-schema/export.json")
    @api_error
    def offline_schema_export_json():
        payload = json.dumps(offline_schema_snapshot(), ensure_ascii=False, default=str)
        return Response(
            payload,
            mimetype="application/json; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=fastrack-offline-schema.json"},
        )

    @app.get("/api/offline-data/<table_name>")
    @api_error
    def offline_data_table(table_name):
        page = max(1, int(request.args.get("page") or 1))
        limit = int(request.args.get("limit") or 100)
        offset = (page - 1) * max(1, min(limit, 1000))
        data = offline_table_rows(table_name, limit, offset, request.args.get("q", ""))
        return jsonify(
            {
                "name": table_name,
                "label": OFFLINE_DATA_TABLES.get(table_name, table_name),
                "columns": data["columns"],
                "rows": data["rows"],
                "total": data["total"],
                "page": page,
                "limit": data["limit"],
                "offset": data["offset"],
                "q": data["q"],
            }
        )

    @app.get("/api/offline-data/<table_name>.csv")
    @api_error
    def offline_data_table_csv(table_name):
        data = offline_table_rows(table_name, int(request.args.get("limit") or 5000), 0, request.args.get("q", ""))
        csv_text = rows_to_csv(data["rows"], data["columns"])
        return Response(
            "\ufeff" + csv_text,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=fastrack-{table_name}.csv"},
        )

    @app.post("/api/settings")
    @api_error
    def save_settings():
        UtilityManager().save_app_settings(request.get_json(force=True))
        return jsonify({"status": "saved"})

    @app.post("/api/backups")
    @api_error
    def create_backup():
        ok, message = BackupManager().create_backup()
        if ok:
            UtilityManager().mark_backup_now()
        return jsonify({"ok": ok, "message": message})

    @app.post("/api/backups/drive")
    @api_error
    def create_drive_backup():
        data = request.get_json(silent=True) or {}
        result = WebGoogleDriveBackup().create_and_upload(data.get("folder_id") or request.args.get("folder_id"))
        if result.get("ok"):
            UtilityManager().mark_backup_now()
        return jsonify(result), 200 if result.get("ok") else 400

    @app.get("/api/finance-center")
    @api_error
    def finance_center():
        bank = BankReconciliationManager()
        finance = WebFinanceCenter()
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        fiscal_year = request.args.get("year") or date.today().year
        alerts = NotificationCenter().get_all_alerts()[:30]
        suggestions = bank.get_match_suggestions(limit=30)
        return jsonify(
            {
                "alerts": alerts,
                "alert_counts": NotificationCenter().get_badge_counts(),
                "approval_thresholds": [
                    row_to_dict(row, ("role", "max_amount", "can_final_approve", "active"))
                    for row in ApprovalThresholdManager().list_thresholds()
                ],
                "fiscal_periods": [
                    row_to_dict(row)
                    for row in FiscalPeriodLockManager().list_periods(int(fiscal_year))
                ],
                "audit_log": [
                    row_to_dict(row)
                    for row in AuditLogManager().read_report(limit=80)
                ],
                "bank": {
                    "summary": bank.get_bank_summary(),
                    "unreconciled": [row_to_dict(row) for row in bank.get_unreconciled()[:80]],
                    "matches": [row_to_dict(row) for row in bank.get_matches()[:80]],
                    "suggestions": [
                        {
                            "bank_row": row_to_dict(item.get("bank_row")),
                            "expense": row_to_dict(item.get("expense")),
                            "confidence": item.get("confidence"),
                        }
                        for item in suggestions
                    ],
                },
                "vat": finance.vat_declaration(start_date, end_date),
                "payroll": finance.payroll_summary(request.args.get("payroll_period")),
            }
        )

    @app.post("/api/approval-thresholds")
    @api_error
    def save_approval_threshold():
        data = request.get_json(force=True)
        ApprovalThresholdManager().save_threshold(
            data["role"],
            float(data.get("max_amount") or 0),
            int(data.get("can_final_approve") or 0),
            int(data.get("active", 1)),
        )
        return jsonify({"status": "saved"})

    @app.post("/api/fiscal-locks")
    @api_error
    def set_fiscal_lock():
        data = request.get_json(force=True)
        updated = FiscalPeriodLockManager().set_locked(
            data["fiscal_period"],
            bool(int(data.get("locked", 1))),
            data.get("user_id") or session.get("user_id") or 1,
        )
        return jsonify({"status": "saved", "updated": updated})

    @app.post("/api/bank/transactions")
    @api_error
    def add_bank_transaction():
        data = request.get_json(force=True)
        bank_account_id = data.get("bank_account_id") or None
        txn_id = BankReconciliationManager().add_bank_transaction(
            bank_account_id,
            data.get("transaction_date") or date.today().isoformat(),
            float(data.get("amount") or 0),
            data.get("description", ""),
            data.get("reference_no", ""),
        )
        return jsonify({"id": txn_id, "status": "created"})

    @app.post("/api/bank/auto-match")
    @api_error
    def bank_auto_match():
        matched = BankReconciliationManager().auto_match_bank_transactions()
        return jsonify({"matched": matched})

    @app.get("/api/project-accounting")
    @api_error
    def project_accounting():
        mgr = ProjectAccountingManager()
        project_id = request.args.get("project_id") or None
        return jsonify(
            {
                "dashboard": mgr.get_global_dashboard(),
                "contracts": [
                    row_to_named_dict(
                        row,
                        (
                            "id",
                            "project_code",
                            "project_name",
                            "contract_type",
                            "contract_no",
                            "partner_name",
                            "signed_date",
                            "contract_value",
                            "vat_rate",
                            "retention_rate",
                            "advance_received",
                            "advance_paid",
                            "start_date",
                            "end_date",
                            "status",
                            "notes",
                            "billed",
                        ),
                    )
                    for row in mgr.get_contracts(project_id=project_id)
                ],
                "billings": [
                    row_to_named_dict(
                        row,
                        (
                            "id",
                            "contract_no",
                            "partner_name",
                            "contract_type",
                            "billing_date",
                            "milestone_name",
                            "quantity_or_percent",
                            "amount_before_vat",
                            "vat_amount",
                            "retention_amount",
                            "net_amount",
                            "status",
                            "notes",
                            "project_code",
                            "project_name",
                        ),
                    )
                    for row in mgr.get_billings(project_id=project_id)
                ],
                "revenues": [
                    row_to_named_dict(
                        row,
                        ("id", "project_code", "project_name", "contract_no", "revenue_date", "amount", "vat_amount", "description"),
                    )
                    for row in mgr.get_revenues(project_id=project_id)
                ],
                "cost_plan_actual": [
                    row_to_named_dict(row, ("project_code", "project_name", "category", "planned", "actual"))
                    for row in mgr.get_cost_plan_vs_actual_report(project_id=project_id)
                ],
                "project_pl": mgr.get_project_pl_report(project_id=project_id),
                "contract_progress": [
                    row_to_named_dict(
                        row,
                        ("project_code", "project_name", "contract_no", "partner_name", "contract_type", "contract_value", "billed", "remaining"),
                    )
                    for row in mgr.get_contract_progress_report(project_id=project_id)
                ],
                "subcontracts": [
                    row_to_named_dict(
                        row,
                        (
                            "project_code",
                            "project_name",
                            "contract_id",
                            "contract_no",
                            "partner_name",
                            "contract_value",
                            "performed_value",
                            "remaining",
                            "active_bonds",
                            "active_warranties",
                        ),
                    )
                    for row in mgr.get_subcontract_control_report(project_id=project_id)
                ],
                "wip": mgr.get_wip_summary(project_id=project_id),
            }
        )

    @app.post("/api/project-accounting/contracts")
    @api_error
    def save_project_contract():
        data = request.get_json(force=True)
        contract_id = ProjectAccountingManager().save_contract(data)
        return jsonify({"id": contract_id, "status": "saved"})

    @app.post("/api/project-accounting/billings")
    @api_error
    def save_project_billing():
        data = request.get_json(force=True)
        create_revenue = bool(int(data.pop("create_revenue", 0) or 0))
        billing_id = ProjectAccountingManager().save_billing(data, create_revenue=create_revenue)
        return jsonify({"id": billing_id, "status": "saved"})

    @app.post("/api/project-accounting/revenues")
    @api_error
    def save_project_revenue():
        data = request.get_json(force=True)
        revenue_id = ProjectAccountingManager().save_revenue(data)
        return jsonify({"id": revenue_id, "status": "saved"})

    @app.post("/api/project-accounting/cost-plans")
    @api_error
    def save_project_cost_plan():
        data = request.get_json(force=True)
        plan_id = ProjectAccountingManager().save_cost_plan(
            data["project_id"],
            data["category_id"],
            float(data.get("planned_amount") or 0),
            data.get("notes", ""),
        )
        return jsonify({"id": plan_id, "status": "saved"})

    @app.get("/api/advances/pending")
    @api_error
    def pending_advances():
        mgr = AdvanceWorkflowManager()
        rows = mgr.get_advance_requests(status="submitted") if hasattr(mgr, "get_advance_requests") else []
        return jsonify([row_to_dict(row) for row in rows])

    return app


INDEX_HTML = r"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="manifest" href="/manifest.json">
  <title>FasTrack ERP Web</title>
  <style>
    :root{--bg:#f4f6f8;--panel:#fff;--ink:#172033;--muted:#667085;--line:#dde3ea;--brand:#1e3a5f;--accent:#0f766e;--warn:#b45309;--danger:#b42318;--good:#15803d;--soft:#eef6ff}
    body.dark{--bg:#0f172a;--panel:#111c32;--ink:#e5edf7;--muted:#9aa8bb;--line:#26354f;--brand:#60a5fa;--accent:#2dd4bf;--soft:#16233a}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,Roboto,Segoe UI,Arial,sans-serif}button,input,select,textarea{font:inherit}
    .authgate{position:fixed;inset:0;background:#10243d;display:grid;place-items:center;z-index:20;padding:18px}.loginbox{width:min(420px,100%);background:#fff;border-radius:8px;padding:22px;border:1px solid var(--line);box-shadow:0 20px 50px #0005}.loginbox h2{margin:0 0 6px}.loginbox form{display:grid;gap:12px;margin-top:18px}.loginbox .primary{width:100%}.userchip{display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:7px;padding:8px 10px;background:#fff;color:var(--muted);font-size:13px}.hidden{display:none!important}
    .shell{display:grid;grid-template-columns:248px 1fr;min-height:100vh}.side{background:#10243d;color:#fff;padding:18px 14px;position:sticky;top:0;height:100vh;overflow:auto}.brand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:18px;margin-bottom:18px}.mark{width:34px;height:34px;border-radius:8px;background:#c9a227;display:grid;place-items:center;color:#10243d}
    nav{display:grid;gap:9px}.navbtn{width:100%;border:0;background:transparent;color:#dbe7f3;text-align:left;padding:12px 13px;border-radius:7px;cursor:pointer}.navbtn.active,.navbtn:hover{background:#1e3a5f;color:#fff}.main{padding:24px;min-width:0}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}.topbar h1{font-size:24px;margin:0}.muted{color:var(--muted)}.grid{display:grid;gap:16px}.kpis{grid-template-columns:repeat(5,minmax(150px,1fr))}.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px}.kpi{position:relative;overflow:hidden}.kpi .label{font-size:13px;color:var(--muted)}.kpi .value{font-size:23px;font-weight:800;margin-top:6px}.kpi .icon{font-size:20px;width:34px;height:34px;border-radius:8px;display:grid;place-items:center;background:var(--soft);margin-bottom:8px}.trend{font-size:12px;margin-top:7px;color:var(--muted)}.trend.good{color:var(--good)}.trend.bad{color:var(--danger)}.two{grid-template-columns:1.1fr .9fr}.actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.primary{background:linear-gradient(135deg,#1e3a5f,#0f766e);color:#fff;border:0;border-radius:7px;padding:10px 13px;cursor:pointer}.primary.cta{background:#f97316;box-shadow:0 8px 20px #f9731633}.secondary{background:var(--panel);color:var(--brand);border:1px solid var(--line);border-radius:7px;padding:9px 12px;cursor:pointer}.danger{color:var(--danger)}.toolbar{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}.search{max-width:320px;width:100%;border:1px solid var(--line);border-radius:7px;padding:10px 12px}
    table{width:100%;border-collapse:collapse;font-size:14px}th,td{border-bottom:1px solid var(--line);padding:10px;text-align:left;vertical-align:top}th{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}td.num{text-align:right;font-variant-numeric:tabular-nums}.status{display:inline-block;padding:3px 8px;border-radius:999px;background:#e8eef6;color:#1e3a5f;font-size:12px}.status.low{background:#fff4e5;color:var(--warn)}.bars{display:grid;gap:10px}.barrow{display:grid;grid-template-columns:130px 1fr 96px;gap:10px;align-items:center}.bar,.progress{height:9px;background:#e8edf3;border-radius:999px;overflow:hidden}.fill{height:100%;background:var(--accent);width:0}.chart{width:100%;height:250px}.project-mini{display:grid;gap:11px}.project-line{display:grid;gap:7px}.project-line header{display:flex;justify-content:space-between;gap:12px}.syncbox{display:grid;gap:6px;background:var(--soft);border:1px solid var(--line);border-radius:8px;padding:12px}.form{display:grid;grid-template-columns:repeat(2,minmax(160px,1fr));gap:10px}.form .wide{grid-column:1/-1}label{display:grid;gap:5px;font-size:13px;color:var(--muted)}input,select,textarea{border:1px solid var(--line);border-radius:7px;padding:10px;background:var(--panel);color:var(--ink)}textarea{min-height:76px;resize:vertical}.toast{position:fixed;right:18px;bottom:18px;background:#10243d;color:#fff;border-radius:8px;padding:12px 14px;box-shadow:0 10px 30px #0003;display:none}.view{display:none}.view.active{display:grid}.empty{padding:28px;color:var(--muted);text-align:center}.mobilebar{display:none;background:#10243d;color:#fff;padding:12px 14px;align-items:center;justify-content:space-between}.mobilebar button{width:42px;height:38px;border:1px solid #365472;background:#16304f;color:#fff;border-radius:7px}
    @media(max-width:980px){.shell{grid-template-columns:1fr}.side{display:none;position:fixed;z-index:5;width:260px}.side.open{display:block}.mobilebar{display:flex}.main{padding:14px}.kpis,.two{grid-template-columns:1fr}.form{grid-template-columns:1fr}.toolbar{align-items:stretch;flex-direction:column}.search{max-width:none}.barrow{grid-template-columns:1fr}.tablewrap{overflow:auto}.topbar{align-items:flex-start;flex-direction:column}}
  </style>
</head>
<body>
  <div class="authgate" id="authGate">
    <div class="loginbox">
      <h2>Dang nhap FasTrack ERP</h2>
      <p class="muted">Dung tai khoan noi bo de vao ban web va ghi audit log.</p>
      <form id="loginForm">
        <label>Tai khoan<input name="username" autocomplete="username" required></label>
        <label>Mat khau<input name="password" type="password" autocomplete="current-password" required></label>
        <button class="primary" type="submit">Dang nhap</button>
      </form>
      <p class="muted">Mac dinh khi DB trong: admin / Admin@2026!</p>
    </div>
  </div>
  <div class="mobilebar"><strong>FasTrack ERP</strong><button id="menuBtn" title="Mở menu">☰</button></div>
  <div class="shell">
    <aside class="side" id="side">
      <div class="brand"><span class="mark">FT</span><span>FasTrack ERP</span></div>
      <nav>
        <button class="navbtn active" data-view="dashboard">Tổng quan</button>
        <button class="navbtn" data-view="offlineData">Dữ liệu offline</button>
        <button class="navbtn" data-view="expenses">Chi phí</button>
        <button class="navbtn" data-view="inventory">Vật tư kho</button>
        <button class="navbtn" data-view="projects">Dự án</button>
        <button class="navbtn" data-view="projectAccounting">Kế toán công trình</button>
        <button class="navbtn" data-view="construction">Công trường</button>
        <button class="navbtn" data-view="documents">Chứng từ</button>
        <button class="navbtn" data-view="forms">Biểu mẫu</button>
        <button class="navbtn" data-view="reports">Báo cáo</button>
        <button class="navbtn" data-view="accounting">Sổ sách</button>
        <button class="navbtn" data-view="finance">Kiểm soát & tài chính</button>
        <button class="navbtn" data-view="security">Bảo mật</button>
        <button class="navbtn" data-view="settings">Cài đặt</button>
        <button class="navbtn" data-view="deploy">Tên miền</button>
      </nav>
    </aside>
    <main class="main">
      <div class="topbar">
        <div><h1 id="pageTitle">Tổng quan</h1><div class="muted" id="subtitle">Bản web dùng chung dữ liệu với ứng dụng desktop.</div></div>
        <div class="actions"><span class="userchip" id="userChip">Chưa đăng nhập</span><button class="secondary" id="themeBtn">Tối</button><button class="secondary" id="logoutBtn">Đăng xuất</button><button class="secondary" id="refreshBtn">Tải lại</button><button class="primary cta" data-view-jump="expenses">Thêm chi phí</button></div>
      </div>

      <section class="view active" id="dashboard">
        <div class="grid kpis">
          <div class="card kpi"><div class="icon">Σ</div><div class="label">Tổng chi phí</div><div class="value" id="kTotal">0</div><div class="trend" id="kTotalTrend">Lũy kế toàn hệ thống</div></div>
          <div class="card kpi"><div class="icon">↗</div><div class="label">Chi phí tháng này</div><div class="value" id="kMonth">0</div><div class="trend" id="kMonthTrend">So với tháng trước</div></div>
          <div class="card kpi" data-view-jump="projects"><div class="icon">▦</div><div class="label">Dự án active</div><div class="value" id="kProjects">0</div><div class="trend">Click để xem danh sách</div></div>
          <div class="card kpi"><div class="icon">□</div><div class="label">Chứng từ</div><div class="value" id="kDocs">0</div><div class="trend">Hồ sơ kế toán</div></div>
          <div class="card kpi"><div class="icon">◇</div><div class="label">Giá trị tồn kho</div><div class="value" id="kStock">0</div><div class="trend">Theo đơn giá hiện tại</div></div>
        </div>
        <div class="grid two">
          <div class="card"><h3>Cơ cấu chi phí</h3><canvas class="chart" id="categoryPie"></canvas><div class="bars" id="categoryBars"></div></div>
          <div class="card"><h3>Chi phí theo dự án</h3><canvas class="chart" id="projectChart"></canvas></div>
        </div>
        <div class="grid two">
          <div class="card"><div class="toolbar"><h3>Dự án đang chạy</h3><button class="secondary" type="button" data-view-jump="projects">Mở dự án</button></div><div class="project-mini" id="activeProjectRows"></div></div>
          <div class="card"><h3>Đồng bộ Desktop/Web</h3><div class="syncbox" id="syncBox"></div><h3>Cảnh báo tồn kho</h3><div class="tablewrap"><table><thead><tr><th>Mã</th><th>Vật tư</th><th>Tồn</th><th>Min</th></tr></thead><tbody id="lowStockRows"></tbody></table></div></div>
        </div>
      </section>

      <section class="view" id="offlineData">
        <div class="grid kpis">
          <div class="card kpi"><div class="label">Nhóm dữ liệu</div><div class="value" id="odTables">0</div></div>
          <div class="card kpi"><div class="label">Nhóm có dữ liệu</div><div class="value" id="odActiveTables">0</div></div>
          <div class="card kpi"><div class="label">Tổng dòng dữ liệu</div><div class="value" id="odRecords">0</div></div>
          <div class="card kpi"><div class="label">Bảng đang xem</div><div class="value" id="odCurrent">-</div></div>
          <div class="card kpi"><div class="label">Dòng preview</div><div class="value" id="odPreviewCount">0</div></div>
        </div>
        <div class="grid two">
          <div class="card">
            <div class="toolbar"><h3>Kho dữ liệu đã đưa lên web</h3><div class="actions"><input class="search" id="offlineSearch" placeholder="Tìm nhóm dữ liệu"><button class="secondary" type="button" id="offlineJsonBtn">JSON đầy đủ</button></div></div>
            <div class="tablewrap"><table><thead><tr><th>Nhóm</th><th>Bảng</th><th>Số dòng</th><th>Xem</th></tr></thead><tbody id="offlineTableRows"></tbody></table></div>
          </div>
          <div class="card">
            <div class="toolbar"><h3 id="offlinePreviewTitle">Preview dữ liệu</h3><div class="actions"><input class="search" id="offlineTableSearch" placeholder="Tìm trong bảng"><button class="secondary" type="button" id="offlinePrevBtn">Trước</button><button class="secondary" type="button" id="offlineNextBtn">Sau</button><button class="secondary" type="button" id="offlineCsvBtn">CSV</button><button class="secondary" type="button" id="offlineReloadBtn">Tải lại</button></div></div>
            <div class="tablewrap"><table id="offlinePreviewTable"><thead id="offlinePreviewHead"></thead><tbody id="offlinePreviewRows"></tbody></table></div>
          </div>
        </div>
        <div class="grid two">
          <div class="card">
            <div class="toolbar"><h3>Cấu trúc database offline</h3><div class="actions"><input class="search" id="schemaSearch" placeholder="Tìm bảng/cột"><button class="secondary" type="button" id="schemaJsonBtn">Schema JSON</button></div></div>
            <div class="tablewrap"><table><thead><tr><th>Bảng</th><th>Cột</th><th>Dòng</th><th>Index</th><th>FK</th><th>Web</th></tr></thead><tbody id="schemaRows"></tbody></table></div>
          </div>
          <div class="card">
            <h3>Quan hệ dữ liệu</h3>
            <div class="tablewrap"><table><thead><tr><th>Từ bảng</th><th>Cột</th><th>Đến bảng</th><th>Cột</th></tr></thead><tbody id="relationRows"></tbody></table></div>
          </div>
        </div>
      </section>

      <section class="view" id="expenses">
        <div class="card">
          <h3>Nhập chi phí nhanh</h3>
          <form class="form" id="expenseForm">
            <label>Ngày chi<input name="expense_date" type="date"></label>
            <label>Dự án<select name="project_id" id="expenseProject"></select></label>
            <label>Danh mục<select name="category_id" id="expenseCategory" required></select></label>
            <label>Số tiền<input name="amount" type="number" min="0" step="1000" required></label>
            <label>Người chi<input name="paid_by" placeholder="Tên người chi"></label>
            <label>Phương thức<select name="payment_method"><option>Tiền mặt</option><option>Chuyển khoản</option><option>Thẻ</option></select></label>
            <label class="wide">Nội dung<textarea name="description" placeholder="Nội dung chi phí"></textarea></label>
            <div class="wide actions"><button class="primary" type="submit">Lưu chi phí</button><button class="secondary" type="reset">Xóa form</button></div>
          </form>
        </div>
        <div class="card">
          <div class="toolbar"><h3>Danh sách chi phí</h3><input class="search" id="expenseSearch" placeholder="Tìm chi phí"></div>
          <div class="tablewrap"><table><thead><tr><th>Ngày</th><th>Dự án</th><th>Danh mục</th><th>Nội dung</th><th>Số tiền</th><th>TT</th></tr></thead><tbody id="expenseRows"></tbody></table></div>
        </div>
      </section>

      <section class="view" id="inventory">
        <div class="grid kpis">
          <div class="card kpi"><div class="label">Giá trị tồn kho</div><div class="value" id="invStockValue">0</div></div>
          <div class="card kpi"><div class="label">Vật tư</div><div class="value" id="invMaterialCount">0</div></div>
          <div class="card kpi"><div class="label">Cảnh báo thông minh</div><div class="value" id="invSmartAlerts">0</div></div>
          <div class="card kpi"><div class="label">Định mức</div><div class="value" id="invStandardCount">0</div></div>
        </div>
        <div class="grid two">
          <div class="card">
            <h3>Nhập / xuất kho công trình</h3>
            <form class="form" id="inventoryTransactionForm">
              <label>Vật tư<select name="material_id" id="inventoryMaterialSelect" required></select></label>
              <label>Loại<select name="transaction_type"><option value="export">Xuất cho công trình</option><option value="import">Nhập kho</option></select></label>
              <label>Số lượng<input name="quantity" type="number" min="0" step="0.01" required></label>
              <label>Đơn giá nhập<input name="unit_price" type="number" min="0" step="1000" placeholder="Chỉ dùng khi nhập"></label>
              <label>Dự án<select name="project_id" id="inventoryProjectSelect"></select></label>
              <label>Hạng mục<select name="work_item_id" id="inventoryWorkItemSelect"></select></label>
              <label class="wide">Ghi chú<textarea name="notes" placeholder="VD: Phiếu giao hàng, ký nhận công trường"></textarea></label>
              <div class="wide actions"><button class="primary" type="submit">Ghi phiếu kho</button></div>
            </form>
            <p class="muted">Xuất kho dùng giá bình quân gia quyền và tự động tạo bút toán 621/152.</p>
          </div>
          <div class="card">
            <h3>Định mức vật tư theo hạng mục</h3>
            <form class="form" id="materialStandardForm">
              <label>Hạng mục<select name="work_item_id" id="standardWorkItemSelect"></select></label>
              <label>Vật tư<select name="material_id" id="standardMaterialSelect" required></select></label>
              <label>Cơ sở<input name="basis_unit" value="m2"></label>
              <label>Định mức / đơn vị<input name="standard_qty_per_unit" type="number" min="0" step="0.0001" required></label>
              <label>Sai lệch %<input name="tolerance_percent" type="number" min="0" step="1" value="15"></label>
              <label class="wide">Ghi chú<textarea name="notes"></textarea></label>
              <div class="wide actions"><button class="primary" type="submit">Lưu định mức</button></div>
            </form>
          </div>
        </div>
        <div class="card">
          <div class="toolbar"><h3>Cảnh báo vật tư theo tiến độ</h3><button class="secondary" type="button" id="reloadInventoryWorkspaceBtn">Tải lại</button></div>
          <div class="tablewrap"><table><thead><tr><th>Ưu tiên</th><th>Dự án / hạng mục</th><th>Vật tư</th><th>Cần dùng</th><th>Đang có</th><th>Thiếu</th><th>Gợi ý</th></tr></thead><tbody id="smartStockRows"></tbody></table></div>
        </div>
        <div class="card">
          <div class="toolbar"><h3>Tồn kho vật tư</h3><input class="search" id="inventorySearch" placeholder="Tìm vật tư"></div>
          <div class="tablewrap"><table><thead><tr><th>Mã</th><th>Tên vật tư</th><th>Nhóm</th><th>Tồn</th><th>Giá BQ</th><th>Định mức</th><th>Trạng thái</th></tr></thead><tbody id="inventoryRows"></tbody></table></div>
        </div>
        <div class="grid two">
          <div class="card">
            <h3>Phương pháp tính giá xuất kho</h3>
            <div class="tablewrap"><table><thead><tr><th>Mã</th><th>Tên phương pháp</th><th>Trạng thái</th></tr></thead><tbody id="valuationRows"></tbody></table></div>
          </div>
          <div class="card">
            <h3>Đơn mua hàng đang mở</h3>
            <div class="tablewrap"><table><thead><tr><th>Số PO</th><th>Nhà cung cấp</th><th>Ngày đặt</th><th>Giá trị</th><th>TT</th></tr></thead><tbody id="poRows"></tbody></table></div>
          </div>
        </div>
        <div class="card">
          <h3>Giao dịch kho gần đây</h3>
          <div class="tablewrap"><table><thead><tr><th>Ngày</th><th>Mã</th><th>Vật tư</th><th>Loại</th><th>SL</th><th>Dự án</th><th>Ghi chú</th></tr></thead><tbody id="historyRows"></tbody></table></div>
        </div>
      </section>

      <section class="view" id="projects">
        <div class="card">
          <h3>Thêm hoặc cập nhật dự án</h3>
          <form class="form" id="projectForm">
            <label>Mã dự án<input name="code" required></label>
            <label>Tên dự án<input name="name" required></label>
            <label>Địa điểm<input name="location"></label>
            <label>Ngân sách<input name="budget" type="number" min="0" step="1000000"></label>
            <label>Trạng thái<select name="status"><option value="active">active</option><option value="completed">completed</option><option value="paused">paused</option></select></label>
            <div class="wide actions"><button class="primary" type="submit">Lưu dự án</button></div>
          </form>
        </div>
        <div class="card"><h3>Danh sách dự án</h3><div class="tablewrap"><table><thead><tr><th>Mã</th><th>Tên dự án</th><th>Địa điểm</th><th>Ngân sách</th><th>TT</th></tr></thead><tbody id="projectRows"></tbody></table></div></div>
      </section>

      <section class="view" id="projectAccounting">
        <div class="grid kpis">
          <div class="card kpi"><div class="label">Dự án active</div><div class="value" id="paActive">0</div></div>
          <div class="card kpi"><div class="label">Dự toán</div><div class="value" id="paPlanned">0</div></div>
          <div class="card kpi"><div class="label">Chi phí thực tế</div><div class="value" id="paSpent">0</div></div>
          <div class="card kpi"><div class="label">Doanh thu</div><div class="value" id="paRevenue">0</div></div>
          <div class="card kpi"><div class="label">Lãi/lỗ</div><div class="value" id="paProfit">0</div></div>
        </div>
        <div class="grid two">
          <div class="card">
            <h3>Hợp đồng công trình</h3>
            <form class="form" id="contractForm">
              <label>Dự án<select name="project_id" id="contractProject"></select></label>
              <label>Loại<select name="contract_type"><option value="customer">Chủ đầu tư</option><option value="subcontract">Thầu phụ</option><option value="supplier">Nhà cung cấp</option></select></label>
              <label>Số hợp đồng<input name="contract_no" required></label>
              <label>Đối tác<input name="partner_name" required></label>
              <label>Ngày ký<input name="signed_date" type="date"></label>
              <label>Giá trị<input name="contract_value" type="number" min="0" step="1000000"></label>
              <label>VAT %<input name="vat_rate" type="number" min="0" step="1" value="10"></label>
              <label>Giữ lại %<input name="retention_rate" type="number" min="0" step="1" value="5"></label>
              <label>Trạng thái<select name="status"><option value="active">active</option><option value="completed">completed</option><option value="paused">paused</option></select></label>
              <label class="wide">Ghi chú<textarea name="notes"></textarea></label>
              <div class="wide actions"><button class="primary" type="submit">Lưu hợp đồng</button></div>
            </form>
          </div>
          <div class="card">
            <h3>Dự toán chi phí</h3>
            <form class="form" id="costPlanForm">
              <label>Dự án<select name="project_id" id="costPlanProject"></select></label>
              <label>Danh mục<select name="category_id" id="costPlanCategory"></select></label>
              <label>Ngân sách<input name="planned_amount" type="number" min="0" step="1000000"></label>
              <label class="wide">Ghi chú<textarea name="notes"></textarea></label>
              <div class="wide actions"><button class="primary" type="submit">Lưu dự toán</button></div>
            </form>
          </div>
        </div>
        <div class="grid two">
          <div class="card">
            <h3>Nghiệm thu / billing</h3>
            <form class="form" id="billingForm">
              <label>Hợp đồng<select name="contract_id" id="billingContract"></select></label>
              <label>Ngày nghiệm thu<input name="billing_date" type="date"></label>
              <label>Mốc nghiệm thu<input name="milestone_name"></label>
              <label>Giá trị trước VAT<input name="amount_before_vat" type="number" min="0" step="1000000"></label>
              <label>VAT %<input name="vat_rate" type="number" min="0" step="1" value="10"></label>
              <label>Giữ lại %<input name="retention_rate" type="number" min="0" step="1" value="5"></label>
              <label>Trạng thái<select name="status"><option value="draft">draft</option><option value="approved">approved</option><option value="paid">paid</option></select></label>
              <label>Tạo doanh thu<select name="create_revenue"><option value="0">Không</option><option value="1">Có</option></select></label>
              <div class="wide actions"><button class="primary" type="submit">Lưu nghiệm thu</button></div>
            </form>
          </div>
          <div class="card">
            <h3>Ghi nhận doanh thu</h3>
            <form class="form" id="revenueForm">
              <label>Dự án<select name="project_id" id="revenueProject"></select></label>
              <label>Hợp đồng<select name="contract_id" id="revenueContract"></select></label>
              <label>Ngày doanh thu<input name="revenue_date" type="date"></label>
              <label>Doanh thu<input name="amount" type="number" min="0" step="1000000"></label>
              <label>VAT<input name="vat_amount" type="number" min="0" step="100000"></label>
              <label class="wide">Diễn giải<textarea name="description"></textarea></label>
              <div class="wide actions"><button class="primary" type="submit">Lưu doanh thu</button></div>
            </form>
          </div>
        </div>
        <div class="card">
          <div class="toolbar"><h3>Danh sách hợp đồng</h3><input class="search" id="contractSearch" placeholder="Tìm hợp đồng"></div>
          <div class="tablewrap"><table><thead><tr><th>Dự án</th><th>Loại</th><th>Số HĐ</th><th>Đối tác</th><th>Giá trị</th><th>Đã nghiệm thu</th><th>TT</th></tr></thead><tbody id="contractRows"></tbody></table></div>
        </div>
        <div class="grid two">
          <div class="card"><h3>Nghiệm thu gần đây</h3><div class="tablewrap"><table><thead><tr><th>Ngày</th><th>HĐ</th><th>Mốc</th><th>Net</th><th>TT</th></tr></thead><tbody id="billingRows"></tbody></table></div></div>
          <div class="card"><h3>Doanh thu dự án</h3><div class="tablewrap"><table><thead><tr><th>Ngày</th><th>Dự án</th><th>HĐ</th><th>Doanh thu</th><th>VAT</th></tr></thead><tbody id="revenueRows"></tbody></table></div></div>
        </div>
        <div class="grid two">
          <div class="card"><h3>Dự toán vs thực tế</h3><div class="tablewrap"><table><thead><tr><th>Dự án</th><th>Danh mục</th><th>Dự toán</th><th>Thực tế</th><th>Chênh lệch</th></tr></thead><tbody id="costPlanRows"></tbody></table></div></div>
          <div class="card"><h3>P/L công trình</h3><div class="tablewrap"><table><thead><tr><th>Dự án</th><th>Doanh thu</th><th>Chi phí</th><th>Lãi/lỗ</th></tr></thead><tbody id="projectPlRows"></tbody></table></div></div>
        </div>
      </section>

      <section class="view" id="construction">
        <div class="card">
          <h3>Hạng mục công trường</h3>
          <div class="tablewrap"><table><thead><tr><th>Dự án</th><th>Mã HM</th><th>Hạng mục</th><th>KL KH</th><th>Hoàn thành</th><th>Chi phí thực tế</th><th>TT</th></tr></thead><tbody id="workRows"></tbody></table></div>
        </div>
        <div class="card">
          <h3>Nhật ký công trường</h3>
          <form class="form" id="diaryForm">
            <label>Ngày<input name="diary_date" type="date"></label>
            <label>Dự án<select name="project_id" id="diaryProject"></select></label>
            <label>Thời tiết<input name="weather"></label>
            <label>Nhân lực<input name="manpower"></label>
            <label>Thiết bị<input name="equipment"></label>
            <label>Người báo cáo<input name="reporter"></label>
            <label class="wide">Nội dung công việc<textarea name="work_content"></textarea></label>
            <label class="wide">Vấn đề phát sinh<textarea name="issues"></textarea></label>
            <div class="wide actions"><button class="primary" type="submit">Lưu nhật ký</button></div>
          </form>
          <div class="tablewrap"><table><thead><tr><th>Ngày</th><th>Dự án</th><th>Thời tiết</th><th>Nội dung</th><th>Người báo cáo</th></tr></thead><tbody id="diaryRows"></tbody></table></div>
        </div>
      </section>

      <section class="view" id="documents">
        <div class="card">
          <h3>Thêm hóa đơn/chứng từ</h3>
          <form class="form" id="documentForm">
            <label>Loại chứng từ<input name="doc_type" value="Hóa đơn"></label>
            <label>Số chứng từ<input name="doc_number"></label>
            <label>Ngày chứng từ<input name="doc_date" type="date"></label>
            <label>Nhà cung cấp/người nhận<input name="supplier_name"></label>
            <label>Số tiền<input name="amount" type="number" min="0" step="1000"></label>
            <label>VAT %<input name="vat_rate" type="number" min="0" max="100" step="1" value="10"></label>
            <label>Dự án<select name="project_id" id="documentProject"></select></label>
            <label>Danh mục<select name="category_id" id="documentCategory"></select></label>
            <label>Liên kết chi phí ID<input name="expense_id" type="number" min="1"></label>
            <label>Đường dẫn file<input name="file_path" placeholder="attachments/... hoặc scan PDF"></label>
            <label class="wide">Diễn giải<textarea name="description"></textarea></label>
            <div class="wide actions"><button class="primary" type="submit">Lưu chứng từ</button></div>
          </form>
        </div>
        <div class="card">
          <div class="toolbar"><h3>Danh sách chứng từ</h3><input class="search" id="documentSearch" placeholder="Tìm chứng từ"></div>
          <div class="tablewrap"><table><thead><tr><th>Ngày</th><th>Loại</th><th>Số</th><th>Nhà cung cấp</th><th>Số tiền</th><th>Dự án</th><th>TT</th></tr></thead><tbody id="documentRows"></tbody></table></div>
        </div>
      </section>

      <section class="view" id="forms">
        <div class="card">
          <div class="toolbar"><h3>Thư viện biểu mẫu</h3><input class="search" id="formSearch" placeholder="Tìm biểu mẫu"></div>
          <div class="tablewrap"><table><thead><tr><th>Mã</th><th>Tên biểu mẫu</th><th>Phạm vi</th><th>File</th></tr></thead><tbody id="formRows"></tbody></table></div>
        </div>
      </section>

      <section class="view" id="reports">
        <div class="card">
          <div class="toolbar"><h3>Xuất báo cáo tháng</h3><div class="actions"><input class="search" id="reportMonth" type="month"><button class="secondary" type="button" id="csvExportBtn">CSV</button><button class="primary" type="button" id="sheetsExportBtn">Google Sheets</button></div></div>
          <div class="tablewrap"><table><thead><tr><th>Chỉ tiêu</th><th>Giá trị</th></tr></thead><tbody id="monthlyExportRows"></tbody></table></div>
        </div>
        <div class="grid two">
          <div class="card"><h3>Chi phí theo tháng</h3><div class="bars" id="monthlyBars"></div></div>
          <div class="card"><h3>Chi phí theo dự án</h3><div class="bars" id="projectBars"></div></div>
        </div>
        <div class="card">
          <h3>Tồn kho theo giá trị</h3>
          <div class="tablewrap"><table><thead><tr><th>Vật tư</th><th>Số lượng</th><th>Đơn giá</th><th>Giá trị</th></tr></thead><tbody id="stockReportRows"></tbody></table></div>
        </div>
      </section>

      <section class="view" id="accounting">
        <div class="grid kpis">
          <div class="card kpi"><div class="label">Tài khoản</div><div class="value" id="aAccounts">0</div></div>
          <div class="card kpi"><div class="label">Bút toán gần đây</div><div class="value" id="aJournals">0</div></div>
          <div class="card kpi"><div class="label">Phát sinh nợ</div><div class="value" id="aDebit">0</div></div>
          <div class="card kpi"><div class="label">Phát sinh có</div><div class="value" id="aCredit">0</div></div>
          <div class="card kpi"><div class="label">Công nợ mở</div><div class="value" id="aOpenDebt">0</div></div>
        </div>
        <div class="grid two">
          <div class="card">
            <div class="toolbar"><h3>Hệ thống tài khoản</h3><input class="search" id="accountSearch" placeholder="Tìm tài khoản"></div>
            <div class="tablewrap"><table><thead><tr><th>TK</th><th>Tên tài khoản</th><th>Loại</th><th>Nợ</th><th>Có</th><th>Số dư</th></tr></thead><tbody id="accountRows"></tbody></table></div>
          </div>
          <div class="card">
            <h3>Nhóm tài khoản</h3>
            <div class="tablewrap"><table><thead><tr><th>Loại</th><th>Tổng TK</th><th>Đang dùng</th></tr></thead><tbody id="accountSummaryRows"></tbody></table></div>
          </div>
        </div>
        <div class="grid two">
          <div class="card">
            <h3>Cân đối phát sinh</h3>
            <div class="tablewrap"><table><thead><tr><th>TK</th><th>Tên tài khoản</th><th>Nợ</th><th>Có</th><th>Số dư</th></tr></thead><tbody id="trialRows"></tbody></table></div>
          </div>
          <div class="card">
            <h3>Bảng cân đối kế toán</h3>
            <div class="tablewrap"><table><thead><tr><th>Nhóm</th><th>TK</th><th>Tên tài khoản</th><th>Số dư</th></tr></thead><tbody id="balanceRows"></tbody></table></div>
          </div>
        </div>
        <div class="grid two">
          <div class="card">
            <div class="toolbar"><h3>Nhật ký bút toán</h3><input class="search" id="journalSearch" placeholder="Tìm bút toán"></div>
            <div class="tablewrap"><table><thead><tr><th>Ngày</th><th>Số CT</th><th>Diễn giải</th><th>Nợ/Có</th><th>Số tiền</th></tr></thead><tbody id="journalRows"></tbody></table></div>
          </div>
          <div class="card">
            <h3>Công nợ phải thu/phải trả</h3>
            <div class="tablewrap"><table><thead><tr><th>Đối tác</th><th>Dự án</th><th>Hạn</th><th>Số tiền</th><th>Còn lại</th><th>TT</th></tr></thead><tbody id="arApRows"></tbody></table></div>
          </div>
        </div>
        <div class="grid two">
          <div class="card"><h3>Tập hợp chi phí công trình</h3><div class="tablewrap"><table><thead><tr><th>Dự án</th><th>Danh mục</th><th>Số dòng</th><th>Số tiền</th></tr></thead><tbody id="costCollectRows"></tbody></table></div></div>
          <div class="card"><h3>Trạng thái kỳ kế toán</h3><div class="tablewrap"><table><thead><tr><th>Năm</th><th>Số kỳ</th><th>Đã khóa</th><th>Đã đóng</th></tr></thead><tbody id="fiscalStatusRows"></tbody></table></div></div>
        </div>
      </section>

      <section class="view" id="finance">
        <div class="grid kpis">
          <div class="card kpi"><div class="label">Cảnh báo</div><div class="value" id="fAlerts">0</div></div>
          <div class="card kpi"><div class="label">Chưa đối soát</div><div class="value" id="fUnreconciled">0</div></div>
          <div class="card kpi"><div class="label">VAT đầu ra</div><div class="value" id="fOutputVat">0</div></div>
          <div class="card kpi"><div class="label">VAT phải nộp</div><div class="value" id="fVatPayable">0</div></div>
          <div class="card kpi"><div class="label">Lương net</div><div class="value" id="fPayrollNet">0</div></div>
        </div>
        <div class="grid two">
          <div class="card">
            <div class="toolbar"><h3>Cảnh báo nghiệp vụ</h3><input class="search" id="financeSearch" placeholder="Tìm cảnh báo"></div>
            <div class="tablewrap"><table><thead><tr><th>Nguồn</th><th>Mức</th><th>Nội dung</th><th>Hạn</th></tr></thead><tbody id="alertRows"></tbody></table></div>
          </div>
          <div class="card">
            <h3>Hạn mức phê duyệt</h3>
            <form class="form" id="thresholdForm">
              <label>Vai trò<input name="role" required></label>
              <label>Hạn mức<input name="max_amount" type="number" min="0" step="100000" required></label>
              <label>Duyệt cuối<select name="can_final_approve"><option value="0">Không</option><option value="1">Có</option></select></label>
              <label>Trạng thái<select name="active"><option value="1">active</option><option value="0">inactive</option></select></label>
              <div class="wide actions"><button class="primary" type="submit">Lưu hạn mức</button></div>
            </form>
            <div class="tablewrap"><table><thead><tr><th>Vai trò</th><th>Hạn mức</th><th>Duyệt cuối</th><th>TT</th></tr></thead><tbody id="thresholdRows"></tbody></table></div>
          </div>
        </div>
        <div class="grid two">
          <div class="card">
            <h3>Khóa kỳ kế toán</h3>
            <div class="tablewrap"><table><thead><tr><th>Kỳ</th><th>Từ ngày</th><th>Đến ngày</th><th>TT</th><th>Thao tác</th></tr></thead><tbody id="periodRows"></tbody></table></div>
          </div>
          <div class="card">
            <h3>Đối soát ngân hàng</h3>
            <form class="form" id="bankForm">
              <label>Ngày giao dịch<input name="transaction_date" type="date"></label>
              <label>Số tiền<input name="amount" type="number" step="1000" required></label>
              <label>Số tham chiếu<input name="reference_no"></label>
              <label>Tài khoản ID<input name="bank_account_id" type="number" min="1"></label>
              <label class="wide">Diễn giải<textarea name="description"></textarea></label>
              <div class="wide actions"><button class="primary" type="submit">Thêm giao dịch</button><button class="secondary" type="button" id="autoMatchBtn">Tự khớp</button></div>
            </form>
            <div class="tablewrap"><table><thead><tr><th>Ngày</th><th>Diễn giải</th><th>Số tiền</th><th>TT</th></tr></thead><tbody id="bankRows"></tbody></table></div>
          </div>
        </div>
        <div class="grid two">
          <div class="card">
            <h3>Tờ khai VAT</h3>
            <div class="tablewrap"><table><thead><tr><th>Chỉ tiêu</th><th>Giá trị</th></tr></thead><tbody id="vatRows"></tbody></table></div>
          </div>
          <div class="card">
            <h3>Audit log</h3>
            <div class="tablewrap"><table><thead><tr><th>Thời điểm</th><th>Hành động</th><th>Bảng</th><th>Chi tiết</th></tr></thead><tbody id="auditRows"></tbody></table></div>
          </div>
        </div>
      </section>

      <section class="view" id="security">
        <div class="grid two">
          <div class="card">
            <h3>Người dùng</h3>
            <form class="form" id="userForm">
              <label>Tài khoản<input name="username" required></label>
              <label>Họ tên<input name="full_name"></label>
              <label>Email<input name="email" type="email"></label>
              <label>Vai trò<select name="role"><option value="admin">admin</option><option value="accountant">accountant</option><option value="manager">manager</option><option value="employee">employee</option></select></label>
              <label class="wide">Mật khẩu tạm<input name="password" type="password" minlength="10" placeholder="Ví dụ: User@2026!"></label>
              <div class="wide actions"><button class="primary" type="submit">Tạo người dùng</button></div>
            </form>
          </div>
          <div class="card">
            <h3>Đổi mật khẩu của tôi</h3>
            <form class="form" id="passwordForm">
              <label>Mật khẩu hiện tại<input name="old_password" type="password" required></label>
              <label>Mật khẩu mới<input name="new_password" type="password" minlength="10" required></label>
              <div class="wide actions"><button class="primary" type="submit">Đổi mật khẩu</button></div>
            </form>
            <p class="muted">Mật khẩu mới cần tối thiểu 10 ký tự, có chữ hoa, chữ thường, số và ký tự đặc biệt.</p>
          </div>
        </div>
        <div class="card">
          <div class="toolbar"><h3>Danh sách người dùng</h3><button class="secondary" type="button" id="reloadUsersBtn">Tải lại</button></div>
          <div class="tablewrap"><table><thead><tr><th>Tài khoản</th><th>Họ tên</th><th>Email</th><th>Vai trò</th><th>Trạng thái</th><th>Tạo lúc</th></tr></thead><tbody id="userRows"></tbody></table></div>
        </div>
      </section>

      <section class="view" id="settings">
        <div class="card">
          <h3>Thông tin công ty</h3>
          <form class="form" id="settingsForm">
            <label>Tên công ty<input name="company_name"></label>
            <label>Mã số thuế<input name="company_tax_code"></label>
            <label>Người đại diện<input name="company_representative"></label>
            <label>Tên viết tắt<input name="company_short_name"></label>
            <div class="wide actions"><button class="primary" type="submit">Lưu cài đặt</button><button class="secondary" type="button" id="backupBtn">Sao lưu ngay</button><button class="secondary" type="button" id="driveBackupBtn">Drive backup</button></div>
          </form>
          <p class="muted" id="backupHealth"></p>
        </div>
        <div class="card">
          <h3>Google Drive backup</h3>
          <form class="form" id="driveBackupForm">
            <label class="wide">Drive folder ID<input name="folder_id" placeholder="Lấy trong URL thư mục Google Drive hoặc cấu hình GOOGLE_DRIVE_BACKUP_FOLDER_ID"></label>
          </form>
          <p class="muted" id="driveBackupStatus">Chưa chạy sao lưu Drive.</p>
        </div>
        <div class="grid two">
          <div class="card"><h3>Kiểm tra liên kết dữ liệu</h3><div class="tablewrap"><table><thead><tr><th>Nhóm</th><th>Vấn đề</th><th>TT</th><th>Số dòng</th></tr></thead><tbody id="linkageRows"></tbody></table></div></div>
          <div class="card"><h3>Thống kê database</h3><div class="tablewrap"><table><thead><tr><th>Bảng</th><th>Số dòng</th></tr></thead><tbody id="databaseRows"></tbody></table></div></div>
        </div>
        <div class="card"><h3>Bản sao lưu</h3><div class="tablewrap"><table><thead><tr><th>File</th><th>Dung lượng</th><th>Ngày</th></tr></thead><tbody id="backupRows"></tbody></table></div></div>
      </section>

      <section class="view" id="deploy">
        <div class="card">
          <h3>Đưa bản web lên Internet</h3>
          <p>Ứng dụng này là Flask + SQLite nên muốn dùng ngoài máy local cần một nơi chạy Python liên tục. Hosting tĩnh như GitHub Pages hoặc Cloudflare Pages chỉ phù hợp nếu tách frontend riêng, không chạy trực tiếp backend Flask này.</p>
          <div class="tablewrap"><table><thead><tr><th>Lựa chọn</th><th>Chi phí</th><th>Phù hợp</th></tr></thead><tbody>
            <tr><td>Cloudflare Tunnel + máy công ty</td><td>Miễn phí</td><td>Dùng thử hoặc nội bộ, máy phải luôn bật</td></tr>
            <tr><td>Render/Railway/Fly.io free hoặc trial</td><td>Có gói miễn phí/trial tùy thời điểm</td><td>Demo web Flask, cần theo dõi giới hạn</td></tr>
            <tr><td>VPS giá rẻ + domain riêng</td><td>Trả phí</td><td>Ổn định hơn cho dữ liệu kế toán thật</td></tr>
          </tbody></table></div>
        </div>
        <div class="card">
          <h3>Tên miền miễn phí</h3>
          <p>Có thể dùng subdomain miễn phí như <strong>ten-du-an.pages.dev</strong>, <strong>ten-user.github.io</strong>, hoặc URL tunnel. Tên miền riêng dạng <strong>.com/.vn</strong> miễn phí lâu dài hiện không nên tin cậy; nên mua domain rẻ rồi trỏ DNS nếu đưa vào vận hành thật.</p>
        </div>
      </section>
    </main>
  </div>
  <div class="toast" id="toast"></div>

  <script>
    const state={auth:null,users:[],offlineData:null,offlineSchema:null,offlineTable:null,dashboard:null,expenses:[],inventory:[],history:[],inventoryWorkspace:null,projects:[],categories:[],projectAccounting:null,workItems:[],diaries:[],documents:[],forms:[],reports:null,accounting:null,finance:null,settings:null};
    const money=v=>new Intl.NumberFormat('vi-VN',{maximumFractionDigits:0}).format(Number(v||0));
    const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    const toast=t=>{const el=document.getElementById('toast');el.textContent=t;el.style.display='block';setTimeout(()=>el.style.display='none',2800)};
    const palette=['#1e3a5f','#0f766e','#f97316','#7c3aed','#dc2626','#0891b2','#65a30d','#b45309'];
    function pct(v){const n=Number(v||0);return `${n>0?'+':''}${n.toFixed(1)}%`}
    function drawPie(canvas,rows,labelKey,valueKey){const ctx=canvas.getContext('2d'),w=canvas.clientWidth,h=canvas.clientHeight,dpr=window.devicePixelRatio||1;canvas.width=w*dpr;canvas.height=h*dpr;ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);const total=rows.reduce((s,r)=>s+Number(r[valueKey]||0),0);let start=-Math.PI/2;const cx=w*.32,cy=h*.48,r=Math.min(w,h)*.32;if(!total){ctx.fillStyle=getComputedStyle(document.body).getPropertyValue('--muted');ctx.fillText('Chưa có dữ liệu',20,30);return}rows.forEach((row,i)=>{const val=Number(row[valueKey]||0),end=start+Math.PI*2*val/total;ctx.beginPath();ctx.moveTo(cx,cy);ctx.arc(cx,cy,r,start,end);ctx.closePath();ctx.fillStyle=palette[i%palette.length];ctx.fill();start=end});ctx.font='12px Inter,Segoe UI';rows.slice(0,7).forEach((row,i)=>{const y=22+i*24;ctx.fillStyle=palette[i%palette.length];ctx.fillRect(w*.62,y-10,10,10);ctx.fillStyle=getComputedStyle(document.body).getPropertyValue('--ink');ctx.fillText(`${row[labelKey]} · ${Math.round(Number(row[valueKey]||0)/total*100)}%`,w*.62+16,y)})}
    function drawColumn(canvas,rows,labelKey,valueKey){const ctx=canvas.getContext('2d'),w=canvas.clientWidth,h=canvas.clientHeight,dpr=window.devicePixelRatio||1;canvas.width=w*dpr;canvas.height=h*dpr;ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);const max=Math.max(1,...rows.map(r=>Number(r[valueKey]||0)));const pad=30,barW=Math.max(18,(w-pad*2)/(rows.length||1)-12);ctx.font='12px Inter,Segoe UI';rows.forEach((row,i)=>{const x=pad+i*(barW+12),bh=(h-70)*Number(row[valueKey]||0)/max,y=h-38-bh;ctx.fillStyle=palette[i%palette.length];ctx.fillRect(x,y,barW,bh);ctx.fillStyle=getComputedStyle(document.body).getPropertyValue('--muted');ctx.fillText(String(row[labelKey]||'').slice(0,10),x,h-16)})}
    async function api(url,options={}){const token=localStorage.getItem('fastrack_auth_token');options={...options,headers:{...(options.headers||{})}};if(token)options.headers.Authorization=`Bearer ${token}`;const r=await fetch(url,options);const data=await r.json();if(r.status===401){localStorage.removeItem('fastrack_auth_token');showLogin();throw new Error(data.error||'Cần đăng nhập')}if(!r.ok)throw new Error(data.error||'Có lỗi xảy ra');return data}
    function showLogin(){authGate.classList.remove('hidden')}
    function hideLogin(){authGate.classList.add('hidden')}
    function switchView(id){document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===id));document.querySelectorAll('.navbtn').forEach(b=>b.classList.toggle('active',b.dataset.view===id));document.getElementById('pageTitle').textContent={dashboard:'Tổng quan',offlineData:'Dữ liệu offline',expenses:'Chi phí',inventory:'Vật tư kho',projects:'Dự án',projectAccounting:'Kế toán công trình',construction:'Công trường',documents:'Chứng từ',forms:'Biểu mẫu',reports:'Báo cáo',accounting:'Sổ sách kế toán',finance:'Kiểm soát & tài chính',security:'Bảo mật',settings:'Cài đặt',deploy:'Tên miền'}[id]||'FasTrack ERP';document.getElementById('side').classList.remove('open')}
    async function boot(){const me=await api('/api/auth/me');state.auth=me.user||null;if(!me.authenticated){showLogin();return}hideLogin();userChip.textContent=`${state.auth.full_name||state.auth.username} · ${state.auth.role}`;await loadAll()}
    async function loadAll(){await Promise.all([loadDashboard(),loadOfflineData(),loadCatalogs(),loadExpenses(),loadInventory(),loadProjects(),loadProjectAccounting(),loadConstruction(),loadDocuments(),loadForms(),loadReports(),loadAccounting(),loadFinance(),loadSettings(),loadUsers()])}
    async function loadDashboard(){state.dashboard=await api('/api/dashboard');renderDashboard()}
    async function loadOfflineData(){const [data,schema]=await Promise.all([api('/api/offline-data'),api('/api/offline-schema')]);state.offlineData=data;state.offlineSchema=schema;renderOfflineData();renderOfflineSchema()}
    async function loadOfflineTable(name,page=1){const q=offlineTableSearch.value||'';state.offlineTable=await api(`/api/offline-data/${encodeURIComponent(name)}?limit=100&page=${page}&q=${encodeURIComponent(q)}`);renderOfflinePreview()}
    async function loadCatalogs(){const [projects,categories]=await Promise.all([api('/api/projects'),api('/api/categories')]);state.projects=projects;state.categories=categories;fillSelects();renderProjects()}
    async function loadExpenses(){state.expenses=await api('/api/expenses');renderExpenses()}
    async function loadInventory(){const [items,history,workspace]=await Promise.all([api('/api/inventory'),api('/api/inventory/history'),api('/api/inventory-workspace')]);state.inventory=workspace.materials||items;state.history=workspace.history||history;state.inventoryWorkspace=workspace;renderInventory();fillInventorySelects()}
    async function loadProjects(){state.projects=await api('/api/projects');fillSelects();renderProjects()}
    async function loadProjectAccounting(){state.projectAccounting=await api('/api/project-accounting');renderProjectAccounting()}
    async function loadConstruction(){const [workItems,diaries]=await Promise.all([api('/api/construction/work-items'),api('/api/construction/diaries')]);state.workItems=workItems;state.diaries=diaries;renderConstruction();fillInventorySelects()}
    async function loadDocuments(){state.documents=await api('/api/documents');renderDocuments()}
    async function loadForms(){state.forms=await api('/api/forms');renderForms()}
    async function loadReports(){state.reports=await api('/api/reports/summary');state.monthlyExport=await api(`/api/export/monthly-report?month=${encodeURIComponent(reportMonth.value||new Date().toISOString().slice(0,7))}`);renderReports()}
    async function loadAccounting(){state.accounting=await api('/api/accounting-workspace');renderAccounting()}
    async function loadFinance(){state.finance=await api('/api/finance-center');renderFinance()}
    async function loadSettings(){state.settings=await api('/api/settings');renderSettings()}
    async function loadUsers(){try{state.users=await api('/api/users');renderUsers()}catch(err){state.users=[];renderUsers(err.message)}}
    function fillSelects(){const projectOptions='<option value="">Không gắn dự án</option>'+state.projects.map(p=>`<option value="${p.id}">${esc(p.code)} - ${esc(p.name)}</option>`).join('');const requiredProjectOptions=state.projects.map(p=>`<option value="${p.id}">${esc(p.code)} - ${esc(p.name)}</option>`).join('');const categoryOptions=state.categories.map(c=>`<option value="${c.id}">${esc(c.code)} - ${esc(c.name)}</option>`).join('');expenseProject.innerHTML=projectOptions;diaryProject.innerHTML=projectOptions;documentProject.innerHTML=projectOptions;contractProject.innerHTML=requiredProjectOptions;costPlanProject.innerHTML=requiredProjectOptions;revenueProject.innerHTML=requiredProjectOptions;expenseCategory.innerHTML=categoryOptions;documentCategory.innerHTML='<option value="">Chọn danh mục</option>'+categoryOptions;costPlanCategory.innerHTML=categoryOptions;fillContractSelects()}
    function fillInventorySelects(){const ws=state.inventoryWorkspace||{};const mats=(ws.materials||state.inventory||[]);const work=(ws.work_items||state.workItems||[]);const matOptions='<option value="">Chọn vật tư</option>'+mats.map(m=>`<option value="${m.id}">${esc(m.code)} - ${esc(m.name)} (${money(m.quantity)} ${esc(m.unit||'')})</option>`).join('');const projectOptions='<option value="">Kho chung</option>'+state.projects.map(p=>`<option value="${p.id}">${esc(p.code)} - ${esc(p.name)}</option>`).join('');const workOptions='<option value="">Không gắn hạng mục</option>'+work.map(w=>`<option value="${w.id}">${esc(w.project_code)} · ${esc(w.item_code)} ${esc(w.item_name)}</option>`).join('');if(typeof inventoryMaterialSelect!=='undefined'){inventoryMaterialSelect.innerHTML=matOptions;standardMaterialSelect.innerHTML=matOptions;inventoryProjectSelect.innerHTML=projectOptions;inventoryWorkItemSelect.innerHTML=workOptions;standardWorkItemSelect.innerHTML=workOptions}}
    function fillContractSelects(){const rows=(state.projectAccounting&&state.projectAccounting.contracts)||[];const options='<option value="">Chọn hợp đồng</option>'+rows.map(c=>`<option value="${c.id}">${esc(c.contract_no)} - ${esc(c.partner_name)}</option>`).join('');if(typeof billingContract!=='undefined'){billingContract.innerHTML=options;revenueContract.innerHTML=options}}
    function renderOfflineData(){const d=state.offlineData||{},s=d.summary||{};odTables.textContent=s.table_count||0;odActiveTables.textContent=s.active_table_count||0;odRecords.textContent=money(s.record_count);const q=(offlineSearch.value||'').toLowerCase();const tables=(d.tables||[]).filter(t=>JSON.stringify(t).toLowerCase().includes(q));offlineTableRows.innerHTML=tables.map(t=>`<tr><td><strong>${esc(t.label)}</strong></td><td>${esc(t.name)}</td><td class="num">${money(t.count)}</td><td><button class="secondary" type="button" data-offline-table="${esc(t.name)}">Xem</button></td></tr>`).join('')||'<tr><td colspan="4" class="empty">Chưa có dữ liệu.</td></tr>';document.querySelectorAll('[data-offline-table]').forEach(btn=>btn.addEventListener('click',()=>{offlineTableSearch.value='';loadOfflineTable(btn.dataset.offlineTable)}));if(!state.offlineTable&&tables.length){loadOfflineTable(tables.find(t=>t.count)?.name||tables[0].name)}}
    function renderOfflinePreview(){const t=state.offlineTable||{},rows=t.rows||[],columns=(t.columns&&t.columns.length?t.columns:[...new Set(rows.flatMap(r=>Object.keys(r)))]).slice(0,14);offlinePreviewTitle.textContent=`${t.label||t.name||''} · ${money(t.total||0)} dòng · trang ${t.page||1}`;odCurrent.textContent=t.name||'-';odPreviewCount.textContent=`${money(rows.length)} / ${money(t.total||0)}`;offlinePrevBtn.disabled=(t.page||1)<=1;offlineNextBtn.disabled=((t.offset||0)+rows.length)>=(t.total||0);offlinePreviewHead.innerHTML=columns.length?`<tr>${columns.map(c=>`<th>${esc(c)}</th>`).join('')}</tr>`:'';offlinePreviewRows.innerHTML=rows.map(r=>`<tr>${columns.map(c=>`<td>${esc(String(r[c]??'').slice(0,120))}</td>`).join('')}</tr>`).join('')||'<tr><td class="empty">Không có dòng dữ liệu.</td></tr>'}
    function renderOfflineSchema(){const s=state.offlineSchema||{},q=(schemaSearch.value||'').toLowerCase();const tables=(s.tables||[]).filter(t=>JSON.stringify({name:t.name,label:t.label,columns:t.columns}).toLowerCase().includes(q));schemaRows.innerHTML=tables.map(t=>`<tr><td><strong>${esc(t.name)}</strong><br><span class="muted">${esc(t.label)}</span></td><td class="num">${money(t.column_count)}</td><td class="num">${money(t.row_count)}</td><td class="num">${money((t.indexes||[]).length)}</td><td class="num">${money((t.foreign_keys||[]).length)}</td><td><span class="status ${t.data_exposed?'':'low'}">${t.data_exposed?'online':'schema'}</span></td></tr>`).join('')||'<tr><td colspan="6" class="empty">Chưa có cấu trúc dữ liệu.</td></tr>';relationRows.innerHTML=(s.relationships||[]).map(r=>`<tr><td>${esc(r.from_table)}</td><td>${esc(r.from_column)}</td><td>${esc(r.to_table)}</td><td>${esc(r.to_column)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Chưa khai báo khóa ngoại.</td></tr>'}
    function renderDashboard(){const d=state.dashboard||{},s=d.stats||{},t=d.trend||{};kTotal.textContent=money(s.total_expenses);kMonth.textContent=money(s.monthly_expenses);kProjects.textContent=s.total_projects||0;kDocs.textContent=s.total_documents||0;kStock.textContent=money(d.stock_value);kMonthTrend.textContent=`${pct(t.month_delta_percent)} so với tháng trước`;kMonthTrend.className=`trend ${Number(t.month_delta||0)<=0?'good':'bad'}`;const max=Math.max(1,...(d.categories||[]).map(x=>x.total||0));categoryBars.innerHTML=(d.categories||[]).map(x=>`<div class="barrow"><strong>${esc(x.name)}</strong><div class="bar"><div class="fill" style="width:${Math.round((x.total||0)/max*100)}%"></div></div><span class="num">${money(x.total)}</span></div>`).join('')||'<div class="empty">Chưa có dữ liệu chi phí.</div>';drawPie(categoryPie,d.categories||[],'name','total');drawColumn(projectChart,d.projects||[],'name','total');activeProjectRows.innerHTML=(d.active_projects||[]).map(p=>`<div class="project-line"><header><strong>${esc(p.code)} · ${esc(p.name)}</strong><span>${money(p.budget_used_percent)}%</span></header><div class="progress"><div class="fill" style="width:${Math.min(100,Math.round(p.budget_used_percent||p.progress||0))}%"></div></div><div class="muted">Đã chi ${money(p.spent)} / ngân sách ${money(p.budget)} · tiến độ ${money(p.progress)}% · ${money(p.work_item_count)} hạng mục</div></div>`).join('')||'<div class="empty">Chưa có dự án active.</div>';const sync=d.sync||{};syncBox.innerHTML=`<strong>Real-time sync</strong><span>Chế độ: ${esc(sync.mode||'')}</span><span>Chi phí cập nhật: ${esc(sync.last_expense_update||'chưa có')}</span><span>Chứng từ cập nhật: ${esc(sync.last_document_update||'chưa có')}</span>`;lowStockRows.innerHTML=(d.low_stock||[]).map(x=>`<tr><td>${esc(x.code)}</td><td>${esc(x.name)}</td><td class="num">${money(x.quantity)} ${esc(x.unit)}</td><td class="num">${money(x.min_quantity)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Không có cảnh báo tồn kho.</td></tr>'}
    function renderExpenses(){const q=(expenseSearch.value||'').toLowerCase();const rows=state.expenses.filter(e=>JSON.stringify(e).toLowerCase().includes(q));expenseRows.innerHTML=rows.map(e=>`<tr><td>${esc(e.expense_date)}</td><td>${esc(e.project_name||'')}</td><td>${esc(e.category_name||'')}</td><td>${esc(e.description||'')}</td><td class="num">${money(e.amount)}</td><td><span class="status">${esc(e.status)}</span></td></tr>`).join('')||'<tr><td colspan="6" class="empty">Chưa có chi phí.</td></tr>'}
    function renderInventory(){const ws=state.inventoryWorkspace||{},sum=ws.summary||{};if(typeof invStockValue!=='undefined'){invStockValue.textContent=money(sum.stock_value);invMaterialCount.textContent=sum.material_count||0;invSmartAlerts.textContent=sum.smart_alert_count||0;invStandardCount.textContent=sum.standard_count||0}const q=(inventorySearch.value||'').toLowerCase();const rows=state.inventory.filter(i=>JSON.stringify(i).toLowerCase().includes(q));inventoryRows.innerHTML=rows.map(i=>`<tr><td>${esc(i.code)}</td><td>${esc(i.name)}</td><td>${esc(i.category)}</td><td class="num">${money(i.quantity)} ${esc(i.unit)}</td><td class="num">${money(i.average_cost||i.unit_price)}</td><td class="num">${money(i.min_quantity||0)}</td><td><span class="status ${Number(i.quantity||0)<=Number(i.min_quantity||0)&&Number(i.min_quantity||0)>0?'low':''}">${esc(i.status)}</span></td></tr>`).join('')||'<tr><td colspan="7" class="empty">Chưa có vật tư.</td></tr>';smartStockRows.innerHTML=(ws.alerts||[]).map(a=>`<tr><td><span class="status ${a.priority==='critical'?'low':''}">${esc(a.priority||'warning')}</span></td><td><strong>${esc(a.project_code||'Kho')}</strong> ${esc(a.project_name||'')}<br><span class="muted">${esc(a.item_code||'')} ${esc(a.item_name||'')}</span></td><td>${esc(a.material_code||a.code||'')} ${esc(a.material_name||a.name||'')}</td><td class="num">${money(a.needed_qty||a.min_quantity)} ${esc(a.unit||'')}</td><td class="num">${money(a.available_qty??a.quantity)} ${esc(a.unit||'')}</td><td class="num">${money(a.shortage_qty)} ${esc(a.unit||'')}</td><td><button class="secondary" type="button" data-po-alert='${esc(JSON.stringify(a))}'>${esc(a.suggestion||'Tạo PO')}</button></td></tr>`).join('')||'<tr><td colspan="7" class="empty">Không có cảnh báo vật tư.</td></tr>';valuationRows.innerHTML=(ws.valuation_methods||[]).map(v=>`<tr><td>${esc(v.code)}</td><td>${esc(v.name)}</td><td><span class="status ${v.status==='planned'?'low':''}">${esc(v.status)}</span></td></tr>`).join('')||'<tr><td colspan="3" class="empty">Chưa có cấu hình tính giá.</td></tr>';poRows.innerHTML=(ws.purchase_orders||[]).map(p=>`<tr><td>${esc(p.po_number)}</td><td>${esc(p.supplier_name||'')}</td><td>${esc(p.order_date||'')}</td><td class="num">${money(p.total_amount)}</td><td><span class="status">${esc(p.status)}</span></td></tr>`).join('')||'<tr><td colspan="5" class="empty">Chưa có đơn mua hàng mở.</td></tr>';historyRows.innerHTML=state.history.map(h=>`<tr><td>${esc(h.transaction_date)}</td><td>${esc(h.material_code||h.code)}</td><td>${esc(h.material_name||h.name)}</td><td>${esc(h.transaction_type)}</td><td class="num">${money(h.quantity)}</td><td>${esc(h.project_code||'')} ${esc(h.project_name||'')}</td><td>${esc(h.notes)}</td></tr>`).join('')||'<tr><td colspan="7" class="empty">Chưa có giao dịch kho.</td></tr>';document.querySelectorAll('[data-po-alert]').forEach(btn=>btn.addEventListener('click',async()=>{try{const alert=JSON.parse(btn.dataset.poAlert);await api('/api/purchase-orders/from-alert',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(alert)});await loadInventory();toast('Đã tạo đơn mua hàng nháp')}catch(err){toast(err.message)}}))}
    function renderProjects(){projectRows.innerHTML=state.projects.map(p=>`<tr><td>${esc(p.code)}</td><td>${esc(p.name)}</td><td>${esc(p.location)}</td><td class="num">${money(p.budget)}</td><td><span class="status">${esc(p.status)}</span></td></tr>`).join('')||'<tr><td colspan="5" class="empty">Chưa có dự án.</td></tr>'}
    function renderProjectAccounting(){const pa=state.projectAccounting||{},d=pa.dashboard||{};paActive.textContent=d.active_projects||0;paPlanned.textContent=money(d.total_planned);paSpent.textContent=money(d.total_spent);paRevenue.textContent=money(d.total_revenue);paProfit.textContent=money(d.profit);fillContractSelects();const q=(contractSearch.value||'').toLowerCase();const contracts=(pa.contracts||[]).filter(c=>JSON.stringify(c).toLowerCase().includes(q));contractRows.innerHTML=contracts.map(c=>`<tr><td>${esc(c.project_code)} ${esc(c.project_name)}</td><td>${esc(c.contract_type)}</td><td>${esc(c.contract_no)}</td><td>${esc(c.partner_name)}</td><td class="num">${money(c.contract_value)}</td><td class="num">${money(c.billed)}</td><td><span class="status">${esc(c.status)}</span></td></tr>`).join('')||'<tr><td colspan="7" class="empty">Chưa có hợp đồng.</td></tr>';billingRows.innerHTML=(pa.billings||[]).map(b=>`<tr><td>${esc(b.billing_date)}</td><td>${esc(b.contract_no)}</td><td>${esc(b.milestone_name)}</td><td class="num">${money(b.net_amount)}</td><td><span class="status">${esc(b.status)}</span></td></tr>`).join('')||'<tr><td colspan="5" class="empty">Chưa có nghiệm thu.</td></tr>';revenueRows.innerHTML=(pa.revenues||[]).map(r=>`<tr><td>${esc(r.revenue_date)}</td><td>${esc(r.project_code)} ${esc(r.project_name)}</td><td>${esc(r.contract_no)}</td><td class="num">${money(r.amount)}</td><td class="num">${money(r.vat_amount)}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">Chưa có doanh thu.</td></tr>';costPlanRows.innerHTML=(pa.cost_plan_actual||[]).map(x=>{const diff=Number(x.planned||0)-Number(x.actual||0);return `<tr><td>${esc(x.project_code)} ${esc(x.project_name)}</td><td>${esc(x.category)}</td><td class="num">${money(x.planned)}</td><td class="num">${money(x.actual)}</td><td class="num">${money(diff)}</td></tr>`}).join('')||'<tr><td colspan="5" class="empty">Chưa có dự toán.</td></tr>';projectPlRows.innerHTML=(pa.project_pl||[]).map(x=>`<tr><td>${esc(x.code)} ${esc(x.name)}</td><td class="num">${money(x.revenue)}</td><td class="num">${money(x.cost)}</td><td class="num">${money(x.profit)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Chưa có P/L công trình.</td></tr>'}
    function renderConstruction(){workRows.innerHTML=state.workItems.map(w=>`<tr><td>${esc(w.project_code)} ${esc(w.project_name)}</td><td>${esc(w.item_code)}</td><td>${esc(w.item_name)}</td><td class="num">${money(w.planned_quantity)} ${esc(w.unit)}</td><td class="num">${money(w.percent_complete)}%</td><td class="num">${money(w.actual_expense)}</td><td><span class="status">${esc(w.status)}</span></td></tr>`).join('')||'<tr><td colspan="7" class="empty">Chưa có hạng mục.</td></tr>';diaryRows.innerHTML=state.diaries.map(d=>`<tr><td>${esc(d.diary_date)}</td><td>${esc(d.project_code)} ${esc(d.project_name)}</td><td>${esc(d.weather)}</td><td>${esc(d.work_content)}</td><td>${esc(d.reporter)}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">Chưa có nhật ký.</td></tr>'}
    function renderDocuments(){const q=(documentSearch.value||'').toLowerCase();const rows=state.documents.filter(d=>JSON.stringify(d).toLowerCase().includes(q));documentRows.innerHTML=rows.map(d=>`<tr><td>${esc(d.doc_date)}</td><td>${esc(d.doc_type)}</td><td>${esc(d.doc_number)}</td><td>${esc(d.supplier_name)}</td><td class="num">${money(d.amount)}</td><td>${esc(d.project_name)}</td><td><span class="status">${esc(d.status)}</span></td></tr>`).join('')||'<tr><td colspan="7" class="empty">Chưa có chứng từ.</td></tr>'}
    function renderForms(){const q=(formSearch.value||'').toLowerCase();const rows=state.forms.filter(f=>JSON.stringify(f).toLowerCase().includes(q));formRows.innerHTML=rows.map(f=>`<tr><td>${esc(f.form_code)}</td><td>${esc(f.form_name)}</td><td>${esc(f.scope)}</td><td>${esc(f.file_path)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Chưa có biểu mẫu.</td></tr>'}
    function drawBars(el,rows,labelKey,valueKey){const max=Math.max(1,...rows.map(r=>Number(r[valueKey]||0)));el.innerHTML=rows.map(r=>`<div class="barrow"><strong>${esc(r[labelKey])}</strong><div class="bar"><div class="fill" style="width:${Math.round(Number(r[valueKey]||0)/max*100)}%"></div></div><span class="num">${money(r[valueKey])}</span></div>`).join('')||'<div class="empty">Chưa có dữ liệu.</div>'}
    function renderReports(){const r=state.reports||{},m=state.monthlyExport||{},s=m.summary||{};monthlyExportRows.innerHTML=[['Kỳ báo cáo',m.month||''],['Từ ngày',m.start_date||''],['Đến ngày',m.end_date||''],['Tổng chi phí',money(s.expense_total)],['Số dòng chi phí',money(s.expense_count)],['Số danh mục',money(s.category_count)],['Số dự án',money(s.project_count)]].map(x=>`<tr><td>${esc(x[0])}</td><td class="num">${esc(x[1])}</td></tr>`).join('');drawBars(monthlyBars,r.monthly_expenses||[],'month','total');drawBars(projectBars,r.project_expenses||[],'project','total');stockReportRows.innerHTML=(r.stock||[]).map(x=>`<tr><td>${esc(x.name)}</td><td class="num">${money(x.quantity)}</td><td class="num">${money(x.unit_price)}</td><td class="num">${money(x.total_value)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Chưa có dữ liệu tồn kho.</td></tr>'}
    function renderAccounting(){const a=state.accounting||{},k=a.kpis||{},bs=a.balance_sheet||{},tot=bs.totals||{};aAccounts.textContent=k.account_count||0;aJournals.textContent=k.journal_count||0;aDebit.textContent=money(k.trial_debit);aCredit.textContent=money(k.trial_credit);aOpenDebt.textContent=money(k.open_ar_ap);const aq=(accountSearch.value||'').toLowerCase();const accounts=(a.accounts||[]).filter(x=>JSON.stringify(x).toLowerCase().includes(aq));accountRows.innerHTML=accounts.map(x=>`<tr><td><strong>${esc(x.account_code)}</strong></td><td>${esc(x.account_name)}</td><td>${esc(x.account_type)}</td><td class="num">${money(x.debit)}</td><td class="num">${money(x.credit)}</td><td class="num">${money(x.balance)}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">Chưa có tài khoản.</td></tr>';accountSummaryRows.innerHTML=(a.account_summary||[]).map(x=>`<tr><td>${esc(x.account_type)}</td><td class="num">${money(x.account_count)}</td><td class="num">${money(x.active_count)}</td></tr>`).join('')||'<tr><td colspan="3" class="empty">Chưa có nhóm tài khoản.</td></tr>';trialRows.innerHTML=(a.trial_balance||[]).map(x=>`<tr><td>${esc(x.account_code)}</td><td>${esc(x.account_name)}</td><td class="num">${money(x.debit)}</td><td class="num">${money(x.credit)}</td><td class="num">${money(x.balance)}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">Chưa có phát sinh.</td></tr>';balanceRows.innerHTML=(bs.rows||[]).map(x=>`<tr><td>${esc(x.group)}</td><td>${esc(x.account_code)}</td><td>${esc(x.account_name)}</td><td class="num">${money(x.balance)}</td></tr>`).join('')+`<tr><td><strong>Lệch</strong></td><td></td><td>Tài sản - Nguồn vốn</td><td class="num"><strong>${money(tot.difference)}</strong></td></tr>`;const jq=(journalSearch.value||'').toLowerCase();const journals=(a.journal_entries||[]).filter(x=>JSON.stringify(x).toLowerCase().includes(jq));journalRows.innerHTML=journals.map(x=>`<tr><td>${esc(x.entry_date)}</td><td>${esc(x.entry_number||x.id)}</td><td><strong>${esc(x.description)}</strong><br><span class="muted">${esc(x.project_code)} ${esc(x.project_name)}</span></td><td>${esc(x.debit_account)} / ${esc(x.credit_account)}</td><td class="num">${money(x.amount)}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">Chưa có bút toán.</td></tr>';arApRows.innerHTML=(a.ar_ap_items||[]).map(x=>`<tr><td>${esc(x.partner_name)}<br><span class="muted">${esc(x.partner_type||'')}</span></td><td>${esc(x.project_code)} ${esc(x.project_name)}</td><td>${esc(x.due_date||'')}</td><td class="num">${money(x.amount)}</td><td class="num">${money(x.remaining_amount)}</td><td><span class="status ${x.status==='open'?'low':''}">${esc(x.status)}</span></td></tr>`).join('')||'<tr><td colspan="6" class="empty">Chưa có công nợ.</td></tr>';costCollectRows.innerHTML=(a.project_cost_collection||[]).map(x=>`<tr><td>${esc(x.project_code)} ${esc(x.project_name)}</td><td>${esc(x.category_name)}</td><td class="num">${money(x.line_count)}</td><td class="num">${money(x.amount)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Chưa có chi phí công trình.</td></tr>';fiscalStatusRows.innerHTML=(a.fiscal_status||[]).map(x=>`<tr><td>${esc(x.fiscal_year)}</td><td class="num">${money(x.period_count)}</td><td class="num">${money(x.locked_count)}</td><td class="num">${money(x.closed_count)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Chưa có kỳ kế toán.</td></tr>'}
    function renderFinance(){const f=state.finance||{},bank=f.bank||{},vat=f.vat||{},pay=f.payroll||{},payCurrent=pay.current||{};fAlerts.textContent=(f.alert_counts||{}).total||0;fUnreconciled.textContent=(bank.summary||{}).unreconciled_count||0;fOutputVat.textContent=money(vat.output_vat);fVatPayable.textContent=money(vat.vat_payable);fPayrollNet.textContent=money(payCurrent.net_amount);const q=(financeSearch.value||'').toLowerCase();const alerts=(f.alerts||[]).filter(a=>JSON.stringify(a).toLowerCase().includes(q));alertRows.innerHTML=alerts.map(a=>`<tr><td>${esc(a.source)}</td><td><span class="status ${a.priority==='critical'?'low':''}">${esc(a.priority)}</span></td><td><strong>${esc(a.title)}</strong><br><span class="muted">${esc(a.message)}</span></td><td>${esc(a.due_date||'')}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Không có cảnh báo.</td></tr>';thresholdRows.innerHTML=(f.approval_thresholds||[]).map(t=>`<tr><td>${esc(t.role)}</td><td class="num">${money(t.max_amount)}</td><td>${Number(t.can_final_approve)?'Có':'Không'}</td><td><span class="status">${Number(t.active)?'active':'inactive'}</span></td></tr>`).join('')||'<tr><td colspan="4" class="empty">Chưa có hạn mức.</td></tr>';periodRows.innerHTML=(f.fiscal_periods||[]).slice(0,18).map(p=>`<tr><td>${esc(p.fiscal_period)}</td><td>${esc(p.period_start)}</td><td>${esc(p.period_end)}</td><td><span class="status ${Number(p.is_locked)?'low':''}">${Number(p.is_locked)?'locked':'open'}</span></td><td><button class="secondary" type="button" data-lock-period="${esc(p.fiscal_period)}" data-lock-value="${Number(p.is_locked)?0:1}">${Number(p.is_locked)?'Mở':'Khóa'}</button></td></tr>`).join('')||'<tr><td colspan="5" class="empty">Chưa có kỳ kế toán.</td></tr>';bankRows.innerHTML=(bank.unreconciled||[]).map(b=>`<tr><td>${esc(b.transaction_date)}</td><td>${esc(b.description)}</td><td class="num">${money(b.amount)}</td><td><span class="status">open</span></td></tr>`).join('')||'<tr><td colspan="4" class="empty">Không có giao dịch chưa đối soát.</td></tr>';vatRows.innerHTML=[['Kỳ',vat.period||''],['Doanh thu chịu thuế',money(vat.output_taxable)],['VAT đầu ra',money(vat.output_vat)],['Chi phí chịu thuế',money(vat.input_taxable)],['VAT đầu vào',money(vat.input_vat)],['Phải nộp',money(vat.vat_payable)],['Còn khấu trừ',money(vat.vat_credit)]].map(x=>`<tr><td>${esc(x[0])}</td><td class="num">${esc(x[1])}</td></tr>`).join('');auditRows.innerHTML=(f.audit_log||[]).map(a=>`<tr><td>${esc(a.created_at)}</td><td>${esc(a.action)}</td><td>${esc(a.entity_type)}</td><td>${esc(String(a.detail||'').slice(0,120))}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Chưa có audit log.</td></tr>';document.querySelectorAll('[data-lock-period]').forEach(btn=>btn.addEventListener('click',async()=>{try{await api('/api/fiscal-locks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fiscal_period:btn.dataset.lockPeriod,locked:btn.dataset.lockValue})});await loadFinance();toast('Đã cập nhật khóa kỳ')}catch(err){toast(err.message)}}))}
    function renderUsers(error){if(error){userRows.innerHTML=`<tr><td colspan="6" class="empty">${esc(error)}</td></tr>`;return}userRows.innerHTML=(state.users||[]).map(u=>`<tr><td>${esc(u.username)}</td><td>${esc(u.full_name||'')}</td><td>${esc(u.email||'')}</td><td><span class="status">${esc(u.role)}</span></td><td>${Number(u.active)?'active':'inactive'}</td><td>${esc(u.created_at||'')}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">Chưa có người dùng.</td></tr>'}
    function renderSettings(){const s=state.settings||{},settings=s.settings||{};['company_name','company_tax_code','company_representative','company_short_name'].forEach(k=>{if(settingsForm[k])settingsForm[k].value=settings[k]||''});backupHealth.textContent=s.backup_health||'';linkageRows.innerHTML=(s.linkage_checks||[]).map(x=>`<tr><td>${esc(x.group)}</td><td>${esc(x.issue)}</td><td><span class="status">${esc(x.status)}</span></td><td class="num">${money(x.count)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Không có cảnh báo.</td></tr>';databaseRows.innerHTML=Object.entries(s.database||{}).map(([k,v])=>`<tr><td>${esc(k)}</td><td class="num">${money(v)}</td></tr>`).join('');backupRows.innerHTML=(s.backups||[]).map(b=>`<tr><td>${esc(b.name)}</td><td>${esc(b.size)}</td><td>${esc(b.date)}</td></tr>`).join('')||'<tr><td colspan="3" class="empty">Chưa có bản sao lưu.</td></tr>'}
    document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));
    document.querySelectorAll('[data-view-jump]').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.viewJump)));
    themeBtn.addEventListener('click',()=>{document.body.classList.toggle('dark');themeBtn.textContent=document.body.classList.contains('dark')?'Sáng':'Tối';renderDashboard();renderReports()});
    menuBtn.addEventListener('click',()=>side.classList.toggle('open'));refreshBtn.addEventListener('click',()=>loadAll().then(()=>toast('Đã tải lại dữ liệu')));
    loginForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(loginForm).entries());try{const r=await api('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(r.token)localStorage.setItem('fastrack_auth_token',r.token);state.auth=r.user;hideLogin();userChip.textContent=`${state.auth.full_name||state.auth.username} · ${state.auth.role}`;loginForm.reset();await loadAll();toast('Đã đăng nhập')}catch(err){toast(err.message)}});
    logoutBtn.addEventListener('click',async()=>{try{await api('/api/auth/logout',{method:'POST'});}catch(err){}localStorage.removeItem('fastrack_auth_token');state.auth=null;userChip.textContent='Chưa đăng nhập';showLogin()});
    reloadUsersBtn.addEventListener('click',()=>loadUsers());
    offlineSearch.addEventListener('input',renderOfflineData);schemaSearch.addEventListener('input',renderOfflineSchema);schemaJsonBtn.addEventListener('click',()=>{window.location.href='/api/offline-schema/export.json'});offlineReloadBtn.addEventListener('click',()=>loadOfflineData());offlineJsonBtn.addEventListener('click',()=>{window.location.href='/api/offline-data/export.json?limit_per_table=5000'});offlineCsvBtn.addEventListener('click',()=>{const t=state.offlineTable||{};if(!t.name)return toast('Chưa chọn bảng');window.location.href=`/api/offline-data/${encodeURIComponent(t.name)}.csv?limit=5000&q=${encodeURIComponent(offlineTableSearch.value||'')}`});offlinePrevBtn.addEventListener('click',()=>{const t=state.offlineTable||{};if(t.name&&Number(t.page)>1)loadOfflineTable(t.name,Number(t.page)-1)});offlineNextBtn.addEventListener('click',()=>{const t=state.offlineTable||{};if(t.name)loadOfflineTable(t.name,Number(t.page||1)+1)});offlineTableSearch.addEventListener('change',()=>{const t=state.offlineTable||{};if(t.name)loadOfflineTable(t.name,1)});
    reportMonth.value=new Date().toISOString().slice(0,7);reportMonth.addEventListener('change',()=>loadReports());csvExportBtn.addEventListener('click',()=>{window.location.href=`/api/export/monthly-report.csv?month=${encodeURIComponent(reportMonth.value)}`});sheetsExportBtn.addEventListener('click',async()=>{try{const r=await api('/api/export/sheets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({month:reportMonth.value})});toast(r.url?'Đã xuất Google Sheets':'Đã gửi yêu cầu xuất')}catch(err){toast(err.message)}});
    expenseSearch.addEventListener('input',renderExpenses);inventorySearch.addEventListener('input',renderInventory);reloadInventoryWorkspaceBtn.addEventListener('click',()=>loadInventory());contractSearch.addEventListener('input',renderProjectAccounting);documentSearch.addEventListener('input',renderDocuments);formSearch.addEventListener('input',renderForms);accountSearch.addEventListener('input',renderAccounting);journalSearch.addEventListener('input',renderAccounting);financeSearch.addEventListener('input',renderFinance);
    expenseForm.expense_date.value=new Date().toISOString().slice(0,10);
    diaryForm.diary_date.value=new Date().toISOString().slice(0,10);
    documentForm.doc_date.value=new Date().toISOString().slice(0,10);
    contractForm.signed_date.value=new Date().toISOString().slice(0,10);
    billingForm.billing_date.value=new Date().toISOString().slice(0,10);
    revenueForm.revenue_date.value=new Date().toISOString().slice(0,10);
    bankForm.transaction_date.value=new Date().toISOString().slice(0,10);
    expenseForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(expenseForm).entries());try{await api('/api/expenses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});expenseForm.reset();expenseForm.expense_date.value=new Date().toISOString().slice(0,10);await Promise.all([loadDashboard(),loadExpenses()]);toast('Đã lưu chi phí')}catch(err){toast(err.message)}});
    inventoryTransactionForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(inventoryTransactionForm).entries());try{await api('/api/inventory/transactions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});inventoryTransactionForm.reset();await Promise.all([loadDashboard(),loadInventory(),loadAccounting()]);toast('Đã ghi phiếu kho')}catch(err){toast(err.message)}});
    materialStandardForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(materialStandardForm).entries());try{await api('/api/material-standards',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});materialStandardForm.reset();materialStandardForm.basis_unit.value='m2';materialStandardForm.tolerance_percent.value='15';await loadInventory();toast('Đã lưu định mức vật tư')}catch(err){toast(err.message)}});
    projectForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(projectForm).entries());try{await api('/api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});projectForm.reset();await Promise.all([loadCatalogs(),loadDashboard()]);toast('Đã lưu dự án')}catch(err){toast(err.message)}});
    contractForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(contractForm).entries());try{await api('/api/project-accounting/contracts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});contractForm.reset();contractForm.vat_rate.value='10';contractForm.retention_rate.value='5';contractForm.signed_date.value=new Date().toISOString().slice(0,10);await loadProjectAccounting();toast('Đã lưu hợp đồng')}catch(err){toast(err.message)}});
    costPlanForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(costPlanForm).entries());try{await api('/api/project-accounting/cost-plans',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});costPlanForm.reset();await loadProjectAccounting();toast('Đã lưu dự toán')}catch(err){toast(err.message)}});
    billingForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(billingForm).entries());try{await api('/api/project-accounting/billings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});billingForm.reset();billingForm.vat_rate.value='10';billingForm.retention_rate.value='5';billingForm.billing_date.value=new Date().toISOString().slice(0,10);await Promise.all([loadProjectAccounting(),loadFinance()]);toast('Đã lưu nghiệm thu')}catch(err){toast(err.message)}});
    revenueForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(revenueForm).entries());try{await api('/api/project-accounting/revenues',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});revenueForm.reset();revenueForm.revenue_date.value=new Date().toISOString().slice(0,10);await Promise.all([loadProjectAccounting(),loadFinance()]);toast('Đã lưu doanh thu')}catch(err){toast(err.message)}});
    diaryForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(diaryForm).entries());try{await api('/api/construction/diaries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});diaryForm.reset();diaryForm.diary_date.value=new Date().toISOString().slice(0,10);await loadConstruction();toast('Đã lưu nhật ký')}catch(err){toast(err.message)}});
    documentForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(documentForm).entries());try{await api('/api/documents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});documentForm.reset();documentForm.doc_type.value='Hóa đơn';documentForm.vat_rate.value='10';documentForm.doc_date.value=new Date().toISOString().slice(0,10);await Promise.all([loadDashboard(),loadDocuments()]);toast('Đã lưu chứng từ')}catch(err){toast(err.message)}});
    thresholdForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(thresholdForm).entries());try{await api('/api/approval-thresholds',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});thresholdForm.reset();await loadFinance();toast('Đã lưu hạn mức')}catch(err){toast(err.message)}});
    bankForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(bankForm).entries());try{await api('/api/bank/transactions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});bankForm.reset();bankForm.transaction_date.value=new Date().toISOString().slice(0,10);await loadFinance();toast('Đã thêm giao dịch ngân hàng')}catch(err){toast(err.message)}});
    autoMatchBtn.addEventListener('click',async()=>{try{const r=await api('/api/bank/auto-match',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});await loadFinance();toast(`Đã tự khớp ${r.matched||0} giao dịch`)}catch(err){toast(err.message)}});
    settingsForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(settingsForm).entries());try{await api('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});await loadSettings();toast('Đã lưu cài đặt')}catch(err){toast(err.message)}});
    userForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(userForm).entries());try{await api('/api/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});userForm.reset();await loadUsers();toast('Đã tạo người dùng')}catch(err){toast(err.message)}});
    passwordForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(passwordForm).entries());try{await api('/api/auth/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});passwordForm.reset();toast('Đã đổi mật khẩu')}catch(err){toast(err.message)}});
    backupBtn.addEventListener('click',async()=>{try{const r=await api('/api/backups',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});await loadSettings();toast(r.message||'Đã sao lưu')}catch(err){toast(err.message)}});
    driveBackupBtn.addEventListener('click',async()=>{const data=Object.fromEntries(new FormData(driveBackupForm).entries());try{driveBackupStatus.textContent='Đang tạo backup và upload Drive...';const r=await api('/api/backups/drive',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});driveBackupStatus.innerHTML=r.file&&r.file.webViewLink?`Đã sao lưu Drive: <a href="${esc(r.file.webViewLink)}" target="_blank" rel="noopener">${esc(r.file.name)}</a>`:(r.message||'Đã sao lưu Drive');await loadSettings();toast('Đã sao lưu lên Google Drive')}catch(err){driveBackupStatus.textContent=err.message;toast(err.message)}});
    navigator.serviceWorker&&navigator.serviceWorker.register('/service-worker.js');
    boot().catch(err=>toast(err.message));
  </script>
</body>
</html>"""


SERVICE_WORKER = """self.addEventListener('install', event => {
  event.waitUntil(caches.open('fastrack-web-v4').then(cache => cache.addAll(['/', '/manifest.json'])));
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});"""


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=False)
