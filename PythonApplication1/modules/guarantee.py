"""Guarantee bond and warranty retention logic."""

from __future__ import annotations

from datetime import date, timedelta

from database import get_connection
from modules.fiscal_lock import assert_date_not_locked
from utils.audit import write_audit


class GuaranteeManager:
    def __init__(self):
        self.conn = get_connection()

    def add_bond(self, contract_id: int, bond_type: str, amount: float, bond_number: str = "",
                 issuer: str = "", issue_date: str | None = None, expiry_date: str | None = None,
                 milestone_id: int | None = None, notes: str = "") -> int:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO guarantee_bonds
            (contract_id, milestone_id, bond_type, bond_number, issuer, amount,
             issue_date, expiry_date, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
        """, (
            contract_id, milestone_id, bond_type, bond_number, issuer, float(amount or 0),
            issue_date or date.today().isoformat(), expiry_date, notes,
        ))
        bond_id = cursor.lastrowid
        self.conn.commit()
        write_audit("ADD_GUARANTEE_BOND", "guarantee_bond", bond_id, new_value={
            "contract_id": contract_id, "bond_type": bond_type, "amount": amount,
        })
        return bond_id

    def get_expiring_bonds(self, days_ahead: int = 30) -> list[dict]:
        until = (date.today() + timedelta(days=days_ahead)).isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT gb.*, pc.contract_no, pc.project_id, p.code AS project_code, p.name AS project_name,
                   julianday(gb.expiry_date) - julianday(date('now')) AS days_left
            FROM guarantee_bonds gb
            JOIN project_contracts pc ON pc.id = gb.contract_id
            LEFT JOIN projects p ON p.id = pc.project_id
            WHERE gb.status = 'active'
              AND gb.expiry_date IS NOT NULL
              AND date(gb.expiry_date) <= date(?)
            ORDER BY gb.expiry_date, gb.id
        """, (until,))
        return [dict(row) for row in cursor.fetchall()]

    def get_bond_summary_by_project(self, project_id: int) -> dict:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT gb.bond_type, COUNT(*) AS bond_count, COALESCE(SUM(gb.amount), 0) AS amount
            FROM guarantee_bonds gb
            JOIN project_contracts pc ON pc.id = gb.contract_id
            WHERE pc.project_id = ? AND gb.status = 'active'
            GROUP BY gb.bond_type
            ORDER BY gb.bond_type
        """, (project_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        return {
            "project_id": project_id,
            "total_amount": sum(float(row["amount"] or 0) for row in rows),
            "by_type": rows,
        }

    def release_retention(self, warranty_id: int, released_by: int = 1,
                          release_date: str | None = None) -> int:
        release_date = release_date or date.today().isoformat()
        assert_date_not_locked(release_date, 'giai phong tien bao hanh')
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT wp.*, pc.project_id, pc.contract_no
            FROM warranty_periods wp
            JOIN project_contracts pc ON pc.id = wp.contract_id
            WHERE wp.id = ?
        """, (warranty_id,))
        warranty = cursor.fetchone()
        if not warranty:
            raise ValueError("Khong tim thay ky bao hanh")
        amount = float(warranty["retention_amount"] or 0)
        if amount <= 0:
            raise ValueError("Ky bao hanh khong co tien giu lai")
        cursor.execute("""
            INSERT INTO journal_entries
            (entry_date, description, debit_account, credit_account, amount, project_id,
             reference_type, reference_id, created_by)
            VALUES (?, ?, '338', '112', ?, ?, 'warranty_release', ?, ?)
        """, (
            release_date, f"Giai phong tien giu lai bao hanh HD {warranty['contract_no']}",
            amount, warranty["project_id"], warranty_id, released_by,
        ))
        journal_id = cursor.lastrowid
        cursor.execute("UPDATE warranty_periods SET status = 'released' WHERE id = ?", (warranty_id,))
        self.conn.commit()
        write_audit("RELEASE_WARRANTY_RETENTION", "warranty_period", warranty_id,
                    new_value={"journal_entry_id": journal_id, "amount": amount},
                    actor_id=released_by)
        return journal_id
