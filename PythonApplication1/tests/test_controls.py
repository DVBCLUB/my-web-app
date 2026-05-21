import os
import tempfile
import unittest
from pathlib import Path


class ControlsSmokeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.old_db = os.environ.get('ACCOUNTING_DB_PATH')
        os.environ['ACCOUNTING_DB_PATH'] = str(Path(self.tmp.name) / 'test.db')
        from database import init_database
        init_database()

    def tearDown(self):
        if self.old_db is None:
            os.environ.pop('ACCOUNTING_DB_PATH', None)
        else:
            os.environ['ACCOUNTING_DB_PATH'] = self.old_db
        self.tmp.cleanup()

    def test_approval_thresholds(self):
        from modules.controls import ApprovalThresholdManager
        manager = ApprovalThresholdManager()
        self.assertTrue(manager.can_approve('employee', 400000)[0])
        self.assertFalse(manager.can_approve('employee', 600000)[0])
        manager.conn.close()

    def test_password_hash_roundtrip(self):
        from modules.auth import AuthManager
        hashed = AuthManager.hash_password('password123')
        self.assertTrue(AuthManager.verify_password('password123', hashed))
        self.assertFalse(AuthManager.verify_password('wrongpass', hashed))

    def test_journal_reversal(self):
        from database import get_connection
        from modules.controls import JournalControlManager
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO journal_entries
            (entry_date, description, debit_account, credit_account, amount)
            VALUES ('2026-05-19', 'Test entry', '642', '111', 100000)
        ''')
        entry_id = cursor.lastrowid
        conn.commit()

        manager = JournalControlManager()
        reversal_id = manager.reverse_entry(entry_id, actor_id=1)
        row = conn.execute('SELECT amount, reversal_of_entry_id FROM journal_entries WHERE id = ?', (reversal_id,)).fetchone()
        self.assertEqual(row['reversal_of_entry_id'], entry_id)
        self.assertEqual(row['amount'], -100000)
        manager.conn.close()
        conn.close()


if __name__ == '__main__':
    unittest.main()
