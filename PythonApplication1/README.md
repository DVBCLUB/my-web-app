# 💼 ERP QUẢN LÝ KẾ TOÁN - CÔNG TY TRUNG HẢI

## 📌 Giới Thiệu

Phần mềm ERP toàn diện cho công ty xây dựng, hỗ trợ:
- ✅ Hạch toán & quản lý chi phí
- ✅ Quản lý hóa đơn / chứng từ
- ✅ Liên kết file chứng từ
- ✅ Quản lý vật tư & kho
- ✅ Báo cáo & biểu đồ thống kê
- ✅ Sao lưu & phục hồi dữ liệu
- ✅ Xuất báo cáo Excel/PDF

---

## 🚀 Cài Đặt & Chạy

### 1. Yêu cầu hệ thống
- Python 3.8+
- Windows/Mac/Linux

### 2. Cài đặt thư viện

```bash
pip install pandas openpyxl python-docx docxtpl matplotlib pillow reportlab
```

### 3. Chạy ứng dụng

```bash
python main.py
```

---

## 📁 Cấu Trúc Dự Án

```
PythonApplication1/
├── main.py                    # File chính
├── database/                  # Quản lý database
│   └── __init__.py
├── modules/                   # Các module chức năng
│   ├── accounting.py         # Quản lý kế toán
│   ├── invoices.py          # Quản lý chứng từ
│   ├── materials.py         # Quản lý vật tư
│   ├── reports.py           # Báo cáo & biểu đồ
│   ├── auth.py              # Xác thực & quyền
│   ├── backup.py            # Sao lưu & phục hồi
│   └── pdf_export.py        # Xuất PDF
├── ui/                        # Giao diện người dùng
│   ├── main_window.py       # Cửa sổ chính
│   ├── dialogs.py           # Hộp thoại form
│   └── __init__.py
├── utils/                     # Hàm tiện ích
│   └── __init__.py
├── data/                      # Database SQLite
├── templates/                 # Mẫu chứng từ Word
├── documents/                 # Chứng từ được tạo
├── reports/                   # Báo cáo PDF
└── backups/                   # File sao lưu
```

---

## 💻 Các Tính Năng Chi Tiết

### 1. **Dashboard (Trang chủ)**
- Thống kê nhanh chi phí
- Biểu đồ chi phí theo loại
- Danh sách chi phí gần đây

### 2. **Quản Lý Chi Phí**
- Thêm/Sửa/Xóa chi phí
- Nhập dữ liệu từ Excel
- Xuất chi phí ra Excel
- Phân loại theo dự án/loại chi phí
- Theo dõi trạng thái (pending/approved/paid)

### 3. **Quản Lý Hóa Đơn/Chứng Từ**
- Tạo phiếu chi, hóa đơn
- Liên kết file đính kèm
- Tạo số chứng từ tự động
- Quản lý mẫu chứng từ Word
- In chứng từ PDF

### 4. **Quản Lý Vật Tư**
- Thêm vật tư mới
- Theo dõi tồn kho
- Ghi nhận nhập/xuất kho
- Lịch sử giao dịch kho
- Tính giá trị vật tư theo dự án

### 5. **Báo Cáo & Biểu Đồ**
- Báo cáo chi phí chi tiết
- Báo cáo tài chính
- Biểu đồ cột (chi phí theo loại)
- Biểu đồ bánh (chi phí theo dự án)
- Xuất báo cáo Excel
- Xuất báo cáo PDF

### 6. **Sao Lưu & Phục Hồi**
- Sao lưu tự động/thủ công
- Danh sách các bộ sao lưu
- Phục hồi từ file sao lưu
- Tối ưu hóa database
- Tạo index truy vấn

### 7. **Cài Đặt Hệ Thống**
- Quản lý người dùng
- Phân quyền hệ thống
- Thống kê database
- Tối ưu hóa hệ thống

---

## 📊 Cơ Sở Dữ Liệu

### Các Bảng Chính

| Bảng | Chức năng |
|------|---------|
| `users` | Lưu thông tin người dùng |
| `projects` | Quản lý dự án xây dựng |
| `expenses` | Quản lý chi phí |
| `expense_categories` | Danh mục chi phí |
| `documents` | Quản lý hóa đơn/chứng từ |
| `attachments` | File đính kèm |
| `materials` | Quản lý vật tư |
| `inventory_transactions` | Giao dịch kho |
| `accounts` | Tài khoản kế toán |
| `journal_entries` | Bút toán |

---

## 🔐 Quản Lý Quyền Hạn

### Các Role (Vai Trò)

```python
ROLES = {
	'admin': ['view_all', 'create_all', 'edit_all', 'delete_all', 'manage_users'],
	'accountant': ['view_all', 'create_expense', 'edit_expense', 'view_report'],
	'manager': ['view_all', 'view_report', 'approve_expense'],
	'employee': ['view_own', 'create_expense'],
}
```

---

## 📝 Hướng Dẫn Sử Dụng Chi Tiết

### Thêm Chi Phí Mới
1. Vào menu "💰 Chi phí"
2. Nhấn "➕ Thêm chi phí"
3. Điền đầy đủ thông tin:
   - Ngày chi
   - Dự án
   - Loại chi phí
   - Mô tả
   - Số tiền
   - Người chi
   - Ghi chú
4. Nhấn "💾 Lưu"

### Nhập Dữ Liệu Từ Excel
1. Vào menu "💰 Chi phí"
2. Nhấn "📥 Nhập từ Excel"
3. Chọn file Excel
4. Hệ thống sẽ tự động xử lý

### Xuất Báo Cáo
1. Vào menu "📈 Báo cáo"
2. Chọn:
   - "💾 Xuất PDF" → Xuất báo cáo PDF
   - "💾 Xuất Excel" → Xuất báo cáo Excel

### Sao Lưu Dữ Liệu
1. Vào menu "⚙️ Cài đặt"
2. Nhấn "🔄 Sao lưu ngay"
3. Chọn tên file sao lưu (tự động hoặc tùy chỉnh)

---

## 🐛 Khắc Phục Sự Cố

### Lỗi "No module named 'pandas'"
```bash
pip install pandas
```

### Lỗi "No module named 'reportlab'"
```bash
pip install reportlab
```

### Database bị hỏng
1. Vào "⚙️ Cài đặt"
2. Nhấn "⏮️ Phục hồi từ sao lưu"
3. Chọn file sao lưu gần nhất

---

## 📧 Liên Hệ & Hỗ Trợ

- **Email**: support@trunghai.vn
- **Hotline**: 0XXX-XXX-XXX
- **Website**: www.trunghai.vn

---

## 📄 License

© 2024 Công ty CP Xây dựng và Đầu tư Trung Hải

---

## 🎯 Roadmap Phát Triển

- [ ] Ứng dụng Mobile (Android/iOS)
- [ ] Đồng bộ dữ liệu Cloud
- [ ] Tích hợp Ngân hàng (API)
- [ ] OCR hóa đơn tự động
- [ ] AI phân tích chi phí
- [ ] Cảnh báo dự toán thực hiện
- [ ] Dashboard biểu đồ nâng cao

---

**Phiên bản hiện tại:** 1.0  
**Cập nhật lần cuối:** 01/2024
