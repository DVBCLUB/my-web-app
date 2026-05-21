"""
MODULE UTILITIES - Cac tien ich nang cao cho phan mem ke toan.
"""

from datetime import datetime, timedelta
from database import get_connection


class UtilityManager:
    """Nghiep vu bo sung: canh bao, danh muc, tam ung, tim kiem va but toan."""

    def __init__(self):
        self.conn = get_connection()

    def get_missing_document_expenses(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT e.id, e.expense_date, COALESCE(p.name, ''), COALESCE(ec.name, ''),
                   e.description, e.amount, e.status,
                   COALESCE(r.rule_name, ''), COALESCE(r.required_documents, ''),
                   COUNT(DISTINCT d.id) AS document_count,
                   COUNT(DISTINCT a.id) AS attachment_count
            FROM expenses e
            LEFT JOIN projects p ON e.project_id = p.id
            LEFT JOIN expense_categories ec ON e.category_id = ec.id
            LEFT JOIN compliance_rules r ON r.expense_category_code = ec.code AND r.active = 1
            LEFT JOIN documents d ON d.expense_id = e.id
            LEFT JOIN attachments a ON a.expense_id = e.id
            WHERE 1 = 1
        '''
        if keyword:
            query += '''
                AND (
                    e.description LIKE ? OR COALESCE(p.name, '') LIKE ?
                    OR COALESCE(ec.name, '') LIKE ? OR COALESCE(r.required_documents, '') LIKE ?
                )
            '''
            search = f'%{keyword}%'
            params.extend([search, search, search, search])
        query += '''
            GROUP BY e.id
            HAVING document_count = 0 OR attachment_count = 0
            ORDER BY e.expense_date DESC, e.id DESC
        '''
        cursor.execute(query, params)
        return cursor.fetchall()

    def get_expense_detail(self, expense_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT e.*, COALESCE(p.name, '') AS project_name,
                   COALESCE(ec.name, '') AS category_name, ec.code AS category_code
            FROM expenses e
            LEFT JOIN projects p ON e.project_id = p.id
            LEFT JOIN expense_categories ec ON e.category_id = ec.id
            WHERE e.id = ?
        ''', (expense_id,))
        return cursor.fetchone()

    def get_account_suggestion_by_expense(self, expense_id):
        expense = self.get_expense_detail(expense_id)
        if not expense:
            return None
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT m.*, da.account_name AS debit_name, ca.account_name AS credit_name
            FROM category_account_mappings m
            LEFT JOIN accounts da ON da.account_code = m.debit_account
            LEFT JOIN accounts ca ON ca.account_code = m.credit_account
            WHERE m.category_id = ? AND m.active = 1
            LIMIT 1
        ''', (expense['category_id'],))
        mapping = cursor.fetchone()
        if mapping:
            return dict(mapping)

        name = (expense['category_name'] or '').lower()
        defaults = [
            ('vat', '621', '111'),
            ('nhan cong', '622', '111'),
            ('thau phu', '627', '331'),
            ('may', '623', '111'),
            ('van chuyen', '627', '111'),
            ('tam ung', '141', '111'),
            ('van phong', '642', '111'),
        ]
        debit, credit = '642', '111'
        for marker, debit_acc, credit_acc in defaults:
            if marker in name:
                debit, credit = debit_acc, credit_acc
                break
        return {
            'category_id': expense['category_id'],
            'debit_account': debit,
            'credit_account': credit,
            'notes': 'Gợi ý tự động theo tên loại chi phí',
            'debit_name': '',
            'credit_name': '',
        }

    def save_account_mapping(self, category_id, debit_account, credit_account, notes=''):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO category_account_mappings
            (category_id, debit_account, credit_account, notes, active)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(category_id) DO UPDATE SET
                debit_account = excluded.debit_account,
                credit_account = excluded.credit_account,
                notes = excluded.notes,
                active = 1
        ''', (category_id, debit_account, credit_account, notes))
        self.conn.commit()

    def get_journal_entries_for_expense(self, expense_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, entry_date, debit_account, credit_account, amount, description, reference_type
            FROM journal_entries WHERE expense_id = ?
            ORDER BY id
        ''', (expense_id,))
        return cursor.fetchall()

    def validate_expense_before_post(self, expense_id):
        expense = self.get_expense_detail(expense_id)
        if not expense:
            return [{'level': 'critical', 'message': 'Không tìm thấy chi phí.'}]

        issues = []
        amount = float(expense['amount'] or 0)
        if amount <= 0:
            issues.append({'level': 'critical', 'message': 'Số tiền phải lớn hơn 0.'})
        if not expense['project_id']:
            issues.append({'level': 'warning', 'message': 'Chi phí chưa gắn dự án.'})
        if not expense['category_id']:
            issues.append({'level': 'critical', 'message': 'Chi phí chưa có loại chi phí.'})

        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM documents WHERE expense_id = ?', (expense_id,))
        document_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM attachments WHERE expense_id = ?', (expense_id,))
        attachment_count = cursor.fetchone()[0]
        if document_count == 0 and attachment_count == 0:
            issues.append({'level': 'critical', 'message': 'Chưa có hóa đơn/chứng từ hoặc file scan đính kèm.'})
        elif document_count == 0:
            issues.append({'level': 'warning', 'message': 'Có file đính kèm nhưng chưa lập chứng từ trong phần mềm.'})
        elif attachment_count == 0:
            issues.append({'level': 'warning', 'message': 'Có chứng từ nhưng chưa có file scan đính kèm.'})

        suggestion = self.get_account_suggestion_by_expense(expense_id)
        if not suggestion or not suggestion.get('debit_account') or not suggestion.get('credit_account'):
            issues.append({'level': 'critical', 'message': 'Chưa có mapping tài khoản Nợ/Có cho loại chi phí.'})
        return issues

    def unpost_expense(self, expense_id, actor='He thong', note='Bỏ ghi sổ bằng bút toán đảo'):
        expense = self.get_expense_detail(expense_id)
        if not expense:
            raise ValueError('Không tìm thấy chi phí')
        entries = self.get_journal_entries_for_expense(expense_id)
        if not entries:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE expenses SET status = 'approved', updated_at = CURRENT_TIMESTAMP WHERE id = ?
            ''', (expense_id,))
            cursor.execute('''
                INSERT INTO approval_logs (expense_id, action, actor, note) VALUES (?, ?, ?, ?)
            ''', (expense_id, 'unposted', actor, note))
            self.conn.commit()
            return 0
        from modules.controls import JournalControlManager
        reversals = JournalControlManager().reverse_expense(expense_id, actor_id=1, reason=note)
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE expenses SET status = 'reversed', updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (expense_id,))
        cursor.execute('''
            INSERT INTO approval_logs (expense_id, action, actor, note) VALUES (?, ?, ?, ?)
        ''', (expense_id, 'reversed', actor, f"{note}; tạo {len(reversals)} bút toán đảo"))
        self.conn.commit()
        return len(reversals)

    def create_journal_from_expense(self, expense_id, created_by=1):
        expense = self.get_expense_detail(expense_id)
        if not expense:
            raise ValueError('Không tìm thấy chi phí')
        if expense['status'] == 'posted':
            raise ValueError('Chi phí đã được ghi sổ. Bỏ ghi trước nếu cần hạch toán lại.')
        existing = self.get_journal_entries_for_expense(expense_id)
        if existing:
            raise ValueError('Đã có bút toán cho chi phí này. Dùng Bỏ ghi sổ trước.')
        suggestion = self.get_account_suggestion_by_expense(expense_id)
        debit = suggestion['debit_account']
        credit = suggestion['credit_account']
        cursor = self.conn.cursor()
        project_id = expense.get('project_id') if hasattr(expense, 'get') else expense['project_id']
        contract_id = expense.get('contract_id') if hasattr(expense, 'get') else expense['contract_id']
        cursor.execute('''
            INSERT INTO journal_entries
            (entry_date, description, debit_account, credit_account, amount,
             expense_id, project_id, contract_id, reference_type, reference_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'expense', ?, ?)
        ''', (
            expense['expense_date'], expense['description'], debit, credit,
            expense['amount'], expense_id, project_id, contract_id,
            expense_id, created_by,
        ))
        cursor.execute('UPDATE expenses SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                       ('posted', expense_id))
        self.conn.commit()
        return cursor.lastrowid, debit, credit

    def update_expense_status(self, expense_id, status, actor='He thong', note=''):
        cursor = self.conn.cursor()
        cursor.execute('UPDATE expenses SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                       (status, expense_id))
        cursor.execute('''
            INSERT INTO approval_logs (expense_id, action, actor, note)
            VALUES (?, ?, ?, ?)
        ''', (expense_id, status, actor, note))
        self.conn.commit()

    def get_approval_logs(self, expense_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT action, actor, note, created_at
            FROM approval_logs
            WHERE expense_id = ?
            ORDER BY created_at DESC, id DESC
        ''', (expense_id,))
        return cursor.fetchall()

    def get_advance_dashboard(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COALESCE(NULLIF(TRIM(paid_by), ''), 'KhĂ´ng rĂµ') AS employee,
                   SUM(CASE WHEN e.amount > 0 THEN e.amount ELSE 0 END) AS total_advance,
                   SUM(CASE WHEN e.status IN ('paid', 'posted', 'approved') THEN e.amount ELSE 0 END) AS settled,
                   SUM(CASE WHEN e.status NOT IN ('paid', 'posted', 'approved') THEN e.amount ELSE 0 END) AS outstanding,
                   MIN(e.expense_date) AS oldest_date,
                   COUNT(*) AS count_items
            FROM expenses e
            LEFT JOIN expense_categories ec ON e.category_id = ec.id
            WHERE LOWER(COALESCE(ec.name, '')) LIKE '%tam%'
               OR LOWER(COALESCE(e.description, '')) LIKE '%tam ung%'
            GROUP BY employee
            ORDER BY outstanding DESC, total_advance DESC
        ''')
        return cursor.fetchall()

    def get_project_budget_report(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT p.id, p.code, p.name, COALESCE(p.budget, 0) AS budget,
                   COALESCE(SUM(e.amount), 0) AS spent,
                   COALESCE(p.budget, 0) - COALESCE(SUM(e.amount), 0) AS remaining
            FROM projects p
            LEFT JOIN expenses e ON e.project_id = p.id
            GROUP BY p.id
            ORDER BY spent DESC
        ''')
        return cursor.fetchall()

    def get_accounting_control_summary(self):
        """Bá»™ chá»‰ bĂ¡o kiá»ƒm soĂ¡t káº¿ toĂ¡n trÆ°á»›c khi khĂ³a sá»• hoáº·c xuáº¥t Power BI."""
        findings = self.get_accounting_control_findings(limit=500)
        grouped = {'critical': 0, 'warning': 0, 'info': 0}
        amount_at_risk = 0.0
        for item in findings:
            grouped[item['severity']] = grouped.get(item['severity'], 0) + 1
            amount_at_risk += float(item.get('amount') or 0)
        score = max(0, 100 - grouped['critical'] * 12 - grouped['warning'] * 5 - grouped['info'] * 2)
        return {
            'score': score,
            'critical': grouped['critical'],
            'warning': grouped['warning'],
            'info': grouped['info'],
            'amount_at_risk': amount_at_risk,
            'findings': findings[:8],
        }

    def get_period_close_check(self, fiscal_period):
        cursor = self.conn.cursor()
        issues = []
        period = str(fiscal_period or '')[:7]
        if not period:
            return issues

        cursor.execute('''
            SELECT COUNT(*) AS count_items, COALESCE(SUM(e.amount), 0) AS total_amount
            FROM expenses e
            LEFT JOIN documents d ON d.expense_id = e.id
            LEFT JOIN attachments a ON a.expense_id = e.id
            WHERE substr(e.expense_date, 1, 7) = ?
            GROUP BY e.id
            HAVING COUNT(DISTINCT d.id) = 0 OR COUNT(DISTINCT a.id) = 0
        ''', (period,))
        missing_rows = cursor.fetchall()
        if missing_rows:
            issues.append({
                'level': 'critical',
                'title': 'Chi phí thiếu hồ sơ',
                'count': len(missing_rows),
                'amount': sum(float(row['total_amount'] or 0) for row in missing_rows),
                'action': 'Bổ sung hóa đơn/chứng từ/file scan trước khi khóa kỳ.',
            })

        cursor.execute('''
            SELECT COUNT(*) AS count_items, COALESCE(SUM(amount), 0) AS total_amount
            FROM documents
            WHERE substr(doc_date, 1, 7) = ?
              AND status NOT IN ('posted', 'cancelled', 'rejected')
        ''', (period,))
        row = cursor.fetchone()
        if row and row['count_items']:
            issues.append({
                'level': 'warning',
                'title': 'Chứng từ chưa ghi sổ',
                'count': row['count_items'],
                'amount': float(row['total_amount'] or 0),
                'action': 'Rà soát và ghi sổ hoặc hủy chứng từ nháp.',
            })

        cursor.execute('''
            SELECT COUNT(*) AS count_items, COALESCE(SUM(amount), 0) AS total_amount
            FROM expenses
            WHERE substr(expense_date, 1, 7) = ?
              AND status IN ('approved', 'paid')
              AND NOT EXISTS (SELECT 1 FROM journal_entries j WHERE j.expense_id = expenses.id)
        ''', (period,))
        row = cursor.fetchone()
        if row and row['count_items']:
            issues.append({
                'level': 'critical',
                'title': 'Chi phí đã duyệt nhưng chưa hạch toán',
                'count': row['count_items'],
                'amount': float(row['total_amount'] or 0),
                'action': 'Tạo bút toán Nợ/Có trước khi khóa kỳ.',
            })

        cursor.execute('''
            SELECT COUNT(*) AS count_items, COALESCE(SUM(amount), 0) AS total_amount
            FROM journal_entries
            WHERE substr(entry_date, 1, 7) = ?
              AND (COALESCE(debit_account, '') = ''
                   OR COALESCE(credit_account, '') = ''
                   OR COALESCE(amount, 0) <= 0)
        ''', (period,))
        row = cursor.fetchone()
        if row and row['count_items']:
            issues.append({
                'level': 'critical',
                'title': 'Bút toán thiếu tài khoản hoặc số tiền',
                'count': row['count_items'],
                'amount': float(row['total_amount'] or 0),
                'action': 'Hoàn thiện tài khoản Nợ/Có và số tiền bút toán.',
            })

        cursor.execute('''
            SELECT COUNT(*) AS count_items, COALESCE(SUM(amount - COALESCE(paid_amount, 0)), 0) AS total_amount
            FROM ar_ap_items
            WHERE status = 'open'
              AND substr(due_date, 1, 7) <= ?
              AND date(due_date) < date('now')
        ''', (period,))
        row = cursor.fetchone()
        if row and row['count_items']:
            issues.append({
                'level': 'warning',
                'title': 'Công nợ quá hạn chưa xử lý',
                'count': row['count_items'],
                'amount': float(row['total_amount'] or 0),
                'action': 'Đối chiếu thu/chi hoặc ghi nhận thanh toán.',
            })
        return issues

    def get_accounting_control_findings(self, limit=100):
        cursor = self.conn.cursor()
        findings = []

        cursor.execute('''
            SELECT e.id, e.expense_date, COALESCE(p.name, '') AS project_name,
                   COALESCE(ec.name, '') AS category_name, e.description, e.amount
            FROM expenses e
            LEFT JOIN projects p ON p.id = e.project_id
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            LEFT JOIN documents d ON d.expense_id = e.id
            LEFT JOIN attachments a ON a.expense_id = e.id
            GROUP BY e.id
            HAVING COUNT(DISTINCT d.id) = 0 AND COUNT(DISTINCT a.id) = 0
            ORDER BY e.amount DESC
            LIMIT ?
        ''', (limit,))
        for row in cursor.fetchall():
            findings.append(self._control_item(
                'warning', 'Thiếu chứng từ/file đính kèm', row,
                'Bổ sung hóa đơn, phiếu chi, đề nghị thanh toán hoặc file scan trước khi duyệt/ghi sổ.'
            ))

        cursor.execute('''
            SELECT e.id, e.expense_date, COALESCE(p.name, '') AS project_name,
                   COALESCE(ec.name, '') AS category_name, e.description, e.amount
            FROM expenses e
            LEFT JOIN projects p ON p.id = e.project_id
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            WHERE e.status IN ('approved', 'paid') AND NOT EXISTS (
                SELECT 1 FROM journal_entries j WHERE j.expense_id = e.id
            )
            ORDER BY e.expense_date DESC
            LIMIT ?
        ''', (limit,))
        for row in cursor.fetchall():
            findings.append(self._control_item(
                'critical', 'Đã duyệt nhưng chưa hạch toán', row,
                'Tạo bút toán Nợ/Có hoặc kiểm tra mapping tài khoản chi phí.'
            ))

        cursor.execute('''
            SELECT e.id, e.expense_date, COALESCE(p.name, '') AS project_name,
                   COALESCE(ec.name, '') AS category_name, e.description, e.amount
            FROM expenses e
            LEFT JOIN projects p ON p.id = e.project_id
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            WHERE e.amount <= 0 OR e.amount IS NULL
            ORDER BY e.id DESC
            LIMIT ?
        ''', (limit,))
        for row in cursor.fetchall():
            findings.append(self._control_item(
                'critical', 'Số tiền không hợp lệ', row,
                'Kiểm tra lại số tiền, dấu thập phân và dữ liệu import Excel/OCR.'
            ))

        cursor.execute('''
            SELECT p.id, p.code, p.name, COALESCE(p.budget, 0) AS budget,
                   COALESCE(SUM(e.amount), 0) AS spent
            FROM projects p
            JOIN expenses e ON e.project_id = p.id
            WHERE COALESCE(p.budget, 0) > 0
            GROUP BY p.id
            HAVING spent > budget
            ORDER BY spent - budget DESC
            LIMIT ?
        ''', (limit,))
        for row in cursor.fetchall():
            findings.append({
                'severity': 'critical',
                'type': 'Vượt ngân sách dự án',
                'record_id': row['id'],
                'record_date': '',
                'project_name': f"{row['code']} - {row['name']}",
                'category_name': 'Ngân sách',
                'description': f"Đã chi {row['spent']:,.0f} / ngân sách {row['budget']:,.0f}",
                'amount': float(row['spent'] or 0) - float(row['budget'] or 0),
                'recommendation': 'Rà soát phát sinh, phê duyệt bổ sung ngân sách hoặc điều chỉnh kế hoạch chi phí.',
            })

        cursor.execute('''
            SELECT j.id, j.entry_date, j.description, j.amount,
                   COALESCE(j.debit_account, '') AS debit_account,
                   COALESCE(j.credit_account, '') AS credit_account
            FROM journal_entries j
            WHERE COALESCE(j.debit_account, '') = ''
               OR COALESCE(j.credit_account, '') = ''
               OR COALESCE(j.amount, 0) <= 0
            ORDER BY j.entry_date DESC
            LIMIT ?
        ''', (limit,))
        for row in cursor.fetchall():
            findings.append({
                'severity': 'critical',
                'type': 'Bút toán thiếu tài khoản hoặc số tiền',
                'record_id': row['id'],
                'record_date': row['entry_date'] or '',
                'project_name': '',
                'category_name': f"{row['debit_account']} / {row['credit_account']}",
                'description': row['description'] or '',
                'amount': row['amount'] or 0,
                'recommendation': 'Bổ sung đủ TK Nợ, TK Có và số tiền trước khi khóa sổ.',
            })

        cursor.execute('''
            SELECT COUNT(*) AS count_items, COALESCE(SUM(ABS(b.amount)), 0) AS total_amount
            FROM bank_statement_rows b
            LEFT JOIN bank_reconciliation_matches m ON m.bank_row_id = b.id
            WHERE m.id IS NULL
        ''')
        row = cursor.fetchone()
        if row and row['count_items']:
            findings.append({
                'severity': 'warning',
                'type': 'Sao kê ngân hàng chưa đối chiếu',
                'record_id': '',
                'record_date': '',
                'project_name': '',
                'category_name': 'Ngân hàng',
                'description': f"Còn {row['count_items']} dòng sao kê chưa khớp với dữ liệu hệ thống.",
                'amount': float(row['total_amount'] or 0),
                'recommendation': 'Mở mục Ngân hàng, chạy Auto-match rồi xử lý các dòng còn treo.',
            })

        cursor.execute('''
            SELECT COUNT(*) AS count_items, COALESCE(SUM(e.amount), 0) AS total_amount
            FROM expenses e
            WHERE LOWER(COALESCE(e.payment_method, '')) LIKE '%chuyển%'
              AND NOT EXISTS (
                  SELECT 1
                  FROM bank_reconciliation_matches m
                  WHERE m.system_record_type = 'expense'
                    AND m.system_record_id = e.id
              )
        ''')
        row = cursor.fetchone()
        if row and row['count_items']:
            findings.append({
                'severity': 'warning',
                'type': 'Chi phí chuyển khoản chưa khớp sao kê',
                'record_id': '',
                'record_date': '',
                'project_name': '',
                'category_name': 'Ngân hàng',
                'description': f"Còn {row['count_items']} chi phí chuyển khoản chưa có dòng sao kê khớp.",
                'amount': float(row['total_amount'] or 0),
                'recommendation': 'Nhập sao kê ngân hàng đầy đủ và đối chiếu trước khi khóa kỳ.',
            })

        cursor.execute('''
            SELECT MIN(e.id) AS id, e.expense_date, COALESCE(p.name, '') AS project_name,
                   COALESCE(ec.name, '') AS category_name, e.description,
                   e.amount, COUNT(*) AS count_items
            FROM expenses e
            LEFT JOIN projects p ON p.id = e.project_id
            LEFT JOIN expense_categories ec ON ec.id = e.category_id
            GROUP BY e.expense_date, COALESCE(e.project_id, 0), COALESCE(e.category_id, 0),
                     LOWER(TRIM(COALESCE(e.description, ''))), ROUND(COALESCE(e.amount, 0), 0)
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC, e.amount DESC
            LIMIT ?
        ''', (limit,))
        for row in cursor.fetchall():
            findings.append({
                'severity': 'warning',
                'type': 'Chi phí nghi trùng',
                'record_id': row['id'],
                'record_date': row['expense_date'] or '',
                'project_name': row['project_name'] or '',
                'category_name': row['category_name'] or '',
                'description': f"{row['description'] or ''} ({row['count_items']} dòng giống nhau)",
                'amount': float(row['amount'] or 0) * int(row['count_items'] or 1),
                'recommendation': 'Rà soát các dòng nhập/import trùng trước khi duyệt hoặc ghi sổ.',
            })

        rank = {'critical': 0, 'warning': 1, 'info': 2}
        findings.sort(key=lambda x: (rank.get(x['severity'], 9), -float(x.get('amount') or 0)))
        return findings[:limit]

    def _control_item(self, severity, issue_type, row, recommendation):
        return {
            'severity': severity,
            'type': issue_type,
            'record_id': row['id'],
            'record_date': row['expense_date'] or '',
            'project_name': row['project_name'] or '',
            'category_name': row['category_name'] or '',
            'description': row['description'] or '',
            'amount': row['amount'] or 0,
            'recommendation': recommendation,
        }

    def global_search(self, keyword):
        if not keyword:
            return []
        cursor = self.conn.cursor()
        search = f'%{keyword}%'
        results = []
        cursor.execute('''
            SELECT e.id, e.expense_date, COALESCE(p.name, ''), COALESCE(ec.name, ''),
                   e.description, e.amount, e.status
            FROM expenses e
            LEFT JOIN projects p ON e.project_id = p.id
            LEFT JOIN expense_categories ec ON e.category_id = ec.id
            WHERE e.description LIKE ? OR e.paid_by LIKE ? OR p.name LIKE ? OR ec.name LIKE ?
               OR CAST(e.amount AS TEXT) LIKE ?
            ORDER BY e.expense_date DESC
        ''', (search, search, search, search, search))
        for row in cursor.fetchall():
            results.append(('Chi phi', row[0], row[1], row[2], row[4], row[5], row[6]))

        cursor.execute('''
            SELECT d.id, d.doc_date, COALESCE(d.supplier_name, ''), COALESCE(d.doc_number, ''),
                   d.description, d.amount, d.status
            FROM documents d
            WHERE d.doc_number LIKE ? OR d.supplier_name LIKE ? OR d.description LIKE ?
               OR CAST(d.amount AS TEXT) LIKE ?
            ORDER BY d.doc_date DESC
        ''', (search, search, search, search))
        for row in cursor.fetchall():
            results.append(('Chung tu', row[0], row[1], row[2], row[4], row[5], row[6]))

        cursor.execute('''
            SELECT a.id, a.uploaded_at, COALESCE(a.file_name, ''), COALESCE(d.doc_number, ''),
                   a.file_path, '', ''
            FROM attachments a
            LEFT JOIN documents d ON a.document_id = d.id
            WHERE a.file_name LIKE ? OR a.file_path LIKE ? OR d.doc_number LIKE ?
            ORDER BY a.uploaded_at DESC
        ''', (search, search, search))
        for row in cursor.fetchall():
            results.append(('File', row[0], row[1], row[2], row[4], row[5], row[6]))
        return results

    def list_categories(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, code, name, description FROM expense_categories ORDER BY name')
        return cursor.fetchall()

    def save_category(self, code, name, description=''):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO expense_categories (code, name, description)
            VALUES (?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET name = excluded.name, description = excluded.description
        ''', (code, name, description))
        self.conn.commit()

    def list_projects(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, code, name, location, budget, status FROM projects ORDER BY code')
        return cursor.fetchall()

    def save_project(self, code, name, location='', budget=0, status='active'):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO projects (code, name, location, budget, status, created_by)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                location = excluded.location,
                budget = excluded.budget,
                status = excluded.status
        ''', (code, name, location, budget, status))
        self.conn.commit()

    def list_simple_catalog(self, catalog_type):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, catalog_type, name, description, active
            FROM simple_catalogs
            WHERE catalog_type = ?
            ORDER BY name
        ''', (catalog_type,))
        return cursor.fetchall()

    def save_simple_catalog(self, catalog_type, name, description=''):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO simple_catalogs (catalog_type, name, description, active)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(catalog_type, name) DO UPDATE SET
                description = excluded.description,
                active = 1
            ''', (catalog_type, name, description))
        self.conn.commit()

    def update_simple_catalog(self, catalog_id, name, description='', active=1):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE simple_catalogs
            SET name = ?, description = ?, active = ?
            WHERE id = ?
        ''', (name, description, int(active), catalog_id))
        self.conn.commit()

    def update_category(self, category_id, code, name, description=''):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE expense_categories
            SET code = ?, name = ?, description = ?
            WHERE id = ?
        ''', (code, name, description, category_id))
        self.conn.commit()

    def update_project(self, project_id, code, name, location='', budget=0, status='active'):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE projects
            SET code = ?, name = ?, location = ?, budget = ?, status = ?
            WHERE id = ?
        ''', (code, name, location, budget, status, project_id))
        self.conn.commit()

    def get_app_settings(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT key, value FROM app_settings')
        return {row['key']: row['value'] for row in cursor.fetchall()}

    def save_app_settings(self, settings):
        cursor = self.conn.cursor()
        for key, value in settings.items():
            cursor.execute('''
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            ''', (key, value))
        self.conn.commit()

    def backup_health(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT value FROM app_settings WHERE key = ?', ('last_backup_at',))
        row = cursor.fetchone()
        if not row or not row['value']:
            return 'Chưa có thông tin sao lưu gần nhất. Nên sao lưu ngay.'
        try:
            last_time = datetime.fromisoformat(row['value'])
        except ValueError:
            return f"Sao lưu gần nhất: {row['value']}"
        days = (datetime.now() - last_time).days
        if days >= 7:
            return f"Đã {days} ngày chưa sao lưu. Nên sao lưu ngay."
        return f"Sao lưu gần nhất cách đây {days} ngày."

    def mark_backup_now(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
        ''', ('last_backup_at', datetime.now().isoformat(timespec='seconds')))
        self.conn.commit()

    def get_linkage_checks(self):
        """Kiểm tra các liên kết dữ liệu quan trọng giữa các phân hệ."""
        cursor = self.conn.cursor()
        checks = []

        def add_check(group, issue, count, detail, action):
            status = 'OK' if count == 0 else 'Cần xử lý'
            checks.append((group, issue, status, count, detail, action))

        cursor.execute('''
            SELECT COUNT(*)
            FROM expenses e
            LEFT JOIN expense_categories ec ON e.category_id = ec.id
            WHERE e.category_id IS NULL OR ec.id IS NULL
        ''')
        add_check(
            'Chi phí', 'Chi phí thiếu loại chi phí',
            cursor.fetchone()[0],
            'Chi phí cần có loại chi phí để áp quy định hồ sơ và gợi ý tài khoản.',
            'Mở Chi phí hoặc Danh mục để gắn lại loại chi phí.'
        )

        cursor.execute('''
            SELECT COUNT(*)
            FROM expenses e
            LEFT JOIN projects p ON e.project_id = p.id
            WHERE e.project_id IS NOT NULL AND p.id IS NULL
        ''')
        add_check(
            'Chi phí', 'Chi phí trỏ đến dự án không tồn tại',
            cursor.fetchone()[0],
            'Dự án bị xóa/thiếu sẽ làm sai báo cáo dự toán và chi phí công trình.',
            'Tạo lại dự án trong Danh mục hoặc sửa chi phí.'
        )

        cursor.execute('''
            SELECT COUNT(*)
            FROM documents d
            LEFT JOIN expenses e ON d.expense_id = e.id
            WHERE d.expense_id IS NULL OR e.id IS NULL
        ''')
        add_check(
            'Chứng từ', 'Chứng từ chưa gắn đúng chi phí',
            cursor.fetchone()[0],
            'Chứng từ nên liên kết với nghiệp vụ chi phí để tra ngược hồ sơ.',
            'Mở Hóa đơn/Chứng từ hoặc Chi phí để thêm chứng từ cho chi phí.'
        )

        cursor.execute('''
            SELECT COUNT(*)
            FROM attachments a
            LEFT JOIN documents d ON a.document_id = d.id
            LEFT JOIN expenses e ON a.expense_id = e.id
            WHERE (a.document_id IS NULL AND a.expense_id IS NULL)
               OR (a.document_id IS NOT NULL AND d.id IS NULL)
               OR (a.expense_id IS NOT NULL AND e.id IS NULL)
        ''')
        add_check(
            'File', 'File đính kèm bị đứt liên kết',
            cursor.fetchone()[0],
            'File cần gắn với chi phí hoặc chứng từ để không thất lạc hồ sơ.',
            'Gắn lại file từ màn hình Chi phí hoặc Hóa đơn.'
        )

        cursor.execute('''
            SELECT COUNT(*)
            FROM journal_entries j
            LEFT JOIN expenses e ON j.expense_id = e.id
            WHERE j.expense_id IS NOT NULL AND e.id IS NULL
        ''')
        add_check(
            'Bút toán', 'Bút toán trỏ đến chi phí không tồn tại',
            cursor.fetchone()[0],
            'Bút toán tự động cần giữ liên kết với chi phí gốc.',
            'Kiểm tra sổ nhật ký và khôi phục chi phí nếu cần.'
        )

        cursor.execute('''
            SELECT COUNT(*)
            FROM expense_categories ec
            LEFT JOIN category_account_mappings m ON m.category_id = ec.id AND m.active = 1
            WHERE m.id IS NULL
        ''')
        add_check(
            'Tài khoản', 'Loại chi phí chưa có mapping tài khoản',
            cursor.fetchone()[0],
            'Mapping giúp phần mềm gợi ý Nợ/Có và tạo bút toán nhanh.',
            'Chọn chi phí theo loại đó và bấm Hạch toán để thiết lập mapping.'
        )

        cursor.execute('''
            SELECT COUNT(*)
            FROM documents d
            LEFT JOIN attachments a ON a.document_id = d.id
            WHERE COALESCE(d.file_path, '') = '' AND a.id IS NULL
        ''')
        add_check(
            'Hồ sơ', 'Chứng từ chưa có file scan/đính kèm',
            cursor.fetchone()[0],
            'Chứng từ không có file làm yếu khả năng đối chiếu và lưu trữ.',
            'Mở Hóa đơn/Chứng từ và bấm Liên kết file.'
        )

        return checks

