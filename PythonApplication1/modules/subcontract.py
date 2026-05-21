"""Subcontractor management and payment tracking."""

from __future__ import annotations

from datetime import date

from database import get_connection


class SubcontractManager:
    """Track subcontractors and payments by project/contract."""

    def __init__(self):
        self.conn = get_connection()

    def add_subcontractor(self, name: str, tax_code: str = "", phone: str = "",
                          email: str = "", address: str = "") -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO subcontractors (name, tax_code, phone, email, address, status)
            VALUES (?, ?, ?, ?, ?, 'active')
        """, (name, tax_code, phone, email, address))
        self.conn.commit()
        return cursor.lastrowid

    def list_subcontractors(self, active_only: bool = True) -> list[dict]:
        cursor = self.conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM subcontractors WHERE status = 'active' ORDER BY name")
        else:
            cursor.execute("SELECT * FROM subcontractors ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]

    def record_payment(self, subcontractor_id: int, amount: float, project_id: int | None = None,
                       contract_id: int | None = None, payment_date: str | None = None,
                       description: str = "", created_by: int = 1, post_journal: bool = True) -> int:
        cursor = self.conn.cursor()
        amount = float(amount or 0)
        if amount <= 0:
            raise ValueError("So tien thanh toan nha thau phu phai lon hon 0")
        journal_id = None
        if post_journal:
            cursor.execute("""
                INSERT INTO journal_entries
                (entry_date, description, debit_account, credit_account, amount,
                 project_id, contract_id, reference_type, created_by)
                VALUES (?, ?, '627', '331', ?, ?, ?, 'subcontract_payment', ?)
            """, (
                payment_date or date.today().isoformat(),
                description or "Ghi nhan chi phi nha thau phu",
                amount, project_id, contract_id, created_by,
            ))
            journal_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO subcontract_payments
            (subcontractor_id, project_id, contract_id, payment_date, amount,
             description, status, journal_entry_id)
            VALUES (?, ?, ?, ?, ?, ?, 'posted', ?)
        """, (
            subcontractor_id, project_id, contract_id,
            payment_date or date.today().isoformat(), amount, description, journal_id,
        ))
        payment_id = cursor.lastrowid
        if journal_id:
            cursor.execute("""
                UPDATE journal_entries
                SET reference_id = ?
                WHERE id = ?
            """, (payment_id, journal_id))
        self.conn.commit()
        return payment_id

    def get_payment_summary(self, project_id: int | None = None) -> list[dict]:
        cursor = self.conn.cursor()
        params = []
        where = ""
        if project_id:
            where = "WHERE sp.project_id = ?"
            params.append(project_id)
        cursor.execute(f"""
            SELECT sc.id AS subcontractor_id, sc.name,
                   COUNT(sp.id) AS payment_count,
                   COALESCE(SUM(sp.amount), 0) AS total_paid
            FROM subcontractors sc
            LEFT JOIN subcontract_payments sp ON sp.subcontractor_id = sc.id
            {where}
            GROUP BY sc.id, sc.name
            ORDER BY total_paid DESC, sc.name
        """, params)
        return [dict(row) for row in cursor.fetchall()]
