"""Cash flow forecast and liquidity alerts."""

from datetime import date, timedelta

from database import get_connection


class CashFlowAlertManager:
    """Forecast 30/60/90 day cash flow from contracts, billings and expenses."""

    def __init__(self):
        self.conn = get_connection()

    def get_forecast(self, horizon_days=90):
        today = date.today()
        end = today + timedelta(days=horizon_days)
        opening = self._opening_cash_balance()
        min_balance = self._minimum_cash_balance()
        events = []
        events.extend(self._future_customer_inflows(today, end))
        events.extend(self._future_subcontract_outflows(today, end))
        events.extend(self._projected_operating_outflows(today, end))
        events.sort(key=lambda item: item["date"])

        running = opening
        for event in events:
            running += event["amount"]
            event["projected_balance"] = running
            event["alert"] = running < min_balance

        buckets = {}
        for days in (30, 60, 90):
            bucket_end = today + timedelta(days=days)
            balance = opening + sum(e["amount"] for e in events if e["date"] <= bucket_end.isoformat())
            buckets[days] = {
                "balance": balance,
                "below_minimum": balance < min_balance,
                "net_flow": balance - opening,
            }
        return {
            "opening_balance": opening,
            "minimum_balance": min_balance,
            "events": events,
            "buckets": buckets,
        }

    def display_cash_flow_alerts(self, parent):
        import tkinter as tk
        from tkinter import ttk

        data = self.get_forecast()
        summary = tk.Frame(parent, bg="#FFFFFF")
        summary.pack(fill="x", padx=10, pady=8)
        parts = [f"Số dư hiện tại: {data['opening_balance']:,.0f}", f"Ngưỡng: {data['minimum_balance']:,.0f}"]
        for days, bucket in data["buckets"].items():
            marker = "CẢNH BÁO" if bucket["below_minimum"] else "OK"
            parts.append(f"{days} ngày: {bucket['balance']:,.0f} ({marker})")
        tk.Label(summary, text="    ".join(parts), bg="#FFFFFF", fg="#17324D",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")

        cols = ("Ngày", "Loại", "Dự án/HĐ", "Diễn giải", "Thu/Chi", "Số dư dự kiến", "Cảnh báo")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=15)
        for col, width in zip(cols, (90, 100, 160, 260, 120, 130, 90)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        for event in data["events"]:
            tree.insert("", "end", values=(
                event["date"], event["type"], event["project"], event["description"],
                f"{event['amount']:,.0f}", f"{event['projected_balance']:,.0f}",
                "Dưới ngưỡng" if event["alert"] else "",
            ))
        tree.pack(fill="both", expand=True, padx=10, pady=8)

    def _future_customer_inflows(self, today, end):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT b.billing_date, p.code, c.contract_no, b.milestone_name, b.net_amount
            FROM contract_billings b
            JOIN project_contracts c ON c.id = b.contract_id
            JOIN projects p ON p.id = c.project_id
            WHERE c.contract_type = 'customer'
              AND date(b.billing_date) BETWEEN date(?) AND date(?)
              AND b.status IN ('draft', 'approved')
        """, (today.isoformat(), end.isoformat()))
        return [{
            "date": row["billing_date"],
            "type": "Thu",
            "project": f"{row['code']} / {row['contract_no']}",
            "description": row["milestone_name"] or "Thu theo hợp đồng",
            "amount": float(row["net_amount"] or 0),
        } for row in cursor.fetchall()]

    def _future_subcontract_outflows(self, today, end):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT b.billing_date, p.code, c.contract_no, b.milestone_name, b.net_amount
            FROM contract_billings b
            JOIN project_contracts c ON c.id = b.contract_id
            JOIN projects p ON p.id = c.project_id
            WHERE c.contract_type IN ('subcontract', 'supplier')
              AND date(b.billing_date) BETWEEN date(?) AND date(?)
              AND b.status IN ('draft', 'approved')
        """, (today.isoformat(), end.isoformat()))
        return [{
            "date": row["billing_date"],
            "type": "Chi",
            "project": f"{row['code']} / {row['contract_no']}",
            "description": row["milestone_name"] or "Thanh toán nhà thầu phụ",
            "amount": -float(row["net_amount"] or 0),
        } for row in cursor.fetchall()]

    def _projected_operating_outflows(self, today, end):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COALESCE(AVG(monthly_total), 0)
            FROM (
                SELECT strftime('%Y-%m', expense_date) AS month, SUM(amount) AS monthly_total
                FROM expenses
                WHERE date(expense_date) >= date(?, '-180 days')
                  AND date(expense_date) < date(?)
                GROUP BY strftime('%Y-%m', expense_date)
            )
        """, (today.isoformat(), today.isoformat()))
        monthly_avg = float(cursor.fetchone()[0] or 0)
        daily = monthly_avg / 30 if monthly_avg else 0
        events = []
        cursor_date = today + timedelta(days=30)
        while cursor_date <= end:
            amount = -daily * 30
            if amount:
                events.append({
                    "date": cursor_date.isoformat(),
                    "type": "Chi du bao",
                    "project": "Van hanh",
                    "description": "Du bao chi phi binh quan 6 thang",
                    "amount": amount,
                })
            cursor_date += timedelta(days=30)
        return events

    def _opening_cash_balance(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = 'cash_opening_balance'")
        row = cursor.fetchone()
        return float(row["value"] or 0) if row and row["value"] else 0.0

    def _minimum_cash_balance(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = 'cash_minimum_balance'")
        row = cursor.fetchone()
        return float(row["value"] or 0) if row and row["value"] else 0.0
