"""Advance request workflow and deadline alerts."""

from datetime import date, datetime, timedelta
import json

from database import get_connection


class AdvanceWorkflowManager:
    """Manage BĐH advance -> signature check -> accounting -> settlement alerts."""

    def __init__(self):
        self.conn = get_connection()

    def create_advance_request(self, advance_number, requester_id, project_id,
                               request_date, amount, purpose='', notes=''):
        received_date = self._to_date(request_date) or date.today()
        deadline = received_date + timedelta(days=15)
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO advance_requests
            (advance_number, requester_id, project_id, request_date, received_date,
             amount, purpose, deadline, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted')
        ''', (
            advance_number, requester_id, project_id, received_date.isoformat(),
            received_date.isoformat(), amount, purpose, deadline.isoformat(), notes
        ))
        self.conn.commit()
        return cursor.lastrowid

    def mark_signature(self, advance_id, role, signed=True):
        columns = {
            'requester': 'has_requester_signature',
            'department': 'has_department_signature',
            'accounting': 'has_accounting_signature',
            'director': 'has_director_signature',
        }
        column = columns.get(role)
        if not column:
            raise ValueError('Vai trò ký không hợp lệ')
        cursor = self.conn.cursor()
        cursor.execute(f'UPDATE advance_requests SET {column} = ? WHERE id = ?', (1 if signed else 0, advance_id))
        self.conn.commit()

    def transfer_to_accounting_if_ready(self, advance_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM advance_requests WHERE id = ?', (advance_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError('Không tìm thấy hồ sơ tạm ứng')
        required = [
            row['has_requester_signature'],
            row['has_department_signature'],
            row['has_accounting_signature'],
            row['has_director_signature'],
        ]
        if not all(required):
            return False
        cursor.execute('''
            UPDATE advance_requests
            SET status = 'accounting', transferred_to_accounting_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (advance_id,))
        self.conn.commit()
        return True

    def get_deadline_alerts(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT ar.id, ar.advance_number, COALESCE(e.full_name, '') AS requester,
                   ar.amount, ar.received_date, ar.deadline, ar.status,
                   COALESCE(SUM(sel.amount), 0) AS settled_expense_total,
                   julianday(ar.deadline) - julianday(date('now')) AS days_left
            FROM advance_requests ar
            LEFT JOIN employees e ON e.id = ar.requester_id
            LEFT JOIN advance_settlements ast ON ast.advance_id = ar.id
            LEFT JOIN settlement_expense_links sel ON sel.settlement_id = ast.id
            WHERE ar.status NOT IN ('settled', 'cancelled')
            GROUP BY ar.id
            ORDER BY ar.deadline ASC
        ''')
        warning = []
        overdue = []
        medium = []
        for row in cursor.fetchall():
            item = dict(row)
            days_left = int(item['days_left'] or 0)
            item['days_left'] = days_left
            item['missing_expenses'] = max(float(item['amount'] or 0) - float(item['settled_expense_total'] or 0), 0)
            if days_left < 0:
                item['alert_level'] = 'overdue'
                overdue.append(item)
            elif days_left <= 3:
                item['alert_level'] = 'warning'
                warning.append(item)
            elif days_left <= 7:
                item['alert_level'] = 'medium'
                medium.append(item)
        return {'warning': warning, 'overdue': overdue, 'medium': medium, 'all': overdue + warning + medium}

    def settle_advance(self, advance_id, settlement_data, expense_ids, settled_by=None):
        """Quyết toán tạm ứng và liên kết các chi phí thực tế trong một giao dịch."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM advance_requests WHERE id = ?', (advance_id,))
        advance = cursor.fetchone()
        if not advance:
            raise ValueError('Không tìm thấy hồ sơ tạm ứng')

        clean_expense_ids = [int(x) for x in (expense_ids or []) if x]
        settled_total = 0.0
        expenses = []
        if clean_expense_ids:
            placeholders = ','.join('?' for _ in clean_expense_ids)
            cursor.execute(f'SELECT id, amount FROM expenses WHERE id IN ({placeholders})', clean_expense_ids)
            expenses = cursor.fetchall()
            settled_total = sum(float(row['amount'] or 0) for row in expenses)

        advance_amount = float(advance['amount'] or 0)
        returned_to_fund = max(advance_amount - settled_total, 0)
        overspend_amount = max(settled_total - advance_amount, 0)
        if overspend_amount > 0:
            settlement_type = 'overspend'
        elif returned_to_fund > 0:
            settlement_type = 'return'
        else:
            settlement_type = 'normal'

        settlement_number = settlement_data.get('settlement_number') or f"HU-{date.today().strftime('%Y%m%d')}-{advance_id}"
        settlement_date = settlement_data.get('settlement_date') or date.today().isoformat()
        notes = settlement_data.get('notes', '')

        cursor.execute('''
            INSERT INTO advance_settlements
            (advance_id, settlement_number, settlement_date, amount,
             settled_expense_total, returned_to_fund, overspend_amount,
             settlement_type, approved_by, approved_at, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'approved', ?)
        ''', (
            advance_id, settlement_number, settlement_date, advance_amount,
            settled_total, returned_to_fund, overspend_amount,
            settlement_type, settled_by, notes
        ))
        settlement_id = cursor.lastrowid

        for row in expenses:
            cursor.execute('''
                INSERT OR IGNORE INTO settlement_expense_links
                (settlement_id, expense_id, amount)
                VALUES (?, ?, ?)
            ''', (settlement_id, row['id'], row['amount'] or 0))
            cursor.execute('UPDATE expenses SET advance_request_id = ? WHERE id = ?', (advance_id, row['id']))

        cursor.execute("UPDATE advance_requests SET status = 'settled' WHERE id = ?", (advance_id,))
        self._auto_create_clearing_journal_entry(
            cursor, advance, settlement_id, settlement_date, settled_total,
            returned_to_fund, overspend_amount, settled_by
        )
        self._write_audit(cursor, 'advance_settlement', settlement_id, 'settle', None, {
            'advance_id': advance_id,
            'settled_total': settled_total,
            'returned_to_fund': returned_to_fund,
            'overspend_amount': overspend_amount,
        }, settled_by)
        self.conn.commit()
        return {
            'settlement_id': settlement_id,
            'settlement_number': settlement_number,
            'settled_expense_total': settled_total,
            'returned_to_fund': returned_to_fund,
            'overspend_amount': overspend_amount,
            'settlement_type': settlement_type,
        }

    def get_uncovered_advances_report(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT ar.id, ar.advance_number, COALESCE(e.full_name, '') AS requester,
                   COALESCE(p.name, '') AS project_name, ar.amount,
                   COALESCE(SUM(sel.amount), 0) AS settled_expense_total,
                   ar.deadline, ar.status
            FROM advance_requests ar
            LEFT JOIN employees e ON e.id = ar.requester_id
            LEFT JOIN projects p ON p.id = ar.project_id
            LEFT JOIN advance_settlements ast ON ast.advance_id = ar.id
            LEFT JOIN settlement_expense_links sel ON sel.settlement_id = ast.id
            GROUP BY ar.id
            HAVING ar.amount > COALESCE(SUM(sel.amount), 0)
            ORDER BY ar.deadline ASC
        ''')
        rows = []
        for row in cursor.fetchall():
            item = dict(row)
            item['uncovered_amount'] = float(item['amount'] or 0) - float(item['settled_expense_total'] or 0)
            rows.append(item)
        return rows

    def _auto_create_clearing_journal_entry(self, cursor, advance, settlement_id,
                                            entry_date, settled_total, returned_to_fund,
                                            overspend_amount, actor_id=None):
        fiscal_period = str(entry_date)[:7]
        fiscal_year = int(fiscal_period[:4]) if len(fiscal_period) >= 4 else date.today().year
        entry_number = f"HU-{date.today().strftime('%Y%m%d')}-{settlement_id}"
        entries = []
        if settled_total:
            entries.append(('627', '141', settled_total, 'Kết chuyển chi phí hoàn ứng'))
        if returned_to_fund:
            entries.append(('111', '141', returned_to_fund, 'Thu lại tiền tạm ứng thừa'))
        if overspend_amount:
            entries.append(('141', '111', overspend_amount, 'Chi thêm phần vượt tạm ứng'))
        for idx, (debit, credit, amount, desc) in enumerate(entries, start=1):
            cursor.execute('''
                INSERT INTO journal_entries
                (entry_number, entry_date, fiscal_year, fiscal_period, entry_type,
                 description, debit_account, credit_account, amount, project_id,
                 reference_type, reference_id, created_by, posted_by, posted_at)
                VALUES (?, ?, ?, ?, 'advance_settlement', ?, ?, ?, ?, ?, 'advance_settlement', ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                f'{entry_number}-{idx}', entry_date, fiscal_year, fiscal_period, desc,
                debit, credit, amount, advance['project_id'], settlement_id, actor_id, actor_id
            ))

    def _write_audit(self, cursor, entity_type, entity_id, action, old_value, new_value, actor_id=None):
        cursor.execute('''
            INSERT INTO audit_log (entity_type, entity_id, action, old_value, new_value, actor_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            entity_type, entity_id, action,
            json.dumps(old_value, ensure_ascii=False) if old_value is not None else None,
            json.dumps(new_value, ensure_ascii=False) if new_value is not None else None,
            actor_id,
        ))

    def _to_date(self, value):
        if isinstance(value, date):
            return value
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                return datetime.strptime(str(value), fmt).date()
            except ValueError:
                continue
        return None
