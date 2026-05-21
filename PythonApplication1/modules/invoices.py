"""
MODULE INVOICES - Quản lý hóa đơn & chứng từ
"""

import sqlite3
import os
import re
from database import ConnectionPerRequestMixin
from datetime import datetime, timedelta
from modules.fiscal_lock import assert_date_not_locked
from utils.logger import get_logger

logger = get_logger(__name__)


class DocumentManager(ConnectionPerRequestMixin):
    """Quản lý hóa đơn và chứng từ."""

    def __init__(self):
        self.attachment_dir = 'attachments'
        os.makedirs(self.attachment_dir, exist_ok=True)

    def add_document(self, doc_type, doc_number, doc_date, supplier_name,
                    description, amount, project_id, category_id, file_path, created_by,
                    expense_id=None, status='draft', vat_rate=10):
        """Thêm chứng từ mới."""
        assert_date_not_locked(doc_date, 'them chung tu')
        cursor = self.conn.cursor()
        if not doc_number:
            doc_number = self.generate_document_number(doc_type, doc_date)

        if expense_id and (not project_id or not category_id):
            cursor.execute('SELECT project_id, category_id FROM expenses WHERE id = ?', (expense_id,))
            expense = cursor.fetchone()
            if expense:
                project_id = project_id or expense['project_id']
                category_id = category_id or expense['category_id']
        supplier_id = self._ensure_supplier(supplier_name)
        duplicate = self.find_duplicate_invoice(doc_number, supplier_name, amount)
        if duplicate:
            raise ValueError(
                f"Hoa don trung voi chung tu #{duplicate['id']} "
                f"({duplicate['supplier_name']} - {duplicate['amount']:,.0f})."
            )

        cursor.execute('''
            INSERT INTO documents 
            (doc_type, doc_number, doc_date, supplier_id, supplier_name, description, 
             amount, expense_id, project_id, category_id, status, file_path, created_by, vat_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (doc_type, doc_number, doc_date, supplier_id, supplier_name, description,
              amount, expense_id, project_id, category_id, status, file_path, created_by, vat_rate))
        self.conn.commit()
        return cursor.lastrowid

    def find_duplicate_invoice(self, doc_number, supplier_name, amount, exclude_document_id=None):
        """Return an existing document with the same invoice number, supplier and amount."""
        supplier_id = self._find_supplier_id(supplier_name)
        if not doc_number or not supplier_id or amount in (None, ''):
            return None
        cursor = self.conn.cursor()
        query = '''
            SELECT id, doc_number, supplier_name, amount, doc_date, status
            FROM documents
            WHERE doc_number = ? AND supplier_id = ? AND ABS(COALESCE(amount, 0) - ?) < 0.01
        '''
        params = [doc_number, supplier_id, float(amount)]
        if exclude_document_id:
            query += ' AND id <> ?'
            params.append(exclude_document_id)
        query += ' ORDER BY id LIMIT 1'
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_documents(self):
        """Lấy tất cả chứng từ."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT d.id, d.doc_type, d.doc_number, d.doc_date, d.supplier_name,
                   d.description, d.amount, p.name, d.status, d.expense_id,
                   COALESCE(d.vat_rate, 10) AS vat_rate
            FROM documents d
            LEFT JOIN projects p ON d.project_id = p.id
            ORDER BY d.doc_date DESC
        ''')
        return cursor.fetchall()

    def get_documents_by_expense(self, expense_id):
        """Lấy chứng từ theo từng nghiệp vụ chi phí."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT d.id, d.doc_type, d.doc_number, d.doc_date, d.supplier_name,
                   d.description, d.amount, d.status
            FROM documents d
            WHERE d.expense_id = ?
            ORDER BY d.doc_date DESC, d.id DESC
        ''', (expense_id,))
        return cursor.fetchall()

    def get_documents_by_type(self, doc_type):
        """Lấy chứng từ theo loại."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM documents WHERE doc_type = ? ORDER BY doc_date DESC
        ''', (doc_type,))
        return cursor.fetchall()

    def attach_file(self, document_id, file_path, expense_id=None):
        """Gắn file vào chứng từ."""
        cursor = self.conn.cursor()
        file_name = os.path.basename(file_path)

        if not document_id and expense_id:
            doc_number = self.generate_document_number('FILE')
            cursor.execute('SELECT expense_date, project_id, category_id, description, amount FROM expenses WHERE id = ?', (expense_id,))
            expense = cursor.fetchone()
            if expense:
                cursor.execute('''
                    INSERT INTO documents
                    (doc_type, doc_number, doc_date, supplier_name, description, amount,
                     expense_id, project_id, category_id, status, file_path, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    'File chứng từ', doc_number, expense['expense_date'], '',
                    expense['description'], expense['amount'], expense_id,
                    expense['project_id'], expense['category_id'], 'draft', file_path, 1
                ))
                document_id = cursor.lastrowid

        if document_id and not expense_id:
            cursor.execute('SELECT expense_id FROM documents WHERE id = ?', (document_id,))
            doc = cursor.fetchone()
            if doc:
                expense_id = doc['expense_id']

        cursor.execute('''
            INSERT INTO attachments (document_id, expense_id, file_path, file_name)
            VALUES (?, ?, ?, ?)
        ''', (document_id, expense_id, file_path, file_name))

        self.conn.commit()
        return cursor.lastrowid

    def get_attachments(self, document_id=None, expense_id=None):
        """Lấy danh sách file đính kèm."""
        cursor = self.conn.cursor()
        if expense_id:
            cursor.execute('''
                SELECT a.*, d.doc_number
                FROM attachments a
                LEFT JOIN documents d ON a.document_id = d.id
                WHERE a.expense_id = ?
                ORDER BY a.uploaded_at DESC
            ''', (expense_id,))
        else:
            cursor.execute('''
                SELECT * FROM attachments WHERE document_id = ?
            ''', (document_id,))
        return cursor.fetchall()

    def get_document_by_id(self, document_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM documents WHERE id = ?', (document_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def is_document_posted(self, document_id):
        doc = self.get_document_by_id(document_id)
        return doc and doc.get('status') == 'posted'

    def update_document(self, document_id, doc_type, doc_number, doc_date, supplier_name,
                        description, amount, expense_id, status, vat_rate=10):
        if self.is_document_posted(document_id):
            raise ValueError('Chứng từ đã ghi sổ. Cần bỏ ghi trước khi sửa.')
        assert_date_not_locked(doc_date, 'sua chung tu')
        cursor = self.conn.cursor()
        supplier_id = self._ensure_supplier(supplier_name)
        duplicate = self.find_duplicate_invoice(doc_number, supplier_name, amount, exclude_document_id=document_id)
        if duplicate:
            raise ValueError(
                f"Hoa don trung voi chung tu #{duplicate['id']} "
                f"({duplicate['supplier_name']} - {duplicate['amount']:,.0f})."
            )
        project_id = category_id = None
        if expense_id:
            cursor.execute('SELECT project_id, category_id FROM expenses WHERE id = ?', (expense_id,))
            exp = cursor.fetchone()
            if exp:
                project_id, category_id = exp['project_id'], exp['category_id']
        cursor.execute('''
            UPDATE documents SET
                doc_type=?, doc_number=?, doc_date=?, supplier_id=?, supplier_name=?, description=?,
                amount=?, expense_id=?, project_id=?, category_id=?, status=?, vat_rate=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (doc_type, doc_number, doc_date, supplier_id, supplier_name, description, amount,
              expense_id, project_id, category_id, status, vat_rate, document_id))
        self.conn.commit()

    def delete_document(self, document_id):
        if self.is_document_posted(document_id):
            raise ValueError('Chứng từ đã ghi sổ. Cần bỏ ghi trước khi xóa.')
        cursor = self.conn.cursor()
        cursor.execute('SELECT doc_date FROM documents WHERE id = ?', (document_id,))
        row = cursor.fetchone()
        if row:
            assert_date_not_locked(row['doc_date'], 'xoa chung tu')
        cursor.execute('DELETE FROM attachments WHERE document_id = ?', (document_id,))
        cursor.execute('DELETE FROM documents WHERE id = ?', (document_id,))
        self.conn.commit()

    def update_document_status(self, document_id, status):
        """Cập nhật trạng thái chứng từ."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT doc_date FROM documents WHERE id = ?', (document_id,))
        row = cursor.fetchone()
        if row:
            assert_date_not_locked(row['doc_date'], 'cap nhat trang thai chung tu')
        cursor.execute('''
            UPDATE documents SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, document_id))
        self.conn.commit()

    def validate_document_before_post(self, document_id):
        doc = self.get_document_by_id(document_id)
        if not doc:
            return [{'level': 'critical', 'message': 'Không tìm thấy chứng từ.'}]
        issues = []
        amount = float(doc.get('amount') or 0)
        vat_rate = float(doc.get('vat_rate') or 0)
        if amount <= 0:
            issues.append({'level': 'critical', 'message': 'Số tiền chứng từ phải lớn hơn 0.'})
        if vat_rate < 0 or vat_rate > 100:
            issues.append({'level': 'critical', 'message': 'VAT % phải nằm trong khoảng 0-100.'})
        if not doc.get('supplier_name'):
            issues.append({'level': 'warning', 'message': 'Chứng từ chưa có nhà cung cấp/người nhận.'})
        if not doc.get('expense_id'):
            issues.append({'level': 'warning', 'message': 'Chứng từ chưa liên kết với nghiệp vụ chi phí.'})
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM attachments WHERE document_id = ?', (document_id,))
        attachment_count = cursor.fetchone()[0]
        if not doc.get('file_path') and attachment_count == 0:
            issues.append({'level': 'warning', 'message': 'Chứng từ chưa có file scan đính kèm.'})
        return issues

    def validate_invoice_compliance(self, document_id):
        """Run a richer invoice/document validity check for review before posting."""
        doc = self.get_document_by_id(document_id)
        if not doc:
            return [{'level': 'critical', 'message': 'Không tìm thấy chứng từ.'}]

        issues = self.validate_document_before_post(document_id)
        cursor = self.conn.cursor()

        doc_number = (doc.get('doc_number') or '').strip()
        supplier = (doc.get('supplier_name') or '').strip()
        doc_type = (doc.get('doc_type') or '').lower()
        amount = float(doc.get('amount') or 0)

        if 'hóa đơn' in doc_type or 'hoa don' in doc_type or doc_number:
            if not doc_number:
                issues.append({'level': 'critical', 'message': 'Hóa đơn/chứng từ chưa có số chứng từ.'})
            elif len(doc_number) < 3:
                issues.append({'level': 'warning', 'message': 'Số chứng từ quá ngắn, cần kiểm tra lại.'})

        if doc.get('doc_date'):
            try:
                doc_date = datetime.strptime(str(doc['doc_date'])[:10], '%Y-%m-%d').date()
                today = datetime.now().date()
                if doc_date > today:
                    issues.append({'level': 'warning', 'message': 'Ngày chứng từ đang ở tương lai.'})
                if (today - doc_date).days > 730:
                    issues.append({'level': 'warning', 'message': 'Chứng từ quá cũ, cần kiểm tra kỳ hạch toán.'})
            except ValueError:
                issues.append({'level': 'critical', 'message': 'Ngày chứng từ không đúng định dạng.'})

        if supplier and re.search(r'\d{10}|\d{13}', supplier):
            tax_code = re.sub(r'\D', '', supplier)
            if len(tax_code) not in (10, 13):
                issues.append({'level': 'warning', 'message': 'Mã số thuế trong tên nhà cung cấp có vẻ không hợp lệ.'})

        if doc_number and supplier:
            duplicate = self.find_duplicate_invoice(doc_number, supplier, amount, exclude_document_id=document_id)
            if duplicate:
                issues.append({'level': 'critical', 'message': f"Trùng hóa đơn với chứng từ #{duplicate['id']}."})

        if doc.get('expense_id'):
            cursor.execute('SELECT amount, description, expense_date FROM expenses WHERE id = ?', (doc['expense_id'],))
            expense = cursor.fetchone()
            if expense:
                if abs(float(expense['amount'] or 0) - amount) > 0.01:
                    issues.append({'level': 'warning', 'message': 'Số tiền chứng từ lệch với chi phí liên kết.'})
                if str(expense['expense_date'])[:10] and doc.get('doc_date') and str(doc['doc_date'])[:10] > str(expense['expense_date'])[:10]:
                    issues.append({'level': 'info', 'message': 'Ngày chứng từ sau ngày chi phí, cần kiểm tra quy trình ghi nhận.'})

        if not issues:
            issues.append({'level': 'ok', 'message': 'Chứng từ đạt các kiểm tra hợp lệ nội bộ.'})
        return issues

    def validate_all_documents(self, limit=200):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM documents ORDER BY doc_date DESC, id DESC LIMIT ?', (limit,))
        rows = []
        for row in cursor.fetchall():
            issues = self.validate_invoice_compliance(row['id'])
            worst = self._worst_level(issues)
            rows.append({'document_id': row['id'], 'level': worst, 'issues': issues})
        return rows

    def _worst_level(self, issues):
        rank = {'critical': 3, 'warning': 2, 'info': 1, 'ok': 0}
        return max((issue.get('level', 'info') for issue in issues), key=lambda level: rank.get(level, 1))

    def post_document(self, document_id):
        self.update_document_status(document_id, 'posted')
        self._sync_document_payable(document_id)

    def unpost_document(self, document_id):
        doc = self.get_document_by_id(document_id)
        if not doc:
            raise ValueError('Không tìm thấy chứng từ')
        self.update_document_status(document_id, 'approved' if doc.get('status') == 'posted' else doc.get('status', 'draft'))
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE ar_ap_items
            SET status = 'cancelled'
            WHERE source_type = 'document' AND source_id = ?
        ''', (document_id,))
        self.conn.commit()

    def _sync_document_payable(self, document_id):
        doc = self.get_document_by_id(document_id)
        if not doc or float(doc.get('amount') or 0) <= 0:
            return
        doc_type = (doc.get('doc_type') or '').lower()
        if any(marker in doc_type for marker in ('phiếu thu', 'phieu thu')):
            return
        due_date = doc.get('doc_date') or datetime.now().strftime('%Y-%m-%d')
        try:
            due_date = (datetime.strptime(str(due_date), '%Y-%m-%d') + timedelta(days=30)).date().isoformat()
        except ValueError:
            due_date = datetime.now().date().isoformat()
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO ar_ap_items
            (partner_type, partner_name, project_id, doc_id, due_date, amount, paid_amount,
             status, notes, source_type, source_id)
            VALUES ('supplier', ?, ?, ?, ?, ?, 0, 'open', ?, 'document', ?)
            ON CONFLICT(source_type, source_id, partner_type)
            WHERE source_type IS NOT NULL AND source_id IS NOT NULL
            DO UPDATE SET
                partner_name = excluded.partner_name,
                project_id = excluded.project_id,
                doc_id = excluded.doc_id,
                due_date = excluded.due_date,
                amount = excluded.amount,
                status = CASE
                    WHEN ar_ap_items.status = 'closed' THEN ar_ap_items.status
                    ELSE 'open'
                END,
                notes = excluded.notes
        ''', (
            doc.get('supplier_name') or 'Chưa xác định',
            doc.get('project_id'), document_id, due_date,
            float(doc.get('amount') or 0),
            f"Tự sinh từ chứng từ {doc.get('doc_number') or document_id}",
            document_id,
        ))
        self.conn.commit()

    def generate_document_number(self, doc_type, doc_date=None):
        """Tạo số chứng từ tự động: tiền tố/tháng-năm/số tăng dần."""
        dt = datetime.now()
        if doc_date:
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
                try:
                    dt = datetime.strptime(str(doc_date), fmt)
                    break
                except ValueError:
                    continue
        period = dt.strftime('%Y%m')
        prefix = self._document_prefix(doc_type)
        sequence_key = f"{prefix}:{period}"
        cursor = self.conn.cursor()
        cursor.execute('SELECT last_number FROM document_sequences WHERE sequence_key = ?', (sequence_key,))
        row = cursor.fetchone()
        next_number = (row['last_number'] if row else 0) + 1
        cursor.execute('''
            INSERT INTO document_sequences (sequence_key, prefix, period, last_number, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(sequence_key) DO UPDATE SET
                last_number = excluded.last_number,
                updated_at = CURRENT_TIMESTAMP
        ''', (sequence_key, prefix, period, next_number))
        return f"{prefix}/{dt.strftime('%m%Y')}/{next_number:04d}"

    def _document_prefix(self, doc_type):
        text = (doc_type or '').lower()
        rules = [
            (('phiếu chi', 'chi tiền'), 'PC'),
            (('phiếu thu', 'thu tiền'), 'PT'),
            (('hóa đơn', 'hoa don'), 'HD'),
            (('tạm ứng', 'tam ung'), 'TU'),
            (('thanh toán', 'thanh toan'), 'TT'),
            (('nhập kho', 'nhap kho'), 'PNK'),
            (('xuất kho', 'xuat kho'), 'PXK'),
            (('file', 'đính kèm'), 'FILE'),
        ]
        for markers, prefix in rules:
            if any(marker in text for marker in markers):
                return prefix
        raw = ''.join(ch for ch in (doc_type or 'CT').upper() if ch.isalnum())
        return raw[:6] or 'CT'

    def _ensure_supplier(self, supplier_name):
        name = (supplier_name or '').strip()
        if not name:
            return None
        cursor = self.conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO suppliers (supplier_name) VALUES (?)', (name,))
        cursor.execute('SELECT id FROM suppliers WHERE supplier_name = ?', (name,))
        row = cursor.fetchone()
        return row['id'] if row else None

    def _find_supplier_id(self, supplier_name):
        name = (supplier_name or '').strip()
        if not name:
            return None
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM suppliers WHERE supplier_name = ?', (name,))
        row = cursor.fetchone()
        return row['id'] if row else None


class TemplateManager:
    """Quản lý mẫu chứng từ."""

    def __init__(self):
        self.templates_dir = 'templates'
        os.makedirs(self.templates_dir, exist_ok=True)

    def get_template_list(self):
        """Lấy danh sách mẫu chứng từ."""
        templates = []
        if os.path.exists(self.templates_dir):
            for file in os.listdir(self.templates_dir):
                if file.endswith('.docx'):
                    templates.append(file)
        return templates

    def fill_template(self, template_name, data):
        """Điền dữ liệu vào mẫu chứng từ."""
        try:
            from docxtpl import DocxTemplate
        except ImportError:
            raise ImportError("Cần cài docxtpl: pip install docxtpl")

        template_path = os.path.join(self.templates_dir, template_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template không tìm thấy: {template_name}")

        doc = DocxTemplate(template_path)
        doc.render(data)

        return doc
