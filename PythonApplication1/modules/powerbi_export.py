"""Power BI dataset export to CSV files."""

import csv
from datetime import datetime
from pathlib import Path

from database import get_connection


class PowerBIExporter:
    def __init__(self, output_dir='reports/powerbi'):
        self.conn = get_connection()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self):
        datasets = {
            'project_costs': self._project_costs,
            'contract_progress': self._contract_progress,
            'cash_flow': self._cash_flow,
        }
        results = {}
        for name, loader in datasets.items():
            rows, headers = loader()
            path = self.output_dir / f"{name}.csv"
            with path.open('w', newline='', encoding='utf-8-sig') as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
                writer.writerows(rows)
            self._log(name, len(rows), 'success', str(path))
            results[name] = str(path)
        return results

    def _project_costs(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT p.code, p.name, ec.name,
                   COALESCE(cp.planned_amount, 0),
                   COALESCE(SUM(e.amount), 0)
            FROM projects p
            CROSS JOIN expense_categories ec
            LEFT JOIN project_cost_plans cp ON cp.project_id = p.id AND cp.category_id = ec.id
            LEFT JOIN expenses e ON e.project_id = p.id AND e.category_id = ec.id
            WHERE p.code != 'CHUNG'
            GROUP BY p.id, ec.id
            HAVING COALESCE(cp.planned_amount, 0) > 0 OR COALESCE(SUM(e.amount), 0) > 0
        """)
        return cursor.fetchall(), ['project_code', 'project_name', 'category', 'planned', 'actual']

    def _contract_progress(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT p.code, p.name, c.contract_no, c.partner_name, c.contract_type,
                   c.contract_value, COALESCE(SUM(b.net_amount), 0),
                   c.contract_value - COALESCE(SUM(b.net_amount), 0)
            FROM project_contracts c
            JOIN projects p ON p.id = c.project_id
            LEFT JOIN contract_billings b ON b.contract_id = c.id
            GROUP BY c.id
        """)
        return cursor.fetchall(), ['project_code', 'project_name', 'contract_no', 'partner', 'type', 'contract_value', 'billed', 'remaining']

    def _cash_flow(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT expense_date, COALESCE(p.code, ''), description, -amount, payment_method
            FROM expenses e
            LEFT JOIN projects p ON p.id = e.project_id
            UNION ALL
            SELECT revenue_date, COALESCE(p.code, ''), description, amount + COALESCE(vat_amount, 0), 'revenue'
            FROM project_revenues r
            LEFT JOIN projects p ON p.id = r.project_id
            ORDER BY 1
        """)
        return cursor.fetchall(), ['date', 'project_code', 'description', 'amount', 'source']

    def _log(self, dataset_name, row_count, status, message):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO powerbi_sync_log (dataset_name, synced_at, status, row_count, message)
            VALUES (?, ?, ?, ?, ?)
        """, (dataset_name, datetime.now().isoformat(timespec='seconds'), status, row_count, message))
        self.conn.commit()
