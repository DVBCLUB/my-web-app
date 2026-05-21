"""Minimal Flask PWA for field/mobile workflows.

Run with:
    python web_app.py
Then open http://127.0.0.1:5000
"""

from datetime import date

try:
    from flask import Flask, jsonify, request, Response
except ImportError:  # pragma: no cover - lets desktop app import safely.
    Flask = None

from database import init_database
from modules.accounting import ExpenseManager
from modules.materials import MaterialManager
from modules.advance_workflow import AdvanceWorkflowManager


def create_app():
    if Flask is None:
        raise RuntimeError("Can cai Flask de chay web/mobile: pip install flask")
    init_database()
    app = Flask(__name__)

    @app.get("/")
    def index():
        return Response(INDEX_HTML, mimetype="text/html")

    @app.get("/manifest.json")
    def manifest():
        return jsonify({
            "name": "FasTrack ERP Mobile",
            "short_name": "FasTrack",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#f3f6fb",
            "theme_color": "#17324D",
            "icons": [],
        })

    @app.get("/service-worker.js")
    def service_worker():
        return Response(SERVICE_WORKER, mimetype="text/javascript")

    @app.get("/api/inventory")
    def inventory():
        rows = MaterialManager().get_all_materials()
        return jsonify([
            {
                "id": row[0], "code": row[1], "name": row[2], "unit": row[3],
                "quantity": row[4], "unit_price": row[5], "category": row[6], "status": row[7],
            }
            for row in rows
        ])

    @app.post("/api/expenses")
    def create_expense():
        data = request.get_json(force=True)
        expense_id = ExpenseManager().add_expense(
            data.get("expense_date") or date.today().isoformat(),
            data.get("project_id"),
            data["category_id"],
            data.get("description", ""),
            float(data.get("amount", 0)),
            data.get("paid_by", ""),
            data.get("payment_method", "Tiền mặt"),
            data.get("notes", ""),
            int(data.get("created_by", 1)),
        )
        return jsonify({"id": expense_id, "status": "created"})

    @app.get("/api/advances/pending")
    def pending_advances():
        mgr = AdvanceWorkflowManager()
        rows = mgr.get_advance_requests(status="submitted") if hasattr(mgr, "get_advance_requests") else []
        return jsonify([dict(row) for row in rows])

    return app


INDEX_HTML = """<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="manifest" href="/manifest.json">
  <title>FasTrack ERP Mobile</title>
  <style>
    body{font-family:Arial,sans-serif;margin:0;background:#f3f6fb;color:#172033}
    header{background:#17324D;color:white;padding:14px 16px;font-weight:700}
    main{padding:14px;display:grid;gap:12px}
    section{background:white;border:1px solid #d8e0ea;padding:12px}
    input,select,button,textarea{width:100%;box-sizing:border-box;margin-top:6px;padding:10px;font-size:16px}
    button{background:#1a56a5;color:white;border:0;font-weight:700}
    table{width:100%;border-collapse:collapse;font-size:13px}td,th{border-bottom:1px solid #e5eaf0;padding:6px;text-align:left}
  </style>
</head>
<body>
  <header>FasTrack ERP Mobile</header>
  <main>
    <section>
      <h3>Nhập phiếu chi nhanh</h3>
      <input id="category" placeholder="Loại chi phí ID">
      <input id="amount" placeholder="Số tiền" inputmode="decimal">
      <textarea id="desc" placeholder="Nội dung"></textarea>
      <button onclick="saveExpense()">Lưu phiếu chi</button>
      <p id="msg"></p>
    </section>
    <section>
      <h3>Tồn kho</h3>
      <button onclick="loadInventory()">Tải tồn kho</button>
      <div id="inventory"></div>
    </section>
  </main>
  <script>
    navigator.serviceWorker && navigator.serviceWorker.register('/service-worker.js');
    async function saveExpense(){
      const payload={category_id:category.value,amount:amount.value,description:desc.value};
      const r=await fetch('/api/expenses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      msg.textContent=JSON.stringify(await r.json());
    }
    async function loadInventory(){
      const rows=await (await fetch('/api/inventory')).json();
      inventory.innerHTML='<table><tr><th>Mã</th><th>Tên</th><th>Tồn</th></tr>'+rows.map(r=>`<tr><td>${r.code}</td><td>${r.name}</td><td>${r.quantity} ${r.unit||''}</td></tr>`).join('')+'</table>';
    }
  </script>
</body>
</html>"""


SERVICE_WORKER = """self.addEventListener('install', e => {
  e.waitUntil(caches.open('fastrack-v1').then(c => c.addAll(['/','/manifest.json'])));
});
self.addEventListener('fetch', e => {
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});"""


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=False)
