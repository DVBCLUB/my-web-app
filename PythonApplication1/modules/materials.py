"""
MODULE MATERIALS - Quản lý vật tư & kho
"""

import sqlite3
from database import ConnectionPerRequestMixin
from datetime import datetime
from modules.fiscal_lock import assert_date_not_locked
from utils.logger import get_logger
from typing import Optional, List, Tuple

logger = get_logger(__name__)

class MaterialManager(ConnectionPerRequestMixin):
    """Quản lý vật tư."""

    def __init__(self):
        pass

    def add_material(self, code: str, name: str, unit: str, unit_price: float,
                    category: str, supplier: str, min_quantity: float = 0) -> int:
        """Thêm vật tư mới."""
        cursor = self.conn.cursor()
        unit_price = float(unit_price or 0)
        cursor.execute('''
            INSERT INTO materials 
            (code, name, unit, unit_price, average_cost, min_quantity, category, supplier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (code, name, unit, unit_price, unit_price, float(min_quantity or 0), category, supplier))
        self.conn.commit()
        return cursor.lastrowid

    def update_material(self, material_id, code, name, unit, unit_price, category, supplier, status='active'):
        """Cập nhật thông tin vật tư."""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE materials
            SET code = ?, name = ?, unit = ?, unit_price = ?, category = ?, supplier = ?, status = ?
            WHERE id = ?
        ''', (code, name, unit, float(unit_price or 0), category, supplier, status, material_id))
        self.conn.commit()

    def get_all_materials(self):
        """Lấy tất cả vật tư."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, code, name, unit, quantity, unit_price, category, status
            FROM materials ORDER BY category, name
        ''')
        return cursor.fetchall()

    def get_material_stock(self, material_id: int) -> int:
        """Lấy tồn kho vật tư."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT quantity FROM materials WHERE id = ?
        ''', (material_id,))
        result = cursor.fetchone()
        return result[0] if result else 0

    def get_average_cost(self, material_id: int) -> float:
        """Lay gia von binh quan gia quyen hien tai cua vat tu."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COALESCE(average_cost, unit_price, 0) AS average_cost
            FROM materials WHERE id = ?
        ''', (int(material_id),))
        row = cursor.fetchone()
        return float(row["average_cost"] if hasattr(row, "keys") else row[0]) if row else 0.0

    def receive_material(self, material_id: int, quantity: float, unit_price: float,
                         supplier_id: Optional[int] = None, document_id: Optional[int] = None,
                         received_by: int = 1, notes: str = "") -> int:
        """Nhap kho va cap nhat gia binh quan gia quyen."""
        cursor = self.conn.cursor()
        material_id = int(material_id)
        quantity = float(quantity or 0)
        unit_price = float(unit_price or 0)
        if quantity <= 0 or unit_price < 0:
            raise ValueError("So luong va don gia nhap kho khong hop le")
        today = datetime.now().date().isoformat()
        assert_date_not_locked(today, 'nhap kho')

        cursor.execute("SELECT quantity, COALESCE(average_cost, unit_price, 0) AS average_cost FROM materials WHERE id = ?",
                       (material_id,))
        material = cursor.fetchone()
        if not material:
            raise ValueError("Khong tim thay vat tu")
        old_qty = float(material["quantity"] or 0)
        old_cost = float(material["average_cost"] or 0)
        new_qty = old_qty + quantity
        new_average = ((old_qty * old_cost) + (quantity * unit_price)) / new_qty if new_qty else unit_price

        detail = notes or f"Nhap kho SL {quantity:,.2f} x {unit_price:,.0f}"
        if supplier_id:
            detail += f"; supplier_id={supplier_id}"
        if document_id:
            detail += f"; document_id={document_id}"
        cursor.execute('''
            UPDATE materials
            SET quantity = ?, unit_price = ?, average_cost = ?
            WHERE id = ?
        ''', (new_qty, unit_price, new_average, material_id))
        cursor.execute('''
            INSERT INTO inventory_transactions
            (material_id, transaction_type, quantity, project_id, notes, created_by, transaction_date)
            VALUES (?, 'import', ?, NULL, ?, ?, ?)
        ''', (material_id, quantity, detail, received_by, today))
        transaction_id = cursor.lastrowid
        self._create_material_journal(cursor, "Nhap kho vat tu", "152", "331",
                                      quantity * unit_price, None, transaction_id, received_by)
        self.conn.commit()
        return transaction_id

    def issue_material(self, material_id: int, quantity: float, project_id: Optional[int],
                       work_item_id: Optional[int] = None, issued_by: int = 1,
                       notes: str = "") -> int:
        """Xuat kho theo gia binh quan va ghi nhan chi phi du an."""
        cursor = self.conn.cursor()
        material_id = int(material_id)
        quantity = float(quantity or 0)
        if quantity <= 0:
            raise ValueError("So luong xuat kho phai lon hon 0")
        today = datetime.now().date().isoformat()
        assert_date_not_locked(today, 'xuat kho')
        cursor.execute("SELECT quantity, COALESCE(average_cost, unit_price, 0) AS average_cost FROM materials WHERE id = ?",
                       (material_id,))
        material = cursor.fetchone()
        if not material:
            raise ValueError("Khong tim thay vat tu")
        current_stock = float(material["quantity"] or 0)
        if current_stock < quantity:
            raise ValueError(f"Ton kho khong du. Hien con {current_stock:,.2f}")
        avg_cost = float(material["average_cost"] or 0)
        project_id = int(project_id) if project_id else None
        detail = notes or f"Xuat kho SL {quantity:,.2f} theo gia BQ {avg_cost:,.0f}"
        if work_item_id:
            detail += f"; work_item_id={work_item_id}"
        cursor.execute("UPDATE materials SET quantity = quantity - ? WHERE id = ?",
                       (quantity, material_id))
        cursor.execute('''
            INSERT INTO inventory_transactions
            (material_id, transaction_type, quantity, project_id, notes, created_by, transaction_date)
            VALUES (?, 'export', ?, ?, ?, ?, ?)
        ''', (material_id, quantity, project_id, detail, issued_by, today))
        transaction_id = cursor.lastrowid
        self._create_material_journal(cursor, "Xuat kho vat tu cho cong trinh", "621", "152",
                                      quantity * avg_cost, project_id, transaction_id, issued_by)
        self.conn.commit()
        return transaction_id

    def check_low_stock(self) -> List[sqlite3.Row]:
        """Danh sach vat tu ton kho duoi dinh muc toi thieu."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, code, name, unit, quantity, min_quantity, category
            FROM materials
            WHERE status = 'active'
              AND COALESCE(min_quantity, 0) > 0
              AND COALESCE(quantity, 0) <= COALESCE(min_quantity, 0)
            ORDER BY category, name
        ''')
        return cursor.fetchall()

    def add_inventory_transaction(self, material_id: int, transaction_type: str, 
                                 quantity: float, project_id: Optional[int], 
                                 notes: str, created_by: int) -> int:
        """Thêm giao dịch kho (nhập/xuất)."""
        cursor = self.conn.cursor()
        material_id = int(material_id)
        quantity = float(quantity or 0)
        project_id = int(project_id) if project_id else None

        if quantity <= 0:
            raise ValueError("Số lượng phải lớn hơn 0")
        today = datetime.now().date().isoformat()
        assert_date_not_locked(today, 'ghi giao dich kho')

        # Cập nhật tồn kho
        if transaction_type == 'import':
            cursor.execute('''
                UPDATE materials SET quantity = quantity + ? WHERE id = ?
            ''', (quantity, material_id))
        elif transaction_type == 'export':
            current_stock = self.get_material_stock(material_id)
            if current_stock < quantity:
                raise ValueError(f"Tồn kho không đủ. Hiện còn {current_stock}")
            cursor.execute('''
                UPDATE materials SET quantity = quantity - ? WHERE id = ?
            ''', (quantity, material_id))
        else:
            raise ValueError("Loại giao dịch kho không hợp lệ")

        # Ghi lại giao dịch
        cursor.execute('''
            INSERT INTO inventory_transactions 
            (material_id, transaction_type, quantity, project_id, notes, created_by, transaction_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (material_id, transaction_type, quantity, project_id, notes, created_by, today))

        self.conn.commit()
        return cursor.lastrowid

    def _create_material_journal(self, cursor, description, debit_account, credit_account,
                                 amount, project_id, transaction_id, created_by):
        amount = float(amount or 0)
        if amount <= 0:
            return None
        cursor.execute('''
            INSERT INTO journal_entries
            (entry_date, description, debit_account, credit_account, amount,
             project_id, reference_type, reference_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?, 'inventory_transaction', ?, ?)
        ''', (datetime.now().date().isoformat(), description, debit_account, credit_account,
              amount, project_id, transaction_id, created_by))
        journal_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO journal_entry_lines
            (journal_entry_id, line_no, account_code, debit_amount, credit_amount,
             project_id, description)
            VALUES (?, 1, ?, ?, 0, ?, ?)
        ''', (journal_id, debit_account, amount, project_id, description))
        cursor.execute('''
            INSERT INTO journal_entry_lines
            (journal_entry_id, line_no, account_code, debit_amount, credit_amount,
             project_id, description)
            VALUES (?, 2, ?, 0, ?, ?, ?)
        ''', (journal_id, credit_account, amount, project_id, description))
        return journal_id

    def get_inventory_history(self, material_id=None, limit=100):
        """Lấy lịch sử giao dịch kho."""
        cursor = self.conn.cursor()

        if material_id:
            cursor.execute('''
                SELECT it.id, m.code, m.name, it.transaction_type, it.quantity, 
                       it.transaction_date, p.name, it.notes
                FROM inventory_transactions it
                JOIN materials m ON it.material_id = m.id
                LEFT JOIN projects p ON it.project_id = p.id
                WHERE it.material_id = ?
                ORDER BY it.transaction_date DESC
                LIMIT ?
            ''', (material_id, limit))
        else:
            cursor.execute('''
                SELECT it.id, m.code, m.name, it.transaction_type, it.quantity, 
                       it.transaction_date, p.name, it.notes
                FROM inventory_transactions it
                JOIN materials m ON it.material_id = m.id
                LEFT JOIN projects p ON it.project_id = p.id
                ORDER BY it.transaction_date DESC
                LIMIT ?
            ''', (limit,))

        return cursor.fetchall()

    def get_material_choices(self):
        """Lấy danh sách vật tư để hiển thị combobox."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, code, name, unit, quantity
            FROM materials
            WHERE status = 'active'
            ORDER BY name
        ''')
        return cursor.fetchall()

    def get_material_value_by_project(self, project_id):
        """Lấy giá trị vật tư theo dự án."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT m.name, SUM(it.quantity * m.unit_price) as total_value
            FROM inventory_transactions it
            JOIN materials m ON it.material_id = m.id
            WHERE it.project_id = ? AND it.transaction_type = 'export'
            GROUP BY it.material_id
            ORDER BY total_value DESC
        ''', (project_id,))
        return cursor.fetchall()


class AuxiliaryMaterialManager(ConnectionPerRequestMixin):
    """Quản lý vật tư phụ."""

    def __init__(self):
        pass

    def get_auxiliary_materials(self):
        """Lấy danh sách vật tư phụ (vật tư phục vụ dự án nhưng không tính vào chi phí trực tiếp)."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM materials WHERE category = 'Vật tư phụ' ORDER BY name
        ''')
        return cursor.fetchall()
