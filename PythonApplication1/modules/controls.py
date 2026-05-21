"""Accounting controls and extension reports."""

from datetime import date, datetime, timedelta
import json
import sqlite3

from database import get_connection


class AuditLogManager:
    """Audit trail for write, read and export actions."""

    def __init__(self):
        pass

    def validate_balanced_entry(self, entry_id):
        """Ensure total debit equals total credit before treating an entry as valid."""
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COALESCE(SUM(debit_amount), 0) AS debit_total,
                       COALESCE(SUM(credit_amount), 0) AS credit_total,
                       COUNT(*) AS line_count
                FROM journal_entry_lines
                WHERE journal_entry_id = ?
            ''', (entry_id,))
            row = cursor.fetchone()
            if not row or row['line_count'] == 0:
                cursor.execute('SELECT COALESCE(amount, 0) AS amount FROM journal_entries WHERE id = ?', (entry_id,))
                entry = cursor.fetchone()
                if not entry:
                    raise ValueError('Khong tim thay but toan.')
                if float(entry['amount'] or 0) <= 0:
                    raise ValueError('But toan khong hop le: so tien phai lon hon 0.')
                return True
            debit_total = float(row['debit_total'] or 0)
            credit_total = float(row['credit_total'] or 0)
            if abs(debit_total - credit_total) > 0.01:
                raise ValueError(
                    f"But toan khong can: No {debit_total:,.0f} <> Co {credit_total:,.0f}."
                )
            return True
        finally:
            conn.close()

    def log(self, entity_type, entity_id=None, action='READ', actor_id=None, old_value=None, new_value=None):
        payload = new_value
        if isinstance(payload, (dict, list, tuple)):
            payload = json.dumps(payload, ensure_ascii=False, default=str)
        old_payload = old_value
        if isinstance(old_payload, (dict, list, tuple)):
            old_payload = json.dumps(old_payload, ensure_ascii=False, default=str)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO audit_log (entity_type, entity_id, action, old_value, new_value, actor_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (entity_type, entity_id, action, old_payload, payload, actor_id))
            conn.commit()
        finally:
            conn.close()

    def read_report(self, limit=200, action=None, offset=0, start_date=None, end_date=None, actor_id=None,
                    entity_type=None, search_text=None):
        conn = get_connection()
        try:
            cursor = conn.cursor()
            params = []
            query = '''
                SELECT created_at, COALESCE(actor_id, '') AS actor_id, action,
                       entity_type, COALESCE(entity_id, '') AS entity_id, COALESCE(new_value, '') AS detail,
                       COALESCE(old_value, '') AS old_value
                FROM audit_log
                WHERE action IN ('READ', 'EXPORT', 'VIEW_REPORT', 'POSTED', 'POST_BLOCKED', 'POST_CANCELLED', 'APPROVAL_BLOCKED')
            '''
            if action and action != 'all':
                query += ' AND action = ?'
                params.append(action)
            if start_date:
                query += ' AND date(created_at) >= date(?)'
                params.append(start_date)
            if end_date:
                query += ' AND date(created_at) <= date(?)'
                params.append(end_date)
            if actor_id:
                query += ' AND lower(COALESCE(actor_id, '')) LIKE lower(?)'
                params.append(f'%{actor_id}%')
            if entity_type and entity_type != 'all':
                query += ' AND lower(entity_type) = lower(?)'
                params.append(entity_type)
            if search_text:
                query += ' AND lower(COALESCE(entity_type, '') || " " || COALESCE(entity_id, '') || " " || COALESCE(new_value, '') || " " || COALESCE(old_value, '')) LIKE lower(?)'
                params.append(f'%{search_text}%')
            query += '''
                ORDER BY id DESC
                LIMIT ? OFFSET ?
            '''
            params.append(limit)
            params.append(offset)
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            conn.close()


class ApprovalThresholdManager:
    DEFAULTS = (
        ('employee', 500000, 0),
        ('accountant', 500000, 0),
        ('kế toán', 500000, 0),
        ('manager', 5000000, 1),
        ('quản lý', 5000000, 1),
        ('admin', 999999999999, 1),
        ('quản trị viên', 999999999999, 1),
        ('director', 999999999999, 1),
        ('giám đốc', 999999999999, 1),
    )

    def __init__(self):
        self.conn = get_connection()
        self.ensure_defaults()

    def ensure_defaults(self):
        cursor = self.conn.cursor()
        for role, max_amount, final in self.DEFAULTS:
            cursor.execute('''
                INSERT OR IGNORE INTO approval_thresholds (role, max_amount, can_final_approve)
                VALUES (?, ?, ?)
            ''', (role, max_amount, final))
        self.conn.commit()

    def can_approve(self, role, amount):
        role = (role or 'employee').strip().lower()
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT max_amount, can_final_approve
            FROM approval_thresholds
            WHERE role = ? AND active = 1
        ''', (role,))
        row = cursor.fetchone()
        if not row:
            return False, f"Role {role} chưa có hạn mức phê duyệt."
        if float(amount or 0) > float(row['max_amount'] or 0):
            return False, f"Khoản chi {amount:,.0f} vượt hạn mức {row['max_amount']:,.0f} của role {role}."
        return True, "Trong hạn mức phê duyệt."

    def list_thresholds(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT role, max_amount, can_final_approve, active
            FROM approval_thresholds
            ORDER BY max_amount
        ''')
        return cursor.fetchall()

    def save_threshold(self, role, max_amount, can_final_approve=0, active=1):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO approval_thresholds (role, max_amount, can_final_approve, active)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(role) DO UPDATE SET
                max_amount = excluded.max_amount,
                can_final_approve = excluded.can_final_approve,
                active = excluded.active
        ''', (role, float(max_amount or 0), int(bool(int(can_final_approve or 0))), int(bool(int(active or 0)))))
        self.conn.commit()


class JournalControlManager:
    """Journal reversal without deleting posted entries."""

    def __init__(self):
        self.conn = get_connection()

    def validate_balanced_entry(self, entry_id):
        """Ensure total debit equals total credit before treating an entry as valid."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COALESCE(SUM(debit_amount), 0) AS debit_total,
                   COALESCE(SUM(credit_amount), 0) AS credit_total,
                   COUNT(*) AS line_count
            FROM journal_entry_lines
            WHERE journal_entry_id = ?
        ''', (entry_id,))
        row = cursor.fetchone()
        if not row or row['line_count'] == 0:
            cursor.execute('SELECT COALESCE(amount, 0) AS amount FROM journal_entries WHERE id = ?', (entry_id,))
            entry = cursor.fetchone()
            if not entry:
                raise ValueError('Khong tim thay but toan.')
            if float(entry['amount'] or 0) <= 0:
                raise ValueError('But toan khong hop le: so tien phai lon hon 0.')
            return True
        debit_total = float(row['debit_total'] or 0)
        credit_total = float(row['credit_total'] or 0)
        if abs(debit_total - credit_total) > 0.01:
            raise ValueError(
                f"But toan khong can: No {debit_total:,.0f} <> Co {credit_total:,.0f}."
            )
        return True

    def reverse_entry(self, entry_id, actor_id=1, reason='Bút toán đảo ngược'):
        self.validate_balanced_entry(entry_id)
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM journal_entries WHERE id = ?', (entry_id,))
        entry = cursor.fetchone()
        if not entry:
            raise ValueError('Không tìm thấy bút toán gốc.')
        if entry['reversal_of_entry_id']:
            raise ValueError('Đây đã là bút toán đảo ngược.')
        if entry['reversed_by']:
            raise ValueError(f"Bút toán đã được đảo bởi bút toán #{entry['reversed_by']}.")

        description = f"Đảo ngược BT #{entry_id}: {reason or entry['description'] or ''}"
        cursor.execute('''
            INSERT INTO journal_entries
            (entry_date, fiscal_year, fiscal_period, entry_type, description,
             debit_account, credit_account, amount, expense_id, project_id, contract_id,
             reference_type, reference_id, reversal_of_entry_id, created_by)
            VALUES (?, ?, ?, 'reversal', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            date.today().isoformat(), datetime.now().year, date.today().strftime('%Y-%m'),
            description, entry['debit_account'], entry['credit_account'],
            -float(entry['amount'] or 0), entry['expense_id'], entry['project_id'],
            entry['contract_id'], entry['reference_type'], entry['reference_id'],
            entry_id, actor_id,
        ))
        reversal_id = cursor.lastrowid
        cursor.execute('UPDATE journal_entries SET reversed_by = ? WHERE id = ?', (reversal_id, entry_id))
        cursor.execute('''
            INSERT INTO audit_log (entity_type, entity_id, action, old_value, new_value, actor_id)
            VALUES ('journal_entries', ?, 'REVERSAL', ?, ?, ?)
        ''', (entry_id, json.dumps(dict(entry), ensure_ascii=False, default=str), json.dumps({'reversal_id': reversal_id}, ensure_ascii=False), actor_id))
        if entry['expense_id']:
            cursor.execute('UPDATE expenses SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', ('reversed', entry['expense_id']))
            cursor.execute('''
                INSERT INTO approval_logs (expense_id, action, actor, note)
                VALUES (?, 'reversed', ?, ?)
            ''', (entry['expense_id'], f'User {actor_id}', reason))
        self.conn.commit()
        return reversal_id

    def reverse_expense(self, expense_id, actor_id=1, reason='Bỏ ghi bằng bút toán đảo'):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id FROM journal_entries
            WHERE (expense_id = ? OR (reference_type IN ('expense', 'expense_wip') AND reference_id = ?))
              AND COALESCE(reversal_of_entry_id, 0) = 0
              AND COALESCE(reversed_by, 0) = 0
            ORDER BY id
        ''', (expense_id, expense_id))
        ids = [row['id'] for row in cursor.fetchall()]
        return [self.reverse_entry(entry_id, actor_id, reason) for entry_id in ids]


class ExtensionReportManager:
    """Compact reports for features 22-35."""

    def __init__(self):
        self.conn = get_connection()

    def fixed_asset_report(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT asset_code, asset_name, acquisition_cost, accumulated_depreciation,
                   acquisition_cost - accumulated_depreciation AS net_value, status
            FROM fixed_assets
            ORDER BY asset_code
        ''')
        return cursor.fetchall()

    def add_fixed_asset(self, data):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO fixed_assets
            (asset_code, asset_name, asset_type, acquisition_date, acquisition_cost,
             useful_life_months, depreciation_method, salvage_value, project_id, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['asset_code'], data['asset_name'], data.get('asset_type', ''),
            data.get('acquisition_date'), float(data.get('acquisition_cost') or 0),
            int(float(data.get('useful_life_months') or 0)),
            data.get('depreciation_method') or 'straight_line',
            float(data.get('salvage_value') or 0),
            data.get('project_id') or None,
            data.get('status') or 'active',
            data.get('notes') or '',
        ))
        self.conn.commit()
        return cursor.lastrowid

    def run_straight_line_depreciation(self, period):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM fixed_assets
            WHERE status = 'active' AND depreciation_method = 'straight_line'
              AND useful_life_months > 0
        ''')
        created = 0
        for asset in cursor.fetchall():
            monthly = max(float(asset['acquisition_cost'] or 0) - float(asset['salvage_value'] or 0), 0) / int(asset['useful_life_months'])
            cursor.execute('''
                INSERT OR IGNORE INTO asset_depreciation_runs
                (asset_id, period, depreciation_amount, project_id)
                VALUES (?, ?, ?, ?)
            ''', (asset['id'], period, monthly, asset['project_id']))
            if cursor.rowcount:
                created += 1
                cursor.execute('''
                    UPDATE fixed_assets
                    SET accumulated_depreciation = COALESCE(accumulated_depreciation, 0) + ?
                    WHERE id = ?
                ''', (monthly, asset['id']))
        self.conn.commit()
        return created

    def allocate_overhead(self, period, basis='actual_cost'):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM projects WHERE code = 'CHUNG' LIMIT 1")
        chung = cursor.fetchone()
        if not chung:
            return 0
        cursor.execute('''
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE project_id = ? AND substr(expense_date, 1, 7) = ?
        ''', (chung['id'], period))
        overhead = float(cursor.fetchone()[0] or 0)
        if overhead <= 0:
            return 0
        if basis == 'revenue':
            query = '''
                SELECT p.id, COALESCE(SUM(r.amount), 0) AS weight
                FROM projects p LEFT JOIN project_revenues r ON r.project_id = p.id
                WHERE p.code != 'CHUNG'
                GROUP BY p.id
            '''
        else:
            query = '''
                SELECT p.id, COALESCE(SUM(e.amount), 0) AS weight
                FROM projects p LEFT JOIN expenses e ON e.project_id = p.id
                WHERE p.code != 'CHUNG'
                GROUP BY p.id
            '''
        cursor.execute(query)
        weights = [dict(row) for row in cursor.fetchall() if float(row['weight'] or 0) > 0]
        total_weight = sum(float(row['weight']) for row in weights)
        if total_weight <= 0:
            return 0
        created = 0
        for row in weights:
            amount = overhead * float(row['weight']) / total_weight
            cursor.execute('''
                INSERT INTO overhead_allocations
                (period, basis, source_project_id, target_project_id, amount)
                VALUES (?, ?, ?, ?, ?)
            ''', (period, basis, chung['id'], row['id'], amount))
            created += 1
        self.conn.commit()
        return created

    def qs_reconciliation_report(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT p.code AS project_code, w.item_code, w.item_name,
                   COALESCE(q.original_budget, COALESCE(w.planned_quantity, 0) * COALESCE(w.unit_price, 0)) AS original_budget,
                   COALESCE(q.revised_budget, COALESCE(w.planned_quantity, 0) * COALESCE(w.unit_price, 0)) AS revised_budget,
                   COALESCE(q.actual_cost, (SELECT SUM(e.amount) FROM expenses e WHERE e.work_item_id = w.id), 0) AS actual_cost
            FROM construction_work_items w
            LEFT JOIN projects p ON p.id = w.project_id
            LEFT JOIN qs_reconciliation_items q ON q.work_item_id = w.id
            ORDER BY p.code, w.item_code
        ''')
        return cursor.fetchall()

    def poc_revenue_report(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT p.code, p.name, r.period, r.contract_value, r.previous_percent,
                   r.current_percent, r.revenue_amount
            FROM poc_revenue_recognitions r
            JOIN projects p ON p.id = r.project_id
            ORDER BY r.period DESC, p.code
        ''')
        return cursor.fetchall()

    def ar_ap_aging(self):
        today = date.today()
        buckets = {'0-30': (0, 30), '31-60': (31, 60), '61-90': (61, 90), '>90': (91, 99999)}
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT partner_type, partner_name, due_date,
                   amount - COALESCE(paid_amount, 0) AS outstanding
            FROM ar_ap_items
            WHERE status = 'open' AND amount > COALESCE(paid_amount, 0)
        ''')
        result = {}
        for row in cursor.fetchall():
            age = max((today - datetime.strptime(row['due_date'], '%Y-%m-%d').date()).days, 0)
            bucket = next(name for name, (lo, hi) in buckets.items() if lo <= age <= hi)
            key = (row['partner_type'], row['partner_name'])
            result.setdefault(key, {'partner_type': row['partner_type'], 'partner_name': row['partner_name'], '0-30': 0, '31-60': 0, '61-90': 0, '>90': 0})
            result[key][bucket] += float(row['outstanding'] or 0)
        return list(result.values())

    def ar_ap_items(self, status='open'):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT a.id, a.partner_type, a.partner_name, COALESCE(p.code, '') AS project_code,
                   a.due_date, a.amount, COALESCE(a.paid_amount, 0) AS paid_amount,
                   a.amount - COALESCE(a.paid_amount, 0) AS outstanding,
                   a.status, COALESCE(a.notes, '') AS notes,
                   COALESCE(a.source_type, 'manual') AS source_type,
                   COALESCE(a.source_id, '') AS source_id
            FROM ar_ap_items a
            LEFT JOIN projects p ON p.id = a.project_id
            WHERE 1=1
        '''
        if status and status != 'all':
            query += ' AND a.status = ?'
            params.append(status)
        query += ' ORDER BY date(a.due_date), a.partner_name'
        cursor.execute(query, params)
        return cursor.fetchall()

    def add_ar_ap_item(self, data):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO ar_ap_items
            (partner_type, partner_name, project_id, doc_id, due_date, amount, paid_amount, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('partner_type') or 'customer',
            data['partner_name'],
            data.get('project_id') or None,
            data.get('doc_id') or None,
            data['due_date'],
            float(data.get('amount') or 0),
            float(data.get('paid_amount') or 0),
            data.get('status') or 'open',
            data.get('notes') or '',
        ))
        self.conn.commit()
        return cursor.lastrowid

    def settle_ar_ap_item(self, item_id, amount=None):
        cursor = self.conn.cursor()
        cursor.execute('SELECT amount, COALESCE(paid_amount, 0) AS paid_amount FROM ar_ap_items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError('Khong tim thay khoan cong no.')
        total = float(row['amount'] or 0)
        paid = float(row['paid_amount'] or 0)
        pay_amount = total - paid if amount is None else float(amount or 0)
        if pay_amount <= 0:
            raise ValueError('So tien thanh toan phai lon hon 0.')
        new_paid = min(total, paid + pay_amount)
        status = 'closed' if new_paid >= total - 0.01 else 'open'
        cursor.execute('''
            UPDATE ar_ap_items
            SET paid_amount = ?, status = ?
            WHERE id = ?
        ''', (new_paid, status, item_id))
        self.conn.commit()
        return new_paid, status

    def sync_ar_ap_from_sources(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO ar_ap_items
            (partner_type, partner_name, project_id, doc_id, due_date, amount, paid_amount,
             status, notes, source_type, source_id)
            SELECT 'supplier',
                   COALESCE(NULLIF(TRIM(d.supplier_name), ''), 'Chưa xác định'),
                   d.project_id,
                   d.id,
                   COALESCE(date(d.doc_date, '+30 days'), date('now')),
                   COALESCE(d.amount, 0),
                   0,
                   'open',
                   'Tự đồng bộ từ chứng từ ' || COALESCE(d.doc_number, d.id),
                   'document',
                   d.id
            FROM documents d
            WHERE d.status = 'posted'
              AND COALESCE(d.amount, 0) > 0
              AND lower(COALESCE(d.doc_type, '')) NOT LIKE '%thu%'
            ON CONFLICT(source_type, source_id, partner_type)
            WHERE source_type IS NOT NULL AND source_id IS NOT NULL
            DO UPDATE SET
                partner_name = excluded.partner_name,
                project_id = excluded.project_id,
                doc_id = excluded.doc_id,
                due_date = excluded.due_date,
                amount = excluded.amount,
                notes = excluded.notes
        ''')
        doc_changes = cursor.rowcount if cursor.rowcount is not None else 0

        cursor.execute('''
            INSERT INTO ar_ap_items
            (partner_type, partner_name, project_id, doc_id, due_date, amount, paid_amount,
             status, notes, source_type, source_id)
            SELECT CASE WHEN c.contract_type = 'customer' THEN 'customer' ELSE 'supplier' END,
                   c.partner_name,
                   c.project_id,
                   NULL,
                   b.billing_date,
                   COALESCE(b.net_amount, 0),
                   CASE WHEN b.status = 'paid' THEN COALESCE(b.net_amount, 0) ELSE 0 END,
                   CASE WHEN b.status = 'paid' THEN 'closed' ELSE 'open' END,
                   'Tự đồng bộ từ nghiệm thu ' || COALESCE(c.contract_no, b.id),
                   'billing',
                   b.id
            FROM contract_billings b
            JOIN project_contracts c ON c.id = b.contract_id
            WHERE COALESCE(b.net_amount, 0) > 0
            ON CONFLICT(source_type, source_id, partner_type)
            WHERE source_type IS NOT NULL AND source_id IS NOT NULL
            DO UPDATE SET
                partner_name = excluded.partner_name,
                project_id = excluded.project_id,
                due_date = excluded.due_date,
                amount = excluded.amount,
                paid_amount = excluded.paid_amount,
                status = excluded.status,
                notes = excluded.notes
        ''')
        billing_changes = cursor.rowcount if cursor.rowcount is not None else 0
        self.conn.commit()
        return max(doc_changes, 0) + max(billing_changes, 0)

    def expiring_items(self, days=60):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT item_type, item_name, reference_no, expiry_date, owner, status
            FROM expiring_items
            WHERE status = 'active' AND date(expiry_date) <= date(?, ?)
            ORDER BY expiry_date
        ''', (date.today().isoformat(), f'+{int(days)} days'))
        return cursor.fetchall()

    def multi_period_expenses(self, months=6):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT strftime('%Y-%m', expense_date) AS period, SUM(amount) AS total
            FROM expenses
            WHERE date(expense_date) >= date('now', ?)
            GROUP BY strftime('%Y-%m', expense_date)
            ORDER BY period
        ''', (f'-{int(months)} months',))
        rows = cursor.fetchall()
        result = []
        previous = None
        for row in rows:
            total = float(row['total'] or 0)
            change = ((total - previous) / previous * 100) if previous else None
            result.append({'period': row['period'], 'total': total, 'change_pct': change})
            previous = total
        return result

    def vendor_scorecards(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT supplier_name, period, price_score, quality_score, delivery_score, document_score,
                   (price_score + quality_score + delivery_score + document_score) / 4.0 AS avg_score,
                   status
            FROM vendor_scorecards
            ORDER BY avg_score DESC, supplier_name
        ''')
        return cursor.fetchall()
