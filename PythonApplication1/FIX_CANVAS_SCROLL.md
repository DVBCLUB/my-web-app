# 🔧 Fix: Content Canvas Scroll Issue

## ❌ Lỗi

Vùng content (phần trắng) không hiển thị nội dung, canvas scroll không cập nhật đúng.

Triệu chứng:
- Trang trắng khi mở section
- Menu hoạt động nhưng content không load
- Scrollbar không cập nhật

## ✅ Giải pháp

### Sửa đổi `ui/main_window.py`

#### 1. Cải thiện `_update_content_scrollregion`
```python
def _update_content_scrollregion(self, _event=None):
	if hasattr(self, 'content_canvas'):
		self.content_canvas.configure(scrollregion=self.content_canvas.bbox('all'))
		# Force update ngay lập tức
		self.content_canvas.after(10, self._resize_content_window_auto)
```

#### 2. Thêm method `_resize_content_window_auto`
```python
def _resize_content_window_auto(self):
	"""Auto resize window based on content"""
	if hasattr(self, 'content_window') and hasattr(self, 'content_canvas'):
		try:
			canvas_width = self.content_canvas.winfo_width()
			content_width = self.content_frame.winfo_reqwidth()
			width = max(canvas_width, content_width) if canvas_width > 1 else content_width

			if width > 1:
				self.content_canvas.itemconfigure(self.content_window, width=width)
		except:
			pass
```

#### 3. Sửa `_resize_content_window`
```python
def _resize_content_window(self, event):
	if hasattr(self, 'content_window'):
		try:
			width = max(event.width, self.content_frame.winfo_reqwidth())
			if width > 1:
				self.content_canvas.itemconfigure(self.content_window, width=width)
		except:
			pass
```

#### 4. Sửa `_clear_content`
```python
def _clear_content(self):
	"""Xóa toàn bộ nội dung."""
	for widget in self.content_frame.winfo_children():
		widget.destroy()
	self.content_canvas.yview_moveto(0)
	self.content_canvas.xview_moveto(0)
	self.content_canvas.configure(scrollregion=(0, 0, 0, 0))
	# Force update
	self.content_frame.update_idletasks()
	self.content_canvas.after(5, self._update_content_scrollregion)
```

## 🔑 Chủ yếu

1. **Thêm delay với `after()`** - Cho phép tkinter cập nhật layout trước khi tính scrollregion
2. **Update idletasks** - Đảm bảo widget được render trước
3. **Error handling** - Try-except để tránh crash nếu widget chưa sẵn sàng
4. **Check width > 1** - Tránh set width = 0 hoặc 1 pixel

## ✔️ Test

```bash
python main.py
# Kiểm tra:
# 1. Mở từng menu item
# 2. Content phải hiển thị (không trắng)
# 3. Scroll phải hoạt động
# 4. Chuyển qua lại các menu item
```

## 📋 Tệp thay đổi
- `ui/main_window.py` - 4 method sửa/thêm

---

**Fix hoàn tất!** ✅
