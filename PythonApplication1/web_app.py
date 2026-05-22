"""Flask web edition for FasTrack ERP.

Run with:
    python web_app.py
Then open:
    http://127.0.0.1:5000
"""

from __future__ import annotations

from datetime import date
from functools import wraps
from typing import Any

try:
    from flask import Flask, Response, jsonify, request
except ImportError:  # pragma: no cover - lets the desktop app import safely.
    Flask = None

from database import get_connection, init_database
from modules.accounting import ExpenseManager
from modules.advance_workflow import AdvanceWorkflowManager
from modules.backup import BackupManager
from modules.construction import ConstructionManager
from modules.invoices import DocumentManager
from modules.materials import MaterialManager
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


def api_error(handler):
    @wraps(handler)
    def wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised through Flask runtime.
            return jsonify({"error": str(exc)}), 400

    return wrapper


def create_app():
    if Flask is None:
        raise RuntimeError("Cần cài Flask để chạy bản web: pip install flask")

    init_database()
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False

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

    @app.get("/api/dashboard")
    @api_error
    def dashboard():
        expenses = ExpenseManager()
        materials = MaterialManager()
        construction = ConstructionManager()
        report = WebReportGenerator()
        stats = expenses.get_statistics()
        categories = [
            {"name": row[0] or "Chưa phân loại", "total": row[1] or 0}
            for row in expenses.get_expenses_by_category()
        ]
        projects = [
            {"name": row[0] or "Không có dự án", "total": row[1] or 0}
            for row in expenses.get_expenses_by_project()
        ]
        stock_value = sum(float(row[3] or 0) for row in report.get_material_stock_summary())
        low_stock = [
            row_to_dict(row, ("id", "code", "name", "unit", "quantity", "min_quantity", "category"))
            for row in materials.check_low_stock()
        ]
        return jsonify(
            {
                "stats": stats,
                "categories": categories[:8],
                "projects": projects[:8],
                "construction": construction.get_dashboard(),
                "stock_value": stock_value,
                "low_stock": low_stock,
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
            int(data.get("created_by") or 1),
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

    @app.post("/api/inventory/transactions")
    @api_error
    def create_inventory_transaction():
        data = request.get_json(force=True)
        transaction_id = MaterialManager().add_inventory_transaction(
            int(data["material_id"]),
            data["transaction_type"],
            float(data.get("quantity") or 0),
            data.get("project_id") or None,
            data.get("notes", ""),
            int(data.get("created_by") or 1),
        )
        return jsonify({"id": transaction_id, "status": "created"})

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
            int(data.get("created_by") or 1),
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
    :root{--bg:#f4f6f8;--panel:#fff;--ink:#172033;--muted:#667085;--line:#dde3ea;--brand:#1e3a5f;--accent:#0f766e;--warn:#b45309;--danger:#b42318}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Segoe UI,Arial,sans-serif}button,input,select,textarea{font:inherit}
    .shell{display:grid;grid-template-columns:248px 1fr;min-height:100vh}.side{background:#10243d;color:#fff;padding:18px 14px;position:sticky;top:0;height:100vh;overflow:auto}.brand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:18px;margin-bottom:18px}.mark{width:34px;height:34px;border-radius:8px;background:#c9a227;display:grid;place-items:center;color:#10243d}
    nav{display:grid;gap:6px}.navbtn{width:100%;border:0;background:transparent;color:#dbe7f3;text-align:left;padding:11px 12px;border-radius:7px;cursor:pointer}.navbtn.active,.navbtn:hover{background:#1e3a5f;color:#fff}.main{padding:20px;min-width:0}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:16px}.topbar h1{font-size:24px;margin:0}.muted{color:var(--muted)}.grid{display:grid;gap:14px}.kpis{grid-template-columns:repeat(5,minmax(140px,1fr))}.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px}.kpi .label{font-size:13px;color:var(--muted)}.kpi .value{font-size:22px;font-weight:800;margin-top:6px}.two{grid-template-columns:1.1fr .9fr}.actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.primary{background:var(--brand);color:#fff;border:0;border-radius:7px;padding:10px 13px;cursor:pointer}.secondary{background:#fff;color:var(--brand);border:1px solid var(--line);border-radius:7px;padding:9px 12px;cursor:pointer}.danger{color:var(--danger)}.toolbar{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}.search{max-width:320px;width:100%;border:1px solid var(--line);border-radius:7px;padding:10px 12px}
    table{width:100%;border-collapse:collapse;font-size:14px}th,td{border-bottom:1px solid var(--line);padding:10px;text-align:left;vertical-align:top}th{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}td.num{text-align:right;font-variant-numeric:tabular-nums}.status{display:inline-block;padding:3px 8px;border-radius:999px;background:#e8eef6;color:#1e3a5f;font-size:12px}.status.low{background:#fff4e5;color:var(--warn)}.bars{display:grid;gap:10px}.barrow{display:grid;grid-template-columns:130px 1fr 96px;gap:10px;align-items:center}.bar{height:9px;background:#e8edf3;border-radius:999px;overflow:hidden}.fill{height:100%;background:var(--accent);width:0}.form{display:grid;grid-template-columns:repeat(2,minmax(160px,1fr));gap:10px}.form .wide{grid-column:1/-1}label{display:grid;gap:5px;font-size:13px;color:var(--muted)}input,select,textarea{border:1px solid var(--line);border-radius:7px;padding:10px;background:#fff;color:var(--ink)}textarea{min-height:76px;resize:vertical}.toast{position:fixed;right:18px;bottom:18px;background:#10243d;color:#fff;border-radius:8px;padding:12px 14px;box-shadow:0 10px 30px #0003;display:none}.view{display:none}.view.active{display:grid}.empty{padding:28px;color:var(--muted);text-align:center}.mobilebar{display:none;background:#10243d;color:#fff;padding:12px 14px;align-items:center;justify-content:space-between}.mobilebar button{width:42px;height:38px;border:1px solid #365472;background:#16304f;color:#fff;border-radius:7px}
    @media(max-width:980px){.shell{grid-template-columns:1fr}.side{display:none;position:fixed;z-index:5;width:260px}.side.open{display:block}.mobilebar{display:flex}.main{padding:14px}.kpis,.two{grid-template-columns:1fr}.form{grid-template-columns:1fr}.toolbar{align-items:stretch;flex-direction:column}.search{max-width:none}.barrow{grid-template-columns:1fr}.tablewrap{overflow:auto}.topbar{align-items:flex-start;flex-direction:column}}
  </style>
</head>
<body>
  <div class="mobilebar"><strong>FasTrack ERP</strong><button id="menuBtn" title="Mở menu">☰</button></div>
  <div class="shell">
    <aside class="side" id="side">
      <div class="brand"><span class="mark">FT</span><span>FasTrack ERP</span></div>
      <nav>
        <button class="navbtn active" data-view="dashboard">Tổng quan</button>
        <button class="navbtn" data-view="expenses">Chi phí</button>
        <button class="navbtn" data-view="inventory">Vật tư kho</button>
        <button class="navbtn" data-view="projects">Dự án</button>
        <button class="navbtn" data-view="construction">Công trường</button>
        <button class="navbtn" data-view="documents">Chứng từ</button>
        <button class="navbtn" data-view="forms">Biểu mẫu</button>
        <button class="navbtn" data-view="reports">Báo cáo</button>
        <button class="navbtn" data-view="settings">Cài đặt</button>
        <button class="navbtn" data-view="deploy">Tên miền</button>
      </nav>
    </aside>
    <main class="main">
      <div class="topbar">
        <div><h1 id="pageTitle">Tổng quan</h1><div class="muted" id="subtitle">Bản web dùng chung dữ liệu với ứng dụng desktop.</div></div>
        <div class="actions"><button class="secondary" id="refreshBtn">Tải lại</button><button class="primary" data-view-jump="expenses">Thêm chi phí</button></div>
      </div>

      <section class="view active" id="dashboard">
        <div class="grid kpis">
          <div class="card kpi"><div class="label">Tổng chi phí</div><div class="value" id="kTotal">0</div></div>
          <div class="card kpi"><div class="label">Chi phí tháng này</div><div class="value" id="kMonth">0</div></div>
          <div class="card kpi"><div class="label">Dự án active</div><div class="value" id="kProjects">0</div></div>
          <div class="card kpi"><div class="label">Chứng từ</div><div class="value" id="kDocs">0</div></div>
          <div class="card kpi"><div class="label">Giá trị tồn kho</div><div class="value" id="kStock">0</div></div>
        </div>
        <div class="grid two">
          <div class="card"><h3>Chi phí theo danh mục</h3><div class="bars" id="categoryBars"></div></div>
          <div class="card"><h3>Cảnh báo tồn kho</h3><div class="tablewrap"><table><thead><tr><th>Mã</th><th>Vật tư</th><th>Tồn</th><th>Min</th></tr></thead><tbody id="lowStockRows"></tbody></table></div></div>
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
        <div class="card">
          <div class="toolbar"><h3>Tồn kho vật tư</h3><input class="search" id="inventorySearch" placeholder="Tìm vật tư"></div>
          <div class="tablewrap"><table><thead><tr><th>Mã</th><th>Tên vật tư</th><th>Nhóm</th><th>Tồn</th><th>Đơn giá</th><th>Trạng thái</th></tr></thead><tbody id="inventoryRows"></tbody></table></div>
        </div>
        <div class="card">
          <h3>Giao dịch kho gần đây</h3>
          <div class="tablewrap"><table><thead><tr><th>Ngày</th><th>Mã</th><th>Vật tư</th><th>Loại</th><th>SL</th><th>Ghi chú</th></tr></thead><tbody id="historyRows"></tbody></table></div>
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
        <div class="grid two">
          <div class="card"><h3>Chi phí theo tháng</h3><div class="bars" id="monthlyBars"></div></div>
          <div class="card"><h3>Chi phí theo dự án</h3><div class="bars" id="projectBars"></div></div>
        </div>
        <div class="card">
          <h3>Tồn kho theo giá trị</h3>
          <div class="tablewrap"><table><thead><tr><th>Vật tư</th><th>Số lượng</th><th>Đơn giá</th><th>Giá trị</th></tr></thead><tbody id="stockReportRows"></tbody></table></div>
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
            <div class="wide actions"><button class="primary" type="submit">Lưu cài đặt</button><button class="secondary" type="button" id="backupBtn">Sao lưu ngay</button></div>
          </form>
          <p class="muted" id="backupHealth"></p>
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
    const state={dashboard:null,expenses:[],inventory:[],history:[],projects:[],categories:[],workItems:[],diaries:[],documents:[],forms:[],reports:null,settings:null};
    const money=v=>new Intl.NumberFormat('vi-VN',{maximumFractionDigits:0}).format(Number(v||0));
    const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    const toast=t=>{const el=document.getElementById('toast');el.textContent=t;el.style.display='block';setTimeout(()=>el.style.display='none',2800)};
    async function api(url,options){const r=await fetch(url,options);const data=await r.json();if(!r.ok)throw new Error(data.error||'Có lỗi xảy ra');return data}
    function switchView(id){document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===id));document.querySelectorAll('.navbtn').forEach(b=>b.classList.toggle('active',b.dataset.view===id));document.getElementById('pageTitle').textContent={dashboard:'Tổng quan',expenses:'Chi phí',inventory:'Vật tư kho',projects:'Dự án',construction:'Công trường',documents:'Chứng từ',forms:'Biểu mẫu',reports:'Báo cáo',settings:'Cài đặt',deploy:'Tên miền'}[id]||'FasTrack ERP';document.getElementById('side').classList.remove('open')}
    async function loadAll(){await Promise.all([loadDashboard(),loadCatalogs(),loadExpenses(),loadInventory(),loadProjects(),loadConstruction(),loadDocuments(),loadForms(),loadReports(),loadSettings()])}
    async function loadDashboard(){state.dashboard=await api('/api/dashboard');renderDashboard()}
    async function loadCatalogs(){const [projects,categories]=await Promise.all([api('/api/projects'),api('/api/categories')]);state.projects=projects;state.categories=categories;fillSelects();renderProjects()}
    async function loadExpenses(){state.expenses=await api('/api/expenses');renderExpenses()}
    async function loadInventory(){const [items,history]=await Promise.all([api('/api/inventory'),api('/api/inventory/history')]);state.inventory=items;state.history=history;renderInventory()}
    async function loadProjects(){state.projects=await api('/api/projects');fillSelects();renderProjects()}
    async function loadConstruction(){const [workItems,diaries]=await Promise.all([api('/api/construction/work-items'),api('/api/construction/diaries')]);state.workItems=workItems;state.diaries=diaries;renderConstruction()}
    async function loadDocuments(){state.documents=await api('/api/documents');renderDocuments()}
    async function loadForms(){state.forms=await api('/api/forms');renderForms()}
    async function loadReports(){state.reports=await api('/api/reports/summary');renderReports()}
    async function loadSettings(){state.settings=await api('/api/settings');renderSettings()}
    function fillSelects(){const projectOptions='<option value="">Không gắn dự án</option>'+state.projects.map(p=>`<option value="${p.id}">${esc(p.code)} - ${esc(p.name)}</option>`).join('');const categoryOptions=state.categories.map(c=>`<option value="${c.id}">${esc(c.code)} - ${esc(c.name)}</option>`).join('');expenseProject.innerHTML=projectOptions;diaryProject.innerHTML=projectOptions;documentProject.innerHTML=projectOptions;expenseCategory.innerHTML=categoryOptions;documentCategory.innerHTML='<option value="">Chọn danh mục</option>'+categoryOptions}
    function renderDashboard(){const d=state.dashboard||{},s=d.stats||{};kTotal.textContent=money(s.total_expenses);kMonth.textContent=money(s.monthly_expenses);kProjects.textContent=s.total_projects||0;kDocs.textContent=s.total_documents||0;kStock.textContent=money(d.stock_value);const max=Math.max(1,...(d.categories||[]).map(x=>x.total||0));categoryBars.innerHTML=(d.categories||[]).map(x=>`<div class="barrow"><strong>${esc(x.name)}</strong><div class="bar"><div class="fill" style="width:${Math.round((x.total||0)/max*100)}%"></div></div><span class="num">${money(x.total)}</span></div>`).join('')||'<div class="empty">Chưa có dữ liệu chi phí.</div>';lowStockRows.innerHTML=(d.low_stock||[]).map(x=>`<tr><td>${esc(x.code)}</td><td>${esc(x.name)}</td><td class="num">${money(x.quantity)} ${esc(x.unit)}</td><td class="num">${money(x.min_quantity)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Không có cảnh báo tồn kho.</td></tr>'}
    function renderExpenses(){const q=(expenseSearch.value||'').toLowerCase();const rows=state.expenses.filter(e=>JSON.stringify(e).toLowerCase().includes(q));expenseRows.innerHTML=rows.map(e=>`<tr><td>${esc(e.expense_date)}</td><td>${esc(e.project_name||'')}</td><td>${esc(e.category_name||'')}</td><td>${esc(e.description||'')}</td><td class="num">${money(e.amount)}</td><td><span class="status">${esc(e.status)}</span></td></tr>`).join('')||'<tr><td colspan="6" class="empty">Chưa có chi phí.</td></tr>'}
    function renderInventory(){const q=(inventorySearch.value||'').toLowerCase();const rows=state.inventory.filter(i=>JSON.stringify(i).toLowerCase().includes(q));inventoryRows.innerHTML=rows.map(i=>`<tr><td>${esc(i.code)}</td><td>${esc(i.name)}</td><td>${esc(i.category)}</td><td class="num">${money(i.quantity)} ${esc(i.unit)}</td><td class="num">${money(i.unit_price)}</td><td><span class="status">${esc(i.status)}</span></td></tr>`).join('')||'<tr><td colspan="6" class="empty">Chưa có vật tư.</td></tr>';historyRows.innerHTML=state.history.map(h=>`<tr><td>${esc(h.transaction_date)}</td><td>${esc(h.code)}</td><td>${esc(h.name)}</td><td>${esc(h.transaction_type)}</td><td class="num">${money(h.quantity)}</td><td>${esc(h.notes)}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">Chưa có giao dịch kho.</td></tr>'}
    function renderProjects(){projectRows.innerHTML=state.projects.map(p=>`<tr><td>${esc(p.code)}</td><td>${esc(p.name)}</td><td>${esc(p.location)}</td><td class="num">${money(p.budget)}</td><td><span class="status">${esc(p.status)}</span></td></tr>`).join('')||'<tr><td colspan="5" class="empty">Chưa có dự án.</td></tr>'}
    function renderConstruction(){workRows.innerHTML=state.workItems.map(w=>`<tr><td>${esc(w.project_code)} ${esc(w.project_name)}</td><td>${esc(w.item_code)}</td><td>${esc(w.item_name)}</td><td class="num">${money(w.planned_quantity)} ${esc(w.unit)}</td><td class="num">${money(w.percent_complete)}%</td><td class="num">${money(w.actual_expense)}</td><td><span class="status">${esc(w.status)}</span></td></tr>`).join('')||'<tr><td colspan="7" class="empty">Chưa có hạng mục.</td></tr>';diaryRows.innerHTML=state.diaries.map(d=>`<tr><td>${esc(d.diary_date)}</td><td>${esc(d.project_code)} ${esc(d.project_name)}</td><td>${esc(d.weather)}</td><td>${esc(d.work_content)}</td><td>${esc(d.reporter)}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">Chưa có nhật ký.</td></tr>'}
    function renderDocuments(){const q=(documentSearch.value||'').toLowerCase();const rows=state.documents.filter(d=>JSON.stringify(d).toLowerCase().includes(q));documentRows.innerHTML=rows.map(d=>`<tr><td>${esc(d.doc_date)}</td><td>${esc(d.doc_type)}</td><td>${esc(d.doc_number)}</td><td>${esc(d.supplier_name)}</td><td class="num">${money(d.amount)}</td><td>${esc(d.project_name)}</td><td><span class="status">${esc(d.status)}</span></td></tr>`).join('')||'<tr><td colspan="7" class="empty">Chưa có chứng từ.</td></tr>'}
    function renderForms(){const q=(formSearch.value||'').toLowerCase();const rows=state.forms.filter(f=>JSON.stringify(f).toLowerCase().includes(q));formRows.innerHTML=rows.map(f=>`<tr><td>${esc(f.form_code)}</td><td>${esc(f.form_name)}</td><td>${esc(f.scope)}</td><td>${esc(f.file_path)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Chưa có biểu mẫu.</td></tr>'}
    function drawBars(el,rows,labelKey,valueKey){const max=Math.max(1,...rows.map(r=>Number(r[valueKey]||0)));el.innerHTML=rows.map(r=>`<div class="barrow"><strong>${esc(r[labelKey])}</strong><div class="bar"><div class="fill" style="width:${Math.round(Number(r[valueKey]||0)/max*100)}%"></div></div><span class="num">${money(r[valueKey])}</span></div>`).join('')||'<div class="empty">Chưa có dữ liệu.</div>'}
    function renderReports(){const r=state.reports||{};drawBars(monthlyBars,r.monthly_expenses||[],'month','total');drawBars(projectBars,r.project_expenses||[],'project','total');stockReportRows.innerHTML=(r.stock||[]).map(x=>`<tr><td>${esc(x.name)}</td><td class="num">${money(x.quantity)}</td><td class="num">${money(x.unit_price)}</td><td class="num">${money(x.total_value)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Chưa có dữ liệu tồn kho.</td></tr>'}
    function renderSettings(){const s=state.settings||{},settings=s.settings||{};['company_name','company_tax_code','company_representative','company_short_name'].forEach(k=>{if(settingsForm[k])settingsForm[k].value=settings[k]||''});backupHealth.textContent=s.backup_health||'';linkageRows.innerHTML=(s.linkage_checks||[]).map(x=>`<tr><td>${esc(x.group)}</td><td>${esc(x.issue)}</td><td><span class="status">${esc(x.status)}</span></td><td class="num">${money(x.count)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Không có cảnh báo.</td></tr>';databaseRows.innerHTML=Object.entries(s.database||{}).map(([k,v])=>`<tr><td>${esc(k)}</td><td class="num">${money(v)}</td></tr>`).join('');backupRows.innerHTML=(s.backups||[]).map(b=>`<tr><td>${esc(b.name)}</td><td>${esc(b.size)}</td><td>${esc(b.date)}</td></tr>`).join('')||'<tr><td colspan="3" class="empty">Chưa có bản sao lưu.</td></tr>'}
    document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));
    document.querySelectorAll('[data-view-jump]').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.viewJump)));
    menuBtn.addEventListener('click',()=>side.classList.toggle('open'));refreshBtn.addEventListener('click',()=>loadAll().then(()=>toast('Đã tải lại dữ liệu')));
    expenseSearch.addEventListener('input',renderExpenses);inventorySearch.addEventListener('input',renderInventory);documentSearch.addEventListener('input',renderDocuments);formSearch.addEventListener('input',renderForms);
    expenseForm.expense_date.value=new Date().toISOString().slice(0,10);
    diaryForm.diary_date.value=new Date().toISOString().slice(0,10);
    documentForm.doc_date.value=new Date().toISOString().slice(0,10);
    expenseForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(expenseForm).entries());try{await api('/api/expenses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});expenseForm.reset();expenseForm.expense_date.value=new Date().toISOString().slice(0,10);await Promise.all([loadDashboard(),loadExpenses()]);toast('Đã lưu chi phí')}catch(err){toast(err.message)}});
    projectForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(projectForm).entries());try{await api('/api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});projectForm.reset();await Promise.all([loadCatalogs(),loadDashboard()]);toast('Đã lưu dự án')}catch(err){toast(err.message)}});
    diaryForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(diaryForm).entries());try{await api('/api/construction/diaries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});diaryForm.reset();diaryForm.diary_date.value=new Date().toISOString().slice(0,10);await loadConstruction();toast('Đã lưu nhật ký')}catch(err){toast(err.message)}});
    documentForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(documentForm).entries());try{await api('/api/documents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});documentForm.reset();documentForm.doc_type.value='Hóa đơn';documentForm.vat_rate.value='10';documentForm.doc_date.value=new Date().toISOString().slice(0,10);await Promise.all([loadDashboard(),loadDocuments()]);toast('Đã lưu chứng từ')}catch(err){toast(err.message)}});
    settingsForm.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(settingsForm).entries());try{await api('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});await loadSettings();toast('Đã lưu cài đặt')}catch(err){toast(err.message)}});
    backupBtn.addEventListener('click',async()=>{try{const r=await api('/api/backups',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});await loadSettings();toast(r.message||'Đã sao lưu')}catch(err){toast(err.message)}});
    navigator.serviceWorker&&navigator.serviceWorker.register('/service-worker.js');
    loadAll().catch(err=>toast(err.message));
  </script>
</body>
</html>"""


SERVICE_WORKER = """self.addEventListener('install', event => {
  event.waitUntil(caches.open('fastrack-web-v2').then(cache => cache.addAll(['/', '/manifest.json'])));
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});"""


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=False)
