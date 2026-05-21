"""
CONFIG - Cấu hình ứng dụng
"""

import os
from pathlib import Path

# ── ĐỦ CẤP HỆ THỐNG ────────────────────────────────────
APP_NAME = "FasTrack ERP"
APP_VERSION = "1.0.0"
COMPANY_NAME = "Công ty CP Xây dựng và Đầu tư Trung Hải"

# ── ĐƯỜNG DẪN ──────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
TEMPLATES_DIR = BASE_DIR / 'templates'
DOCUMENTS_DIR = BASE_DIR / 'documents'
REPORTS_DIR = BASE_DIR / 'reports'
ATTACHMENTS_DIR = BASE_DIR / 'attachments'
BACKUPS_DIR = BASE_DIR / 'backups'

# Tạo các thư mục nếu chưa tồn tại
for dir_path in [DATA_DIR, TEMPLATES_DIR, DOCUMENTS_DIR, REPORTS_DIR, ATTACHMENTS_DIR, BACKUPS_DIR]:
    dir_path.mkdir(exist_ok=True)

# ── DATABASE ───────────────────────────────────────────
DB_PATH = DATA_DIR / 'accounting.db'
DB_BACKUP_DIR = BACKUPS_DIR

# ── CẤU HÌNH GIAO DIỆN ─────────────────────────────────
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 700
WINDOW_GEOMETRY = f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"

# Màu sắc
COLORS = {
    'primary': '#1a56a5',
    'secondary': '#2c3e50',
    'success': '#27ae60',
    'danger': '#e74c3c',
    'warning': '#f39c12',
    'info': '#3498db',
    'light': '#ecf0f1',
    'dark': '#34495e',
    'background': '#f0f4f8',
}

# Font mặc định
FONTS = {
    'title': ('Arial', 16, 'bold'),
    'heading': ('Arial', 14, 'bold'),
    'subheading': ('Arial', 12, 'bold'),
    'normal': ('Arial', 10),
    'small': ('Arial', 9),
    'mono': ('Courier', 10),
}

# ── CẤU HÌNH VÀI TRÒ & QUYỀN ───────────────────────────
ROLES = {
    'admin': {
        'name': 'Quản trị viên',
        'permissions': [
            'view_all', 'create_all', 'edit_all', 'delete_all',
            'manage_users', 'manage_reports', 'manage_backup'
        ]
    },
    'accountant': {
        'name': 'Kế toán',
        'permissions': [
            'view_all', 'create_expense', 'edit_expense',
            'view_report', 'create_document', 'edit_document'
        ]
    },
    'manager': {
        'name': 'Quản lý',
        'permissions': [
            'view_all', 'view_report', 'approve_expense'
        ]
    },
    'employee': {
        'name': 'Nhân viên',
        'permissions': [
            'view_own', 'create_expense'
        ]
    },
}

# ── DANH MỤC CHI PHÍ ───────────────────────────────────
EXPENSE_CATEGORIES = {
    'VT': ('Vật tư', None),
    'VT.BT': ('Vật liệu xây dựng', 'VT'),
    'VT.TP': ('Vật tư phụ', 'VT'),
    'NK': ('Nhân công', None),
    'NK.TU': ('Nhân công tự do', 'NK'),
    'NK.HT': ('Nhân công hợp tác', 'NK'),
    'MM': ('Máy móc - Thiết bị', None),
    'MM.TC': ('Thuê máy xúc', 'MM'),
    'MM.BD': ('Bảo dưỡng máy', 'MM'),
    'VT.KH': ('Vận tải - Khác', None),
}

# ── HÌNH THỨC THANH TOÁN ───────────────────────────────
PAYMENT_METHODS = [
    'Tiền mặt',
    'Chuyển khoản',
    'Séc',
    'Thẻ tín dụng',
    'Khác'
]

# ── LOẠI CHỨNG TỪ ──────────────────────────────────────
DOCUMENT_TYPES = [
    'Hóa đơn',
    'Phiếu chi',
    'Phiếu nhập',
    'Phiếu xuất',
    'Chứng từ khác'
]

# ── TRẠNG THÁI CHỨNG TỪ ────────────────────────────────
DOCUMENT_STATUS = {
    'draft': 'Nháp',
    'submitted': 'Đã nộp',
    'approved': 'Đã duyệt',
    'paid': 'Đã thanh toán',
    'rejected': 'Từ chối',
}

# ── TRẠNG THÁI CHI PHÍ ─────────────────────────────────
EXPENSE_STATUS = {
    'pending': 'Chờ duyệt',
    'approved': 'Đã duyệt',
    'paid': 'Đã thanh toán',
    'posted': 'Đã ghi sổ',
    'rejected': 'Từ chối',
}

# ── KẾ TOÁN DỰ ÁN / CÔNG TRÌNH ─────────────────────────
CONTRACT_TYPES = {
    'customer': 'Hợp đồng thi công (chủ đầu tư)',
    'subcontract': 'Hợp đồng thầu phụ',
    'supply': 'Hợp đồng cung cấp vật tư',
}

BILLING_STATUS = {
    'draft': 'Nháp',
    'submitted': 'Đã nộp',
    'approved': 'Đã duyệt',
    'paid': 'Đã thanh toán',
}

PROJECT_TYPES = {
    'construction': 'Công trình xây dựng',
    'investment': 'Đầu tư',
    'office': 'Văn phòng / chi phí chung',
}

# ── CẤU HÌNH SAO LƯU ───────────────────────────────────
AUTO_BACKUP_ENABLED = True
AUTO_BACKUP_INTERVAL_HOURS = 24  # Sao lưu mỗi 24 giờ
SESSION_TIMEOUT_MINUTES = 30
BACKUP_RETENTION_DAYS = 30  # Giữ sao lưu trong 30 ngày

# ── CẤU HÌNH BÁNG CÁO ──────────────────────────────────
REPORT_FORMAT = 'PDF'  # PDF hoặc Excel
PAGE_SIZE = 'A4'
MARGIN_TOP = 20
MARGIN_BOTTOM = 20
MARGIN_LEFT = 20
MARGIN_RIGHT = 20

# ── NGÔN NGỮ ───────────────────────────────────────────
DEFAULT_LANGUAGE = 'vi'  # Tiếng Việt

# ── CẤU HÌNH LOG ───────────────────────────────────────
LOG_LEVEL = 'INFO'
LOG_FILE = BASE_DIR / 'logs' / 'app.log'
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5

# Logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d]: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'level': LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'level': LOG_LEVEL,
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'detailed',
            'filename': str(LOG_FILE),
            'maxBytes': LOG_MAX_SIZE,
            'backupCount': LOG_BACKUP_COUNT,
            'encoding': 'utf-8'
        },
    },
    'loggers': {
        '': {  # Root logger
            'handlers': ['console', 'file'],
            'level': LOG_LEVEL,
            'propagate': False
        },
        'database': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False
        },
    }
}

# Tạo thư mục logs
LOG_FILE.parent.mkdir(exist_ok=True)

# ── CẤU HÌNH GOOGLE GEMINI AI ──────────────────────────
# API Key - Lấy từ environment hoặc file cấu hình riêng
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
GEMINI_ENABLED = bool(GEMINI_API_KEY)

# Unified AI providers. These are optional and read from environment by default,
# so adding providers does not make the desktop app heavier at startup.
AI_DEFAULT_PROVIDER = os.getenv('AI_PROVIDER', 'gemini')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-3-5-haiku-latest')
COPILOT_API_KEY = os.getenv('COPILOT_API_KEY', '')
COPILOT_MODEL = os.getenv('COPILOT_MODEL', 'openai/gpt-4.1-mini')
COPILOT_BASE_URL = os.getenv('COPILOT_BASE_URL', 'https://models.github.ai/inference/chat/completions')

# Cấu hình AI chat
AI_CHAT_ENABLED = False
AI_SYSTEM_PROMPT = """Bạn là một trợ lý kế toán thông minh cho phần mềm quản lý kế toán FasTrack ERP.
Bạn có kiến thức sâu về:
- Kế toán tài chính
- Quản lý chi phí dự án xây dựng
- Hóa đơn, chứng từ, phiếu chi
- Báo cáo tài chính
- Quy định kế toán Việt Nam

Hãy trả lời các câu hỏi một cách chuyên nghiệp, rõ ràng và hỗ trợ người dùng với các khuyến nghị."""

AI_MAX_HISTORY = 20  # Số lượng tin nhắn lịch sử tối đa
AI_RESPONSE_TIMEOUT = 30  # Timeout cho response (giây)
