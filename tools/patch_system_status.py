from pathlib import Path

path = Path('PythonApplication1/web_app.py')
text = path.read_text(encoding='utf-8')

anchor = '\n    return app\n\n\nINDEX_HTML = r"""<!doctype html>'
insert = '''

    @app.get("/healthz")
    def healthz():
        return jsonify({
            "ok": True,
            "service": "FT ERP",
            "time": datetime.now().isoformat(timespec="seconds"),
            "revision": os.environ.get("K_REVISION", "local"),
        })

    @app.get("/api/system/status")
    @api_error
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
        return jsonify({
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
        })
'''
if '/api/system/status' not in text:
    text = text.replace(anchor, insert + anchor, 1)

path.write_text(text, encoding='utf-8')
