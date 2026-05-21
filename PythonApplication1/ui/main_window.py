"""
MAIN WINDOW - Giao diện chính của ứng dụng
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta
from importlib import import_module
import os
import re

from modules.accounting import ExpenseManager
from modules.backup import BackupManager
from modules.branding import ensure_app_logo_asset
import config
from ui.dialogs import (
    ExpenseDialog, DocumentDialog, MaterialDialog,
    BulkExpenseDialog, OCRImportDialog,
    InventoryTransactionDialog, AccountDialog,
    SimpleCatalogDialog, AccountMappingDialog, TemplateFieldDialog,
    TemplateMappingDialog, ConstructionRecordDialog, RenderTemplateDialog, ExpensePrintDialog,
    ContractDialog, BillingDialog, CostPlanDialog, RevenueDialog,
)
from utils import ExcelImporter, ExcelExporter, format_money, format_quantity, parse_number
from ui.theme import THEME, apply_ttk_styles, create_modern_button, draw_header_accent, format_status
from ui.expense_table import ExpenseDataTable

# AI chat is currently disabled in this streamlined accounting build.
AI_CHAT_AVAILABLE = False


class _LazyManager:
    """Delay constructing heavier managers until their screen is opened."""

    def __init__(self, module_name, class_name):
        self._module_name = module_name
        self._class_name = class_name
        self._instance = None

    def _get(self):
        if self._instance is None:
            factory = getattr(import_module(self._module_name), self._class_name)
            self._instance = factory()
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get(), name)


def _wrap_words(text, max_chars=26, max_lines=3):
    words = str(text or '').split()
    lines = []
    current = ''
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(' .') + '...'
    return "\n".join(lines)


class MainWindow:
    def __init__(self, root, current_user=None):
        self.root = root
        self.current_user = current_user or {
            'full_name': '',
            'username': '',
            'role': 'Kế toán',
        }
        self.root.title("FasTrack ERP - Phần mềm kế toán")
        self.root.geometry("1360x780")
        self.root.resizable(True, True)
        self.app_logo_path, self.app_icon_path = ensure_app_logo_asset()
        if self.app_icon_path:
            try:
                self.root.iconbitmap(self.app_icon_path)
            except Exception:
                pass
        self.theme = THEME.copy()
        self.root.configure(bg=self.theme['bg'])
        apply_ttk_styles(self.root)

        # Các manager
        self.expense_mgr = ExpenseManager()
        self.document_mgr = _LazyManager('modules.invoices', 'DocumentManager')
        self.material_mgr = _LazyManager('modules.materials', 'MaterialManager')
        self.report_gen = _LazyManager('modules.reports', 'ReportGenerator')
        self.compliance_mgr = _LazyManager('modules.compliance', 'ComplianceManager')
        self.account_catalog_mgr = _LazyManager('modules.compliance', 'AccountCatalogManager')
        self.knowledge_mgr = _LazyManager('modules.knowledge_base', 'KnowledgeBaseManager')
        self.utility_mgr = _LazyManager('modules.utilities', 'UtilityManager')
        self.construction_mgr = _LazyManager('modules.construction', 'ConstructionManager')
        self.project_acct_mgr = _LazyManager('modules.project_accounting', 'ProjectAccountingManager')
        self.template_renderer = _LazyManager('modules.template_renderer', 'TemplateRenderer')
        self.bank_recon_mgr = _LazyManager('modules.bank_reconciliation', 'BankReconciliationManager')
        self.vat_report_mgr = _LazyManager('modules.tax_reports', 'VATReportManager')
        self.evm_mgr = _LazyManager('modules.evm', 'EVMManager')
        self.cash_flow_alert_mgr = _LazyManager('modules.cash_flow_alerts', 'CashFlowAlertManager')
        self.auth_mgr = _LazyManager('modules.auth', 'AuthManager')
        self.project_access_mgr = _LazyManager('modules.auth', 'ProjectAccessManager')
        self.variance_mgr = _LazyManager('modules.variance_analysis', 'VarianceAnalysisManager')
        self.fiscal_lock_mgr = _LazyManager('modules.fiscal_lock', 'FiscalPeriodLockManager')
        self.material_control_mgr = _LazyManager('modules.material_controls', 'MaterialControlManager')
        self.payroll_mgr = _LazyManager('modules.payroll', 'PayrollManager')
        self.powerbi_exporter = _LazyManager('modules.powerbi_export', 'PowerBIExporter')
        self.einvoice_mgr = _LazyManager('modules.einvoice', 'EInvoiceManager')
        self.qr_mgr = _LazyManager('modules.qr_verification', 'QRVerificationManager')
        self.notification_center = _LazyManager('modules.notification_center', 'NotificationCenter')
        self.audit_mgr = _LazyManager('modules.controls', 'AuditLogManager')
        self.approval_threshold_mgr = _LazyManager('modules.controls', 'ApprovalThresholdManager')
        self.journal_control_mgr = _LazyManager('modules.controls', 'JournalControlManager')
        self.extension_report_mgr = _LazyManager('modules.controls', 'ExtensionReportManager')
        self._last_expense_id = None
        self._tab_loaded = {}
        self._active_screen_command = None
        self._active_screen_name = None
        self._last_activity_time = datetime.now()
        self._session_locked = False

        # Xây dựng giao diện
        self._build_ui()
        self._setup_keyboard_shortcuts()
        self._setup_session_timeout()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('Treeview', rowheight=32, font=('Segoe UI', 11), background=self.theme['PANEL_BG'],
                        fieldbackground=self.theme['PANEL_BG'], foreground=self.theme['TEXT_PRIMARY'])
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'),
                        background=self.theme['PAGE_BG'], foreground=self.theme['TEXT_MUTED'])
        style.map('Treeview',
                  background=[('selected', '#EBF3FF')],
                  foreground=[('selected', self.theme['ACCENT_BLUE'])])
        style.configure('TNotebook', background=self.theme['bg'], borderwidth=0)
        style.configure('TNotebook.Tab', font=('Segoe UI', 10), padding=(14, 8))

    def _make_button(self, parent, text, command, color=None, padx=14, variant=None):
        if variant:
            return create_modern_button(parent, text, command, variant=variant, padx=padx)
        variant_map = {
            self.theme.get('success'): 'success',
            self.theme.get('danger'): 'danger',
            self.theme.get('warning'): 'warning',
            self.theme.get('info'): 'info',
            self.theme.get('accent'): 'accent',
        }
        v = variant_map.get(color, 'primary')
        return create_modern_button(parent, text, command, variant=v, padx=padx)

    def _setup_keyboard_shortcuts(self):
        """Global shortcuts for frequent accounting actions."""
        bindings = {
            '<Control-n>': lambda _e: self._add_expense(),
            '<Control-N>': lambda _e: self._add_expense(),
            '<Control-f>': lambda _e: self._focus_active_search_field(),
            '<Control-F>': lambda _e: self._focus_active_search_field(),
            '<Control-e>': lambda _e: self._export_current_view_excel(),
            '<Control-E>': lambda _e: self._export_current_view_excel(),
            '<Control-p>': lambda _e: self._print_current_view_pdf(),
            '<Control-P>': lambda _e: self._print_current_view_pdf(),
            '<Control-z>': lambda _e: self._undo_last_entry(),
            '<Control-Z>': lambda _e: self._undo_last_entry(),
            '<F5>': lambda _e: self._refresh_current_view(),
        }
        for sequence, handler in bindings.items():
            self.root.bind(sequence, handler)

    def _setup_session_timeout(self):
        self.root.bind_all('<KeyPress>', self._record_activity, add='+')
        self.root.bind_all('<ButtonPress>', self._record_activity, add='+')
        self.root.bind_all('<Motion>', self._record_activity, add='+')
        self.root.after(60000, self._check_session_timeout)

    def _record_activity(self, _event=None):
        if not self._session_locked:
            self._last_activity_time = datetime.now()

    def _check_session_timeout(self):
        timeout_minutes = int(getattr(config, 'SESSION_TIMEOUT_MINUTES', 30) or 30)
        if not self._session_locked and datetime.now() - self._last_activity_time >= timedelta(minutes=timeout_minutes):
            self._lock_session()
        self.root.after(60000, self._check_session_timeout)

    def _lock_session(self):
        self._session_locked = True
        lock = tk.Toplevel(self.root)
        lock.title("Khóa phiên làm việc")
        lock.transient(self.root)
        lock.grab_set()
        lock.resizable(False, False)
        lock.configure(bg=self.theme['PANEL_BG'])
        lock.protocol("WM_DELETE_WINDOW", lambda: None)
        lock.geometry("+%d+%d" % (
            self.root.winfo_rootx() + max(self.root.winfo_width() // 2 - 190, 40),
            self.root.winfo_rooty() + max(self.root.winfo_height() // 2 - 95, 40),
        ))

        frame = tk.Frame(lock, bg=self.theme['PANEL_BG'])
        frame.pack(fill='both', expand=True, padx=22, pady=18)
        tk.Label(frame, text="Phiên làm việc đã khóa", bg=self.theme['PANEL_BG'],
                 fg=self.theme['TEXT_PRIMARY'], font=('Segoe UI', 13, 'bold')).pack(anchor='w')
        username = self.current_user.get('username') or ''
        tk.Label(frame, text=f"Nhập mật khẩu của {username} để tiếp tục.",
                 bg=self.theme['PANEL_BG'], fg=self.theme['TEXT_MUTED'],
                 font=('Segoe UI', 10)).pack(anchor='w', pady=(4, 12))

        password_var = tk.StringVar()
        password_entry = ttk.Entry(frame, textvariable=password_var, show='*', width=34)
        password_entry.pack(fill='x')
        error_label = tk.Label(frame, text="", bg=self.theme['PANEL_BG'],
                               fg=self.theme['ACCENT_RED'], font=('Segoe UI', 9))
        error_label.pack(anchor='w', pady=(8, 0))

        def unlock(_event=None):
            if self._verify_current_user_password(password_var.get()):
                self._session_locked = False
                self._last_activity_time = datetime.now()
                lock.grab_release()
                lock.destroy()
            else:
                error_label.config(text="Mật khẩu không đúng.")
                password_entry.select_range(0, 'end')
                password_entry.focus_set()

        button_row = tk.Frame(frame, bg=self.theme['PANEL_BG'])
        button_row.pack(fill='x', pady=(12, 0))
        create_modern_button(button_row, "Mở khóa", unlock, variant='primary',
                             padx=14, pady=7).pack(side='left')
        create_modern_button(button_row, "Đăng xuất", self._on_close, variant='secondary',
                             padx=14, pady=7).pack(side='left', padx=(8, 0))
        password_entry.bind('<Return>', unlock)
        password_entry.focus_set()

    def _verify_current_user_password(self, password):
        username = self.current_user.get('username')
        if not username:
            return False
        try:
            cursor = self.auth_mgr.conn.cursor()
            cursor.execute('SELECT password FROM users WHERE username = ? AND active = 1', (username,))
            row = cursor.fetchone()
            AuthManager = getattr(import_module('modules.auth'), 'AuthManager')
            return bool(row and AuthManager.verify_password(password, row['password']))
        except Exception:
            return False

    def _create_quick_actions_button(self):
        if not hasattr(self, 'body_frame'):
            return
        self.quick_actions_btn = create_modern_button(
            self.body_frame, "Thao tác nhanh", self._show_quick_actions,
            variant='primary', padx=14, pady=8, font=('Segoe UI', 9, 'bold')
        )
        self.quick_actions_btn.place(relx=1.0, rely=1.0, anchor='se', x=-22, y=-18)

    def _show_quick_actions(self):
        popup = tk.Toplevel(self.root)
        popup.title("Thao tác nhanh")
        popup.transient(self.root)
        popup.resizable(False, False)
        popup.configure(bg=self.theme['panel'])
        popup.geometry("+%d+%d" % (
            self.root.winfo_rootx() + self.root.winfo_width() - 330,
            self.root.winfo_rooty() + self.root.winfo_height() - 330,
        ))

        tk.Label(
            popup, text="Thao tác nhanh", font=('Segoe UI', 12, 'bold'),
            bg=self.theme['panel'], fg=self.theme['text']
        ).pack(anchor='w', padx=14, pady=(12, 6))
        actions = [
            ("Thêm chi phí", "Ctrl+N", self._add_expense, 'success'),
            ("Xuất Excel màn hình hiện tại", "Ctrl+E", self._export_current_view_excel, 'outline'),
            ("In / Xuất PDF", "Ctrl+P", self._print_current_view_pdf, 'outline'),
            ("Làm mới dữ liệu", "F5", self._refresh_current_view, 'primary'),
            ("Tìm kiếm", "Ctrl+F", self._focus_active_search_field, 'secondary'),
        ]
        for label, shortcut, command, variant in actions:
            row = tk.Frame(popup, bg=self.theme['panel'])
            row.pack(fill='x', padx=12, pady=4)
            create_modern_button(
                row, f"{label} ({shortcut})",
                lambda cmd=command, win=popup: (win.destroy(), cmd()),
                variant=variant, padx=12, pady=7
            ).pack(fill='x')

    def _focus_active_search_field(self):
        candidates = (
            'active_search_entry', 'global_search_entry', 'construction_search_entry',
            'knowledge_search_entry', 'account_search_entry', 'compliance_search_entry',
            'contract_search_entry',
        )
        for attr in candidates:
            widget = getattr(self, attr, None)
            if widget and widget.winfo_exists():
                widget.focus_set()
                try:
                    widget.select_range(0, 'end')
                except Exception:
                    pass
                return "break"
        messagebox.showinfo("Tìm kiếm", "Màn hình hiện tại chưa có ô tìm kiếm nhanh.")
        return "break"

    def _export_current_view_excel(self):
        command = getattr(self, '_active_screen_command', None)
        if command == self._show_expenses:
            self._export_expenses()
        elif command == self._show_documents:
            self._export_documents_excel()
        elif command == self._show_materials:
            self._export_materials_excel()
        elif command == self._show_reports:
            self._export_report_excel()
        elif command in (self._show_project_accounting, self._show_contracts):
            self._export_qt06_project()
        else:
            messagebox.showinfo("Xuất Excel", "Màn hình hiện tại chưa có lệnh xuất Excel riêng.")
        return "break"

    def _print_current_view_pdf(self):
        command = getattr(self, '_active_screen_command', None)
        if command == self._show_reports:
            self._export_report_pdf()
        elif command == self._show_expenses:
            self._print_forms_for_selected_expense()
        elif command == self._show_documents:
            self._print_document()
        else:
            messagebox.showinfo("In / PDF", "Màn hình hiện tại chưa có lệnh in hoặc PDF riêng.")
        return "break"

    def _undo_last_entry(self):
        messagebox.showinfo("Hoàn tác", "Chưa có nghiệp vụ nháp gần nhất để hoàn tác trên màn hình này.")
        return "break"

    def _refresh_current_view(self):
        command = getattr(self, '_active_screen_command', None)
        if command:
            command()
        return "break"

    def _page_title(self, text, subtitle=None):
        frame = tk.Frame(self.content_frame, bg=self.theme['bg'])
        frame.pack(fill='x', padx=18, pady=(16, 8))
        tk.Label(frame, text=text, font=('Arial', 16, 'bold'), bg=self.theme['bg'],
                 fg=self.theme['primary_dark']).pack(anchor='w')
        if subtitle:
            tk.Label(frame, text=subtitle, font=('Arial', 10), bg=self.theme['bg'],
                     fg=self.theme['muted']).pack(anchor='w', pady=(2, 0))
        return frame

    def _build_ui(self):
        """Xây dựng giao diện chính."""
        self._setup_styles()

        # ── HEADER ──────────────────────────────────────────
        self._create_header()

        # ── MENU ────────────────────────────────────────────
        self._create_menu()

        # ── MAIN CONTENT ────────────────────────────────────
        self._create_content_area()

        # ── FOOTER ──────────────────────────────────────────
        self._create_footer()

        # ── QUICK ACTIONS ───────────────────────────────────
        self._create_quick_actions_button()

    def _create_header(self):
        """Topbar cố định theo design system FasTrack ERP."""
        header = tk.Frame(
            self.root,
            bg=self.theme['TOPBAR_BG'],
            height=self.theme['TOPBAR_HEIGHT'],
            highlightbackground=self.theme['TOPBAR_BORDER'],
            highlightthickness=0,
        )
        header.pack(fill='x', side='top')
        header.pack_propagate(False)

        topbar = tk.Frame(header, bg=self.theme['TOPBAR_BG'])
        topbar.pack(fill='both', expand=True)

        left = tk.Frame(topbar, bg=self.theme['TOPBAR_BG'])
        left.pack(side='left', fill='y', padx=18)
        self.topbar_title = tk.Label(
            left, text='Tổng quan vận hành', anchor='w',
            bg=self.theme['TOPBAR_BG'], fg=self.theme['TEXT_PRIMARY'],
            font=('Segoe UI', 13, 'bold')
        )
        self.topbar_title.pack(anchor='w', pady=(7, 0))
        self.topbar_subtitle = tk.Label(
            left, text='Theo dõi chi phí, chứng từ, dự án và hồ sơ cần xử lý',
            anchor='w', bg=self.theme['TOPBAR_BG'], fg=self.theme['TEXT_MUTED'],
            font=('Segoe UI', 10)
        )
        self.topbar_subtitle.pack(anchor='w')

        right = tk.Frame(topbar, bg=self.theme['TOPBAR_BG'])
        right.pack(side='right', fill='y', padx=12)

        bell_wrap = tk.Frame(right, bg=self.theme['TOPBAR_BG'], width=36, height=34)
        bell_wrap.pack(side='left', padx=(0, 8), pady=9)
        bell_wrap.pack_propagate(False)
        bell = tk.Label(
            bell_wrap, text='!', bg='#F8FAFC', fg=self.theme['ACCENT_BLUE'],
            font=('Segoe UI', 12, 'bold'), bd=0, relief='flat',
            highlightbackground=self.theme['PANEL_BORDER'], highlightthickness=1,
            cursor='hand2'
        )
        bell.pack(fill='both', expand=True)
        bell._tooltip_text = 'Thông báo và việc cần xử lý'
        self.notification_button = bell
        for target in (bell_wrap, bell):
            target.bind('<Button-1>', lambda _e: self._show_notifications())
            target.bind('<Enter>', lambda _e, w=bell: w.configure(bg='#EBF3FF'))
            target.bind('<Leave>', lambda _e, w=bell: w.configure(bg='#F8FAFC'))
        self.alert_badge = tk.Canvas(bell_wrap, width=8, height=8, bg=self.theme['TOPBAR_BG'],
                                     highlightthickness=0, bd=0)
        self.alert_badge.place(x=25, y=4)
        self.alert_badge.create_oval(1, 1, 7, 7, fill=self.theme['ACCENT_RED'], outline='')
        self.alert_badge.bind('<Button-1>', lambda _e: self._show_notifications())
        self._refresh_notification_badge()

        logout_btn = create_modern_button(
            right, "Đăng xuất", self._logout, variant='secondary', padx=12, pady=5,
            font=('Segoe UI', 9, 'bold')
        )
        logout_btn.pack(side='left', pady=9)

        tk.Frame(self.root, bg=self.theme['TOPBAR_BORDER'], height=1).pack(fill='x', side='top')

    def _build_topbar(self):
        """Compatibility wrapper for the redesigned topbar."""
        return self._create_header()

    def _refresh_notification_badge(self):
        try:
            count = self.notification_center.get_badge_counts().get('total', 0)
        except Exception:
            count = 0
        if not hasattr(self, 'alert_badge'):
            return
        self.alert_badge.delete('all')
        if count:
            self.alert_badge.configure(width=18, height=16)
            self.alert_badge.place(x=18, y=1)
            self.alert_badge.create_oval(1, 1, 16, 15, fill=self.theme['ACCENT_RED'], outline='')
            self.alert_badge.create_text(8, 8, text=str(min(count, 9)), fill='white', font=('Segoe UI', 7, 'bold'))
        else:
            self.alert_badge.configure(width=8, height=8)
            self.alert_badge.place(x=25, y=4)

    def _logout(self):
        if messagebox.askyesno("Đăng xuất", "Bạn muốn đăng xuất khỏi FasTrack ERP?"):
            self._on_close()

    def _on_close(self):
        self._close_database_connections()
        self.root.destroy()

    def _close_database_connections(self):
        seen = set()
        manager_names = [
            'expense_mgr', 'document_mgr', 'material_mgr', 'report_gen',
            'compliance_mgr', 'account_catalog_mgr', 'knowledge_mgr',
            'utility_mgr', 'construction_mgr', 'project_acct_mgr',
            'template_renderer', 'bank_recon_mgr', 'vat_report_mgr',
            'evm_mgr', 'cash_flow_alert_mgr', 'auth_mgr',
            'project_access_mgr', 'variance_mgr', 'fiscal_lock_mgr',
            'material_control_mgr', 'payroll_mgr', 'powerbi_exporter',
            'einvoice_mgr', 'qr_mgr', 'audit_mgr', 'approval_threshold_mgr',
            'journal_control_mgr', 'extension_report_mgr', 'notification_center',
        ]
        for name in manager_names:
            manager = getattr(self, name, None)
            conn = getattr(manager, 'conn', None)
            if conn is None or id(conn) in seen:
                continue
            seen.add(id(conn))
            try:
                conn.commit()
                conn.execute('PRAGMA wal_checkpoint(FULL)')
                conn.close()
            except Exception:
                pass

    def _create_menu(self):
        """Tạo sidebar chính theo design system."""
        self.body_frame = tk.Frame(self.root, bg=self.theme['bg'])
        self.body_frame.pack(fill='both', expand=True)
        menu_frame = tk.Frame(self.body_frame, bg=self.theme['SIDEBAR_BG'], width=252)
        menu_frame.pack(fill='y', side='left')
        menu_frame.pack_propagate(False)

        logo_area = tk.Frame(menu_frame, bg=self.theme['SIDEBAR_BG'])
        logo_area.pack(fill='x', padx=14, pady=(14, 8))
        tk.Label(logo_area, text="FasTrack ERP", font=('Segoe UI', 14, 'bold'),
                 bg=self.theme['SIDEBAR_BG'], fg='white').pack(anchor='w')
        tk.Label(logo_area, text="PHẦN MỀM KẾ TOÁN XÂY DỰNG", font=('Segoe UI', 8, 'bold'),
                 bg=self.theme['SIDEBAR_BG'], fg=self.theme['SIDEBAR_SECTION']).pack(anchor='w', pady=(2, 0))

        settings = self.utility_mgr.get_app_settings()
        company_name = (settings.get('company_name') or '').strip()
        tax_code = (settings.get('company_tax_code') or '').strip()
        if company_name or tax_code:
            company_display = _wrap_words(company_name, max_chars=27, max_lines=3) if company_name else ''
            company_chip = tk.Frame(
                menu_frame, bg=self.theme['SIDEBAR_HOVER_BG'],
                highlightbackground=self.theme['SIDEBAR_BORDER'], highlightthickness=1
            )
            company_chip.pack(fill='x', padx=10, pady=(2, 12))
            if company_display:
                company_label = tk.Label(
                    company_chip, text=company_display, bg=self.theme['SIDEBAR_HOVER_BG'],
                    fg='white', font=('Segoe UI', 8, 'bold'), anchor='w',
                    justify='left'
                )
                company_label.pack(fill='x', padx=10, pady=(8, 3))
            if tax_code:
                tk.Label(company_chip, text=f"MST {tax_code}", bg=self.theme['SIDEBAR_HOVER_BG'],
                         fg=self.theme['SIDEBAR_SECTION'], font=('Segoe UI', 9), anchor='w').pack(fill='x', padx=10, pady=(0, 8))

        menu_scroll_wrap = tk.Frame(menu_frame, bg=self.theme['SIDEBAR_BG'])
        menu_scroll_wrap.pack(fill='both', expand=True)

        self.menu_canvas = tk.Canvas(menu_scroll_wrap, bg=self.theme['SIDEBAR_BG'],
                                     highlightthickness=0, bd=0, width=238)
        menu_v_scroll = ttk.Scrollbar(menu_scroll_wrap, orient='vertical', command=self.menu_canvas.yview)
        self.menu_canvas.configure(yscrollcommand=menu_v_scroll.set)

        self.menu_inner = tk.Frame(self.menu_canvas, bg=self.theme['SIDEBAR_BG'])
        self.menu_window_id = self.menu_canvas.create_window((0, 0), window=self.menu_inner, anchor='nw')
        self.menu_inner.bind('<Configure>', self._update_menu_scrollregion)
        self.menu_canvas.bind('<Configure>', self._resize_menu_window)

        self.menu_canvas.grid(row=0, column=0, sticky='nsew')
        menu_v_scroll.grid(row=0, column=1, sticky='ns')
        menu_scroll_wrap.rowconfigure(0, weight=1)
        menu_scroll_wrap.columnconfigure(0, weight=1)

        def _menu_wheel(event):
            if self.menu_canvas.winfo_containing(event.x_root, event.y_root):
                self.menu_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
        self.menu_canvas.bind('<Enter>', lambda _e: self.menu_canvas.bind_all('<MouseWheel>', _menu_wheel))
        self.menu_canvas.bind('<Leave>', lambda _e: self.menu_canvas.unbind_all('<MouseWheel>'))

        self.menu_buttons = []
        self.active_menu_button = None

        # Tạo menu groups với hoặc không có AI Chat tùy theo khả dụng
        overview_items = [
            ('D', 'Dashboard', self._show_dashboard, 'Tổng quan vận hành'),
            ('B', 'Báo cáo', self._show_reports, 'Báo cáo quản trị'),
        ]

        # Thêm AI Chat nếu khả dụng
        if AI_CHAT_AVAILABLE:
            overview_items.append(('AI', 'Trợ lý AI', self._show_ai_chat, 'Hỏi đáp dữ liệu'))

        system_items = [
            ('KS', 'Kiểm soát', self._show_extension_controls, 'Hạn mức, audit, TSCĐ và công nợ'),
            ('DM', 'Danh mục', self._show_catalogs, 'Dữ liệu dùng chung'),
            ('PQ', 'Phân quyền', self._show_project_rbac, 'Phân quyền dự án'),
            ('KỲ', 'Khóa kỳ', self._show_fiscal_locks, 'Khóa sổ kế toán theo kỳ'),
            ('NH', 'Ngân hàng', self._show_bank_reconciliation, 'Đối chiếu sao kê ngân hàng'),
            ('SL', 'Sao lưu', self._show_backup_settings, 'Sao lưu và phục hồi'),
            ('CĐ', 'Cài đặt', self._show_settings, 'Thiết lập hệ thống'),
        ]
        if (self.current_user.get('role') or '').lower() == 'admin':
            system_items.insert(1, ('AU', 'Audit log', self._show_audit_log, 'Nhật ký đọc, xuất và ghi sổ'))

        menu_groups = [
            ('TỔNG QUAN', overview_items),
            ('KẾ TOÁN', [
                ('C', 'Chi phí', self._show_expenses, 'Quản lý chi phí'),
                ('HĐ', 'Hóa đơn / Chứng từ', self._show_documents, 'Hóa đơn và chứng từ'),
                ('TƯ', 'Tạm ứng', self._show_advances, 'Tạm ứng và hoàn ứng'),
                ('BT', 'Bút toán', self._show_journals, 'Sổ nhật ký và bút toán'),
            ]),
            ('CÔNG TRÌNH', [
                ('CT', 'Công trường', self._show_construction, 'Nhật ký công trường'),
                ('DA', 'Kế toán dự án', self._show_project_accounting, 'Chi phí và doanh thu dự án'),
                ('HĐ', 'Hợp đồng', self._show_contracts, 'Hợp đồng và thanh toán'),
                ('K', 'Vật tư / Kho', self._show_materials, 'Vật tư và tồn kho'),
            ]),
            ('HỆ THỐNG', system_items),
        ]

        for group_name, buttons in menu_groups:
            section = tk.Frame(self.menu_inner, bg=self.theme['SIDEBAR_BG'])
            section.pack(fill='x', padx=14, pady=(14, 6))
            tk.Frame(section, bg=self.theme['SIDEBAR_BORDER'], height=1).pack(side='left', fill='x', expand=True)
            tk.Label(section, text=group_name, anchor='center',
                     font=('Segoe UI', 8, 'bold'), bg=self.theme['SIDEBAR_BG'],
                     fg=self.theme['SIDEBAR_SECTION'], padx=8).pack(side='left')
            tk.Frame(section, bg=self.theme['SIDEBAR_BORDER'], height=1).pack(side='left', fill='x', expand=True)
            for icon, text, cmd, subtitle in buttons:
                btn = tk.Frame(self.menu_inner, bg=self.theme['SIDEBAR_BG'], cursor='hand2')
                btn.pack(fill='x', padx=12, pady=3)
                btn._accent = tk.Frame(btn, bg=self.theme['SIDEBAR_BG'], width=3)
                btn._accent.pack(side='left', fill='y')
                btn._icon_label = tk.Label(
                    btn, text=icon, width=4, anchor='center', bg=self.theme['SIDEBAR_BG'],
                    fg=self.theme['SIDEBAR_ITEM'], font=('Segoe UI', 9, 'bold'), cursor='hand2'
                )
                btn._icon_label.pack(side='left', fill='y', padx=(5, 2), pady=8)
                btn._text_label = tk.Label(
                    btn, text=text, anchor='w', bg=self.theme['SIDEBAR_BG'],
                    fg=self.theme['SIDEBAR_ITEM'], font=('Segoe UI', 10), cursor='hand2'
                )
                btn._text_label.pack(side='left', fill='x', expand=True, pady=8)
                btn._nav_command = cmd
                btn._nav_title = text
                btn._nav_subtitle = subtitle
                for target in (btn, btn._icon_label, btn._text_label):
                    target.bind('<Button-1>', lambda e, b=btn: self._activate_nav(b))
                    target.bind('<Enter>', lambda e, b=btn: self._nav_hover(b, True))
                    target.bind('<Leave>', lambda e, b=btn: self._nav_hover(b, False))
                self.menu_buttons.append(btn)

        user_area = tk.Frame(menu_frame, bg=self.theme['SIDEBAR_BG'],
                             highlightbackground=self.theme['SIDEBAR_BORDER'], highlightthickness=1)
        user_area.pack(fill='x', side='bottom', padx=0, pady=0)
        user_inner = tk.Frame(user_area, bg=self.theme['SIDEBAR_BG'])
        user_inner.pack(fill='x', padx=12, pady=10)
        user_name = (self.current_user.get('full_name') or self.current_user.get('username') or '').strip()
        user_role = (self.current_user.get('role') or 'Kế toán').strip()
        display_name = user_name or user_role
        initials = ''.join(part[:1] for part in display_name.split()[-2:]).upper() or 'KT'
        avatar = tk.Label(user_inner, text=initials, bg=self.theme['ACCENT_BLUE'], fg='white',
                          font=('Segoe UI', 9, 'bold'), width=4, height=2)
        avatar.pack(side='left')
        text_box = tk.Frame(user_inner, bg=self.theme['SIDEBAR_BG'])
        text_box.pack(side='left', fill='x', expand=True, padx=(8, 0))
        tk.Label(text_box, text=display_name, bg=self.theme['SIDEBAR_BG'], fg='white',
                 font=('Segoe UI', 9, 'bold'), anchor='w').pack(fill='x')
        if user_name and user_role:
            tk.Label(text_box, text=user_role, bg=self.theme['SIDEBAR_BG'],
                     fg=self.theme['SIDEBAR_SECTION'], font=('Segoe UI', 8), anchor='w').pack(fill='x')

        if self.menu_buttons:
            self.active_menu_button = self.menu_buttons[0]
            self._set_nav_state(self.menu_buttons[0], active=True)
            if hasattr(self, 'topbar_title'):
                self.topbar_title.configure(text=getattr(self.menu_buttons[0], '_nav_title', 'FasTrack ERP'))
            if hasattr(self, 'topbar_subtitle'):
                self.topbar_subtitle.configure(text=getattr(self.menu_buttons[0], '_nav_subtitle', ''))

    def _activate_nav(self, button):
        if self.active_menu_button and self.active_menu_button.winfo_exists():
            self._set_nav_state(self.active_menu_button, active=False)
        self.active_menu_button = button
        self._set_nav_state(button, active=True)
        if hasattr(self, 'topbar_title'):
            self.topbar_title.configure(text=getattr(button, '_nav_title', 'FasTrack ERP'))
        if hasattr(self, 'topbar_subtitle'):
            self.topbar_subtitle.configure(text=getattr(button, '_nav_subtitle', ''))
        self._run_nav_command(button)

    def _run_nav_command(self, button):
        command = getattr(button, '_nav_command', None)
        if not command:
            return
        screen_name = getattr(button, '_nav_title', command.__name__)
        self._active_screen_command = command
        self._active_screen_name = screen_name
        if screen_name in self._tab_loaded:
            command()
            return

        self._clear_content()
        loading = tk.Frame(self.content_frame, bg=self.theme['bg'])
        loading.pack(fill='both', expand=True, padx=18, pady=18)
        tk.Label(
            loading, text=f"Đang tải {screen_name}...",
            font=('Segoe UI', 12, 'bold'), bg=self.theme['bg'], fg=self.theme['text']
        ).pack(anchor='center', pady=(80, 12))
        progress = ttk.Progressbar(loading, mode='indeterminate', length=260)
        progress.pack(anchor='center')
        progress.start(12)

        def _build():
            progress.stop()
            command()
            self._tab_loaded[screen_name] = True

        self.root.after(30, _build)

    def _nav_hover(self, button, entering):
        if button is self.active_menu_button:
            return
        self._set_nav_state(button, hover=entering)

    def _set_nav_state(self, button, active=False, hover=False):
        bg = self.theme['SIDEBAR_ACTIVE_BG'] if active else self.theme['SIDEBAR_HOVER_BG'] if hover else self.theme['SIDEBAR_BG']
        fg = 'white' if active or hover else self.theme['SIDEBAR_ITEM']
        accent = self.theme['ACCENT_BLUE'] if active else bg
        button.configure(bg=bg)
        for attr in ('_accent', '_icon_label', '_text_label'):
            child = getattr(button, attr, None)
            if child:
                child.configure(bg=accent if attr == '_accent' else bg)
                if attr != '_accent':
                    child.configure(fg=fg)

    def _build_sidebar(self):
        """Compatibility wrapper for the redesigned sidebar."""
        return self._create_menu()

    def _update_menu_scrollregion(self, _event=None):
        if hasattr(self, 'menu_canvas'):
            self.menu_canvas.configure(scrollregion=self.menu_canvas.bbox('all'))

    def _resize_menu_window(self, event):
        if hasattr(self, 'menu_window_id'):
            self.menu_canvas.itemconfigure(self.menu_window_id, width=event.width)

    def _create_content_area(self):
        """Tạo vùng nội dung chính."""
        parent = getattr(self, 'body_frame', self.root)
        shell = tk.Frame(parent, bg=self.theme['bg'])
        shell.pack(fill='both', expand=True, padx=0, pady=0)

        self.content_canvas = tk.Canvas(shell, bg=self.theme['bg'], highlightthickness=0)
        self.content_v_scroll = ttk.Scrollbar(shell, orient='vertical', command=self.content_canvas.yview)
        self.content_h_scroll = ttk.Scrollbar(shell, orient='horizontal', command=self.content_canvas.xview)
        self.content_canvas.configure(
            yscrollcommand=self.content_v_scroll.set,
            xscrollcommand=self.content_h_scroll.set
        )
        self.content_canvas.grid(row=0, column=0, sticky='nsew')
        self.content_v_scroll.grid(row=0, column=1, sticky='ns')
        self.content_h_scroll.grid(row=1, column=0, sticky='ew')
        shell.rowconfigure(0, weight=1)
        shell.columnconfigure(0, weight=1)

        self.content_frame = tk.Frame(self.content_canvas, bg=self.theme['bg'])
        self.content_window = self.content_canvas.create_window((0, 0), window=self.content_frame, anchor='nw')
        self.content_frame.bind('<Configure>', self._update_content_scrollregion)
        self.content_canvas.bind('<Configure>', self._resize_content_window)
        self.content_canvas.bind('<Enter>', lambda _e: self.content_canvas.bind_all('<MouseWheel>', self._on_content_mousewheel))
        self.content_canvas.bind('<Leave>', lambda _e: self.content_canvas.unbind_all('<MouseWheel>'))

        # Hiển thị dashboard mặc định
        if getattr(self, 'active_menu_button', None):
            self._run_nav_command(self.active_menu_button)
        else:
            self._show_dashboard()

    def _update_content_scrollregion(self, _event=None):
        if hasattr(self, 'content_canvas'):
            bbox = self.content_canvas.bbox('all') or (0, 0, 0, 0)
            canvas_height = max(self.content_canvas.winfo_height(), 1)
            canvas_width = max(self.content_canvas.winfo_width(), 1)
            content_height = max(bbox[3] - bbox[1], canvas_height)
            content_width = max(bbox[2] - bbox[0], canvas_width)
            self.content_canvas.configure(scrollregion=(0, 0, content_width, content_height))
            if content_height <= canvas_height + 2:
                self.content_canvas.yview_moveto(0)
            # Cập nhật window size ngay lập tức
            self.content_canvas.after(10, self._resize_content_window_auto)

    def _resize_content_window_auto(self):
        """Auto resize window based on content"""
        if hasattr(self, 'content_window') and hasattr(self, 'content_canvas'):
            try:
                canvas_width = self.content_canvas.winfo_width()
                content_width = self.content_frame.winfo_reqwidth()
                width = max(canvas_width, content_width) if canvas_width > 1 else content_width

                if width > 1:
                    self.content_canvas.itemconfigure(self.content_window, width=width)
            except:
                pass

    def _resize_content_window(self, event):
        if hasattr(self, 'content_window'):
            try:
                width = max(event.width, self.content_frame.winfo_reqwidth())
                if width > 1:
                    self.content_canvas.itemconfigure(self.content_window, width=width)
            except:
                pass

    def _on_content_mousewheel(self, event):
        focused = self.root.focus_get()
        if isinstance(focused, ttk.Treeview):
            return
        under_mouse = self.root.winfo_containing(event.x_root, event.y_root)
        if self._is_inside_widget_type(under_mouse, ExpenseDataTable):
            return
        if hasattr(self, 'content_canvas'):
            first, last = self.content_canvas.yview()
            direction = -1 * int(event.delta / 120)
            if direction < 0 and first <= 0.0:
                self.content_canvas.yview_moveto(0)
                return "break"
            if direction > 0 and last >= 1.0:
                return "break"
            self.content_canvas.yview_scroll(direction, 'units')
            return "break"

    def _is_inside_widget_type(self, widget, widget_type):
        while widget is not None:
            if isinstance(widget, widget_type):
                return True
            widget = getattr(widget, 'master', None)
        return False

    def _clear_content(self):
        """Xóa toàn bộ nội dung."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        self.content_canvas.yview_moveto(0)
        self.content_canvas.xview_moveto(0)
        self.content_canvas.configure(scrollregion=(0, 0, 0, 0))
        # Force update scroll region
        self.content_frame.update_idletasks()
        self.content_canvas.after(5, self._update_content_scrollregion)

    def _show_dashboard(self):
        """Hiển thị trang Dashboard."""
        self._clear_content()

        hero = tk.Frame(self.content_frame, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        hero.pack(fill='x', padx=16, pady=(16, 12))

        header = tk.Frame(hero, bg=self.theme['panel'])
        header.pack(fill='x', padx=18, pady=(14, 10))
        hero_left = tk.Frame(header, bg=self.theme['panel'])
        hero_left.pack(side='left', fill='both', expand=True)
        hero_right = tk.Frame(header, bg=self.theme['panel'])
        hero_right.pack(side='right', anchor='e')

        tk.Label(hero_left, text="Tổng quan vận hành", font=('Segoe UI', 18, 'bold'),
                 bg=self.theme['panel'], fg=self.theme['text']).pack(anchor='w')
        tk.Label(hero_left, text="Theo dõi chi phí, chứng từ, dự án và hồ sơ cần xử lý trong ngày.",
                 font=('Segoe UI', 10), bg=self.theme['panel'], fg=self.theme['muted']).pack(anchor='w', pady=(4, 0))

        create_modern_button(hero_right, "Xem cảnh báo", self._show_notifications,
                             variant='warning', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(hero_right, "Báo cáo chi tiết", self._show_reports,
                             variant='outline', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(hero_right, "Chi phí mới", self._show_expenses,
                             variant='primary', padx=12, pady=7).pack(side='left', padx=4)

        stats_frame = tk.Frame(hero, bg=self.theme['panel'])
        stats_frame.pack(fill='x', padx=12, pady=(0, 14))

        stats = self.expense_mgr.get_statistics()
        stat_items = [
            ("Tổng chi phí", f"₫ {stats.get('total_expenses', 0):,.0f}", self.theme['danger']),
            ("Chi phí tháng này", f"₫ {stats.get('monthly_expenses', 0):,.0f}", self.theme['primary']),
            ("Số dự án", f"{stats.get('total_projects', 0)}", self.theme['success']),
            ("Số chứng từ", f"{stats.get('total_documents', 0)}", self.theme['warning']),
        ]

        for title, value, color in stat_items:
            self._create_stat_card(stats_frame, title, value, color)

        self._show_dashboard_risk_summary(hero)

        insight_frame = tk.Frame(hero, bg=self.theme['panel'])
        insight_frame.pack(fill='x', padx=18, pady=(0, 12))
        tk.Label(insight_frame, text="Gợi ý vận hành", font=('Segoe UI', 11, 'bold'),
                 bg=self.theme['panel'], fg=self.theme['text']).pack(anchor='w', pady=(0, 6))
        tk.Label(insight_frame,
                 text="Dữ liệu hiện tại cho biết chi phí tháng này vẫn trong giới hạn ngân sách. Kiểm tra các chứng từ chưa hạch toán và hoàn tất xử lý công nợ trước khi đóng kỳ.",
                 font=('Segoe UI', 10), bg=self.theme['panel'], fg=self.theme['muted'], wraplength=980, justify='left').pack(anchor='w')

        quick_frame = tk.Frame(self.content_frame, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        quick_frame.pack(fill='x', padx=15, pady=(0, 15))
        tk.Label(quick_frame, text="Hành động nhanh", font=('Segoe UI', 12, 'bold'),
                 bg=self.theme['panel'], fg=self.theme['text']).pack(anchor='w', padx=12, pady=(10, 0))
        self._create_dashboard_quick_actions(quick_frame)

        control_frame = tk.Frame(self.content_frame, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        control_frame.pack(fill='x', padx=15, pady=(0, 15))
        tk.Label(control_frame, text="Kiểm soát kế toán & chất lượng dữ liệu", font=('Segoe UI', 12, 'bold'),
                 bg=self.theme['panel'], fg=self.theme['text']).pack(anchor='w', padx=12, pady=(10, 0))
        self._show_accounting_control(control_frame)

        chart_frame = tk.Frame(self.content_frame, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        chart_frame.pack(fill='x', padx=15, pady=(0, 15))
        chart_head = tk.Frame(chart_frame, bg=self.theme['panel'])
        chart_head.pack(fill='x', padx=12, pady=10)
        tk.Label(chart_head, text="Báo cáo nhanh", font=('Segoe UI', 12, 'bold'),
                 bg=self.theme['panel'], fg=self.theme['text']).pack(side='left')
        create_modern_button(chart_head, "Mở báo cáo chi tiết", self._show_reports,
                             variant='outline').pack(side='right')
        tk.Label(chart_frame, text="Biểu đồ chi tiết được tải khi mở mục Báo cáo để giữ Dashboard nhẹ và phản hồi nhanh.",
                 font=('Segoe UI', 10), bg=self.theme['panel'], fg=self.theme['muted']).pack(anchor='w', padx=12, pady=(0, 12))

        alert_frame = tk.Frame(self.content_frame, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        alert_frame.pack(fill='x', padx=15, pady=(0, 15))
        header_frame = tk.Frame(alert_frame, bg=self.theme['panel'])
        header_frame.pack(fill='x', padx=12, pady=(10, 0))
        tk.Label(header_frame, text="Cảnh báo vận hành", font=('Segoe UI', 12, 'bold'),
                 bg=self.theme['panel'], fg=self.theme['text']).pack(side='left')
        create_modern_button(header_frame, "Mở trung tâm cảnh báo", self._show_notifications,
                             variant='outline', padx=12, pady=5).pack(side='right')
        self._show_notification_summary(alert_frame)

        recent_frame = tk.Frame(self.content_frame, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        recent_frame.pack(fill='x', padx=15, pady=(0, 15))
        tk.Label(recent_frame, text="Chi phí gần đây", font=('Segoe UI', 12, 'bold'),
                 bg=self.theme['panel'], fg=self.theme['text']).pack(anchor='w', padx=12, pady=(10, 0))
        self._show_recent_expenses(recent_frame)

        advance_frame = tk.Frame(self.content_frame, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        advance_frame.pack(fill='x', padx=15, pady=(0, 15))
        tk.Label(advance_frame, text="Tạm ứng / công nợ nội bộ", font=('Segoe UI', 12, 'bold'),
                 bg=self.theme['panel'], fg=self.theme['text']).pack(anchor='w', padx=12, pady=(10, 0))
        self._show_advance_summary(advance_frame)

    def _create_stat_card(self, parent, title, value, color):
        """Tạo card thống kê."""
        card = tk.Frame(parent, bg='white', highlightbackground=self.theme['line'], highlightthickness=1)
        card.pack(side='left', fill='both', expand=True, padx=6, pady=5)
        tk.Frame(card, bg=color, height=3).pack(fill='x')

        content = tk.Frame(card, bg='white')
        content.pack(side='left', fill='both', expand=True, padx=12, pady=9)
        tk.Label(content, text=title, font=('Segoe UI', 9), fg=self.theme['muted'],
                 bg='white', justify='left').pack(anchor='w')

        tk.Label(content, text=value, font=('Segoe UI', 16, 'bold'), fg=self.theme['text'],
                 bg='white', wraplength=190, justify='left').pack(anchor='w', pady=(2, 0))

    def _show_dashboard_risk_summary(self, parent):
        counts = self.notification_center.get_badge_counts()
        risk_frame = tk.Frame(parent, bg=self.theme['panel'])
        risk_frame.pack(fill='x', padx=12, pady=(0, 12))

        self._create_alert_card(risk_frame, 'Toàn bộ cảnh báo', counts.get('total', 0), self.theme['accent'], '#EFF6FF')
        self._create_alert_card(risk_frame, 'Nghiêm trọng', counts.get('critical', 0), self.theme['danger'], '#FEF2F2')
        self._create_alert_card(risk_frame, 'Cần theo dõi', counts.get('warning', 0), self.theme['warning'], '#FFFBEB')

    def _create_dashboard_action_card(self, parent, title, subtitle, command):
        card = tk.Frame(parent, bg='white', highlightbackground=self.theme['line'], highlightthickness=1)
        card.pack(side='left', fill='both', expand=True, padx=6, pady=8)
        tk.Label(card, text=title, font=('Segoe UI', 11, 'bold'), bg='white', fg=self.theme['text']).pack(anchor='w', padx=12, pady=(12, 4))
        tk.Label(card, text=subtitle, font=('Segoe UI', 9), bg='white', fg=self.theme['TEXT_MUTED'], wraplength=220, justify='left').pack(anchor='w', padx=12)
        create_modern_button(card, "Mở", command, variant='primary', padx=14).pack(anchor='w', pady=12, padx=12)

    def _show_recent_expenses(self, parent):
        """Hiển thị chi phí gần đây."""
        expenses = self.expense_mgr.get_recent_expenses(limit=10)

        # Tạo Treeview
        columns = ('ID', 'Ngày', 'Dự án', 'Loại', 'Số tiền', 'Trạng thái')
        tree = ttk.Treeview(parent, columns=columns, height=6, show='tree headings')

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)

        for expense in expenses:
            tree.insert('', 'end', values=(
                expense[0], expense[1], expense[2],
                expense[3], f"₫ {expense[4]:,.0f}", expense[5]
            ))

        tree.pack(fill='both', expand=True)

    def _show_notification_summary(self, parent):
        counts = self.notification_center.get_badge_counts()
        cards = tk.Frame(parent, bg=self.theme['panel'])
        cards.pack(fill='x', padx=12, pady=(8, 6))
        for title, value, color in [
            ("Tổng cảnh báo", counts.get('total', 0), self.theme['primary']),
            ("Nghiêm trọng", counts.get('critical', 0), self.theme['danger']),
            ("Cần theo dõi", counts.get('warning', 0), self.theme['warning']),
            ("Thông tin", counts.get('info', 0), self.theme['info']),
        ]:
            self._create_stat_card(cards, title, str(value), color)

        columns = ('Mức', 'Nguồn', 'Tiêu đề', 'Ngày hạn', 'Nội dung')
        tree = ttk.Treeview(parent, columns=columns, height=5, show='headings')
        self.notification_tree = tree
        self.notification_items = {}
        for col, width in zip(columns, (100, 110, 260, 100, 360)):
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor='w')
        labels = {'critical': 'Nghiêm trọng', 'warning': 'Cảnh báo', 'info': 'Thông tin'}
        for idx, alert in enumerate(self.notification_center.get_all_alerts()[:10]):
            iid = f"alert_{idx}"
            self.notification_items[iid] = alert
            tree.insert('', 'end', iid=iid, values=(
                labels.get(alert['priority'], alert['priority']),
                alert['source'], alert['title'], alert.get('due_date') or '', alert['message'],
            ))
        if not self.notification_items:
            tree.insert('', 'end', values=('OK', '', 'Chưa có cảnh báo vận hành', '', ''))
        tree.bind('<Double-1>', lambda _e: self._open_selected_notification())
        tree.pack(fill='x', padx=12, pady=(0, 12))

    def _create_dashboard_quick_actions(self, parent):
        counts = self.notification_center.get_badge_counts()
        quick_frame = tk.Frame(parent, bg=self.theme['panel'])
        quick_frame.pack(fill='x', padx=12, pady=(8, 12))
        action_items = [
            ("Cảnh báo hiện tại", f"{counts.get('total', 0)} mục cần xử lý", self._show_notifications),
            ("Audit log", "Theo dõi hoạt động hệ thống và xuất Excel", self._show_audit_log),
            ("Báo cáo nhanh", "Mở báo cáo chi tiết để xem chi phí và doanh thu", self._show_reports),
            ("Chi phí mới", "Thêm hoặc kiểm tra chứng từ mới nhập", self._show_expenses),
        ]
        for title, subtitle, command in action_items:
            self._create_dashboard_action_card(quick_frame, title, subtitle, command)

    def _open_selected_notification(self):
        tree = getattr(self, 'notification_tree', None)
        if not tree or not tree.selection():
            return
        alert = getattr(self, 'notification_items', {}).get(tree.selection()[0])
        if not alert:
            return
        source = alert.get('source')
        if source == 'ar_ap':
            self._show_extension_controls()
        elif source == 'budget':
            self._show_project_accounting()
        elif source == 'materials':
            self._show_materials()
        elif source == 'advance':
            self._show_advances()
        else:
            self._show_extension_controls()

    def _show_notifications(self):
        win = tk.Toplevel(self.root)
        win.title("Trung tâm cảnh báo")
        win.geometry("860x520")
        win.configure(bg=self.theme['bg'])
        win.transient(self.root)

        tk.Label(win, text="Trung tâm cảnh báo", bg=self.theme['bg'],
                 fg=self.theme['TEXT_PRIMARY'], font=('Segoe UI', 15, 'bold')).pack(anchor='w', padx=18, pady=(16, 2))
        tk.Label(win, text="Các việc cần xử lý từ tạm ứng, công nợ, ngân sách, vật tư và hồ sơ hết hạn.",
                 bg=self.theme['bg'], fg=self.theme['TEXT_MUTED'], font=('Segoe UI', 10)).pack(anchor='w', padx=18, pady=(0, 12))

        body = tk.Frame(win, bg='white', highlightbackground=self.theme['line'], highlightthickness=1)
        body.pack(fill='both', expand=True, padx=18, pady=(0, 12))
        cols = ('Mức', 'Nguồn', 'Tiêu đề', 'Ngày hạn', 'Nội dung')
        tree = ttk.Treeview(body, columns=cols, show='headings', height=14)
        for col, width in zip(cols, (110, 110, 270, 100, 330)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        alerts = self.notification_center.get_all_alerts()
        alert_by_iid = {}
        labels = {'critical': 'Nghiêm trọng', 'warning': 'Cảnh báo', 'info': 'Thông tin'}
        for idx, alert in enumerate(alerts):
            iid = f"notice_{idx}"
            alert_by_iid[iid] = alert
            tree.insert('', 'end', iid=iid, values=(
                labels.get(alert['priority'], alert['priority']),
                alert['source'], alert['title'], alert.get('due_date') or '', alert['message'],
            ))
        if not alerts:
            tree.insert('', 'end', values=('OK', '', 'Không có cảnh báo', '', ''))
        tree.pack(fill='both', expand=True, padx=10, pady=10)

        actions = tk.Frame(win, bg=self.theme['bg'])
        actions.pack(fill='x', padx=18, pady=(0, 14))

        def open_selected():
            if not tree.selection():
                messagebox.showwarning("Cảnh báo", "Chọn một cảnh báo.")
                return
            alert = alert_by_iid.get(tree.selection()[0])
            if not alert:
                return
            win.destroy()
            source = alert.get('source')
            if source == 'ar_ap':
                self._show_extension_controls()
            elif source == 'budget':
                self._show_project_accounting()
            elif source == 'materials':
                self._show_materials()
            elif source == 'advance':
                self._show_advances()
            else:
                self._show_extension_controls()

        create_modern_button(actions, "Mở phân hệ liên quan", open_selected,
                             variant='primary', padx=12, pady=7).pack(side='left')
        create_modern_button(actions, "Đóng", win.destroy,
                             variant='secondary', padx=12, pady=7).pack(side='right')
        tree.bind('<Double-1>', lambda _e: open_selected())

    def _show_accounting_control(self, parent):
        summary = self.utility_mgr.get_accounting_control_summary()
        card_frame = tk.Frame(parent, bg=self.theme['panel'])
        card_frame.pack(fill='x', padx=12, pady=(8, 6))
        score_color = self.theme['success'] if summary['score'] >= 80 else self.theme['warning']
        if summary['score'] < 60:
            score_color = self.theme['danger']
        cards = [
            ("Điểm sạch dữ liệu", f"{summary['score']}/100", score_color),
            ("Lỗi nghiêm trọng", str(summary['critical']), self.theme['danger']),
            ("Cảnh báo", str(summary['warning']), self.theme['warning']),
            ("Giá trị cần rà soát", f"₫ {summary['amount_at_risk']:,.0f}", self.theme['primary']),
        ]
        for title, value, color in cards:
            self._create_stat_card(card_frame, title, value, color)

        badge_frame = tk.Frame(parent, bg=self.theme['panel'])
        badge_frame.pack(fill='x', padx=12, pady=(0, 8))
        for label_text, value, bg_color in [
            ('Nghiêm trọng', summary['critical'], self.theme['danger']),
            ('Cảnh báo', summary['warning'], self.theme['warning']),
            ('Theo dõi', summary['info'], self.theme['info']),
        ]:
            badge = tk.Label(badge_frame, text=f"{label_text}: {value}",
                             bg=bg_color, fg='white', font=('Segoe UI', 9, 'bold'),
                             padx=10, pady=4)
            badge.pack(side='left', padx=(0, 8))

        columns = ('Mức', 'Vấn đề', 'Ngày', 'Dự án', 'Nội dung', 'Số tiền', 'Khuyến nghị')
        action_bar = tk.Frame(parent, bg=self.theme['panel'])
        action_bar.pack(fill='x', padx=12, pady=(0, 6))
        create_modern_button(action_bar, "Mở dòng cần xử lý", self._open_selected_control_finding,
                             variant='outline', padx=12, pady=7).pack(side='left')

        table_frame = tk.Frame(parent, bg='white', highlightbackground=self.theme['line'], highlightthickness=1)
        table_frame.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        widths = (78, 190, 82, 140, 230, 95, 245)
        for col_index, (col, width) in enumerate(zip(columns, widths)):
            header = tk.Label(table_frame, text=col, bg=self.theme['panel'], fg=self.theme['TEXT_PRIMARY'],
                              font=('Segoe UI', 9, 'bold'), borderwidth=1, relief='solid', padx=6, pady=6)
            header.grid(row=0, column=col_index, sticky='nsew', padx=(0 if col_index == 0 else 1, 0), pady=(0, 1))
            table_frame.columnconfigure(col_index, weight=1)

        # Scrollable content area to prevent text overflow
        content_wrap = tk.Frame(table_frame, bg='white')
        content_wrap.grid(row=1, column=0, columnspan=len(columns), sticky='nsew')
        table_frame.rowconfigure(1, weight=1)

        canvas = tk.Canvas(content_wrap, bg='white', highlightthickness=0)
        v_scroll = ttk.Scrollbar(content_wrap, orient='vertical', command=canvas.yview)
        x_scroll = ttk.Scrollbar(content_wrap, orient='horizontal', command=canvas.xview)
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=x_scroll.set)
        canvas.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        x_scroll.grid(row=1, column=0, sticky='ew')
        content_wrap.rowconfigure(0, weight=1)
        content_wrap.columnconfigure(0, weight=1)

        inner = tk.Frame(canvas, bg='white')
        canvas_window = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _on_inner_config(evt):
            canvas.configure(scrollregion=canvas.bbox('all'))

        inner.bind('<Configure>', _on_inner_config)
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(canvas_window, width=max(e.width, inner.winfo_reqwidth())))

        self.accounting_control_items = {}
        self.accounting_control_row_widgets = {}
        self._selected_accounting_control_iid = None

        def select_control_row(iid):
            prev_iid = getattr(self, '_selected_accounting_control_iid', None)
            if prev_iid and prev_iid in self.accounting_control_row_widgets:
                for widget in self.accounting_control_row_widgets[prev_iid]:
                    # restore original colors
                    try:
                        widget.configure(bg=getattr(widget, '_orig_bg', 'white'), fg=getattr(widget, '_orig_fg', self.theme['TEXT_PRIMARY']))
                    except Exception:
                        pass
            self._selected_accounting_control_iid = iid
            if iid and iid in self.accounting_control_row_widgets:
                for widget in self.accounting_control_row_widgets[iid]:
                    # apply highlight (use primary color and white text for contrast)
                    try:
                        widget.configure(bg=self.theme.get('primary', '#1a73e8'), fg='#ffffff')
                    except Exception:
                        pass

        severity_labels = {
            'critical': 'Nghiêm trọng',
            'warning': 'Cảnh báo',
            'info': 'Theo dõi',
        }

        # Fixed height limit for the scrollable area
        canvas.configure(height=200)

        if not summary['findings']:
            no_data = tk.Label(inner, text='Dữ liệu hiện tương đối sạch. Có thể tiếp tục kiểm tra trước khi khóa sổ.',
                               bg='white', fg=self.theme['TEXT_MUTED'], anchor='w', justify='left', wraplength=900,
                               padx=8, pady=8, borderwidth=1, relief='solid')
            no_data.grid(row=0, column=0, columnspan=len(columns), sticky='nsew', padx=0, pady=(0, 1))
            inner.rowconfigure(0, weight=1)
        else:
            for row_index, item in enumerate(summary['findings'], start=0):
                iid = f"finding_{row_index}"
                self.accounting_control_items[iid] = item
                cells = [
                    severity_labels.get(item['severity'], item['severity']),
                    item['type'],
                    item['record_date'],
                    item['project_name'],
                    item['description'],
                    f"{item['amount']:,.0f}",
                    item['recommendation'],
                ]
                row_widgets = []
                row_bg = self.theme['row_alt'] if row_index % 2 else 'white'
                for col_index, value in enumerate(cells):
                    wraplen = 220 if col_index == 4 else 300 if col_index == 6 else 180
                    display_text = value
                    fg_color = self.theme['TEXT_PRIMARY']
                    if col_index == 0:
                        sev = str(value)
                        color_map = {'Nghiêm trọng': self.theme.get('danger', '#d9534f'),
                                     'Cảnh báo': self.theme.get('warning', '#f0ad4e'),
                                     'Theo dõi': self.theme.get('info', '#5bc0de')}
                        sev_color = color_map.get(sev, self.theme.get('muted', '#777'))
                        display_text = f"● {sev}"
                        fg_color = sev_color
                    label = tk.Label(inner, text=display_text, bg=row_bg, fg=fg_color,
                                     anchor='nw', justify='left', wraplength=wraplen,
                                     padx=8, pady=10, bd=0)
                    label._orig_bg = row_bg
                    label._orig_fg = fg_color
                    label.grid(row=row_index, column=col_index, sticky='nsew', padx=(0 if col_index == 0 else 1, 0), pady=(0, 1))
                    label.bind('<Button-1>', lambda _e, row_iid=iid: select_control_row(row_iid))
                    row_widgets.append(label)
                self.accounting_control_row_widgets[iid] = row_widgets
                inner.rowconfigure(row_index, weight=1)

    def _open_selected_control_finding(self):
        iid = getattr(self, '_selected_accounting_control_iid', None)
        if not iid:
            messagebox.showwarning("Kiểm soát kế toán", "Chọn một dòng cảnh báo cần xử lý.")
            return
        item = getattr(self, 'accounting_control_items', {}).get(iid)
        if not item:
            return
        finding_type = item.get('type', '')
        record_id = item.get('record_id')
        if finding_type in ('Thiếu chứng từ/file đính kèm', 'Đã duyệt nhưng chưa hạch toán', 'Số tiền không hợp lệ') and record_id:
            self._open_expense_detail(int(record_id))
            return
        if finding_type == 'Bút toán thiếu tài khoản hoặc số tiền' and record_id:
            messagebox.showinfo("Bút toán", f"Mở màn Bút toán và tìm ID #{record_id}.")
            self._show_journals()
            return
        messagebox.showinfo("Kiểm soát kế toán", "Dòng này là cảnh báo tổng hợp. Vui lòng mở phân hệ liên quan để xử lý.")

    def _show_advance_summary(self, parent):
        from modules.advance_workflow import AdvanceWorkflowManager
        alerts = AdvanceWorkflowManager().get_deadline_alerts()
        alert_frame = tk.Frame(parent, bg=self.theme['panel'])
        alert_frame.pack(fill='x', padx=12, pady=(8, 6))
        self._create_alert_card(alert_frame, "Sắp trễ hạn hoàn ứng", len(alerts['warning']), self.theme['warning'], "#FFFBEB")
        self._create_alert_card(alert_frame, "Đã quá hạn hoàn ứng", len(alerts['overdue']), self.theme['danger'], "#FEF2F2")

        rows = self.utility_mgr.get_advance_dashboard()
        columns = ('Người tạm ứng', 'Tổng tạm ứng', 'Đã xử lý', 'Còn treo', 'Ngày cũ nhất', 'Số khoản')
        tree = ttk.Treeview(parent, columns=columns, height=4, show='tree headings')
        for col, width in zip(columns, (180, 140, 140, 140, 120, 90)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        for row in rows:
            tree.insert('', 'end', values=(
                row[0], f"{row[1] or 0:,.0f}", f"{row[2] or 0:,.0f}",
                f"{row[3] or 0:,.0f}", row[4] or '', row[5]
            ))
        tree.pack(fill='both', expand=True)

    def _show_expenses(self):
        """Hiển thị trang Quản lý chi phí — bảng MISA với thao tác từng dòng."""
        self._clear_content()
        self._page_title("Quản lý chi phí", "Thao tác Sửa · Ghi sổ · Bỏ ghi · Xem CT nằm bên phải mỗi dòng.")

        toolbar = tk.Frame(self.content_frame, bg=self.theme['bg'])
        toolbar.pack(fill='x', padx=16, pady=(0, 8))
        primary_actions = tk.Frame(toolbar, bg=self.theme['bg'])
        primary_actions.pack(side='left')
        create_modern_button(primary_actions, "+ Thêm mới", self._add_expense, variant='primary').pack(side='left', padx=(0, 10))
        create_modern_button(primary_actions, "Nhập hàng loạt", self._bulk_add_expenses, variant='secondary').pack(side='left', padx=(0, 10))

        secondary_actions = tk.Frame(toolbar, bg=self.theme['bg'])
        secondary_actions.pack(side='left', padx=(18, 0))
        create_modern_button(secondary_actions, "Nhập Excel", self._import_expenses, variant='outline').pack(side='left', padx=(0, 10))
        create_modern_button(secondary_actions, "Tải mẫu nhập", self._export_expense_import_template, variant='outline').pack(side='left', padx=(0, 10))
        create_modern_button(secondary_actions, "Xuất Excel", self._export_expenses, variant='outline').pack(side='left', padx=(0, 10))
        create_modern_button(secondary_actions, "In PDF", self._print_forms_for_selected_expense, variant='outline').pack(side='left', padx=(0, 10))

        card = tk.Frame(self.content_frame, bg=self.theme['panel'],
                        highlightbackground=self.theme['line'], highlightthickness=1)
        card.pack(fill='x', expand=False, padx=16, pady=(0, 12))

        expenses = self.expense_mgr.get_all_expenses()
        table = ExpenseDataTable(card, expenses, self._expense_row_callbacks())
        table.pack(fill='both', expand=True, padx=1, pady=1)
        self.expenses_tree = None
        self.root.after_idle(lambda: self.content_canvas.yview_moveto(0))

    def _expense_row_callbacks(self):
        def _track(fn):
            def wrapped(expense_id):
                self._last_expense_id = expense_id
                return fn(expense_id)
            return wrapped
        return {
            'open': _track(self._open_expense_detail),
            'edit': _track(self._edit_expense_by_id),
            'post': _track(self._post_expense_by_id),
            'unpost': _track(self._unpost_expense_by_id),
            'view_docs': _track(self._view_expense_docs_by_id),
            'add_doc': _track(self._add_document_for_expense_id),
            'delete': _track(self._delete_expense_by_id),
        }

    def _show_expenses_table(self, parent):
        """Giữ tương thích — dùng ExpenseDataTable."""
        expenses = self.expense_mgr.get_all_expenses()
        ExpenseDataTable(parent, expenses, self._expense_row_callbacks()).pack(fill='both', expand=True)

    def _open_expense_detail(self, expense_id):
        """Mở màn hình chi tiết chi phí khi nhấp đúp vào dòng."""
        expense = self.utility_mgr.get_expense_detail(expense_id)
        if not expense:
            messagebox.showwarning("Không tìm thấy", f"Không tìm thấy chi phí #{expense_id}.")
            return

        win = tk.Toplevel(self.root)
        win.title(f"Chi tiết chi phí #{expense_id}")
        win.geometry("760x520")
        win.configure(bg=self.theme['bg'])
        win.transient(self.root)
        win.grab_set()

        header = tk.Frame(win, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        header.pack(fill='x', padx=14, pady=(14, 8))
        tk.Label(header, text=f"Chi phí #{expense_id}", font=('Segoe UI', 15, 'bold'),
                 bg=self.theme['panel'], fg=self.theme['primary_dark']).pack(anchor='w', padx=14, pady=(10, 2))
        tk.Label(header, text=expense['description'] or '', font=('Segoe UI', 10),
                 bg=self.theme['panel'], fg=self.theme['muted'], wraplength=700, justify='left'
                 ).pack(anchor='w', padx=14, pady=(0, 10))

        body = tk.Frame(win, bg=self.theme['bg'])
        body.pack(fill='both', expand=True, padx=14, pady=6)
        fields = [
            ("Ngày", expense['expense_date']),
            ("Dự án", expense['project_name']),
            ("Loại chi phí", expense['category_name']),
            ("Số tiền", f"{expense['amount'] or 0:,.0f} đồng"),
            ("Người thanh toán", expense['paid_by']),
            ("Phương thức", expense['payment_method']),
            ("Trạng thái", format_status(expense['status'])),
            ("Ghi chú", expense['notes']),
        ]
        for idx, (label, value) in enumerate(fields):
            tk.Label(body, text=f"{label}:", width=18, anchor='w', font=('Segoe UI', 10, 'bold'),
                     bg=self.theme['bg'], fg=self.theme['text']).grid(row=idx, column=0, sticky='nw', pady=6)
            tk.Label(body, text=str(value or ''), anchor='w', font=('Segoe UI', 10),
                     bg=self.theme['bg'], fg=self.theme['text'], wraplength=520, justify='left'
                     ).grid(row=idx, column=1, sticky='ew', pady=6)
        body.columnconfigure(1, weight=1)

        actions = tk.Frame(win, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        actions.pack(fill='x', padx=14, pady=(8, 14))

        def run_and_close(action):
            win.destroy()
            action(expense_id)

        create_modern_button(actions, "Sửa", lambda: run_and_close(self._edit_expense_by_id), variant='primary').pack(side='left', padx=8, pady=10)
        create_modern_button(actions, "Xóa", lambda: run_and_close(self._delete_expense_by_id), variant='danger').pack(side='left', padx=4, pady=10)
        create_modern_button(actions, "Xem chứng từ", lambda: run_and_close(self._view_expense_docs_by_id), variant='outline').pack(side='left', padx=4, pady=10)
        create_modern_button(actions, "Ghi sổ", lambda: run_and_close(self._post_expense_by_id), variant='success').pack(side='left', padx=4, pady=10)
        create_modern_button(actions, "Bỏ ghi", lambda: run_and_close(self._unpost_expense_by_id), variant='outline').pack(side='left', padx=4, pady=10)
        create_modern_button(actions, "Đóng", win.destroy, variant='ghost').pack(side='right', padx=8, pady=10)

    def _add_expense(self):
        """Thêm chi phí mới."""
        dialog = ExpenseDialog(self.root, title="Thêm chi phí mới")
        self.root.wait_window(dialog)

        if dialog.result:
            try:
                # Chuyển đổi định dạng ngày
                from utils import format_date
                date_str = format_date(dialog.result['date'], '%Y-%m-%d')
                duplicate = self.expense_mgr.find_duplicate_expense(
                    date_str,
                    dialog.result['project_id'],
                    dialog.result['category_id'],
                    dialog.result['description'],
                    dialog.result['amount'],
                )
                if duplicate and not messagebox.askyesno(
                    "Chi phí nghi trùng",
                    f"Dữ liệu giống chi phí #{duplicate['id']} đã tồn tại.\n\nVẫn lưu thêm dòng này?"
                ):
                    return

                expense_id = self.expense_mgr.add_expense(
                    date_str,
                    dialog.result['project_id'],
                    dialog.result['category_id'],
                    dialog.result['description'],
                    dialog.result['amount'],
                    dialog.result['paid_by'],
                    dialog.result['method'],
                    dialog.result['notes'],
                    1,  # user_id (tạm thời)
                    dialog.result.get('extra_fields', {}),
                    work_item_id=dialog.result.get('work_item_id'),
                    contract_id=dialog.result.get('contract_id'),
                )

                rule = self.compliance_mgr.get_rule_by_category_id(dialog.result['category_id'])
                if rule:
                    messagebox.showwarning(
                        "Hồ sơ cần có cho chi phí này",
                        f"{rule['rule_name']}\n\n{rule['required_documents']}\n\nCảnh báo: {rule['warning_message']}"
                    )

                messagebox.showinfo("Thành công", "Thêm chi phí thành công!")
                self._show_expenses()  # Làm mới danh sách
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi thêm chi phí: {str(e)}")

    def _bulk_add_expenses(self):
        """Nhập nhiều chi phí bằng bảng dán từ Excel."""
        dialog = BulkExpenseDialog(self.root)
        self.root.wait_window(dialog)
        if not dialog.result:
            return

        success = 0
        skipped = 0
        errors = list(dialog.result.get('errors') or [])
        for idx, row in enumerate(dialog.result.get('rows') or [], 1):
            source_row = row.get('source_row', idx)
            try:
                duplicate = self.expense_mgr.find_duplicate_expense(
                    row['date'], row['project_id'], row['category_id'],
                    row['description'], row['amount']
                )
                if duplicate:
                    skipped += 1
                    errors.append(f"Dòng {source_row}: bỏ qua vì trùng với chi phí #{duplicate['id']}.")
                    continue
                self.expense_mgr.add_expense(
                    row['date'], row['project_id'], row['category_id'],
                    row['description'], row['amount'], row['paid_by'],
                    row['method'], row['notes'], 1, row.get('extra_fields', {})
                )
                success += 1
            except Exception as exc:
                errors.append(f"Dòng {source_row}: không lưu được - {exc}")

        msg = f"Đã nhập {success} chi phí."
        if skipped:
            msg += f"\nĐã bỏ qua {skipped} dòng trùng dữ liệu."
        if errors:
            msg += f"\nLỗi/cảnh báo: {len(errors)} dòng\n" + "\n".join(errors[:10])
        if errors:
            full_msg = f"Đã nhập {success} chi phí."
            if skipped:
                full_msg += f"\nĐã bỏ qua {skipped} dòng trùng dữ liệu."
            full_msg += f"\n\nChi tiết lỗi/cảnh báo ({len(errors)} dòng):\n" + "\n".join(errors)
            self._show_text_report("Kết quả nhập chi phí hàng loạt", full_msg)
        else:
            messagebox.showinfo("Nhập chi phí hàng loạt", msg)
        self._show_expenses()

    def _show_text_report(self, title, content):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("760x520")
        win.minsize(620, 360)
        win.configure(bg=self.theme['bg'])
        tk.Label(win, text=title, bg=self.theme['bg'], fg=self.theme['TEXT_PRIMARY'],
                 font=('Segoe UI', 13, 'bold')).pack(anchor='w', padx=14, pady=(12, 6))
        box_frame = tk.Frame(win, bg=self.theme['bg'])
        box_frame.pack(fill='both', expand=True, padx=14, pady=(0, 10))
        text = tk.Text(box_frame, wrap='word', font=('Consolas', 10),
                       bg='white', fg=self.theme['TEXT_PRIMARY'], relief='flat', bd=0)
        scroll = ttk.Scrollbar(box_frame, orient='vertical', command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        text.insert('1.0', content)
        text.config(state='disabled')
        footer = tk.Frame(win, bg=self.theme['bg'])
        footer.pack(fill='x', padx=14, pady=(0, 12))

        def copy_content():
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("Đã copy", "Đã copy nội dung vào clipboard.")

        create_modern_button(footer, "Copy", copy_content, variant='outline', padx=12, pady=7).pack(side='left')
        create_modern_button(footer, "Đóng", win.destroy, variant='primary', padx=12, pady=7).pack(side='right')

    def _import_expenses(self):
        """Nhập chi phí từ Excel có bước preview trước khi ghi dữ liệu."""
        file_path = filedialog.askopenfilename(
            title="Chọn file Excel",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            valid_rows, error_rows = self._parse_expense_excel_preview(file_path)
            if not self._show_import_preview_dialog("Xem trước nhập chi phí", valid_rows, error_rows):
                return
            success, errors, skipped = self._commit_expense_import_rows(valid_rows)
            msg = f"Đã nhập {success} chi phí."
            if skipped:
                msg += f"\nĐã bỏ qua {skipped} dòng trùng dữ liệu."
            if errors:
                msg += f"\n\nLỗi/cảnh báo ({len(errors)} dòng):\n" + "\n".join(errors)
                self._show_text_report("Kết quả nhập Excel chi phí", msg)
            else:
                messagebox.showinfo("Kết quả nhập", msg)
            self._show_expenses()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi nhập Excel: {str(e)}")

    def _parse_expense_excel_preview(self, file_path):
        from modules.bulk_expense_validator import BulkExpenseValidator
        df, _sheet_name = ExcelImporter.read_excel(file_path)
        projects, categories = self._load_expense_import_lookups()
        validator = BulkExpenseValidator(categories=categories, projects=projects)
        valid_rows = []
        error_rows = []
        raw_rows = []
        source_rows = []

        def clean(value):
            if value is None:
                return ''
            text = str(value).strip()
            return '' if text.lower() in ('nan', 'none', 'nat') else text

        for idx, row in df.iterrows():
            raw = [
                clean(row.get('Ngày', row.get('Ngay', ''))),
                clean(row.get('Dự án ID', row.get('Du an ID', row.get('Dự án', '')))),
                clean(row.get('Loại chi phí ID', row.get('Loai chi phi ID', row.get('Loại chi phí', '')))),
                clean(row.get('Mô tả', row.get('Mo ta', row.get('Nội dung', '')))),
                clean(row.get('Số tiền', row.get('So tien', 0))),
                clean(row.get('Người chi', row.get('Nguoi chi', ''))),
                clean(row.get('Hình thức', row.get('Hinh thuc', 'Tiền mặt'))),
                clean(row.get('Ghi chú', row.get('Ghi chu', ''))),
                clean(row.get('Phòng ban', row.get('Phong ban', ''))),
                clean(row.get('Mục đích sử dụng', row.get('Muc dich su dung', ''))),
                clean(row.get('Danh sách/Nội dung lên mẫu', row.get('Nội dung lên mẫu', ''))),
                clean(row.get('Kế toán ký', '')),
                clean(row.get('Trưởng phòng ký', '')),
                clean(row.get('Người lập', '')),
                clean(row.get('Hồ sơ đính kèm', '')),
            ]
            raw_rows.append(raw)
            source_rows.append(int(idx) + 2)

        results = validator.validate_batch(raw_rows)
        for source_row, result in zip(source_rows, results):
            if result.is_empty:
                continue
            if not result.is_valid or not result.parsed_data:
                error_rows.append({
                    'source_row': source_row,
                    'description': raw_rows[source_rows.index(source_row)][3] if source_row in source_rows else '',
                    'amount': raw_rows[source_rows.index(source_row)][4] if source_row in source_rows else '',
                    'error': '; '.join(result.error_messages),
                })
                continue
            data = result.parsed_data
            valid_rows.append({
                'source_row': source_row,
                'date': data.get('date', ''),
                'project_id': int(data.get('project_id', 0)) if data.get('project_id') else None,
                'category_id': int(data.get('category_id', 0)),
                'description': data.get('description', ''),
                'amount': float(data.get('amount', 0)),
                'paid_by': data.get('paid_by', ''),
                'method': data.get('method') or 'Tiền mặt',
                'notes': data.get('notes', ''),
                'warning': '; '.join(result.warning_messages),
                'extra_fields': {
                    'department': data.get('department', ''),
                    'purpose': data.get('purpose', ''),
                    'item_list': data.get('item_list', ''),
                    'accounting_staff': data.get('accounting_staff', ''),
                    'department_head': data.get('department_head', ''),
                    'prepared_by': data.get('prepared_by', ''),
                    'attachments': data.get('attachments', ''),
                },
            })
        return valid_rows, error_rows

    def _load_expense_import_lookups(self):
        conn = self.expense_mgr.conn
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM projects WHERE status = "active" ORDER BY name')
        projects = [(row['id'], row['name']) for row in cursor.fetchall()]
        cursor.execute('SELECT id, name FROM expense_categories ORDER BY name')
        categories = [(row['id'], row['name']) for row in cursor.fetchall()]
        return projects, categories

    def _show_import_preview_dialog(self, title, valid_rows, error_rows):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("980x560")
        win.minsize(820, 460)
        win.configure(bg=self.theme['bg'])
        win.transient(self.root)
        result = {'confirm': False}
        tk.Label(win, text=title, bg=self.theme['bg'], fg=self.theme['TEXT_PRIMARY'],
                 font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=16, pady=(14, 2))
        tk.Label(win, text=f"Hợp lệ: {len(valid_rows)} dòng   |   Lỗi: {len(error_rows)} dòng",
                 bg=self.theme['bg'], fg=self.theme['TEXT_MUTED'], font=('Segoe UI', 10)).pack(anchor='w', padx=16, pady=(0, 10))

        nb = ttk.Notebook(win)
        nb.pack(fill='both', expand=True, padx=16, pady=(0, 12))

        valid_frame = tk.Frame(nb, bg=self.theme['panel'])
        error_frame = tk.Frame(nb, bg=self.theme['panel'])
        nb.add(valid_frame, text='Hợp lệ')
        nb.add(error_frame, text='Lỗi')

        valid_tree = self._create_tree(valid_frame, ('Dòng', 'Ngày', 'Dự án', 'Loại', 'Mô tả', 'Số tiền', 'Cảnh báo'),
                                       (60, 100, 80, 80, 300, 120, 300))
        for row in valid_rows:
            valid_tree.insert('', 'end', values=(
                row['source_row'], row['date'], row['project_id'] or '', row['category_id'],
                row['description'], f"{row['amount']:,.0f}", row.get('warning', '')
            ))

        error_tree = self._create_tree(error_frame, ('Dòng', 'Mô tả', 'Số tiền', 'Lỗi'), (60, 320, 120, 520))
        for row in error_rows:
            error_tree.insert('', 'end', values=(row['source_row'], row['description'], row['amount'], row['error']))

        footer = tk.Frame(win, bg=self.theme['bg'])
        footer.pack(fill='x', padx=16, pady=(0, 14))

        def confirm():
            if not valid_rows:
                messagebox.showwarning("Nhập Excel", "Không có dòng hợp lệ để nhập.")
                return
            result['confirm'] = True
            win.destroy()

        create_modern_button(footer, "Xác nhận nhập", confirm, variant='primary', padx=14, pady=8).pack(side='left')
        create_modern_button(footer, "Hủy", win.destroy, variant='outline', padx=14, pady=8).pack(side='right')
        self.root.wait_window(win)
        return result['confirm']

    def _commit_expense_import_rows(self, rows):
        success = 0
        skipped = 0
        errors = []
        for idx, row in enumerate(rows, 1):
            source_row = row.get('source_row', idx)
            try:
                duplicate = self.expense_mgr.find_duplicate_expense(
                    row['date'], row['project_id'], row['category_id'], row['description'], row['amount']
                )
                if duplicate:
                    skipped += 1
                    errors.append(f"Dòng {source_row}: bỏ qua vì trùng với chi phí #{duplicate['id']}.")
                    continue
                self.expense_mgr.add_expense(
                    row['date'], row['project_id'], row['category_id'],
                    row['description'], row['amount'], row['paid_by'],
                    row['method'], row['notes'], 1, row.get('extra_fields', {})
                )
                success += 1
            except Exception as exc:
                errors.append(f"Dòng {source_row}: không lưu được - {exc}")
        return success, errors, skipped

    def _export_expense_import_template(self):
        """Xuất file mẫu chuẩn để người dùng điền rồi import."""
        file_path = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=f"mau_nhap_chi_phi_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
        if not file_path:
            return
        try:
            ExcelExporter.export_expense_import_template(file_path)
            messagebox.showinfo("Thành công", f"Đã tạo mẫu nhập chi phí:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không tạo được mẫu nhập: {str(e)}")

    def _export_expenses(self):
        """Xuất chi phí ra Excel."""
        file_path = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=f"expenses_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )

        if not file_path:
            return

        try:
            expenses = self.expense_mgr.get_all_expenses()
            ExcelExporter.export_expenses(expenses, file_path)
            self.audit_mgr.log('expenses', None, 'EXPORT', actor_id=1, new_value={'file': file_path, 'rows': len(expenses)})
            messagebox.showinfo("Thành công", f"Xuất dữ liệu thành công!\n{file_path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi xuất Excel: {str(e)}")

    def _show_documents(self):
        """Hiển thị trang Quản lý hóa đơn/chứng từ."""
        self._clear_content()
        self._page_title("Hóa đơn / Chứng từ", "Quản lý chứng từ, file đính kèm, VAT và trạng thái ghi sổ.")

        button_frame = tk.Frame(self.content_frame, bg=self.theme['bg'])
        button_frame.pack(fill='x', padx=16, pady=(0, 8))
        create_modern_button(button_frame, "+ Thêm chứng từ", self._add_document, variant='primary').pack(side='left', padx=(0, 8))
        create_modern_button(button_frame, "Sửa", self._edit_document, variant='outline').pack(side='left', padx=4)
        create_modern_button(button_frame, "In", self._print_document, variant='outline').pack(side='left', padx=4)
        create_modern_button(button_frame, "Gắn file", self._attach_file, variant='outline').pack(side='left', padx=4)
        create_modern_button(button_frame, "Mở file", self._open_linked_file, variant='outline').pack(side='left', padx=4)
        create_modern_button(button_frame, "Kiểm tra hợp lệ", self._validate_selected_document, variant='warning').pack(side='left', padx=4)
        create_modern_button(button_frame, "Ghi sổ", self._post_selected_document, variant='success').pack(side='left', padx=4)
        create_modern_button(button_frame, "Bỏ ghi", self._unpost_selected_document, variant='secondary').pack(side='left', padx=4)
        create_modern_button(button_frame, "HĐĐT", self._push_selected_einvoice, variant='warning').pack(side='left', padx=4)
        create_modern_button(button_frame, "QR", self._create_selected_document_qr, variant='outline').pack(side='left', padx=4)
        create_modern_button(button_frame, "Nhập Excel", self._import_documents_excel, variant='outline').pack(side='right', padx=4)
        create_modern_button(button_frame, "Xuất Excel", self._export_documents_excel, variant='outline').pack(side='right', padx=4)
        create_modern_button(button_frame, "Xóa", self._delete_document, variant='danger').pack(side='right', padx=4)

        docs_frame = tk.Frame(self.content_frame, bg=self.theme['panel'],
                              highlightbackground=self.theme['line'], highlightthickness=1)
        docs_frame.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        self._show_documents_table(docs_frame)

    def _show_documents_table(self, parent):
        """Hiển thị bảng chứng từ."""
        documents = self.document_mgr.get_all_documents()

        columns = ('ID', 'Loại', 'Số CT', 'Ngày', 'Nhà cung cấp', 'Số tiền', 'VAT %', 'Trạng thái', 'Chi phí ID')
        tree = ttk.Treeview(parent, columns=columns, show='tree headings')
        self.documents_tree = tree

        widths = (50, 120, 120, 100, 220, 120, 70, 100, 80)
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor='e' if col in ('Số tiền', 'VAT %') else 'w')

        for doc in documents:
            tree.insert('', 'end', values=(
                doc[0], doc[1], doc[2], doc[3], doc[4],
                f"{doc[6]:,.0f}" if doc[6] else "0", f"{doc[10] or 10:g}",
                format_status(doc[8]), doc[9] or ''
            ))

        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        x_scroll = ttk.Scrollbar(parent, orient='horizontal', command=tree.xview)
        tree.configure(yscroll=scrollbar.set, xscroll=x_scroll.set)

        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky='nsew', padx=(10, 0), pady=(10, 0))
        scrollbar.grid(row=0, column=1, sticky='ns', padx=(0, 10), pady=(10, 0))
        x_scroll.grid(row=1, column=0, sticky='ew', padx=(10, 0), pady=(0, 10))

    def _add_document(self):
        """Thêm chứng từ mới."""
        dialog = DocumentDialog(self.root)
        self.root.wait_window(dialog)

        if dialog.result:
            try:
                from utils import format_date
                date_str = format_date(dialog.result['doc_date'], '%Y-%m-%d')
                duplicate = self.document_mgr.find_duplicate_invoice(
                    dialog.result['doc_number'], dialog.result['supplier'], dialog.result['amount']
                )
                if duplicate:
                    messagebox.showwarning(
                        "Cảnh báo trùng hóa đơn",
                        f"Hóa đơn này có vẻ đã tồn tại: CT #{duplicate['id']} - "
                        f"{duplicate['supplier_name']} - {duplicate['amount']:,.0f}"
                    )
                    return

                self.document_mgr.add_document(
                    dialog.result['doc_type'],
                    dialog.result['doc_number'],
                    date_str,
                    dialog.result['supplier'],
                    dialog.result['description'],
                    dialog.result['amount'],
                    None,  # project_id
                    None,  # category_id
                    None,  # file_path
                    1,     # created_by
                    dialog.result['expense_id'],
                    dialog.result['status'],
                    dialog.result.get('vat_rate', 10)
                )

                messagebox.showinfo("Thành công", "Thêm chứng từ thành công!")
                self._show_documents()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi thêm chứng từ: {str(e)}")

    def _print_document(self):
        """In chứng từ."""
        doc_id = self._get_selected_document_id()
        if not doc_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một chứng từ trong bảng trước.")
            return
        self._show_document_print_preview(doc_id)

    def _attach_file(self):
        """Liên kết file vào chứng từ đang chọn."""
        doc_id = self._get_selected_document_id()
        if not doc_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một chứng từ trong bảng trước.")
            return

        file_path = filedialog.askopenfilename(
            title="Chọn file để liên kết"
        )

        if file_path:
            self.document_mgr.attach_file(doc_id, file_path)
            messagebox.showinfo("Liên kết file", "Đã gắn file vào chứng từ và nghiệp vụ chi phí liên quan.")
            self._show_documents()

    def _open_linked_file(self):
        doc_id = self._get_selected_document_id()
        if not doc_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một chứng từ trong bảng trước.")
            return
        attachments = self.document_mgr.get_attachments(document_id=doc_id)
        if not attachments:
            messagebox.showinfo("Thông báo", "Chứng từ này chưa có file liên kết.")
            return
        file_path = attachments[0]['file_path']
        try:
            os.startfile(file_path)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không mở được file:\n{file_path}\n\n{str(e)}")

    def _validate_selected_document(self):
        doc_id = self._get_selected_document_id()
        if not doc_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một chứng từ trong bảng trước.")
            return
        issues = self.document_mgr.validate_invoice_compliance(doc_id)
        lines = [f"Kiểm tra hợp lệ chứng từ #{doc_id}", ""]
        level_label = {
            'critical': 'Lỗi',
            'warning': 'Cảnh báo',
            'info': 'Thông tin',
            'ok': 'OK',
        }
        for issue in issues:
            lines.append(f"- {level_label.get(issue.get('level'), issue.get('level'))}: {issue.get('message')}")
        self._show_text_report("Kiểm tra hợp lệ chứng từ", "\n".join(lines))

    def _import_documents_excel(self):
        file_path = filedialog.askopenfilename(
            title="Chọn file Excel chứng từ",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if not file_path:
            return
        try:
            results = ExcelImporter.import_documents_from_excel(file_path, self.document_mgr)
            messagebox.showinfo(
                "Kết quả import",
                f"Thành công: {results['success']} dòng\nLỗi: {results['failed']} dòng\n"
                + "\n".join(results['errors'][:5])
            )
            self._show_documents()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi import chứng từ: {str(e)}")

    def _export_documents_excel(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=f"documents_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
        if not file_path:
            return
        try:
            documents = self.document_mgr.get_all_documents()
            ExcelExporter.export_documents(documents, file_path)
            self.audit_mgr.log('documents', None, 'EXPORT', actor_id=1, new_value={'file': file_path, 'rows': len(documents)})
            messagebox.showinfo("Thành công", f"Đã xuất Excel:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi xuất chứng từ: {str(e)}")

    def _show_document_print_preview(self, doc_id):
        cursor = self.document_mgr.conn.cursor()
        cursor.execute('SELECT * FROM documents WHERE id = ?', (doc_id,))
        doc = cursor.fetchone()
        if not doc:
            return
        preview = tk.Toplevel(self.root)
        preview.title("Mẫu chứng từ trên phần mềm")
        preview.geometry("760x620")

        frame = tk.Frame(preview, bg='white')
        frame.pack(fill='both', expand=True, padx=18, pady=18)

        rows = [
            ("CÔNG TY CỔ PHẦN XÂY DỰNG VÀ ĐẦU TƯ TRUNG HẢI", 14, 'bold'),
            ("PHIẾU/CHỨNG TỪ KẾ TOÁN", 16, 'bold'),
            (f"Loại chứng từ: {doc['doc_type']}", 11, 'normal'),
            (f"Số chứng từ: {doc['doc_number'] or ''}", 11, 'normal'),
            (f"Ngày chứng từ: {doc['doc_date'] or ''}", 11, 'normal'),
            (f"Nhà cung cấp/Người nhận: {doc['supplier_name'] or ''}", 11, 'normal'),
            (f"Nội dung: {doc['description'] or ''}", 11, 'normal'),
            (f"Số tiền: {doc['amount'] or 0:,.0f} đồng", 11, 'bold'),
            (f"VAT: {doc['vat_rate'] or 0:g}%", 11, 'normal'),
            ("", 11, 'normal'),
            ("Người lập phiếu          Kế toán trưởng          Giám đốc", 11, 'normal'),
            ("(Ký, họ tên)             (Ký, họ tên)            (Ký, họ tên)", 10, 'normal'),
        ]
        for text, size, weight in rows:
            tk.Label(frame, text=text, font=('Arial', size, weight), bg='white',
                    wraplength=700, justify='left').pack(anchor='w', pady=6)

        tk.Button(preview, text="Đóng", bg='#95a5a6', fg='white', padx=20, pady=8,
                 command=preview.destroy).pack(pady=8)

    def _get_selected_expense_id(self):
        tree = getattr(self, 'expenses_tree', None)
        if tree and tree.selection():
            values = tree.item(tree.selection()[0], 'values')
            return int(values[0]) if values else None
        return getattr(self, '_last_expense_id', None)

    def _edit_expense_by_id(self, expense_id):
        if self.expense_mgr.is_expense_posted(expense_id):
            messagebox.showwarning("Không sửa được", "Chi phí đã ghi sổ. Bấm Bỏ ghi trên dòng đó trước.")
            return
        dialog = ExpenseDialog(self.root, title=f"Sửa chi phí #{expense_id}", expense_id=expense_id)
        self.root.wait_window(dialog)
        if not dialog.result:
            return
        try:
            from utils import format_date
            date_str = format_date(dialog.result['date'], '%Y-%m-%d')
            duplicate = self.expense_mgr.find_duplicate_expense(
                date_str,
                dialog.result['project_id'],
                dialog.result['category_id'],
                dialog.result['description'],
                dialog.result['amount'],
                exclude_id=expense_id,
            )
            if duplicate and not messagebox.askyesno(
                "Chi phí nghi trùng",
                f"Dữ liệu giống chi phí #{duplicate['id']} đã tồn tại.\n\nVẫn cập nhật dòng này?"
            ):
                return
            self.expense_mgr.update_expense(
                expense_id, date_str,
                dialog.result['project_id'], dialog.result['category_id'],
                dialog.result['description'], dialog.result['amount'],
                dialog.result['paid_by'], dialog.result['method'], dialog.result['notes'],
                dialog.result.get('extra_fields', {}),
                work_item_id=dialog.result.get('work_item_id'),
                contract_id=dialog.result.get('contract_id'),
            )
            messagebox.showinfo("Thành công", "Đã cập nhật chi phí.")
            self._show_expenses()
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _delete_expense_by_id(self, expense_id):
        if not messagebox.askyesno("Xác nhận", f"Xóa chi phí #{expense_id}?"):
            return
        try:
            self.expense_mgr.delete_expense(expense_id)
            messagebox.showinfo("Thành công", "Đã xóa.")
            self._show_expenses()
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _post_expense_by_id(self, expense_id):
        try:
            suggestion = self.utility_mgr.get_account_suggestion_by_expense(expense_id)
            expense = self.utility_mgr.get_expense_detail(expense_id)
            if expense:
                issues = self.utility_mgr.validate_expense_before_post(expense_id)
                critical = [item['message'] for item in issues if item['level'] == 'critical']
                warnings = [item['message'] for item in issues if item['level'] != 'critical']
                if critical:
                    messagebox.showwarning(
                        "Chưa thể ghi sổ",
                        "Cần xử lý trước khi ghi sổ:\n\n- " + "\n- ".join(critical)
                    )
                    self.audit_mgr.log('expenses', expense_id, 'POST_BLOCKED', actor_id=1, new_value={'issues': issues})
                    return
                if warnings and not messagebox.askyesno(
                    "Kiểm soát trước ghi sổ",
                    "Có cảnh báo cần rà soát:\n\n- " + "\n- ".join(warnings) + "\n\nBạn vẫn muốn ghi sổ?"
                ):
                    self.audit_mgr.log('expenses', expense_id, 'POST_CANCELLED', actor_id=1, new_value={'issues': issues})
                    return
                ok, threshold_msg = self.approval_threshold_mgr.can_approve(
                    self.current_user.get('role') or 'kế toán',
                    float(expense['amount'] or 0),
                )
                if not ok:
                    messagebox.showwarning("Vượt hạn mức phê duyệt", threshold_msg)
                    self.audit_mgr.log('expenses', expense_id, 'APPROVAL_BLOCKED', actor_id=1, new_value=threshold_msg)
                    return
            if suggestion and expense:
                dialog = AccountMappingDialog(
                    self.root, self.account_catalog_mgr,
                    expense['category_id'], expense['category_name'], suggestion
                )
                self.root.wait_window(dialog)
                if dialog.result:
                    self.utility_mgr.save_account_mapping(
                        dialog.result['category_id'],
                        dialog.result['debit_account'],
                        dialog.result['credit_account'],
                        dialog.result['notes'],
                    )
            entry_id, debit, credit = self.utility_mgr.create_journal_from_expense(expense_id, 1)
            self.audit_mgr.log(
                'expenses', expense_id, 'POSTED', actor_id=1,
                new_value={'journal_entry_id': entry_id, 'debit': debit, 'credit': credit}
            )
            messagebox.showinfo("Thành công", f"Đã ghi sổ — BT #{entry_id}: Nợ {debit} / Có {credit}.")
            self._show_expenses()
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _unpost_expense_by_id(self, expense_id):
        if not messagebox.askyesno("Bỏ ghi sổ", f"Bỏ ghi sổ chi phí #{expense_id}?"):
            return
        try:
            n = self.utility_mgr.unpost_expense(expense_id, actor='Admin')
            messagebox.showinfo("Thành công", f"Đã bỏ ghi ({n} bút toán).")
            self._show_expenses()
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _view_expense_docs_by_id(self, expense_id):
        docs = self.document_mgr.get_documents_by_expense(expense_id)
        attachments = self.document_mgr.get_attachments(expense_id=expense_id)
        win = tk.Toplevel(self.root)
        win.title(f"Chứng từ chi phí #{expense_id}")
        win.geometry("760x400")
        win.configure(bg=self.theme['bg'])
        nb = ttk.Notebook(win)
        nb.pack(fill='both', expand=True, padx=10, pady=10)
        f1 = tk.Frame(nb, bg=self.theme['panel'])
        nb.add(f1, text=f"Chứng từ ({len(docs)})")
        cols = ('Loại', 'Số CT', 'Ngày', 'Số tiền', 'TT')
        tree = ttk.Treeview(f1, columns=cols, show='headings', height=10)
        for c, w in zip(cols, (120, 120, 100, 110, 90)):
            tree.heading(c, text=c)
            tree.column(c, width=w)
        for d in docs:
            tree.insert('', 'end', values=(d[1], d[2], d[3], f"{d[5]:,.0f}", format_status(d[6])))
        tree.pack(fill='both', expand=True, padx=8, pady=8)
        f2 = tk.Frame(nb, bg=self.theme['panel'])
        nb.add(f2, text=f"File ({len(attachments)})")
        t2 = ttk.Treeview(f2, columns=('Tên', 'Đường dẫn'), show='headings', height=10)
        t2.heading('Tên', text='Tên file')
        t2.heading('Đường dẫn', text='Đường dẫn')
        for a in attachments:
            t2.insert('', 'end', values=(a['file_name'], a['file_path']))
        t2.pack(fill='both', expand=True, padx=8, pady=8)
        bar = tk.Frame(win, bg=self.theme['bg'])
        bar.pack(fill='x', padx=10, pady=(0, 10))
        create_modern_button(bar, "Bút toán", lambda: self._show_expense_journal_for(expense_id), variant='ghost').pack(side='left', padx=4)
        create_modern_button(bar, "Thêm chứng từ", lambda: self._add_document_for_expense_id(expense_id), variant='primary').pack(side='left', padx=4)

    def _show_expense_journal_for(self, expense_id):
        entries = self.utility_mgr.get_journal_entries_for_expense(expense_id)
        win = tk.Toplevel(self.root)
        win.title(f"Bút toán #{expense_id}")
        win.geometry("760x340")
        cols = ('ID', 'Ngày', 'Nợ', 'Có', 'Số tiền', 'Diễn giải')
        tree = ttk.Treeview(win, columns=cols, show='headings', height=8)
        for c, w in zip(cols, (50, 96, 56, 56, 110, 260)):
            tree.heading(c, text=c)
            tree.column(c, width=w)
        for row in entries:
            tree.insert('', 'end', values=(
                row['id'], row['entry_date'], row['debit_account'], row['credit_account'],
                f"{row['amount']:,.0f}", row['description'] or '',
            ))
        tree.pack(fill='both', expand=True, padx=12, pady=12)
        bar = tk.Frame(win)
        bar.pack(fill='x', padx=12, pady=(0, 12))

        def reverse_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Thông báo", "Vui lòng chọn bút toán cần đảo.")
                return
            entry_id = int(tree.item(sel[0], 'values')[0])
            if not messagebox.askyesno("Tạo bút toán đảo", f"Tạo bút toán đảo ngược cho BT #{entry_id}?"):
                return
            try:
                reversal_id = self.journal_control_mgr.reverse_entry(entry_id, actor_id=1)
                messagebox.showinfo("Thành công", f"Đã tạo bút toán đảo #{reversal_id}.")
                win.destroy()
                self._show_expense_journal_for(expense_id)
                self._show_expenses()
            except Exception as exc:
                messagebox.showerror("Lỗi", str(exc))

        create_modern_button(bar, "Tạo bút toán đảo ngược", reverse_selected, variant='danger').pack(side='left', padx=4)

    def _add_document_for_expense_id(self, expense_id):
        dialog = DocumentDialog(self.root, title="Thêm chứng từ", expense_id=expense_id)
        self.root.wait_window(dialog)
        if not dialog.result:
            return
        try:
            from utils import format_date
            date_str = format_date(dialog.result['doc_date'], '%Y-%m-%d')
            self.document_mgr.add_document(
                dialog.result['doc_type'], dialog.result['doc_number'], date_str,
                dialog.result['supplier'], dialog.result['description'], dialog.result['amount'],
                None, None, None, 1, dialog.result['expense_id'], dialog.result['status'],
                dialog.result.get('vat_rate', 10)
            )
            messagebox.showinfo("Thành công", "Đã thêm chứng từ.")
            self._show_expenses()
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _get_selected_document_id(self):
        tree = getattr(self, 'documents_tree', None)
        if not tree or not tree.selection():
            return None
        values = tree.item(tree.selection()[0], 'values')
        return int(values[0]) if values else None

    def _select_tree_row_by_id(self, tree, row_id):
        if not tree:
            return
        target = str(row_id)
        for item in tree.get_children():
            values = tree.item(item, 'values')
            if values and str(values[0]) == target:
                tree.selection_set(item)
                tree.focus(item)
                tree.see(item)
                break

    def _get_selected_expense_category_id(self):
        expense_id = self._get_selected_expense_id()
        if not expense_id:
            return None
        cursor = self.expense_mgr.conn.cursor()
        cursor.execute('SELECT category_id FROM expenses WHERE id = ?', (expense_id,))
        row = cursor.fetchone()
        return row['category_id'] if row else None

    def _add_document_for_selected_expense(self):
        """Thêm chứng từ và gắn trực tiếp vào nghiệp vụ chi phí đang chọn."""
        expense_id = self._get_selected_expense_id()
        if not expense_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một nghiệp vụ chi phí trước.")
            return

        dialog = DocumentDialog(self.root, title="Thêm chứng từ cho chi phí", expense_id=expense_id)
        self.root.wait_window(dialog)

        if dialog.result:
            try:
                from utils import format_date
                date_str = format_date(dialog.result['doc_date'], '%Y-%m-%d')
                self.document_mgr.add_document(
                    dialog.result['doc_type'],
                    dialog.result['doc_number'],
                    date_str,
                    dialog.result['supplier'],
                    dialog.result['description'],
                    dialog.result['amount'],
                    None,
                    None,
                    None,
                    1,
                    dialog.result['expense_id'],
                    dialog.result['status'],
                    dialog.result.get('vat_rate', 10)
                )
                messagebox.showinfo("Thành công", "Đã thêm chứng từ cho nghiệp vụ chi phí.")
                self._show_expenses()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi thêm chứng từ: {str(e)}")

    def _attach_file_to_selected_expense(self):
        """Gắn file trực tiếp theo từng nghiệp vụ chi phí."""
        expense_id = self._get_selected_expense_id()
        if not expense_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một nghiệp vụ chi phí trước.")
            return

        file_path = filedialog.askopenfilename(title="Chọn file chứng từ cho chi phí")
        if file_path:
            self.document_mgr.attach_file(None, file_path, expense_id=expense_id)
            messagebox.showinfo("Thành công", "Đã gắn file chứng từ theo nghiệp vụ chi phí.")
            self._show_expenses()

    def _show_selected_expense_rule(self):
        category_id = self._get_selected_expense_category_id()
        if not category_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một nghiệp vụ chi phí trước.")
            return

        rule = self.compliance_mgr.get_rule_by_category_id(category_id)
        if not rule:
            messagebox.showinfo("Hồ sơ cần có", "Chưa có quy định hồ sơ cho loại chi phí này.")
            return

        messagebox.showinfo(
            "Hồ sơ cần có",
            f"Nghiệp vụ: {rule['transaction_type']}\n\n"
            f"Hồ sơ cần có:\n{rule['required_documents']}\n\n"
            f"Cảnh báo:\n{rule['warning_message']}\n\n"
            f"Căn cứ:\n{rule['legal_basis']}"
        )

    def _show_selected_expense_files(self):
        expense_id = self._get_selected_expense_id()
        if not expense_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một nghiệp vụ chi phí trước.")
            return
        attachments = self.document_mgr.get_attachments(expense_id=expense_id)
        if not attachments:
            messagebox.showinfo("File đính kèm", "Chi phí này chưa có file đính kèm.")
            return

        win = tk.Toplevel(self.root)
        win.title(f"File đính kèm của chi phí #{expense_id}")
        win.geometry("820x420")
        frame = tk.Frame(win, bg='#f0f4f8')
        frame.pack(fill='both', expand=True, padx=12, pady=12)

        columns = ('ID', 'Tên file', 'Số CT', 'Ngày gắn', 'Đường dẫn')
        tree = ttk.Treeview(frame, columns=columns, show='tree headings')
        for col, width in zip(columns, (60, 220, 120, 140, 360)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        for row in attachments:
            tree.insert('', 'end', values=(
                row['id'], row['file_name'] or '', row['doc_number'] or '',
                row['uploaded_at'] or '', row['file_path'] or ''
            ))
        tree.pack(fill='both', expand=True)

        def open_selected():
            if not tree.selection():
                messagebox.showwarning("Thông báo", "Vui lòng chọn file cần mở.")
                return
            values = tree.item(tree.selection()[0], 'values')
            try:
                os.startfile(values[4])
            except Exception as exc:
                messagebox.showerror("Lỗi", f"Không mở được file:\n{values[4]}\n\n{exc}")

        tk.Button(frame, text="Mo file dang chon", bg='#16a085', fg='white',
                 font=('Arial', 10), padx=16, pady=7, command=open_selected).pack(anchor='w', pady=8)

    def _change_selected_expense_status(self, status):
        expense_id = self._get_selected_expense_id()
        if not expense_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một nghiệp vụ chi phí trước.")
            return
        try:
            self.utility_mgr.update_expense_status(expense_id, status, actor='Admin')
            messagebox.showinfo("Thành công", f"Đã cập nhật trạng thái chi phí thành {status}.")
            self._show_expenses()
        except Exception as exc:
            messagebox.showerror("Lỗi", f"Không cập nhật được trạng thái: {exc}")

    def _post_selected_expense(self):
        eid = self._get_selected_expense_id()
        if eid:
            self._post_expense_by_id(eid)

    def _unpost_selected_expense(self):
        eid = self._get_selected_expense_id()
        if eid:
            self._unpost_expense_by_id(eid)

    def _edit_expense(self):
        eid = self._get_selected_expense_id()
        if eid:
            self._edit_expense_by_id(eid)

    def _delete_expense(self):
        eid = self._get_selected_expense_id()
        if eid:
            self._delete_expense_by_id(eid)

    def _show_expense_journal(self):
        eid = self._get_selected_expense_id()
        if eid:
            self._show_expense_journal_for(eid)

    def _show_advances(self):
        self._clear_content()
        self._page_title("Tạm ứng", "Theo dõi tạm ứng, hoàn ứng và khoản còn treo theo nhân viên/dự án.")
        frame = tk.Frame(self.content_frame, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        frame.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        self._show_advance_summary(frame)

    def _show_journals(self):
        self._clear_content()
        self._page_title("Bút toán", "Danh sách bút toán kế toán và trạng thái đảo ngược.")
        cols = ('ID', 'Ngày', 'Diễn giải', 'Nợ', 'Có', 'Số tiền', 'Loại', 'Đảo bởi')
        tree = ttk.Treeview(self.content_frame, columns=cols, show='headings', height=20)
        for col, width in zip(cols, (60, 100, 320, 80, 80, 130, 100, 80)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        cursor = self.utility_mgr.conn.cursor()
        cursor.execute('''
            SELECT id, entry_date, COALESCE(description, '') AS description,
                   COALESCE(debit_account, '') AS debit_account,
                   COALESCE(credit_account, '') AS credit_account,
                   COALESCE(amount, 0) AS amount,
                   COALESCE(entry_type, '') AS entry_type,
                   COALESCE(reversed_by, '') AS reversed_by
            FROM journal_entries
            ORDER BY entry_date DESC, id DESC
            LIMIT 500
        ''')
        for row in cursor.fetchall():
            tree.insert('', 'end', values=(
                row['id'], row['entry_date'], row['description'], row['debit_account'],
                row['credit_account'], f"{row['amount']:,.0f}", row['entry_type'], row['reversed_by'],
            ))
        tree.pack(fill='both', expand=True, padx=16, pady=(0, 16))

    def _show_contracts(self):
        """Màn hình quản lý hợp đồng riêng, không trộn với kế toán dự án."""
        self._clear_content()
        self._page_title(
            "HỢP ĐỒNG & THANH TOÁN",
            "Theo dõi hợp đồng thi công, thầu phụ, cung cấp vật tư, nghiệm thu và phần còn phải thanh toán."
        )

        dashboard = self.project_acct_mgr.get_global_dashboard()
        cards = tk.Frame(self.content_frame, bg=self.theme['bg'])
        cards.pack(fill='x', padx=18, pady=(0, 8))
        for label, value, color in [
            ("HĐ sắp hết hạn", dashboard.get('expiring_contracts', 0), self.theme['warning']),
            ("Dự án đang chạy", dashboard.get('active_projects', 0), self.theme['info']),
            ("Tổng doanh thu", f"{dashboard.get('total_revenue', 0):,.0f}", self.theme['success']),
            ("Lãi/lỗ sơ bộ", f"{dashboard.get('profit', 0):,.0f}",
             self.theme['success'] if dashboard.get('profit', 0) >= 0 else self.theme['danger']),
        ]:
            self._create_stat_card(cards, label, str(value), color)

        toolbar = tk.Frame(self.content_frame, bg=self.theme['bg'])
        toolbar.pack(fill='x', padx=18, pady=(0, 8))

        self.contract_project_var = tk.StringVar()
        self.contract_type_var = tk.StringVar(value="Tất cả")
        self.contract_keyword_var = tk.StringVar()
        projects = [(p['id'], p['code'], p['name']) for p in self.project_acct_mgr.list_projects_active()]
        project_values = ["Tất cả dự án"] + [f"{p[0]} - {p[1]} - {p[2]}" for p in projects if p[1] != 'CHUNG']

        tk.Label(toolbar, text="Dự án:", bg=self.theme['bg']).pack(side='left')
        project_combo = ttk.Combobox(toolbar, textvariable=self.contract_project_var,
                                     values=project_values, width=34, state='readonly')
        project_combo.pack(side='left', padx=6)
        project_combo.current(0)

        type_labels = ["Tất cả"] + list(config.CONTRACT_TYPES.values())
        tk.Label(toolbar, text="Loại:", bg=self.theme['bg']).pack(side='left', padx=(8, 0))
        type_combo = ttk.Combobox(toolbar, textvariable=self.contract_type_var,
                                  values=type_labels, width=24, state='readonly')
        type_combo.pack(side='left', padx=6)

        tk.Label(toolbar, text="Tìm:", bg=self.theme['bg']).pack(side='left', padx=(8, 0))
        self.contract_search_entry = tk.Entry(toolbar, textvariable=self.contract_keyword_var,
                                              font=('Segoe UI', 10), width=24)
        self.contract_search_entry.pack(side='left', padx=6)
        self.contract_search_entry.bind('<Return>', lambda _e: self._refresh_contracts_view())
        self.active_search_entry = self.contract_search_entry

        self._make_button(toolbar, "Lọc", self._refresh_contracts_view, self.theme['primary']).pack(side='left', padx=4)
        self._make_button(toolbar, "Thêm HĐ", self._pa_add_contract, self.theme['success']).pack(side='left', padx=4)
        self._make_button(toolbar, "Nghiệm thu", self._pa_add_billing, self.theme['info']).pack(side='left', padx=4)

        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True, padx=18, pady=(0, 15))

        list_frame = tk.Frame(notebook, bg=self.theme['panel'])
        bill_frame = tk.Frame(notebook, bg=self.theme['panel'])
        progress_frame = tk.Frame(notebook, bg=self.theme['panel'])
        subcontract_frame = tk.Frame(notebook, bg=self.theme['panel'])
        notebook.add(list_frame, text='Danh sách HĐ')
        notebook.add(bill_frame, text='Nghiệm thu / thanh toán')
        notebook.add(progress_frame, text='Tiến độ HĐ')
        notebook.add(subcontract_frame, text='Thầu phụ & bảo lãnh')

        self.contract_tree = self._create_tree(
            list_frame,
            ('ID', 'Mã DA', 'Dự án', 'Loại', 'Số HĐ', 'Đối tác', 'Ngày ký', 'Giá trị', 'Đã NT', 'Còn lại', 'TT'),
            (50, 70, 170, 120, 110, 180, 90, 120, 120, 120, 90)
        )
        self.contract_billing_tree = self._create_tree(
            bill_frame,
            ('ID', 'Mã DA', 'Dự án', 'Số HĐ', 'Đối tác', 'Ngày', 'Mốc', 'Trước VAT', 'VAT', 'Giữ lại', 'Thực nhận', 'TT'),
            (45, 70, 150, 100, 160, 90, 130, 110, 90, 90, 110, 80)
        )
        self.contract_progress_tree = self._create_tree(
            progress_frame,
            ('Mã DA', 'Dự án', 'Số HĐ', 'Đối tác', 'Loại', 'Giá trị', 'Đã NT', 'Còn lại'),
            (70, 180, 110, 170, 120, 120, 120, 120)
        )
        self.contract_subcontract_tree = self._create_tree(
            subcontract_frame,
            ('Mã DA', 'Dự án', 'ID HĐ', 'Số HĐ', 'Nhà thầu phụ', 'Giá trị HĐ', 'Đã thực hiện', 'Còn lại', 'Bảo lãnh', 'Bảo hành'),
            (70, 160, 60, 110, 180, 120, 120, 120, 100, 90)
        )
        self._refresh_contracts_view()

    def _get_contract_project_filter_id(self):
        value = getattr(self, 'contract_project_var', tk.StringVar()).get()
        if not value or value == "Tất cả dự án":
            return None
        try:
            return int(value.split(' - ', 1)[0])
        except (ValueError, IndexError):
            return None

    def _get_contract_type_filter(self):
        label = getattr(self, 'contract_type_var', tk.StringVar(value="Tất cả")).get()
        if not label or label == "Tất cả":
            return None
        type_map = {v: k for k, v in config.CONTRACT_TYPES.items()}
        return type_map.get(label)

    def _refresh_contracts_view(self):
        project_id = self._get_contract_project_filter_id()
        contract_type = self._get_contract_type_filter()
        keyword = self.contract_keyword_var.get().strip() if hasattr(self, 'contract_keyword_var') else None

        for tree_name in ('contract_tree', 'contract_billing_tree', 'contract_progress_tree', 'contract_subcontract_tree'):
            tree = getattr(self, tree_name, None)
            if tree:
                for item in tree.get_children():
                    tree.delete(item)

        for row in self.project_acct_mgr.get_contracts(project_id=project_id, contract_type=contract_type, keyword=keyword):
            billed = row['billed'] or 0
            value = row['contract_value'] or 0
            ctype = config.CONTRACT_TYPES.get(row['contract_type'], row['contract_type'])
            self.contract_tree.insert('', 'end', values=(
                row['id'], row['code'], row['name'], ctype, row['contract_no'], row['partner_name'],
                row['signed_date'] or '', f"{value:,.0f}", f"{billed:,.0f}",
                f"{value - billed:,.0f}", row['status'],
            ))

        for row in self.project_acct_mgr.get_billings(project_id=project_id):
            if contract_type and row['contract_type'] != contract_type:
                continue
            self.contract_billing_tree.insert('', 'end', values=(
                row['id'], row['code'], row['name'], row['contract_no'], row['partner_name'],
                row['billing_date'], row['milestone_name'], f"{row['amount_before_vat']:,.0f}",
                f"{row['vat_amount']:,.0f}", f"{row['retention_amount']:,.0f}",
                f"{row['net_amount']:,.0f}", row['status'],
            ))

        for row in self.project_acct_mgr.get_contract_progress_report(project_id):
            if contract_type and row['contract_type'] != contract_type:
                continue
            self.contract_progress_tree.insert('', 'end', values=(
                row['code'], row['name'], row['contract_no'], row['partner_name'],
                config.CONTRACT_TYPES.get(row['contract_type'], row['contract_type']),
                f"{row['contract_value']:,.0f}", f"{row['billed']:,.0f}", f"{row['remaining']:,.0f}",
            ))

        for row in self.project_acct_mgr.get_subcontract_control_report(project_id):
            if contract_type and contract_type != 'subcontract':
                continue
            self.contract_subcontract_tree.insert('', 'end', values=(
                row['code'], row['name'], row['id'], row['contract_no'], row['partner_name'],
                f"{row['contract_value']:,.0f}", f"{row['performed_value']:,.0f}", f"{row['remaining']:,.0f}",
                f"{row['active_bonds']:,.0f}", row['active_warranties'],
            ))

    def _show_backup_settings(self):
        self._clear_content()
        self._page_title("Sao lưu & phục hồi", "Theo dõi trạng thái bảo vệ dữ liệu và thao tác backup khi cần.")
        panel = tk.Frame(self.content_frame, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        panel.pack(fill='x', padx=16, pady=(0, 16))
        tk.Label(panel, text=self._backup_status_text(), font=('Segoe UI', 11),
                 bg=self.theme['panel'], fg=self.theme['text'], justify='left').pack(anchor='w', padx=16, pady=(14, 10))
        buttons = tk.Frame(panel, bg=self.theme['panel'])
        buttons.pack(fill='x', padx=12, pady=(0, 14))
        create_modern_button(buttons, "Sao lưu ngay", self._create_backup, variant='success').pack(side='left', padx=4)
        create_modern_button(buttons, "Phục hồi", self._restore_backup, variant='warning').pack(side='left', padx=4)
        create_modern_button(buttons, "Danh sách sao lưu", self._show_backups, variant='accent').pack(side='left', padx=4)
        create_modern_button(buttons, "Kiểm tra sao lưu", self._show_backup_health, variant='accent').pack(side='left', padx=4)
        create_modern_button(buttons, "Dữ liệu dùng chung", self._configure_shared_database, variant='accent').pack(side='left', padx=4)

    def _edit_document(self):
        doc_id = self._get_selected_document_id()
        if not doc_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn chứng từ cần sửa.")
            return
        if self.document_mgr.is_document_posted(doc_id):
            messagebox.showwarning("Không sửa được", "Chứng từ đã ghi sổ. Bấm Bỏ ghi trước.")
            return
        dialog = DocumentDialog(self.root, title=f"Sửa chứng từ #{doc_id}", document_id=doc_id)
        self.root.wait_window(dialog)
        if not dialog.result:
            return
        try:
            from utils import format_date
            date_str = format_date(dialog.result['doc_date'], '%Y-%m-%d')
            duplicate = self.document_mgr.find_duplicate_invoice(
                dialog.result['doc_number'], dialog.result['supplier'], dialog.result['amount'],
                exclude_document_id=doc_id
            )
            if duplicate:
                messagebox.showwarning(
                    "Cảnh báo trùng hóa đơn",
                    f"Hóa đơn này có vẻ đã tồn tại: CT #{duplicate['id']} - "
                    f"{duplicate['supplier_name']} - {duplicate['amount']:,.0f}"
                )
                return
            self.document_mgr.update_document(
                doc_id, dialog.result['doc_type'], dialog.result['doc_number'],
                date_str, dialog.result['supplier'], dialog.result['description'],
                dialog.result['amount'], dialog.result['expense_id'], dialog.result['status'],
                dialog.result.get('vat_rate', 10),
            )
            messagebox.showinfo("Thành công", "Đã cập nhật chứng từ.")
            self._show_documents()
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _delete_document(self):
        doc_id = self._get_selected_document_id()
        if not doc_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn chứng từ cần xóa.")
            return
        if not messagebox.askyesno("Xác nhận", "Xóa chứng từ này?"):
            return
        try:
            self.document_mgr.delete_document(doc_id)
            messagebox.showinfo("Thành công", "Đã xóa chứng từ.")
            self._show_documents()
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _post_selected_document(self):
        doc_id = self._get_selected_document_id()
        if not doc_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn chứng từ.")
            return
        try:
            issues = self.document_mgr.validate_document_before_post(doc_id)
            critical = [item['message'] for item in issues if item['level'] == 'critical']
            warnings = [item['message'] for item in issues if item['level'] != 'critical']
            if critical:
                messagebox.showwarning("Chưa thể ghi sổ", "Cần xử lý trước:\n\n- " + "\n- ".join(critical))
                self.audit_mgr.log('documents', doc_id, 'POST_BLOCKED', actor_id=1, new_value={'issues': issues})
                return
            if warnings and not messagebox.askyesno(
                "Kiểm soát chứng từ",
                "Có cảnh báo cần rà soát:\n\n- " + "\n- ".join(warnings) + "\n\nBạn vẫn muốn ghi sổ?"
            ):
                self.audit_mgr.log('documents', doc_id, 'POST_CANCELLED', actor_id=1, new_value={'issues': issues})
                return
            self.document_mgr.post_document(doc_id)
            self.audit_mgr.log('documents', doc_id, 'POSTED', actor_id=1, new_value={'status': 'posted'})
            messagebox.showinfo("Thành công", "Đã ghi sổ chứng từ.")
            self._show_documents()
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _unpost_selected_document(self):
        doc_id = self._get_selected_document_id()
        if not doc_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn chứng từ.")
            return
        try:
            self.document_mgr.unpost_document(doc_id)
            messagebox.showinfo("Thành công", "Đã bỏ ghi sổ chứng từ.")
            self._show_documents()
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _push_selected_einvoice(self):
        doc_id = self._get_selected_document_id()
        if not doc_id:
            messagebox.showwarning("HĐĐT", "Vui lòng chọn chứng từ.")
            return
        try:
            result = self.einvoice_mgr.push_document(doc_id, provider='MISA')
            messagebox.showinfo("HĐĐT", f"Trạng thái: {result.get('status')}\n{result.get('message', '')}")
            self._show_documents()
        except Exception as exc:
            messagebox.showerror("HĐĐT", str(exc))

    def _create_selected_document_qr(self):
        doc_id = self._get_selected_document_id()
        if not doc_id:
            messagebox.showwarning("QR", "Vui lòng chọn chứng từ.")
            return
        try:
            path, payload = self.qr_mgr.create_qr_for_document(doc_id)
            messagebox.showinfo("QR chứng từ", f"Đã tạo QR:\n{path}\n\n{payload}")
        except Exception as exc:
            messagebox.showerror("QR", str(exc))

    def _print_forms_for_selected_expense(self):
        expense_id = self._get_selected_expense_id()
        if not expense_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một nghiệp vụ chi phí trước.")
            return
        dialog = ExpensePrintDialog(self.root, self.template_renderer, expense_id)
        self.root.wait_window(dialog)
        if dialog.result:
            output_path = dialog.result['output_path']
            try:
                os.startfile(os.path.abspath(output_path))
            except Exception as exc:
                messagebox.showerror("Lỗi", f"Không mở được chứng từ đã tạo: {exc}")

    def _show_missing_documents(self):
        self._clear_content()
        self._page_title("Chi phí thiếu hồ sơ", "Rà soát hóa đơn, file scan và hồ sơ bắt buộc trước khi duyệt/ghi sổ.")

        toolbar = tk.Frame(self.content_frame, bg=self.theme['bg'])
        toolbar.pack(fill='x', padx=16, pady=(0, 8))
        tk.Label(toolbar, text="Lọc", font=('Segoe UI', 10, 'bold'),
                 bg=self.theme['bg'], fg=self.theme['TEXT_MUTED']).pack(side='left')
        self.missing_search_var = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.missing_search_var, width=35)
        entry.pack(side='left', padx=6)
        entry.bind('<Return>', lambda _e: self._refresh_missing_documents())
        self.active_search_entry = entry
        create_modern_button(toolbar, "Quét lại", self._refresh_missing_documents,
                             variant='primary', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(toolbar, "Mở chi phí", self._open_missing_expense,
                             variant='outline', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(toolbar, "Thêm chứng từ", self._add_document_for_missing_expense,
                             variant='outline', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(toolbar, "Gắn file", self._attach_file_for_missing_expense,
                             variant='outline', padx=12, pady=7).pack(side='left', padx=4)

        frame = tk.Frame(self.content_frame, bg=self.theme['panel'],
                         highlightbackground=self.theme['line'], highlightthickness=1)
        frame.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        columns = ('ID', 'Ngày', 'Dự án', 'Loại', 'Mô tả', 'Số tiền', 'Trạng thái', 'CT', 'File', 'Hồ sơ cần có')
        self.missing_tree = ttk.Treeview(frame, columns=columns, show='tree headings')
        for col, width in zip(columns, (60, 90, 150, 140, 220, 110, 90, 50, 50, 420)):
            self.missing_tree.heading(col, text=col)
            self.missing_tree.column(col, width=width)
        y_scroll = ttk.Scrollbar(frame, orient='vertical', command=self.missing_tree.yview)
        x_scroll = ttk.Scrollbar(frame, orient='horizontal', command=self.missing_tree.xview)
        self.missing_tree.configure(yscroll=y_scroll.set, xscroll=x_scroll.set)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.missing_tree.grid(row=0, column=0, sticky='nsew', padx=(10, 0), pady=(10, 0))
        y_scroll.grid(row=0, column=1, sticky='ns', padx=(0, 10), pady=(10, 0))
        x_scroll.grid(row=1, column=0, sticky='ew', padx=(10, 0), pady=(0, 10))
        self._refresh_missing_documents()

    def _get_selected_missing_expense_id(self):
        tree = getattr(self, 'missing_tree', None)
        if not tree or not tree.selection():
            messagebox.showwarning("Thiếu hồ sơ", "Vui lòng chọn một dòng chi phí.")
            return None
        values = tree.item(tree.selection()[0], 'values')
        return int(values[0]) if values and values[0] else None

    def _open_missing_expense(self):
        expense_id = self._get_selected_missing_expense_id()
        if expense_id:
            self._open_expense_detail(expense_id)

    def _add_document_for_missing_expense(self):
        expense_id = self._get_selected_missing_expense_id()
        if expense_id:
            self._add_document_for_expense_id(expense_id)
            self._refresh_missing_documents()

    def _attach_file_for_missing_expense(self):
        expense_id = self._get_selected_missing_expense_id()
        if not expense_id:
            return
        file_path = filedialog.askopenfilename(title="Chọn file chứng từ cho chi phí")
        if file_path:
            self.document_mgr.attach_file(None, file_path, expense_id=expense_id)
            self._refresh_missing_documents()

    def _refresh_missing_documents(self):
        tree = getattr(self, 'missing_tree', None)
        if not tree:
            return
        for item in tree.get_children():
            tree.delete(item)
        keyword = self.missing_search_var.get().strip() if hasattr(self, 'missing_search_var') else None
        for row in self.utility_mgr.get_missing_document_expenses(keyword):
            tree.insert('', 'end', values=(
                row[0], row[1], row[2], row[3], row[4],
                f"{row[5]:,.0f}", row[6], row[9], row[10], row[8]
            ))

    def _show_linkage_checks(self):
        self._clear_content()
        self._page_title("Kiểm tra liên kết dữ liệu", "Phát hiện lệch dữ liệu giữa chi phí, chứng từ, bút toán, dự án và vật tư.")

        toolbar = tk.Frame(self.content_frame, bg=self.theme['bg'])
        toolbar.pack(fill='x', padx=16, pady=(0, 8))
        create_modern_button(toolbar, "Quét lại", self._refresh_linkage_checks,
                             variant='primary', padx=14, pady=7).pack(side='left')

        frame = tk.Frame(self.content_frame, bg=self.theme['panel'],
                         highlightbackground=self.theme['line'], highlightthickness=1)
        frame.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        columns = ('Phân hệ', 'Vấn đề kiểm tra', 'Trạng thái', 'Số lượng', 'Ý nghĩa', 'Gợi ý xử lý')
        self.linkage_tree = ttk.Treeview(frame, columns=columns, show='tree headings')
        widths = (100, 220, 100, 80, 360, 360)
        for col, width in zip(columns, widths):
            self.linkage_tree.heading(col, text=col)
            self.linkage_tree.column(col, width=width)
        y_scroll = ttk.Scrollbar(frame, orient='vertical', command=self.linkage_tree.yview)
        x_scroll = ttk.Scrollbar(frame, orient='horizontal', command=self.linkage_tree.xview)
        self.linkage_tree.configure(yscroll=y_scroll.set, xscroll=x_scroll.set)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.linkage_tree.grid(row=0, column=0, sticky='nsew', padx=(10, 0), pady=(10, 0))
        y_scroll.grid(row=0, column=1, sticky='ns', padx=(0, 10), pady=(10, 0))
        x_scroll.grid(row=1, column=0, sticky='ew', padx=(10, 0), pady=(0, 10))
        self._refresh_linkage_checks()

    def _refresh_linkage_checks(self):
        tree = getattr(self, 'linkage_tree', None)
        if not tree:
            return
        for item in tree.get_children():
            tree.delete(item)
        for row in self.utility_mgr.get_linkage_checks():
            tree.insert('', 'end', values=row)

    def _show_extension_controls(self):
        self._clear_content()
        self._page_title("Kiểm soát mở rộng", "Rà soát các nghiệp vụ bổ sung: rollback, hạn mức duyệt, audit đọc, TSCĐ, công nợ, hết hạn.")
        self.audit_mgr.log('extension_controls', None, 'READ', actor_id=1, new_value={'screen': 'extension_controls'})

        nb = ttk.Notebook(self.content_frame)
        nb.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        self._render_threshold_tab(nb)
        self._render_read_audit_tab(nb)
        self._render_fixed_asset_tab(nb)
        self._render_ar_ap_tab(nb)
        self._render_simple_report_tab(nb, 'Hết hạn', ('Loại', 'Tên', 'Số/Ref', 'Ngày hết hạn', 'Phụ trách', 'TT'),
                                      (120, 240, 120, 110, 140, 90),
                                      lambda: [(r['item_type'], r['item_name'], r['reference_no'], r['expiry_date'], r['owner'], r['status'])
                                               for r in self.extension_report_mgr.expiring_items(60)])
        self._render_simple_report_tab(nb, 'So sánh nhiều kỳ', ('Kỳ', 'Tổng chi phí', '% thay đổi'),
                                      (100, 150, 120),
                                      lambda: [(r['period'], f"{r['total']:,.0f}",
                                                '' if r['change_pct'] is None else f"{r['change_pct']:.1f}%")
                                               for r in self.extension_report_mgr.multi_period_expenses(12)])
        self._render_simple_report_tab(nb, 'QS vs thực tế', ('DA', 'HM', 'Tên hạng mục', 'QS gốc', 'QS điều chỉnh', 'Thực tế', 'Chênh lệch'),
                                      (70, 80, 220, 120, 120, 120, 120),
                                      lambda: [(r['project_code'], r['item_code'], r['item_name'],
                                                f"{r['original_budget'] or 0:,.0f}", f"{r['revised_budget'] or 0:,.0f}",
                                                f"{r['actual_cost'] or 0:,.0f}", f"{(r['actual_cost'] or 0) - (r['revised_budget'] or 0):,.0f}")
                                               for r in self.extension_report_mgr.qs_reconciliation_report()])
        self._render_simple_report_tab(nb, 'Doanh thu POC', ('DA', 'Dự án', 'Kỳ', 'Giá trị HĐ', '% trước', '% hiện tại', 'DT ghi nhận'),
                                      (70, 220, 90, 120, 80, 80, 120),
                                      lambda: [(r['code'], r['name'], r['period'], f"{r['contract_value'] or 0:,.0f}",
                                                f"{r['previous_percent'] or 0:.1f}%", f"{r['current_percent'] or 0:.1f}%",
                                                f"{r['revenue_amount'] or 0:,.0f}")
                                               for r in self.extension_report_mgr.poc_revenue_report()])
        self._render_simple_report_tab(nb, 'Nhà cung cấp', ('Nhà cung cấp', 'Kỳ', 'Giá', 'Chất lượng', 'Tiến độ', 'Hồ sơ', 'TB', 'TT'),
                                      (220, 90, 70, 90, 80, 80, 70, 100),
                                      lambda: [(r['supplier_name'], r['period'], r['price_score'], r['quality_score'],
                                                r['delivery_score'], r['document_score'], f"{r['avg_score'] or 0:.1f}", r['status'])
                                               for r in self.extension_report_mgr.vendor_scorecards()])

    def _render_threshold_tab(self, notebook):
        frame = tk.Frame(notebook, bg=self.theme['panel'])
        notebook.add(frame, text='Hạn mức duyệt')
        toolbar = tk.Frame(frame, bg=self.theme['panel'])
        toolbar.pack(fill='x', padx=12, pady=(12, 8))
        tree_holder = tk.Frame(frame, bg=self.theme['panel'])
        tree_holder.pack(fill='both', expand=True)
        tree = self._create_tree(tree_holder, ('Role', 'Hạn mức tối đa', 'Duyệt cuối', 'Active'), (140, 160, 100, 80))
        self.threshold_tree = tree

        def reload_tree():
            for item in tree.get_children():
                tree.delete(item)
            for row in self.approval_threshold_mgr.list_thresholds():
                tree.insert('', 'end', values=(row['role'], f"{row['max_amount']:,.0f}", '1' if row['can_final_approve'] else '0', '1' if row['active'] else '0'))

        def edit_threshold():
            selected = tree.selection()
            values = tree.item(selected[0], 'values') if selected else ('', '0', '0', '1')
            dialog = SimpleCatalogDialog(self.root, "Hạn mức phê duyệt", [
                ('role', 'Role:', values[0]),
                ('max_amount', 'Hạn mức tối đa:', values[1]),
                ('can_final_approve', 'Duyệt cuối (1/0):', values[2]),
                ('active', 'Active (1/0):', values[3]),
            ])
            self.root.wait_window(dialog)
            if dialog.result:
                try:
                    self.approval_threshold_mgr.save_threshold(
                        dialog.result['role'],
                        parse_number(dialog.result['max_amount']),
                        dialog.result.get('can_final_approve') or 0,
                        dialog.result.get('active') or 1,
                    )
                    reload_tree()
                except Exception as exc:
                    messagebox.showerror("Hạn mức duyệt", str(exc))

        create_modern_button(toolbar, "Thêm / sửa hạn mức", edit_threshold,
                             variant='primary', padx=12, pady=7).pack(side='left')
        create_modern_button(toolbar, "Làm mới", reload_tree,
                             variant='outline', padx=12, pady=7).pack(side='left', padx=6)
        tree.bind('<Double-1>', lambda _e: edit_threshold())
        reload_tree()

    def _render_read_audit_tab(self, notebook):
        frame = tk.Frame(notebook, bg=self.theme['panel'])
        notebook.add(frame, text='Audit đọc/xuất')
        self._build_audit_log_content(frame)

    def _show_audit_log(self):
        if (self.current_user.get('role') or '').lower() != 'admin':
            messagebox.showwarning("Audit log", "Chỉ Admin được xem nhật ký audit.")
            return
        self._clear_content()
        self._page_title("Audit log", "Theo dõi thao tác đọc, xuất báo cáo, ghi sổ và các lần bị chặn kiểm soát.")
        holder = tk.Frame(self.content_frame, bg=self.theme['panel'])
        holder.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        self._build_audit_log_content(holder)

    def _build_audit_log_content(self, frame):
        toolbar = tk.Frame(frame, bg=self.theme['panel'])
        toolbar.pack(fill='x', padx=12, pady=(12, 8))
        tk.Label(toolbar, text="Hành động", bg=self.theme['panel'], fg=self.theme['TEXT_MUTED'],
                 font=('Segoe UI', 10, 'bold')).pack(side='left')
        action_var = tk.StringVar(value='all')
        ttk.Combobox(
            toolbar, textvariable=action_var,
            values=('all', 'READ', 'EXPORT', 'VIEW_REPORT', 'POSTED', 'POST_BLOCKED', 'POST_CANCELLED', 'APPROVAL_BLOCKED'),
            width=18, state='readonly'
        ).pack(side='left', padx=(8, 10))
        tk.Label(toolbar, text="Từ", bg=self.theme['panel'], fg=self.theme['TEXT_MUTED'],
                 font=('Segoe UI', 9)).pack(side='left', padx=(8, 2))
        start_date_var = tk.StringVar(value='')
        start_entry = self._create_placeholder_entry(toolbar, start_date_var, 'YYYY-MM-DD')
        start_entry.configure(width=12)
        start_entry.pack(side='left', padx=(0, 8))
        tk.Label(toolbar, text="Đến", bg=self.theme['panel'], fg=self.theme['TEXT_MUTED'],
                 font=('Segoe UI', 9)).pack(side='left', padx=(0, 2))
        end_date_var = tk.StringVar(value='')
        end_entry = self._create_placeholder_entry(toolbar, end_date_var, 'YYYY-MM-DD')
        end_entry.configure(width=12)
        end_entry.pack(side='left', padx=(0, 8))
        tk.Label(toolbar, text="User", bg=self.theme['panel'], fg=self.theme['TEXT_MUTED'], font=('Segoe UI', 9)).pack(side='left', padx=(0, 2))
        actor_var = tk.StringVar(value='')
        actor_entry = tk.Entry(toolbar, textvariable=actor_var, width=10)
        actor_entry.pack(side='left', padx=(0, 8))
        tk.Label(toolbar, text="Đối tượng", bg=self.theme['panel'], fg=self.theme['TEXT_MUTED'], font=('Segoe UI', 9)).pack(side='left', padx=(0, 2))
        entity_type_var = tk.StringVar(value='all')
        ttk.Combobox(
            toolbar, textvariable=entity_type_var,
            values=('all', 'expense', 'invoice', 'journal', 'report', 'user', 'project', 'payment'),
            width=14, state='readonly'
        ).pack(side='left', padx=(0, 8))
        tk.Label(toolbar, text="Tìm", bg=self.theme['panel'], fg=self.theme['TEXT_MUTED'], font=('Segoe UI', 9)).pack(side='left', padx=(0, 2))
        search_var = tk.StringVar(value='')
        search_entry = self._create_placeholder_entry(toolbar, search_var, 'Tìm nhanh...')
        search_entry.configure(width=18)
        search_entry.pack(side='left', padx=(0, 8))
        page_var = tk.IntVar(value=0)
        page_label = tk.Label(toolbar, text="Trang 1", bg=self.theme['panel'],
                              fg=self.theme['TEXT_MUTED'], font=('Segoe UI', 9, 'bold'))
        page_label.pack(side='left', padx=(8, 4))
        results_label = tk.Label(toolbar, text="Đang tải dữ liệu...", bg=self.theme['panel'],
                                 fg=self.theme['TEXT_MUTED'], font=('Segoe UI', 9))
        results_label.pack(side='right', padx=(0, 8))

        summary_var = tk.StringVar(value='Chưa có dữ liệu lọc.')
        summary_label = tk.Label(toolbar, textvariable=summary_var, bg=self.theme['panel'],
                                 fg=self.theme['TEXT_MUTED'], font=('Segoe UI', 9))
        summary_label.pack(side='right', padx=(0, 16))

        note_label = tk.Label(toolbar, text='Audit log hiển thị dữ liệu theo bộ lọc; dùng Xuất toàn bộ để lấy tất cả.',
                              bg=self.theme['panel'], fg=self.theme['TEXT_MUTED'], font=('Segoe UI', 9, 'italic'))
        note_label.pack(side='right', padx=(0, 16))

        def clear_filters():
            action_var.set('all')
            start_date_var.set('')
            end_date_var.set('')
            actor_var.set('')
            entity_type_var.set('all')
            search_var.set('')
            page_var.set(0)
            reload_tree()

        holder = tk.Frame(frame, bg=self.theme['panel'])
        holder.pack(fill='both', expand=True)
        tree = self._create_tree(holder, ('Thời gian', 'User', 'Hành động', 'Đối tượng', 'ID', 'Chi tiết'), (150, 70, 110, 140, 60, 520))
        self.audit_tree = tree

        def reload_tree():
            page = max(0, page_var.get())
            page_label.configure(text=f"Trang {page + 1}")
            for item in tree.get_children():
                tree.delete(item)
            sd = start_date_var.get().strip() or None
            ed = end_date_var.get().strip() or None
            actor = actor_var.get().strip() or None
            entity_type = entity_type_var.get() if entity_type_var.get() != 'all' else None
            search_text = search_var.get().strip() or None
            rows = self.audit_mgr.read_report(
                50, action_var.get(), page * 50,
                start_date=sd, end_date=ed, actor_id=actor,
                entity_type=entity_type, search_text=search_text,
            )
            counter = {}
            count = 0
            for row in rows:
                count += 1
                action_name = row['action'] or 'UNKNOWN'
                counter[action_name] = counter.get(action_name, 0) + 1
                detail = str(row['detail'] or '')
                if len(detail) > 140:
                    detail = detail[:137] + '...'
                tree.insert('', 'end', values=(row['created_at'], row['actor_id'], row['action'], row['entity_type'], row['entity_id'], detail))
            results_label.configure(text=f"Hiển thị {count} bản ghi")
            action_summary = ', '.join(f"{name}: {value}" for name, value in counter.items()) or 'Không có dữ liệu.'
            summary_var.set(f"Tóm tắt trang: {action_summary}")

        def move_page(delta):
            page_var.set(max(0, page_var.get() + delta))
            reload_tree()

        def export_audit():
            try:
                sd = start_date_var.get().strip() or None
                ed = end_date_var.get().strip() or None
                actor = actor_var.get().strip() or None
                entity_type = entity_type_var.get() if entity_type_var.get() != 'all' else None
                search_text = search_var.get().strip() or None
                rows = self.audit_mgr.read_report(
                    10000, action_var.get(), 0,
                    start_date=sd, end_date=ed, actor_id=actor,
                    entity_type=entity_type, search_text=search_text,
                )
                file_path = filedialog.asksaveasfilename(
                    title="Xuất Audit log",
                    defaultextension='.xlsx',
                    filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                    initialfile=f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                )
                if not file_path:
                    return
                ExcelExporter.export_audit_log(rows, file_path)
                messagebox.showinfo("Audit log", f"Đã xuất Excel:\n{file_path}")
            except Exception as exc:
                messagebox.showerror("Audit log", str(exc))

        def show_detail():
            if not tree.selection():
                messagebox.showwarning("Audit", "Chọn một dòng audit.")
                return
            values = tree.item(tree.selection()[0], 'values')
            win = tk.Toplevel(self.root)
            win.title("Chi tiết audit")
            win.geometry("720x420")
            win.configure(bg=self.theme['bg'])
            text = tk.Text(win, wrap='word', font=('Consolas', 10), bg='white', fg=self.theme['TEXT_PRIMARY'])
            text.pack(fill='both', expand=True, padx=12, pady=12)
            text.insert('1.0', "\n".join(f"{label}: {value}" for label, value in zip(('Thời gian', 'User', 'Hành động', 'Đối tượng', 'ID', 'Chi tiết'), values)))
            text.config(state='disabled')

        create_modern_button(toolbar, "Lọc", lambda: (page_var.set(0), reload_tree()), variant='primary', padx=12, pady=7).pack(side='left')
        create_modern_button(toolbar, "Xóa bộ lọc", clear_filters, variant='outline', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(toolbar, "Trước", lambda: move_page(-1), variant='outline', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(toolbar, "Sau", lambda: move_page(1), variant='outline', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(toolbar, "Xem chi tiết", show_detail, variant='outline', padx=12, pady=7).pack(side='left', padx=6)
        create_modern_button(toolbar, "Xuất Excel", export_audit, variant='success', padx=12, pady=7).pack(side='left', padx=6)
        tree.bind('<Double-1>', lambda _e: show_detail())
        reload_tree()

    def _render_fixed_asset_tab(self, notebook):
        frame = tk.Frame(notebook, bg=self.theme['panel'])
        notebook.add(frame, text='TSCĐ')

        toolbar = tk.Frame(frame, bg=self.theme['panel'])
        toolbar.pack(fill='x', padx=12, pady=(12, 8))
        tk.Label(toolbar, text="Kỳ khấu hao", bg=self.theme['panel'],
                 fg=self.theme['TEXT_MUTED'], font=('Segoe UI', 10, 'bold')).pack(side='left')
        period_var = tk.StringVar(value=datetime.now().strftime('%Y-%m'))
        ttk.Entry(toolbar, textvariable=period_var, width=12).pack(side='left', padx=(8, 10))

        body = tk.Frame(frame, bg=self.theme['panel'])
        body.pack(fill='both', expand=True, padx=0, pady=0)
        columns = ('Mã TS', 'Tên tài sản', 'Nguyên giá', 'Đã KH', 'Giá trị còn lại', 'TT')
        widths = (90, 240, 130, 130, 140, 90)
        tree = self._create_tree(body, columns, widths)

        def reload_tree():
            for item in tree.get_children():
                tree.delete(item)
            rows = self.extension_report_mgr.fixed_asset_report()
            for row in rows:
                tree.insert('', 'end', values=(
                    row['asset_code'], row['asset_name'],
                    f"{row['acquisition_cost'] or 0:,.0f}",
                    f"{row['accumulated_depreciation'] or 0:,.0f}",
                    f"{row['net_value'] or 0:,.0f}", row['status'],
                ))
            if not rows:
                tree.insert('', 'end', values=('', 'Chưa có tài sản cố định', '', '', '', ''))

        def run_depreciation():
            period = period_var.get().strip()
            if not re.match(r'^\d{4}-\d{2}$', period):
                messagebox.showwarning("Khấu hao", "Kỳ khấu hao cần có dạng YYYY-MM.")
                return
            created = self.extension_report_mgr.run_straight_line_depreciation(period)
            messagebox.showinfo("Khấu hao", f"Đã tạo {created} dòng khấu hao cho kỳ {period}.")
            reload_tree()

        def add_asset():
            dialog = SimpleCatalogDialog(self.root, "Thêm tài sản cố định", [
                ('asset_code', 'Mã tài sản:', ''),
                ('asset_name', 'Tên tài sản:', ''),
                ('asset_type', 'Loại tài sản:', 'Máy thi công'),
                ('acquisition_date', 'Ngày mua (YYYY-MM-DD):', datetime.now().strftime('%Y-%m-%d')),
                ('acquisition_cost', 'Nguyên giá:', '0'),
                ('useful_life_months', 'Thời gian KH (tháng):', '60'),
                ('salvage_value', 'Giá trị thu hồi:', '0'),
                ('project_id', 'ID dự án (trống nếu dùng chung):', ''),
                ('status', 'Trạng thái:', 'active'),
                ('notes', 'Ghi chú:', ''),
            ])
            self.root.wait_window(dialog)
            if dialog.result:
                try:
                    data = dict(dialog.result)
                    for key in ('acquisition_cost', 'salvage_value'):
                        data[key] = parse_number(data.get(key))
                    data['useful_life_months'] = parse_number(data.get('useful_life_months'))
                    data['project_id'] = int(data['project_id']) if str(data.get('project_id') or '').strip() else None
                    self.extension_report_mgr.add_fixed_asset(data)
                    reload_tree()
                except Exception as exc:
                    messagebox.showerror("TSCĐ", str(exc))

        create_modern_button(toolbar, "Thêm TSCĐ", add_asset,
                             variant='outline', padx=12, pady=7).pack(side='left', padx=(0, 6))
        create_modern_button(toolbar, "Chạy khấu hao", run_depreciation,
                             variant='primary', padx=12, pady=7).pack(side='left', padx=(0, 6))
        create_modern_button(toolbar, "Làm mới", reload_tree,
                             variant='outline', padx=12, pady=7).pack(side='left')
        reload_tree()

    def _render_ar_ap_tab(self, notebook):
        frame = tk.Frame(notebook, bg=self.theme['panel'])
        notebook.add(frame, text='Công nợ tuổi nợ')

        summary = tk.Frame(frame, bg=self.theme['panel'])
        summary.pack(fill='x', padx=8, pady=(10, 4))
        aging = self.extension_report_mgr.ar_ap_aging()
        totals = {'0-30': 0, '31-60': 0, '61-90': 0, '>90': 0}
        for row in aging:
            for bucket in totals:
                totals[bucket] += float(row[bucket] or 0)
        for label, value, color in [
            ('0-30 ngày', f"{totals['0-30']:,.0f}", self.theme['success']),
            ('31-60 ngày', f"{totals['31-60']:,.0f}", self.theme['info']),
            ('61-90 ngày', f"{totals['61-90']:,.0f}", self.theme['warning']),
            ('Trên 90 ngày', f"{totals['>90']:,.0f}", self.theme['danger']),
        ]:
            self._create_stat_card(summary, label, value, color)

        toolbar = tk.Frame(frame, bg=self.theme['panel'])
        toolbar.pack(fill='x', padx=12, pady=(6, 8))
        tk.Label(toolbar, text="Trạng thái", bg=self.theme['panel'],
                 fg=self.theme['TEXT_MUTED'], font=('Segoe UI', 10, 'bold')).pack(side='left')
        status_var = tk.StringVar(value='open')
        ttk.Combobox(toolbar, textvariable=status_var, values=('open', 'closed', 'all'),
                     width=10, state='readonly').pack(side='left', padx=(8, 10))

        body = tk.Frame(frame, bg=self.theme['panel'])
        body.pack(fill='both', expand=True)
        columns = ('ID', 'Loại', 'Đối tác', 'DA', 'Hạn', 'Phải thu/trả', 'Đã thanh toán', 'Còn lại', 'TT', 'Nguồn', 'Ghi chú')
        tree = self._create_tree(body, columns, (50, 90, 180, 80, 95, 120, 120, 120, 80, 100, 220))

        def reload_tree():
            for item in tree.get_children():
                tree.delete(item)
            rows = self.extension_report_mgr.ar_ap_items(status_var.get())
            for row in rows:
                tree.insert('', 'end', values=(
                    row['id'],
                    'Phải thu' if row['partner_type'] == 'customer' else 'Phải trả',
                    row['partner_name'], row['project_code'], row['due_date'],
                    f"{row['amount']:,.0f}", f"{row['paid_amount']:,.0f}",
                    f"{row['outstanding']:,.0f}", row['status'],
                    f"{row['source_type']} {row['source_id']}".strip(), row['notes'],
                ))
            if not rows:
                tree.insert('', 'end', values=('', '', 'Chưa có công nợ phù hợp', '', '', '', '', '', '', '', ''))

        def settle_selected():
            if not tree.selection():
                messagebox.showwarning("Công nợ", "Chọn một khoản công nợ cần ghi nhận thanh toán.")
                return
            values = tree.item(tree.selection()[0], 'values')
            if not values or not values[0]:
                return
            try:
                dialog = SimpleCatalogDialog(self.root, "Ghi nhận thanh toán", [
                    ('amount', 'Số tiền thanh toán (trống = toàn bộ còn lại):', ''),
                ])
                self.root.wait_window(dialog)
                if not dialog.result:
                    return
                amount_text = str(dialog.result.get('amount') or '').strip()
                pay_amount = None if not amount_text else parse_number(amount_text)
                new_paid, status = self.extension_report_mgr.settle_ar_ap_item(int(values[0]), pay_amount)
                messagebox.showinfo("Công nợ", f"Đã cập nhật thanh toán: {new_paid:,.0f}. Trạng thái: {status}.")
                reload_tree()
            except Exception as exc:
                messagebox.showerror("Công nợ", str(exc))

        def add_item():
            dialog = SimpleCatalogDialog(self.root, "Thêm khoản công nợ", [
                ('partner_type', 'Loại (customer/supplier):', 'customer'),
                ('partner_name', 'Đối tác:', ''),
                ('project_id', 'ID dự án:', ''),
                ('doc_id', 'ID chứng từ:', ''),
                ('due_date', 'Ngày đến hạn (YYYY-MM-DD):', datetime.now().strftime('%Y-%m-%d')),
                ('amount', 'Số tiền:', '0'),
                ('paid_amount', 'Đã thanh toán:', '0'),
                ('status', 'Trạng thái:', 'open'),
                ('notes', 'Ghi chú:', ''),
            ])
            self.root.wait_window(dialog)
            if dialog.result:
                try:
                    data = dict(dialog.result)
                    data['project_id'] = int(data['project_id']) if str(data.get('project_id') or '').strip() else None
                    data['doc_id'] = int(data['doc_id']) if str(data.get('doc_id') or '').strip() else None
                    data['amount'] = parse_number(data.get('amount'))
                    data['paid_amount'] = parse_number(data.get('paid_amount'))
                    self.extension_report_mgr.add_ar_ap_item(data)
                    reload_tree()
                except Exception as exc:
                    messagebox.showerror("Công nợ", str(exc))

        def sync_sources():
            try:
                changed = self.extension_report_mgr.sync_ar_ap_from_sources()
                messagebox.showinfo("Công nợ", f"Đã đồng bộ công nợ từ chứng từ/nghiệm thu. Số dòng xử lý: {changed}.")
                reload_tree()
            except Exception as exc:
                messagebox.showerror("Công nợ", str(exc))

        def export_ar_ap():
            file_path = filedialog.asksaveasfilename(
                defaultextension='.xlsx',
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                initialfile=f"cong_no_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )
            if not file_path:
                return
            try:
                rows = self.extension_report_mgr.ar_ap_items(status_var.get())
                ExcelExporter.export_ar_ap_items(rows, file_path)
                self.audit_mgr.log('ar_ap_items', None, 'EXPORT', actor_id=1, new_value={'file': file_path, 'rows': len(rows)})
                messagebox.showinfo("Công nợ", f"Đã xuất Excel:\n{file_path}")
            except Exception as exc:
                messagebox.showerror("Công nợ", str(exc))

        def open_source():
            if not tree.selection():
                messagebox.showwarning("Công nợ", "Chọn một dòng công nợ.")
                return
            values = tree.item(tree.selection()[0], 'values')
            if not values or not values[0]:
                return
            source = str(values[9] or '').split()
            if not source:
                messagebox.showinfo("Công nợ", "Dòng này được nhập tay, không có nguồn tự động.")
                return
            source_type = source[0]
            source_id = int(source[1]) if len(source) > 1 and str(source[1]).isdigit() else None
            if source_type == 'document' and source_id:
                self._show_documents()
                self.root.after(100, lambda: self._select_tree_row_by_id(getattr(self, 'documents_tree', None), source_id))
            elif source_type == 'billing':
                self._show_contracts()
            else:
                messagebox.showinfo("Công nợ", "Nguồn này chưa có màn mở nhanh.")

        create_modern_button(toolbar, "Thêm công nợ", add_item, variant='outline',
                             padx=12, pady=7).pack(side='left', padx=(0, 6))
        create_modern_button(toolbar, "Đồng bộ từ chứng từ/HĐ", sync_sources, variant='outline',
                             padx=12, pady=7).pack(side='left', padx=(0, 6))
        create_modern_button(toolbar, "Xuất Excel", export_ar_ap, variant='outline',
                             padx=12, pady=7).pack(side='left', padx=(0, 6))
        create_modern_button(toolbar, "Làm mới", reload_tree, variant='outline',
                             padx=12, pady=7).pack(side='left', padx=(0, 6))
        create_modern_button(toolbar, "Mở nguồn", open_source, variant='outline',
                             padx=12, pady=7).pack(side='left', padx=(0, 6))
        create_modern_button(toolbar, "Ghi nhận đã thanh toán", settle_selected, variant='primary',
                             padx=12, pady=7).pack(side='left')
        tree.bind('<Double-1>', lambda _e: open_source())
        reload_tree()

    def _render_simple_report_tab(self, notebook, title, columns, widths, row_provider):
        frame = tk.Frame(notebook, bg=self.theme['panel'])
        notebook.add(frame, text=title)
        header = tk.Frame(frame, bg=self.theme['panel'])
        header.pack(fill='x', padx=12, pady=(12, 8))
        tk.Label(header, text=title, bg=self.theme['panel'], fg=self.theme['TEXT_PRIMARY'],
                 font=('Segoe UI', 11, 'bold')).pack(side='left')
        tree_frame = tk.Frame(frame, bg=self.theme['panel'])
        tree_frame.pack(fill='both', expand=True)
        tree = self._create_tree(tree_frame, columns, widths)
        rows = list(row_provider())
        for row in rows:
            tree.insert('', 'end', values=row)
        if not rows:
            empty = [''] * len(columns)
            if empty:
                empty[min(1, len(empty) - 1)] = 'Chưa có dữ liệu'
            tree.insert('', 'end', values=tuple(empty))

    def _show_global_search(self):
        self._clear_content()
        self._page_title("Tìm kiếm toàn cục", "Tra cứu nhanh chi phí, chứng từ, dự án và file liên quan.")

        toolbar = tk.Frame(self.content_frame, bg=self.theme['bg'])
        toolbar.pack(fill='x', padx=16, pady=(0, 8))
        tk.Label(toolbar, text="Từ khóa", font=('Segoe UI', 10, 'bold'),
                 bg=self.theme['bg'], fg=self.theme['TEXT_MUTED']).pack(side='left')
        self.global_search_var = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.global_search_var, width=42)
        entry.pack(side='left', padx=6)
        create_modern_button(toolbar, "Tìm", self._refresh_global_search,
                             variant='primary', padx=14, pady=7).pack(side='left', padx=4)
        entry.bind('<Return>', lambda _event: self._refresh_global_search())
        self.active_search_entry = entry

        frame = tk.Frame(self.content_frame, bg=self.theme['panel'],
                         highlightbackground=self.theme['line'], highlightthickness=1)
        frame.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        columns = ('Loại', 'ID', 'Ngày', 'Đối tượng', 'Nội dung/Đường dẫn', 'Số tiền', 'Trạng thái')
        self.global_search_tree = ttk.Treeview(frame, columns=columns, show='tree headings')
        for col, width in zip(columns, (90, 60, 130, 180, 460, 120, 100)):
            self.global_search_tree.heading(col, text=col)
            self.global_search_tree.column(col, width=width)
        self.global_search_tree.pack(fill='both', expand=True, padx=10, pady=10)

    def _refresh_global_search(self):
        tree = getattr(self, 'global_search_tree', None)
        if not tree:
            return
        for item in tree.get_children():
            tree.delete(item)
        for row in self.utility_mgr.global_search(self.global_search_var.get().strip()):
            tree.insert('', 'end', values=row)

    def _show_catalogs(self):
        self._clear_content()
        self._page_title("Quản lý danh mục", "Dữ liệu nền dùng chung cho kế toán, công trình, vật tư và thanh toán.")

        toolbar = tk.Frame(self.content_frame, bg=self.theme['bg'])
        toolbar.pack(fill='x', padx=16, pady=(0, 8))
        create_modern_button(toolbar, "Thêm dự án", self._add_project_catalog,
                             variant='primary', padx=12, pady=7).pack(side='left', padx=(0, 6))
        create_modern_button(toolbar, "Loại chi phí", self._add_category_catalog,
                             variant='outline', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(toolbar, "Nhà cung cấp", lambda: self._add_simple_catalog('supplier'),
                             variant='outline', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(toolbar, "Khách hàng", lambda: self._add_simple_catalog('customer'),
                             variant='outline', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(toolbar, "Nhân viên", lambda: self._add_simple_catalog('employee'),
                             variant='outline', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(toolbar, "Thanh toán", lambda: self._add_simple_catalog('payment_method'),
                             variant='outline', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(toolbar, "Sửa mục đã chọn", self._edit_selected_catalog,
                             variant='secondary', padx=12, pady=7).pack(side='right', padx=4)

        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        self.catalog_trees = {}
        self._add_catalog_tab(notebook, 'Dự án', 'projects', ('ID', 'Mã', 'Tên', 'Địa điểm', 'Ngân sách', 'Trạng thái'), (60, 100, 260, 180, 120, 100))
        self._add_catalog_tab(notebook, 'Loại chi phí', 'categories', ('ID', 'Mã', 'Tên', 'Mô tả'), (60, 120, 240, 520))
        self._add_catalog_tab(notebook, 'Nhà cung cấp', 'supplier', ('ID', 'Loại', 'Tên', 'Mô tả', 'Active'), (60, 120, 260, 420, 80))
        self._add_catalog_tab(notebook, 'Khách hàng', 'customer', ('ID', 'Loại', 'Tên', 'Mô tả', 'Active'), (60, 120, 260, 420, 80))
        self._add_catalog_tab(notebook, 'Nhân viên', 'employee', ('ID', 'Loại', 'Tên', 'Mô tả', 'Active'), (60, 120, 260, 420, 80))
        self._add_catalog_tab(notebook, 'Phòng ban', 'department', ('ID', 'Loại', 'Tên', 'Mô tả', 'Active'), (60, 120, 260, 420, 80))
        self._add_catalog_tab(notebook, 'Tiểu mục CP', 'cost_subitem', ('ID', 'Loại', 'Tên', 'Mô tả', 'Active'), (60, 120, 260, 420, 80))
        self._add_catalog_tab(notebook, 'Nhóm CP', 'cost_group', ('ID', 'Loại', 'Tên', 'Mô tả', 'Active'), (60, 120, 260, 420, 80))
        self._add_catalog_tab(notebook, 'Số dư đầu kỳ', 'opening_balance', ('ID', 'Loại', 'Tên', 'Mô tả', 'Active'), (60, 120, 260, 420, 80))
        self._add_catalog_tab(notebook, 'Chủng loại VT', 'item_type', ('ID', 'Loại', 'Tên', 'Mô tả', 'Active'), (60, 120, 260, 420, 80))
        self._add_catalog_tab(notebook, 'Thanh toán', 'payment_method', ('ID', 'Loại', 'Tên', 'Mô tả', 'Active'), (60, 120, 260, 420, 80))
        self._refresh_catalogs()

    def _add_catalog_tab(self, notebook, title, key, columns, widths):
        frame = tk.Frame(notebook, bg=self.theme['panel'])
        notebook.add(frame, text=title)
        tree = ttk.Treeview(frame, columns=columns, show='tree headings')
        self.catalog_trees[key] = tree
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        tree.pack(fill='both', expand=True, padx=8, pady=8)
        tree.bind('<Double-1>', lambda _e: self._edit_catalog_row(key))

    def _create_alert_card(self, parent, title, count, color, bg):
        card = tk.Frame(parent, bg=bg, highlightbackground=color, highlightthickness=1)
        card.pack(side='left', fill='x', expand=True, padx=4)
        tk.Label(card, text=title, bg=bg, fg=color, font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=12, pady=(8, 0))
        tk.Label(card, text=str(count), bg=bg, fg=color, font=('Segoe UI', 20, 'bold')).pack(anchor='w', padx=12, pady=(0, 8))

    def _refresh_catalogs(self):
        if not hasattr(self, 'catalog_trees'):
            return
        loaders = {
            'projects': self.utility_mgr.list_projects,
            'categories': self.utility_mgr.list_categories,
            'supplier': lambda: self.utility_mgr.list_simple_catalog('supplier'),
            'customer': lambda: self.utility_mgr.list_simple_catalog('customer'),
            'employee': lambda: self.utility_mgr.list_simple_catalog('employee'),
            'department': lambda: self.utility_mgr.list_simple_catalog('department'),
            'cost_subitem': lambda: self.utility_mgr.list_simple_catalog('cost_subitem'),
            'cost_group': lambda: self.utility_mgr.list_simple_catalog('cost_group'),
            'opening_balance': lambda: self.utility_mgr.list_simple_catalog('opening_balance'),
            'item_type': lambda: self.utility_mgr.list_simple_catalog('item_type'),
            'payment_method': lambda: self.utility_mgr.list_simple_catalog('payment_method'),
        }
        for key, loader in loaders.items():
            tree = self.catalog_trees.get(key)
            if not tree:
                continue
            for item in tree.get_children():
                tree.delete(item)
            for row in loader():
                tree.insert('', 'end', values=tuple(row))

    def _add_project_catalog(self):
        dialog = SimpleCatalogDialog(self.root, "Thêm dự án", [
            ('code', 'Mã dự án:', ''),
            ('name', 'Tên dự án:', ''),
            ('location', 'Địa điểm:', ''),
            ('budget', 'Ngân sách:', '0'),
            ('status', 'Trạng thái:', 'active'),
        ])
        self.root.wait_window(dialog)
        if dialog.result:
            try:
                self.utility_mgr.save_project(
                    dialog.result['code'], dialog.result['name'],
                    dialog.result['location'], float((dialog.result['budget'] or '0').replace(',', '')),
                    dialog.result['status'] or 'active'
                )
                self._refresh_catalogs()
            except Exception as exc:
                messagebox.showerror("Lỗi", f"Không lưu được dự án: {exc}")

    def _add_category_catalog(self):
        dialog = SimpleCatalogDialog(self.root, "Thêm loại chi phí", [
            ('code', 'Mã loại:', ''),
            ('name', 'Tên loại:', ''),
            ('description', 'Mô tả:', ''),
        ])
        self.root.wait_window(dialog)
        if dialog.result:
            try:
                self.utility_mgr.save_category(dialog.result['code'], dialog.result['name'], dialog.result['description'])
                self._refresh_catalogs()
            except Exception as exc:
                messagebox.showerror("Lỗi", f"Không lưu được loại chi phí: {exc}")

    def _add_simple_catalog(self, catalog_type):
        labels = {
            'supplier': 'Thêm nhà cung cấp',
            'customer': 'Thêm khách hàng',
            'employee': 'Thêm nhân viên',
            'department': 'Thêm phòng ban',
            'cost_subitem': 'Thêm tiểu mục chi phí',
            'cost_group': 'Thêm nhóm chi phí',
            'opening_balance': 'Thêm số dư đầu kỳ',
            'item_type': 'Thêm chủng loại vật tư',
            'payment_method': 'Thêm hình thức thanh toán',
        }
        dialog = SimpleCatalogDialog(self.root, labels.get(catalog_type, 'Thêm danh mục'))
        self.root.wait_window(dialog)
        if dialog.result:
            try:
                self.utility_mgr.save_simple_catalog(catalog_type, dialog.result['name'], dialog.result['description'])
                self._refresh_catalogs()
            except Exception as exc:
                messagebox.showerror("Lỗi", f"Không lưu được danh mục: {exc}")

    def _edit_selected_catalog(self):
        for key, tree in getattr(self, 'catalog_trees', {}).items():
            if tree.selection():
                self._edit_catalog_row(key)
                return
        messagebox.showwarning("Danh mục", "Vui lòng chọn một dòng cần sửa.")

    def _edit_catalog_row(self, key):
        tree = self.catalog_trees.get(key)
        if not tree or not tree.selection():
            return
        values = tree.item(tree.selection()[0], 'values')
        if not values:
            return
        try:
            if key == 'projects':
                dialog = SimpleCatalogDialog(self.root, "Sửa dự án", [
                    ('code', 'Mã dự án:', values[1]),
                    ('name', 'Tên dự án:', values[2]),
                    ('location', 'Địa điểm:', values[3]),
                    ('budget', 'Ngân sách:', values[4]),
                    ('status', 'Trạng thái:', values[5]),
                ])
                self.root.wait_window(dialog)
                if dialog.result:
                    self.utility_mgr.update_project(
                        int(values[0]), dialog.result['code'], dialog.result['name'],
                        dialog.result['location'], parse_number(dialog.result['budget']),
                        dialog.result['status'] or 'active'
                    )
            elif key == 'categories':
                dialog = SimpleCatalogDialog(self.root, "Sửa loại chi phí", [
                    ('code', 'Mã loại:', values[1]),
                    ('name', 'Tên loại:', values[2]),
                    ('description', 'Mô tả:', values[3]),
                ])
                self.root.wait_window(dialog)
                if dialog.result:
                    self.utility_mgr.update_category(
                        int(values[0]), dialog.result['code'],
                        dialog.result['name'], dialog.result['description']
                    )
            else:
                dialog = SimpleCatalogDialog(self.root, "Sửa danh mục", [
                    ('name', 'Tên:', values[2]),
                    ('description', 'Mô tả:', values[3]),
                    ('active', 'Active (1/0):', values[4]),
                ])
                self.root.wait_window(dialog)
                if dialog.result:
                    self.utility_mgr.update_simple_catalog(
                        int(values[0]), dialog.result['name'],
                        dialog.result['description'], dialog.result.get('active') or 1
                    )
            self._refresh_catalogs()
        except Exception as exc:
            messagebox.showerror("Lỗi", f"Không sửa được danh mục: {exc}")

    def _show_compliance(self):
        """Hiển thị danh sách hệ thống quy định và quy trình hồ sơ."""
        self._clear_content()
        self._page_title("Quy định & hồ sơ", "Quy trình chứng từ cần có theo từng nghiệp vụ chi phí.")

        search_frame = tk.Frame(self.content_frame, bg=self.theme['bg'])
        search_frame.pack(fill='x', padx=16, pady=(0, 8))

        tk.Label(search_frame, text="Tra cứu", font=('Segoe UI', 10, 'bold'),
                 bg=self.theme['bg'], fg=self.theme['TEXT_MUTED']).pack(side='left', padx=(0, 5))
        self.compliance_search_var = tk.StringVar()
        compliance_entry = ttk.Entry(search_frame, textvariable=self.compliance_search_var, width=35)
        compliance_entry.pack(side='left', padx=5)
        compliance_entry.bind('<Return>', lambda _e: self._refresh_compliance_table())
        self.active_search_entry = compliance_entry
        create_modern_button(search_frame, "Tìm", self._refresh_compliance_table,
                             variant='primary', padx=14, pady=7).pack(side='left', padx=5)

        rules_frame = tk.Frame(self.content_frame, bg=self.theme['panel'],
                               highlightbackground=self.theme['line'], highlightthickness=1)
        rules_frame.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        columns = ('ID', 'Mã', 'Loại chi phí', 'Nghiệp vụ', 'Quy trình', 'Hồ sơ cần có', 'Cảnh báo')
        tree = ttk.Treeview(rules_frame, columns=columns, show='tree headings')
        self.compliance_tree = tree
        widths = (50, 110, 140, 160, 160, 360, 260)
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(rules_frame, orient='vertical', command=tree.yview)
        x_scroll = ttk.Scrollbar(rules_frame, orient='horizontal', command=tree.xview)
        tree.configure(yscroll=scrollbar.set, xscroll=x_scroll.set)
        rules_frame.rowconfigure(0, weight=1)
        rules_frame.columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky='nsew', padx=(10, 0), pady=(10, 0))
        scrollbar.grid(row=0, column=1, sticky='ns', padx=(0, 10), pady=(10, 0))
        x_scroll.grid(row=1, column=0, sticky='ew', padx=(10, 0), pady=(0, 10))
        self._refresh_compliance_table()

    def _refresh_compliance_table(self):
        tree = getattr(self, 'compliance_tree', None)
        if not tree:
            return
        for item in tree.get_children():
            tree.delete(item)
        keyword = self.compliance_search_var.get().strip() if hasattr(self, 'compliance_search_var') else None
        for rule in self.compliance_mgr.get_rules(keyword):
            tree.insert('', 'end', values=(
                rule[0], rule[1], rule[2], rule[3], rule[4], rule[5], rule[6]
            ))

    def _show_accounts(self):
        """Hiển thị hệ thống tài khoản kế toán."""
        self._clear_content()
        self._page_title("Hệ thống tài khoản", "Danh mục tài khoản kế toán, tiểu mục và cấu trúc hạch toán.")

        search_frame = tk.Frame(self.content_frame, bg=self.theme['bg'])
        search_frame.pack(fill='x', padx=16, pady=(0, 8))

        tk.Label(search_frame, text="Tra cứu tài khoản", font=('Segoe UI', 10, 'bold'),
                 bg=self.theme['bg'], fg=self.theme['TEXT_MUTED']).pack(side='left', padx=(0, 5))
        self.account_search_var = tk.StringVar()
        account_entry = ttk.Entry(search_frame, textvariable=self.account_search_var, width=30)
        account_entry.pack(side='left', padx=5)
        account_entry.bind('<Return>', lambda _e: self._refresh_accounts_table())
        self.active_search_entry = account_entry
        create_modern_button(search_frame, "Tìm", self._refresh_accounts_table,
                             variant='primary', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(search_frame, "Thêm tiểu mục", self._add_account_subitem,
                             variant='outline', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(search_frame, "Import Excel", self._import_accounts_excel,
                             variant='outline', padx=12, pady=7).pack(side='left', padx=4)
        create_modern_button(search_frame, "Export Excel", self._export_accounts_excel,
                             variant='outline', padx=12, pady=7).pack(side='left', padx=4)

        accounts_frame = tk.Frame(self.content_frame, bg=self.theme['panel'],
                                  highlightbackground=self.theme['line'], highlightthickness=1)
        accounts_frame.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        columns = ('Số hiệu', 'Tên tài khoản', 'Loại', 'Cấp', 'Tài khoản cha', 'Mô tả')
        tree = ttk.Treeview(accounts_frame, columns=columns, show='tree headings')
        self.accounts_tree = tree
        widths = (80, 240, 130, 60, 100, 420)
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(accounts_frame, orient='vertical', command=tree.yview)
        x_scroll = ttk.Scrollbar(accounts_frame, orient='horizontal', command=tree.xview)
        tree.configure(yscroll=scrollbar.set, xscroll=x_scroll.set)
        accounts_frame.rowconfigure(0, weight=1)
        accounts_frame.columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky='nsew', padx=(10, 0), pady=(10, 0))
        scrollbar.grid(row=0, column=1, sticky='ns', padx=(0, 10), pady=(10, 0))
        x_scroll.grid(row=1, column=0, sticky='ew', padx=(10, 0), pady=(0, 10))
        self._refresh_accounts_table()

    def _refresh_accounts_table(self):
        tree = getattr(self, 'accounts_tree', None)
        if not tree:
            return
        for item in tree.get_children():
            tree.delete(item)
        keyword = self.account_search_var.get().strip() if hasattr(self, 'account_search_var') else None
        for account in self.account_catalog_mgr.get_accounts(keyword):
            tree.insert('', 'end', values=(
                account[0], account[1], account[2], account[3], account[4], account[6]
            ))

    def _add_account_subitem(self):
        dialog = AccountDialog(self.root, self.account_catalog_mgr)
        self.root.wait_window(dialog)
        if dialog.result:
            try:
                self.account_catalog_mgr.add_account(
                    dialog.result['account_code'],
                    dialog.result['account_name'],
                    dialog.result['account_type'],
                    dialog.result['parent_code'],
                    dialog.result['description'],
                )
                messagebox.showinfo("Thành công", "Đã thêm tài khoản/tiểu mục.")
                self._refresh_accounts_table()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi thêm tài khoản: {str(e)}")

    def _import_accounts_excel(self):
        file_path = filedialog.askopenfilename(
            title="Chọn file Excel tài khoản",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if not file_path:
            return
        try:
            results = ExcelImporter.import_accounts_from_excel(file_path, self.account_catalog_mgr)
            messagebox.showinfo(
                "Kết quả import",
                f"Thành công: {results['success']} dòng\nLỗi: {results['failed']} dòng\n"
                + "\n".join(results['errors'][:5])
            )
            self._refresh_accounts_table()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi import tài khoản: {str(e)}")

    def _export_accounts_excel(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=f"accounts_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
        if not file_path:
            return
        try:
            ExcelExporter.export_accounts(self.account_catalog_mgr.get_accounts(), file_path)
            messagebox.showinfo("Thành công", f"Đã xuất Excel:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi xuất tài khoản: {str(e)}")

    def _show_knowledge_base(self):
        """Hiển thị kho biểu mẫu, hồ sơ, quy trình, định mức và nhắc việc."""
        self._clear_content()

        title = tk.Label(self.content_frame, text="📁 KHO BIỂU MẪU - HỒ SƠ - QUY TRÌNH VẬN HÀNH",
                        font=('Arial', 14, 'bold'), bg='#f0f4f8', fg='#1a56a5')
        title.pack(padx=15, pady=15, anchor='w')

        toolbar = tk.Frame(self.content_frame, bg='#f0f4f8')
        toolbar.pack(fill='x', padx=15, pady=5)

        tk.Label(toolbar, text="Tra cứu:", font=('Arial', 10), bg='#f0f4f8').pack(side='left')
        self.knowledge_search_var = tk.StringVar()
        tk.Entry(toolbar, textvariable=self.knowledge_search_var, font=('Arial', 10), width=35).pack(side='left', padx=6)
        tk.Button(toolbar, text="Tìm", bg='#3498db', fg='white', font=('Arial', 10),
                 padx=14, pady=6, cursor='hand2', command=self._refresh_knowledge_tabs).pack(side='left', padx=4)
        tk.Button(toolbar, text="Mở thư mục mẫu", bg='#16a085', fg='white', font=('Arial', 10),
                 padx=14, pady=6, cursor='hand2', command=self._open_templates_folder).pack(side='left', padx=4)
        tk.Button(toolbar, text="Mở file mẫu đang chọn", bg='#2980b9', fg='white', font=('Arial', 10),
                 padx=14, pady=6, cursor='hand2', command=self._open_selected_template_file).pack(side='left', padx=4)
        tk.Button(toolbar, text="Cập nhật từ Excel mẫu", bg='#8e44ad', fg='white', font=('Arial', 10),
                 padx=14, pady=6, cursor='hand2', command=self._reload_template_data).pack(side='left', padx=4)
        tk.Button(toolbar, text="Thêm trường dữ liệu", bg='#c0392b', fg='white', font=('Arial', 10),
                 padx=14, pady=6, cursor='hand2', command=self._add_template_field).pack(side='left', padx=4)
        tk.Button(toolbar, text="Thiết lập vị trí điền", bg='#D68910', fg='white', font=('Arial', 10),
                 padx=14, pady=6, cursor='hand2', command=self._add_template_mapping).pack(side='left', padx=4)
        tk.Button(toolbar, text="Tạo biểu mẫu để in", bg='#2E7D32', fg='white', font=('Arial', 10),
                 padx=14, pady=6, cursor='hand2', command=self._render_selected_template).pack(side='left', padx=4)

        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True, padx=15, pady=(5, 15))
        self.knowledge_notebook = notebook
        self.knowledge_trees = {}

        self._add_knowledge_tab(
            notebook, 'Biểu mẫu', 'forms',
            ('ID', 'Mã BM', 'Tên biểu mẫu', 'Áp dụng', 'Dùng khi nào', 'Chữ ký', 'Nơi lưu', 'Cách lưu', 'Ghi chú'),
            (50, 120, 260, 100, 260, 260, 100, 120, 260)
        )
        self._add_knowledge_tab(
            notebook, 'Hồ sơ/chứng từ', 'requirements',
            ('ID', 'Mã', 'Nghiệp vụ/chi phí', 'Nhóm', 'Loại HS', 'Áp dụng', 'Chứng từ bắt buộc', 'Bổ sung', 'Chữ ký', 'Deadline', 'Biểu mẫu', 'Cảnh báo'),
            (50, 70, 260, 120, 100, 90, 360, 240, 240, 140, 140, 240)
        )
        self._add_knowledge_tab(
            notebook, 'Quy trình', 'processes',
            ('ID', 'Quy trình', 'Bước', 'Trách nhiệm', 'Nội dung', 'Thời gian', 'Biểu mẫu/CT', 'Lưu ý'),
            (50, 240, 60, 160, 420, 130, 150, 260)
        )
        self._add_knowledge_tab(
            notebook, 'Định mức', 'limits',
            ('ID', 'Nhóm định mức', 'Khoản mục', 'Giá trị 1', 'Giá trị 2', 'Giá trị 3', 'Giá trị 4', 'Ghi chú'),
            (50, 240, 220, 120, 120, 120, 120, 260)
        )
        self._add_knowledge_tab(
            notebook, 'Nhắc việc', 'tasks',
            ('ID', 'Thời gian', 'Loại CV', 'Nội dung', 'Người thực hiện', 'Người duyệt', 'Biểu mẫu', 'Ưu tiên', 'Trạng thái', 'Ghi chú'),
            (50, 120, 120, 320, 140, 120, 120, 90, 90, 220)
        )

        self._add_knowledge_tab(
            notebook, 'Trường dữ liệu mẫu', 'fields',
            ('ID', 'Mã BM', 'Tên biểu mẫu', 'Mã trường', 'Tên trường', 'Kiểu', 'Bắt buộc', 'Mặc định', 'Thứ tự', 'Ghi chú'),
            (50, 100, 240, 130, 220, 90, 80, 160, 70, 240)
        )
        self._add_knowledge_tab(
            notebook, 'Vị trí điền dữ liệu', 'mappings',
            ('ID', 'Mã BM', 'Tên biểu mẫu', 'Sheet', 'Mã trường', 'Ô Excel', 'Chế độ dòng'),
            (50, 120, 260, 160, 140, 90, 110)
        )

        self._refresh_knowledge_tabs()

    def _add_knowledge_tab(self, notebook, title, key, columns, widths):
        frame = tk.Frame(notebook, bg='#f0f4f8')
        notebook.add(frame, text=title)

        tree = ttk.Treeview(frame, columns=columns, show='tree headings')
        self.knowledge_trees[key] = tree

        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width)

        y_scroll = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        x_scroll = ttk.Scrollbar(frame, orient='horizontal', command=tree.xview)
        tree.configure(yscroll=y_scroll.set, xscroll=x_scroll.set)

        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky='nsew')
        y_scroll.grid(row=0, column=1, sticky='ns')
        x_scroll.grid(row=1, column=0, sticky='ew')

    def _refresh_knowledge_tabs(self):
        keyword = self.knowledge_search_var.get().strip() if hasattr(self, 'knowledge_search_var') else None
        loaders = {
            'forms': self.knowledge_mgr.search_forms,
            'requirements': self.knowledge_mgr.search_requirements,
            'processes': self.knowledge_mgr.search_processes,
            'limits': self.knowledge_mgr.search_limits,
            'tasks': self.knowledge_mgr.search_tasks,
            'fields': self.knowledge_mgr.search_template_fields,
            'mappings': self.knowledge_mgr.search_field_mappings,
        }

        for key, loader in loaders.items():
            tree = self.knowledge_trees.get(key)
            if not tree:
                continue
            for item in tree.get_children():
                tree.delete(item)
            for row in loader(keyword):
                if key == 'forms':
                    values = (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8])
                elif key == 'requirements':
                    values = (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[10], row[11], row[13])
                elif key == 'processes':
                    values = (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])
                elif key == 'limits':
                    values = (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])
                elif key == 'tasks':
                    values = (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9])
                elif key == 'fields':
                    values = (row[0], row[1], row[2], row[3], row[4], row[5], 'Có' if row[6] else 'Không', row[7], row[8], row[9])
                else:
                    values = (row[0], row[1], row[2], row[3], row[4], row[5], row[6])
                tree.insert('', 'end', values=values)

    def _add_template_field(self):
        dialog = TemplateFieldDialog(self.root, self.knowledge_mgr)
        self.root.wait_window(dialog)
        if dialog.result:
            try:
                self.knowledge_mgr.add_template_field(
                    dialog.result['form_template_id'],
                    dialog.result['field_key'],
                    dialog.result['field_label'],
                    dialog.result['field_type'],
                    dialog.result['required'],
                    dialog.result['default_value'],
                    dialog.result['display_order'],
                    dialog.result['notes'],
                )
                messagebox.showinfo("Thành công", "Đã thêm/cập nhật trường dữ liệu cho biểu mẫu.")
                self._refresh_knowledge_tabs()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không lưu được trường dữ liệu: {str(e)}")

    def _add_template_mapping(self):
        dialog = TemplateMappingDialog(self.root, self.knowledge_mgr)
        self.root.wait_window(dialog)
        if dialog.result:
            try:
                self.knowledge_mgr.add_field_mapping(
                    dialog.result['form_template_id'],
                    dialog.result['field_key'],
                    dialog.result['cell_address'],
                    dialog.result['row_mode'],
                )
                messagebox.showinfo("Thành công", "Đã lưu vị trí điền dữ liệu cho biểu mẫu.")
                self._refresh_knowledge_tabs()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không lưu được vị trí điền dữ liệu: {str(e)}")

    def _get_selected_template_id(self):
        tree = self.knowledge_trees.get('forms') if hasattr(self, 'knowledge_trees') else None
        if not tree or not tree.selection():
            return None
        values = tree.item(tree.selection()[0], 'values')
        return int(values[0]) if values else None

    def _render_selected_template(self):
        form_id = self._get_selected_template_id()
        dialog = RenderTemplateDialog(self.root, self.template_renderer, form_id=form_id)
        self.root.wait_window(dialog)
        if dialog.result:
            output_path = dialog.result['output_path']
            if messagebox.askyesno("Đã tạo biểu mẫu", f"Đã tạo biểu mẫu:\n{output_path}\n\nBạn có muốn mở file để in không?"):
                try:
                    os.startfile(os.path.abspath(output_path))
                except Exception as e:
                    messagebox.showerror("Lỗi", f"Không mở được biểu mẫu: {str(e)}")

    def _open_templates_folder(self):
        """Mở thư mục chứa file Excel mẫu để người dùng tùy chỉnh."""
        template_path = os.path.abspath('templates')
        try:
            os.startfile(template_path)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không mở được thư mục mẫu: {str(e)}")

    def _open_selected_template_file(self):
        """Mở file Excel nguồn của biểu mẫu đang chọn."""
        tree = self.knowledge_trees.get('forms') if hasattr(self, 'knowledge_trees') else None
        if not tree or not tree.selection():
            messagebox.showwarning("Thông báo", "Vui lòng chọn một dòng trong tab Biểu mẫu.")
            return
        values = tree.item(tree.selection()[0], 'values')
        if not values:
            return
        form_code = values[1]
        cursor = self.knowledge_mgr.conn.cursor()
        cursor.execute('''
            SELECT file_path FROM form_templates
            WHERE form_code = ? AND active = 1
            ORDER BY id LIMIT 1
        ''', (form_code,))
        row = cursor.fetchone()
        if not row or not row['file_path']:
            messagebox.showinfo("Thông báo", "Không tìm thấy file mẫu liên kết.")
            return
        try:
            os.startfile(os.path.abspath(row['file_path']))
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không mở được file mẫu:\n{row['file_path']}\n\n{str(e)}")

    def _reload_template_data(self):
        """Đọc lại dữ liệu tra cứu từ các workbook Excel trong thư mục templates."""
        try:
            from database import init_database
            init_database()
            self.knowledge_mgr = _LazyManager('modules.knowledge_base', 'KnowledgeBaseManager')
            messagebox.showinfo("Thành công", "Đã cập nhật dữ liệu từ các file Excel mẫu trong thư mục templates.")
            self._refresh_knowledge_tabs()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi cập nhật dữ liệu mẫu: {str(e)}")

    def _show_materials(self):
        """Hiển thị trang Quản lý vật tư."""
        self._clear_content()

        title = tk.Label(self.content_frame, text="📦 QUẢN LÝ VẬT TƯ",
                        font=('Arial', 14, 'bold'), bg='#f0f4f8', fg='#1a56a5')
        title.pack(padx=15, pady=15, anchor='w')

        # Frame nút chức năng
        button_frame = tk.Frame(self.content_frame, bg='#f0f4f8')
        button_frame.pack(fill='x', padx=15, pady=5)

        tk.Button(button_frame, text="➕ Thêm vật tư", bg='#27ae60', fg='white',
                 font=('Arial', 10), padx=15, pady=8, cursor='hand2',
                 command=self._add_material).pack(side='left', padx=5)

        tk.Button(button_frame, text="📥 Nhập kho", bg='#3498db', fg='white',
                 font=('Arial', 10), padx=15, pady=8, cursor='hand2',
                 command=self._import_inventory).pack(side='left', padx=5)

        tk.Button(button_frame, text="📤 Xuất kho", bg='#2980b9', fg='white',
                 font=('Arial', 10), padx=15, pady=8, cursor='hand2',
                 command=self._export_inventory).pack(side='left', padx=5)

        tk.Button(button_frame, text="📥 Import Excel", bg='#8e44ad', fg='white',
                 font=('Arial', 10), padx=15, pady=8, cursor='hand2',
                 command=self._import_materials_excel).pack(side='left', padx=5)

        tk.Button(button_frame, text="📤 Export Excel", bg='#f39c12', fg='white',
                 font=('Arial', 10), padx=15, pady=8, cursor='hand2',
                 command=self._export_materials_excel).pack(side='left', padx=5)

        # Bảng vật tư
        materials_frame = tk.LabelFrame(self.content_frame, text="  Danh sách vật tư  ",
                                       font=('Arial', 10, 'bold'), bg='#f0f4f8',
                                       fg='#1a56a5', padx=10, pady=10)
        materials_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        self._show_materials_table(materials_frame)

        history_frame = tk.LabelFrame(self.content_frame, text="  Lịch sử nhập/xuất kho  ",
                                      font=('Arial', 10, 'bold'), bg='#f0f4f8',
                                      fg='#1a56a5', padx=10, pady=10)
        history_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        self._show_inventory_history(history_frame)

    def _show_materials_table(self, parent):
        """Hiển thị bảng vật tư."""
        materials = self.material_mgr.get_all_materials()

        columns = ('ID', 'Mã', 'Tên vật tư', 'Đơn vị', 'Tồn kho', 'Đơn giá', 'Danh mục', 'Trạng thái')
        tree = ttk.Treeview(parent, columns=columns, show='tree headings')
        self.materials_tree = tree

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=90)

        for mat in materials:
            tree.insert('', 'end', values=mat)

        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        tree.configure(yscroll=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def _show_inventory_history(self, parent):
        history = self.material_mgr.get_inventory_history(limit=50)
        columns = ('ID', 'Mã VT', 'Tên vật tư', 'Loại', 'Số lượng', 'Ngày', 'Dự án', 'Ghi chú')
        tree = ttk.Treeview(parent, columns=columns, height=7, show='tree headings')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)

        type_names = {'import': 'Nhập kho', 'export': 'Xuất kho'}
        for row in history:
            tree.insert('', 'end', values=(
                row[0], row[1], row[2], type_names.get(row[3], row[3]),
                row[4], row[5], row[6] or '', row[7] or ''
            ))
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def _add_material(self):
        dialog = MaterialDialog(self.root)
        self.root.wait_window(dialog)
        if dialog.result:
            try:
                self.material_mgr.add_material(
                    dialog.result['code'], dialog.result['name'], dialog.result['unit'],
                    dialog.result['unit_price'], dialog.result['category'], dialog.result['supplier']
                )
                messagebox.showinfo("Thành công", "Đã thêm vật tư.")
                self._show_materials()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi thêm vật tư: {str(e)}")

    def _run_inventory_transaction(self, transaction_type):
        if not self.material_mgr.get_material_choices():
            messagebox.showwarning("Thông báo", "Chưa có vật tư. Vui lòng thêm vật tư trước.")
            return
        dialog = InventoryTransactionDialog(self.root, self.material_mgr, transaction_type)
        self.root.wait_window(dialog)
        if dialog.result:
            try:
                self.material_mgr.add_inventory_transaction(
                    dialog.result['material_id'], dialog.result['transaction_type'],
                    dialog.result['quantity'], dialog.result['project_id'],
                    dialog.result['notes'], 1
                )
                messagebox.showinfo("Thành công", "Đã ghi nhận giao dịch kho.")
                self._show_materials()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi ghi nhận kho: {str(e)}")

    def _import_inventory(self):
        self._run_inventory_transaction('import')

    def _export_inventory(self):
        self._run_inventory_transaction('export')

    def _import_materials_excel(self):
        file_path = filedialog.askopenfilename(
            title="Chọn file Excel vật tư",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if not file_path:
            return
        try:
            results = ExcelImporter.import_materials_from_excel(file_path, self.material_mgr)
            messagebox.showinfo(
                "Kết quả import",
                f"Thành công: {results['success']} dòng\nLỗi: {results['failed']} dòng\n"
                + "\n".join(results['errors'][:5])
            )
            self._show_materials()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi import vật tư: {str(e)}")

    def _export_materials_excel(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile=f"materials_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
        if not file_path:
            return
        try:
            ExcelExporter.export_materials(self.material_mgr.get_all_materials(), file_path)
            messagebox.showinfo("Thành công", f"Đã xuất Excel:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi xuất vật tư: {str(e)}")

    def _show_construction(self):
        """Hiển thị phân hệ công trường xây dựng."""
        self._clear_content()
        self._page_title(
            "CÔNG TRƯỜNG XÂY DỰNG",
            "Theo dõi hạng mục, nhật ký, tiến độ, ca máy và an toàn lao động theo từng dự án."
        )

        stats = self.construction_mgr.get_dashboard()
        stats_frame = tk.Frame(self.content_frame, bg=self.theme['bg'])
        stats_frame.pack(fill='x', padx=15, pady=(0, 10))
        items = [
            ("Hạng mục", stats['work_items'], self.theme['primary']),
            ("Mốc đang mở", stats['open_milestones'], self.theme['warning']),
            ("ATLD cần xử lý", stats['open_safety'], self.theme['danger']),
            ("Giờ máy", f"{stats['equipment_hours']:,.1f}", self.theme['success']),
            ("Nhiên liệu", f"{stats['fuel_cost']:,.0f}", self.theme['info']),
        ]
        for title, value, color in items:
            self._create_stat_card(stats_frame, title, str(value), color)

        toolbar = tk.Frame(self.content_frame, bg=self.theme['bg'])
        toolbar.pack(fill='x', padx=15, pady=(0, 8))
        self.construction_search_var = tk.StringVar()
        tk.Label(toolbar, text="Tìm nhanh:", font=('Arial', 10), bg=self.theme['bg']).pack(side='left')
        tk.Entry(toolbar, textvariable=self.construction_search_var, font=('Arial', 10), width=34).pack(side='left', padx=6)
        self._make_button(toolbar, "Tìm", self._refresh_construction_tabs, self.theme['info']).pack(side='left', padx=4)
        self._make_button(toolbar, "Thêm hạng mục", lambda: self._add_construction_record('work_item'), self.theme['success']).pack(side='left', padx=4)
        self._make_button(toolbar, "Thêm nhật ký", lambda: self._add_construction_record('diary'), self.theme['primary']).pack(side='left', padx=4)
        self._make_button(toolbar, "Thêm tiến độ", lambda: self._add_construction_record('milestone'), self.theme['warning']).pack(side='left', padx=4)
        self._make_button(toolbar, "Thêm ca máy", lambda: self._add_construction_record('equipment'), self.theme['info']).pack(side='left', padx=4)
        self._make_button(toolbar, "Thêm ATLD", lambda: self._add_construction_record('safety'), self.theme['danger']).pack(side='left', padx=4)

        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True, padx=15, pady=(0, 15))
        self.construction_trees = {}
        self._add_construction_tab(notebook, 'Hạng mục', 'work_items',
            ('ID', 'Mã DA', 'Dự án', 'Mã HM', 'Hạng mục', 'ĐVT', 'KL dự toán', 'KL đã làm', 'Đơn giá', 'GT dự toán', 'GT hoàn thành', 'CP thực tế', 'Trạng thái', 'Ghi chú'),
            (50, 80, 180, 90, 220, 70, 100, 100, 100, 120, 120, 110, 100, 240))
        self._add_construction_tab(notebook, 'Nhật ký', 'diaries',
            ('ID', 'Ngày', 'Mã DA', 'Dự án', 'Thời tiết', 'Nhân lực', 'Thiết bị', 'Nội dung', 'Vướng mắc', 'Người lập'),
            (50, 95, 80, 180, 120, 150, 150, 320, 260, 120))
        self._add_construction_tab(notebook, 'Tiến độ', 'milestones',
            ('ID', 'Mã DA', 'Dự án', 'Mốc tiến độ', 'Ngày KH', 'Ngày TT', 'Trạng thái', 'Ghi chú'),
            (50, 80, 200, 260, 110, 110, 100, 320))
        self._add_construction_tab(notebook, 'Máy thi công', 'equipment',
            ('ID', 'Ngày', 'Mã DA', 'Dự án', 'Máy/thiết bị', 'Người vận hành', 'Giờ', 'Nhiên liệu', 'Ghi chú'),
            (50, 95, 80, 190, 200, 150, 80, 120, 300))
        self._add_construction_tab(notebook, 'An toàn', 'safety',
            ('ID', 'Ngày', 'Mã DA', 'Dự án', 'Nội dung kiểm tra', 'Kết quả', 'Phụ trách', 'Việc cần xử lý', 'Hạn', 'Trạng thái'),
            (50, 95, 80, 180, 260, 100, 140, 300, 100, 100))
        self._refresh_construction_tabs()

    def _add_construction_tab(self, notebook, title, key, columns, widths):
        frame = tk.Frame(notebook, bg=self.theme['bg'])
        notebook.add(frame, text=title)
        tree = ttk.Treeview(frame, columns=columns, show='tree headings')
        self.construction_trees[key] = tree
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        y_scroll = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        x_scroll = ttk.Scrollbar(frame, orient='horizontal', command=tree.xview)
        tree.configure(yscroll=y_scroll.set, xscroll=x_scroll.set)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky='nsew')
        y_scroll.grid(row=0, column=1, sticky='ns')
        x_scroll.grid(row=1, column=0, sticky='ew')

    def _refresh_construction_tabs(self):
        keyword = self.construction_search_var.get().strip() if hasattr(self, 'construction_search_var') else None
        loaders = {
            'work_items': self.construction_mgr.get_work_items,
            'diaries': self.construction_mgr.get_site_diaries,
            'milestones': self.construction_mgr.get_milestones,
            'equipment': self.construction_mgr.get_equipment_usage,
            'safety': self.construction_mgr.get_safety_checks,
        }
        for key, loader in loaders.items():
            tree = self.construction_trees.get(key)
            if not tree:
                continue
            for item in tree.get_children():
                tree.delete(item)
            for row in loader(keyword):
                tree.insert('', 'end', values=tuple(row))

    def _add_construction_record(self, record_type):
        dialog = ConstructionRecordDialog(self.root, record_type)
        self.root.wait_window(dialog)
        if not dialog.result:
            return
        data = dialog.result
        try:
            if record_type == 'work_item':
                self.construction_mgr.add_work_item(data['project_id'], data['item_code'], data['item_name'], data['unit'], data['planned_quantity'], data['completed_quantity'], data['unit_price'], data['status'], data['notes'])
            elif record_type == 'diary':
                self.construction_mgr.add_site_diary(data['diary_date'], data['project_id'], data['weather'], data['manpower'], data['equipment'], data['work_content'], data['issues'], data['reporter'])
            elif record_type == 'milestone':
                self.construction_mgr.add_milestone(data['project_id'], data['milestone_name'], data['planned_date'], data['actual_date'], data['status'], data['notes'])
            elif record_type == 'equipment':
                self.construction_mgr.add_equipment_usage(data['usage_date'], data['project_id'], data['equipment_name'], data['operator'], data['hours'], data['fuel_cost'], data['notes'])
            else:
                self.construction_mgr.add_safety_check(data['check_date'], data['project_id'], data['check_item'], data['result'], data['responsible'], data['action_required'], data['deadline'], data['status'])
            messagebox.showinfo("Thành công", "Đã lưu dữ liệu công trường.")
            self._show_construction()
        except Exception as exc:
            messagebox.showerror("Lỗi", f"Không lưu được dữ liệu công trường: {exc}")

    def _show_project_accounting(self):
        """Phân hệ kế toán dự án / công trình."""
        self._clear_content()
        self._page_title(
            "KẾ TOÁN DỰ ÁN / CÔNG TRÌNH",
            "Hợp đồng, dự toán chi phí, tập hợp TK 154, doanh thu nghiệm thu và báo cáo quản trị dự án."
        )
        global_dash = self.project_acct_mgr.get_global_dashboard()
        cards = tk.Frame(self.content_frame, bg=self.theme['bg'])
        cards.pack(fill='x', padx=18, pady=8)
        for label, value, color in [
            ("Dự án đang chạy", global_dash['active_projects'], self.theme['success']),
            ("Tổng dự toán", f"{global_dash['total_planned']:,.0f}", self.theme['info']),
            ("Tổng chi phí", f"{global_dash['total_spent']:,.0f}", self.theme['warning']),
            ("Tổng doanh thu", f"{global_dash['total_revenue']:,.0f}", self.theme['primary']),
            ("Lãi/lỗ sơ bộ", f"{global_dash['profit']:,.0f}", self.theme['success'] if global_dash['profit'] >= 0 else self.theme['danger']),
            ("DA vượt 90% NS", global_dash['over_budget'], self.theme['danger']),
        ]:
            self._create_stat_card(cards, label, str(value), color)

        toolbar = tk.Frame(self.content_frame, bg=self.theme['bg'])
        toolbar.pack(fill='x', padx=18, pady=4)
        self.pa_project_var = tk.StringVar()
        projects = [(p['id'], p['code'], p['name']) for p in self.project_acct_mgr.list_projects_active()]
        project_values = [f"{p[0]} - {p[2]}" for p in projects if p[1] != 'CHUNG']
        tk.Label(toolbar, text="Dự án:", bg=self.theme['bg']).pack(side='left')
        pa_combo = ttk.Combobox(toolbar, textvariable=self.pa_project_var, values=project_values, width=36)
        pa_combo.pack(side='left', padx=6)
        if project_values:
            pa_combo.current(0)
        self._make_button(toolbar, "Làm mới", self._show_project_accounting, self.theme['info']).pack(side='left', padx=4)
        self._make_button(toolbar, "Xuất QT06", self._export_qt06_project, self.theme['warning']).pack(side='left', padx=4)

        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True, padx=18, pady=(0, 15))
        pid = self._get_pa_project_id()

        # Tab Tổng quan dự án
        overview_frame = tk.Frame(notebook, bg=self.theme['panel'])
        notebook.add(overview_frame, text='Tổng quan')
        if pid:
            dash = self.project_acct_mgr.get_project_dashboard(pid)
            summary = tk.Frame(overview_frame, bg=self.theme['panel'])
            summary.pack(fill='x', padx=14, pady=14)
            tk.Label(summary, text=f"{dash['project']['code']} - {dash['project']['name']}",
                     font=('Segoe UI', 14, 'bold'), bg=self.theme['panel'], fg=self.theme['text']).pack(anchor='w')
            tk.Label(summary, text=f"Chủ đầu tư: {dash['project'].get('owner_name') or 'Chưa cập nhật'}",
                     font=('Segoe UI', 10), bg=self.theme['panel'], fg=self.theme['muted']).pack(anchor='w', pady=(2, 10))

            metric_grid = tk.Frame(overview_frame, bg=self.theme['panel'])
            metric_grid.pack(fill='x', padx=8, pady=(0, 10))
            metrics = [
                ("Dự toán", f"{dash['planned']:,.0f}", self.theme['primary']),
                ("Đã chi", f"{dash['spent']:,.0f}", self.theme['warning']),
                ("Còn lại", f"{dash['remaining']:,.0f}", self.theme['success'] if dash['remaining'] >= 0 else self.theme['danger']),
                ("Tỷ lệ sử dụng", f"{dash['usage_percent']:.1f}%", self.theme['info']),
                ("Doanh thu", f"{dash['revenue']:,.0f}", self.theme['success']),
                ("Lãi/lỗ", f"{dash['profit']:,.0f}", self.theme['success'] if dash['profit'] >= 0 else self.theme['danger']),
                ("HĐ thi công", f"{dash['contract_value']:,.0f}", self.theme['primary']),
                ("CPSXDD 154", f"{dash['wip_total']:,.0f}", self.theme['warning']),
            ]
            for idx, (label, value, color) in enumerate(metrics):
                tile = tk.Frame(metric_grid, bg='white', highlightbackground=self.theme['line'], highlightthickness=1)
                tile.grid(row=idx // 4, column=idx % 4, sticky='nsew', padx=6, pady=6)
                tk.Frame(tile, bg=color, height=3).pack(fill='x')
                tk.Label(tile, text=label, font=('Segoe UI', 9), bg='white', fg=self.theme['muted']).pack(anchor='w', padx=12, pady=(9, 0))
                tk.Label(tile, text=value, font=('Segoe UI', 13, 'bold'), bg='white', fg=self.theme['text'],
                         wraplength=180, justify='left').pack(anchor='w', padx=12, pady=(2, 10))
            for col in range(4):
                metric_grid.columnconfigure(col, weight=1)

        # Tab Hiệu quả & dòng tiền
        health_frame = tk.Frame(notebook, bg=self.theme['panel'])
        notebook.add(health_frame, text='Hiệu quả & dòng tiền')
        if pid:
            dash = self.project_acct_mgr.get_project_dashboard(pid)
            health_cards = tk.Frame(health_frame, bg=self.theme['panel'])
            health_cards.pack(fill='x', padx=8, pady=(10, 4))
            margin = (dash['profit'] / dash['revenue'] * 100) if dash['revenue'] else 0
            billed_rate = (dash['billed'] / dash['contract_value'] * 100) if dash['contract_value'] else 0
            health_metrics = [
                ("Biên lợi nhuận", f"{margin:.1f}%", self.theme['success'] if margin >= 0 else self.theme['danger']),
                ("Nghiệm thu/HĐ", f"{billed_rate:.1f}%", self.theme['primary']),
                ("Còn ngân sách", f"{dash['remaining']:,.0f}", self.theme['success'] if dash['remaining'] >= 0 else self.theme['danger']),
                ("CPSXDD 154", f"{dash['wip_total']:,.0f}", self.theme['warning']),
            ]
            for label, value, color in health_metrics:
                self._create_stat_card(health_cards, label, value, color)

            insight = tk.Frame(health_frame, bg='white', highlightbackground=self.theme['line'], highlightthickness=1)
            insight.pack(fill='x', padx=14, pady=8)
            notes = []
            if dash['usage_percent'] >= 90:
                notes.append("Chi phí đã dùng trên 90% ngân sách, cần rà soát dự toán còn lại.")
            if dash['contract_value'] and billed_rate < 50 and dash['usage_percent'] > 50:
                notes.append("Tỷ lệ nghiệm thu thấp hơn tốc độ phát sinh chi phí, cần đẩy hồ sơ nghiệm thu.")
            if dash['profit'] < 0:
                notes.append("Lãi/lỗ sơ bộ đang âm, cần kiểm tra chi phí vượt dự toán và doanh thu chưa ghi nhận.")
            if not notes:
                notes.append("Dự án chưa có cảnh báo tài chính lớn theo dữ liệu hiện tại.")
            for note in notes:
                tk.Label(insight, text=f"• {note}", bg='white', fg=self.theme['TEXT_PRIMARY'],
                         font=('Segoe UI', 10), anchor='w', justify='left',
                         wraplength=860).pack(fill='x', padx=12, pady=4)

            flow_cols = ('Ngày', 'Loại', 'Hợp đồng', 'Diễn giải', 'Thu/Chi', 'Số dư dự kiến', 'Cảnh báo')
            flow_tree = self._create_tree(health_frame, flow_cols, (90, 90, 150, 270, 120, 130, 90))
            project_code = dash['project']['code']
            forecast = self.cash_flow_alert_mgr.get_forecast(90)
            events = [e for e in forecast['events'] if str(e.get('project', '')).startswith(project_code)]
            for event in events:
                flow_tree.insert('', 'end', values=(
                    event['date'], event['type'], event['project'], event['description'],
                    f"{event['amount']:,.0f}", f"{event['projected_balance']:,.0f}",
                    "Dưới ngưỡng" if event['alert'] else '',
                ))
            if not events:
                flow_tree.insert('', 'end', values=('', '', '', 'Chưa có dòng tiền dự kiến cho dự án trong 90 ngày', '', '', ''))

        # Tab Dự toán chi phí
        plan_frame = tk.Frame(notebook, bg=self.theme['bg'])
        notebook.add(plan_frame, text='Dự toán CP')
        p_tool = tk.Frame(plan_frame, bg=self.theme['bg'])
        p_tool.pack(fill='x', padx=8, pady=6)
        self._make_button(p_tool, "Thêm dự toán", self._pa_add_cost_plan, self.theme['success']).pack(side='left', padx=4)
        self.pa_plan_tree = self._create_tree(plan_frame,
            ('Loại CP', 'Dự toán', 'Thực tế', 'Chênh lệch', '% TH', 'Ghi chú'),
            (180, 120, 120, 120, 70, 200))
        if pid:
            for row in self.project_acct_mgr.get_cost_plans(pid):
                self.pa_plan_tree.insert('', 'end', values=(
                    row['category_name'], f"{row['planned_amount']:,.0f}",
                    f"{row['actual_amount']:,.0f}", f"{row['variance']:,.0f}",
                    f"{row['percent']:.1f}%", row['notes'],
                ))

        # Tab Chi phí & 154
        cost_frame = tk.Frame(notebook, bg=self.theme['bg'])
        notebook.add(cost_frame, text='Chi phí & 154')
        cost_tool = tk.Frame(cost_frame, bg=self.theme['bg'])
        cost_tool.pack(fill='x', padx=8, pady=6)
        self._make_button(cost_tool, "Tập hợp vào 154", self._pa_post_wip, self.theme['primary']).pack(side='left', padx=4)
        self.pa_cost_tree = self._create_tree(cost_frame,
            ('ID', 'Ngày', 'Loại CP', 'Mô tả', 'Số tiền', 'Trạng thái'),
            (50, 100, 140, 280, 110, 90))
        if pid:
            cursor = self.project_acct_mgr.conn.cursor()
            cursor.execute('''
                SELECT e.id, e.expense_date, ec.name, e.description, e.amount, e.status
                FROM expenses e JOIN expense_categories ec ON e.category_id = ec.id
                WHERE e.project_id = ? ORDER BY e.expense_date DESC
            ''', (pid,))
            for row in cursor.fetchall():
                self.pa_cost_tree.insert('', 'end', values=(
                    row[0], row[1], row[2], row[3], f"{row[4]:,.0f}", row[5],
                ))
            wip = self.project_acct_mgr.get_wip_summary(pid)
            tk.Label(cost_frame, text=f"Tổng CPSXDD (TK 154): {wip['total_wip']:,.0f} ₫",
                     font=('Arial', 11, 'bold'), bg=self.theme['bg']).pack(anchor='w', padx=10, pady=6)

        # Tab Doanh thu & nghiệm thu
        rev_frame = tk.Frame(notebook, bg=self.theme['bg'])
        notebook.add(rev_frame, text='Doanh thu & NT')
        r_tool = tk.Frame(rev_frame, bg=self.theme['bg'])
        r_tool.pack(fill='x', padx=8, pady=6)
        self._make_button(r_tool, "Nghiệm thu", self._pa_add_billing, self.theme['success']).pack(side='left', padx=4)
        self._make_button(r_tool, "Ghi doanh thu", self._pa_add_revenue, self.theme['info']).pack(side='left', padx=4)
        self._make_button(r_tool, "Bút toán DT", self._pa_revenue_journal, self.theme['warning']).pack(side='left', padx=4)
        rev_nb = ttk.Notebook(rev_frame)
        rev_nb.pack(fill='both', expand=True, padx=8, pady=4)
        bill_f = tk.Frame(rev_nb)
        rev_nb.add(bill_f, text='Nghiệm thu')
        self.pa_billing_tree = self._create_tree(bill_f,
            ('ID', 'Số HĐ', 'Đối tác', 'Ngày', 'Mốc', 'Trước VAT', 'VAT', 'Giữ lại', 'Thực nhận', 'TT'),
            (40, 90, 140, 90, 100, 100, 80, 80, 100, 70))
        for row in self.project_acct_mgr.get_billings(project_id=pid):
            self.pa_billing_tree.insert('', 'end', values=(
                row['id'], row['contract_no'], row['partner_name'], row['billing_date'],
                row['milestone_name'], f"{row['amount_before_vat']:,.0f}",
                f"{row['vat_amount']:,.0f}", f"{row['retention_amount']:,.0f}",
                f"{row['net_amount']:,.0f}", row['status'],
            ))
        rev_f = tk.Frame(rev_nb)
        rev_nb.add(rev_f, text='Doanh thu')
        self.pa_revenue_tree = self._create_tree(rev_f,
            ('ID', 'Mã DA', 'Dự án', 'Số HĐ', 'Ngày', 'Doanh thu', 'VAT', 'Diễn giải'),
            (40, 70, 160, 100, 90, 110, 90, 200))
        for row in self.project_acct_mgr.get_revenues(project_id=pid):
            self.pa_revenue_tree.insert('', 'end', values=(
                row['id'], row[1], row[2], row[3], row[4],
                f"{row[5]:,.0f}", f"{row[6]:,.0f}", row[7],
            ))

        # Tab Bút toán dự án
        journal_frame = tk.Frame(notebook, bg=self.theme['bg'])
        notebook.add(journal_frame, text='Bút toán')
        self.pa_journal_tree = self._create_tree(journal_frame,
            ('ID', 'Ngày', 'Mã DA', 'Diễn giải', 'Nợ', 'Có', 'Số tiền', 'Loại'),
            (50, 90, 70, 240, 60, 60, 110, 80))
        for row in self.project_acct_mgr.list_journal_by_project(project_id=pid):
            self.pa_journal_tree.insert('', 'end', values=(
                row['id'], row['entry_date'], row[2] or '', row['description'],
                row['debit_account'], row['credit_account'], f"{row['amount']:,.0f}",
                row['reference_type'] or '',
            ))

        # Tab nhà thầu phụ nâng cao
        subcontract_frame = tk.Frame(notebook, bg=self.theme['bg'])
        notebook.add(subcontract_frame, text='Thầu phụ + bảo lãnh')
        self.pa_subcontract_tree = self._create_tree(subcontract_frame,
            ('Mã DA', 'Dự án', 'ID HĐ', 'Số HĐ', 'Nhà thầu phụ', 'Giá trị HĐ', 'Đã thực hiện', 'Còn lại', 'Bảo lãnh', 'Bảo hành'),
            (70, 150, 60, 100, 160, 110, 110, 110, 100, 80))
        for row in self.project_acct_mgr.get_subcontract_control_report(pid):
            self.pa_subcontract_tree.insert('', 'end', values=(
                row[0], row[1], row[2], row[3], row[4],
                f"{row[5]:,.0f}", f"{row[6]:,.0f}", f"{row[7]:,.0f}",
                f"{row[8]:,.0f}", row[9],
            ))

        # Tab Báo cáo
        report_frame = tk.Frame(notebook, bg=self.theme['bg'])
        notebook.add(report_frame, text='Báo cáo')
        self.pa_report_tree = self._create_tree(report_frame,
            ('Mã DA', 'Dự án', 'Doanh thu', 'Chi phí', 'Lãi/lỗ'),
            (80, 220, 120, 120, 120))
        for row in self.project_acct_mgr.get_project_pl_report(pid):
            self.pa_report_tree.insert('', 'end', values=(
                row['code'], row['name'], f"{row['revenue']:,.0f}",
                f"{row['cost']:,.0f}", f"{row['profit']:,.0f}",
            ))

    def _create_tree(self, parent, columns, widths):
        tree = ttk.Treeview(parent, columns=columns, show='headings', height=14)
        last_index = len(columns) - 1
        for index, (col, width) in enumerate(zip(columns, widths)):
            tree.heading(col, text=col)
            tree.column(col, width=width, minwidth=max(70, min(width, 140)), stretch=(index == last_index))
        y_scroll = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        x_scroll = ttk.Scrollbar(parent, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky='nsew', padx=(8, 0), pady=(4, 0))
        y_scroll.grid(row=0, column=1, sticky='ns', padx=(0, 8), pady=(4, 0))
        x_scroll.grid(row=1, column=0, sticky='ew', padx=(8, 0), pady=(0, 4))
        return tree

    def _get_pa_project_id(self):
        val = getattr(self, 'pa_project_var', None)
        if not val or not val.get():
            return None
        try:
            return int(val.get().split(' - ')[0])
        except (ValueError, IndexError):
            return None

    def _pa_add_contract(self):
        projects = [(p['id'], p['code'], p['name']) for p in self.project_acct_mgr.list_projects_active()
                    if p['code'] != 'CHUNG']
        dialog = ContractDialog(self.root, projects, config.CONTRACT_TYPES)
        self.root.wait_window(dialog)
        if dialog.result:
            try:
                self.project_acct_mgr.save_contract(dialog.result)
                messagebox.showinfo("Thành công", "Đã lưu hợp đồng.")
                if getattr(self, '_active_screen_command', None) == self._show_contracts:
                    self._show_contracts()
                else:
                    self._show_project_accounting()
            except Exception as exc:
                messagebox.showerror("Lỗi", str(exc))

    def _pa_add_cost_plan(self):
        projects = [(p['id'], p['code'], p['name']) for p in self.project_acct_mgr.list_projects_active()
                    if p['code'] != 'CHUNG']
        categories = self.project_acct_mgr.get_expense_categories_for_plan()
        dialog = CostPlanDialog(self.root, projects, categories)
        self.root.wait_window(dialog)
        if dialog.result:
            self.project_acct_mgr.save_cost_plan(**dialog.result)
            messagebox.showinfo("Thành công", "Đã lưu dự toán.")
            self._show_project_accounting()

    def _pa_add_billing(self):
        if getattr(self, '_active_screen_command', None) == self._show_contracts:
            pid = self._get_contract_project_filter_id()
        else:
            pid = self._get_pa_project_id()
        cursor = self.project_acct_mgr.conn.cursor()
        if pid:
            cursor.execute('SELECT id, contract_no FROM project_contracts WHERE project_id = ?', (pid,))
        else:
            cursor.execute('SELECT id, contract_no FROM project_contracts ORDER BY contract_no')
        contracts = [(r[0], r[1]) for r in cursor.fetchall()]
        if not contracts:
            messagebox.showwarning("Thông báo", "Chưa có hợp đồng cho dự án này.")
            return
        dialog = BillingDialog(self.root, contracts)
        self.root.wait_window(dialog)
        if dialog.result:
            data = dict(dialog.result)
            create_rev = data.pop('create_revenue', False)
            self.project_acct_mgr.save_billing(data, create_revenue=create_rev)
            messagebox.showinfo("Thành công", "Đã lưu nghiệm thu.")
            if getattr(self, '_active_screen_command', None) == self._show_contracts:
                self._show_contracts()
            else:
                self._show_project_accounting()

    def _pa_add_revenue(self):
        projects = [(p['id'], p['code'], p['name']) for p in self.project_acct_mgr.list_projects_active()
                    if p['code'] != 'CHUNG']
        dialog = RevenueDialog(self.root, projects)
        self.root.wait_window(dialog)
        if dialog.result:
            self.project_acct_mgr.save_revenue(dialog.result)
            messagebox.showinfo("Thành công", "Đã ghi nhận doanh thu.")
            self._show_project_accounting()

    def _pa_revenue_journal(self):
        tree = getattr(self, 'pa_revenue_tree', None)
        if not tree or not tree.selection():
            messagebox.showwarning("Thông báo", "Chọn dòng doanh thu cần hạch toán.")
            return
        rev_id = int(tree.item(tree.selection()[0], 'values')[0])
        try:
            jid = self.project_acct_mgr.create_revenue_journal(rev_id)
            messagebox.showinfo("Thành công", f"Đã tạo bút toán doanh thu #{jid}.")
            self._show_project_accounting()
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _pa_post_wip(self):
        tree = getattr(self, 'pa_cost_tree', None)
        if not tree or not tree.selection():
            messagebox.showwarning("Thông báo", "Chọn chi phí cần tập hợp vào TK 154.")
            return
        expense_id = int(tree.item(tree.selection()[0], 'values')[0])
        try:
            jid = self.project_acct_mgr.post_expense_to_wip(expense_id)
            messagebox.showinfo("Thành công", f"Đã tập hợp CPSXDD, bút toán #{jid}.")
            self._show_project_accounting()
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _export_qt06_project(self):
        pid = self._get_pa_project_id()
        if not pid:
            messagebox.showwarning("Thông báo", "Chọn dự án cần xuất.")
            return
        try:
            from modules.project_accounting import export_project_qt06_excel
            path = export_project_qt06_excel(self.project_acct_mgr, pid)
            messagebox.showinfo("Thành công", f"Đã xuất báo cáo:\n{path}")
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _show_reports(self):
        """Hiển thị trang Báo cáo."""
        self._clear_content()
        self.audit_mgr.log('reports', None, 'READ', actor_id=1, new_value={'screen': 'reports'})

        self._page_title("BÁO CÁO & THỐNG KÊ", "Dashboard báo cáo, biểu đồ và bảng tổng hợp công trình.")

        # Frame nút chức năng
        button_frame = tk.Frame(self.content_frame, bg=self.theme['bg'])
        button_frame.pack(fill='x', padx=16, pady=(0, 10))

        create_modern_button(button_frame, "Xem báo cáo chi phí", self._report_expenses, variant='primary').pack(side='left', padx=(0, 6))
        create_modern_button(button_frame, "Xem báo cáo dự án", self._report_projects, variant='primary').pack(side='left', padx=6)
        create_modern_button(button_frame, "Xuất PDF", self._export_report_pdf, variant='outline').pack(side='left', padx=6)
        create_modern_button(button_frame, "Xuất Excel", self._export_report_excel, variant='outline').pack(side='left', padx=6)
        create_modern_button(button_frame, "Xuất Power BI CSV", self._export_powerbi_csv, variant='outline').pack(side='left', padx=6)

        tab_bar_wrap = tk.Frame(self.content_frame, bg=self.theme['bg'])
        tab_bar_wrap.pack(fill='x', padx=16, pady=(0, 8))
        tab_canvas = tk.Canvas(tab_bar_wrap, bg=self.theme['bg'], height=44, highlightthickness=0)
        tab_scroll = ttk.Scrollbar(tab_bar_wrap, orient='horizontal', command=tab_canvas.xview)
        tab_canvas.configure(xscrollcommand=tab_scroll.set)
        tab_canvas.pack(fill='x')
        tab_scroll.pack(fill='x')
        tab_inner = tk.Frame(tab_canvas, bg=self.theme['bg'])
        tab_canvas.create_window((0, 0), window=tab_inner, anchor='nw')
        tab_inner.bind('<Configure>', lambda _e: tab_canvas.configure(scrollregion=tab_canvas.bbox('all')))

        report_body = tk.Frame(self.content_frame, bg=self.theme['panel'], highlightbackground=self.theme['line'], highlightthickness=1)
        report_body.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        report_buttons = {}

        def clear_body():
            for widget in report_body.winfo_children():
                widget.destroy()

        def activate_tab(name, renderer):
            clear_body()
            for tab_name, button in report_buttons.items():
                active = tab_name == name
                button.configure(bg=self.theme['primary'] if active else '#EEF2F7',
                                 fg='white' if active else self.theme['text'])
            header = tk.Label(report_body, text=name, font=('Segoe UI', 13, 'bold'),
                              bg=self.theme['panel'], fg=self.theme['text'])
            header.pack(anchor='w', padx=14, pady=(12, 4))
            frame = tk.Frame(report_body, bg=self.theme['panel'])
            frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
            renderer(frame)

        def add_tab(name, renderer):
            btn = tk.Button(tab_inner, text=name, bg='#EEF2F7', fg=self.theme['text'],
                            activebackground=self.theme['primary'], activeforeground='white',
                            font=('Segoe UI', 10, 'bold'), bd=0, padx=14, pady=8,
                            cursor='hand2', command=lambda: activate_tab(name, renderer))
            btn.pack(side='left', padx=(0, 6), pady=4)
            report_buttons[name] = btn

        add_tab('Chi phí theo loại', self.report_gen.display_expense_chart)
        add_tab('Chi phí theo dự án', self.report_gen.display_project_chart)
        add_tab('Xu hướng theo tháng', self.report_gen.display_monthly_expense_chart)
        add_tab('Tồn kho vật tư', self.report_gen.display_material_stock_chart)
        add_tab('Bảng cân đối kế toán', self.report_gen.display_balance_sheet)
        add_tab('Tờ khai GTGT', self.vat_report_mgr.display_vat_declaration)
        add_tab('EVM dự án', self.evm_mgr.display_evm_dashboard)
        add_tab('Cảnh báo dòng tiền', self.cash_flow_alert_mgr.display_cash_flow_alerts)
        add_tab('Variance Analysis', self.variance_mgr.display_variance_analysis)
        add_tab('Định mức vật tư', self.material_control_mgr.display_material_alerts)
        add_tab('Bảng lương', self.payroll_mgr.display_payroll_summary)
        add_tab('Dự toán vs thực tế', self._show_project_budget_table)
        add_tab('Lãi lỗ dự án', self.report_gen.display_project_pl_table)

        def render_cost_collection(cost_col_frame):
            cols = ('Mã DA', 'Dự án', 'Loại CP', 'Tổng chi')
            cost_tree = ttk.Treeview(cost_col_frame, columns=cols, show='headings', height=14)
            for col, w in zip(cols, (80, 200, 180, 120)):
                cost_tree.heading(col, text=col)
                cost_tree.column(col, width=w)
            for row in self.report_gen.get_project_cost_collection():
                cost_tree.insert('', 'end', values=(row[0], row[1], row[2], f"{row[3]:,.0f}"))
            cost_tree.pack(fill='both', expand=True, padx=10, pady=10)
        add_tab('Tập hợp CP công trình', render_cost_collection)

        def render_wip(wip_frame):
            wip_cols = ('Mã DA', 'Dự án', 'Tổng TK 154')
            wip_tree = ttk.Treeview(wip_frame, columns=wip_cols, show='headings', height=14)
            for col, w in zip(wip_cols, (80, 260, 140)):
                wip_tree.heading(col, text=col)
                wip_tree.column(col, width=w)
            for row in self.report_gen.get_project_wip_report():
                wip_tree.insert('', 'end', values=(row[0], row[1], f"{row[2]:,.0f}"))
            wip_tree.pack(fill='both', expand=True, padx=10, pady=10)
        add_tab('Sổ 154 CPSXDD', render_wip)

        def render_contract_progress(hd_frame):
            hd_cols = ('Mã DA', 'Dự án', 'Số HĐ', 'Đối tác', 'Loại', 'Giá trị', 'Đã NT', 'Còn lại')
            hd_tree = ttk.Treeview(hd_frame, columns=hd_cols, show='headings', height=14)
            for col, w in zip(hd_cols, (70, 160, 100, 140, 90, 110, 110, 110)):
                hd_tree.heading(col, text=col)
                hd_tree.column(col, width=w)
            for row in self.project_acct_mgr.get_contract_progress_report():
                hd_tree.insert('', 'end', values=(
                    row[0], row[1], row[2], row[3],
                    config.CONTRACT_TYPES.get(row[4], row[4]),
                    f"{row[5]:,.0f}", f"{row[6]:,.0f}", f"{row[7]:,.0f}",
                ))
            hd_tree.pack(fill='both', expand=True, padx=10, pady=10)
        add_tab('Tiến độ hợp đồng', render_contract_progress)

        def render_ar_ap_aging(aging_frame):
            cols = ('Loại', 'Đối tác', '0-30', '31-60', '61-90', '>90')
            tree = ttk.Treeview(aging_frame, columns=cols, show='headings', height=14)
            widths = (90, 260, 120, 120, 120, 120)
            for col, width in zip(cols, widths):
                tree.heading(col, text=col)
                tree.column(col, width=width, anchor='e' if col not in ('Loại', 'Đối tác') else 'w')
            for row in self.extension_report_mgr.ar_ap_aging():
                tree.insert('', 'end', values=(
                    'Phải thu' if row['partner_type'] == 'customer' else 'Phải trả',
                    row['partner_name'],
                    f"{row['0-30']:,.0f}",
                    f"{row['31-60']:,.0f}",
                    f"{row['61-90']:,.0f}",
                    f"{row['>90']:,.0f}",
                ))
            tree.pack(fill='both', expand=True, padx=10, pady=10)
        add_tab('Tuổi nợ công nợ', render_ar_ap_aging)

        def render_expiring_items(expiring_frame):
            cols = ('Loại hồ sơ', 'Tên', 'Số tham chiếu', 'Ngày hết hạn', 'Phụ trách', 'Trạng thái')
            tree = ttk.Treeview(expiring_frame, columns=cols, show='headings', height=14)
            widths = (130, 240, 130, 120, 140, 110)
            for col, width in zip(cols, widths):
                tree.heading(col, text=col)
                tree.column(col, width=width)
            for row in self.extension_report_mgr.expiring_items():
                tree.insert('', 'end', values=(
                    row['item_type'], row['item_name'], row['reference_no'],
                    row['expiry_date'], row['owner'], row['status'],
                ))
            tree.pack(fill='both', expand=True, padx=10, pady=10)
        add_tab('Hồ sơ sắp hết hạn', render_expiring_items)
        activate_tab('Chi phí theo loại', self.report_gen.display_expense_chart)

    def _show_project_budget_table(self, parent):
        columns = ('ID', 'Mã dự án', 'Tên dự án', 'Dự toán', 'Đã chi', 'Còn lại', 'Tỷ lệ')
        tree = ttk.Treeview(parent, columns=columns, show='tree headings')
        for col, width in zip(columns, (60, 100, 260, 140, 140, 140, 90)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        for row in self.utility_mgr.get_project_budget_report():
            budget = row['budget'] or 0
            spent = row['spent'] or 0
            percent = (spent / budget * 100) if budget else 0
            tree.insert('', 'end', values=(
                row['id'], row['code'], row['name'],
                f"{budget:,.0f}", f"{spent:,.0f}", f"{row['remaining'] or 0:,.0f}",
                f"{percent:.1f}%"
            ))
        tree.pack(fill='both', expand=True, padx=10, pady=10)

    def _report_expenses(self):
        """Xem báo cáo chi phí chi tiết."""
        self._show_reports()

    def _report_projects(self):
        """Xem báo cáo chi phí theo dự án."""
        self._show_reports()

    def _export_report_pdf(self):
        """Xuất báo cáo ra PDF."""
        try:
            from modules.pdf_export import PDFExporter

            expenses = self.expense_mgr.get_all_expenses()
            if not expenses:
                messagebox.showwarning("Thông báo", "Chưa có dữ liệu để xuất báo cáo")
                return

            exporter = PDFExporter()
            filename = exporter.export_expense_report(expenses)
            messagebox.showinfo("Thành công", f"Xuất PDF thành công!\n{filename}")
        except ImportError:
            messagebox.showerror("Lỗi", "Cần cài reportlab: pip install reportlab")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi xuất PDF: {str(e)}")

    def _export_report_excel(self):
        """Xuất báo cáo ra Excel."""
        try:
            expenses = self.expense_mgr.get_all_expenses()
            if not expenses:
                messagebox.showwarning("Thông báo", "Chưa có dữ liệu để xuất báo cáo")
                return

            filename = f"report_{datetime.now().strftime('%Y%m%d')}.xlsx"
            ExcelExporter.export_expenses(expenses, filename)
            self.audit_mgr.log('reports', None, 'EXPORT', actor_id=1, new_value={'file': filename, 'type': 'expense_report'})
            messagebox.showinfo("Thành công", f"Xuất Excel thành công!\n{filename}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi xuất Excel: {str(e)}")

    def _export_powerbi_csv(self):
        try:
            results = self.powerbi_exporter.export_all()
            self.audit_mgr.log('powerbi', None, 'EXPORT', actor_id=1, new_value=results)
            messagebox.showinfo("Power BI", "Đã xuất dataset:\n" + "\n".join(results.values()))
        except Exception as exc:
            messagebox.showerror("Power BI", str(exc))

    def _show_bank_reconciliation(self):
        self._clear_content()
        self._page_title("Đối chiếu ngân hàng", "Nhập sao kê CSV, tự động khớp với chi phí chuyển khoản và xem chênh lệch.")

        toolbar = tk.Frame(self.content_frame, bg=self.theme['bg'])
        toolbar.pack(fill='x', padx=16, pady=(0, 8))
        create_modern_button(toolbar, "Nhập sao kê CSV", self._import_bank_statement_csv, variant='primary').pack(side='left', padx=(0, 6))
        create_modern_button(toolbar, "Auto-match", self._auto_match_bank_statement, variant='success').pack(side='left', padx=6)
        create_modern_button(toolbar, "Gợi ý khớp", self._show_bank_match_suggestions, variant='outline').pack(side='left', padx=6)
        create_modern_button(toolbar, "Làm mới", self._show_bank_reconciliation, variant='outline').pack(side='left', padx=6)

        report = self.bank_recon_mgr.get_unmatched_report()
        matches = self.bank_recon_mgr.get_matches()
        summary = tk.Frame(self.content_frame, bg=self.theme['bg'])
        summary.pack(fill='x', padx=10, pady=(0, 8))
        total_bank_unmatched = sum(float(row['amount'] or 0) for row in report['bank_unmatched'])
        total_system_unmatched = sum(float(row['amount'] or 0) for row in report['system_unmatched'])
        for label, value, color in [
            ('Đã khớp', len(matches), self.theme['success']),
            ('Sao kê chưa khớp', len(report['bank_unmatched']), self.theme['warning']),
            ('Chi phí CK chưa khớp', len(report['system_unmatched']), self.theme['danger'] if report['system_unmatched'] else self.theme['info']),
            ('Chênh lệch đang treo', f"{total_bank_unmatched - total_system_unmatched:,.0f}", self.theme['primary']),
        ]:
            self._create_stat_card(summary, label, str(value), color)

        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        matches_frame = tk.Frame(notebook, bg=self.theme['panel'])
        bank_frame = tk.Frame(notebook, bg=self.theme['panel'])
        system_frame = tk.Frame(notebook, bg=self.theme['panel'])
        notebook.add(matches_frame, text='Đã đối chiếu')
        notebook.add(bank_frame, text='Sao kê chưa khớp')
        notebook.add(system_frame, text='Chi phí chưa khớp')

        self._render_bank_matches(matches_frame)
        self._render_bank_unmatched(bank_frame, report['bank_unmatched'])
        self._render_system_unmatched(system_frame, report['system_unmatched'])

    def _import_bank_statement_csv(self):
        file_path = filedialog.askopenfilename(
            title="Chọn file sao kê ngân hàng CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            return
        try:
            result = self.bank_recon_mgr.import_csv(file_path)
            messagebox.showinfo("Nhập sao kê", f"Đã nhập {result['imported']} dòng, bỏ qua {result['skipped']} dòng.")
            self._show_bank_reconciliation()
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _auto_match_bank_statement(self):
        try:
            matched = self.bank_recon_mgr.auto_match()
            messagebox.showinfo("Đối chiếu ngân hàng", f"Đã tự động khớp {matched} giao dịch.")
            self._show_bank_reconciliation()
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _show_bank_match_suggestions(self):
        try:
            suggestions = self.bank_recon_mgr.get_match_suggestions()
            if not suggestions:
                messagebox.showinfo("Gợi ý khớp", "Chưa tìm thấy gợi ý khớp mới.")
                return
            lines = ["Gợi ý khớp sao kê - chi phí", ""]
            for item in suggestions[:50]:
                bank = item['bank_row']
                exp = item['expense']
                lines.append(
                    f"NH #{bank['id']} {bank['transaction_date']} {float(bank['amount'] or 0):,.0f} "
                    f"-> CP #{exp['id']} {exp['expense_date']} {float(exp['amount'] or 0):,.0f} "
                    f"({item['confidence']}%)"
                )
                lines.append(f"  NH: {bank['description'] or ''}")
                lines.append(f"  CP: {exp['description'] or ''}")
            self._show_text_report("Gợi ý đối chiếu ngân hàng", "\n".join(lines))
        except Exception as exc:
            messagebox.showerror("Gợi ý khớp", str(exc))

    def _render_bank_matches(self, parent):
        cols = ('Ngày NH', 'Tiền NH', 'Mô tả NH', 'CP ID', 'Ngày CP', 'Tiền CP', 'Trạng thái', 'Tin cậy')
        tree = ttk.Treeview(parent, columns=cols, show='headings', height=14)
        for col, width in zip(cols, (90, 120, 260, 70, 90, 120, 90, 70)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        for row in self.bank_recon_mgr.get_matches():
            tree.insert('', 'end', values=(
                row['transaction_date'], f"{row['bank_amount']:,.0f}", row['bank_description'],
                row['expense_id'] or '', row['expense_date'] or '',
                f"{row['expense_amount'] or 0:,.0f}", row['match_status'], row['confidence'],
            ))
        self._pack_tree_with_scrollbars(parent, tree)

    def _render_bank_unmatched(self, parent, rows):
        cols = ('ID', 'Tài khoản', 'Ngày', 'Số tiền', 'Diễn giải', 'Mã GD')
        tree = ttk.Treeview(parent, columns=cols, show='headings', height=14)
        for col, width in zip(cols, (60, 120, 90, 120, 300, 120)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        for row in rows:
            tree.insert('', 'end', values=(
                row['id'], row['bank_account'], row['transaction_date'],
                f"{row['amount']:,.0f}", row['description'], row['reference_no'],
            ))
        self._pack_tree_with_scrollbars(parent, tree)

    def _render_system_unmatched(self, parent, rows):
        cols = ('ID', 'Ngày', 'Dự án', 'Mô tả', 'Số tiền', 'Phương thức', 'Trạng thái')
        tree = ttk.Treeview(parent, columns=cols, show='headings', height=14)
        for col, width in zip(cols, (60, 90, 160, 280, 120, 120, 90)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        for row in rows:
            tree.insert('', 'end', values=(
                row['id'], row['expense_date'], row['project_name'], row['description'],
                f"{row['amount'] or 0:,.0f}", row['payment_method'], row['status'],
            ))
        self._pack_tree_with_scrollbars(parent, tree)

    def _pack_tree_with_scrollbars(self, parent, tree, padx=10, pady=10):
        y_scroll = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        x_scroll = ttk.Scrollbar(parent, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky='nsew', padx=(padx, 0), pady=(pady, 0))
        y_scroll.grid(row=0, column=1, sticky='ns', padx=(0, padx), pady=(pady, 0))
        x_scroll.grid(row=1, column=0, sticky='ew', padx=(padx, 0), pady=(0, pady))

    def _show_project_rbac(self):
        self._clear_content()
        self._page_title("Phân quyền theo dự án", "Giới hạn user chỉ xem/sửa/phê duyệt các dự án được phân công.")

        form = tk.Frame(self.content_frame, bg=self.theme['bg'])
        form.pack(fill='x', padx=16, pady=(0, 8))
        users = self.auth_mgr.get_all_users()
        projects = self.project_acct_mgr.list_projects_active()
        self.rbac_user_var = tk.StringVar()
        self.rbac_project_var = tk.StringVar()
        user_values = [f"{u['id']} - {u['username']} ({u['role']})" for u in users]
        project_values = [f"{p['id']} - {p['code']} - {p['name']}" for p in projects]
        ttk.Combobox(form, textvariable=self.rbac_user_var, values=user_values, width=28).pack(side='left', padx=4)
        ttk.Combobox(form, textvariable=self.rbac_project_var, values=project_values, width=38).pack(side='left', padx=4)
        self.rbac_edit_var = tk.IntVar(value=0)
        self.rbac_approve_var = tk.IntVar(value=0)
        tk.Checkbutton(form, text='Sửa', variable=self.rbac_edit_var, bg=self.theme['bg']).pack(side='left', padx=4)
        tk.Checkbutton(form, text='Duyệt', variable=self.rbac_approve_var, bg=self.theme['bg']).pack(side='left', padx=4)
        create_modern_button(form, "Cấp quyền", self._grant_project_rbac, variant='primary').pack(side='left', padx=6)

        cols = ('User', 'Họ tên', 'Role', 'Mã DA', 'Dự án', 'View', 'Edit', 'Approve')
        tree = ttk.Treeview(self.content_frame, columns=cols, show='headings', height=16)
        for col, width in zip(cols, (120, 160, 90, 80, 220, 70, 70, 80)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        cursor = self.project_access_mgr.conn.cursor()
        cursor.execute('''
            SELECT u.username, COALESCE(u.full_name, ''), u.role,
                   p.code, p.name, a.can_view, a.can_edit, a.can_approve
            FROM user_project_access a
            JOIN users u ON u.id = a.user_id
            JOIN projects p ON p.id = a.project_id
            ORDER BY u.username, p.code
        ''')
        for row in cursor.fetchall():
            tree.insert('', 'end', values=tuple(row))
        tree.pack(fill='both', expand=True, padx=16, pady=(0, 16))

    def _grant_project_rbac(self):
        try:
            user_id = int(self.rbac_user_var.get().split(' - ')[0])
            project_id = int(self.rbac_project_var.get().split(' - ')[0])
        except (ValueError, IndexError):
            messagebox.showwarning("Phân quyền", "Vui lòng chọn user và dự án.")
            return
        can_edit = bool(self.rbac_edit_var.get())
        can_approve = bool(self.rbac_approve_var.get())
        level = 'approve' if can_approve else 'edit' if can_edit else 'view'
        self.project_access_mgr.grant_project_access(
            user_id, project_id, level, can_view=True, can_edit=can_edit, can_approve=can_approve
        )
        messagebox.showinfo("Phân quyền", "Đã cấp quyền dự án.")
        self._show_project_rbac()

    def _show_fiscal_locks(self):
        self._clear_content()
        self._page_title("Khóa kỳ kế toán", "Sau khi khóa kỳ, database sẽ chặn thêm/sửa/xóa bút toán trong kỳ đó.")
        toolbar = tk.Frame(self.content_frame, bg=self.theme['bg'])
        toolbar.pack(fill='x', padx=16, pady=(0, 8))
        create_modern_button(toolbar, "Khóa kỳ đang chọn", lambda: self._set_selected_period_lock(True), variant='danger').pack(side='left', padx=4)
        create_modern_button(toolbar, "Mở khóa", lambda: self._set_selected_period_lock(False), variant='outline').pack(side='left', padx=4)
        cols = ('Kỳ', 'Từ ngày', 'Đến ngày', 'Đã khóa', 'Khóa lúc', 'Người khóa')
        self.fiscal_lock_tree = ttk.Treeview(self.content_frame, columns=cols, show='headings', height=18)
        for col, width in zip(cols, (100, 100, 100, 80, 150, 90)):
            self.fiscal_lock_tree.heading(col, text=col)
            self.fiscal_lock_tree.column(col, width=width)
        for row in self.fiscal_lock_mgr.list_periods():
            self.fiscal_lock_tree.insert('', 'end', values=(
                row['fiscal_period'], row['period_start'], row['period_end'],
                'Có' if row['is_locked'] else '', row['locked_at'] or '', row['locked_by'] or '',
            ))
        self.fiscal_lock_tree.pack(fill='both', expand=True, padx=16, pady=(0, 16))

    def _set_selected_period_lock(self, locked):
        sel = getattr(self, 'fiscal_lock_tree', None).selection() if hasattr(self, 'fiscal_lock_tree') else []
        if not sel:
            messagebox.showwarning("Khóa kỳ", "Vui lòng chọn một kỳ.")
            return
        period = self.fiscal_lock_tree.item(sel[0], 'values')[0]
        try:
            if locked and not self._confirm_period_close(period):
                return
            self.fiscal_lock_mgr.set_locked(period, locked, user_id=1)
            messagebox.showinfo("Khóa kỳ", "Đã cập nhật trạng thái khóa kỳ.")
            self._show_fiscal_locks()
        except Exception as exc:
            messagebox.showerror("Khóa kỳ", str(exc))

    def _confirm_period_close(self, period):
        issues = self.utility_mgr.get_period_close_check(period)
        critical = [item for item in issues if item['level'] == 'critical']
        if not issues:
            return messagebox.askyesno("Khóa kỳ", f"Kỳ {period} không có cảnh báo lớn. Khóa kỳ này?")

        win = tk.Toplevel(self.root)
        win.title(f"Checklist khóa kỳ {period}")
        win.geometry("820x460")
        win.configure(bg=self.theme['bg'])
        win.transient(self.root)
        win.grab_set()
        result = {'ok': False}

        tk.Label(win, text=f"Checklist khóa kỳ {period}", bg=self.theme['bg'],
                 fg=self.theme['TEXT_PRIMARY'], font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=16, pady=(14, 2))
        subtitle = "Cần xử lý lỗi nghiêm trọng trước khi khóa kỳ." if critical else "Có cảnh báo cần rà soát trước khi khóa kỳ."
        tk.Label(win, text=subtitle, bg=self.theme['bg'], fg=self.theme['TEXT_MUTED'],
                 font=('Segoe UI', 10)).pack(anchor='w', padx=16, pady=(0, 10))

        body = tk.Frame(win, bg='white', highlightbackground=self.theme['line'], highlightthickness=1)
        body.pack(fill='both', expand=True, padx=16, pady=(0, 12))
        cols = ('Mức', 'Vấn đề', 'Số dòng', 'Giá trị', 'Việc cần làm')
        tree = ttk.Treeview(body, columns=cols, show='headings', height=10)
        for col, width in zip(cols, (110, 220, 80, 120, 330)):
            tree.heading(col, text=col)
            tree.column(col, width=width)
        for item in issues:
            tree.insert('', 'end', values=(
                'Nghiêm trọng' if item['level'] == 'critical' else 'Cảnh báo',
                item['title'], item['count'], f"{item['amount']:,.0f}", item['action'],
            ))
        tree.pack(fill='both', expand=True, padx=10, pady=10)

        actions = tk.Frame(win, bg=self.theme['bg'])
        actions.pack(fill='x', padx=16, pady=(0, 14))

        def close(value):
            result['ok'] = value
            win.destroy()

        if critical:
            create_modern_button(actions, "Mở kiểm soát kế toán", lambda: (win.destroy(), self._show_dashboard()),
                                 variant='primary', padx=12, pady=7).pack(side='left')
            create_modern_button(actions, "Đóng", lambda: close(False),
                                 variant='secondary', padx=12, pady=7).pack(side='right')
        else:
            create_modern_button(actions, "Vẫn khóa kỳ", lambda: close(True),
                                 variant='danger', padx=12, pady=7).pack(side='left')
            create_modern_button(actions, "Hủy", lambda: close(False),
                                 variant='secondary', padx=12, pady=7).pack(side='right')
        self.root.wait_window(win)
        return result['ok']

    def _create_placeholder_entry(self, parent, variable, placeholder):
        entry = tk.Entry(parent, textvariable=variable, font=('Arial', 10), relief='solid', bd=1)
        if placeholder and not variable.get():
            entry.insert(0, placeholder)
            entry.configure(fg=self.theme['muted'])

        def on_focus_in(_event):
            if entry.get() == placeholder and entry.cget('fg') == self.theme['muted']:
                entry.delete(0, 'end')
                entry.configure(fg=self.theme['text'])

        def on_focus_out(_event):
            if placeholder and not entry.get().strip():
                entry.insert(0, placeholder)
                entry.configure(fg=self.theme['muted'])

        entry.bind('<FocusIn>', on_focus_in)
        entry.bind('<FocusOut>', on_focus_out)
        return entry

    def _company_setting_value(self, key):
        var = self.company_setting_vars.get(key)
        if not var:
            return ''
        value = var.get().strip()
        placeholder = getattr(self, 'company_setting_placeholders', {}).get(key, '')
        return '' if value == placeholder else value

    def _show_settings(self):
        """Hiển thị trang Cài đặt."""
        self._clear_content()

        title = tk.Label(self.content_frame, text="⚙️  CÀI ĐẶT HỆ THỐNG",
                         font=('Arial', 14, 'bold'), bg='#f0f4f8', fg='#1a56a5')
        title.pack(padx=15, pady=15, anchor='w')

        settings_frame = tk.Frame(self.content_frame, bg=self.theme['bg'])
        settings_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        company_frame = tk.LabelFrame(settings_frame, text="  THÔNG TIN DOANH NGHIỆP MẶC ĐỊNH  ",
                                      font=('Arial', 10, 'bold'), bg='white', fg='#1a56a5', padx=18, pady=16,
                                      highlightbackground=self.theme['line'], highlightthickness=1)
        company_frame.pack(fill='x', pady=(0, 10))
        tk.Label(company_frame, text="Cập nhật thông tin doanh nghiệp để in biểu mẫu chính xác và đồng bộ dữ liệu.",
                 font=('Segoe UI', 10), bg='white', fg=self.theme['muted']).grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 12))

        settings = self.utility_mgr.get_app_settings()
        company_rows = [
            ("company_name", "Tên công ty", settings.get("company_name", "")),
            ("company_tax_code", "Mã số thuế", settings.get("company_tax_code", "")),
            ("company_representative", "Người đại diện", settings.get("company_representative", "")),
            ("company_address", "Địa chỉ", settings.get("company_address", "")),
            ("company_phone", "Điện thoại", settings.get("company_phone", "")),
            ("company_bank_account", "Tài khoản NH", settings.get("company_bank_account", "")),
            ("company_bank_name", "Ngân hàng", settings.get("company_bank_name", "")),
            ("default_accountant", "Kế toán mặc định", settings.get("default_accountant", "Kế toán")),
            ("default_department_head", "Trưởng phòng mặc định", settings.get("default_department_head", "")),
        ]
        self.company_setting_vars = {}
        self.company_setting_placeholders = {
            "company_address": "Ví dụ: 123 Nguyễn Văn Linh, Q.7, TP.HCM",
            "company_phone": "Ví dụ: 028 1234 5678 hoặc 0901 234 567",
            "company_bank_account": "Số tài khoản ngân hàng",
            "company_bank_name": "Ví dụ: Vietcombank - CN TP.HCM",
            "default_accountant": "Tên kế toán phụ trách",
            "default_department_head": "Tên trưởng phòng/phê duyệt",
        }
        required_keys = {"company_name", "company_tax_code"}
        for index, (key, label, value) in enumerate(company_rows):
            if index == 8:
                row = 4
                col = 0
            elif index < 4:
                row = index
                col = 0
            else:
                row = index - 4
                col = 2
            suffix = " *" if key in required_keys else ""
            tk.Label(company_frame, text=f"{label}{suffix}:", font=('Segoe UI', 10, 'bold'),
                     bg='white', fg='#17324D', anchor='w').grid(row=row + 1, column=col, sticky='w', pady=8)
            var = tk.StringVar(value=value)
            self.company_setting_vars[key] = var
            entry = self._create_placeholder_entry(company_frame, var, self.company_setting_placeholders.get(key, ''))
            entry.configure(font=('Segoe UI', 10), relief='flat', highlightthickness=1,
                            highlightbackground='#d1d5db', highlightcolor=self.theme['primary'], bd=0, bg='white')
            if index == 8:
                entry.grid(row=row + 1, column=col + 1, columnspan=3, sticky='ew', pady=8, padx=(8, 0))
            else:
                entry.grid(row=row + 1, column=col + 1, sticky='ew', pady=8, padx=(8, 0))
        company_frame.columnconfigure(1, weight=1)
        company_frame.columnconfigure(3, weight=1)
        button_row = tk.Frame(company_frame, bg='white')
        button_row.grid(row=6, column=0, columnspan=4, sticky='w', pady=(12, 0))
        create_modern_button(button_row, "Lưu thông tin công ty", self._save_company_settings,
                     variant='success', padx=18, pady=7).pack(side='left')
        create_modern_button(button_row, "Làm mới", lambda: self._show_settings(),
                     variant='outline', padx=18, pady=7).pack(side='left', padx=8)
        tk.Label(company_frame, text="* Các trường bắt buộc phải nhập để in biểu mẫu và nộp báo cáo.",
             font=('Segoe UI', 9), bg='white', fg=self.theme['TEXT_MUTED']).grid(row=7, column=0, columnspan=4, sticky='w', pady=(8, 0))
        tk.Label(company_frame, text="Ghi chú: Thông tin này được sử dụng trên hóa đơn, chứng từ, và mẫu biểu in.",
             font=('Segoe UI', 9, 'italic'), bg='white', fg=self.theme['TEXT_MUTED']).grid(row=8, column=0, columnspan=4, sticky='w', pady=(4, 0))

        # ── SAO LƯU & PHỤC HỒI ─────────────────────────
        backup_frame = tk.LabelFrame(settings_frame, text="  💾 SAO LƯU & PHỤC HỒI  ",
                                     font=('Arial', 10, 'bold'), bg='white',
                                     fg='#1a56a5', padx=18, pady=16,
                                     highlightbackground=self.theme['line'], highlightthickness=1)
        backup_frame.pack(fill='x', pady=(0, 10))
        tk.Label(backup_frame, text=self._backup_status_text(), font=('Segoe UI', 10),
                 bg='white', fg='#17324D', justify='left').pack(anchor='w', pady=(0, 10))
        backup_buttons = tk.Frame(backup_frame, bg='white')
        backup_buttons.pack(fill='x')
        create_modern_button(backup_buttons, "Sao lưu ngay", self._create_backup, variant='success',
                             padx=16, pady=7).pack(side='left', padx=5)
        create_modern_button(backup_buttons, "Phục hồi", self._restore_backup, variant='warning',
                             padx=16, pady=7).pack(side='left', padx=5)
        create_modern_button(backup_buttons, "Danh sách sao lưu", self._show_backups, variant='accent',
                             padx=16, pady=7).pack(side='left', padx=5)
        create_modern_button(backup_buttons, "Kiểm tra sao lưu", self._show_backup_health, variant='accent',
                             padx=16, pady=7).pack(side='left', padx=5)
        create_modern_button(backup_buttons, "Dữ liệu dùng chung", self._configure_shared_database, variant='accent',
                             padx=16, pady=7).pack(side='left', padx=5)

        # ── THỐNG KÊ DATABASE ───────────────────────────
        stats_frame = tk.LabelFrame(settings_frame, text="  📊 THỐNG KÊ DATABASE  ",
                                   font=('Arial', 10, 'bold'), bg='white',
                                   fg='#1a56a5', padx=18, pady=16,
                                   highlightbackground=self.theme['line'], highlightthickness=1)
        stats_frame.pack(fill='x', pady=(0, 10))

        create_modern_button(stats_frame, "Xem thống kê", self._show_db_stats, variant='accent',
                             padx=16, pady=7).pack(side='left', padx=5)
        create_modern_button(stats_frame, "Tối ưu hóa DB", self._optimize_database, variant='warning',
                             padx=16, pady=7).pack(side='left', padx=5)

        # ── KHÁC ────────────────────────────────────────
        other_frame = tk.LabelFrame(settings_frame, text="  ⚙️  KHÁC  ",
                                   font=('Arial', 10, 'bold'), bg='#f0f4f8',
                                   fg='#1a56a5', padx=15, pady=10)
        other_frame.pack(fill='x')

        create_modern_button(other_frame, "Thông tin ứng dụng", self._show_about, variant='accent',
                             padx=16, pady=7).pack(side='left', padx=5)
        create_modern_button(other_frame, "Mở thư mục biểu mẫu đã in", self._open_generated_forms_folder,
                             variant='accent', padx=16, pady=7).pack(side='left', padx=5)

    def _save_company_settings(self):
        try:
            data = {key: self._company_setting_value(key) for key in getattr(self, 'company_setting_vars', {})}
            required = {
                'company_name': 'Tên công ty',
                'company_tax_code': 'Mã số thuế',
            }
            missing = [label for key, label in required.items() if not data.get(key)]
            if missing:
                messagebox.showwarning("Thiếu thông tin bắt buộc", "Vui lòng nhập: " + ", ".join(missing))
                return
            tax_code = re.sub(r'\D', '', data.get('company_tax_code', ''))
            if len(tax_code) not in (10, 13):
                messagebox.showwarning("Mã số thuế không hợp lệ", "MST phải gồm đúng 10 hoặc 13 chữ số.")
                return
            data['company_tax_code'] = tax_code
            phone = data.get('company_phone', '')
            if phone:
                digits = re.sub(r'\D', '', phone)
                if not (10 <= len(digits) <= 11 and (digits.startswith('0') or digits.startswith('84'))):
                    messagebox.showwarning("Số điện thoại không hợp lệ", "Vui lòng nhập số điện thoại Việt Nam hợp lệ.")
                    return
            self.utility_mgr.save_app_settings(data)
            self.template_renderer = _LazyManager('modules.template_renderer', 'TemplateRenderer')
            messagebox.showinfo("Thành công", "Đã lưu thông tin công ty để dùng trên phần mềm và biểu mẫu.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không lưu được thông tin công ty: {str(e)}")

    def _backup_status_text(self):
        try:
            backup_mgr = BackupManager()
            backups = backup_mgr.get_backup_list()
            if backups:
                last = backups[0]
                return (
                    "Sao lưu tự động: BẬT\n"
                    f"Lần cuối: {last['date']} ({last['size']})\n"
                    f"Lưu tại: {os.path.abspath(backup_mgr.backup_dir)}"
                )
            return (
                "Sao lưu tự động: BẬT\n"
                "Lần cuối: Chưa có bản sao lưu\n"
                f"Lưu tại: {os.path.abspath(backup_mgr.backup_dir)}"
            )
        except Exception:
            return "Sao lưu tự động: Chưa xác định\nLần cuối: --\nLưu tại: --"

    def _show_ocr_import(self):
        OCRImportDialog(self.root)

    def _open_generated_forms_folder(self):
        try:
            folder = os.path.abspath(os.path.join('documents', 'generated_forms'))
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không mở được thư mục biểu mẫu: {str(e)}")

    def _create_backup(self):
        """Tạo sao lưu."""
        try:
            backup_mgr = BackupManager()
            success, message = backup_mgr.create_backup()
            if success:
                self.utility_mgr.mark_backup_now()
                messagebox.showinfo("Thành công", message)
            else:
                messagebox.showerror("Lỗi", message)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi sao lưu: {str(e)}")

    def _restore_backup(self):
        """Phục hồi từ sao lưu."""
        try:
            backup_mgr = BackupManager()
            backups = backup_mgr.get_backup_list()

            if not backups:
                messagebox.showwarning("Thông báo", "Không có file sao lưu nào")
                return

            self._show_backups()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi phục hồi: {str(e)}")

    def _show_backups(self):
        """Hiển thị danh sách sao lưu."""
        try:
            backup_mgr = BackupManager()
            backups = backup_mgr.get_backup_list()

            if not backups:
                messagebox.showinfo("Thông báo", "Chưa có file sao lưu nào")
                return

            win = tk.Toplevel(self.root)
            win.title("Danh sách sao lưu")
            win.geometry("760x420")
            win.configure(bg=self.theme['bg'])
            win.transient(self.root)

            tk.Label(win, text="Danh sách sao lưu", bg=self.theme['bg'],
                     fg=self.theme['TEXT_PRIMARY'], font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=16, pady=(14, 2))
            tk.Label(win, text=os.path.abspath(backup_mgr.backup_dir), bg=self.theme['bg'],
                     fg=self.theme['TEXT_MUTED'], font=('Segoe UI', 9)).pack(anchor='w', padx=16, pady=(0, 10))

            body = tk.Frame(win, bg='white', highlightbackground=self.theme['line'], highlightthickness=1)
            body.pack(fill='both', expand=True, padx=16, pady=(0, 12))
            cols = ('Tên file', 'Kích thước', 'Ngày tạo')
            tree = ttk.Treeview(body, columns=cols, show='headings', height=10)
            for col, width in zip(cols, (360, 120, 180)):
                tree.heading(col, text=col)
                tree.column(col, width=width)
            for backup in backups:
                tree.insert('', 'end', values=(backup['name'], backup['size'], backup['date']))
            tree.pack(fill='both', expand=True, padx=10, pady=10)

            actions = tk.Frame(win, bg=self.theme['bg'])
            actions.pack(fill='x', padx=16, pady=(0, 14))

            def selected_name():
                if not tree.selection():
                    messagebox.showwarning("Sao lưu", "Chọn một bản sao lưu.")
                    return None
                return tree.item(tree.selection()[0], 'values')[0]

            def restore_selected():
                name = selected_name()
                if not name:
                    return
                if messagebox.askyesno("Phục hồi", f"Phục hồi dữ liệu từ {name}? Hệ thống sẽ tạo bản sao lưu trước khi phục hồi."):
                    success, msg = backup_mgr.restore_backup(name)
                    messagebox.showinfo("Phục hồi" if success else "Lỗi", msg)
                    win.destroy()

            def delete_selected():
                name = selected_name()
                if not name:
                    return
                if messagebox.askyesno("Xóa sao lưu", f"Xóa bản sao lưu {name}?"):
                    success, msg = backup_mgr.delete_backup(name)
                    messagebox.showinfo("Xóa sao lưu" if success else "Lỗi", msg)
                    win.destroy()
                    self._show_backups()

            create_modern_button(actions, "Phục hồi bản chọn", restore_selected, variant='warning').pack(side='left', padx=(0, 6))
            create_modern_button(actions, "Xóa bản chọn", delete_selected, variant='danger').pack(side='left', padx=6)
            create_modern_button(actions, "Đóng", win.destroy, variant='secondary').pack(side='right')
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi: {str(e)}")

    def _show_backup_health(self):
        try:
            messagebox.showinfo("Tình trạng sao lưu", self.utility_mgr.backup_health())
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không kiểm tra được sao lưu: {str(e)}")

    def _configure_shared_database(self):
        try:
            from database import get_database_path, set_database_path, init_database
            current_path = os.path.abspath(get_database_path())
            messagebox.showinfo(
                "Dữ liệu dùng chung",
                "Chọn file accounting.db nằm trong thư mục dùng chung LAN/OneDrive/ổ mạng.\n\n"
                f"Đang dùng:\n{current_path}\n\n"
                "Sau khi đổi đường dẫn, nên tắt và mở lại phần mềm trên các máy."
            )
            file_path = filedialog.asksaveasfilename(
                title="Chọn hoặc tạo database dùng chung",
                defaultextension='.db',
                filetypes=[("SQLite database", "*.db"), ("All files", "*.*")],
                initialfile="accounting.db"
            )
            if not file_path:
                return
            saved_path = set_database_path(file_path)
            init_database()
            messagebox.showinfo(
                "Thành công",
                "Đã cấu hình dữ liệu dùng chung:\n"
                f"{saved_path}\n\n"
                "Hãy cấu hình máy thứ hai trỏ tới đúng file này."
            )
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không cấu hình được dữ liệu dùng chung: {str(e)}")

    def _show_db_stats(self):
        """Hiển thị thống kê database."""
        try:
            cursor = self.utility_mgr.conn.cursor()
            month = datetime.now().strftime('%Y-%m')
            cursor.execute("SELECT COUNT(*) FROM projects WHERE status = 'active'")
            active_projects = cursor.fetchone()[0]
            cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE substr(expense_date, 1, 7) = ?", (month,))
            month_expense = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM documents WHERE status IN ('draft', 'pending', 'submitted')")
            pending_docs = cursor.fetchone()[0]
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = 'advance_requests'")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM advance_requests WHERE status NOT IN ('settled', 'closed', 'rejected')")
                open_advances = cursor.fetchone()[0]
            else:
                cursor.execute("SELECT COUNT(*) FROM expenses WHERE status NOT IN ('paid', 'posted', 'approved', 'reversed')")
                open_advances = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM materials WHERE COALESCE(quantity, 0) > 0")
            stock_items = cursor.fetchone()[0]
            win = tk.Toplevel(self.root)
            win.title("Thống kê nghiệp vụ")
            win.geometry("860x560")
            win.minsize(760, 480)
            win.configure(bg=self.theme['bg'])
            win.transient(self.root)

            tk.Label(win, text="Thống kê nghiệp vụ", bg=self.theme['bg'],
                     fg=self.theme['TEXT_PRIMARY'], font=('Segoe UI', 15, 'bold')).pack(anchor='w', padx=18, pady=(16, 2))
            tk.Label(win, text="Tình trạng dữ liệu và các việc cần xử lý trong tháng hiện tại.",
                     bg=self.theme['bg'], fg=self.theme['TEXT_MUTED'],
                     font=('Segoe UI', 10)).pack(anchor='w', padx=18, pady=(0, 12))

            cards = tk.Frame(win, bg=self.theme['bg'])
            cards.pack(fill='x', padx=14, pady=(0, 8))
            for label, value, color in [
                ("Dự án hoạt động", active_projects, self.theme['primary']),
                ("Chi phí tháng", f"{month_expense:,.0f}", self.theme['warning']),
                ("Hóa đơn chờ", pending_docs, self.theme['danger'] if pending_docs else self.theme['success']),
                ("Tạm ứng treo", open_advances, self.theme['info']),
                ("Vật tư tồn", stock_items, self.theme['success']),
            ]:
                self._create_stat_card(cards, label, str(value), color)

            body = tk.Frame(win, bg='white', highlightbackground=self.theme['line'], highlightthickness=1)
            body.pack(fill='both', expand=True, padx=18, pady=(4, 14))
            tk.Label(body, text="Khuyến nghị", bg='white',
                     fg=self.theme['TEXT_PRIMARY'], font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=12, pady=(10, 4))
            recs = []
            if pending_docs:
                recs.append(("Hóa đơn", f"Có {pending_docs} chứng từ đang chờ xử lý.", "Duyệt hoặc bổ sung hồ sơ trước khi ghi sổ."))
            if open_advances:
                recs.append(("Tạm ứng", f"Có {open_advances} khoản chưa quyết toán.", "Rà soát hoàn ứng để giảm số dư treo."))
            if month_expense <= 0:
                recs.append(("Chi phí", "Tháng này chưa có chi phí phát sinh.", "Kiểm tra nhập liệu hoặc kỳ báo cáo."))
            for finding in self.utility_mgr.get_accounting_control_findings(limit=4):
                recs.append((
                    finding.get('type', 'Kiểm soát'),
                    finding.get('description', ''),
                    finding.get('recommendation', ''),
                ))
            if not recs:
                recs.append(("Tổng quan", "Dữ liệu không có cảnh báo lớn.", "Tiếp tục theo dõi báo cáo chi phí và dòng tiền."))

            table_wrap = tk.Frame(body, bg='white')
            table_wrap.pack(fill='both', expand=True, padx=12, pady=(0, 12))
            headers = ['Hạng mục', 'Tình trạng', 'Việc nên làm']
            for col_index, header in enumerate(headers):
                tk.Label(table_wrap, text=header, bg='white', fg=self.theme['TEXT_PRIMARY'],
                         font=('Segoe UI', 9, 'bold'), borderwidth=1, relief='solid', padx=8, pady=6).grid(
                             row=0, column=col_index, sticky='nsew', padx=(0 if col_index == 0 else 1, 0), pady=(0, 2))
            table_wrap.columnconfigure(0, weight=1)
            table_wrap.columnconfigure(1, weight=2)
            table_wrap.columnconfigure(2, weight=3)
            for row_index, rec in enumerate(recs, start=1):
                tk.Label(table_wrap, text=rec[0], bg='white', fg=self.theme['TEXT_PRIMARY'],
                         anchor='w', padx=8, pady=6, borderwidth=1, relief='solid').grid(
                             row=row_index, column=0, sticky='nsew', padx=(0, 1), pady=(0, 1))
                tk.Label(table_wrap, text=rec[1], bg='white', fg=self.theme['TEXT_PRIMARY'],
                         anchor='w', padx=8, pady=6, borderwidth=1, relief='solid').grid(
                             row=row_index, column=1, sticky='nsew', padx=1, pady=(0, 1))
                tk.Label(table_wrap, text=rec[2], bg='white', fg=self.theme['TEXT_PRIMARY'],
                         anchor='w', justify='left', wraplength=420, padx=8, pady=6,
                         borderwidth=1, relief='solid').grid(
                             row=row_index, column=2, sticky='nsew', padx=(1, 0), pady=(0, 1))

            action_bar = tk.Frame(win, bg=self.theme['bg'])
            action_bar.pack(fill='x', padx=18, pady=(0, 14))
            create_modern_button(action_bar, "Mở kiểm soát dữ liệu",
                                 lambda: (win.destroy(), self._show_dashboard()),
                                 variant='primary', padx=12, pady=7).pack(side='left')
            create_modern_button(action_bar, "Đóng", win.destroy, variant='outline',
                                 padx=12, pady=7).pack(side='right')

            settings = self.utility_mgr.get_app_settings()
            if str(settings.get('developer_mode', '')).lower() in ('1', 'true', 'yes', 'on'):
                from modules.backup import BackupManager
                stats = BackupManager().get_database_statistics()
                dev_text = "--- Developer Mode ---\n"
                for table, count in stats.items():
                    dev_text += f"{table}: {count}\n"
                tk.Label(body, text=dev_text, bg='white', fg=self.theme['TEXT_MUTED'],
                         font=('Consolas', 9), justify='left').pack(anchor='w', padx=12, pady=(0, 10))
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi: {str(e)}")

    def _optimize_database(self):
        """Tối ưu hóa database."""
        try:
            from modules.backup import DatabaseOptimizer

            from database import get_database_path
            success, msg = DatabaseOptimizer.vacuum_database(get_database_path())
            if success:
                success2, msg2 = DatabaseOptimizer.create_indexes(get_database_path())
                messagebox.showinfo("Thành công", msg + "\n" + msg2)
            else:
                messagebox.showerror("Lỗi", msg)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi: {str(e)}")

    def _show_ai_chat(self):
        """Hiển thị giao diện AI Chat."""
        try:
            from ui.ai_chat_widget import AIChatWidget
        except Exception as exc:
            messagebox.showerror(
                "Lỗi",
                "Trợ lý AI chưa được cài đặt.\n\n"
                "Chạy lệnh:\npip install google-generativeai\n\n"
                f"Chi tiết: {exc}"
            )
            return

        self._clear_content()

        # Tạo widget AI Chat
        ai_widget = AIChatWidget(
            self.content_frame,
            theme=self.theme,
            context_provider=self._build_ai_context_snapshot,
            bg=self.theme['bg'],
        )
        ai_widget.pack(fill='both', expand=True, padx=0, pady=0)

    def _build_ai_context_snapshot(self):
        """Small, safe context packet for the AI assistant."""
        return {
            'screen': self._active_screen_name or 'Tổng quan',
            'user_role': self.current_user.get('role') or '',
            'company': getattr(config, 'COMPANY_NAME', ''),
            'notes': 'Ung dung desktop Tkinter quan ly ke toan, chi phi, vat tu, chung tu va du an xay dung.',
        }

    def _show_about(self):
        """Hiển thị thông tin về ứng dụng."""
        about_text = """
FasTrack ERP - PHẦN MỀM KẾ TOÁN

Phiên bản: 1.0
Ngôn ngữ: Python 3.x
Giao diện: Tkinter

Chức năng:
✓ Hạch toán & quản lý chi phí
✓ Quản lý hóa đơn / chứng từ
✓ Liên kết file chứng từ
✓ Quản lý vật tư / kho
✓ Báo cáo & biểu đồ
✓ Sao lưu & phục hồi
✓ Xuất Excel / PDF

© 2024 Công ty CP Xây dựng và Đầu tư Trung Hải
Phát triển cho: Trung Hải
        """
        messagebox.showinfo("Thông tin ứng dụng", about_text)

    def _create_footer(self):
        footer = tk.Frame(self.root, bg=self.theme['sidebar'], height=28)
        footer.pack(fill='x', side='bottom')
        tk.Label(footer,
                text=f"FasTrack ERP  ·  v1.1  ·  {datetime.now().strftime('%d/%m/%Y')}",
                font=('Segoe UI', 9), fg=self.theme['sidebar_muted'],
                bg=self.theme['sidebar']).pack(pady=5)


# Import messagebox
from tkinter import messagebox
