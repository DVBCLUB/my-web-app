"""
MODULE AUTH - Quáº£n lĂ½ ngÆ°á»i dĂ¹ng & xĂ¡c thá»±c
"""

import sqlite3
import base64
import hashlib
import hmac
import os
import re
try:
    import bcrypt
except ImportError:
    bcrypt = None
from datetime import datetime, timedelta
from database import get_connection


class AuthManager:
    """Quáº£n lĂ½ xĂ¡c thá»±c & ngÆ°á»i dĂ¹ng."""

    def __init__(self):
        self.conn = get_connection()

    @staticmethod
    def hash_password(password):
        AuthManager.validate_password_policy(password)
        if bcrypt is None:
            salt = os.urandom(16)
            digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 260000)
            return 'pbkdf2_sha256$260000${}${}'.format(
                base64.b64encode(salt).decode('ascii'),
                base64.b64encode(digest).decode('ascii'),
            )
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    @staticmethod
    def validate_password_policy(password):
        password = password or ''
        errors = []
        if len(password) < 10:
            errors.append('toi thieu 10 ky tu')
        if not re.search(r'[A-Z]', password):
            errors.append('it nhat 1 chu hoa')
        if not re.search(r'[a-z]', password):
            errors.append('it nhat 1 chu thuong')
        if not re.search(r'\d', password):
            errors.append('it nhat 1 chu so')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=/\\\[\]]', password):
            errors.append('it nhat 1 ky tu dac biet')
        if errors:
            raise ValueError('Mat khau khong du manh: ' + ', '.join(errors) + '.')
        return True

    @staticmethod
    def verify_password(password, hashed_password):
        """Kiá»ƒm tra máº­t kháº©u vá»›i hash."""
        if str(hashed_password or '').startswith('pbkdf2_sha256$'):
            try:
                _algo, rounds, salt_b64, digest_b64 = hashed_password.split('$', 3)
                salt = base64.b64decode(salt_b64)
                expected = base64.b64decode(digest_b64)
                actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(rounds))
                return hmac.compare_digest(actual, expected)
            except Exception:
                return False
        try:
            if bcrypt is None:
                raise ValueError('bcrypt unavailable')
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except (ValueError, TypeError):
            # Fallback cho passwords cÅ© (sha256) náº¿u cáº§n migration
            old_hash = hashlib.sha256(password.encode()).hexdigest()
            return old_hash == hashed_password

    def create_user(self, username, password, full_name, email, role='employee'):
        """Táº¡o ngÆ°á»i dĂ¹ng má»›i."""
        cursor = self.conn.cursor()

        try:
            hashed_password = self.hash_password(password)
            cursor.execute('''
                INSERT INTO users (username, password, full_name, email, role, password_changed_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (username, hashed_password, full_name, email, role))
            self.conn.commit()
            return True, "Táº¡o ngÆ°á»i dĂ¹ng thĂ nh cĂ´ng"
        except sqlite3.IntegrityError:
            return False, "TĂªn Ä‘Äƒng nháº­p Ä‘Ă£ tá»“n táº¡i"
        except Exception as e:
            return False, str(e)

    def authenticate(self, username, password):
        """XĂ¡c thá»±c ngÆ°á»i dĂ¹ng."""
        cursor = self.conn.cursor()

        cursor.execute('''
            SELECT id, username, full_name, email, role, password,
                   failed_login_count, locked_until, password_changed_at, must_change_password
            FROM users 
            WHERE username = ? AND active = 1
        ''', (username,))

        user = cursor.fetchone()
        if user:
            user_dict = dict(user)
            stored_password = user_dict.pop('password')
            if user_dict.get('locked_until'):
                try:
                    if datetime.fromisoformat(str(user_dict['locked_until'])) > datetime.now():
                        return False, None
                except ValueError:
                    pass
            
            if self.verify_password(password, stored_password):
                cursor.execute('''
                    UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE id = ?
                ''', (user_dict['id'],))
                self.conn.commit()
                changed_at = user_dict.get('password_changed_at')
                user_dict['password_expired'] = False
                if changed_at:
                    try:
                        user_dict['password_expired'] = datetime.fromisoformat(str(changed_at)) < datetime.now() - timedelta(days=90)
                    except ValueError:
                        pass
                return True, user_dict
            failed = int(user_dict.get('failed_login_count') or 0) + 1
            locked_until = (datetime.now() + timedelta(minutes=30)).isoformat(timespec='seconds') if failed >= 5 else None
            cursor.execute('''
                UPDATE users SET failed_login_count = ?, locked_until = ? WHERE id = ?
            ''', (failed, locked_until, user_dict['id']))
            self.conn.commit()
        return False, None

    def change_password(self, user_id, old_password, new_password):
        """Äá»•i máº­t kháº©u."""
        cursor = self.conn.cursor()

        # Láº¥y password hiá»‡n táº¡i
        cursor.execute('''
            SELECT password FROM users WHERE id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        
        if not result:
            return False, "KhĂ´ng tĂ¬m tháº¥y ngÆ°á»i dĂ¹ng"
        
        stored_password = result['password']
        
        # Kiá»ƒm tra máº­t kháº©u cÅ©
        if not self.verify_password(old_password, stored_password):
            return False, "Máº­t kháº©u cÅ© khĂ´ng Ä‘Ăºng"

        # Cáº­p nháº­t máº­t kháº©u má»›i vá»›i bcrypt
        new_hashed = self.hash_password(new_password)
        cursor.execute('''
            UPDATE users
            SET password = ?, password_changed_at = CURRENT_TIMESTAMP,
                must_change_password = 0, failed_login_count = 0, locked_until = NULL
            WHERE id = ?
        ''', (new_hashed, user_id))
        self.conn.commit()

        return True, "Äá»•i máº­t kháº©u thĂ nh cĂ´ng"

    def get_user(self, user_id):
        """Láº¥y thĂ´ng tin ngÆ°á»i dĂ¹ng."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, username, full_name, email, role, created_at, active
            FROM users WHERE id = ?
        ''', (user_id,))

        user = cursor.fetchone()
        return dict(user) if user else None

    def get_all_users(self):
        """Láº¥y danh sĂ¡ch táº¥t cáº£ ngÆ°á»i dĂ¹ng."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, username, full_name, email, role, created_at, active
            FROM users ORDER BY created_at DESC
        ''')
        return cursor.fetchall()

    def update_user(self, user_id, **kwargs):
        """Cáº­p nháº­t thĂ´ng tin ngÆ°á»i dĂ¹ng."""
        cursor = self.conn.cursor()

        allowed_fields = ['full_name', 'email', 'role', 'active']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False, "KhĂ´ng cĂ³ trÆ°á»ng nĂ o Ä‘á»ƒ cáº­p nháº­t"

        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [user_id]

        cursor.execute(f'''
            UPDATE users SET {set_clause} WHERE id = ?
        ''', values)
        self.conn.commit()

        return True, "Cáº­p nháº­t thĂ nh cĂ´ng"

    def deactivate_user(self, user_id):
        """VĂ´ hiá»‡u hĂ³a ngÆ°á»i dĂ¹ng."""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE users SET active = 0 WHERE id = ?
        ''', (user_id,))
        self.conn.commit()
        return True, "VĂ´ hiá»‡u hĂ³a ngÆ°á»i dĂ¹ng thĂ nh cĂ´ng"


class PermissionManager:
    """Quáº£n lĂ½ quyá»n háº¡n."""

    ROLES = {
        'admin': ['view_all', 'create_all', 'edit_all', 'delete_all', 'manage_users'],
        'accountant': ['view_all', 'create_expense', 'edit_expense', 'view_report'],
        'manager': ['view_all', 'view_report', 'approve_expense'],
        'employee': ['view_own', 'create_expense'],
    }

    @staticmethod
    def has_permission(role, action):
        """Kiá»ƒm tra quyá»n."""
        if role not in PermissionManager.ROLES:
            return False
        return action in PermissionManager.ROLES[role]

    @staticmethod
    def get_role_permissions(role):
        """Láº¥y danh sĂ¡ch quyá»n cá»§a role."""
        return PermissionManager.ROLES.get(role, [])

    @staticmethod
    def add_custom_role(role_name, permissions):
        """ThĂªm role tĂ¹y chá»‰nh (náº¿u cáº§n)."""
        PermissionManager.ROLES[role_name] = permissions


class ProjectAccessManager:
    """Project-level RBAC helpers for filtering and permission checks."""

    def __init__(self):
        self.conn = get_connection()

    def grant_project_access(self, user_id, project_id, access_level='view',
                             can_view=True, can_edit=False, can_approve=False):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO user_project_access
            (user_id, project_id, access_level, can_view, can_edit, can_approve)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, project_id) DO UPDATE SET
                access_level = excluded.access_level,
                can_view = excluded.can_view,
                can_edit = excluded.can_edit,
                can_approve = excluded.can_approve
        ''', (user_id, project_id, access_level, int(can_view), int(can_edit), int(can_approve)))
        self.conn.commit()

    def revoke_project_access(self, user_id, project_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM user_project_access WHERE user_id = ? AND project_id = ?', (user_id, project_id))
        self.conn.commit()

    def list_accessible_projects(self, user_id, action='view'):
        user = AuthManager().get_user(user_id)
        if user and PermissionManager.has_permission(user.get('role'), 'view_all'):
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, code, name FROM projects WHERE status = 'active' ORDER BY code")
            return cursor.fetchall()
        column = {'view': 'can_view', 'edit': 'can_edit', 'approve': 'can_approve'}.get(action, 'can_view')
        cursor = self.conn.cursor()
        cursor.execute(f'''
            SELECT p.id, p.code, p.name
            FROM user_project_access a
            JOIN projects p ON p.id = a.project_id
            WHERE a.user_id = ? AND a.{column} = 1
            ORDER BY p.code
        ''', (user_id,))
        return cursor.fetchall()

    def can_access_project(self, user_id, project_id, action='view'):
        user = AuthManager().get_user(user_id)
        if user and PermissionManager.has_permission(user.get('role'), 'view_all'):
            return True
        column = {'view': 'can_view', 'edit': 'can_edit', 'approve': 'can_approve'}.get(action, 'can_view')
        cursor = self.conn.cursor()
        cursor.execute(f'''
            SELECT 1 FROM user_project_access
            WHERE user_id = ? AND project_id = ? AND {column} = 1
        ''', (user_id, project_id))
        return cursor.fetchone() is not None

    def project_filter_sql(self, user_id, table_alias='p', action='view'):
        user = AuthManager().get_user(user_id)
        if user and PermissionManager.has_permission(user.get('role'), 'view_all'):
            return '1=1', []
        column = {'view': 'can_view', 'edit': 'can_edit', 'approve': 'can_approve'}.get(action, 'can_view')
        return (
            f"{table_alias}.id IN (SELECT project_id FROM user_project_access WHERE user_id = ? AND {column} = 1)",
            [user_id],
        )


class LoginWindow:
    """Cá»­a sá»• Ä‘Äƒng nháº­p."""

    def __init__(self, root, on_login_success):
        import tkinter as tk
        from tkinter import messagebox

        self.root = root
        self.on_login_success = on_login_success
        self.auth_manager = AuthManager()

        self.root.title("ÄÄƒng Nháº­p - ERP Trung Háº£i")
        self.root.geometry("400x350")
        self.root.resizable(False, False)
        self.root.configure(bg='#1a56a5')

        self._build_ui()

    def _build_ui(self):
        """XĂ¢y dá»±ng giao diá»‡n Ä‘Äƒng nháº­p."""
        import tkinter as tk
        from tkinter import messagebox

        # Header
        header = tk.Frame(self.root, bg='#1a56a5', height=80)
        header.pack(fill='x')

        tk.Label(header, text="đŸ’¼ ERP TRUNG Háº¢I",
                font=('Arial', 18, 'bold'), fg='white', bg='#1a56a5').pack(pady=15)

        tk.Label(header, text="Quáº£n lĂ½ káº¿ toĂ¡n cĂ´ng ty xĂ¢y dá»±ng",
                font=('Arial', 10), fg='#c8d8f0', bg='#1a56a5').pack()

        # Content
        content = tk.Frame(self.root, bg='#f0f4f8')
        content.pack(fill='both', expand=True, padx=30, pady=30)

        tk.Label(content, text="TĂªn Ä‘Äƒng nháº­p:", font=('Arial', 11, 'bold'),
                bg='#f0f4f8', fg='#333').pack(anchor='w', pady=(0, 5))

        self.username_var = tk.StringVar()
        username_entry = tk.Entry(content, textvariable=self.username_var,
                                 font=('Arial', 11), width=30,
                                 relief='solid', bd=1)
        username_entry.pack(fill='x', pady=(0, 15))
        username_entry.focus()

        tk.Label(content, text="Máº­t kháº©u:", font=('Arial', 11, 'bold'),
                bg='#f0f4f8', fg='#333').pack(anchor='w', pady=(0, 5))

        self.password_var = tk.StringVar()
        password_entry = tk.Entry(content, textvariable=self.password_var,
                                 font=('Arial', 11), width=30,
                                 relief='solid', bd=1, show='â—')
        password_entry.pack(fill='x', pady=(0, 30))

        # NĂºt Ä‘Äƒng nháº­p
        login_btn = tk.Button(content, text="đŸ”“ ÄÄ‚NG NHáº¬P",
                             font=('Arial', 12, 'bold'), bg='#27ae60', fg='white',
                             activebackground='#1e8449',
                             padx=20, pady=10, bd=0, cursor='hand2',
                             command=self._login)
        login_btn.pack(fill='x', pady=(0, 10))

        # NĂºt thoĂ¡t
        exit_btn = tk.Button(content, text="âŒ THOĂT",
                            font=('Arial', 11), bg='#95a5a6', fg='white',
                            activebackground='#7f8c8d',
                            padx=20, pady=8, bd=0, cursor='hand2',
                            command=self.root.quit)
        exit_btn.pack(fill='x')

        # Bind Enter key
        password_entry.bind('<Return>', lambda e: self._login())

    def _login(self):
        """Xá»­ lĂ½ Ä‘Äƒng nháº­p."""
        import tkinter as tk
        from tkinter import messagebox

        username = self.username_var.get().strip()
        password = self.password_var.get()

        if not username or not password:
            messagebox.showwarning("Lá»—i", "Vui lĂ²ng nháº­p tĂªn Ä‘Äƒng nháº­p vĂ  máº­t kháº©u")
            return

        success, user_data = self.auth_manager.authenticate(username, password)

        if success:
            messagebox.showinfo("ThĂ nh cĂ´ng", f"ChĂ o má»«ng {user_data['full_name']}!")
            self.on_login_success(user_data)
        else:
            messagebox.showerror("Lá»—i", "TĂªn Ä‘Äƒng nháº­p hoáº·c máº­t kháº©u khĂ´ng chĂ­nh xĂ¡c")

