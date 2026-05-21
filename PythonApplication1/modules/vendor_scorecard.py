"""Vendor scorecard logic."""

from __future__ import annotations

from database import get_connection
from utils.audit import write_audit


class VendorScorecardManager:
    def __init__(self):
        self.conn = get_connection()

    def record_score(self, supplier_name: str, period: str, quality_score: float,
                     delivery_score: float, price_score: float, document_score: float,
                     supplier_id: int | None = None, violation_notes: str = "") -> int:
        scores = [quality_score, delivery_score, price_score, document_score]
        if any(float(score or 0) < 1 or float(score or 0) > 5 for score in scores):
            raise ValueError("Diem danh gia nha cung cap phai nam trong khoang 1-5")
        supplier_id = supplier_id or self._ensure_supplier(supplier_name)
        status = self._status(sum(float(score) for score in scores) / 4)
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO vendor_scorecards
            (supplier_id, supplier_name, period, price_score, quality_score,
             delivery_score, document_score, violation_notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            supplier_id, supplier_name, period, price_score, quality_score,
            delivery_score, document_score, violation_notes, status,
        ))
        scorecard_id = cursor.lastrowid
        self.conn.commit()
        write_audit("RECORD_VENDOR_SCORE", "vendor_scorecard", scorecard_id,
                    new_value={"supplier_name": supplier_name, "period": period, "status": status})
        return scorecard_id

    def update_from_purchase_order(self, purchase_order_id: int, quality_score: float = 4,
                                   delivery_score: float = 4, price_score: float = 4,
                                   document_score: float = 4) -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT po.supplier_id, COALESCE(s.supplier_name, po.supplier_name) AS supplier_name,
                   substr(po.order_date, 1, 7) AS period
            FROM purchase_orders po
            LEFT JOIN suppliers s ON s.id = po.supplier_id
            WHERE po.id = ?
        """, (purchase_order_id,))
        po = cursor.fetchone()
        if not po:
            raise ValueError("Khong tim thay don mua hang")
        return self.record_score(
            po["supplier_name"] or "Nha cung cap",
            po["period"],
            quality_score,
            delivery_score,
            price_score,
            document_score,
            supplier_id=po["supplier_id"],
        )

    def get_vendor_summary(self, supplier_id: int | None = None) -> list[dict]:
        cursor = self.conn.cursor()
        params = []
        where = ""
        if supplier_id:
            where = "WHERE supplier_id = ?"
            params.append(supplier_id)
        cursor.execute(f"""
            SELECT supplier_id, supplier_name,
                   AVG((price_score + quality_score + delivery_score + document_score) / 4.0) AS average_score,
                   COUNT(*) AS rating_count,
                   MAX(period) AS latest_period,
                   MIN(status) AS status
            FROM vendor_scorecards
            {where}
            GROUP BY supplier_id, supplier_name
            ORDER BY average_score DESC, supplier_name
        """, params)
        return [dict(row) for row in cursor.fetchall()]

    def _ensure_supplier(self, supplier_name: str) -> int | None:
        name = (supplier_name or "").strip()
        if not name:
            return None
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO suppliers (supplier_name) VALUES (?)", (name,))
        cursor.execute("SELECT id FROM suppliers WHERE supplier_name = ?", (name,))
        row = cursor.fetchone()
        return row["id"] if row else None

    def _status(self, average_score: float) -> str:
        if average_score >= 4.2:
            return "preferred"
        if average_score >= 3.0:
            return "approved"
        return "watchlist"
