"""
SETUP CHECKER - Kiểm tra các thành phần setup
"""

import sys
from pathlib import Path

def check_python_version():
    """Kiểm tra phiên bản Python."""
    version = sys.version_info
    required = (3, 8)

    if version >= required:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} (Yêu cầu >= 3.8)")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor} (Yêu cầu >= 3.8)")
        return False


def check_directories():
    """Kiểm tra và tạo các thư mục."""
    dirs = [
        'data',
        'templates',
        'documents',
        'reports',
        'attachments',
        'backups',
        'logs'
    ]

    print("\n📁 Kiểm tra thư mục:")
    all_ok = True

    for dir_name in dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"  ✅ {dir_name}/ (đã tồn tại)")
        else:
            dir_path.mkdir(exist_ok=True)
            print(f"  ✅ {dir_name}/ (đã tạo)")

    return all_ok


def check_dependencies():
    """Kiểm tra các thư viện cần thiết."""
    print("\n📦 Kiểm tra thư viện:")

    required_libs = {
        'tkinter': 'Tkinter',
        'sqlite3': 'SQLite3',
        'pandas': 'Pandas',
        'openpyxl': 'OpenPyXL',
        'docx': 'python-docx',
        'docxtpl': 'docxtpl',
        'matplotlib': 'Matplotlib',
        'PIL': 'Pillow',
        'reportlab': 'ReportLab',
    }

    missing = []

    for module, name in required_libs.items():
        try:
            __import__(module)
            print(f"  ✅ {name:20} (đã cài đặt)")
        except ImportError:
            print(f"  ❌ {name:20} (CHƯA CÀI)")
            missing.append(name)

    if missing:
        print(f"\n⚠️  Các thư viện cần cài đặt:")
        print(f"    pip install {' '.join([lib.lower() for lib in missing])}")
        return False

    return True


def check_database():
    """Kiểm tra database."""
    print("\n🗄️  Kiểm tra Database:")

    db_path = Path('data/accounting.db')

    if db_path.exists():
        size = db_path.stat().st_size
        print(f"  ✅ Database tồn tại (Kích thước: {size:,} bytes)")
        return True
    else:
        print(f"  ℹ️  Database chưa tạo (sẽ tạo lần đầu khởi động)")
        return True


def check_config():
    """Kiểm tra file cấu hình."""
    print("\n⚙️  Kiểm tra Cấu hình:")

    config_files = [
        'config.py',
        'main.py',
        'requirements.txt'
    ]

    all_exist = True
    for file_name in config_files:
        file_path = Path(file_name)
        if file_path.exists():
            print(f"  ✅ {file_name}")
        else:
            print(f"  ❌ {file_name} (THIẾU)")
            all_exist = False

    return all_exist


def main():
    """Chạy kiểm tra đầy đủ."""
    print("""
╔═════════════════════════════════════════════════════════════════╗
║     🔍 KIỂM TRA CÀI ĐẶT - ERP QUẢN LÝ KẾ TOÁN TRUNG HẢI     ║
╚═════════════════════════════════════════════════════════════════╝
    """)

    checks = [
        ("Python Version", check_python_version),
        ("Directories", check_directories),
        ("Dependencies", check_dependencies),
        ("Database", check_database),
        ("Configuration", check_config),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Lỗi kiểm tra {name}: {str(e)}")
            results.append((name, False))

    # Tóm tắt
    print("\n" + "═" * 65)
    print("\n📋 TÓM TẮT:\n")

    all_passed = all(result for _, result in results)

    for name, result in results:
        status = "✅ OK" if result else "❌ LỖI"
        print(f"  {name:30} {status}")

    print("\n" + "═" * 65)

    if all_passed:
        print("""
✨ SETUP HOÀN HẢO! ✨

Bạn có thể chạy ứng dụng bằng lệnh:
  python main.py
        """)
    else:
        print("""
⚠️  CÓ MỘT SỐ VẤNĐỀ CẦN KHẮC PHỤC

Vui lòng xem lỗi ở trên và chạy lệnh cài đặt:
  pip install -r requirements.txt
        """)

    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
