# FasTrack ERP - Design System UI Guide

## 🎨 Design System Overview

### Bảng Màu Chính
```
┌─────────────────────────────────────────────────────────┐
│ SIDEBAR (Navy Dark)                                     │
├─────────────────────────────────────────────────────────┤
│ #0F2544  → Background (Navy đậm)                        │
│ #4A6880  → Section labels (ALL CAPS, tiêu đề)          │
│ #8BAEC8  → Menu items (Regular)                         │
│ #3B82F6  → Active item text (Blue)                      │
│ #1E3A5F  → Active item bg (Dark blue)                   │
│ #162D47  → Hover bg                                     │
│ #1A3558  → Border                                       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ CONTENT AREA (Light Gray)                               │
├─────────────────────────────────────────────────────────┤
│ #F0F4FA  → Page background                              │
│ #FFFFFF  → Panel/Card background                        │
│ #DCE3EC  → Border/Divider                               │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ TEXT & ACCENT                                           │
├─────────────────────────────────────────────────────────┤
│ #1A2D4A  → Primary text (Bold titles)                   │
│ #5A7A99  → Secondary text (Labels, metadata)            │
│ #8A9BB0  → Muted text (Placeholder, hint)               │
│ #1D72C8  → Accent Blue (Links, KPI, active)             │
│ #0D9455  → Accent Green (Success, positive)             │
│ #C27A10  → Accent Amber (Warning, caution)              │
│ #E53935  → Accent Red (Error, danger)                   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ STATUS PILLS                                            │
├─────────────────────────────────────────────────────────┤
│ Pending: #FEF3C7 bg, #92400E fg (Amber)                 │
│ Done:    #D1FAE5 bg, #065F46 fg (Green)                 │
│ Processing: #DBEAFE bg, #1E40AF fg (Blue)               │
└─────────────────────────────────────────────────────────┘
```

### Typography (Segoe UI, fallback Arial)
```
FONT_TITLE    = 13px bold      → Page titles, dialog headers
FONT_HEADING  = 11px bold      → Section headings
FONT_BODY     = 10px regular   → Normal text, labels
FONT_SMALL    = 9px regular    → Meta, hints, captions
FONT_SECTION  = 8px bold       → ALL CAPS labels
FONT_NAV      = 10px regular   → Menu items
```

### Spacing & Layout
```
SIDEBAR_WIDTH    = 220px
TOPBAR_HEIGHT    = 52px
PADDING_LARGE    = 16px       → Outer margins
PADDING_MEDIUM   = 12px       → Inter-component spacing
PADDING_SMALL    = 8px        → Fine-tuning
BORDER_RADIUS    = 7px        → Rounded corners
CARD_CORNER      = 6px        → Card corner radius
```

---

## 📱 Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                        TOPBAR (52px, white)                     │
│ Page Title + Subtitle      |  Notifications  Logout              │
├────────┬──────────────────────────────────────────────────────┤
│        │                                                        │
│ SIDEBAR│                  PAGE CONTENT (F0F4FA)                │
│ (220px)│  ┌────────────────────────────────────────────────┐  │
│ Navy   │  │ CARD / PANEL (white, border 1px)              │  │
│        │  │ ┌──────────────────────────────────────────┐  │  │
│ [Logo] │  │ │ Heading 11px bold                        │  │  │
│        │  │ │ ┌────────────────────────────────────┐   │  │  │
│ [Comp] │  │ │ │ Content...                         │   │  │  │
│        │  │ │ │ • Item 1                           │   │  │  │
│ [Nav]  │  │ │ │ • Item 2                           │   │  │  │
│        │  │ │ └────────────────────────────────────┘   │  │  │
│ [User] │  │ └──────────────────────────────────────────┘  │  │
│        │  │ KPI CARDS (4 columns):                         │  │
│        │  │ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐          │  │
│        │  │ │ 123K │ │ 45%  │ │ 890M │ │ 12K  │          │  │
│        │  │ │ Rev  │ │ Marg │ │ Cost │ │ Hrs  │          │  │
│        │  │ └──────┘ └──────┘ └──────┘ └──────┘          │  │
│        │  │ TABLE (scrollable):                            │  │
│        │  │ [Header row] [Item 1] [Item 2] ...             │  │
│        │  └────────────────────────────────────────────────┘  │
│        │  (scrollable, PAGE_BG fills rest)                    │
└────────┴──────────────────────────────────────────────────────┘
```

---

## 🔵 Sidebar Structure

```
┌─────────────────────┐
│   FasTrack ERP      │  14px bold white
│ PHẦN MỀM KẾ TOÁN... │  8px SECTION_COLOR
│                     │
├─────────────────────┤
│ ┌─────────────────┐ │
│ │ CÔNG TY ABC     │ │  10px SIDEBAR_ITEM
│ │ MST 0312019045  │ │  9px SECTION_COLOR
│ └─────────────────┘ │  (bg: HOVER_BG)
│                     │
├─────────────────────┤
│ TỔNG QUAN           │  8px bold SECTION
│ [D] Dashboard       │  10px ITEM (hover: bg change)
│ [AI] Trợ lý AI     │  
│                     │
├─────────────────────┤
│ KẾ TOÁN             │  8px bold SECTION
│ [C] Chi phí        │  
│ [HĐ] Hóa đơn       │  
│ [TƯ] Tạm ứng       │
│ [BT] Bút toán      │
│                     │
├─────────────────────┤
│ CÔNG TRÌNH          │
│ [CT] Công trường   │
│ [DA] Kế toán dự án │
│ ...                 │
│                     │
├─────────────────────┤
│ HỆ THỐNG            │
│ [DM] Danh mục       │
│ ...                 │
│                     │
├─────────────────────┤
│ ┌─────────────────┐ │
│ │ AM  Anh Minh    │ │  Avatar 30px (ACCENT_BLUE)
│ │     Admin       │ │  9px bold + 8px SECTION
│ └─────────────────┘ │
└─────────────────────┘

Active item:
┌─────────────────────┐
│ [D] Dashboard    ✓  │  bg: SIDEBAR_ACTIVE_BG
│                     │  fg: SIDEBAR_ACTIVE (blue)
└─────────────────────┘
```

---

## 📋 OCR Import Dialog (Modern Design)

```
┌───────────────────────────────────────────────────────────────┐
│ Trích xuất dữ liệu từ PDF / Hình ảnh                          │
│ Hệ thống sẽ tự động nhận diện text...  [Chọn file] [Lưu] [X] │
├───────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────┬──────────────────────────┐  │
│ │ VĂNG BẢN OCR GỐC             │ THÔNG TIN NHẬN DIỆN     │  │
│ │                              │                          │  │
│ │ Chi Minh.                    │ Mã số thuế               │  │
│ │ Ân Phúc và                   │ ┌──────────────────────┐│  │
│ │ ...                          │ │                      ││  │
│ │ 3.720.000đ (Bằng chữ:       │ │                      ││  │
│ │ Thông tin thanh toán:        │ └──────────────────────┘│  │
│ │ ...                          │ Số hóa đơn              │  │
│ │ Tên tài khoản: Công ty TNHH  │ ┌──────────────────────┐│  │
│ │                              │ │                      ││  │
│ │ Xin trân trọng cảm ơn!       │ └──────────────────────┘│  │
│ │ ...                          │ Ngày hóa đơn            │  │
│ │                              │ [Input fields...]       │  │
│ │                              │                          │  │
│ │ (scrollable, Consolas 10px)  │ Độ tin cậy: 75% ⚠      │  │
│ │                              │                          │  │
│ │ (text editing allowed)        │ (4 fields shown)         │  │
│ │                              │                          │  │
│ └──────────────────────────────┴──────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘

Alert (Confidence < 70%):
┌───────────────────────────────────────────────────────────┐
│ 🟡 Độ tin cậy thấp                                        │
│    Hãy kiểm tra kỹ và chỉnh sửa các trường để đảm bảo...│
└───────────────────────────────────────────────────────────┘

Confidence indicator:
┌──────────────────────┐
│ 🟢 Độ tin cậy: 90%   │ >= 80% → GREEN
│ 🟡 Độ tin cậy: 65%   │ 50-79% → AMBER
│ 🔴 Độ tin cậy: 30%   │ < 50%  → RED
└──────────────────────┘
```

---

## 🎨 Component Examples

### Card Component
```
┌────────────────────────────┐  (bg: PANEL_BG white)
│ Card Title          border:1px PANEL_BORDER │
│                                              │
│ Content goes here...                        │
│                                              │
│ • Item 1                                    │
│ • Item 2                                    │
│ • Item 3                                    │
└────────────────────────────┘
```

### Button Variants
```
PRIMARY:         [Chọn file] (blue bg, white fg)
SECONDARY:       [Hủy]       (white bg, gray fg, border)
SUCCESS:         [Lưu]       (green bg, white fg)
DANGER:          [Xóa]       (red bg, white fg)
```

### KPI Cards (4-column grid)
```
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ DOANH THU    │ MARGIN       │ CHI PHÍ      │ GIỜ CÔNG     │
│ 1,234,567K   │ 45%          │ 890,123K     │ 1,240        │
│ ↑ 15.2%      │ ↑ 2.5%       │ ↓ 8.3%       │ ↑ 5.0%       │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

### Status Pills
```
[Pending]    (amber bg, brown fg, rounded 20px, 9px)
[Done]       (green bg, dark-green fg)
[Processing] (blue bg, dark-blue fg)
```

### Alert/Info Boxes
```
🟢 ┌─ Thành công
   │  Dữ liệu đã được lưu thành công. ID: 12345

🟡 ┌─ Cảnh báo
   │  Độ tin cậy OCR thấp (45%), hãy kiểm tra lại

🔴 ┌─ Lỗi
   │  Tesseract OCR chưa được cài. Vui lòng cài từ...
```

---

## 🔌 Tkinter Implementation Tips

### 1. Frame với border (Card style)
```python
from ui.component_library import Card

card = Card(parent)
card.pack(fill='both', padx=16, pady=14)
```

### 2. Modern Button
```python
from ui.component_library import Button

btn = Button(
	parent,
	text="Chọn file",
	command=self._choose_file,
	variant="primary"  # primary|secondary|danger|success
)
btn.pack(padx=8, pady=4)
```

### 3. KPI Card Grid
```python
from ui.component_library import KPICard

kpi_frame = tk.Frame(parent, bg=PAGE_BG)
kpi_frame.pack(fill='x', padx=14, pady=14)

for label, value, trend in [
	("Doanh thu", "1.2M", 15.2),
	("Margin", "45%", 2.5),
]:
	kpi = KPICard(
		kpi_frame,
		label=label,
		value=value,
		trend=trend
	)
	kpi.pack(side='left', fill='both', expand=True, padx=6)
```

### 4. Status Pills
```python
from ui.component_library import Pill

pill = Pill(parent, text="Completed", status="done")
pill.pack()
```

### 5. Alert/Info
```python
from ui.component_library import Alert

alert = Alert(
	parent,
	severity="warning",
	title="Độ tin cậy thấp",
	message="Hãy kiểm tra và chỉnh sửa..."
)
alert.pack(fill='x', padx=16, pady=14)
```

---

## 📐 Grid Layout (TwoColumnForm)
```python
from ui.component_library import TwoColumnForm

form = TwoColumnForm(parent)
form.pack(fill='both', padx=16, pady=14)

# Add fields
label1 = tk.Label(form, text="Mã số thuế")
field1 = tk.Entry(form)

label2 = tk.Label(form, text="Số hóa đơn")
field2 = tk.Entry(form)

form.add_row("Mã số thuế", field1, "Số hóa đơn", field2)
form.add_row("Ngày HĐ", field3, "Tổng tiền", field4)
```

---

## 🎨 Migration Guide (Old → New)

### Before (Old style)
```python
tk.Button(
	parent,
	text="Chọn file",
	bg="#0F4C81",
	fg="white",
	font=("Arial", 10, "bold"),
	padx=16,
	pady=8
).pack(side='left', padx=4)
```

### After (Design System)
```python
from ui.component_library import Button

Button(
	parent,
	text="Chọn file",
	command=self._choose_file,
	variant="primary"
).pack(side='left', padx=4)
```

---

## ✨ Dark Mode Support (Future)

Current:
- Light theme (gray bg + dark text)

Future plan:
```python
# In theme.py
if DARK_MODE:
	PAGE_BG = "#1E293B"
	PANEL_BG = "#2D3748"
	TEXT_PRIMARY = "#F1F5F9"
	# ... etc
```

---

**Implementation Status:** ✅ Ready
**Components:** ✅ Created (component_library.py)
**OCR Dialog:** ✅ Redesigned
**Theme:** ✅ Applied
**Docs:** ✅ Complete

Enjoy the new design! 🎉
