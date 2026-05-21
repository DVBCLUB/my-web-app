"""
MODULE CONSTRUCTION - Quản lý nghiệp vụ công trường xây dựng.
"""

from datetime import datetime
from database import get_connection


class ConstructionManager:
    """Theo dõi hạng mục, nhật ký công trường, tiến độ, máy thi công và an toàn."""

    def __init__(self):
        self.conn = get_connection()

    def get_dashboard(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM construction_work_items')
        work_items = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM project_milestones WHERE status NOT IN ('done', 'completed', 'Hoàn thành')")
        open_milestones = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM safety_checks WHERE status NOT IN ('closed', 'Đã đóng', 'Hoàn thành')")
        open_safety = cursor.fetchone()[0]
        cursor.execute('SELECT COALESCE(SUM(hours), 0), COALESCE(SUM(fuel_cost), 0) FROM equipment_usage')
        equipment = cursor.fetchone()
        return {
            'work_items': work_items,
            'open_milestones': open_milestones,
            'open_safety': open_safety,
            'equipment_hours': equipment[0] or 0,
            'fuel_cost': equipment[1] or 0,
        }

    def get_work_items(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT w.id, COALESCE(p.code, ''), COALESCE(p.name, ''), w.item_code,
                   w.item_name, COALESCE(w.unit, ''), w.planned_quantity,
                   w.completed_quantity, COALESCE(w.percent_complete, 0), w.unit_price,
                   (w.planned_quantity * w.unit_price) AS planned_value,
                   ((w.planned_quantity * w.unit_price) * COALESCE(w.percent_complete, 0) / 100) AS completed_value,
                   COALESCE((SELECT SUM(e.amount) FROM expenses e
                             WHERE e.work_item_id = w.id), 0) AS actual_expense,
                   w.status, COALESCE(w.notes, '')
            FROM construction_work_items w
            LEFT JOIN projects p ON w.project_id = p.id
            WHERE 1 = 1
        '''
        if keyword:
            query += ' AND (w.item_name LIKE ? OR w.item_code LIKE ? OR p.name LIKE ? OR p.code LIKE ?)'
            search = f'%{keyword}%'
            params.extend([search, search, search, search])
        query += ' ORDER BY p.code, w.item_code, w.id'
        cursor.execute(query, params)
        return cursor.fetchall()

    def add_work_item(self, project_id, item_code, item_name, unit, planned_quantity,
                      completed_quantity, unit_price, status, notes):
        cursor = self.conn.cursor()
        percent_complete = 0
        if float(planned_quantity or 0):
            percent_complete = min(float(completed_quantity or 0) / float(planned_quantity or 0) * 100, 100)
        cursor.execute('''
            INSERT INTO construction_work_items
            (project_id, item_code, item_name, unit, planned_quantity,
             completed_quantity, percent_complete, unit_price, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (project_id, item_code, item_name, unit, planned_quantity,
              completed_quantity, percent_complete, unit_price, status, notes))
        self.conn.commit()
        return cursor.lastrowid

    def get_site_diaries(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT d.id, d.diary_date, COALESCE(p.code, ''), COALESCE(p.name, ''),
                   COALESCE(d.weather, ''), COALESCE(d.manpower, ''),
                   COALESCE(d.equipment, ''), COALESCE(d.work_content, ''),
                   COALESCE(d.issues, ''), COALESCE(d.reporter, '')
            FROM site_diaries d
            LEFT JOIN projects p ON d.project_id = p.id
            WHERE 1 = 1
        '''
        if keyword:
            query += ' AND (p.name LIKE ? OR d.work_content LIKE ? OR d.issues LIKE ? OR d.reporter LIKE ?)'
            search = f'%{keyword}%'
            params.extend([search, search, search, search])
        query += ' ORDER BY d.diary_date DESC, d.id DESC'
        cursor.execute(query, params)
        return cursor.fetchall()

    def add_site_diary(self, diary_date, project_id, weather, manpower, equipment,
                       work_content, issues, reporter):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO site_diaries
            (diary_date, project_id, weather, manpower, equipment,
             work_content, issues, reporter)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (diary_date, project_id, weather, manpower, equipment,
              work_content, issues, reporter))
        self.conn.commit()
        return cursor.lastrowid

    def get_milestones(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT m.id, COALESCE(p.code, ''), COALESCE(p.name, ''), m.milestone_name,
                   COALESCE(m.planned_date, ''), COALESCE(m.actual_date, ''),
                   m.status, COALESCE(m.notes, '')
            FROM project_milestones m
            LEFT JOIN projects p ON m.project_id = p.id
            WHERE 1 = 1
        '''
        if keyword:
            query += ' AND (p.name LIKE ? OR m.milestone_name LIKE ? OR m.status LIKE ?)'
            search = f'%{keyword}%'
            params.extend([search, search, search])
        query += ' ORDER BY m.planned_date, m.id'
        cursor.execute(query, params)
        return cursor.fetchall()

    def add_milestone(self, project_id, milestone_name, planned_date, actual_date, status, notes):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO project_milestones
            (project_id, milestone_name, planned_date, actual_date, status, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (project_id, milestone_name, planned_date, actual_date, status, notes))
        self.conn.commit()
        return cursor.lastrowid

    def get_equipment_usage(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT e.id, e.usage_date, COALESCE(p.code, ''), COALESCE(p.name, ''),
                   e.equipment_name, COALESCE(e.operator, ''), e.hours,
                   e.fuel_cost, COALESCE(e.notes, '')
            FROM equipment_usage e
            LEFT JOIN projects p ON e.project_id = p.id
            WHERE 1 = 1
        '''
        if keyword:
            query += ' AND (p.name LIKE ? OR e.equipment_name LIKE ? OR e.operator LIKE ?)'
            search = f'%{keyword}%'
            params.extend([search, search, search])
        query += ' ORDER BY e.usage_date DESC, e.id DESC'
        cursor.execute(query, params)
        return cursor.fetchall()

    def add_equipment_usage(self, usage_date, project_id, equipment_name, operator,
                            hours, fuel_cost, notes):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO equipment_usage
            (usage_date, project_id, equipment_name, operator, hours, fuel_cost, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (usage_date, project_id, equipment_name, operator, hours, fuel_cost, notes))
        self.conn.commit()
        return cursor.lastrowid

    def get_safety_checks(self, keyword=None):
        cursor = self.conn.cursor()
        params = []
        query = '''
            SELECT s.id, s.check_date, COALESCE(p.code, ''), COALESCE(p.name, ''),
                   s.check_item, s.result, COALESCE(s.responsible, ''),
                   COALESCE(s.action_required, ''), COALESCE(s.deadline, ''), s.status
            FROM safety_checks s
            LEFT JOIN projects p ON s.project_id = p.id
            WHERE 1 = 1
        '''
        if keyword:
            query += ' AND (p.name LIKE ? OR s.check_item LIKE ? OR s.responsible LIKE ? OR s.status LIKE ?)'
            search = f'%{keyword}%'
            params.extend([search, search, search, search])
        query += ' ORDER BY s.check_date DESC, s.id DESC'
        cursor.execute(query, params)
        return cursor.fetchall()

    def add_safety_check(self, check_date, project_id, check_item, result,
                         responsible, action_required, deadline, status):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO safety_checks
            (check_date, project_id, check_item, result, responsible,
             action_required, deadline, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (check_date, project_id, check_item, result, responsible,
              action_required, deadline, status))
        self.conn.commit()
        return cursor.lastrowid
