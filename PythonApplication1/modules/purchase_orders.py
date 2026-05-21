"""Purchase order workflow for materials."""

from __future__ import annotations

from datetime import date

from database import get_connection


class PurchaseOrderManager:
    """Create, approve and track material purchase orders."""

    def __init__(self):
        self.conn = get_connection()

    def create_purchase_order(self, po_number: str, supplier_id: int | None = None,
                              supplier_name: str = "", order_date: str | None = None,
                              expected_date: str | None = None, notes: str = "",
                              lines: list[dict] | None = None) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO purchase_orders
            (po_number, supplier_id, supplier_name, order_date, expected_date, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, 'draft')
        """, (po_number, supplier_id, supplier_name, order_date or date.today().isoformat(),
              expected_date, notes))
        po_id = cursor.lastrowid
        for line in lines or []:
            self._add_line(cursor, po_id, line)
        self._refresh_total(cursor, po_id)
        self.conn.commit()
        return po_id

    def add_line(self, purchase_order_id: int, material_id: int | None, description: str,
                 quantity: float, unit_price: float, project_id: int | None = None) -> int:
        cursor = self.conn.cursor()
        line_id = self._add_line(cursor, purchase_order_id, {
            "material_id": material_id,
            "description": description,
            "quantity": quantity,
            "unit_price": unit_price,
            "project_id": project_id,
        })
        self._refresh_total(cursor, purchase_order_id)
        self.conn.commit()
        return line_id

    def approve(self, purchase_order_id: int, approved_by: int = 1) -> None:
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE purchase_orders
            SET status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (approved_by, purchase_order_id))
        self.conn.commit()

    def receive_line(self, line_id: int, received_quantity: float) -> None:
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE purchase_order_lines
            SET received_quantity = COALESCE(received_quantity, 0) + ?
            WHERE id = ?
        """, (float(received_quantity or 0), line_id))
        self.conn.commit()

    def get_open_purchase_orders(self) -> list[dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT po.*,
                   SUM(COALESCE(pol.quantity, 0)) AS ordered_quantity,
                   SUM(COALESCE(pol.received_quantity, 0)) AS received_quantity
            FROM purchase_orders po
            LEFT JOIN purchase_order_lines pol ON pol.purchase_order_id = po.id
            WHERE po.status IN ('draft', 'approved')
            GROUP BY po.id
            ORDER BY po.order_date DESC, po.id DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def _add_line(self, cursor, purchase_order_id: int, line: dict) -> int:
        quantity = float(line.get("quantity", 0) or 0)
        unit_price = float(line.get("unit_price", 0) or 0)
        cursor.execute("""
            INSERT INTO purchase_order_lines
            (purchase_order_id, material_id, description, quantity, unit_price, project_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            purchase_order_id, line.get("material_id"), line.get("description"),
            quantity, unit_price, line.get("project_id"),
        ))
        return cursor.lastrowid

    def _refresh_total(self, cursor, purchase_order_id: int) -> None:
        cursor.execute("""
            UPDATE purchase_orders
            SET total_amount = (
                SELECT COALESCE(SUM(quantity * unit_price), 0)
                FROM purchase_order_lines
                WHERE purchase_order_id = ?
            )
            WHERE id = ?
        """, (purchase_order_id, purchase_order_id))
