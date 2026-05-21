"""Fiscal period lock helpers."""

from datetime import datetime

from database import get_connection


class FiscalPeriodLockManager:
    def __init__(self):
        self.conn = get_connection()

    def list_periods(self, year=None):
        cursor = self.conn.cursor()
        params = []
        query = """
            SELECT fiscal_year, fiscal_period, period_start, period_end,
                   CASE WHEN COALESCE(is_locked, 0) = 1 OR COALESCE(is_closed, 0) = 1
                        THEN 1 ELSE 0 END AS is_locked,
                   locked_at, locked_by
            FROM fiscal_calendar
            WHERE 1=1
        """
        if year:
            query += " AND fiscal_year = ?"
            params.append(year)
        query += " ORDER BY fiscal_period DESC"
        cursor.execute(query, params)
        return cursor.fetchall()

    def set_locked(self, fiscal_period, locked=True, user_id=None):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE fiscal_calendar
            SET is_locked = ?, is_closed = ?,
                locked_at = CASE WHEN ? = 1 THEN ? ELSE NULL END,
                locked_by = CASE WHEN ? = 1 THEN ? ELSE NULL END
            WHERE fiscal_period = ?
        """, (
            int(locked), int(locked), int(locked), datetime.now().isoformat(timespec="seconds"),
            int(locked), user_id, fiscal_period,
        ))
        self.conn.commit()
        return cursor.rowcount

    def is_date_locked(self, entry_date):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 1 FROM fiscal_calendar
            WHERE ? BETWEEN period_start AND period_end
              AND (COALESCE(is_locked, 0) = 1 OR COALESCE(is_closed, 0) = 1)
        """, (entry_date,))
        return cursor.fetchone() is not None


def assert_date_not_locked(entry_date, action='ghi so'):
    """Chan thao tac ghi du lieu vao ky ke toan da khoa."""
    if not entry_date:
        return
    entry_date = str(entry_date)[:10]
    if FiscalPeriodLockManager().is_date_locked(entry_date):
        raise ValueError(f"Ky {entry_date[:7]} da khoa so. Khong the {action}.")
