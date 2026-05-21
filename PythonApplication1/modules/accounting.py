"""
MODULE ACCOUNTING - Quản lý hạch toán & chi phí
"""

import sqlite3
from database import ConnectionPerRequestMixin
from datetime import datetime, timedelta
from modules.fiscal_lock import assert_date_not_locked
from utils.logger import get_logger
from typing import Optional, Dict, List, Any, Tuple

logger = get_logger(__name__)


class ExpenseManager(ConnectionPerRequestMixin):
    """Quản lý chi phí công ty."""

    def __init__(self):
        pass

    def add_expense(self, expense_date: str, project_id: Optional[int], category_id: int, 
                   description: str, amount: float, paid_by: str, payment_method: str, 
                   notes: str, created_by: int,
                   extra_fields: Optional[Dict[str, Any]] = None, 
                   work_item_id: Optional[int] = None, 
                   contract_id: Optional[int] = None) -> int:
        """Thêm chi phí mới."""
        try:
            project_id = int(project_id) if project_id else None
            category_id = int(category_id)
            work_item_id = int(work_item_id) if work_item_id else None
            contract_id = int(contract_id) if contract_id else None
            extra_fields = extra_fields or {}
            fiscal_period = str(expense_date)[:7] if expense_date else None
            assert_date_not_locked(expense_date, 'them chi phi')
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO expenses 
                (expense_date, project_id, category_id, description, amount, 
                 paid_by, payment_method, status, notes, created_by,
                 department, purpose, item_list, accounting_staff, department_head,
                 prepared_by, attachments, work_item_id, contract_id,
                 debit_account_id, credit_account_id, fiscal_period,
                 advance_request_id, invoice_id, is_ocr_imported)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (expense_date, project_id, category_id, description, amount,
                  paid_by, payment_method, 'pending', notes, created_by,
                  extra_fields.get('department', ''),
                  extra_fields.get('purpose', ''),
                  extra_fields.get('item_list', ''),
                  extra_fields.get('accounting_staff', ''),
                  extra_fields.get('department_head', ''),
                  extra_fields.get('prepared_by', ''),
                  extra_fields.get('attachments', ''),
                  work_item_id, contract_id,
                  extra_fields.get('debit_account_id'),
                  extra_fields.get('credit_account_id'),
                  extra_fields.get('fiscal_period', fiscal_period),
                  extra_fields.get('advance_request_id'),
                  extra_fields.get('invoice_id'),
                  1 if extra_fields.get('is_ocr_imported') else 0))
            self.conn.commit()
            expense_id = cursor.lastrowid
            logger.info(f"Added expense with ID: {expense_id}")
            return expense_id
        except Exception as e:
            logger.error(f"Error adding expense: {e}", exc_info=True)
            raise

    def get_expense_by_id(self, expense_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM expenses WHERE id = ?', (expense_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def find_duplicate_expense(self, expense_date: str, project_id: Optional[int],
                               category_id: int, description: str,
                               amount: float, exclude_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Tìm dòng chi phí có cùng ngày, dự án, loại, mô tả và số tiền."""
        cursor = self.conn.cursor()
        params = [
            expense_date,
            int(project_id) if project_id else 0,
            int(category_id),
            (description or '').strip().lower(),
            round(float(amount or 0), 0),
        ]
        sql = '''
            SELECT id, expense_date, project_id, category_id, description, amount, status
            FROM expenses
            WHERE expense_date = ?
              AND COALESCE(project_id, 0) = ?
              AND category_id = ?
              AND LOWER(TRIM(COALESCE(description, ''))) = ?
              AND ROUND(COALESCE(amount, 0), 0) = ?
        '''
        if exclude_id:
            sql += ' AND id <> ?'
            params.append(int(exclude_id))
        sql += ' ORDER BY id DESC LIMIT 1'
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def is_expense_posted(self, expense_id: int) -> bool:
        expense = self.get_expense_by_id(expense_id)
        if not expense:
            return False
        if expense.get('status') == 'posted':
            return True
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM journal_entries WHERE expense_id = ?', (expense_id,))
        return cursor.fetchone()[0] > 0

    def update_expense(self, expense_id: int, expense_date: str, project_id: Optional[int], 
                       category_id: int, description: str, amount: float, 
                       paid_by: str, payment_method: str, notes: str,
                       extra_fields: Optional[Dict[str, Any]] = None, 
                       work_item_id: Optional[int] = None, 
                       contract_id: Optional[int] = None) -> None:
        if self.is_expense_posted(expense_id):
            raise ValueError('Chi phí đã ghi sổ. Cần bỏ ghi trước khi sửa.')
        assert_date_not_locked(expense_date, 'sua chi phi')
        project_id = int(project_id) if project_id else None
        category_id = int(category_id)
        work_item_id = int(work_item_id) if work_item_id else None
        contract_id = int(contract_id) if contract_id else None
        extra_fields = extra_fields or {}
        fiscal_period = str(expense_date)[:7] if expense_date else None
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE expenses SET
                expense_date=?, project_id=?, category_id=?, description=?, amount=?,
                paid_by=?, payment_method=?, notes=?,
                department=?, purpose=?, item_list=?, accounting_staff=?,
                department_head=?, prepared_by=?, attachments=?,
                work_item_id=?, contract_id=?, debit_account_id=?, credit_account_id=?,
                fiscal_period=?, advance_request_id=?, invoice_id=?, is_ocr_imported=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (
            expense_date, project_id, category_id, description, amount,
            paid_by, payment_method, notes,
            extra_fields.get('department', ''),
            extra_fields.get('purpose', ''),
            extra_fields.get('item_list', ''),
            extra_fields.get('accounting_staff', ''),
            extra_fields.get('department_head', ''),
            extra_fields.get('prepared_by', ''),
            extra_fields.get('attachments', ''),
            work_item_id, contract_id,
            extra_fields.get('debit_account_id'),
            extra_fields.get('credit_account_id'),
            extra_fields.get('fiscal_period', fiscal_period),
            extra_fields.get('advance_request_id'),
            extra_fields.get('invoice_id'),
            1 if extra_fields.get('is_ocr_imported') else 0,
            expense_id,
        ))
        self.conn.commit()

    def delete_expense(self, expense_id: int) -> None:
        if self.is_expense_posted(expense_id):
            raise ValueError('Chi phí đã ghi sổ. Cần bỏ ghi trước khi xóa.')
        cursor = self.conn.cursor()
        cursor.execute('SELECT expense_date FROM expenses WHERE id = ?', (expense_id,))
        row = cursor.fetchone()
        if row:
            assert_date_not_locked(row['expense_date'], 'xoa chi phi')
        cursor.execute('DELETE FROM approval_logs WHERE expense_id = ?', (expense_id,))
        cursor.execute('UPDATE documents SET expense_id = NULL WHERE expense_id = ?', (expense_id,))
        cursor.execute('UPDATE attachments SET expense_id = NULL WHERE expense_id = ?', (expense_id,))
        cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
        self.conn.commit()

    def get_all_expenses(self) -> List[sqlite3.Row]:
        """Lấy tất cả chi phí."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT e.id, e.expense_date, p.name, ec.name, e.description, 
                   e.amount, e.status,
                   COUNT(DISTINCT d.id) AS document_count,
                   COUNT(DISTINCT a.id) AS attachment_count
            FROM expenses e
            LEFT JOIN projects p ON e.project_id = p.id
            LEFT JOIN expense_categories ec ON e.category_id = ec.id
            LEFT JOIN documents d ON d.expense_id = e.id
            LEFT JOIN attachments a ON a.expense_id = e.id
            GROUP BY e.id
            ORDER BY e.expense_date DESC
        ''')
        return cursor.fetchall()

    def get_recent_expenses(self, limit: int = 10) -> List[sqlite3.Row]:
        """Lấy chi phí gần đây."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT e.id, e.expense_date, p.name, ec.name, e.amount, e.status
            FROM expenses e
            LEFT JOIN projects p ON e.project_id = p.id
            LEFT JOIN expense_categories ec ON e.category_id = ec.id
            ORDER BY e.expense_date DESC
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()

    def get_expense_choices(self):
        """Lấy danh sách chi phí để chọn khi gắn chứng từ/file."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT e.id, e.expense_date, COALESCE(p.name, 'Không có dự án'),
                   COALESCE(ec.name, 'Chưa phân loại'), e.description, e.amount
            FROM expenses e
            LEFT JOIN projects p ON e.project_id = p.id
            LEFT JOIN expense_categories ec ON e.category_id = ec.id
            ORDER BY e.expense_date DESC, e.id DESC
        ''')
        return cursor.fetchall()

    def get_statistics(self) -> Dict[str, Any]:
        """Lấy thống kê chi phí."""
        cursor = self.conn.cursor()

        # Tổng chi phí
        cursor.execute('SELECT SUM(amount) FROM expenses')
        total_expenses = cursor.fetchone()[0] or 0

        # Chi phí tháng này
        today = datetime.now()
        first_day = today.replace(day=1)
        cursor.execute('''
            SELECT SUM(amount) FROM expenses 
            WHERE expense_date >= ?
        ''', (first_day.date(),))
        monthly_expenses = cursor.fetchone()[0] or 0

        # Số dự án
        cursor.execute('SELECT COUNT(*) FROM projects WHERE status = "active"')
        total_projects = cursor.fetchone()[0]

        # Số chứng từ
        cursor.execute('SELECT COUNT(*) FROM documents')
        total_documents = cursor.fetchone()[0]

        return {
            'total_expenses': total_expenses,
            'monthly_expenses': monthly_expenses,
            'total_projects': total_projects,
            'total_documents': total_documents,
        }

    def get_expenses_by_category(self):
        """Lấy chi phí theo danh mục."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT ec.name, SUM(e.amount) as total
            FROM expenses e
            JOIN expense_categories ec ON e.category_id = ec.id
            GROUP BY e.category_id
            ORDER BY total DESC
        ''')
        return cursor.fetchall()

    def get_expenses_by_project(self):
        """Lấy chi phí theo dự án."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT p.name, SUM(e.amount) as total
            FROM expenses e
            LEFT JOIN projects p ON e.project_id = p.id
            GROUP BY e.project_id
            ORDER BY total DESC
        ''')
        return cursor.fetchall()

    def create_journal_entry(self, entry_date, description, debit_acc, 
                            credit_acc, amount, expense_id, created_by):
        """Tạo bút toán."""
        assert_date_not_locked(entry_date, 'tao but toan')
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO journal_entries 
            (entry_date, description, debit_account, credit_account, amount, expense_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (entry_date, description, debit_acc, credit_acc, amount, expense_id, created_by))
        self.conn.commit()
        return cursor.lastrowid

    def get_account_balance(self, account_code):
        """Lấy số dư tài khoản."""
        cursor = self.conn.cursor()

        # Tính tổng Nợ
        cursor.execute('''
            SELECT SUM(amount) FROM journal_entries 
            WHERE debit_account = ?
        ''', (account_code,))
        debit = cursor.fetchone()[0] or 0

        # Tính tổng Có
        cursor.execute('''
            SELECT SUM(amount) FROM journal_entries 
            WHERE credit_account = ?
        ''', (account_code,))
        credit = cursor.fetchone()[0] or 0

        return debit - credit


class ProjectManager(ConnectionPerRequestMixin):
    """Quản lý dự án xây dựng."""

    def __init__(self):
        pass

    def add_project(self, code, name, location, start_date, end_date, budget, created_by):
        """Thêm dự án mới."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO projects 
            (code, name, location, start_date, end_date, budget, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (code, name, location, start_date, end_date, budget, created_by))
        self.conn.commit()
        return cursor.lastrowid

    def get_all_projects(self):
        """Lấy tất cả dự án."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM projects ORDER BY start_date DESC
        ''')
        return cursor.fetchall()

    def get_project_budget_summary(self, project_id):
        """Lấy tóm tắt ngân sách dự án."""
        cursor = self.conn.cursor()

        # Tổng ngân sách
        cursor.execute('SELECT budget FROM projects WHERE id = ?', (project_id,))
        budget = cursor.fetchone()[0]

        # Tổng chi phí
        cursor.execute('''
            SELECT SUM(amount) FROM expenses WHERE project_id = ?
        ''', (project_id,))
        spent = cursor.fetchone()[0] or 0

        return {
            'budget': budget,
            'spent': spent,
            'remaining': budget - spent,
            'percentage': (spent / budget * 100) if budget > 0 else 0
        }
