"""Budget control and variance analysis."""

from __future__ import annotations

from database import get_connection


class BudgetManager:
    """Manage project budget versions and compare them with actual costs."""

    def __init__(self):
        self.conn = get_connection()

    def create_budget_version(self, project_id: int, version_no: str, name: str = "",
                              items: list[dict] | None = None) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO budget_versions (project_id, version_no, name, status)
            VALUES (?, ?, ?, 'draft')
            ON CONFLICT(project_id, version_no) DO UPDATE SET name = excluded.name
        """, (project_id, version_no, name or version_no))
        cursor.execute("SELECT id FROM budget_versions WHERE project_id = ? AND version_no = ?",
                       (project_id, version_no))
        version_id = cursor.fetchone()["id"]
        if items is not None:
            cursor.execute("DELETE FROM budget_items WHERE budget_version_id = ?", (version_id,))
            for item in items:
                quantity = float(item.get("quantity", 0) or 0)
                unit_price = float(item.get("unit_price", 0) or 0)
                budget_amount = float(item.get("budget_amount", 0) or 0) or quantity * unit_price
                cursor.execute("""
                    INSERT INTO budget_items
                    (budget_version_id, work_item_id, cost_category, description,
                     quantity, unit_price, budget_amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    version_id, item.get("work_item_id"), item.get("cost_category"),
                    item.get("description"), quantity, unit_price, budget_amount,
                ))
        self.conn.commit()
        return version_id

    def approve_budget_version(self, version_id: int, approved_by: int = 1) -> None:
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE budget_versions
            SET status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (approved_by, version_id))
        self.conn.commit()

    def get_variance_analysis(self, project_id: int, version_id: int | None = None) -> list[dict]:
        cursor = self.conn.cursor()
        if version_id is None:
            cursor.execute("""
                SELECT id FROM budget_versions
                WHERE project_id = ?
                ORDER BY CASE status WHEN 'approved' THEN 0 ELSE 1 END, id DESC
                LIMIT 1
            """, (project_id,))
            row = cursor.fetchone()
            if not row:
                return []
            version_id = row["id"]
        cursor.execute("""
            SELECT bi.cost_category, bi.work_item_id, bi.description,
                   SUM(bi.budget_amount) AS budget_amount
            FROM budget_items bi
            WHERE bi.budget_version_id = ?
            GROUP BY bi.cost_category, bi.work_item_id, bi.description
            ORDER BY bi.cost_category, bi.description
        """, (version_id,))
        budget_rows = cursor.fetchall()
        results = []
        for row in budget_rows:
            if row["work_item_id"]:
                cursor.execute("""
                    SELECT SUM(COALESCE(amount, 0)) AS actual_amount
                    FROM expenses
                    WHERE project_id = ? AND work_item_id = ?
                """, (project_id, row["work_item_id"]))
            else:
                cursor.execute("""
                    SELECT SUM(COALESCE(e.amount, 0)) AS actual_amount
                    FROM expenses e
                    LEFT JOIN expense_categories ec ON ec.id = e.category_id
                    WHERE e.project_id = ? AND (
                        ec.name = ? OR CAST(e.category_id AS TEXT) = ?
                    )
                """, (project_id, row["cost_category"], row["cost_category"]))
            actual = float((cursor.fetchone() or {"actual_amount": 0})["actual_amount"] or 0)
            budget = float(row["budget_amount"] or 0)
            variance = actual - budget
            results.append({
                "cost_category": row["cost_category"],
                "work_item_id": row["work_item_id"],
                "description": row["description"],
                "budget_amount": budget,
                "actual_amount": actual,
                "variance_amount": variance,
                "variance_percent": (variance / budget * 100) if budget else 0,
            })
        return results

    def get_budget_alerts(self, project_id: int, threshold_percent: float = 10) -> list[dict]:
        alerts = []
        for row in self.get_variance_analysis(project_id):
            if row["budget_amount"] > 0 and row["variance_percent"] >= threshold_percent:
                row = dict(row)
                row["message"] = (
                    f"Chi phi thuc te vuot du toan {row['variance_percent']:.1f}%"
                )
                alerts.append(row)
        return alerts
