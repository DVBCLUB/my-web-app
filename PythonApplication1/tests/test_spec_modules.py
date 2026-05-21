import os
import tempfile
import unittest


class SpecModuleSmokeTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["ACCOUNTING_DB_PATH"] = os.path.join(self.tmpdir.name, "accounting.db")
        from database import init_database

        init_database()
        self._connections = []

    def tearDown(self):
        for conn in self._connections:
            conn.close()
        from database import close_connection

        close_connection()
        self.tmpdir.cleanup()

    def test_payroll_progressive_pit_and_lines(self):
        from database import get_connection
        from modules.payroll import PayrollManager

        conn = get_connection()
        self._connections.append(conn)
        cur = conn.cursor()
        cur.execute("INSERT INTO employees (full_name, dependents) VALUES ('Nguyen Van A', 0)")
        employee_id = cur.lastrowid
        cur.execute("INSERT INTO projects (code, name) VALUES ('P001', 'Cong trinh 1')")
        project_id = cur.lastrowid
        conn.commit()

        manager = PayrollManager()
        self._connections.append(manager.conn)
        manager.add_timesheet(employee_id, project_id, "2026-05-10", work_days=20, daily_rate=1_000_000)
        lines = manager.calculate_period("2026-05")
        self.assertEqual(len(lines), 1)
        self.assertGreater(lines[0]["bhxh_employee"], 0)
        self.assertGreaterEqual(lines[0]["pit_amount"], 0)
        run_id = manager.create_payroll_run("2026-05")
        self.assertGreater(run_id, 0)

    def test_material_average_cost_and_low_stock(self):
        from modules.materials import MaterialManager

        manager = MaterialManager()
        self._connections.append(manager.conn)
        material_id = manager.add_material("XM01", "Xi mang", "bao", 100_000, "Vat tu", "NCC", min_quantity=5)
        manager.receive_material(material_id, 10, 120_000)
        manager.receive_material(material_id, 10, 80_000)
        self.assertEqual(manager.get_average_cost(material_id), 100_000)
        manager.issue_material(material_id, 16, None)
        self.assertEqual(len(manager.check_low_stock()), 1)

    def test_budget_and_subcontract_managers(self):
        from database import get_connection
        from modules.budget import BudgetManager
        from modules.subcontract import SubcontractManager

        conn = get_connection()
        self._connections.append(conn)
        cur = conn.cursor()
        cur.execute("INSERT INTO projects (code, name) VALUES ('P002', 'Cong trinh 2')")
        project_id = cur.lastrowid
        cur.execute("INSERT INTO expense_categories (code, name) VALUES ('VT', 'Vat tu')")
        category_id = cur.lastrowid
        cur.execute("""
            INSERT INTO expenses (expense_date, project_id, category_id, description, amount, status)
            VALUES ('2026-05-11', ?, ?, 'Chi phi vat tu', 1200000, 'draft')
        """, (project_id, category_id))
        conn.commit()

        budget = BudgetManager()
        self._connections.append(budget.conn)
        budget.create_budget_version(project_id, "V1", items=[{
            "cost_category": "Vat tu",
            "description": "Vat tu",
            "budget_amount": 1_000_000,
        }])
        alerts = budget.get_budget_alerts(project_id, threshold_percent=10)
        self.assertEqual(len(alerts), 1)

        subcontract = SubcontractManager()
        self._connections.append(subcontract.conn)
        subcontractor_id = subcontract.add_subcontractor("Nha thau A")
        payment_id = subcontract.record_payment(subcontractor_id, 500_000, project_id=project_id)
        self.assertGreater(payment_id, 0)

    def test_operational_controls_from_updated_spec(self):
        from database import get_connection
        from modules.accounting import ExpenseManager
        from modules.currency import CurrencyManager
        from modules.guarantee import GuaranteeManager
        from modules.notification_center import NotificationCenter
        from modules.vendor_scorecard import VendorScorecardManager

        conn = get_connection()
        self._connections.append(conn)
        cur = conn.cursor()
        cur.execute("INSERT INTO projects (code, name, budget) VALUES ('P003', 'Cong trinh 3', 1000000)")
        project_id = cur.lastrowid
        cur.execute("INSERT INTO expense_categories (code, name) VALUES ('CP', 'Chi phi')")
        category_id = cur.lastrowid
        cur.execute("""
            INSERT INTO project_contracts
            (project_id, contract_type, contract_no, partner_name, signed_date, contract_value)
            VALUES (?, 'customer', 'HD001', 'Chu dau tu', '2026-05-01', 10000000)
        """, (project_id,))
        contract_id = cur.lastrowid
        cur.execute("""
            INSERT INTO warranty_periods
            (contract_id, warranty_scope, start_date, end_date, retention_amount)
            VALUES (?, 'Bao hanh cong trinh', '2026-05-01', '2026-06-01', 100000)
        """, (contract_id,))
        warranty_id = cur.lastrowid
        conn.commit()

        guarantee = GuaranteeManager()
        self._connections.append(guarantee.conn)
        bond_id = guarantee.add_bond(contract_id, "performance", 500000, expiry_date="2026-06-10")
        self.assertGreater(bond_id, 0)
        self.assertGreaterEqual(guarantee.get_bond_summary_by_project(project_id)["total_amount"], 500000)
        self.assertGreater(guarantee.release_retention(warranty_id), 0)

        vendor = VendorScorecardManager()
        self._connections.append(vendor.conn)
        vendor.record_score("NCC A", "2026-05", 5, 4, 4, 5)
        self.assertEqual(vendor.get_vendor_summary()[0]["status"], "preferred")

        currency = CurrencyManager()
        self._connections.append(currency.conn)
        currency.set_rate("USD", "2026-05-01", 25000)
        fx_id = currency.record_foreign_transaction("invoice", None, "USD", 100, "2026-05-02")
        self.assertGreater(fx_id, 0)

        expense = ExpenseManager()
        self._connections.append(expense.conn)
        expense.add_expense("2026-05-03", project_id, category_id, "Vuot ngan sach", 950000,
                            "A", "Tien mat", "", 1)
        alerts = NotificationCenter().get_all_alerts()
        self.assertTrue(any(alert["source"] in {"budget", "guarantee_bond"} for alert in alerts))


if __name__ == "__main__":
    unittest.main()
