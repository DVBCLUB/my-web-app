"""
MODULE KNOWLEDGE BASE - Tra cứu biểu mẫu, hồ sơ, quy trình, định mức và nhắc việc.
"""

from database import get_connection


class KnowledgeBaseManager:
    """Kho dữ liệu vận hành kế toán lấy từ các workbook mẫu."""

    def __init__(self):
        self.conn = get_connection()

    def search_forms(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT id, form_code, form_name, COALESCE(scope, ''),
                   COALESCE(used_when, ''), COALESCE(required_signatures, ''),
                   COALESCE(storage_owner, ''), COALESCE(storage_method, ''),
                   COALESCE(usage_notes, ''), COALESCE(source_workbook, ''),
                   COALESCE(sheet_name, ''), COALESCE(file_path, '')
            FROM form_templates
            WHERE active = 1
        '''
        if keyword:
            query += '''
                AND (
                    form_code LIKE ? OR form_name LIKE ? OR COALESCE(scope, '') LIKE ?
                    OR COALESCE(used_when, '') LIKE ? OR COALESCE(usage_notes, '') LIKE ?
                )
            '''
            search = f'%{keyword}%'
            params.extend([search, search, search, search, search])
        query += ' ORDER BY form_code, scope'
        cursor.execute(query, params)
        return cursor.fetchall()

    def search_requirements(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT id, COALESCE(ref_code, ''), business_type, COALESCE(cost_group, ''),
                   COALESCE(record_type, ''), COALESCE(scope, ''),
                   COALESCE(required_documents, ''), COALESCE(optional_documents, ''),
                   COALESCE(required_signatures, ''), COALESCE(approval_authority, ''),
                   COALESCE(deadline, ''), COALESCE(forms, ''),
                   COALESCE(limit_notes, ''), COALESCE(warning_message, ''),
                   COALESCE(source_workbook, '')
            FROM document_requirements
            WHERE active = 1
        '''
        if keyword:
            query += '''
                AND (
                    business_type LIKE ? OR COALESCE(cost_group, '') LIKE ?
                    OR COALESCE(record_type, '') LIKE ? OR COALESCE(required_documents, '') LIKE ?
                    OR COALESCE(forms, '') LIKE ? OR COALESCE(warning_message, '') LIKE ?
                )
            '''
            search = f'%{keyword}%'
            params.extend([search, search, search, search, search, search])
        query += ' ORDER BY source_workbook, ref_code'
        cursor.execute(query, params)
        return cursor.fetchall()

    def search_processes(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT id, process_name, COALESCE(step_no, ''), COALESCE(responsible, ''),
                   action, COALESCE(duration, ''), COALESCE(forms, ''),
                   COALESCE(notes, ''), COALESCE(source_workbook, '')
            FROM process_steps
            WHERE active = 1
        '''
        if keyword:
            query += '''
                AND (
                    process_name LIKE ? OR action LIKE ? OR COALESCE(responsible, '') LIKE ?
                    OR COALESCE(forms, '') LIKE ? OR COALESCE(notes, '') LIKE ?
                )
            '''
            search = f'%{keyword}%'
            params.extend([search, search, search, search, search])
        query += ' ORDER BY source_workbook, id'
        cursor.execute(query, params)
        return cursor.fetchall()

    def search_limits(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT id, COALESCE(policy_group, ''), item_name,
                   COALESCE(value_a, ''), COALESCE(value_b, ''),
                   COALESCE(value_c, ''), COALESCE(value_d, ''),
                   COALESCE(notes, ''), COALESCE(source_workbook, '')
            FROM policy_limits
            WHERE active = 1
        '''
        if keyword:
            query += '''
                AND (
                    COALESCE(policy_group, '') LIKE ? OR item_name LIKE ?
                    OR COALESCE(notes, '') LIKE ?
                )
            '''
            search = f'%{keyword}%'
            params.extend([search, search, search])
        query += ' ORDER BY source_workbook, id'
        cursor.execute(query, params)
        return cursor.fetchall()

    def search_tasks(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT id, schedule_text, COALESCE(task_type, ''), task_content,
                   COALESCE(owner, ''), COALESCE(approver, ''), COALESCE(forms, ''),
                   COALESCE(priority, ''), COALESCE(status, ''), COALESCE(notes, ''),
                   COALESCE(source_workbook, '')
            FROM recurring_tasks
            WHERE active = 1
        '''
        if keyword:
            query += '''
                AND (
                    schedule_text LIKE ? OR COALESCE(task_type, '') LIKE ?
                    OR task_content LIKE ? OR COALESCE(owner, '') LIKE ?
                    OR COALESCE(forms, '') LIKE ?
                )
            '''
            search = f'%{keyword}%'
            params.extend([search, search, search, search, search])
        query += ' ORDER BY id'
        cursor.execute(query, params)
        return cursor.fetchall()

    def search_template_fields(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT f.id, f.form_code, COALESCE(t.form_name, ''),
                   f.field_key, f.field_label, f.field_type, f.required,
                   COALESCE(f.default_value, ''), f.display_order,
                   COALESCE(f.notes, '')
            FROM form_template_fields f
            LEFT JOIN form_templates t ON f.form_template_id = t.id
            WHERE f.active = 1
        '''
        if keyword:
            query += '''
                AND (
                    f.form_code LIKE ? OR COALESCE(t.form_name, '') LIKE ?
                    OR f.field_key LIKE ? OR f.field_label LIKE ?
                    OR COALESCE(f.notes, '') LIKE ?
                )
            '''
            search = f'%{keyword}%'
            params.extend([search, search, search, search, search])
        query += ' ORDER BY f.form_code, f.display_order, f.id'
        cursor.execute(query, params)
        return cursor.fetchall()

    def search_field_mappings(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT m.id, m.form_code, COALESCE(t.form_name, ''),
                   COALESCE(m.sheet_name, ''), m.field_key, m.cell_address,
                   COALESCE(m.row_mode, 'fixed')
            FROM form_field_mappings m
            LEFT JOIN form_templates t ON m.form_template_id = t.id
            WHERE m.active = 1
        '''
        if keyword:
            query += '''
                AND (
                    m.form_code LIKE ? OR COALESCE(t.form_name, '') LIKE ?
                    OR COALESCE(m.sheet_name, '') LIKE ? OR m.field_key LIKE ?
                    OR m.cell_address LIKE ?
                )
            '''
            search = f'%{keyword}%'
            params.extend([search, search, search, search, search])
        query += ' ORDER BY m.form_code, m.sheet_name, m.id'
        cursor.execute(query, params)
        return cursor.fetchall()

    def get_form_choices(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, form_code, form_name
            FROM form_templates
            WHERE active = 1
            ORDER BY form_code, form_name
        ''')
        return cursor.fetchall()

    def add_template_field(self, form_template_id, field_key, field_label,
                           field_type='text', required=0, default_value='',
                           display_order=0, notes=''):
        cursor = self.conn.cursor()
        cursor.execute('SELECT form_code FROM form_templates WHERE id = ?', (form_template_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError('Không tìm thấy biểu mẫu')
        cursor.execute('''
            INSERT INTO form_template_fields
            (form_template_id, form_code, field_key, field_label, field_type,
             required, default_value, display_order, notes, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(form_code, field_key) DO UPDATE SET
                form_template_id = excluded.form_template_id,
                field_label = excluded.field_label,
                field_type = excluded.field_type,
                required = excluded.required,
                default_value = excluded.default_value,
                display_order = excluded.display_order,
                notes = excluded.notes,
                active = 1
        ''', (form_template_id, row['form_code'], field_key, field_label,
              field_type, required, default_value, display_order, notes))
        self.conn.commit()

    def add_field_mapping(self, form_template_id, field_key, cell_address, row_mode='fixed'):
        cursor = self.conn.cursor()
        cursor.execute('SELECT form_code, sheet_name FROM form_templates WHERE id = ?', (form_template_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError('Không tìm thấy biểu mẫu')
        cursor.execute('''
            INSERT INTO form_field_mappings
            (form_template_id, form_code, sheet_name, field_key, cell_address, row_mode, active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(form_code, sheet_name, field_key) DO UPDATE SET
                form_template_id = excluded.form_template_id,
                cell_address = excluded.cell_address,
                row_mode = excluded.row_mode,
                active = 1,
                updated_at = CURRENT_TIMESTAMP
        ''', (form_template_id, row['form_code'], row['sheet_name'], field_key, cell_address, row_mode))
        self.conn.commit()

    def update_status(self, table_name, record_id, active):
        if table_name not in {
            'form_templates', 'document_requirements', 'process_steps',
            'policy_limits', 'recurring_tasks', 'form_template_fields',
            'form_field_mappings',
        }:
            raise ValueError('Bảng không hợp lệ')
        cursor = self.conn.cursor()
        cursor.execute(f'UPDATE {table_name} SET active = ? WHERE id = ?', (1 if active else 0, record_id))
        self.conn.commit()
