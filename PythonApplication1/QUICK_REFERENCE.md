# Quick Reference - FasTrack ERP Design System

## 🎨 Color Palette Cheat Sheet

### Sidebar (Dark Navy Theme)
```python
from ui.theme import (
	SIDEBAR_BG,      # "#0F2544" - Dark navy background
	SIDEBAR_ITEM,    # "#8BAEC8" - Menu item text
	SIDEBAR_ACTIVE,  # "#3B82F6" - Active item text (blue)
	SIDEBAR_ACTIVE_BG, # "#1E3A5F" - Active item background
	SIDEBAR_HOVER_BG,  # "#162D47" - Hover background
)
```

### Content Area (Light Gray Theme)
```python
from ui.theme import (
	PAGE_BG,         # "#F0F4FA" - Page background
	PANEL_BG,        # "#FFFFFF" - Card/panel background
	PANEL_BORDER,    # "#DCE3EC" - Borders
)
```

### Text Hierarchy
```python
from ui.theme import (
	TEXT_PRIMARY,    # "#1A2D4A" - Bold titles
	TEXT_SECONDARY,  # "#5A7A99" - Body text
	TEXT_MUTED,      # "#8A9BB0" - Placeholder/meta
)
```

### Semantic Colors
```python
from ui.theme import (
	ACCENT_BLUE,     # "#1D72C8" - Primary, links, info
	ACCENT_GREEN,    # "#0D9455" - Success, positive
	ACCENT_AMBER,    # "#C27A10" - Warning
	ACCENT_RED,      # "#E53935" - Error, danger
)
```

---

## 🧩 Component Quick Start

### Button (with hover effects)
```python
from ui.component_library import Button

# Primary button (blue)
btn = Button(parent, text="Lưu", command=save_action, variant="primary")
btn.pack(padx=10, pady=8)

# Secondary button (gray)
btn = Button(parent, text="Hủy", command=cancel_action, variant="secondary")
btn.pack(padx=10, pady=8)

# Danger button (red)
btn = Button(parent, text="Xóa", command=delete_action, variant="danger")
btn.pack(padx=10, pady=8)

# Success button (green)
btn = Button(parent, text="Hoàn thành", command=complete_action, variant="success")
btn.pack(padx=10, pady=8)
```

### Card (Panel with border)
```python
from ui.component_library import Card

card = Card(parent)
card.pack(fill="both", expand=True, padx=16, pady=14)

# Add content to card
tk.Label(card, text="Tiêu đề", bg=PANEL_BG, fg=TEXT_PRIMARY,
		 font=FONT_TITLE).pack(padx=16, pady=(16, 8))
```

### Pill/Badge (Status indicator)
```python
from ui.component_library import Pill

# Done (green)
Pill(parent, text="Hoàn thành", status="done").pack()

# Pending (yellow)
Pill(parent, text="Chờ xử lý", status="pending").pack()

# Processing (blue)
Pill(parent, text="Đang xử lý", status="processing").pack()
```

### Alert (Notification box)
```python
from ui.component_library import Alert

# Error (red)
Alert(parent, severity="error", title="Lỗi",
	  message="Không thể lưu dữ liệu").pack(fill="x")

# Warning (amber)
Alert(parent, severity="warning", title="Cảnh báo",
	  message="Dữ liệu chưa được xác nhận").pack(fill="x")

# Success (green)
Alert(parent, severity="success", title="Thành công",
	  message="Đã lưu dữ liệu").pack(fill="x")

# Info (blue)
Alert(parent, severity="info", title="Thông báo",
	  message="Công ty mới được thêm").pack(fill="x")
```

### KPI Card (Dashboard metric)
```python
from ui.component_library import KPICard
from ui.theme import ACCENT_GREEN

kpi = KPICard(parent,
	label="Tổng chi phí",
	value="450,250,000",
	unit="VND",
	trend=5.2,
	trend_color=ACCENT_GREEN)
kpi.pack(fill="x", padx=12, pady=8)
```

### Progress Bar
```python
from ui.component_library import ProgressBar

pbar = ProgressBar(parent, value=65, max_value=100)
pbar.pack(fill="x", padx=16, pady=8)

# Update progress
pbar.set_value(85)
```

### Two-Column Form
```python
from ui.component_library import TwoColumnForm

form = TwoColumnForm(parent)
form.pack(fill="x", padx=16, pady=14)

# Add fields
entry1 = tk.Entry(parent)
entry2 = tk.Entry(parent)
form.add_row("Tên công ty", entry1, "MST", entry2)

entry3 = tk.Entry(parent)
form.add_row("Địa chỉ", entry3)
```

---

## 🎯 Font Sizes

```python
from ui.theme import (
	FONT_TITLE,      # ("Segoe UI", 13, "bold") - Page titles
	FONT_HEADING,    # ("Segoe UI", 11, "bold") - Section headings
	FONT_BODY,       # ("Segoe UI", 10) - Body text
	FONT_SMALL,      # ("Segoe UI", 9) - Small text
	FONT_NAV,        # ("Segoe UI", 10) - Navigation labels
	FONT_SECTION,    # ("Segoe UI", 8, "bold") - ALL CAPS labels
	FONT_KPI,        # ("Segoe UI", 20, "bold") - KPI values
)
```

**Usage**:
```python
tk.Label(parent, text="Chi phí tháng 3", font=FONT_TITLE, fg=TEXT_PRIMARY)
tk.Label(parent, text="Tổng cộng", font=FONT_HEADING, fg=TEXT_SECONDARY)
tk.Label(parent, text="Chi phí đã thanh toán", font=FONT_BODY, fg=TEXT_SECONDARY)
tk.Label(parent, text="Chi tiết nhỏ", font=FONT_SMALL, fg=TEXT_MUTED)
```

---

## 📦 Imports Template

```python
# Colors
from ui.theme import (
	# Sidebar
	SIDEBAR_BG, SIDEBAR_SECTION, SIDEBAR_ITEM, SIDEBAR_ACTIVE,
	SIDEBAR_ACTIVE_BG, SIDEBAR_HOVER_BG, SIDEBAR_BORDER,

	# Page & panels
	PAGE_BG, PANEL_BG, PANEL_BORDER,

	# Text
	TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,

	# Semantic
	ACCENT_BLUE, ACCENT_GREEN, ACCENT_AMBER, ACCENT_RED,

	# Topbar
	TOPBAR_BG, TOPBAR_BORDER, TOPBAR_HEIGHT,

	# Pills
	PILL_PENDING_BG, PILL_PENDING_FG,
	PILL_DONE_BG, PILL_DONE_FG,
	PILL_PROC_BG, PILL_PROC_FG,

	# Fonts
	FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL,
	FONT_NAV, FONT_SECTION, FONT_KPI,
)

# Components
from ui.component_library import (
	Card, Button, Pill, Alert, KPICard,
	ProgressBar, StatusLabel, InfoBox, TwoColumnForm
)

# OCR
from modules.ocr_enhanced import OCRToolEnhanced, OCRResult, OCRStatus
```

---

## 🔧 Common Patterns

### Sidebar Menu Item
```python
menu_item = tk.Label(
	parent,
	text="Chi phí",
	bg=SIDEBAR_BG,
	fg=SIDEBAR_ITEM,
	font=FONT_NAV,
	cursor="hand2"
)
menu_item.pack(fill="x", padx=10, pady=6)

# Active state
def activate():
	menu_item.configure(bg=SIDEBAR_ACTIVE_BG, fg=SIDEBAR_ACTIVE)

# Hover state
def on_hover(e):
	menu_item.configure(bg=SIDEBAR_HOVER_BG)

def on_leave(e):
	menu_item.configure(bg=SIDEBAR_BG)

menu_item.bind("<Button-1>", lambda e: activate())
menu_item.bind("<Enter>", on_hover)
menu_item.bind("<Leave>", on_leave)
```

### Form Section
```python
# Section title (ALL CAPS)
tk.Label(parent, text="THÔNG TIN CHUNG",
		 bg=PANEL_BG, fg=TEXT_MUTED, font=FONT_SECTION).pack(anchor="w", padx=16, pady=(16, 8))

# Form field
tk.Label(parent, text="Tên công ty",
		 bg=PANEL_BG, fg=TEXT_SECONDARY, font=FONT_SMALL).pack(anchor="w", padx=16, pady=(4, 0))

entry = tk.Entry(parent, font=FONT_BODY, relief="solid", bd=1,
				bg=PANEL_BG, fg=TEXT_PRIMARY, insertbackground=ACCENT_BLUE)
entry.pack(fill="x", padx=16, pady=(0, 12))
```

### Page Layout
```python
# Page background
page = tk.Frame(root, bg=PAGE_BG)
page.pack(fill="both", expand=True)

# Card
card = Card(page)
card.pack(fill="both", expand=True, padx=16, pady=16)

# Content inside card
tk.Label(card, text="Chi phí tháng này",
		 bg=PANEL_BG, fg=TEXT_PRIMARY, font=FONT_TITLE).pack(padx=16, pady=(16, 8), anchor="w")

# Data table or more content...
```

---

## 🎓 OCR Integration Quick Start

### Simple Sync OCR
```python
from modules.ocr_enhanced import OCRToolEnhanced, OCRStatus

ocr = OCRToolEnhanced()
result = ocr.extract_text("invoice.pdf")

if result.status == OCRStatus.SUCCESS:
	print(f"✓ Success: {result.text[:100]}...")
	print(f"  Confidence: {result.confidence:.0%}")
else:
	print(f"✗ Error: {result.error}")
```

### Async OCR with Callback
```python
from modules.ocr_enhanced import OCRToolEnhanced, OCRStatus

ocr = OCRToolEnhanced()

def on_ocr_done(result):
	if result.status == OCRStatus.SUCCESS:
		print(f"Text: {result.text[:200]}...")
		print(f"Confidence: {result.confidence:.0%}")

		# Show alert if low confidence
		if result.confidence < 0.7:
			print("⚠ Low confidence - review results carefully")
	else:
		print(f"Error: {result.error}")

ocr.extract_text_async("invoice.pdf", callback=on_ocr_done)
```

### In OCR Dialog
```python
from modules.ocr_enhanced import OCRToolEnhanced
from ui.dialogs import OCRProgressDialog

ocr = OCRToolEnhanced()

# Show progress modal
progress_dialog = OCRProgressDialog(parent, "Đang trích xuất text...")

def on_ocr_result(result):
	progress_dialog.destroy()

	if result.status == OCRStatus.SUCCESS:
		# Update UI with results
		text_widget.delete("1.0", "end")
		text_widget.insert("1.0", result.text)

		# Show confidence with color
		confidence = result.confidence
		if confidence >= 0.8:
			color = ACCENT_GREEN
			text = f"Độ tin cậy: {confidence:.0%} ✓"
		elif confidence >= 0.5:
			color = ACCENT_AMBER
			text = f"Độ tin cậy: {confidence:.0%} ⚠"
		else:
			color = ACCENT_RED
			text = f"Độ tin cậy: {confidence:.0%} ✗"

		confidence_label.configure(fg=color, text=text)

ocr.extract_text_async("file.pdf", callback=on_ocr_result)
```

---

## 📊 Layout Spacing Guide

```python
from ui.theme import (
	PADDING_LARGE,    # 16px - Card padding, major sections
	PADDING_MEDIUM,   # 12px - Standard padding between elements
	PADDING_SMALL,    # 8px - Small gaps, list items
)

# Card with standard spacing
Card(parent).pack(padx=PADDING_LARGE, pady=PADDING_LARGE)

# Content inside card
tk.Label(card, text="Title").pack(padx=PADDING_LARGE, pady=(PADDING_LARGE, PADDING_SMALL))
tk.Label(card, text="Body").pack(padx=PADDING_LARGE, pady=PADDING_MEDIUM)

# List items with tight spacing
for item in items:
	tk.Label(parent, text=item).pack(padx=PADDING_MEDIUM, pady=PADDING_SMALL)
```

---

## 🚀 Next Dialog to Migrate

1. **Pick a dialog** (e.g., `ExpenseDialog`)
2. **Import components**:
   ```python
   from ui.component_library import Card, Button, Alert
   from ui.theme import PANEL_BG, TEXT_PRIMARY, ACCENT_BLUE
   ```
3. **Replace colors**:
   - `bg='white'` → `bg=PANEL_BG`
   - `fg='black'` → `fg=TEXT_PRIMARY`
   - `bg='#0099ff'` → `bg=ACCENT_BLUE`
4. **Replace buttons**:
   ```python
   Button(parent, text="Lưu", command=save, variant="primary")
   ```
5. **Add cards** around sections:
   ```python
   card = Card(parent)
   card.pack(fill="both", padx=16, pady=14)
   # Add content to card instead of parent
   ```
6. **Test and verify**

---

**Version**: 1.0  
**Last Updated**: Current Session  
**Status**: Ready to Use ✅
