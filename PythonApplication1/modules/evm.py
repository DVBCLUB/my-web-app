"""Earned Value Management analytics for construction projects."""

import tkinter as tk
from tkinter import ttk

from database import get_connection


class EVMManager:
    """Calculate PV, EV, AC, CPI and SPI for projects and work items."""

    def __init__(self):
        self.conn = get_connection()

    def get_project_evm(self, project_id=None):
        cursor = self.conn.cursor()
        params = []
        query = """
            SELECT w.id, COALESCE(p.code, '') AS project_code, COALESCE(p.name, '') AS project_name,
                   w.item_code, w.item_name, COALESCE(w.planned_quantity, 0) AS planned_quantity,
                   COALESCE(w.completed_quantity, 0) AS completed_quantity,
                   COALESCE(w.percent_complete, 0) AS percent_complete,
                   COALESCE(w.unit_price, 0) AS unit_price,
                   COALESCE((SELECT SUM(e.amount) FROM expenses e WHERE e.work_item_id = w.id), 0) AS actual_cost
            FROM construction_work_items w
            LEFT JOIN projects p ON p.id = w.project_id
            WHERE 1=1
        """
        if project_id:
            query += " AND w.project_id = ?"
            params.append(project_id)
        query += " ORDER BY p.code, w.item_code, w.id"
        cursor.execute(query, params)
        items = []
        for row in cursor.fetchall():
            pv = float(row["planned_quantity"] or 0) * float(row["unit_price"] or 0)
            percent = float(row["percent_complete"] or 0)
            if percent <= 0 and row["planned_quantity"]:
                percent = min(float(row["completed_quantity"] or 0) / float(row["planned_quantity"]) * 100, 100)
            ev = pv * percent / 100
            ac = float(row["actual_cost"] or 0)
            cpi = ev / ac if ac else None
            spi = ev / pv if pv else None
            items.append({
                "id": row["id"],
                "project_code": row["project_code"],
                "project_name": row["project_name"],
                "item_code": row["item_code"],
                "item_name": row["item_name"],
                "percent_complete": percent,
                "pv": pv,
                "ev": ev,
                "ac": ac,
                "cpi": cpi,
                "spi": spi,
                "alert": self._alert(cpi, spi),
            })
        totals = {
            "pv": sum(item["pv"] for item in items),
            "ev": sum(item["ev"] for item in items),
            "ac": sum(item["ac"] for item in items),
        }
        totals["cpi"] = totals["ev"] / totals["ac"] if totals["ac"] else None
        totals["spi"] = totals["ev"] / totals["pv"] if totals["pv"] else None
        totals["alert"] = self._alert(totals["cpi"], totals["spi"])
        return {"items": items, "totals": totals}

    def update_work_item_percent(self, work_item_id, percent_complete):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE construction_work_items
            SET percent_complete = ?
            WHERE id = ?
        """, (float(percent_complete or 0), work_item_id))
        self.conn.commit()

    def display_evm_dashboard(self, parent):
        data = self.get_project_evm()
        totals = data["totals"]
        header = tk.Frame(parent, bg="#FFFFFF")
        header.pack(fill="x", padx=10, pady=8)
        tk.Label(
            header,
            text=(
                f"PV: {totals['pv']:,.0f}    EV: {totals['ev']:,.0f}    AC: {totals['ac']:,.0f}    "
                f"CPI: {self._fmt_ratio(totals['cpi'])}    SPI: {self._fmt_ratio(totals['spi'])}    {totals['alert']}"
            ),
            bg="#FFFFFF", fg="#17324D", font=("Segoe UI", 10, "bold")
        ).pack(anchor="w")

        cols = ("DA", "HM", "Tên hạng mục", "% HT", "PV", "EV", "AC", "CPI", "SPI", "Cảnh báo")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=15)
        for col, width in zip(cols, (70, 80, 240, 70, 110, 110, 110, 70, 70, 180)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        for item in data["items"]:
            tree.insert("", "end", values=(
                item["project_code"], item["item_code"], item["item_name"],
                f"{item['percent_complete']:.1f}%", f"{item['pv']:,.0f}",
                f"{item['ev']:,.0f}", f"{item['ac']:,.0f}",
                self._fmt_ratio(item["cpi"]), self._fmt_ratio(item["spi"]), item["alert"],
            ))
        tree.pack(fill="both", expand=True, padx=10, pady=8)

    def _alert(self, cpi, spi):
        alerts = []
        if cpi is not None and cpi < 0.9:
            alerts.append("Chi phí vượt CPI<0.9")
        if spi is not None and spi < 0.85:
            alerts.append("Tiến độ chậm SPI<0.85")
        return "; ".join(alerts) if alerts else "OK"

    def _fmt_ratio(self, value):
        return "" if value is None else f"{value:.2f}"
