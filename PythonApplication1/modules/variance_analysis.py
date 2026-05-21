"""Cost variance analysis with volume/price split and drill-down."""

import tkinter as tk
from tkinter import ttk

from database import get_connection


class VarianceAnalysisManager:
    def __init__(self):
        self.conn = get_connection()

    def get_variance_report(self, project_id=None, threshold_percent=10):
        cursor = self.conn.cursor()
        params = []
        query = """
            SELECT p.id AS project_id, p.code, p.name AS project_name,
                   ec.id AS category_id, ec.name AS category_name,
                   COALESCE(cp.planned_amount, 0) AS planned,
                   COALESCE(SUM(e.amount), 0) AS actual
            FROM projects p
            CROSS JOIN expense_categories ec
            LEFT JOIN project_cost_plans cp ON cp.project_id = p.id AND cp.category_id = ec.id
            LEFT JOIN expenses e ON e.project_id = p.id AND e.category_id = ec.id
            WHERE p.code != 'CHUNG'
        """
        if project_id:
            query += " AND p.id = ?"
            params.append(project_id)
        query += """
            GROUP BY p.id, ec.id
            HAVING planned > 0 OR actual > 0
            ORDER BY p.code, (actual - planned) DESC
        """
        cursor.execute(query, params)
        rows = []
        for row in cursor.fetchall():
            planned = float(row["planned"] or 0)
            actual = float(row["actual"] or 0)
            variance = actual - planned
            variance_pct = variance / planned * 100 if planned else 0
            volume_variance, price_variance = self._split_variance(row["project_id"], row["category_id"], variance)
            rows.append({
                "project_id": row["project_id"],
                "project_code": row["code"],
                "project_name": row["project_name"],
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "planned": planned,
                "actual": actual,
                "variance": variance,
                "variance_pct": variance_pct,
                "volume_variance": volume_variance,
                "price_variance": price_variance,
                "alert": planned > 0 and variance_pct > threshold_percent,
                "reason": self._reason(volume_variance, price_variance, variance_pct, threshold_percent),
            })
        return rows

    def get_drilldown(self, project_id, category_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT e.id, e.expense_date, e.description, e.amount, e.status,
                   COALESCE(w.item_code, '') AS item_code,
                   COALESCE(w.item_name, '') AS item_name
            FROM expenses e
            LEFT JOIN construction_work_items w ON w.id = e.work_item_id
            WHERE e.project_id = ? AND e.category_id = ?
            ORDER BY e.amount DESC, e.expense_date DESC
        """, (project_id, category_id))
        return cursor.fetchall()

    def display_variance_analysis(self, parent):
        rows = self.get_variance_report()
        cols = ("DA", "Loại CP", "Dự toán", "Thực tế", "Lệch", "%", "Volume var", "Price var", "Cảnh báo", "Nhận định")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for col, width in zip(cols, (70, 180, 110, 110, 110, 70, 110, 110, 90, 220)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        for row in rows:
            tree.insert("", "end", values=(
                row["project_code"], row["category_name"], f"{row['planned']:,.0f}",
                f"{row['actual']:,.0f}", f"{row['variance']:,.0f}",
                f"{row['variance_pct']:.1f}%", f"{row['volume_variance']:,.0f}",
                f"{row['price_variance']:,.0f}", "Vượt >10%" if row["alert"] else "", row["reason"],
            ))
        tree.pack(fill="both", expand=True, padx=10, pady=8)

    def _split_variance(self, project_id, category_id, total_variance):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(
                CASE
                    WHEN COALESCE(w.planned_quantity, 0) > 0
                    THEN (COALESCE(w.completed_quantity, 0) - COALESCE(w.planned_quantity, 0))
                         * COALESCE(w.unit_price, 0)
                    ELSE 0
                END
            ), 0)
            FROM construction_work_items w
            WHERE w.project_id = ?
        """, (project_id,))
        volume_variance = float(cursor.fetchone()[0] or 0)
        if total_variance == 0:
            return 0.0, 0.0
        if abs(volume_variance) > abs(total_variance):
            volume_variance = total_variance * 0.6
        return volume_variance, total_variance - volume_variance

    def _reason(self, volume_variance, price_variance, variance_pct, threshold_percent):
        if variance_pct <= threshold_percent:
            return "Trong ngưỡng kiểm soát"
        if abs(volume_variance) >= abs(price_variance):
            return "Biến động chủ yếu do khối lượng/phạm vi"
        return "Biến động chủ yếu do đơn giá/giá mua"
