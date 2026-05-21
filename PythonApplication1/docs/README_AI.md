# 🤖 FasTrack ERP - Tích hợp Gemini AI

## 📌 Quick Start

### 1️⃣ Cài đặt
```bash
pip install google-generativeai
```

### 2️⃣ Lấy API Key
Truy cập: https://aistudio.google.com/app/apikey

### 3️⃣ Chạy ứng dụng
```bash
python main.py
```

### 4️⃣ Sử dụng AI Chat
- Menu → "🤖 Trợ lý AI"
- Nhấp "⚙ Cấu hình API"
- Dán API Key → "Kết nối & Lưu"
- Bắt đầu chat!

## 🎯 Tính năng

✅ **Chat tương tác** - Cuộc hội thoại liên tục  
✅ **Tư vấn kế toán** - Trả lời về thuế, hạch toán  
✅ **Phân tích dữ liệu** - Giúp phân tích số liệu tài chính  
✅ **Tiếng Việt** - Giao diện & phản hồi hoàn toàn bằng Tiếng Việt  
✅ **Lịch sử chat** - Lưu trữ tối đa 20 tin nhắn  

## 📂 Cấu trúc tệp

```
PythonApplication1/
├── ai_service.py              # Module AI chính
├── ui/ai_chat_widget.py       # Widget giao diện
├── config.py                  # Cấu hình (có GEMINI_API_KEY)
├── main.py                    # Khởi tạo AI service
├── ui/main_window.py          # Tích hợp vào menu
├── AI_CHAT_GUIDE.md           # Hướng dẫn sử dụng chi tiết
├── GEMINI_INTEGRATION_SUMMARY.md # Tóm tắt tích hợp
├── SETUP_GEMINI_AI.bat        # Script setup
└── requirements.txt           # Dependencies
```

## 🔑 Cấu hình API Key

### Cách 1: Từ ứng dụng (✅ Khuyến nghị)
```
Menu → Trợ lý AI → ⚙ Cấu hình API → Dán API Key
```

### Cách 2: Biến môi trường (🔐 Bảo mật)
```powershell
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "sk-your-key", "User")
```

### Cách 3: File config (⚠️ Cẩn thận)
```python
# config.py
GEMINI_API_KEY = "sk-your-key"
```

## 💬 Ví dụ

### Tư vấn
```
Q: Cách hạch toán chi phí xây dựng?
A: Chi phí xây dựng:
   - TK 15x: Chi phí dự án
   - TK 622: Chi phí vận hành
   - Theo NV 107/2014/TT-BTC...
```

### Phân tích
```
Q: Chi phí của tôi có hợp lý không?
A: [Phân tích chi tiết...]
```

## 🆘 Khắc phục

| Lỗi | Cách khắc phục |
|-----|---|
| "Chưa cấu hình API" | Lấy API Key tại aistudio.google.com |
| "Kết nối thất bại" | Kiểm tra API Key & kết nối internet |
| Chậm phản hồi | Chờ hoặc kiểm tra kết nối |

## 📚 Tài liệu

- **AI_CHAT_GUIDE.md** - Hướng dẫn chi tiết
- **GEMINI_INTEGRATION_SUMMARY.md** - Tóm tắt kỹ thuật

## ⚠️ Lưu ý

- Không chia sẻ API Key công khai
- Dữ liệu được gửi đến Google (tuân theo chính sách riêng tư)
- Có giới hạn chi phí miễn phí hàng tháng

## 📞 Hỗ trợ

Kiểm tra `logs/app.log` nếu gặp vấn đề.

---

**Happy chatting! 🚀**
