# 🔧 Fix: Google Generative AI Optional

## ❌ Lỗi

Khi chạy ứng dụng mà chưa cài đặt `google-generativeai`, bị lỗi:
```
Thiếu thư viện: google-generativeai
```

## ✅ Giải pháp

Làm cho `google-generativeai` là **optional** (không bắt buộc):

### 📝 Thay đổi

1. **main.py** - Làm cho AI service optional
   - Bỏ `google-generativeai` khỏi `required` list
   - Thêm vào `optional` list
   - Try-catch khi khởi tạo AI service

2. **ai_service.py** - Handle lỗi khi thư viện không có
   - Import `genai` với try-except
   - Kiểm tra `GEMINI_AVAILABLE` flag
   - Error message rõ ràng

3. **ui/main_window.py** - Conditional UI
   - Import `AIChatWidget` với try-except
   - Thêm `AI_CHAT_AVAILABLE` flag
   - Chỉ show "Trợ lý AI" nếu available
   - Show error message nếu click nhưng chưa install

### 🚀 Hậu quả

✅ Ứng dụng chạy bình thường **mà không cần** `google-generativeai`  
✅ Nếu muốn AI: `pip install google-generativeai`  
✅ Menu hiện hoặc ẩn tùy theo cài đặt  

## 📋 Code Changes

### main.py
```python
# Trước:
required = ['pandas', 'openpyxl', ..., 'google-generativeai']

# Sau:
required = ['pandas', 'openpyxl', ...]  # Bắt buộc
optional = ['google_generativeai']  # Optional
```

### ai_service.py
```python
try:
	import google.generativeai as genai
	GEMINI_AVAILABLE = True
except ImportError:
	GEMINI_AVAILABLE = False
	genai = None
```

### ui/main_window.py
```python
try:
	from ui.ai_chat_widget import AIChatWidget
	AI_CHAT_AVAILABLE = True
except ImportError:
	AI_CHAT_AVAILABLE = False
	AIChatWidget = None

# Menu điều kiện
if AI_CHAT_AVAILABLE:
	overview_items.append(('🤖 Trợ lý AI', self._show_ai_chat))
```

## 🎯 Hướng dẫn sử dụng

### Chỉ dùng ERP (không cần AI)
```bash
pip install -r requirements.txt  # (không có google-generativeai)
python main.py
# Ứng dụng chạy bình thường, không có menu "Trợ lý AI"
```

### Muốn dùng AI
```bash
pip install google-generativeai
python main.py
# Menu sẽ có "🤖 Trợ lý AI"
```

## ✔️ Test

```bash
# Chạy mà không có google-generativeai
python main.py
# ✓ Ứng dụng chạy OK

# Cài google-generativeai
pip install google-generativeai

# Chạy lại
python main.py
# ✓ Menu sẽ có "🤖 Trợ lý AI"
```

---

**Vấn đề giải quyết!** ✅
