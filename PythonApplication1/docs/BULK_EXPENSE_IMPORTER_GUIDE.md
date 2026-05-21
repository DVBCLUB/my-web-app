# Bulk Expense Importer - Modern UI & Validation Guide

## Overview

The modernized **Bulk Expense Importer** provides an enterprise-grade interface for batch importing expenses into FasTrack ERP, inspired by modern accounting software like Wave, Freshbooks, and QuickBooks Online.

### Key Features

✅ **Real-time Validation**  
- Field-by-field validation as you type  
- Visual indicators (✓ valid, ⚠ warning, ✗ error)  
- Smart date and amount parsing (US and Vietnamese formats)

✅ **Efficient Data Entry**  
- Copy-paste from Excel (Ctrl+V)  
- Tabular grid with scrolling  
- Summary panel showing statistics  

✅ **Error Management**  
- Clear error messages with field names  
- Warning detection for edge cases (future dates, large amounts)  
- Error export for detailed review  

✅ **Modern Design**  
- Integrated with FasTrack ERP design system  
- Color-coded status indicators  
- Responsive layout

---

## How to Use

### Opening the Dialog

```python
from ui.dialogs import BulkExpenseDialog

def open_bulk_import():
	dialog = BulkExpenseDialog(parent_window, rows=30)
	dialog.grab_set()  # Modal
	parent_window.wait_window(dialog)

	if dialog.result:
		rows = dialog.result['rows']  # Valid rows to import
		errors = dialog.result['errors']  # Errors (if any)
		print(f"Imported {len(rows)} rows successfully")
```

### Data Entry

#### Option 1: Direct Entry
- Click any cell and type values
- Tab to move to next cell

#### Option 2: Copy-Paste from Excel
1. Copy your expense table in Excel (including headers)
2. Click the first cell in the grid
3. Press Ctrl+V to paste all data
4. Validation runs automatically

### Understanding Status Indicators

| Indicator | Meaning | Action |
|-----------|---------|--------|
| **✓** (Green) | Row valid | Ready to import |
| **⚠** (Orange) | Row has warnings | Review and confirm |
| **✗** (Red) | Row has errors | Fix before importing |
| *Empty* | Row not filled | Continue or skip |

### Field Validation Rules

| Field | Rules | Example |
|-------|-------|---------|
| **Ngày** (Date) | Required, DD/MM/YYYY or YYYY-MM-DD format | 18/05/2026 |
| **Mô tả** (Description) | Required, 5-500 characters | Thuê xe cẩu chở vật tư |
| **Số tiền** (Amount) | Required, > 0, US or VN format | 5,940,000 or 1000.50 |
| **Dự án ID** | Optional integer | 1 |
| **Loại chi phí ID** | Optional integer | 2 |
| **Người chi** | Optional, 2+ chars | Nguyễn Văn A |
| **Hình thức** | Optional (default: Tiền mặt) | Tiền mặt, Chuyển khoản |
| Other fields | Optional text | - |

### Sample Data Format

When copying from Excel, ensure these columns in order:
```
Ngày | Dự án ID | Loại chi phí ID | Mô tả | Số tiền | Người chi | Hình thức | ... (up to 15 fields)
18/05/2026 | 1 | 2 | Thuê xe cẩu | 5,940,000 | Nguyễn A | Tiền mặt | ... 
```

### Number Format Support

The system intelligently handles multiple formats:
- **US format:** 1,000,000.50 → 1000000.50
- **Vietnamese format:** 1.000.000,50 → 1000000.50
- **Simple:** 1000000 → 1000000.0

---

## Summary Panel

The right-side panel displays real-time statistics:

```
Tóm tắt
───────
Tổng: 30        (total rows in grid)
Hợp lệ: 28      (valid, ready to import)
Cảnh báo: 1     (warnings, review needed)
Lỗi: 1          (errors, must fix)
```

These numbers update as you validate rows.

---

## Buttons & Actions

### Lưu dòng hợp lệ (Save Valid Rows)
- Collects all valid and warning rows
- Shows a confirmation dialog if errors exist
- Returns result with rows and error list

### Xuất lỗi (Export Errors)
- Shows detailed error messages
- Helps identify which rows need fixing

### Xóa mẫu (Clear Sample)
- Clears all data from the grid
- Useful for restarting

### Hủy (Cancel)
- Closes without saving
- No data imported

---

## Validation Logic

### How Validation Works

1. **On Paste (Ctrl+V)**  
   - Data splits by tabs (Excel columns)  
   - Each pasted row is validated individually  

2. **On Focus Out**  
   - When leaving a cell, that row is validated  

3. **On Keystroke** (Debounced)  
   - After 500ms of no typing, row is validated  
   - Avoids excessive validation during typing  

4. **On Save**  
   - Final validation pass on all rows  
   - Separates valid from error rows  

### Error Messages

| Error | Resolution |
|-------|-----------|
| "Ngày: Bắt buộc nhập" | Enter a date in DD/MM/YYYY format |
| "Mô tả: Bắt buộc nhập" | Enter a description (5+ chars) |
| "Số tiền: Không phải số hợp lệ" | Use a valid number (e.g., 1000, 1,000.50) |
| "Số tiền: Số tiền phải > 0" | Amount must be positive |
| "Mô tả: Mô tả quá dài (> 500 ký tự)" | Shorten the description |

### Warnings

| Warning | Recommendation |
|---------|-----------------|
| "Ngày: Ngày tương lai" | Date is in future; confirm intentional |
| "Số tiền: Số tiền rất lớn" | Amount > 1 billion; verify correctness |
| "Mô tả: Mô tả quá ngắn (< 5 ký tự)" | Add more detail for clarity |

---

## Programmatic Usage

### Example 1: Validate a Single Row

```python
from modules.bulk_expense_validator import BulkExpenseValidator

validator = BulkExpenseValidator()
row = ['18/05/2026', '1', '2', 'Mô tả chi phí', '5,940,000', 'Nguyễn A', 'Tiền mặt']
result = validator.validate_row(row, row_index=0)

if result.is_valid:
	print(f"Valid: {result.parsed_data}")
else:
	print(f"Errors: {result.error_messages}")
	print(f"Warnings: {result.warning_messages}")
```

### Example 2: Batch Validate

```python
rows = [
	['18/05/2026', '', '', 'Mô tả 1', '100,000', '', ''],
	['19/05/2026', '', '', 'Mô tả 2', '200,000', '', ''],
]

results = validator.validate_batch(rows)
summary = validator.get_summary(results)

print(f"Total: {summary['total']}, Valid: {summary['valid']}, Errors: {summary['error']}")
importable = validator.get_importable_rows(results)
print(f"Ready to import: {len(importable)} rows")
```

### Example 3: Export Errors

```python
error_report = validator.export_errors(results)
print(error_report)
# Output:
# === LỖI VALIDATION ===
# Dòng 3:
#   • Ngày: Định dạng không hợp lệ
```

---

## Architecture

### Components

1. **BulkExpenseValidator** (`modules/bulk_expense_validator.py`)  
   - Pure validation engine  
   - No UI dependencies  
   - Reusable in scripts/APIs  

2. **BulkExpenseDialog** (`ui/dialogs.py`)  
   - Modern UI with Canvas grid  
   - Real-time validation integration  
   - Visual indicators and summary  

3. **Design System** (`ui/theme.py`)  
   - Color constants (ACCENT_GREEN, ACCENT_RED, etc.)  
   - Typography and spacing  
   - Consistent styling  

### Data Flow

```
User Input (Paste/Type)
	↓
validate_row() → RowValidationResult
	↓
Visual Indicator Update (✓/⚠/✗)
	↓
Summary Panel Update
	↓
[On Save] → Collect Valid Rows → Dialog Result
```

---

## Testing

### Unit Tests

Run the test suite:

```bash
python -m unittest tests.test_bulk_expense_validator -v
```

Tests cover:
- Number parsing (US & Vietnamese formats)
- Date parsing and validation
- Required field validation
- Warning detection
- Batch validation
- Error export

### Manual Testing

1. Open the dialog
2. Paste sample data from Excel
3. Verify validation indicators appear
4. Review error messages
5. Export errors for inspection
6. Click Save and verify results

---

## Performance Considerations

### Large Pastes

When pasting 100+ rows:
- Validation is debounced (500ms) to avoid UI freeze
- Only affected rows are re-validated on keystroke
- Summary updates efficiently

### Optimization Tips

- Use Ctrl+V for bulk paste (most efficient)
- Don't type individual rows if possible
- Review errors in batch before fixing
- Use export for error tracking

---

## Troubleshooting

### Q: Dates not parsing?
**A:** Ensure format is DD/MM/YYYY (e.g., 18/05/2026). US format MM/DD/YYYY is also supported.

### Q: Numbers showing as invalid?
**A:** Remove commas or use consistent format. Both "1000" and "1,000.50" work.

### Q: Can't paste from Excel?
**A:** Ensure columns are separated by tabs, not spaces. Ctrl+V triggers paste handler.

### Q: Validation seems slow?
**A:** Debouncing is intentional to prevent UI lag. Wait 500ms after typing to see updates.

### Q: How to import without warnings?
**A:** Warnings are non-blocking. Click Save to import valid rows including those with warnings.

---

## Future Enhancements

🔄 Planned improvements:
- Bulk edit mode (edit multiple cells at once)
- CSV import format support
- Import history and undo
- Custom validation rules
- Field mapping for different expense types
- Drag-drop file upload

---

## Support & Documentation

- **Validator API:** See `modules/bulk_expense_validator.py` docstrings
- **Dialog Usage:** Refer to `ui/dialogs.py` class docs
- **Design System:** Check `ui/theme.py` for available colors and fonts

---

*Last Updated: 2024*  
*FasTrack ERP - Accounting & Financial Management*
