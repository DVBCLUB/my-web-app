"""Foreign currency transaction helpers."""

from __future__ import annotations

from datetime import date

from database import get_connection
from modules.fiscal_lock import assert_date_not_locked
from utils.audit import write_audit


class CurrencyManager:
    def __init__(self):
        self.conn = get_connection()

    def set_rate(self, currency: str, rate_date: str, exchange_rate: float,
                 source: str = "manual") -> None:
        if float(exchange_rate or 0) <= 0:
            raise ValueError("Ty gia phai lon hon 0")
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO currency_rates (currency, rate_date, exchange_rate, source)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(currency, rate_date) DO UPDATE SET
                exchange_rate = excluded.exchange_rate,
                source = excluded.source
        """, (currency.upper(), rate_date, float(exchange_rate), source))
        self.conn.commit()

    def get_rate(self, currency: str, rate_date: str | None = None) -> float:
        currency = currency.upper()
        rate_date = rate_date or date.today().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT exchange_rate
            FROM currency_rates
            WHERE currency = ? AND date(rate_date) <= date(?)
            ORDER BY rate_date DESC
            LIMIT 1
        """, (currency, rate_date))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Chua co ty gia {currency} den ngay {rate_date}")
        return float(row["exchange_rate"])

    def record_foreign_transaction(self, transaction_type: str, reference_id: int | None,
                                   currency: str, foreign_amount: float,
                                   transaction_date: str | None = None,
                                   exchange_rate: float | None = None) -> int:
        transaction_date = transaction_date or date.today().isoformat()
        assert_date_not_locked(transaction_date, 'ghi giao dich ngoai te')
        exchange_rate = float(exchange_rate or self.get_rate(currency, transaction_date))
        local_amount = float(foreign_amount or 0) * exchange_rate
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO foreign_currency_transactions
            (transaction_type, reference_id, currency, foreign_amount, exchange_rate,
             local_amount, transaction_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            transaction_type, reference_id, currency.upper(), float(foreign_amount or 0),
            exchange_rate, local_amount, transaction_date,
        ))
        txn_id = cursor.lastrowid
        self.conn.commit()
        write_audit("RECORD_FOREIGN_CURRENCY", "foreign_currency_transaction", txn_id,
                    new_value={"currency": currency.upper(), "local_amount": local_amount})
        return txn_id

    def get_currency_exposure(self, currency: str | None = None) -> list[dict]:
        cursor = self.conn.cursor()
        params = []
        where = ""
        if currency:
            where = "WHERE currency = ?"
            params.append(currency.upper())
        cursor.execute(f"""
            SELECT currency,
                   SUM(foreign_amount) AS foreign_balance,
                   SUM(local_amount) AS local_balance,
                   AVG(exchange_rate) AS average_rate
            FROM foreign_currency_transactions
            {where}
            GROUP BY currency
            ORDER BY currency
        """, params)
        return [dict(row) for row in cursor.fetchall()]

    def create_revaluation_entry(self, currency: str, revaluation_date: str,
                                 new_rate: float, created_by: int = 1) -> int | None:
        assert_date_not_locked(revaluation_date, 'danh gia lai ngoai te')
        exposure = next((row for row in self.get_currency_exposure(currency)), None)
        if not exposure:
            return None
        foreign_balance = float(exposure["foreign_balance"] or 0)
        old_local = float(exposure["local_balance"] or 0)
        new_local = foreign_balance * float(new_rate or 0)
        diff = new_local - old_local
        if abs(diff) < 0.01:
            return None
        debit, credit = ("413", "515") if diff > 0 else ("635", "413")
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO journal_entries
            (entry_date, description, debit_account, credit_account, amount,
             reference_type, created_by)
            VALUES (?, ?, ?, ?, ?, 'fx_revaluation', ?)
        """, (
            revaluation_date, f"Danh gia lai chen lech ty gia {currency.upper()}",
            debit, credit, abs(diff), created_by,
        ))
        journal_id = cursor.lastrowid
        self.conn.commit()
        return journal_id
