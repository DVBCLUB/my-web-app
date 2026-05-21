"""
MODULE COMPLIANCE - Tra cứu quy định, hồ sơ bắt buộc và hệ thống tài khoản.
"""

from database import get_connection


class ComplianceManager:
    """Quản lý quy định/quy trình chứng từ theo nghiệp vụ chi phí."""

    def __init__(self):
        self.conn = get_connection()

    def get_rules(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT r.id, r.rule_code, COALESCE(ec.name, r.expense_category_code),
                   r.transaction_type, r.rule_name, r.required_documents,
                   r.warning_message, r.legal_basis
            FROM compliance_rules r
            LEFT JOIN expense_categories ec ON r.expense_category_code = ec.code
            WHERE r.active = 1
        '''

        if keyword:
            query += '''
                AND (
                    r.transaction_type LIKE ?
                    OR r.rule_name LIKE ?
                    OR r.required_documents LIKE ?
                    OR COALESCE(ec.name, '') LIKE ?
                )
            '''
            search = f'%{keyword}%'
            params.extend([search, search, search, search])

        query += ' ORDER BY r.expense_category_code, r.transaction_type'
        cursor.execute(query, params)
        return cursor.fetchall()

    def get_rule_by_category_id(self, category_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT r.id, r.rule_code, ec.name, r.transaction_type, r.rule_name,
                   r.required_documents, r.warning_message, r.legal_basis
            FROM compliance_rules r
            JOIN expense_categories ec ON r.expense_category_code = ec.code
            WHERE ec.id = ? AND r.active = 1
            ORDER BY r.id
            LIMIT 1
        ''', (category_id,))
        return cursor.fetchone()


class AccountCatalogManager:
    """Tra cứu hệ thống tài khoản kế toán."""

    def __init__(self):
        self.conn = get_connection()

    def get_accounts(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT account_code, account_name, account_type, account_level,
                   COALESCE(parent_code, ''), COALESCE(legal_basis, ''),
                   COALESCE(description, '')
            FROM accounts
            WHERE active = 1
        '''

        if keyword:
            query += '''
                AND (
                    account_code LIKE ?
                    OR account_name LIKE ?
                    OR account_type LIKE ?
                    OR COALESCE(description, '') LIKE ?
                )
            '''
            search = f'%{keyword}%'
            params.extend([search, search, search, search])

        query += ' ORDER BY account_code'
        cursor.execute(query, params)
        return cursor.fetchall()

    def add_account(self, account_code, account_name, account_type, parent_code=None,
                    description='', legal_basis='Tùy chỉnh nội bộ'):
        """Thêm tài khoản hoặc tiểu mục tài khoản kế toán."""
        parent_code = parent_code or None
        level = 1
        if parent_code:
            cursor = self.conn.cursor()
            cursor.execute('SELECT account_level FROM accounts WHERE account_code = ?', (parent_code,))
            parent = cursor.fetchone()
            level = (parent['account_level'] if parent else 1) + 1

        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO accounts
            (account_code, account_name, account_type, account_level, parent_code, legal_basis, description, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        ''', (account_code, account_name, account_type, level, parent_code, legal_basis, description))
        self.conn.commit()
        return cursor.lastrowid

    def get_parent_choices(self):
        """Lấy danh sách tài khoản cha để tạo tiểu mục."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT account_code, account_name
            FROM accounts
            WHERE active = 1
            ORDER BY account_code
        ''')
        return cursor.fetchall()
