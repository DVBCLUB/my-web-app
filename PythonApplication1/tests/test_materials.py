"""
TEST_MATERIALS - Unit tests cho materials module
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

from modules.materials import MaterialManager, AuxiliaryMaterialManager


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
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            unit TEXT,
            quantity INTEGER DEFAULT 0,
            unit_price REAL,
            category TEXT,
            supplier TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            project_id INTEGER,
            notes TEXT,
            created_by INTEGER,
            transaction_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(material_id) REFERENCES materials(id)
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
    
    conn.commit()
    conn.close()
    
    yield path
    
    # Cleanup
    os.unlink(path)
    database.get_connection = original_get_connection


@pytest.fixture
def sample_material(temp_db):
    """Tạo vật tư mẫu cho test"""
    import database
    conn = database.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO materials (code, name, unit, unit_price, category, supplier, quantity)
        VALUES ('MAT001', 'Test Material', 'kg', 10000, 'Vật liệu xây dựng', 'Supplier A', 100)
    ''')
    material_id = cursor.lastrowid
    
    # Insert project
    cursor.execute('''
        INSERT INTO projects (code, name, location, budget)
        VALUES ('PROJ001', 'Test Project', 'Hanoi', 1000000000)
    ''')
    project_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return {
        'material_id': material_id,
        'project_id': project_id
    }


class TestMaterialManager:
    """Test class cho MaterialManager"""
    
    def test_add_material(self, temp_db):
        """Test thêm vật tư mới"""
        mgr = MaterialManager()
        
        material_id = mgr.add_material(
            code='MAT002',
            name='Cement',
            unit='bag',
            unit_price=50000,
            category='Vật liệu xây dựng',
            supplier='Supplier B'
        )
        
        assert material_id is not None
        assert material_id > 0
        
        # Verify material was added
        materials = mgr.get_all_materials()
        assert len(materials) > 0
    
    def test_get_all_materials(self, temp_db, sample_material):
        """Test lấy tất cả vật tư"""
        mgr = MaterialManager()
        materials = mgr.get_all_materials()
        assert isinstance(materials, list)
        assert len(materials) >= 1
    
    def test_get_material_stock(self, temp_db, sample_material):
        """Test lấy tồn kho vật tư"""
        mgr = MaterialManager()
        stock = mgr.get_material_stock(sample_material['material_id'])
        assert stock == 100
    
    def test_update_material(self, temp_db, sample_material):
        """Test cập nhật vật tư"""
        mgr = MaterialManager()
        
        mgr.update_material(
            material_id=sample_material['material_id'],
            code='MAT001',
            name='Updated Material',
            unit='kg',
            unit_price=15000,
            category='Vật liệu xây dựng',
            supplier='Supplier A',
            status='active'
        )
        
        materials = mgr.get_all_materials()
        updated = [m for m in materials if m[0] == sample_material['material_id']][0]
        assert updated[2] == 'Updated Material'  # name is at index 2
        assert updated[4] == 15000  # unit_price is at index 4
    
    def test_add_inventory_transaction_import(self, temp_db, sample_material):
        """Test thêm giao dịch nhập kho"""
        mgr = MaterialManager()
        
        transaction_id = mgr.add_inventory_transaction(
            material_id=sample_material['material_id'],
            transaction_type='import',
            quantity=50,
            project_id=sample_material['project_id'],
            notes='Import test',
            created_by=1
        )
        
        assert transaction_id is not None
        assert transaction_id > 0
        
        # Check stock increased
        stock = mgr.get_material_stock(sample_material['material_id'])
        assert stock == 150  # 100 + 50
    
    def test_add_inventory_transaction_export(self, temp_db, sample_material):
        """Test thêm giao dịch xuất kho"""
        mgr = MaterialManager()
        
        transaction_id = mgr.add_inventory_transaction(
            material_id=sample_material['material_id'],
            transaction_type='export',
            quantity=30,
            project_id=sample_material['project_id'],
            notes='Export test',
            created_by=1
        )
        
        assert transaction_id is not None
        assert transaction_id > 0
        
        # Check stock decreased
        stock = mgr.get_material_stock(sample_material['material_id'])
        assert stock == 70  # 100 - 30
    
    def test_add_inventory_transaction_insufficient_stock(self, temp_db, sample_material):
        """Test xuất kho khi tồn kho không đủ"""
        mgr = MaterialManager()
        
        with pytest.raises(ValueError, match="Tồn kho không đủ"):
            mgr.add_inventory_transaction(
                material_id=sample_material['material_id'],
                transaction_type='export',
                quantity=200,  # More than available
                project_id=sample_material['project_id'],
                notes='Export test',
                created_by=1
            )
    
    def test_add_inventory_transaction_invalid_quantity(self, temp_db, sample_material):
        """Test giao dịch với số lượng không hợp lệ"""
        mgr = MaterialManager()
        
        with pytest.raises(ValueError, match="Số lượng phải lớn hơn 0"):
            mgr.add_inventory_transaction(
                material_id=sample_material['material_id'],
                transaction_type='import',
                quantity=0,
                project_id=sample_material['project_id'],
                notes='Test',
                created_by=1
            )
    
    def test_add_inventory_transaction_invalid_type(self, temp_db, sample_material):
        """Test giao dịch với loại không hợp lệ"""
        mgr = MaterialManager()
        
        with pytest.raises(ValueError, match="Loại giao dịch kho không hợp lệ"):
            mgr.add_inventory_transaction(
                material_id=sample_material['material_id'],
                transaction_type='invalid',
                quantity=10,
                project_id=sample_material['project_id'],
                notes='Test',
                created_by=1
            )
    
    def test_get_inventory_history(self, temp_db, sample_material):
        """Test lấy lịch sử giao dịch kho"""
        mgr = MaterialManager()
        
        # Add some transactions
        mgr.add_inventory_transaction(
            material_id=sample_material['material_id'],
            transaction_type='import',
            quantity=50,
            project_id=sample_material['project_id'],
            notes='Import 1',
            created_by=1
        )
        
        mgr.add_inventory_transaction(
            material_id=sample_material['material_id'],
            transaction_type='export',
            quantity=20,
            project_id=sample_material['project_id'],
            notes='Export 1',
            created_by=1
        )
        
        history = mgr.get_inventory_history(material_id=sample_material['material_id'])
        assert isinstance(history, list)
        assert len(history) >= 2
    
    def test_get_material_choices(self, temp_db, sample_material):
        """Test lấy danh sách vật tư cho combobox"""
        mgr = MaterialManager()
        choices = mgr.get_material_choices()
        assert isinstance(choices, list)
        assert len(choices) >= 1
    
    def test_get_material_value_by_project(self, temp_db, sample_material):
        """Test lấy giá trị vật tư theo dự án"""
        mgr = MaterialManager()
        
        # Add export transaction
        mgr.add_inventory_transaction(
            material_id=sample_material['material_id'],
            transaction_type='export',
            quantity=10,
            project_id=sample_material['project_id'],
            notes='Export for project',
            created_by=1
        )
        
        values = mgr.get_material_value_by_project(sample_material['project_id'])
        assert isinstance(values, list)


class TestAuxiliaryMaterialManager:
    """Test class cho AuxiliaryMaterialManager"""
    
    def test_get_auxiliary_materials(self, temp_db):
        """Test lấy danh sách vật tư phụ"""
        import database
        conn = database.get_connection()
        cursor = conn.cursor()
        
        # Add auxiliary material
        cursor.execute('''
            INSERT INTO materials (code, name, unit, unit_price, category, supplier)
            VALUES ('AUX001', 'Auxiliary Material', 'pcs', 5000, 'Vật tư phụ', 'Supplier C')
        ''')
        conn.commit()
        conn.close()
        
        mgr = AuxiliaryMaterialManager()
        aux_materials = mgr.get_auxiliary_materials()
        assert isinstance(aux_materials, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
