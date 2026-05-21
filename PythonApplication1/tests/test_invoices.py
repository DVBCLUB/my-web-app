"""
TEST_INVOICES - Unit tests cho invoices module
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

from modules.invoices import DocumentManager, TemplateManager


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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expense_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            parent_id INTEGER,
            description TEXT
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_name TEXT UNIQUE NOT NULL,
            tax_code TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS document_sequences (
            sequence_key TEXT PRIMARY KEY,
            prefix TEXT,
            period TEXT,
            last_number INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        INSERT INTO projects (code, name, location, budget)
        VALUES ('PROJ001', 'Test Project', 'Hanoi', 1000000000)
    ''')
    project_id = cursor.lastrowid
    
    # Insert category
    cursor.execute('''
        INSERT INTO expense_categories (code, name)
        VALUES ('VT', 'Vật tư')
    ''')
    category_id = cursor.lastrowid
    
    # Insert expense
    cursor.execute('''
        INSERT INTO expenses (expense_date, project_id, category_id, description, amount, paid_by, payment_method, created_by)
        VALUES ('2024-01-15', ?, ?, 'Test expense', 1000000, 'Test User', 'Tiền mặt', ?)
    ''', (project_id, category_id, user_id))
    expense_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return {
        'user_id': user_id,
        'project_id': project_id,
        'category_id': category_id,
        'expense_id': expense_id
    }


class TestDocumentManager:
    """Test class cho DocumentManager"""
    
    def test_add_document(self, temp_db, sample_data):
        """Test thêm chứng từ mới"""
        mgr = DocumentManager()
        
        doc_id = mgr.add_document(
            doc_type='Hóa đơn',
            doc_number='HD001',
            doc_date='2024-01-15',
            supplier_name='Supplier A',
            description='Test document',
            amount=1000000,
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            file_path='/path/to/file.pdf',
            created_by=sample_data['user_id']
        )
        
        assert doc_id is not None
        assert doc_id > 0
    
    def test_add_document_auto_number(self, temp_db, sample_data):
        """Test thêm chứng từ với số tự động"""
        mgr = DocumentManager()
        
        doc_id = mgr.add_document(
            doc_type='Hóa đơn',
            doc_number=None,  # Auto generate
            doc_date='2024-01-15',
            supplier_name='Supplier A',
            description='Test document',
            amount=1000000,
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            file_path='/path/to/file.pdf',
            created_by=sample_data['user_id']
        )
        
        assert doc_id is not None
        assert doc_id > 0
        
        # Check document has auto-generated number
        doc = mgr.get_document_by_id(doc_id)
        assert doc is not None
        assert doc['doc_number'] is not None
    
    def test_get_document_by_id(self, temp_db, sample_data):
        """Test lấy chứng từ theo ID"""
        mgr = DocumentManager()
        
        doc_id = mgr.add_document(
            doc_type='Hóa đơn',
            doc_number='HD002',
            doc_date='2024-01-15',
            supplier_name='Supplier A',
            description='Test document',
            amount=1000000,
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            file_path='/path/to/file.pdf',
            created_by=sample_data['user_id']
        )
        
        doc = mgr.get_document_by_id(doc_id)
        assert doc is not None
        assert doc['id'] == doc_id
        assert doc['doc_number'] == 'HD002'
    
    def test_get_document_by_id_not_found(self, temp_db):
        """Test lấy chứng từ không tồn tại"""
        mgr = DocumentManager()
        doc = mgr.get_document_by_id(99999)
        assert doc is None
    
    def test_get_all_documents(self, temp_db, sample_data):
        """Test lấy tất cả chứng từ"""
        mgr = DocumentManager()
        
        mgr.add_document(
            doc_type='Hóa đơn',
            doc_number='HD003',
            doc_date='2024-01-15',
            supplier_name='Supplier A',
            description='Test document 1',
            amount=1000000,
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            file_path='/path/to/file1.pdf',
            created_by=sample_data['user_id']
        )
        
        mgr.add_document(
            doc_type='Phiếu chi',
            doc_number='PC001',
            doc_date='2024-01-16',
            supplier_name='Supplier B',
            description='Test document 2',
            amount=2000000,
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            file_path='/path/to/file2.pdf',
            created_by=sample_data['user_id']
        )
        
        documents = mgr.get_all_documents()
        assert isinstance(documents, list)
        assert len(documents) >= 2
    
    def test_get_documents_by_expense(self, temp_db, sample_data):
        """Test lấy chứng từ theo expense"""
        mgr = DocumentManager()
        
        doc_id = mgr.add_document(
            doc_type='Hóa đơn',
            doc_number='HD004',
            doc_date='2024-01-15',
            supplier_name='Supplier A',
            description='Test document',
            amount=1000000,
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            file_path='/path/to/file.pdf',
            created_by=sample_data['user_id'],
            expense_id=sample_data['expense_id']
        )
        
        documents = mgr.get_documents_by_expense(sample_data['expense_id'])
        assert isinstance(documents, list)
        assert len(documents) >= 1
    
    def test_get_documents_by_type(self, temp_db, sample_data):
        """Test lấy chứng từ theo loại"""
        mgr = DocumentManager()
        
        mgr.add_document(
            doc_type='Hóa đơn',
            doc_number='HD005',
            doc_date='2024-01-15',
            supplier_name='Supplier A',
            description='Test document',
            amount=1000000,
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            file_path='/path/to/file.pdf',
            created_by=sample_data['user_id']
        )
        
        documents = mgr.get_documents_by_type('Hóa đơn')
        assert isinstance(documents, list)
        assert len(documents) >= 1
    
    def test_update_document(self, temp_db, sample_data):
        """Test cập nhật chứng từ"""
        mgr = DocumentManager()
        
        doc_id = mgr.add_document(
            doc_type='Hóa đơn',
            doc_number='HD006',
            doc_date='2024-01-15',
            supplier_name='Supplier A',
            description='Test document',
            amount=1000000,
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            file_path='/path/to/file.pdf',
            created_by=sample_data['user_id']
        )
        
        mgr.update_document(
            document_id=doc_id,
            doc_type='Phiếu chi',
            doc_number='PC002',
            doc_date='2024-01-16',
            supplier_name='Supplier B',
            description='Updated document',
            amount=2000000,
            expense_id=None,
            status='approved'
        )
        
        doc = mgr.get_document_by_id(doc_id)
        assert doc['description'] == 'Updated document'
        assert doc['amount'] == 2000000
        assert doc['status'] == 'approved'
    
    def test_delete_document(self, temp_db, sample_data):
        """Test xóa chứng từ"""
        mgr = DocumentManager()
        
        doc_id = mgr.add_document(
            doc_type='Hóa đơn',
            doc_number='HD007',
            doc_date='2024-01-15',
            supplier_name='Supplier A',
            description='Test document',
            amount=1000000,
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            file_path='/path/to/file.pdf',
            created_by=sample_data['user_id']
        )
        
        mgr.delete_document(doc_id)
        
        doc = mgr.get_document_by_id(doc_id)
        assert doc is None
    
    def test_update_document_status(self, temp_db, sample_data):
        """Test cập nhật trạng thái chứng từ"""
        mgr = DocumentManager()
        
        doc_id = mgr.add_document(
            doc_type='Hóa đơn',
            doc_number='HD008',
            doc_date='2024-01-15',
            supplier_name='Supplier A',
            description='Test document',
            amount=1000000,
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            file_path='/path/to/file.pdf',
            created_by=sample_data['user_id']
        )
        
        mgr.update_document_status(doc_id, 'approved')
        
        doc = mgr.get_document_by_id(doc_id)
        assert doc['status'] == 'approved'
    
    def test_post_document(self, temp_db, sample_data):
        """Test ghi sổ chứng từ"""
        mgr = DocumentManager()
        
        doc_id = mgr.add_document(
            doc_type='Hóa đơn',
            doc_number='HD009',
            doc_date='2024-01-15',
            supplier_name='Supplier A',
            description='Test document',
            amount=1000000,
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            file_path='/path/to/file.pdf',
            created_by=sample_data['user_id']
        )
        
        mgr.post_document(doc_id)
        
        doc = mgr.get_document_by_id(doc_id)
        assert doc['status'] == 'posted'
    
    def test_is_document_posted(self, temp_db, sample_data):
        """Test kiểm tra chứng từ đã ghi sổ"""
        mgr = DocumentManager()
        
        doc_id = mgr.add_document(
            doc_type='Hóa đơn',
            doc_number='HD010',
            doc_date='2024-01-15',
            supplier_name='Supplier A',
            description='Test document',
            amount=1000000,
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            file_path='/path/to/file.pdf',
            created_by=sample_data['user_id']
        )
        
        # Initially not posted
        assert mgr.is_document_posted(doc_id) == False
        
        # Post the document
        mgr.post_document(doc_id)
        
        # Now should be posted
        assert mgr.is_document_posted(doc_id) == True
    
    def test_find_duplicate_invoice(self, temp_db, sample_data):
        """Test tìm hóa đơn trùng"""
        mgr = DocumentManager()
        
        # Add first document
        mgr.add_document(
            doc_type='Hóa đơn',
            doc_number='HD011',
            doc_date='2024-01-15',
            supplier_name='Supplier A',
            description='Test document',
            amount=1000000,
            project_id=sample_data['project_id'],
            category_id=sample_data['category_id'],
            file_path='/path/to/file.pdf',
            created_by=sample_data['user_id']
        )
        
        # Try to add duplicate
        with pytest.raises(ValueError, match="Hoa don trung"):
            mgr.add_document(
                doc_type='Hóa đơn',
                doc_number='HD011',  # Same number
                doc_date='2024-01-15',
                supplier_name='Supplier A',  # Same supplier
                description='Test document',
                amount=1000000,  # Same amount
                project_id=sample_data['project_id'],
                category_id=sample_data['category_id'],
                file_path='/path/to/file.pdf',
                created_by=sample_data['user_id']
            )
    
    def test_generate_document_number(self, temp_db, sample_data):
        """Test tạo số chứng từ tự động"""
        mgr = DocumentManager()
        
        # Generate for different types
        num1 = mgr.generate_document_number('Hóa đơn', '2024-01-15')
        assert num1 is not None
        assert 'HD' in num1
        
        num2 = mgr.generate_document_number('Phiếu chi', '2024-01-15')
        assert num2 is not None
        assert 'PC' in num2
        
        num3 = mgr.generate_document_number('Phiếu thu', '2024-01-15')
        assert num3 is not None
        assert 'PT' in num3


class TestTemplateManager:
    """Test class cho TemplateManager"""
    
    def test_get_template_list(self, temp_db):
        """Test lấy danh sách template"""
        import tempfile
        import os
        
        # Create temporary templates directory
        templates_dir = tempfile.mkdtemp()
        
        # Create a sample template file
        template_path = os.path.join(templates_dir, 'template1.docx')
        with open(template_path, 'w') as f:
            f.write('test')
        
        mgr = TemplateManager()
        mgr.templates_dir = templates_dir
        
        templates = mgr.get_template_list()
        assert isinstance(templates, list)
        
        # Cleanup
        os.unlink(template_path)
        os.rmdir(templates_dir)
    
    def test_fill_template_missing_docxtpl(self, temp_db):
        """Test điền template khi không có docxtpl"""
        mgr = TemplateManager()
        
        with pytest.raises(ImportError, match="Cần cài docxtpl"):
            mgr.fill_template('template.docx', {})


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
