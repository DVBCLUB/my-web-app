"""Print a compact overview of the FasTrack accounting application.

This helper is intentionally short so it stays maintainable.  Detailed and
up-to-date documentation should live in README/CHANGELOG instead of a large
ASCII-art script.
"""

SECTIONS = {
    "Core modules": [
        "Accounting, expenses and journal entries",
        "Invoices, documents and attachments",
        "Materials, inventory and purchase orders",
        "Projects, construction work items and site diaries",
        "Reports, dashboard snapshots and exports",
        "Users, permissions, audit and backup utilities",
    ],
    "Entry points": [
        "Desktop app: PythonApplication1/main.py",
        "Web app: PythonApplication1/web_app.py",
        "Database bootstrap: PythonApplication1/database/__init__.py",
    ],
    "Runtime data": [
        "SQLite databases, logs, backups and generated reports are local runtime files.",
        "Do not commit local .db, backup, log, output or IDE snapshot files.",
    ],
}


def main() -> None:
    print("FasTrack ERP Accounting App")
    print("=" * 32)
    for title, lines in SECTIONS.items():
        print(f"\n{title}")
        for line in lines:
            print(f"- {line}")


if __name__ == "__main__":
    main()
