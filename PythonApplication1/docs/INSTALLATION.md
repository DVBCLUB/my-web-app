# 📦 Hướng dẫn Cài đặt & Tích hợp Gemini AI

## 📋 Mục lục
1. [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
2. [Cài đặt bước 1: Dependencies](#cài-đặt-bước-1-dependencies)
3. [Cài đặt bước 2: API Key](#cài-đặt-bước-2-api-key)
4. [Cài đặt bước 3: Khởi động](#cài-đặt-bước-3-khởi-động)
5. [Xác minh cài đặt](#xác-minh-cài-đặt)
6. [Khắc phục sự cố](#khắc-phục-sự-cố)

---

## ✅ Yêu cầu hệ thống

- **Python:** 3.8 trở lên
- **OS:** Windows, macOS, hoặc Linux
- **Internet:** Kết nối để gọi Gemini API
- **Tài khoản:** Google Account (để lấy API Key)

---

## 🔧 Cài đặt bước 1: Dependencies

### Cách A: Automatic (Khuyến nghị)

**Windows:**
```bash
SETUP_GEMINI_AI.bat
```

**macOS/Linux:**
```bash
pip install -r requirements.txt
```

### Cách B: Manual

```bash
pip install google-generativeai>=0.3.0
```

Hoặc cài tất cả:
```bash
pip install -r requirements.txt
```

### ✓ Kiểm tra cài đặt

```bash
python test_ai_service.py
```

Kết quả mong đợi:
```
✅ Tất cả test thành công!
```

---

## 🔑 Cài đặt bước 2: API Key

### Lấy API Key

1. **Truy cập:** https://aistudio.google.com/app/apikey
2. **Đăng nhập:** Sử dụng tài khoản Google
3. **Tạo Key:** Nhấp "Create API Key"
4. **Sao chép:** Copy API Key (không chia sẻ công khai)

![API Key Steps](https://ai.google.dev/images/guides/api-key.png)

### Cấu hình API Key

**Cách 1: Từ ứng dụng (✅ Khuyến nghị)**
- Chạy: `python main.py`
- Menu → "🤖 Trợ lý AI"
- Nhấp "⚙ Cấu hình API"
- Dán API Key → "Kết nối & Lưu"

**Cách 2: Biến môi trường (🔐 Bảo mật)**

Windows PowerShell:
```powershell
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "your-api-key-here", "User")
```

Windows Command Prompt:
```cmd
setx GEMINI_API_KEY your-api-key-here
```

macOS/Linux:
```bash
export GEMINI_API_KEY=your-api-key-here
echo 'export GEMINI_API_KEY=your-api-key-here' >> ~/.bashrc
```

**Cách 3: File config.py (⚠️ Cẩn thận)**
```python
# config.py
GEMINI_API_KEY = "your-api-key-here"
```
⚠️ **Cảnh báo:** Không commit key vào version control!

---

## 🚀 Cài đặt bước 3: Khởi động

### Chạy ứng dụng

```bash
python main.py
```

### Truy cập AI Chat

1. Mở ứng dụng FasTrack ERP
2. Menu bên trái, phần "TỔNG QUAN"
3. Nhấp "🤖 Trợ lý AI"

### Bắt đầu chat

```
[Nhập câu hỏi]: Tính thuế TNDN như thế nào?
[Nhấn Ctrl+Enter]
[Chờ phản hồi...]
🤖 AI: [Trả lời chi tiết...]
```

---

## ✔️ Xác minh cài đặt

### Test 1: Python & Dependencies

```bash
python test_ai_service.py
```

Kết quả:
```
✅ Tất cả test thành công!
```

### Test 2: Import Modules

```bash
python -c "from modules.ai_service import get_ai_service; print('✓ Import OK')"
```

### Test 3: Cấu hình

```bash
python -c "import config; print(f'Model: {config.GEMINI_MODEL}')"
```

### Test 4: Service Creation

```bash
python -c "from modules.ai_service import GeminiAIService; s = GeminiAIService(); print('✓ Service OK')"
```

---

## 🆘 Khắc phục sự cố

### Lỗi: "ModuleNotFoundError: No module named 'google.generativeai'"

**Giải pháp:**
```bash
pip install google-generativeai
```

### Lỗi: "API Key không hợp lệ"

**Giải pháp:**
1. Kiểm tra API Key tại: https://aistudio.google.com/app/apikey
2. Đảm bảo sao chép đầy đủ (không có khoảng trắng)
3. Thử tạo API Key mới

### Lỗi: "ConnectionError" hoặc "Timeout"

**Giải pháp:**
1. Kiểm tra kết nối internet
2. Thử lại sau vài phút
3. Kiểm tra trạng thái Google Gemini API

### Lỗi: "AttributeError: module 'ai_service' has no attribute..."

**Giải pháp:**
1. Kiểm tra tệp `ai_service.py` không bị sửa đổi sai
2. Xóa file `.pyc`: `del PythonApplication1\__pycache__\ai_service.*`
3. Khởi động lại ứng dụng

### UI không hiển thị "🤖 Trợ lý AI"

**Giải pháp:**
1. Kiểm tra file `ui/main_window.py` có import `AIChatWidget` không
2. Kiểm tra file `ui/ai_chat_widget.py` tồn tại không
3. Xóa cache: `rmdir /s __pycache__` (Windows)

### AI phản hồi chậm

**Giải pháp:**
1. Kiểm tra kết nối internet
2. Thử câu hỏi đơn giản hơn
3. Kiểm tra giới hạn API: https://aistudio.google.com/app/usageinfo

### "Chưa cấu hình API Key"

**Giải pháp:**
1. Lấy API Key mới tại: https://aistudio.google.com/app/apikey
2. Nhấp "⚙ Cấu hình API" trong ứng dụng
3. Dán API Key đầy đủ
4. Nhấp "Kết nối & Lưu"

---

## 🔐 Bảo mật

### Quy tắc an toàn

✅ **Nên làm:**
- Sử dụng biến môi trường cho API Key
- Giữ API Key bí mật
- Không commit API Key vào repository
- Thay đổi API Key định kỳ

❌ **Không nên làm:**
- Chia sẻ API Key công khai
- Để API Key trong config.py
- Push API Key lên GitHub
- Sử dụng API Key cũ

### Giới hạn API

- **Miễn phí:** 15 lệnh gọi/phút
- **Chi phí:** $0.075/1000 input tokens, $0.30/1000 output tokens
- **Theo dõi:** https://aistudio.google.com/app/usageinfo

---

## 📞 Hỗ trợ

### Logs

Xem log chi tiết:
```bash
cat PythonApplication1/logs/app.log
```

### Tài liệu

- **QUICK_START_AI.md** - Cách nhanh
- **AI_CHAT_GUIDE.md** - Hướng dẫn chi tiết
- **README_AI.md** - Tổng quan
- **GEMINI_INTEGRATION_SUMMARY.md** - Chi tiết kỹ thuật

### Liên hệ

1. Kiểm tra log file
2. Chạy `test_ai_service.py`
3. Liên hệ nhóm phát triển

---

## 📅 Lịch sử thay đổi

### v1.0 (2024)
- Tích hợp Google Gemini API
- Chat widget tương tác
- Cấu hình API Key từ UI
- Lịch sử chat & xuất lịch sử
- Hỗ trợ Tiếng Việt

---

**✅ Cài đặt hoàn tất! Bây giờ bạn có thể sử dụng Trợ lý AI. 🚀**
