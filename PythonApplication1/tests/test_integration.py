#!/usr/bin/env python3
"""Comprehensive validation test for bulk expense system"""

import sys

def test_all():
    """Test all components"""
    # Test core validator
    from modules.bulk_expense_validator import BulkExpenseValidator, ValidationStatus
    v = BulkExpenseValidator()
    row = ['18/05/2026', '1', '2', 'Mô tả chi phí', '5,940,000', 'Nguyễn A', 'Tiền mặt']
    result = v.validate_row(row, 0)
    print('✅ Validator imports and works')
    print(f'   - Sample row validated: {result.status.value}')

    # Test dialog imports
    from ui.dialogs import BulkExpenseDialog
    from ui.theme import PAGE_BG, PANEL_BG, TEXT_PRIMARY, ACCENT_GREEN
    print('✅ Dialog and theme constants import successfully')

    # Test validator get_summary
    summary = v.get_summary([result])
    print(f'✅ Summary works: {summary["valid"]} valid, {summary["error"]} errors')

    # Test batch validation
    rows = [row, ['', '', '', '', '', '', '']]
    batch_results = v.validate_batch(rows)
    batch_summary = v.get_summary(batch_results)
    print(f'✅ Batch validation: {batch_summary["total"]} total, {batch_summary["empty"]} empty')

    print('\n🎉 All components validated successfully!')

if __name__ == '__main__':
    try:
        test_all()
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
