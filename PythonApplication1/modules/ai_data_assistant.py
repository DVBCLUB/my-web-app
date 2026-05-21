"""Safe text-to-SQL assistant for real accounting data questions."""

import re
import sqlite3
from datetime import date, timedelta

from database import get_connection


class AccountingDataAssistant:
    """Translate common Vietnamese business questions into safe SELECT SQL."""

    ALLOWED_TABLES = {
        'expenses', 'expense_categories', 'projects', 'documents', 'materials',
        'inventory_transactions', 'project_contracts', 'contract_billings',
        'project_revenues', 'journal_entries', 'construction_work_items',
        'advance_requests', 'employees',
    }

    SCHEMA_CONTEXT = """
    Bang chinh:
    - expenses(expense_date, project_id, category_id, description, amount, paid_by, payment_method, status)
    - expense_categories(code, name)
    - projects(code, name, budget, status)
    - materials(code, name, unit, quantity, unit_price, category)
    - inventory_transactions(material_id, transaction_type, quantity, transaction_date, project_id)
    - documents(doc_number, doc_date, supplier_name, amount, status)
    - project_contracts(project_id, contract_type, contract_no, partner_name, contract_value, status)
    - contract_billings(contract_id, billing_date, amount_before_vat, vat_amount, net_amount, status)
    - project_revenues(project_id, revenue_date, amount, vat_amount)
    - journal_entries(entry_date, debit_account, credit_account, amount)
    """

    def __init__(self):
        self.conn = get_connection()

    def answer(self, question):
        sql, params, label = self.build_sql(question)
        if not sql:
            return (
                "Mình chưa nhận ra dạng câu hỏi số liệu này. Bạn có thể hỏi kiểu: "
                "'Chi phí vật liệu tháng này là bao nhiêu?', 'Tồn kho hiện tại?', "
                "'Doanh thu quý này?', hoặc 'Top 5 chi phí tháng này'."
            )
        rows = self._execute_select(sql, params)
        return self._format_answer(question, label, rows, sql, params)

    def build_sql(self, question):
        q = self._normalize(question)
        start, end, period_label = self._period_from_question(q)

        if any(word in q for word in ('ton kho', 'tồn kho', 'vat tu ton', 'vật tư tồn')):
            return (
                """
                SELECT code, name, unit, quantity, unit_price,
                       quantity * COALESCE(unit_price, 0) AS value
                FROM materials
                WHERE status = 'active'
                ORDER BY value DESC, name
                LIMIT 20
                """,
                [],
                f"tồn kho hiện tại",
            )

        if any(word in q for word in ('doanh thu', 'revenue')):
            return (
                """
                SELECT COALESCE(SUM(amount), 0) AS total_revenue,
                       COALESCE(SUM(vat_amount), 0) AS total_vat,
                       COUNT(*) AS count_items
                FROM project_revenues
                WHERE revenue_date BETWEEN ? AND ?
                """,
                [start, end],
                f"doanh thu {period_label}",
            )

        if any(word in q for word in ('cong no', 'công nợ', 'phai thu', 'phải thu')):
            return (
                """
                SELECT p.code, p.name,
                       COALESCE(SUM(r.amount + COALESCE(r.vat_amount, 0)), 0) AS revenue_total,
                       COALESCE(SUM(b.net_amount), 0) AS billed_total
                FROM projects p
                LEFT JOIN project_revenues r ON r.project_id = p.id
                LEFT JOIN project_contracts c ON c.project_id = p.id AND c.contract_type = 'customer'
                LEFT JOIN contract_billings b ON b.contract_id = c.id
                GROUP BY p.id
                ORDER BY revenue_total DESC
                LIMIT 20
                """,
                [],
                "công nợ/phải thu theo dự án",
            )

        if any(word in q for word in ('top', 'lon nhat', 'lớn nhất')):
            return (
                """
                SELECT e.expense_date, COALESCE(p.name, '') AS project_name,
                       COALESCE(ec.name, '') AS category_name, e.description, e.amount
                FROM expenses e
                LEFT JOIN projects p ON p.id = e.project_id
                LEFT JOIN expense_categories ec ON ec.id = e.category_id
                WHERE e.expense_date BETWEEN ? AND ?
                ORDER BY e.amount DESC
                LIMIT 5
                """,
                [start, end],
                f"top chi phí {period_label}",
            )

        if any(word in q for word in ('chi phi', 'chi phí', 'cp ')):
            category_filter = self._category_filter(q)
            if category_filter:
                return (
                    """
                    SELECT COALESCE(SUM(e.amount), 0) AS total_amount, COUNT(*) AS count_items
                    FROM expenses e
                    LEFT JOIN expense_categories ec ON ec.id = e.category_id
                    WHERE e.expense_date BETWEEN ? AND ?
                      AND (LOWER(COALESCE(ec.name, '')) LIKE ? OR LOWER(COALESCE(e.description, '')) LIKE ?)
                    """,
                    [start, end, category_filter, category_filter],
                    f"chi phí {category_filter.replace('%', '')} {period_label}",
                )
            return (
                """
                SELECT COALESCE(ec.name, 'Chưa phân loại') AS category_name,
                       COALESCE(SUM(e.amount), 0) AS total_amount,
                       COUNT(*) AS count_items
                FROM expenses e
                LEFT JOIN expense_categories ec ON ec.id = e.category_id
                WHERE e.expense_date BETWEEN ? AND ?
                GROUP BY ec.id
                ORDER BY total_amount DESC
                LIMIT 20
                """,
                [start, end],
                f"chi phí {period_label}",
            )

        if any(word in q for word in ('hop dong', 'hợp đồng')):
            return (
                """
                SELECT contract_type, COUNT(*) AS count_items,
                       COALESCE(SUM(contract_value), 0) AS total_value
                FROM project_contracts
                GROUP BY contract_type
                ORDER BY total_value DESC
                """,
                [],
                "hợp đồng theo loại",
            )

        return None, [], ''

    def run_sql(self, sql, params=None):
        return self._execute_select(sql, params or [])

    def _execute_select(self, sql, params):
        self._guard_sql(sql)
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def _guard_sql(self, sql):
        compact = self._normalize(sql)
        if not compact.startswith('select'):
            raise ValueError('Chi cho phep truy van SELECT.')
        banned = (' insert ', ' update ', ' delete ', ' drop ', ' alter ', ' pragma ', ' attach ', ' detach ', ';')
        if any(token in f" {compact} " for token in banned):
            raise ValueError('SQL khong an toan.')
        tables = set(re.findall(r'\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)', compact))
        if not tables.issubset(self.ALLOWED_TABLES):
            raise ValueError('SQL dung bang chua duoc phep truy cap.')

    def _format_answer(self, question, label, rows, sql, params):
        if not rows:
            return f"Không có dữ liệu cho {label}."
        first = rows[0]
        if len(rows) == 1 and any(k.startswith('total') or k in ('count_items',) for k in first):
            parts = []
            for key, value in first.items():
                if isinstance(value, (int, float)):
                    parts.append(f"{self._label(key)}: {value:,.0f}")
                else:
                    parts.append(f"{self._label(key)}: {value}")
            return f"Kết quả {label}: " + "; ".join(parts) + "."

        lines = [f"Kết quả {label}:"]
        for row in rows[:10]:
            bits = []
            for key, value in row.items():
                if isinstance(value, (int, float)):
                    bits.append(f"{self._label(key)} {value:,.0f}")
                elif value not in (None, ''):
                    bits.append(str(value))
            lines.append("- " + " | ".join(bits))
        if len(rows) > 10:
            lines.append(f"... còn {len(rows) - 10} dòng khác.")
        return "\n".join(lines)

    def _period_from_question(self, q):
        today = date.today()
        if 'nam nay' in q or 'năm nay' in q:
            return date(today.year, 1, 1).isoformat(), date(today.year, 12, 31).isoformat(), 'năm nay'
        if 'quy nay' in q or 'quý này' in q:
            quarter = (today.month - 1) // 3 + 1
            start_month = (quarter - 1) * 3 + 1
            start = date(today.year, start_month, 1)
            end_month = start_month + 2
            end = self._month_end(today.year, end_month)
            return start.isoformat(), end.isoformat(), 'quý này'
        if 'thang truoc' in q or 'tháng trước' in q:
            first = today.replace(day=1)
            prev_end = first - timedelta(days=1)
            prev_start = prev_end.replace(day=1)
            return prev_start.isoformat(), prev_end.isoformat(), 'tháng trước'
        start = today.replace(day=1)
        return start.isoformat(), self._month_end(today.year, today.month).isoformat(), 'tháng này'

    def _month_end(self, year, month):
        if month == 12:
            return date(year, 12, 31)
        return date(year, month + 1, 1) - timedelta(days=1)

    def _category_filter(self, q):
        patterns = {
            ('vat lieu', 'vật liệu', 'vat tu', 'vật tư'): '%vat%',
            ('nhan cong', 'nhân công', 'luong', 'lương'): '%nhan%',
            ('may thi cong', 'máy thi công', 'thiet bi', 'thiết bị'): '%may%',
            ('thau phu', 'thầu phụ'): '%thau%',
            ('van phong', 'văn phòng'): '%van phong%',
        }
        for markers, value in patterns.items():
            if any(marker in q for marker in markers):
                return value
        return ''

    def _label(self, key):
        return {
            'total_amount': 'tổng tiền',
            'total_revenue': 'doanh thu',
            'total_vat': 'VAT',
            'count_items': 'số dòng',
            'category_name': 'loại',
            'project_name': 'dự án',
            'quantity': 'tồn kho',
            'value': 'giá trị',
        }.get(key, key)

    def _normalize(self, text):
        return re.sub(r'\s+', ' ', str(text or '').strip().lower())
