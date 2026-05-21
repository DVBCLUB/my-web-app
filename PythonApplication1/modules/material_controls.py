"""Material consumption standards and abnormal usage alerts."""

import tkinter as tk
from tkinter import ttk

from database import get_connection


class MaterialControlManager:
    def __init__(self):
        self.conn = get_connection()

    def save_standard(self, material_id, work_item_id=None, basis_unit='m2',
                      standard_qty_per_unit=0, tolerance_percent=15, notes=''):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO material_standards
            (work_item_id, material_id, basis_unit, standard_qty_per_unit, tolerance_percent, notes, active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(work_item_id, material_id, basis_unit) DO UPDATE SET
                standard_qty_per_unit = excluded.standard_qty_per_unit,
                tolerance_percent = excluded.tolerance_percent,
                notes = excluded.notes,
                active = 1
        """, (work_item_id, material_id, basis_unit, standard_qty_per_unit, tolerance_percent, notes))
        self.conn.commit()

    def get_consumption_alerts(self, project_id=None):
        cursor = self.conn.cursor()
        params = []
        query = """
            SELECT p.code AS project_code, p.name AS project_name,
                   COALESCE(w.item_code, '') AS item_code,
                   COALESCE(w.item_name, 'Chung') AS item_name,
                   m.code AS material_code, m.name AS material_name, m.unit,
                   s.standard_qty_per_unit, s.tolerance_percent,
                   COALESCE(w.completed_quantity, 0) AS completed_quantity,
                   COALESCE(SUM(CASE WHEN it.transaction_type = 'export' THEN it.quantity ELSE 0 END), 0) AS actual_qty
            FROM material_standards s
            JOIN materials m ON m.id = s.material_id
            LEFT JOIN construction_work_items w ON w.id = s.work_item_id
            LEFT JOIN projects p ON p.id = COALESCE(w.project_id, ?)
            LEFT JOIN inventory_transactions it ON it.material_id = s.material_id
                AND it.transaction_type = 'export'
                AND (it.project_id = p.id OR p.id IS NULL)
            WHERE s.active = 1
        """
        params.append(project_id)
        if project_id:
            query += " AND p.id = ?"
            params.append(project_id)
        query += """
            GROUP BY s.id, p.id
            ORDER BY p.code, m.name
        """
        cursor.execute(query, params)
        rows = []
        for row in cursor.fetchall():
            allowed = float(row["completed_quantity"] or 0) * float(row["standard_qty_per_unit"] or 0)
            threshold = allowed * (1 + float(row["tolerance_percent"] or 15) / 100)
            actual = float(row["actual_qty"] or 0)
            rows.append({
                "project_code": row["project_code"] or "",
                "project_name": row["project_name"] or "",
                "item_code": row["item_code"],
                "item_name": row["item_name"],
                "material_code": row["material_code"],
                "material_name": row["material_name"],
                "unit": row["unit"],
                "allowed_qty": allowed,
                "actual_qty": actual,
                "variance_qty": actual - allowed,
                "tolerance_percent": row["tolerance_percent"],
                "alert": allowed > 0 and actual > threshold,
            })
        return rows

    def display_material_alerts(self, parent):
        rows = self.get_consumption_alerts()
        cols = ("DA", "Hạng mục", "Vật tư", "ĐVT", "Định mức cho phép", "Thực xuất", "Lệch", "Cảnh báo")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for col, width in zip(cols, (70, 190, 200, 70, 130, 110, 110, 120)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        for row in rows:
            tree.insert("", "end", values=(
                row["project_code"], row["item_name"], row["material_name"], row["unit"],
                f"{row['allowed_qty']:,.4f}", f"{row['actual_qty']:,.4f}",
                f"{row['variance_qty']:,.4f}", "Vượt định mức" if row["alert"] else "",
            ))
        tree.pack(fill="both", expand=True, padx=10, pady=8)
