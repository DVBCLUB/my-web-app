"""Centralized business alert aggregation."""

from __future__ import annotations

from database import get_connection


class NotificationCenter:
    def __init__(self):
        self.conn = get_connection()

    def get_all_alerts(self, user_id: int | None = None) -> list[dict]:
        alerts = []
        alerts.extend(self._advance_alerts())
        alerts.extend(self._expiring_items())
        alerts.extend(self._expiring_bonds())
        alerts.extend(self._low_stock())
        alerts.extend(self._budget_alerts())
        alerts.extend(self._ar_ap_overdue())
        priority_order = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda item: (priority_order.get(item["priority"], 9), item.get("due_date") or "9999-12-31"))
        return alerts

    def get_badge_counts(self, user_id: int | None = None) -> dict:
        counts = {"critical": 0, "warning": 0, "info": 0, "total": 0}
        for alert in self.get_all_alerts(user_id):
            counts[alert["priority"]] = counts.get(alert["priority"], 0) + 1
            counts["total"] += 1
        return counts

    def _advance_alerts(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, advance_number, deadline,
                   julianday(deadline) - julianday(date('now')) AS days_left
            FROM advance_requests
            WHERE status NOT IN ('settled', 'cancelled')
              AND deadline IS NOT NULL
              AND date(deadline) <= date('now', '+7 days')
        """)
        rows = []
        for row in cursor.fetchall():
            days_left = int(row["days_left"] or 0)
            rows.append({
                "source": "advance",
                "priority": "critical" if days_left < 0 else "warning",
                "title": f"Tam ung {row['advance_number']} sap/da qua han",
                "message": f"Con {days_left} ngay den deadline quyet toan",
                "due_date": row["deadline"],
                "entity_id": row["id"],
            })
        return rows

    def _expiring_items(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, item_type, item_name, expiry_date,
                   julianday(expiry_date) - julianday(date('now')) AS days_left
            FROM expiring_items
            WHERE status = 'active'
              AND date(expiry_date) <= date('now', '+30 days')
        """)
        return [{
            "source": "expiring_item",
            "priority": "critical" if float(row["days_left"] or 0) < 0 else "warning",
            "title": f"{row['item_type']}: {row['item_name']}",
            "message": "Ho so/giay phep sap het han",
            "due_date": row["expiry_date"],
            "entity_id": row["id"],
        } for row in cursor.fetchall()]

    def _expiring_bonds(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, bond_type, bond_number, expiry_date,
                   julianday(expiry_date) - julianday(date('now')) AS days_left
            FROM guarantee_bonds
            WHERE status = 'active'
              AND expiry_date IS NOT NULL
              AND date(expiry_date) <= date('now', '+30 days')
        """)
        return [{
            "source": "guarantee_bond",
            "priority": "critical" if float(row["days_left"] or 0) < 0 else "warning",
            "title": f"Bao lanh {row['bond_type']} {row['bond_number'] or ''}".strip(),
            "message": "Bao lanh sap het han",
            "due_date": row["expiry_date"],
            "entity_id": row["id"],
        } for row in cursor.fetchall()]

    def _low_stock(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, code, name, quantity, min_quantity
            FROM materials
            WHERE status = 'active'
              AND COALESCE(min_quantity, 0) > 0
              AND COALESCE(quantity, 0) <= COALESCE(min_quantity, 0)
        """)
        return [{
            "source": "materials",
            "priority": "warning",
            "title": f"Vat tu duoi ton toi thieu: {row['code']}",
            "message": f"{row['name']} con {row['quantity']} / nguong {row['min_quantity']}",
            "due_date": None,
            "entity_id": row["id"],
        } for row in cursor.fetchall()]

    def _budget_alerts(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT p.id, p.code, p.name, p.budget, COALESCE(SUM(e.amount), 0) AS actual
            FROM projects p
            LEFT JOIN expenses e ON e.project_id = p.id
            WHERE COALESCE(p.budget, 0) > 0
            GROUP BY p.id
            HAVING actual > p.budget * 0.9
        """)
        return [{
            "source": "budget",
            "priority": "critical" if float(row["actual"] or 0) > float(row["budget"] or 0) else "warning",
            "title": f"Ngan sach du an {row['code']} sap/vuot nguong",
            "message": f"Da dung {float(row['actual'] or 0) / float(row['budget'] or 1) * 100:.1f}% ngan sach",
            "due_date": None,
            "entity_id": row["id"],
        } for row in cursor.fetchall()]

    def _ar_ap_overdue(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, partner_type, partner_name, due_date, amount, paid_amount
            FROM ar_ap_items
            WHERE status = 'open'
              AND date(due_date) < date('now')
              AND COALESCE(paid_amount, 0) < COALESCE(amount, 0)
        """)
        return [{
            "source": "ar_ap",
            "priority": "critical",
            "title": f"Cong no qua han: {row['partner_name']}",
            "message": f"{row['partner_type']} con {float(row['amount'] or 0) - float(row['paid_amount'] or 0):,.0f}",
            "due_date": row["due_date"],
            "entity_id": row["id"],
        } for row in cursor.fetchall()]
