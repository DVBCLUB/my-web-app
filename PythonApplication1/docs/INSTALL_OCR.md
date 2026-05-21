# Hướng dẫn cài đặt OCR cho FasTrack ERP

## Vấn đề
Khi bạn muốn chuyển PDF scan hoặc ảnh chụp thành text (OCR), ứng dụng cần hai công cụ chính:
1. **Tesseract OCR** - Engine nhận diện chữ (phần mềm độc lập)
2. **Thư viện Python** - Kết nối Tesseract từ Python (pytesseract, pypdfium2, v.v.)

## 1. Cài đặt Python packages

Chạy lệnh này trong thư mục project:

```bash
pip install -r requirements.txt
```

Packages quan trọng cho OCR:
- `pytesseract` - Wrapper Python cho Tesseract
- `pypdfium2` - Đọc PDF và render sang ảnh
- `pillow>=9.0.0` - Xử lý ảnh, preprocessing
- `pdfplumber` - Extract text trực tiếp từ PDF

## 2. Cài đặt Tesseract OCR

### Windows

#### Cách 1: Cài đặt installer (Khuyến khích)

1. Tải installer từ: https://github.com/UB-Mannheim/tesseract/wiki/Downloads

   Tìm file: `tesseract-ocr-w64-setup-v5.x.x.exe` (64-bit) hoặc v5.x.x.exe (32-bit)

2. Chạy installer và chọn:
   - **Installation folder**: Để mặc định `C:\Program Files\Tesseract-OCR`
   - **Additional language data**: 
	 - ✅ **Vietnamese (vie)** - QUAN TRỌNG cho tài liệu Việt
	 - ✅ **English (eng)**
	 - Các ngôn ngữ khác nếu cần

3. Nhấn Install

#### Cách 2: Cài portable (không cần admin)

1. Tải từ: https://github.com/UB-Mannheim/tesseract/releases

   Tìm file: `tesseract-ocr-w64-...portable.zip`

2. Giải nén vào `C:\Tesseract-OCR` hoặc `C:\Users\<username>\AppData\Local\Tesseract-OCR`

3. Sau đó, ứng dụng sẽ tự tìm và dùng nó

### macOS

```bash
brew install tesseract

# Cài tiếng Việt
brew install tesseract-lang
```

Xác nhận cài được:
```bash
tesseract --version
```

### Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-vie

# Xác nhận
tesseract --version
```

Nếu dùng Docker:
```dockerfile
RUN apt-get install -y tesseract-ocr tesseract-ocr-vie
```

## 3. Cài đặt gói ngôn ngữ (Language Data)

### Windows - Tải thêm Vietnamese (Khuyến khích)

1. Tải file `vie.traineddata` từ: https://github.com/UB-Mannheim/tesseract/tree/main/tessdata

2. Copy vào: `C:\Program Files\Tesseract-OCR\tessdata\vie.traineddata`

3. Hoặc, nếu dùng portable, copy vào: `C:\Tesseract-OCR\tessdata\vie.traineddata`

**Danh sách file quan trọng:**
- `eng.traineddata` - English (thường có sẵn)
- `vie.traineddata` - Vietnamese (cải thiện OCR cho tài liệu Việt)
- `osd.traineddata` - Script orientation detection (tìm hướng chữ)

### Xác nhận gói ngôn ngữ được cài

```bash
tesseract --list-langs
```

Nếu thấy `vie` và `eng`, bạn đã sẵn sàng!

## 4. Kiểm tra cài đặt

Chạy script test:

```python
import pytesseract
from PIL import Image

# Test Tesseract
try:
	text = pytesseract.image_to_string(Image.new('RGB', (100, 100), color='white'))
	print("✅ Tesseract đã cài đúng!")
except Exception as e:
	print(f"❌ Lỗi Tesseract: {e}")

# Test ngôn ngữ
try:
	langs = pytesseract.get_languages()
	print(f"✅ Có {len(langs)} ngôn ngữ: {', '.join(langs)}")
	if 'vie' in langs:
		print("✅ Vietnamese (vie) đã cài!")
	else:
		print("⚠️ Chưa cài Vietnamese - OCR Việt sẽ kém")
except Exception as e:
	print(f"❌ Lỗi kiểm tra ngôn ngữ: {e}")
```

## 5. Sử dụng trong ứng dụng

### Trong OCRImportDialog

1. Mở ứng dụng FasTrack ERP
2. Menu → **Đọc PDF/ảnh OCR**
3. Click **"Chọn file PDF/ảnh"**
4. Chọn file → Ứng dụng sẽ:
   - Hiển thị progress dialog (không đóng UI)
   - Trích xuất text
   - Tự điền các trường: MST, Số HĐ, Ngày, Tổng tiền
   - Hiển thị độ tin cậy

### Các tùy chọn OCR

Nếu kết quả OCR không tốt:

1. **Cải thiện chất lượng ảnh**:
   - Scan ở độ phân giải cao (300 DPI)
   - Chụp ảnh trong ánh sáng tốt
   - Tránh bóng, nếp gấp

2. **Thử lại với scaling**:
   - Module OCR tự scale ảnh nhỏ lên 2-3 lần
   - Nếu vẫn kém, lưu ảnh to hơn

3. **Kiểm tra tessdata**:
   - Chắc chắn `vie.traineddata` ở đúng folder
   - Có thể đặt tessdata local trong project:
	 ```
	 PythonApplication1\tessdata\vie.traineddata
	 PythonApplication1\tessdata\eng.traineddata
	 ```
   - Nếu có local tessdata, app sẽ dùng thay vì system tesseract

## 6. Troubleshooting

### Lỗi: "Tesseract is not installed"

**Giải pháp:**
```python
# Cầu hình đường dẫn thủ công
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### Lỗi: "vie language not installed"

**Giải pháp:**
- Tải `vie.traineddata` từ: https://github.com/UB-Mannheim/tesseract/blob/main/tessdata/vie.traineddata
- Copy vào `C:\Program Files\Tesseract-OCR\tessdata\`
- Hoặc dùng folder local project `PythonApplication1\tessdata\vie.traineddata`

### OCR rất chậm (> 30 giây)

**Nguyên nhân:**
- Ảnh quá to (> 5000x5000 px)
- Tesseract engine cũ

**Giải pháp:**
- Downscale ảnh trước (nên ≤ 3000x3000)
- Module OCR tự optimize: scale nếu < 1000px, giảm scale nếu PDF render quá to
- Timeout: mỗi page có 45 giây, nếu vượt sẽ skip

### Kết quả OCR sai lệch (nhất là tiếng Việt)

**Nguyên nhân:**
- Tessdata không phải bản mới (v5+)
- Ảnh kém chất lượng

**Giải pháp:**
- Update tessdata từ GitHub (v5.0+ tốt hơn)
- Cấu hình preprocessing: module tự thử 5 biến thể ảnh khác nhau
- Nếu vẫn kém, yêu cầu người dùng scan lại ở chất lượng cao hơn

## 7. Cập nhật / Gỡ cài

### Cập nhật Tesseract (Windows)

Đơn giản nhất:
1. Cài installer phiên bản mới
2. Chọn "Repair" trong installer
3. Kiểm tra tessdata được cập nhật

### Gỡ cài (nếu cần)

**Windows:**
- Control Panel → Programs and Features → Tesseract OCR → Remove

**macOS:**
```bash
brew uninstall tesseract
brew uninstall tesseract-lang
```

**Linux:**
```bash
sudo apt-get remove tesseract-ocr tesseract-ocr-vie
```

## 8. Tham khảo

- **Tesseract GitHub:** https://github.com/UB-Mannheim/tesseract
- **Tessdata (ngôn ngữ):** https://github.com/tesseract-ocr/tessdata
- **pytesseract:** https://github.com/madmaze/pytesseract
- **FasTrack ERP OCR Module:** `modules/ocr_enhanced.py`

---

**Notes:**
- Nếu cài đặt đúng, app sẽ tự tìm Tesseract từ PATH hoặc các thư mục chuẩn
- Async OCR sẽ không block UI – bạn có thể hủy bất cứ lúc nào
- Lần đầu OCR sẽ chậm hơn (initialize Tesseract), những lần sau nhanh hơn
