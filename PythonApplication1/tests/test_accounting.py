"""
TEST_ACCOUNTING - Unit tests cho accounting module
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, date
import sys
from pathlib import Path

# Add app root directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import get_connection, init_database
from modules.accounting import ExpenseManager, ProjectManager


@pytest.fixture
def temp_db():
    """Tạo database tạm thời cho test"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Override database path
    import database
    original_get_connection = database.get_connection
    database.get_connection = lambda: sqlite3.connect(path, timeout=30)
    database.get_connection().row_factory = sqlite3.Row
    
    # Initialize database
    conn = database.get_connection()
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            email TEXT,
            role TEXT DEFAULT 'employee',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            location TEXT,
            start_date DATE,
            end_date DATE,
            budget REAL,
            status TEXT DEFAULT 'active',
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expense_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            parent_id INTEGER,
            description TEXT,
            FOREIGN KEY(parent_id) REFERENCES expense_categories(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date DATE NOT NULL,
            project_id INTEGER,
            category_id INTEGER NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            paid_by TEXT,
            payment_method TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            department TEXT,
            purpose TEXT,
            item_list TEXT,
            accounting_staff TEXT,
            department_head TEXT,
            prepared_by TEXT,
            attachments TEXT,
            work_item_id INTEGER,
            contract_id INTEGER,
            debit_account_id TEXT,
            credit_account_id TEXT,
            fiscal_period TEXT,
            advance_request_id INTEGER,
            invoice_id INTEGER,
            is_ocr_imported INTEGER DEFAULT 0,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(category_id) REFERENCES expense_categories(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date DATE NOT NULL,
            description TEXT,
            debit_account TEXT,
            credit_account TEXT,
            amount REAL NOT NULL,
            expense_id INTEGER,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(expense_id) REFERENCES expenses(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS approval_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id INTEGER,
            approved_by INTEGER,
            approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY(expense_id) REFERENCES expenses(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_type TEXT NOT NULL,
            doc_number TEXT,
            doc_date DATE,
            supplier_id INTEGER,
            supplier_name TEXT,
            description TEXT,
            amount REAL,
            expense_id INTEGER,
            project_id INTEGER,
            category_id INTEGER,
            status TEXT DEFAULT 'draft',
            file_path TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(expense_id) REFERENCES expenses(id),
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(category_id) REFERENCES expense_categories(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            expense_id INTEGER,
            file_path TEXT NOT NULL,
            file_name TEXT,
            file_type TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(document_id) REFERENCES documents(id),
            FOREIGN KEY(expense_id) REFERENCES expenses(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    yield path
    
    # Cleanup
    os.unlink(path)
    database.get_connection = original_get_connection


@pytest.fixture
def sample_data(temp_db):
    """Tạo dữ liệu mẫu cho test"""
    import database
    conn = database.get_connection()
    cursor = conn.cursor()
    
    # Insert user
    cursor.execute('''
        INSERT INTO users (username, password, full_name, role)
        VALUES ('test_user', 'password', 'Test User', 'accountant')
    ''')
    user_id = cursor.lastrowid
    
    # Insert project
    cursor.execute('''
        INSERT INTO projects (code, name, location, budget, created_by)
        VALUES ('PROJ001', 'Test Project', 'Hanoi', 1000000000, ?)
    ''', (user_id,))
    project_id = cursor.lastrowid
    
    # Insert category
    cursor.execute('''
        INSERT INTO expense_categories (code, name)
        VALUES ('VT', 'Vật tư')
    ''')
    category_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return {
        'user_id': user_id,
        'project_id': project_id,
        'category_id': category_id
    }


class TestExpenseManager:
    """Test class cho ExpenseManager"""
    
    def test_add_expense(self, temp_db, sample_data):
        """Test thêm chi phí mới"""
        mgr = ExpenseManager()
        
        expense_id = mgr.add_expense(
            expense_date='2024-01-15',
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            description='Test expense',
            amount=1000000,
            paid_by='Test User',
            payment_method='Tiền mặt',
            notes='Test notes',
            created_by=sample_data['user_id']
        )
        
        assert expense_id is not None
        assert expense_id > 0
        
        # Verify expense was added
        expense = mgr.get_expense_by_id(expense_id)
        assert expense is not None
        assert expense['description'] == 'Test expense'
        assert expense['amount'] == 1000000
    
    def test_get_expense_by_id(self, temp_db, sample_data):
        """Test lấy chi phí theo ID"""
        mgr = ExpenseManager()
        
        expense_id = mgr.add_expense(
            expense_date='2024-01-15',
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            description='Test expense',
            amount=1000000,
            paid_by='Test User',
            payment_method='Tiền mặt',
            notes='Test notes',
            created_by=sample_data['user_id']
        )
        
        expense = mgr.get_expense_by_id(expense_id)
        assert expense is not None
        assert expense['id'] == expense_id
        assert expense['description'] == 'Test expense'
    
    def test_get_expense_by_id_not_found(self, temp_db):
        """Test lấy chi phí không tồn tại"""
        mgr = ExpenseManager()
        expense = mgr.get_expense_by_id(99999)
        assert expense is None
    
    def test_update_expense(self, temp_db, sample_data):
        """Test cập nhật chi phí"""
        mgr = ExpenseManager()
        
        expense_id = mgr.add_expense(
            expense_date='2024-01-15',
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            description='Test expense',
            amount=1000000,
            paid_by='Test User',
            payment_method='Tiền mặt',
            notes='Test notes',
            created_by=sample_data['user_id']
        )
        
        mgr.update_expense(
            expense_id=expense_id,
            expense_date='2024-01-16',
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            description='Updated expense',
            amount=2000000,
            paid_by='Test User',
            payment_method='Chuyển khoản',
            notes='Updated notes'
        )
        
        expense = mgr.get_expense_by_id(expense_id)
        assert expense['description'] == 'Updated expense'
        assert expense['amount'] == 2000000
        assert expense['payment_method'] == 'Chuyển khoản'
    
    def test_delete_expense(self, temp_db, sample_data):
        """Test xóa chi phí"""
        mgr = ExpenseManager()
        
        expense_id = mgr.add_expense(
            expense_date='2024-01-15',
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            description='Test expense',
            amount=1000000,
            paid_by='Test User',
            payment_method='Tiền mặt',
            notes='Test notes',
            created_by=sample_data['user_id']
        )
        
        mgr.delete_expense(expense_id)
        
        expense = mgr.get_expense_by_id(expense_id)
        assert expense is None
    
    def test_is_expense_posted(self, temp_db, sample_data):
        """Test kiểm tra chi phí đã ghi sổ"""
        mgr = ExpenseManager()
        
        expense_id = mgr.add_expense(
            expense_date='2024-01-15',
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            description='Test expense',
            amount=1000000,
            paid_by='Test User',
            payment_method='Tiền mặt',
            notes='Test notes',
            created_by=sample_data['user_id']
        )
        
        # Initially not posted
        assert mgr.is_expense_posted(expense_id) == False
    
    def test_get_statistics(self, temp_db, sample_data):
        """Test lấy thống kê"""
        mgr = ExpenseManager()
        
        # Add some expenses
        mgr.add_expense(
            expense_date='2024-01-15',
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            description='Test expense 1',
            amount=1000000,
            paid_by='Test User',
            payment_method='Tiền mặt',
            notes='Test notes',
            created_by=sample_data['user_id']
        )
        
        mgr.add_expense(
            expense_date='2024-01-16',
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            description='Test expense 2',
            amount=2000000,
            paid_by='Test User',
            payment_method='Tiền mặt',
            notes='Test notes',
            created_by=sample_data['user_id']
        )
        
        stats = mgr.get_statistics()
        assert 'total_expenses' in stats
        assert 'monthly_expenses' in stats
        assert 'total_projects' in stats
        assert 'total_documents' in stats
        assert stats['total_expenses'] == 3000000


class TestProjectManager:
    """Test class cho ProjectManager"""
    
    def test_add_project(self, temp_db, sample_data):
        """Test thêm dự án mới"""
        mgr = ProjectManager()
        
        project_id = mgr.add_project(
            code='PROJ002',
            name='Test Project 2',
            location='Ho Chi Minh',
            start_date='2024-01-01',
            end_date='2024-12-31',
            budget=5000000000,
            created_by=sample_data['user_id']
        )
        
        assert project_id is not None
        assert project_id > 0
    
    def test_get_all_projects(self, temp_db):
        """Test lấy tất cả dự án"""
        mgr = ProjectManager()
        projects = mgr.get_all_projects()
        assert isinstance(projects, list)
    
    def test_get_project_budget_summary(self, temp_db, sample_data):
        """Test lấy tóm tắt ngân sách dự án"""
        mgr = ProjectManager()
        
        summary = mgr.get_project_budget_summary(sample_data['project_id'])
        assert 'budget' in summary
        assert 'spent' in summary
        assert 'remaining' in summary
        assert 'percentage' in summary


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
