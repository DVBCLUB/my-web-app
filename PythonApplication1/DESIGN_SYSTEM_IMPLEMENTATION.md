# Design System Implementation - FasTrack ERP UI Redesign

## Overview

Successfully implemented a comprehensive design system for FasTrack ERP Tkinter application based on the provided specifications (Navy sidebar + Light Gray content). The implementation includes:

- ✅ **Design System Constants** (`ui/theme.py`)
- ✅ **Reusable Component Library** (`ui/component_library.py`)
- ✅ **Enhanced OCR Engine** with confidence scoring (`modules/ocr_enhanced.py`)
- ✅ **Redesigned OCR Dialog** using new design system (`ui/dialogs.py`)
- ✅ **Topbar & Sidebar Integration** in MainWindow (`ui/main_window.py`)
- ✅ **Documentation & Setup Guides**

---

## 1. DESIGN SYSTEM CONSTANTS (`ui/theme.py`)

### Color Palette

```python
# Sidebar (Dark Navy)
SIDEBAR_BG           = "#0F2544"    # Navy đậm
SIDEBAR_SECTION      = "#4A6880"    # Tiêu đề nhóm menu
SIDEBAR_ITEM         = "#8BAEC8"    # Menu item thường
SIDEBAR_ACTIVE       = "#3B82F6"    # Item đang chọn (chữ)
SIDEBAR_ACTIVE_BG    = "#1E3A5F"    # Item đang chọn (nền)
SIDEBAR_HOVER_BG     = "#162D47"    # Hover
SIDEBAR_BORDER       = "#1A3558"    # Đường phân cách

# Page & Panels (Light Gray background)
PAGE_BG              = "#F0F4FA"    # Nền toàn trang
PANEL_BG             = "#FFFFFF"    # Nền card/panel
PANEL_BORDER         = "#DCE3EC"    # Viền panel nhẹ

# Text Colors
TEXT_PRIMARY         = "#1A2D4A"    # Tiêu đề đậm
TEXT_SECONDARY       = "#5A7A99"    # Chú thích, nhãn
TEXT_MUTED           = "#8A9BB0"    # Placeholder, meta

# Semantic Colors
ACCENT_BLUE          = "#1D72C8"    # KPI, link, active
ACCENT_GREEN         = "#0D9455"    # Thành công, tốt
ACCENT_AMBER         = "#C27A10"    # Cảnh báo
ACCENT_RED           = "#E53935"    # Lỗi, nguy hiểm

# Topbar
TOPBAR_BG            = "#FFFFFF"
TOPBAR_BORDER        = "#DCE3EC"
TOPBAR_HEIGHT        = 52

# Pills/Badges
PILL_PENDING_BG      = "#FEF3C7"    PILL_PENDING_FG = "#92400E"
PILL_DONE_BG         = "#D1FAE5"    PILL_DONE_FG    = "#065F46"
PILL_PROC_BG         = "#DBEAFE"    PILL_PROC_FG    = "#1E40AF"
```

### Typography

```python
FONT_TITLE           = ("Segoe UI", 13, "bold")      # Page titles
FONT_HEADING         = ("Segoe UI", 11, "bold")      # Section headings
FONT_BODY            = ("Segoe UI", 10)              # Body text
FONT_SMALL           = ("Segoe UI", 9)               # Small text
FONT_NAV             = ("Segoe UI", 10)              # Navigation
FONT_SECTION         = ("Segoe UI", 8, "bold")       # ALL CAPS section labels
FONT_KPI             = ("Segoe UI", 20, "bold")      # KPI values
```

### Layout Constants

```python
SIDEBAR_WIDTH        = 220                           # Fixed sidebar width
TOPBAR_HEIGHT        = 52                            # Fixed topbar height
PADDING_LARGE        = 16                            # Card padding
PADDING_MEDIUM       = 12                            # Standard padding
PADDING_SMALL        = 8                             # Small gaps
BORDER_RADIUS        = 7                             # Corner radius (px)
```

---

## 2. COMPONENT LIBRARY (`ui/component_library.py`)

A comprehensive set of reusable themed components following the design system:

### Core Components

#### **Card**
- Light gray bordered panel
- Used for content sections
```python
Card(parent, bg=PANEL_BG)
```

#### **Button** (with hover effects)
- Variants: `primary`, `secondary`, `danger`, `success`, `neutral`
- Automatic hover state management
```python
Button(parent, text="Lưu", command=callback, variant="primary")
```

#### **Pill/Badge**
- Status indicators
- Types: `pending`, `done`, `processing`
```python
Pill(parent, text="Hoàn thành", status="done")
```

#### **Alert**
- Notification rows with severity dots
- Types: `error`, `warning`, `success`, `info`
```python
Alert(parent, severity="warning", title="Cảnh báo", 
	  message="Độ tin cậy thấp")
```

#### **KPICard**
- Dashboard metric display
- Shows value, unit, and trend
```python
KPICard(parent, label="Tổng chi phí", value="45,250,000", 
		unit="VND", trend=5.2, trend_color=ACCENT_GREEN)
```

#### **ProgressBar** (Canvas-based)
- Custom progress visualization
- Range 0-100
```python
pb = ProgressBar(parent, value=65, max_value=100)
pb.set_value(75)
```

#### **StatusLabel**
- Color-coded status display
- Semantic colors for success/error/warning
```python
StatusLabel(parent, text="Đã xử lý", status="success")
```

#### **InfoBox**
- Label + input or readonly display
```python
InfoBox(parent, label="Mã số thuế", value="0312019045", readonly=True)
```

#### **TwoColumnForm**
- Multi-column form layout helper
```python
form = TwoColumnForm(parent)
form.add_row("Trường 1", widget1, "Trường 2", widget2)
```

---

## 3. ENHANCED OCR ENGINE (`modules/ocr_enhanced.py`)

### Key Features

- **Asynchronous Processing**: Non-blocking OCR via `extract_text_async()`
- **Confidence Scoring**: Returns `(text, confidence)` tuples (0.0-1.0)
- **Multiple Variants**: 5 preprocessing variants × 4 Tesseract configs = 20 attempts
- **Timeout Handling**: Per-file and per-page timeouts to prevent hanging
- **Robust Error Recovery**: Fallback text extraction → OCR → human fallback

### Main API

```python
from modules.ocr_enhanced import OCRToolEnhanced, OCRResult, OCRStatus

ocr = OCRToolEnhanced()

# Synchronous (blocking)
result = ocr.extract_text("path/to/file.pdf", timeout=30.0)
if result.status == OCRStatus.SUCCESS:
	text = result.text
	confidence = result.confidence  # 0.0-1.0
	print(f"Confidence: {confidence:.0%}")

# Asynchronous (non-blocking)
def on_ocr_done(ocr_result):
	print(f"Text: {ocr_result.text[:100]}...")
	print(f"Confidence: {ocr_result.confidence:.0%}")

ocr.extract_text_async("path/to/file.pdf", callback=on_ocr_done)
```

### OCRResult Structure

```python
@dataclass
class OCRResult:
	text: str              # Extracted text
	status: OCRStatus      # SUCCESS, FAILED, CANCELLED
	confidence: float      # 0.0-1.0 confidence score
	error: str = None      # Error message if failed
	duration: float = 0.0  # Processing time (seconds)
	pages: int = 0         # Number of pages processed
```

### Preprocessing Variants

1. **Autocontrast**: Standard contrast adjustment
2. **Median + Sharpen**: Noise reduction + edge enhancement
3. **Enhanced Contrast**: 1.5x contrast boost
4. **Binary Threshold**: Pure black/white (140 threshold)
5. **Bilateral-like**: 5×5 median filter (smooth while preserving edges)

### Tesseract Configs

1. **PSM 6, OEM 3**: Default (single column text)
2. **PSM 4, OEM 3**: Variable column structures
3. **PSM 11, OEM 3**: Sparse text (tables, forms)
4. **PSM 6, OEM 1**: Legacy Tesseract engine

---

## 4. OCR DIALOG REDESIGN (`ui/dialogs.py`)

### New OCRImportDialog Features

✅ **Modern Layout**: Header + left raw text + right fields panel
✅ **Async OCR**: Non-blocking processing with progress modal
✅ **Confidence Display**: Color-coded confidence indicator
✅ **Alert System**: Warnings when confidence < 70%
✅ **Auto-Parse**: Extracts tax code, invoice #, dates, amounts
✅ **User Editable**: Fields can be manually corrected before save

### Layout

```
┌─────────────────────────────────────────┐
│ Header (Title + Buttons)                │
├──────────────────────┬──────────────────┤
│                      │                  │
│  Raw OCR Text        │  Extracted       │
│  (Scrollable)        │  Fields Panel    │
│                      │  (Editable)      │
│                      │                  │
│  [Confidence Badge]  │  [Confidence     │
│                      │   Indicator]     │
└──────────────────────┴──────────────────┘
```

### User Flow

1. Click "Chọn file PDF/ảnh" → file dialog
2. Progress modal appears with cancel button
3. OCR runs asynchronously with per-page timeouts
4. Raw text displays in left panel
5. Extracted fields populate right panel
6. Confidence shown with color feedback:
   - 🟢 80%+ = Green (high confidence)
   - 🟡 50-79% = Amber (medium confidence) + warning alert
   - 🔴 <50% = Red (low confidence) + error alert
7. User can edit fields, then save as document

### Dialog Classes

```python
class OCRImportDialog(tk.Toplevel):
	"""Main OCR import dialog with theme integration"""
	def _choose_file()          # File selection + async OCR start
	def _process_ocr_result()   # Display results + confidence + alerts

class OCRProgressDialog(tk.Toplevel):
	"""Progress modal with cancel button"""
	def set_status(status_text) # Update progress message
	def is_cancelled()          # Check if user clicked cancel
	def set_ocr_instance(ocr)   # Set OCR engine for cancel handling
```

---

## 5. MAIN WINDOW INTEGRATION (`ui/main_window.py`)

### Sidebar (`_create_menu()`)

✅ **Logo Area**: "FasTrack ERP" (white, 14px bold)
✅ **Subtitle**: "PHẦN MỀM KẾ TOÁN XÂY DỰNG" (section color, 8px)
✅ **Company Chip**: Rounded frame showing company name + tax code
✅ **Menu Groups**: TỔNG QUAN, KẾ TOÁN, CÔNG TRÌNH, HỆ THỐNG
✅ **Menu Items**: Icon + label with hover/active states
✅ **Active State**: Blue highlight + navy background
✅ **Scrollable**: Canvas + scrollbar for long menu lists

### Topbar (`_create_header()`)

✅ **Left Section**: Page title (bold) + subtitle (muted)
✅ **Right Section**: Alert bell + logout button
✅ **Alert Badge**: Red dot (7px) on bell icon
✅ **Fixed Height**: 52px as per design system
✅ **Border**: 1px separator below topbar
✅ **Dynamic Title**: Updates when menu item clicked

### Theme Integration

All UI elements reference `self.theme` dictionary:

```python
self.theme = {
	'SIDEBAR_BG': SIDEBAR_BG,
	'PAGE_BG': PAGE_BG,
	'TEXT_PRIMARY': TEXT_PRIMARY,
	'ACCENT_BLUE': ACCENT_BLUE,
	# ... all design system colors
}
```

---

## 6. SETUP & INSTALLATION

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Key OCR packages**:
- `pytesseract>=0.3.10` - Python wrapper for Tesseract
- `pypdfium2>=4.10.0` - PDF rendering (fast, low memory)
- `pdfplumber>=0.7.0` - PDF text extraction
- `pypdf>=3.0.0` - Alternative PDF text extractor
- `pillow>=9.0.0` - Image processing

### 2. Install Tesseract OCR

**Windows**:
1. Download: https://github.com/UB-Mannheim/tesseract/wiki → **tesseract-ocr-w64-setup-v5.x.exe**
2. Run installer, choose Vietnamese language pack
3. Default install path: `C:\Program Files\Tesseract-OCR`

**macOS**:
```bash
brew install tesseract
# Optional: install Vietnamese language data
brew install tesseract-lang
```

**Linux (Ubuntu)**:
```bash
sudo apt-get install tesseract-ocr
sudo apt-get install tesseract-ocr-vie  # Vietnamese support
```

### 3. Vietnamese Language Data (Optional but Recommended)

For improved Vietnamese text recognition:

```bash
# Download Vietnamese trained data
# https://github.com/UB-Mannheim/tesseract/wiki

# Windows: Place vie.traineddata in C:\Program Files\Tesseract-OCR\tessdata\
# macOS/Linux: Usually /usr/share/tesseract-ocr-4.00/tessdata/
```

Or add local `tessdata/` folder in project root with `vie.traineddata`.

### 4. Verify Installation

```python
import pytesseract
from PIL import Image

# This will list available languages
langs = pytesseract.get_languages()
print(langs)  # Should include 'vie' and 'eng'

# Test with simple image
result = pytesseract.image_to_string(Image.new('RGB', (100, 20)))
print(result)
```

---

## 7. FILE STRUCTURE

```
PythonApplication1/
├── ui/
│   ├── theme.py                    # ✅ Design system constants
│   ├── component_library.py        # ✅ Reusable components
│   ├── main_window.py              # ✅ Sidebar + Topbar (theme integrated)
│   ├── dialogs.py                  # ✅ OCRImportDialog (redesigned)
│   └── ...
├── modules/
│   ├── ocr_enhanced.py             # ✅ Enhanced OCR engine (async + confidence)
│   ├── document_intake.py          # ✅ Async extraction pipeline
│   ├── ocr_tools.py                # Legacy OCR helper (InvoiceOCRParser)
│   └── ...
├── docs/
│   ├── INSTALL_OCR.md              # ✅ Tesseract setup guide
│   ├── QUICK_START_OCR.md          # ✅ 5-minute quick start
│   ├── IMPROVE_OCR.md              # ✅ Tips for better results
│   ├── UI_GUIDE.md                 # ✅ Component library guide
│   └── ...
├── requirements.txt                # ✅ Updated with OCR packages
└── DESIGN_SYSTEM_IMPLEMENTATION.md # ✅ This document
```

---

## 8. USAGE EXAMPLES

### Using the Component Library in New Dialogs

```python
from ui.component_library import Card, Button, KPICard, Alert
from ui.theme import ACCENT_GREEN, TEXT_MUTED, PANEL_BG

# Create a card
card = Card(parent, bg=PANEL_BG)
card.pack(padx=16, pady=14)

# Add button
btn = Button(card, text="Xử lý", command=on_click, variant="primary")
btn.pack(padx=16, pady=8)

# Add KPI
kpi = KPICard(card, label="Doanh thu", value="150M", unit="VND",
			  trend=12.5, trend_color=ACCENT_GREEN)
kpi.pack(padx=16, pady=8)

# Add alert
alert = Alert(card, severity="warning", title="Chú ý",
			  message="Dữ liệu chưa được xác nhận")
alert.pack(padx=16, pady=8)
```

### Using the Enhanced OCR Engine

```python
from modules.ocr_enhanced import OCRToolEnhanced, OCRStatus

ocr = OCRToolEnhanced()

# Async mode (recommended for UI)
def handle_ocr_result(result):
	if result.status == OCRStatus.SUCCESS:
		print(f"Text: {result.text[:200]}...")
		print(f"Confidence: {result.confidence:.0%}")
		if result.confidence < 0.7:
			print("⚠ Low confidence - review results carefully")
	else:
		print(f"Error: {result.error}")

ocr.extract_text_async("invoice.pdf", callback=handle_ocr_result)

# Or synchronous mode (blocks until done)
result = ocr.extract_text("invoice.pdf", timeout=60)
```

---

## 9. MIGRATION CHECKLIST

### Phase 1: Core Design System ✅
- [x] Create `ui/theme.py` with all color & font constants
- [x] Create `ui/component_library.py` with basic components
- [x] Update `ui/main_window.py` to use theme in sidebar/topbar
- [x] Verify MainWindow builds without errors

### Phase 2: OCR Engine Enhancement ✅
- [x] Create `modules/ocr_enhanced.py` with async + confidence
- [x] Modify `modules/document_intake.py` for async extraction
- [x] Update `modules/ocr_enhanced.py` to return (text, confidence)
- [x] Verify imports and syntax

### Phase 3: UI Dialog Redesign ✅
- [x] Redesign `OCRImportDialog` with new component system
- [x] Integrate `OCRProgressDialog` for progress + cancel
- [x] Add confidence display and alert system
- [x] Test async OCR flow in dialog
- [x] Verify syntax and imports

### Phase 4: Documentation ✅
- [x] Create `docs/INSTALL_OCR.md`
- [x] Create `docs/QUICK_START_OCR.md`
- [x] Create `docs/IMPROVE_OCR.md`
- [x] Create `docs/UI_GUIDE.md` (component examples)
- [x] Create `DESIGN_SYSTEM_IMPLEMENTATION.md` (this file)

### Phase 5: Remaining Dialogs (In Progress)
- [ ] Migrate ExpenseDialog to use component library
- [ ] Migrate DocumentDialog to component library
- [ ] Migrate MaterialDialog to component library
- [ ] Migrate other dialogs progressively
- [ ] Apply custom Treeview styling (`Custom.Treeview` TTK style)

### Phase 6: Advanced Features (Planned)
- [ ] Implement table row striping (alternating bg)
- [ ] Implement status pill rendering in Treeview
- [ ] Create dashboard KPI grid layout
- [ ] Add animated progress indicators
- [ ] Implement form validation feedback
- [ ] Add custom alerts/notifications system

### Phase 7: Testing & Polish (Planned)
- [ ] End-to-end manual testing with sample scanned PDFs
- [ ] Collect OCR accuracy metrics and adjust thresholds
- [ ] Performance profiling (OCR speed, UI responsiveness)
- [ ] Accessibility review (color contrast, keyboard navigation)
- [ ] Cross-platform testing (Windows, macOS, Linux)

---

## 10. KNOWN LIMITATIONS & FUTURE IMPROVEMENTS

### Current Limitations
1. **Treeview Styling**: TTK Treeview has limited customization; consider custom Canvas implementation for full design compliance
2. **Border Radius**: Tkinter Canvas borders are squared; use Canvas for rounded corners if needed
3. **Dark Mode**: Design system is light mode only; dark mode variant planned
4. **Animations**: Tkinter doesn't support native animations; consider transitioning to PyQt/PySide for advanced UI

### Future Improvements
1. **Component Enhancement**:
   - [ ] Add SelectionDropdown component
   - [ ] Add SearchBox component
   - [ ] Add DatePicker component
   - [ ] Add TimePicker component
   - [ ] Add MultiSelect component

2. **OCR Improvements**:
   - [ ] Train custom Tesseract model for invoice-specific fields
   - [ ] Add form field detection (bounding boxes)
   - [ ] Implement confidence feedback per field
   - [ ] Add manual field correction workflow

3. **UI/UX**:
   - [ ] Implement responsive layout for smaller screens
   - [ ] Add keyboard shortcuts for common actions
   - [ ] Add context menus (right-click)
   - [ ] Implement undo/redo functionality
   - [ ] Add drag-drop support

---

## 11. SUPPORT & TROUBLESHOOTING

### OCR Issues

**Q: "tesseract is not installed" error**
```
A: Install Tesseract OCR from:
   https://github.com/UB-Mannheim/tesseract/wiki
   Then set in pytesseract:
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

**Q: Vietnamese text not recognized**
```
A: Download vie.traineddata and place in tessdata folder
   Or set local tessdata in project:
   - Create PythonApplication1/tessdata/
   - Download vie.traineddata from GitHub
   - Set --tessdata-dir in pytesseract config
```

**Q: OCR is very slow**
```
A: 1. Use lower image resolution (scale down before OCR)
   2. Increase timeout to allow more preprocessing variants
   3. Use faster image preprocessing (reduce variants from 5 to 3)
   4. Consider running OCR in separate process (already done with async)
```

**Q: Low confidence on handwritten forms**
```
A: 1. Scan at 300+ DPI
   2. Use better lighting (avoid shadows)
   3. Use threshold preprocessing (variant 4)
   4. Consider manual data entry for handwritten fields
```

### UI Issues

**Q: Sidebar not showing all menu items**
```
A: Sidebar has scrollable Canvas. Use mouse wheel to scroll.
   Or increase window height to fit more items.
```

**Q: Components not themed correctly**
```
A: Ensure you:
   1. Import from ui.component_library
   2. Import theme colors from ui.theme
   3. Call component with correct bg/fg parameters
   4. Don't override with hardcoded colors
```

---

## 12. SUMMARY OF CHANGES

### New Files Created
1. `ui/component_library.py` - 8 reusable components
2. `modules/ocr_enhanced.py` - Enhanced OCR engine
3. `docs/INSTALL_OCR.md` - Setup guide
4. `docs/QUICK_START_OCR.md` - Quick start
5. `docs/IMPROVE_OCR.md` - Optimization tips
6. `docs/UI_GUIDE.md` - Component guide
7. `DESIGN_SYSTEM_IMPLEMENTATION.md` - This document

### Files Modified
1. `ui/theme.py` - Verified color/font constants
2. `ui/main_window.py` - TopBar/Sidebar now use theme colors
3. `ui/dialogs.py` - OCRImportDialog completely redesigned
4. `modules/document_intake.py` - Added async OCR support
5. `modules/ocr_enhanced.py` - Modified to return confidence
6. `requirements.txt` - Added OCR packages (pytesseract, pdfplumber, pypdf, pypdfium2, pillow)

### Build Status
- ✅ All files compile without syntax errors
- ✅ All imports verified successfully
- ✅ No breaking changes to existing code
- ✅ Backward compatible with legacy dialogs

---

**Created**: 2024  
**Design System Version**: 1.0  
**Status**: Core implementation complete, UI migration in progress  
**Last Updated**: Latest session
