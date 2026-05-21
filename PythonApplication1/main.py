"""
=============================================================================
PHẦN MỀM QUẢN LÝ KẾ TOÁN - CÔNG TY TRUNG HẢI (ERP SYSTEM)
=============================================================================

CÀI ĐẶT THƯ VIỆN TRƯỚC:
    pip install pandas openpyxl python-docx docxtpl matplotlib pillow google-generativeai

CHỨC NĂNG:
    ✓ Hạch toán & quản lý chi phí
    ✓ Quản lý hóa đơn / chứng từ
    ✓ Liên kết file chứng từ
    ✓ Mẫu chứng từ (in PDF/Word)
    ✓ Quản lý vật tư / kho
    ✓ Báo cáo & biểu đồ thống kê
    ✓ Quản lý dự án xây dựng
    ✓ Quản lý người dùng & quyền hạn

=============================================================================
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import threading
from datetime import datetime
import sqlite3
from pathlib import Path

# Import các module con
from utils.logger import setup_logging, get_logger

# Setup logging early for dependency check and early diagnostics
setup_logging()
logger = get_logger(__name__)

def check_dependencies():
    """Kiểm tra các thư viện bắt buộc."""
    required = ['pandas', 'openpyxl', 'docxtpl', 'matplotlib']
    optional = ['google_generativeai']  # Optional - cho AI Chat
    missing = []

    for lib in required:
        try:
            __import__(lib)
        except ImportError:
            missing.append(lib)

    # Check optional dependencies (không bắt buộc)
    for lib in optional:
        try:
            __import__(lib)
        except ImportError:
            pass  # Bỏ qua nếu không có

    if missing:
        msg = f"Thiếu thư viện bắt buộc: {', '.join(missing)}\n\nChạy lệnh:\npip install {' '.join(missing)}"
        logger.error(msg)
        print(f"❌ {msg}")
        return False
    
    logger.info("All required dependencies are installed")
    return True


def create_app_directories():
    """Tạo các thư mục cần thiết cho ứng dụng."""
    dirs = [
        'data',
        'templates',
        'documents',
        'reports',
        'attachments',
        'backups'
    ]

    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)


def initialize_ai_service_async():
    """Start optional AI service without blocking login/opening the app."""
    def worker():
        try:
            from modules.ai_service import initialize_ai_service
            initialize_ai_service()
            logger.info("AI service initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize AI service: {e}")
            print(f"AI service skipped: {e}")

    thread = threading.Thread(target=worker, name="ai-service-init", daemon=True)
    thread.start()
    return thread


def main():
    """Hàm chính."""
    logger.info("Starting FasTrack ERP application")
    
    # Kiểm tra thư viện
    if not check_dependencies():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Lỗi", "Vui lòng cài đặt các thư viện bắt buộc")
        root.destroy()
        logger.error("Application stopped due to missing dependencies")
        return

    # Setup runtime logging and imports after dependency check
    setup_logging()

    from database import init_database
    from ui.main_window import MainWindow

    # Tạo thư mục
    create_app_directories()
    logger.info("Application directories created/verified")

    # AI service is disabled for this trimmed-down accounting build.
    try:
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Lỗi Database", f"Không thể khởi tạo database: {e}")
        root.destroy()
        return

    # Khởi tạo giao diện chính
    try:
        root = tk.Tk()
        app = MainWindow(root)
        logger.info("Main window created successfully")
        root.mainloop()
        logger.info("Application closed normally")
    except Exception as e:
        logger.error(f"Error in main window: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
