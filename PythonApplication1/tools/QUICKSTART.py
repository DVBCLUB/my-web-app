"""
QUICK START - Hướng dẫn nhanh bắt đầu
"""

# 1. CÀI ĐẶT THƯ VIỆN
# Mở Command Prompt/Terminal và chạy:
# pip install -r requirements.txt

# 2. CHẠY ỨNG DỤNG
# python main.py

# 3. ĐĂNG NHẬP (Tạm thời bỏ qua - sẽ hoàn thiện phần xác thực)
# username: admin
# password: admin

# ====================================================================
# CẤU TRÚC ỨNG DỤNG
# ====================================================================

"""
Dashboard
├─ Thống kê nhanh (Tổng chi phí, Chi phí tháng này, Số dự án, Số chứng từ)
├─ Biểu đồ chi phí theo loại
├─ Chi phí gần đây

Quản Lý Chi Phí
├─ Thêm chi phí mới
├─ Nhập từ Excel
├─ Xuất ra Excel
├─ Xem danh sách chi phí
└─ Lọc/Tìm kiếm

Quản Lý Hóa Đơn/Chứng Từ
├─ Thêm chứng từ mới
├─ Liên kết file
├─ In chứng từ
└─ Xem danh sách chứng từ

Quản Lý Vật Tư
├─ Thêm vật tư
├─ Nhập kho
├─ Xuất kho
└─ Xem tồn kho

Báng Cáo
├─ Báo cáo chi phí chi tiết
├─ Báo cáo theo dự án
├─ Biểu đồ cột
├─ Biểu đồ bánh
├─ Xuất PDF
└─ Xuất Excel

Cài Đặt
├─ Sao lưu dữ liệu
├─ Phục hồi từ sao lưu
├─ Danh sách sao lưu
├─ Thống kê DB
├─ Tối ưu hóa DB
└─ Thông tin ứng dụng
"""

# ====================================================================
# QUICK TIPS - MẸOOĐ NHANH
# ====================================================================

TIPS = {
    'thêm_chi_phí': '''
    1. Nhấn "💰 Chi phí"
    2. Nhấn "➕ Thêm chi phí"
    3. Điền thông tin
    4. Nhấn "💾 Lưu"
    ''',

    'nhập_excel': '''
    1. Nhấn "💰 Chi phí"
    2. Nhấn "📥 Nhập từ Excel"
    3. Chọn file Excel
    4. Hệ thống tự động xử lý

    Format Excel cần có các cột:
    - Ngày
    - Dự án
    - Loại chi phí
    - Mô tả
    - Số tiền
    - Người chi
    - Hình thức (tùy chọn)
    - Ghi chú (tùy chọn)
    ''',

    'xuất_báng_cáo': '''
    1. Nhấn "📈 Báng Cáo"
    2. Chọn "💾 Xuất PDF" hoặc "💾 Xuất Excel"
    3. File sẽ được lưu tự động
    ''',

    'sao_lưu': '''
    1. Nhấn "⚙️ Cài đặt"
    2. Nhấn "🔄 Sao lưu ngay"
    3. Chọn tên file sao lưu
    4. Hoàn tất!
    ''',
}

# ====================================================================
# KEYBOARD SHORTCUTS - PHÍM TẮT
# ====================================================================

SHORTCUTS = {
    'Ctrl+N': 'Thêm mới',
    'Ctrl+S': 'Lưu',
    'Ctrl+E': 'Xuất Excel',
    'Ctrl+P': 'In/In PDF',
    'Ctrl+B': 'Sao lưu',
    'F1': 'Trợ giúp',
}

# ====================================================================
# SETUP LẦN ĐẦU
# ====================================================================

FIRST_TIME_SETUP = '''
Các bước setup lần đầu:

1. ✅ Cài đặt thư viện:
   pip install -r requirements.txt

2. ✅ Chạy ứng dụng:
   python main.py

3. ✅ Tạo tài khoản admin:
   - Đăng nhập với username/password mặc định
   - Vào Cài đặt > Quản lý người dùng
   - Thêm tài khoản admin

4. ✅ Thêm danh mục chi phí:
   - Vào Cài đặt > Danh mục chi phí
   - Thêm các loại chi phí phù hợp với công ty

5. ✅ Thêm dự án:
   - Vào Quản Lý Chi Phí
   - Thêm dự án xây dựng

6. ✅ Tạo mẫu chứng từ:
   - Đặt file mẫu .docx vào thư mục "templates"
   - Định danh các tag {{tag_name}} trong mẫu

7. ✅ Cấu hình sao lưu:
   - Vào Cài đặt > Sao lưu
   - Bật sao lưu tự động (tùy chọn)
'''

print(__doc__)
print(FIRST_TIME_SETUP)

# ====================================================================
# TROUBLESHOOTING - KHẮC PHỤC SỰ CỐ
# ====================================================================

TROUBLESHOOTING = {
    'Lỗi "No module named \'pandas\'"': 'pip install pandas',
    'Lỗi "No module named \'openpyxl\'"': 'pip install openpyxl',
    'Lỗi "No module named \'docxtpl\'"': 'pip install docxtpl',
    'Lỗi "No module named \'matplotlib\'"': 'pip install matplotlib',
    'Database bị hỏng': 'Vào Cài đặt > Phục hồi từ sao lưu',
    'Chậm khi load dữ liệu': 'Vào Cài đặt > Tối ưu hóa DB',
}

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 QUICK START - HƯỚNG DẪN NHANH")
    print("="*60 + "\n")

    print("📋 TIPS NHANH:\n")
    for key, value in TIPS.items():
        print(f"\n{key.upper()}:")
        print(value)

    print("\n\n⌨️  KEYBOARD SHORTCUTS:")
    for key, value in SHORTCUTS.items():
        print(f"  {key:15} → {value}")

    print("\n\n❓ KHẮC PHỤC SỰ CỐ:")
    for problem, solution in TROUBLESHOOTING.items():
        print(f"  • {problem}")
        print(f"    → {solution}\n")
    print("\nChạy phần mềm bằng lệnh: python main.py")
