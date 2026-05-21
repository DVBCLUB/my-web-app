# TROUBLESHOOTING - Khắc Phục Sự Cố

## 🔴 Các Lỗi Thường Gặp & Cách Khắc Phục

### 1. Lỗi Import Thư Viện

#### ❌ `ModuleNotFoundError: No module named 'pandas'`

**Nguyên nhân:** Chưa cài đặt thư viện pandas

**Cách khắc phục:**
```bash
pip install pandas
```

#### ❌ `ModuleNotFoundError: No module named 'openpyxl'`

**Cách khắc phục:**
```bash
pip install openpyxl
```

#### ❌ `ModuleNotFoundError: No module named 'docxtpl'`

**Cách khắc phục:**
```bash
pip install docxtpl
```

#### ❌ `ModuleNotFoundError: No module named 'matplotlib'`

**Cách khắc phục:**
```bash
pip install matplotlib
```

**Cài tất cả một lần:**
```bash
pip install -r requirements.txt
```

---

### 2. Lỗi Database

#### ❌ `database is locked`

**Nguyên nhân:** Database đang được dùng bởi process khác

**Cách khắc phục:**
- Đóng tất cả các instance của ứng dụng
- Chờ 30 giây
- Khởi động lại ứng dụng

#### ❌ `database disk image is malformed`

**Nguyên nhân:** Database bị hỏng

**Cách khắc phục:**
1. Vào "⚙️ Cài đặt"
2. Nhấn "⏮️ Phục hồi từ sao lưu"
3. Chọn file sao lưu gần nhất
4. Nhấn "Phục hồi"

Nếu không có sao lưu:
```bash
# Xóa database hỏng
rm data/accounting.db

# Ứng dụng sẽ tạo database mới
python main.py
```

#### ❌ `table xxx does not exist`

**Nguyên nhân:** Database chưa được khởi tạo

**Cách khắc phục:**
```bash
python main.py
# Ứng dụng sẽ tự động tạo các bảng
```

---

### 3. Lỗi Giao Diện

#### ❌ Ứng dụng không khởi động

**Nguyên nhân:** Thiếu thư viện hoặc lỗi trong config

**Cách khắc phục:**
1. Chạy setup checker:
```bash
python setup_checker.py
```

2. Cài đặt thư viện thiếu
3. Khởi động lại ứng dụng

#### ❌ Biểu đồ không hiển thị

**Nguyên nhân:** Matplotlib chưa cài đặt hoặc cấu hình sai

**Cách khắc phục:**
```bash
pip install matplotlib
pip install pillow
```

#### ❌ Font chữ không hiển thị đúng

**Nguyên nhân:** Font không hỗ trợ Tiếng Việt

**Cách khắc phục:** (Tự động xử lý - không cần làm gì)

---

### 4. Lỗi Nhập/Xuất Dữ Liệu

#### ❌ Lỗi khi nhập Excel

**Nguyên nhân:** File Excel không đúng format hoặc thiếu cột

**Cách khắc phục:**
1. Kiểm tra file Excel có các cột:
   - Ngày
   - Dự án
   - Loại chi phí
   - Mô tả
   - Số tiền
   - Người chi

2. Kiểm tra định dạng ngày: DD/MM/YYYY

3. Thử lại nhập dữ liệu

#### ❌ Lỗi khi xuất PDF

**Nguyên nhân:** ReportLab chưa cài đặt

**Cách khắc phục:**
```bash
pip install reportlab
```

#### ❌ Lỗi khi xuất Excel

**Nguyên nhân:** File Excel đang được mở

**Cách khắc phục:**
1. Đóng file Excel
2. Thử xuất lại

---

### 5. Lỗi Hiệu Suất

#### ❌ Ứng dụng chạy chậm

**Nguyên nhân:** Database quá lớn hoặc không được tối ưu

**Cách khắc phục:**
1. Vào "⚙️ Cài đặt"
2. Nhấn "🧹 Tối ưu hóa DB"
3. Chờ quá trình hoàn tất

#### ❌ Mất một lúc để load danh sách

**Cách khắc phục:**
- Database được tối ưu hóa tự động
- Nếu vẫn chậm, sử dụng filter/tìm kiếm

#### ❌ Báo cáo mất lâu để tạo

**Cách khắc phục:**
- Giảm khoảng thời gian báo cáo
- Dùng filter để giảm dữ liệu

---

### 6. Lỗi Xác Thực

#### ❌ Quên mật khẩu

**Cách khắc phục:**
- Đặt lại mật khẩu (tính năng sắp có)
- Hoặc xóa database và khởi tạo lại

#### ❌ Không thể đăng nhập

**Nguyên nhân:** Sai username/password

**Cách khắc phục:**
1. Kiểm tra Username: admin
2. Kiểm tra Password (mặc định)
3. Hoặc xóa database khôi tạo lại

---

### 7. Lỗi Sao Lưu

#### ❌ Không thể sao lưu

**Nguyên nhân:** Thư mục backups không có quyền ghi

**Cách khắc phục:**
1. Kiểm tra quyền folder `backups`
2. Cấp quyền: `chmod 755 backups` (Linux/Mac)
3. Thử sao lưu lại

#### ❌ Không thể phục hồi

**Nguyên nhân:** File sao lưu bị hỏng hoặc không có quyền

**Cách khắc phục:**
1. Kiểm tra file sao lưu có tồn tại
2. Cấp quyền file
3. Thử phục hồi lại

---

## 🟢 Các Mẹo Hữu Ích

### 1. Kiểm tra setup lần đầu
```bash
python setup_checker.py
```

### 2. Xem thông tin phiên bản
```bash
python -c "import sys; print(f'Python {sys.version}')"
```

### 3. Xem thống kê database
```
⚙️ Cài đặt → 📈 Xem thống kê
```

### 4. Dùng backup thường xuyên
```
⚙️ Cài đặt → 🔄 Sao lưu ngay
```

### 5. Tối ưu database định kỳ
```
⚙️ Cài đặt → 🧹 Tối ưu hóa DB
```

---

## 📞 Liên Hệ Hỗ Trợ

Nếu vẫn gặp sự cố:

1. **Xem log file**
   ```
   logs/app.log
   ```

2. **Chạy setup checker**
   ```bash
   python setup_checker.py
   ```

3. **Liên hệ IT team**
   - Email: support@trunghai.vn
   - Hotline: 0XXX-XXX-XXX

4. **Cung cấp thông tin:**
   - Python version
   - OS (Windows/Mac/Linux)
   - Error message
   - Steps to reproduce

---

## 🔄 Khôi Phục Toàn Bộ Hệ Thống

Nếu tất cả đều không hoạt động:

### Step 1: Backup dữ liệu
```bash
cp -r data backups/emergency_backup_$(date +%s)
```

### Step 2: Xóa database
```bash
rm data/accounting.db
```

### Step 3: Xóa cache Python
```bash
find . -type d -name __pycache__ -exec rm -r {} +
find . -type f -name "*.pyc" -delete
```

### Step 4: Cài đặt lại thư viện
```bash
pip install --upgrade --force-reinstall -r requirements.txt
```

### Step 5: Khởi động ứng dụng
```bash
python main.py
```

---

## 📋 Checklist Kiểm Tra

- [ ] Python 3.8+ đã cài đặt
- [ ] Tất cả thư viện trong requirements.txt đã cài
- [ ] Thư mục `data` có tồn tại
- [ ] Database file được tạo
- [ ] Ứng dụng khởi động được
- [ ] Có thể đăng nhập
- [ ] Dashboard hiển thị bình thường
- [ ] Có thể thêm chi phí
- [ ] Có thể xuất báo cáo
- [ ] Có thể sao lưu

---

**Cập nhật lần cuối:** 2024-01-XX
**Phiên bản:** 1.0
