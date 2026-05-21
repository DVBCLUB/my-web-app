"""
MODULE PDF EXPORT - Xuất báo cáo & chứng từ ra PDF
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from utils import format_currency, number_to_text_vn


# Đăng ký font Unicode cho tiếng Việt
try:
    pdfmetrics.registerFont(TTFont('Times', 'times.ttf'))
except:
    pass


class PDFExporter:
    """Xuất báo cáo ra PDF."""

    def __init__(self, output_dir='reports'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export_expense_report(self, expenses, title="BÁO CÁO CHI PHÍ", 
                             start_date=None, end_date=None):
        """Xuất báo cáo chi phí ra PDF."""
        filename = os.path.join(self.output_dir, f"expense_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []

        # Tiêu đề
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Normal'],
            fontSize=16,
            textColor=colors.HexColor('#1a56a5'),
            spaceAfter=30,
            alignment=1,  # Center
            fontName='Helvetica-Bold'
        )

        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 0.3*cm))

        # Công ty
        company_style = ParagraphStyle(
            'Company',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.grey,
            spaceAfter=10,
            alignment=1,
        )
        elements.append(Paragraph("CÔNG TY CP XÂY DỰNG VÀ ĐẦU TƯ TRUNG HẢI", company_style))

        if start_date and end_date:
            elements.append(Paragraph(f"Từ {start_date} đến {end_date}", company_style))

        elements.append(Spacer(1, 0.5*cm))

        # Bảng chi phí
        data = [['STT', 'Ngày', 'Loại chi phí', 'Mô tả', 'Số tiền']]

        total = 0
        for idx, expense in enumerate(expenses, 1):
            amount = expense[-1]
            total += amount
            data.append([
                str(idx),
                expense[1],
                expense[3],
                expense[4][:30] if len(expense[4]) > 30 else expense[4],
                format_currency(amount)
            ])

        # Hàng tổng cộng
        data.append(['', '', '', 'TỔNG CỘNG:', format_currency(total)])

        table = Table(data, colWidths=[1*cm, 1.5*cm, 2*cm, 4*cm, 2*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a56a5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (3, 0), (3, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.lightblue]),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.5*cm))

        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=1,
        )
        elements.append(Paragraph(f"<i>Tạo lúc: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</i>", footer_style))

        doc.build(elements)
        return filename

    def export_financial_statement(self, income, expenses, filename=None):
        """Xuất báo cáo tài chính (Bảng cân đối)."""
        if filename is None:
            filename = os.path.join(self.output_dir, f"financial_statement_{datetime.now().strftime('%Y%m%d')}.pdf")

        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Normal'],
            fontSize=16,
            textColor=colors.HexColor('#1a56a5'),
            spaceAfter=30,
            alignment=1,
            fontName='Helvetica-Bold'
        )

        elements.append(Paragraph("BẢNG CÂN ĐỐI KẾ TOÁN", title_style))
        elements.append(Spacer(1, 0.5*cm))

        # Dữ liệu
        data = [
            ['TÀI KHOẢN', 'SỐ TIỀN'],
            ['Chi phí', format_currency(expenses)],
            ['Doanh thu', format_currency(income)],
            ['', ''],
            ['Lợi nhuận ròng', format_currency(income - expenses)],
        ]

        table = Table(data, colWidths=[5*cm, 4*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a56a5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))

        elements.append(table)

        doc.build(elements)
        return filename


class DocumentTemplate:
    """Tạo mẫu chứng từ PDF."""

    @staticmethod
    def create_expense_voucher(expense_data, output_path):
        """Tạo phiếu chi PDF."""
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        elements = []

        styles = getSampleStyleSheet()

        # Header
        title = Paragraph("<b>PHIẾU CHI</b>", ParagraphStyle(
            'Title', parent=styles['Normal'], fontSize=14, alignment=1
        ))
        elements.append(title)
        elements.append(Spacer(1, 0.5*cm))

        # Thông tin
        info_data = [
            ['Ngày chi:', expense_data.get('date', '')],
            ['Người chi:', expense_data.get('paid_by', '')],
            ['Dự án:', expense_data.get('project', '')],
            ['Loại chi phí:', expense_data.get('category', '')],
        ]

        info_table = Table(info_data, colWidths=[3*cm, 10*cm])
        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))

        elements.append(info_table)
        elements.append(Spacer(1, 0.5*cm))

        # Chi tiết
        details = f"""
        <b>Nội dung:</b> {expense_data.get('description', '')}<br/>
        <b>Số tiền:</b> {format_currency(expense_data.get('amount', 0))} đồng<br/>
        <b>Bằng chữ:</b> {number_to_text_vn(expense_data.get('amount', 0))}<br/>
        <b>Ghi chú:</b> {expense_data.get('notes', '')}
        """

        elements.append(Paragraph(details, styles['Normal']))
        elements.append(Spacer(1, 1*cm))

        # Chữ ký
        sig_data = [
            ['Người chi', 'Kế toán', 'Giám đốc'],
            ['', '', ''],
            ['(Ký & ghi rõ họ tên)', '(Ký & ghi rõ họ tên)', '(Ký & ghi rõ họ tên)'],
        ]

        sig_table = Table(sig_data, colWidths=[4*cm, 4*cm, 4*cm])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]))

        elements.append(sig_table)

        doc.build(elements)
