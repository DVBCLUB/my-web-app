# 🤖 Hướng dẫn sử dụng Trợ lý AI Kế toán

## Giới thiệu

FasTrack ERP hiện tích hợp **Google Gemini AI** - một trợ lý kế toán thông minh để:
- Tư vấn về kế toán & thuế
- Phân tích dữ liệu tài chính
- Tóm tắt và giải thích báo cáo
- Trả lời các câu hỏi về hạch toán

## Cài đặt & Cấu hình

### 1. Cài đặt thư viện Google Gemini AI

Chạy lệnh sau trong terminal/PowerShell:

```bash
pip install google-generativeai
```

### 2. Lấy API Key

1. Truy cập: https://aistudio.google.com/app/apikey
2. Đăng nhập bằng tài khoản Google
3. Nhấp "Create API Key"
4. Sao chép API Key (không chia sẻ công khai)

### 3. Cấu hình trong ứng dụng

**Cách 1: Từ giao diện (Khuyến nghị)**
- Mở ứng dụng FasTrack ERP
- Nhấp "🤖 Trợ lý AI" trong menu bên trái
- Nhấp nút "⚙ Cấu hình API"
- Dán API Key và nhấp "Kết nối & Lưu"

**Cách 2: Biến môi trường**
```powershell
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "sk-your-api-key-here", "User")
```

Sau đó khởi động lại ứng dụng.

## Sử dụng Trợ lý AI

### Truy cập

1. Mở ứng dụng FasTrack ERP
2. Từ menu bên trái, nhấp **"🤖 Trợ lý AI"** trong phần **TỔNG QUAN**

### Giao diện Chat

```
┌─────────────────────────────────────────┐
│ 🤖 Trợ lý kế toán AI          ● Sẵn sàng│
├─────────────────────────────────────────┤
│ Lịch sử chat...                         │
│ Bạn: Tính thuế TNDN cho doanh nghiệp    │
│                                         │
│ 🤖 AI: [Phản hồi chi tiết...]          │
├─────────────────────────────────────────┤
│ [Nhập câu hỏi...]                       │
│ ⚙ Cấu hình API | Xóa lịch sử | Gửi... │
└─────────────────────────────────────────┘
```

### Gửi tin nhắn

- **Gõ câu hỏi** trong ô nhập liệu
- **Nhấn `Ctrl+Enter`** hoặc nhấp nút **"Gửi"**
- **Chờ AI phản hồi** (thường mất 2-5 giây)

## Ví dụ sử dụng

### 1. Tư vấn Kế toán
```
Bạn: Chi phí vận tải cho công trình xây dựng được tính như thế nào?

🤖 AI: Chi phí vận tải được phân loại như sau:
- Nếu là chi phí dự án: Hạch toán vào TK 15x (công cụ, dụng cụ)
- Quy định: Theo NV 107/2014/TT-BTC
...
```

### 2. Phân tích dữ liệu
```
Bạn: Tôi có chi phí như sau:
- Vật liệu: 500 triệu
- Nhân công: 300 triệu
- Máy móc: 200 triệu

Hãy đưa ra nhận xét về cơ cấu chi phí này.

🤖 AI: Cơ cấu chi phí của bạn:
- Vật liệu: 50% (tỷ trọng bình thường)
- Nhân công: 30% (phù hợp với ngành xây dựng)
- Máy móc: 20% (hợp lý)

Nhận xét: Cơ cấu chi phí cân bằng, tuân theo tiêu chuẩn ngành...
```

### 3. Tóm tắt Báo cáo
```
Bạn: Tóm tắt ngắn gọn báo cáo tài chính sau: [dán dữ liệu]

🤖 AI: [Tóm tắt 3-5 dòng với các điểm chính]
```

## Các tính năng

| Tính năng | Mô tả |
|-----------|-------|
| **Chat tương tác** | Cuộc hội thoại liên tục, AI nhớ ngữ cảnh |
| **Lịch sử lưu trữ** | Giữ tối đa 20 tin nhắn gần nhất |
| **Tư vấn chuyên sâu** | Trả lời chi tiết như một chuyên gia kế toán |
| **Phân tích dữ liệu** | Giúp phân tích số liệu tài chính |
| **Hỗ trợ Tiếng Việt** | Giao diện và trả lời hoàn toàn bằng Tiếng Việt |

## Các câu hỏi thường gặp

### Q: Dữ liệu của tôi có được lưu trữ?
**A:** Không. Dữ liệu chỉ gửi đến Gemini API để xử lý và không được lưu. Tuy nhiên, tuân thủ chính sách riêng tư của Google.

### Q: API Key có an toàn không?
**A:** 
- Không chia sẻ API Key công khai
- Nên sử dụng biến môi trường để bảo mật
- Google giới hạn chi phí miễn phí hàng tháng

### Q: Tại sao AI phản hồi chậm?
**A:** 
- Phụ thuộc vào tốc độ internet
- Độ phức tạp của câu hỏi
- Thường xuyên này có thể liên quan đến máy chủ Google

### Q: Làm cách nào để đổi API Key?
**A:** 
- Nhấp "⚙ Cấu hình API"
- Nhập API Key mới
- Nhấp "Kết nối & Lưu"

## Cách khắc phục sự cố

### Lỗi "Chưa cấu hình API"
- Kiểm tra biến môi trường `GEMINI_API_KEY`
- Nhấp "⚙ Cấu hình API" và nhập API Key

### Lỗi "Kết nối API thất bại"
- Kiểm tra API Key có đúng không
- Kiểm tra kết nối internet
- Thử lại API Key từ https://aistudio.google.com/app/apikey

### AI không phản hồi
- Kiểm tra tính khả dụng của Gemini API
- Thử làm mới trang
- Xóa lịch sử chat và thử lại

## Giới hạn sử dụng

| Mục | Giới hạn |
|-----|----------|
| Số tin nhắn trong lịch sử | 20 tin nhắn gần nhất |
| Thời gian timeout | 30 giây/tin nhắn |
| Độ dài phản hồi | Tối đa 2000 ký tự |

## Bảo mật & Quyền riêng tư

- ✅ Dữ liệu không được lưu trữ trên máy chủ ứng dụng
- ✅ Giao tiếp được mã hóa (HTTPS)
- ⚠️ Tuân thủ chính sách Google: https://policies.google.com/privacy
- ⚠️ Không nên gửi dữ liệu nhạy cảm quá nhiều (mã số định danh, số tài khoản ngân hàng)

## Liên hệ & Hỗ trợ

Nếu gặp vấn đề:
1. Kiểm tra lỗi trong **Output Window** (View → Output)
2. Xem tệp log: `PythonApplication1/logs/app.log`
3. Liên hệ nhóm phát triển (nếu có)

---

**Cập nhật lần cuối:** 2024
**Phiên bản:** 1.0
