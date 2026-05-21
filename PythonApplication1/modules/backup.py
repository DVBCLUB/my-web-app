"""
MODULE BACKUP - Sao lÆ°u & phá»¥c há»“i dá»¯ liá»‡u
"""

import sqlite3
import shutil
import os
import tempfile
from datetime import datetime
from pathlib import Path


class BackupManager:
    """Quáº£n lĂ½ sao lÆ°u vĂ  phá»¥c há»“i."""

    def __init__(self, db_path=None, backup_dir='backups'):
        if db_path is None:
            from database import get_database_path
            db_path = get_database_path()
        self.db_path = db_path
        self.backup_dir = backup_dir
        Path(self.backup_dir).mkdir(exist_ok=True)

    def create_backup(self, backup_name=None):
        """Táº¡o file sao lÆ°u."""
        if backup_name is None:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

        backup_path = os.path.join(self.backup_dir, backup_name)

        try:
            self._checkpoint_source()
            shutil.copy2(self.db_path, backup_path)
            ok, detail = self.verify_backup(backup_path)
            if not ok:
                return False, f"Sao lưu tạo file nhưng kiểm tra thất bại: {detail}"
            return True, f"Sao lưu thành công và đã kiểm tra toàn vẹn: {backup_path}\n{detail}"
        except Exception as e:
            return False, f"Lỗi sao lưu: {str(e)}"

    def verify_backup(self, backup_path):
        """Restore thử vào file tạm, chạy integrity_check và so row count."""
        tmp_path = None
        try:
            if not os.path.exists(backup_path):
                return False, "File backup không tồn tại."
            fd, tmp_path = tempfile.mkstemp(prefix='backup_verify_', suffix='.db')
            os.close(fd)
            shutil.copy2(backup_path, tmp_path)
            source_counts = self._table_counts(self.db_path)
            backup_counts = self._table_counts(tmp_path)
            conn = sqlite3.connect(tmp_path)
            integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
            conn.close()
            if integrity != 'ok':
                return False, f"PRAGMA integrity_check={integrity}"
            mismatches = {
                table: (source_counts.get(table), backup_counts.get(table))
                for table in source_counts
                if source_counts.get(table) != backup_counts.get(table)
            }
            if mismatches:
                return False, f"Row count lệch: {mismatches}"
            return True, f"Integrity OK, {len(source_counts)} bảng khớp row count."
        except Exception as exc:
            return False, str(exc)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _table_counts(self, db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        counts = {}
        for table in tables:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            counts[table] = cursor.fetchone()[0]
        conn.close()
        return counts

    def _checkpoint_source(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA wal_checkpoint(FULL)')
            conn.close()
        except sqlite3.DatabaseError:
            pass

    def restore_backup(self, backup_file):
        """Phá»¥c há»“i tá»« file sao lÆ°u."""
        backup_path = os.path.join(self.backup_dir, backup_file)

        if not os.path.exists(backup_path):
            return False, "File sao lÆ°u khĂ´ng tá»“n táº¡i"

        try:
            # Táº¡o sao lÆ°u cá»§a database hiá»‡n táº¡i trÆ°á»›c khi phá»¥c há»“i
            self.create_backup(f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")

            # Phá»¥c há»“i database
            shutil.copy2(backup_path, self.db_path)
            return True, "Phá»¥c há»“i dá»¯ liá»‡u thĂ nh cĂ´ng"
        except Exception as e:
            return False, f"Lá»—i phá»¥c há»“i: {str(e)}"

    def get_backup_list(self):
        """Láº¥y danh sĂ¡ch cĂ¡c file sao lÆ°u."""
        backups = []
        if os.path.exists(self.backup_dir):
            for file in os.listdir(self.backup_dir):
                if file.endswith('.db'):
                    file_path = os.path.join(self.backup_dir, file)
                    file_size = os.path.getsize(file_path) / 1024  # KB
                    file_time = os.path.getmtime(file_path)
                    file_date = datetime.fromtimestamp(file_time)

                    backups.append({
                        'name': file,
                        'size': f"{file_size:.2f} KB",
                        'date': file_date.strftime('%d/%m/%Y %H:%M:%S'),
                        'path': file_path
                    })

        return sorted(backups, key=lambda x: x['date'], reverse=True)

    def delete_backup(self, backup_file):
        """XĂ³a file sao lÆ°u."""
        backup_path = os.path.join(self.backup_dir, backup_file)

        try:
            os.remove(backup_path)
            return True, "XĂ³a file sao lÆ°u thĂ nh cĂ´ng"
        except Exception as e:
            return False, f"Lá»—i xĂ³a file: {str(e)}"

    def export_to_csv(self, table_name, output_file):
        """Xuáº¥t báº£ng ra CSV."""
        try:
            import pandas as pd

            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            conn.close()

            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            return True, f"Xuáº¥t CSV thĂ nh cĂ´ng: {output_file}"
        except Exception as e:
            return False, f"Lá»—i xuáº¥t CSV: {str(e)}"

    def import_from_csv(self, table_name, csv_file):
        """Nháº­p dá»¯ liá»‡u tá»« CSV."""
        try:
            import pandas as pd

            df = pd.read_csv(csv_file, encoding='utf-8-sig')

            conn = sqlite3.connect(self.db_path)
            df.to_sql(table_name, conn, if_exists='append', index=False)
            conn.close()

            return True, f"Nháº­p CSV thĂ nh cĂ´ng"
        except Exception as e:
            return False, f"Lá»—i nháº­p CSV: {str(e)}"

    def get_database_statistics(self):
        """Láº¥y thá»‘ng kĂª database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Láº¥y tĂªn cĂ¡c báº£ng
            cursor.execute('''
                SELECT name FROM sqlite_master WHERE type='table'
            ''')
            tables = cursor.fetchall()

            stats = {}
            for table in tables:
                table_name = table[0]
                cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
                count = cursor.fetchone()[0]
                stats[table_name] = count

            conn.close()
            return stats
        except Exception as e:
            return {'error': str(e)}


class AutoBackupScheduler:
    """Láº­p lá»‹ch sao lÆ°u tá»± Ä‘á»™ng."""

    def __init__(self, backup_manager, interval_hours=24):
        self.backup_manager = backup_manager
        self.interval_hours = interval_hours
        self.is_running = False

    def start(self):
        """Báº¯t Ä‘áº§u láº­p lá»‹ch sao lÆ°u."""
        import threading
        import time

        self.is_running = True

        def backup_loop():
            while self.is_running:
                # Cháº¡y sao lÆ°u
                self.backup_manager.create_backup()

                # Äá»£i Ä‘á»§ khoáº£ng thá»i gian
                time.sleep(self.interval_hours * 3600)

        backup_thread = threading.Thread(target=backup_loop, daemon=True)
        backup_thread.start()

    def stop(self):
        """Dá»«ng láº­p lá»‹ch sao lÆ°u."""
        self.is_running = False


class DatabaseOptimizer:
    """Tá»‘i Æ°u hĂ³a database."""

    @staticmethod
    def vacuum_database(db_path):
        """LĂ m sáº¡ch database."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('VACUUM')
            conn.commit()
            conn.close()
            return True, "Tá»‘i Æ°u hĂ³a database thĂ nh cĂ´ng"
        except Exception as e:
            return False, f"Lá»—i: {str(e)}"

    @staticmethod
    def create_indexes(db_path):
        """Táº¡o index Ä‘á»ƒ tÄƒng tá»‘c Ä‘á»™ truy váº¥n."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            indexes = [
                'CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date)',
                'CREATE INDEX IF NOT EXISTS idx_expenses_project ON expenses(project_id)',
                'CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id)',
                'CREATE INDEX IF NOT EXISTS idx_documents_date ON documents(doc_date)',
                'CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entries(entry_date)',
                'CREATE INDEX IF NOT EXISTS idx_inventory_date ON inventory_transactions(transaction_date)',
            ]

            for index in indexes:
                cursor.execute(index)

            conn.commit()
            conn.close()
            return True, "Táº¡o index thĂ nh cĂ´ng"
        except Exception as e:
            return False, f"Lá»—i: {str(e)}"

