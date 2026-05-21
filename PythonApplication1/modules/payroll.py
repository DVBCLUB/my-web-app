"""Payroll and labor cost accounting."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from database import ConnectionPerRequestMixin


class PayrollManager(ConnectionPerRequestMixin):
    """Calculate payroll, statutory deductions and labor cost journals."""

    BHXH_RATE = 0.08
    BHYT_RATE = 0.015
    BHTN_RATE = 0.01
    PERSONAL_DEDUCTION = 11_000_000
    DEPENDENT_DEDUCTION = 4_400_000
    PIT_BRACKETS = (
        (5_000_000, 0.05),
        (5_000_000, 0.10),
        (8_000_000, 0.15),
        (14_000_000, 0.20),
        (20_000_000, 0.25),
        (28_000_000, 0.30),
        (None, 0.35),
    )

    def __init__(self):
        pass

    def add_timesheet(self, employee_id, project_id, work_date, work_days=1,
                      work_item_id=None, quantity_completed=0, daily_rate=0,
                      piece_rate=0, notes=''):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO timesheets
            (employee_id, project_id, work_item_id, work_date, work_days,
             quantity_completed, daily_rate, piece_rate, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (employee_id, project_id, work_item_id, work_date, work_days,
              quantity_completed, daily_rate, piece_rate, notes))
        self.conn.commit()
        return cursor.lastrowid

    def calculate_period(self, payroll_period: str) -> list[dict]:
        start_date = f"{payroll_period}-01"
        end_date = self._period_end(payroll_period)
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT t.employee_id,
                   COALESCE(emp.full_name, 'Chua gan NV') AS employee_name,
                   COALESCE(emp.dependents, 0) AS dependents,
                   t.project_id, COALESCE(p.code, '') AS project_code,
                   COALESCE(p.name, '') AS project_name,
                   SUM(t.work_days) AS work_days,
                   SUM(t.quantity_completed) AS quantity_completed,
                   SUM(t.work_days * t.daily_rate + t.quantity_completed * t.piece_rate) AS gross_amount
            FROM timesheets t
            LEFT JOIN employees emp ON emp.id = t.employee_id
            LEFT JOIN projects p ON p.id = t.project_id
            WHERE t.work_date BETWEEN ? AND ?
            GROUP BY t.employee_id, t.project_id
            ORDER BY p.code, employee_name
        """, (start_date, end_date))
        lines = []
        for row in cursor.fetchall():
            gross = float(row["gross_amount"] or 0)
            insurance = self._employee_insurance(gross)
            pit = self.calculate_pit_progressive(
                gross - sum(insurance.values()) - self.PERSONAL_DEDUCTION
                - float(row["dependents"] or 0) * self.DEPENDENT_DEDUCTION
            )
            lines.append({
                "employee_id": row["employee_id"],
                "employee_name": row["employee_name"],
                "project_id": row["project_id"],
                "project_code": row["project_code"],
                "project_name": row["project_name"],
                "work_days": row["work_days"] or 0,
                "quantity_completed": row["quantity_completed"] or 0,
                "gross_amount": gross,
                "bhxh_employee": insurance["bhxh_employee"],
                "bhyt_employee": insurance["bhyt_employee"],
                "bhtn_employee": insurance["bhtn_employee"],
                "pit_amount": pit,
                "net_amount": gross - sum(insurance.values()) - pit,
            })
        return lines

    def create_payroll_run(self, payroll_period: str) -> int:
        lines = self.calculate_period(payroll_period)
        gross = sum(line["gross_amount"] for line in lines)
        pit = sum(line["pit_amount"] for line in lines)
        insurance = sum(
            line["bhxh_employee"] + line["bhyt_employee"] + line["bhtn_employee"]
            for line in lines
        )
        net = gross - pit - insurance
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO payroll_runs
            (payroll_period, run_date, gross_amount, pit_amount, net_amount, status)
            VALUES (?, ?, ?, ?, ?, 'draft')
            ON CONFLICT(payroll_period) DO UPDATE SET
                run_date = excluded.run_date,
                gross_amount = excluded.gross_amount,
                pit_amount = excluded.pit_amount,
                net_amount = excluded.net_amount,
                status = 'draft'
        """, (payroll_period, date.today().isoformat(), gross, pit, net))
        cursor.execute("SELECT id FROM payroll_runs WHERE payroll_period = ?", (payroll_period,))
        run_id = cursor.fetchone()["id"]
        cursor.execute("DELETE FROM payroll_run_lines WHERE payroll_run_id = ?", (run_id,))
        for line in lines:
            cursor.execute("""
                INSERT INTO payroll_run_lines
                (payroll_run_id, employee_id, project_id, work_days, quantity_completed,
                 gross_amount, pit_amount, net_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (run_id, line["employee_id"], line["project_id"], line["work_days"],
                  line["quantity_completed"], line["gross_amount"], line["pit_amount"], line["net_amount"]))
        self._sync_payroll_period(cursor, payroll_period, run_id, lines)
        self.conn.commit()
        return run_id

    def approve_period(self, payroll_period_id: int, approved_by: int = 1) -> None:
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE payroll_periods
            SET status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (approved_by, payroll_period_id))
        self.conn.commit()

    def get_payroll_by_project(self, project_id: int, payroll_period: str) -> list[dict]:
        self.create_payroll_run(payroll_period)
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT pl.*, e.full_name AS employee_name
            FROM payroll_lines pl
            JOIN payroll_periods pp ON pp.id = pl.payroll_period_id
            LEFT JOIN employees e ON e.id = pl.employee_id
            WHERE pl.project_id = ? AND pp.period = ?
            ORDER BY e.full_name
        """, (project_id, payroll_period))
        return [dict(row) for row in cursor.fetchall()]

    def export_payroll_excel(self, payroll_period: str, output_path: str) -> str:
        lines = self.calculate_period(payroll_period)
        try:
            from openpyxl import Workbook
        except ImportError as exc:
            raise RuntimeError("Can cai openpyxl de xuat Excel bang luong") from exc

        wb = Workbook()
        ws = wb.active
        ws.title = "Bang luong"
        headers = [
            "Nhan vien", "Du an", "Ngay cong", "San luong", "Luong gross",
            "BHXH", "BHYT", "BHTN", "TNCN", "Thuc linh",
        ]
        ws.append(headers)
        for line in lines:
            ws.append([
                line["employee_name"], line["project_code"], line["work_days"],
                line["quantity_completed"], line["gross_amount"],
                line["bhxh_employee"], line["bhyt_employee"], line["bhtn_employee"],
                line["pit_amount"], line["net_amount"],
            ])
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        wb.save(output)
        return str(output)

    def post_payroll_journal(self, payroll_period, created_by=1):
        self.create_payroll_run(payroll_period)
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM payroll_runs WHERE payroll_period = ?", (payroll_period,))
        run = cursor.fetchone()
        if not run:
            raise ValueError("Khong tim thay bang luong")
        if run["journal_entry_id"]:
            return run["journal_entry_id"]
        entry_date = self._period_end(payroll_period)
        cursor.execute("""
            INSERT INTO journal_entries
            (entry_date, fiscal_period, description, debit_account, credit_account,
             amount, reference_type, reference_id, created_by)
            VALUES (?, ?, ?, '622', '334', ?, 'payroll', ?, ?)
        """, (entry_date, payroll_period, f"Ket chuyen chi phi nhan cong {payroll_period}",
              run["gross_amount"], run["id"], created_by))
        journal_id = cursor.lastrowid
        cursor.execute("""
            UPDATE payroll_runs
            SET journal_entry_id = ?, status = 'posted'
            WHERE id = ?
        """, (journal_id, run["id"]))
        self.conn.commit()
        return journal_id

    def display_payroll_summary(self, parent):
        period = date.today().strftime("%Y-%m")
        lines = self.calculate_period(period)
        header = tk.Frame(parent, bg="#FFFFFF")
        header.pack(fill="x", padx=10, pady=8)
        tk.Label(header, text=f"Bang luong tam tinh ky {period}", bg="#FFFFFF",
                 fg="#17324D", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        cols = ("Nhan vien", "DA", "Ngay cong", "San luong", "Gross", "BH", "TNCN", "Net")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for col, width in zip(cols, (180, 80, 90, 90, 120, 100, 100, 120)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        for line in lines:
            insurance = line["bhxh_employee"] + line["bhyt_employee"] + line["bhtn_employee"]
            tree.insert("", "end", values=(
                line["employee_name"], line["project_code"], f"{line['work_days']:,.2f}",
                f"{line['quantity_completed']:,.2f}", f"{line['gross_amount']:,.0f}",
                f"{insurance:,.0f}", f"{line['pit_amount']:,.0f}", f"{line['net_amount']:,.0f}",
            ))
        tree.pack(fill="both", expand=True, padx=10, pady=8)

    def calculate_pit_progressive(self, taxable_income: float) -> float:
        remaining = max(float(taxable_income or 0), 0)
        tax = 0.0
        for bracket_amount, rate in self.PIT_BRACKETS:
            if remaining <= 0:
                break
            portion = remaining if bracket_amount is None else min(remaining, bracket_amount)
            tax += portion * rate
            remaining -= portion
        return round(tax, 0)

    def _employee_insurance(self, gross: float) -> dict[str, float]:
        gross = max(float(gross or 0), 0)
        return {
            "bhxh_employee": round(gross * self.BHXH_RATE, 0),
            "bhyt_employee": round(gross * self.BHYT_RATE, 0),
            "bhtn_employee": round(gross * self.BHTN_RATE, 0),
        }

    def _sync_payroll_period(self, cursor, payroll_period: str, run_id: int, lines: list[dict]) -> None:
        start_date = f"{payroll_period}-01"
        end_date = self._period_end(payroll_period)
        gross = sum(line["gross_amount"] for line in lines)
        pit = sum(line["pit_amount"] for line in lines)
        insurance = sum(
            line["bhxh_employee"] + line["bhyt_employee"] + line["bhtn_employee"]
            for line in lines
        )
        net = gross - pit - insurance
        cursor.execute("""
            INSERT INTO payroll_periods
            (period, start_date, end_date, gross_amount, insurance_amount, pit_amount,
             net_amount, status, payroll_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?)
            ON CONFLICT(period) DO UPDATE SET
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                gross_amount = excluded.gross_amount,
                insurance_amount = excluded.insurance_amount,
                pit_amount = excluded.pit_amount,
                net_amount = excluded.net_amount,
                payroll_run_id = excluded.payroll_run_id,
                status = CASE WHEN payroll_periods.status = 'approved' THEN 'approved' ELSE 'draft' END
        """, (payroll_period, start_date, end_date, gross, insurance, pit, net, run_id))
        cursor.execute("SELECT id FROM payroll_periods WHERE period = ?", (payroll_period,))
        period_id = cursor.fetchone()["id"]
        cursor.execute("DELETE FROM payroll_lines WHERE payroll_period_id = ?", (period_id,))
        for line in lines:
            cursor.execute("""
                INSERT INTO payroll_lines
                (payroll_period_id, employee_id, project_id, work_days, quantity_completed,
                 gross_amount, bhxh_employee, bhyt_employee, bhtn_employee, pit_amount, net_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                period_id, line["employee_id"], line["project_id"], line["work_days"],
                line["quantity_completed"], line["gross_amount"], line["bhxh_employee"],
                line["bhyt_employee"], line["bhtn_employee"], line["pit_amount"], line["net_amount"],
            ))

    def _period_end(self, payroll_period):
        start = datetime.strptime(f"{payroll_period}-01", "%Y-%m-%d").date()
        if start.month == 12:
            nxt = start.replace(year=start.year + 1, month=1)
        else:
            nxt = start.replace(month=start.month + 1)
        return (nxt - timedelta(days=1)).isoformat()
