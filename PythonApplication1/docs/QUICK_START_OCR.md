# Quick Start: Sử dụng OCR trong FasTrack ERP

## ✅ Những gì đã được cải tiến

### 1. **Không còn "Ứng dụng không phản hồi"**
   - OCR chạy trên background thread (không block UI)
   - Bạn có thể hủy OCR bất cứ lúc nào với nút "Hủy"
   - Progress dialog hiển thị trạng thái

### 2. **Nhận diện tốt hơn từ scan điện thoại/máy**
   - 5 biến thể preprocessing (autocontrast, sharpen, threshold, v.v.)
   - Thử nhiều cấu hình Tesseract (PSM 6, 4, 11, legacy)
   - Chọn kết quả tốt nhất dựa trên điểm số
   - Scale ảnh tự động nếu quá nhỏ

### 3. **Timeout & Retry**
   - Mỗi page PDF có 45 giây timeout
   - Nếu vượt quá, skip page (không hang vĩnh viễn)
   - Có thể retry sau

### 4. **Cục bộ tessdata support**
   - Nếu có `PythonApplication1/tessdata/vie.traineddata`, ưu tiên dùng
   - Không cần cài system-wide

---

## 🚀 Cài đặt nhanh (5 phút)

### Bước 1: Cài Python packages
```bash
cd PythonApplication1
pip install -r requirements.txt
```

**Includes:**
- pytesseract (bridge Python → Tesseract)
- pypdfium2 (render PDF)
- pillow (xử lý ảnh)
- pdfplumber (extract text từ PDF)

### Bước 2: Cài Tesseract OCR (Bắt buộc!)

**Windows:**
1. Tải từ: https://github.com/UB-Mannheim/tesseract/wiki/Downloads
2. Tìm file: `tesseract-ocr-w64-setup-v5.x.x.exe`
3. Run installer, chọn:
   - ✅ **Vietnamese (vie)**  ← QUAN TRỌNG
   - ✅ **English (eng)**
4. Install path: `C:\Program Files\Tesseract-OCR` (default)

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Linux:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-vie
```

### Bước 3: Xác nhận cài đặt
```bash
# Nên thấy phiên bản >= 5.0
tesseract --version

# Nên thấy "vie" và "eng"
tesseract --list-langs
```

---

## 📖 Sử dụng OCR

### Quy trình:
1. **Mở FasTrack ERP**
2. **Menu → "Đọc PDF/ảnh OCR"**
3. **Nhấn "Chọn file PDF/ảnh"**
4. **Chọn file** → Progress dialog hiển thị "Đang xử lý..."
5. **Đợi** → Text được trích xuất tự động
6. **Xem kết quả**:
   - Văn bản gốc (OCR) hiển thị bên trái
   - Các trường tự điền: MST, Số HĐ, Ngày, Tổng tiền
   - Độ tin cậy OCR hiển thị bên dưới
7. **Chỉnh sửa** nếu cần (có sai, sửa thủ công)
8. **Nhấn "Lưu thành chứng từ"** → Lưu vào database

### Nút Cancel
- Nếu OCR lâu quá hoặc bạn không cần, nhấn **"Hủy"**
- Dialog sẽ đóng, không pending

---

## ⚠️ Troubleshooting

### Lỗi 1: "Tesseract is not installed"
**Giải pháp:** Cài Tesseract từ bước 2 ở trên

### Lỗi 2: "vie language not installed"
**Giải pháp:** 
- Cài lại Tesseract, chọn Vietnamese
- Hoặc tải `vie.traineddata` từ: https://github.com/tesseract-ocr/tessdata/raw/main/vie.traineddata
- Copy vào: `C:\Program Files\Tesseract-OCR\tessdata\vie.traineddata`

### Lỗi 3: "OCR kết quả sai lệch, nhất là chữ Việt"
**Giải pháp:**
- Ảnh scan phải chất lượng cao (300+ DPI)
- Nên scan chữ đen trên nền trắng
- Tránh bóng, nếp gấp

### Lỗi 4: "OCR lâu hơn 30 giây"
**Giải pháp:**
- Module sẽ timeout tự động sau 45s
- Scan ảnh có kích thước vừa phải (~2000x3000 px)
- Module tự scale nhỏ nếu < 1000px

### Lỗi 5: "ImportError: pytesseract"
**Giải pháp:**
```bash
pip install pytesseract pillow pypdfium2 pdfplumber
```

---

## 🔧 Nâng cao

### Dùng tessdata cục bộ

Nếu muốn bundle tessdata trong project:

1. Tạo folder: `PythonApplication1/tessdata/`
2. Copy file:
   ```
   PythonApplication1/tessdata/vie.traineddata
   PythonApplication1/tessdata/eng.traineddata
   PythonApplication1/tessdata/osd.traineddata
   ```
3. App sẽ tự dùng (ưu tiên hơn system Tesseract)

### Tùy chỉnh timeout

Edit `modules/ocr_enhanced.py`:
```python
class OCRToolEnhanced:
	TIMEOUT_PDF_EXTRACT = 30  # Đổi thành 60 nếu PDF lớn
	TIMEOUT_OCR_PAGE = 45     # Per page
	TIMEOUT_IMAGE = 30
```

### Debug OCR

Enable logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Sẽ hiển thị:
- Variant/config nào được dùng
- Score của mỗi variant
- Warnings

---

## 📚 Tài liệu đầy đủ

Xem chi tiết: `docs/INSTALL_OCR.md`

---

## ❓ FAQ

**Q: Có thể OCR mà không cài Tesseract không?**
A: Không. Tesseract là engine duy nhất. Pytesseract chỉ là wrapper Python.

**Q: Ứng dụng có tự tìm Tesseract không?**
A: Có. Nó sẽ tìm từ:
- PATH system
- `C:\Program Files\Tesseract-OCR\` (Windows)
- `/usr/local/bin/tesseract` (macOS)
- `/usr/bin/tesseract` (Linux)

**Q: Có thể dùng Google Vision API thay vì Tesseract?**
A: Hiện tại là không. Nhưng có thể customize `ocr_enhanced.py` để support sau.

**Q: OCR offline được không?**
A: Có. Tesseract là offline, không cần internet.

---

**Cần trợ giúp?**
- Xem: `docs/INSTALL_OCR.md` (hướng dẫn chi tiết)
- Check logs: Enable `logging.DEBUG`
- Kiểm tra Tesseract: `tesseract --version && tesseract --list-langs`

