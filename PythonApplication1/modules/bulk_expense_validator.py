"""
BULK EXPENSE VALIDATOR - Module xác thực chi phí hàng loạt
Tách biệt logic validation để sử dụng lại và kiểm tra dễ dàng
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re
import unicodedata
from datetime import datetime, date


class ValidationStatus(Enum):
    """Trạng thái validation"""
    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"
    EMPTY = "empty"


@dataclass
class ValidationError:
    """Một lỗi validation"""
    field: str          # Tên field
    message: str        # Pesan lỗi
    severity: str       # "error", "warning"
    row_index: int      # Dòng số mấy (0-based)

    def __str__(self):
        return f"{self.field}: {self.message}"


@dataclass
class RowValidationResult:
    """Kết quả validation một dòng"""
    row_index: int
    status: ValidationStatus
    errors: List[ValidationError]
    warnings: List[ValidationError]
    parsed_data: Optional[Dict] = None

    @property
    def is_valid(self) -> bool:
        return self.status == ValidationStatus.VALID or self.status == ValidationStatus.WARNING

    @property
    def error_messages(self) -> List[str]:
        return [f"{e.field}: {e.message}" for e in self.errors]

    @property
    def warning_messages(self) -> List[str]:
        return [f"{e.field}: {e.message}" for e in self.warnings]

    @property
    def all_messages(self) -> List[str]:
        return self.error_messages + self.warning_messages

    @property
    def is_empty(self) -> bool:
        return self.status == ValidationStatus.EMPTY


class BulkExpenseValidator:
    """Validator cho chi phí hàng loạt"""

    # Field mapping
    FIELD_MAPPING = {
        0: ('date', 'Ngày'),
        1: ('project_id', 'Dự án ID'),
        2: ('category_id', 'Loại chi phí ID'),
        3: ('description', 'Mô tả'),
        4: ('amount', 'Số tiền'),
        5: ('paid_by', 'Người chi'),
        6: ('method', 'Hình thức'),
        7: ('notes', 'Ghi chú'),
        8: ('department', 'Phòng ban'),
        9: ('purpose', 'Mục đích'),
        10: ('item_list', 'Nội dung'),
        11: ('accounting_staff', 'Kế toán ký'),
        12: ('department_head', 'Trưởng phòng ký'),
        13: ('prepared_by', 'Người lập'),
        14: ('attachments', 'Hồ sơ đính kèm'),
    }

    # Required fields
    REQUIRED_FIELDS = ['date', 'category_id', 'description', 'amount']

    # Field rules (min, max length / pattern)
    FIELD_RULES = {
        'date': {'pattern': r'^\d{1,2}/\d{1,2}/\d{4}$|^\d{4}-\d{2}-\d{2}$', 'required': True},
        'description': {'min_len': 5, 'max_len': 500, 'required': True},
        'amount': {'min_val': 0, 'required': True},
        'paid_by': {'min_len': 2, 'max_len': 100},
        'department': {'max_len': 100},
        'purpose': {'max_len': 200},
    }

    def __init__(self, categories=None, projects=None):
        self.errors_per_row: Dict[int, List[ValidationError]] = {}
        self.warnings_per_row: Dict[int, List[ValidationError]] = {}
        self.category_lookup = self._build_lookup(categories or [])
        self.project_lookup = self._build_lookup(projects or [])

    def _normalize_text(self, value: str) -> str:
        text = unicodedata.normalize('NFKD', str(value or '').strip().lower())
        text = ''.join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r'[^a-z0-9]+', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()

    def _build_lookup(self, rows) -> Dict[str, int]:
        lookup = {}
        for row in rows:
            try:
                item_id, name = row[0], row[1]
            except Exception:
                continue
            if item_id is None:
                continue
            lookup[str(item_id)] = int(item_id)
            if name:
                lookup[self._normalize_text(name)] = int(item_id)
                lookup[self._normalize_text(f"{item_id} - {name}")] = int(item_id)
        return lookup

    def parse_id(self, value: str) -> Optional[int]:
        """Parse ID nhập trực tiếp hoặc dạng '12 - Tên danh mục'."""
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        match = re.match(r'^(\d+)', text)
        if not match:
            return None
        return int(match.group(1))

    def parse_lookup_id(self, value: str, lookup: Dict[str, int]) -> Optional[int]:
        parsed_id = self.parse_id(value)
        if parsed_id is not None:
            return parsed_id
        if not value:
            return None
        return lookup.get(self._normalize_text(value))

    def parse_number(self, value: str) -> Optional[float]:
        """Parse một số từ string

        Supports formats:
        - US format: 1,000,000.50
        - Vietnamese format: 1.000.000,50 or 1.000.000
        - Simple: 1000000 or 1000000.5
        """
        if not value or not isinstance(value, str):
            return None

        value = value.strip()

        # If has both comma and dot, determine which is decimal separator
        if ',' in value and '.' in value:
            # Last occurrence determines decimal
            last_comma = value.rfind(',')
            last_dot = value.rfind('.')

            if last_dot > last_comma:
                # US format: 1,000,000.50
                value = value.replace(',', '').replace('.', '.')
            else:
                # Vietnamese format: 1.000.000,50
                value = value.replace('.', '').replace(',', '.')
        elif ',' in value:
            # Could be US decimal or Vietnamese thousands
            # If comma is near end (2-3 positions from end), likely decimal
            if len(value) - value.rfind(',') <= 3:
                # Likely decimal: 1000,50
                value = value.replace(',', '.')
            else:
                # Likely thousands: 1,000,000
                value = value.replace(',', '')
        elif '.' in value:
            # Could be decimal or Vietnamese thousands
            # If dot is near end (2-3 positions from end), likely decimal
            if len(value) - value.rfind('.') <= 3:
                # Likely decimal: 1000.50
                pass  # Keep as is
            else:
                # Likely thousands: 1.000.000
                value = value.replace('.', '')

        try:
            return float(value)
        except ValueError:
            return None

    def parse_date(self, value: str) -> Optional[str]:
        """Parse và validate date"""
        if not value or not isinstance(value, str):
            return None

        value = value.strip()

        # Thử các format phổ biến
        formats = ['%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d', '%d-%m-%Y']

        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue

        return None

    def validate_date(self, value: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Validate ngày tháng
        Returns: (is_valid, parsed_value, error_message)
        """
        if not value or not value.strip():
            return False, None, "Bắt buộc nhập"

        parsed = self.parse_date(value)
        if not parsed:
            return False, None, "Định dạng không hợp lệ (DD/MM/YYYY hoặc YYYY-MM-DD)"

        # Kiểm tra ngày có quá xa không
        try:
            dt = datetime.strptime(parsed, '%Y-%m-%d')
            today = date.today()
            if dt.date() > today:
                return True, parsed, "Ngày tương lai"  # Warning
            if (today - dt.date()).days > 365:
                return True, parsed, "Ngày cách quá xa"  # Warning
        except:
            pass

        return True, parsed, None

    def validate_amount(self, value: str) -> Tuple[bool, Optional[float], Optional[str]]:
        """Validate số tiền
        Returns: (is_valid, parsed_value, error_message)
        """
        if not value or not value.strip():
            return False, None, "Bắt buộc nhập"

        parsed = self.parse_number(value)
        if parsed is None:
            return False, None, "Không phải số hợp lệ"

        if parsed <= 0:
            return False, None, "Số tiền phải > 0"

        if parsed > 1_000_000_000:
            return True, parsed, "Số tiền rất lớn"  # Warning

        return True, parsed, None

    def validate_field(self, field_name: str, value: str, row_index: int) -> Tuple[ValidationStatus, Optional[str], List[str]]:
        """Validate một field
        Returns: (status, parsed_value, error_messages_list)
        """
        if field_name == 'date':
            is_valid, parsed, msg = self.validate_date(value)
            if not is_valid:
                return ValidationStatus.ERROR, None, [msg] if msg else ["Lỗi"]
            status = ValidationStatus.WARNING if msg else ValidationStatus.VALID
            msgs = [msg] if msg else []
            return (status, parsed, msgs)

        elif field_name == 'amount':
            is_valid, parsed, msg = self.validate_amount(value)
            if not is_valid:
                return ValidationStatus.ERROR, None, [msg] if msg else []
            status = ValidationStatus.WARNING if msg else ValidationStatus.VALID
            msgs = [msg] if msg else []
            # Store amount as string of the float value (no commas/formatting)
            return status, str(int(parsed)) if parsed == int(parsed) else str(parsed), msgs

        elif field_name == 'category_id':
            parsed = self.parse_lookup_id(value, self.category_lookup)
            if parsed is None:
                return ValidationStatus.ERROR, None, ["Bắt buộc nhập ID loại chi phí"]
            return ValidationStatus.VALID, str(parsed), []

        elif field_name == 'project_id':
            parsed = self.parse_lookup_id(value, self.project_lookup)
            if value and parsed is None:
                return ValidationStatus.ERROR, None, ["ID dự án không hợp lệ"]
            return ValidationStatus.VALID, str(parsed) if parsed is not None else '', []

        elif field_name == 'description':
            if not value or not value.strip():
                return ValidationStatus.ERROR, None, ["Bắt buộc nhập"]
            if len(value) < 5:
                return ValidationStatus.WARNING, value.strip(), ["Mô tả quá ngắn (< 5 ký tự)"]
            if len(value) > 500:
                return ValidationStatus.ERROR, None, ["Mô tả quá dài (> 500 ký tự)"]
            return ValidationStatus.VALID, value.strip(), []

        elif field_name in ['paid_by', 'department', 'purpose']:
            if value and len(value) < 2:
                return ValidationStatus.WARNING, value.strip(), [f"{field_name} quá ngắn"]
            return ValidationStatus.VALID, value.strip() if value else '', []

        else:
            return ValidationStatus.VALID, value.strip() if value else '', []

    def validate_row(self, row_data: List[str], row_index: int) -> RowValidationResult:
        """Validate một dòng dữ liệu

        Args:
            row_data: List 15 giá trị (hoặc ít hơn)
            row_index: Index của dòng (0-based)

        Returns:
            RowValidationResult
        """
        # Pad row_data to ensure all fields are present
        row_data = list(row_data) + [''] * (len(self.FIELD_MAPPING) - len(row_data))

        # Check if empty
        if not row_data or not any(row_data):
            return RowValidationResult(
                row_index=row_index,
                status=ValidationStatus.EMPTY,
                errors=[],
                warnings=[],
                parsed_data=None
            )

        errors = []
        warnings = []
        parsed_data = {}
        overall_status = ValidationStatus.VALID

        # Validate từng field
        for col_index, (field_name, field_label) in self.FIELD_MAPPING.items():
            value = row_data[col_index] if col_index < len(row_data) else ''

            status, parsed_value, msgs = self.validate_field(field_name, value, row_index)

            if status == ValidationStatus.ERROR:
                overall_status = ValidationStatus.ERROR
                errors.append(ValidationError(
                    field=field_label,
                    message=msgs[0] if msgs else "Lỗi",
                    severity='error',
                    row_index=row_index
                ))
            elif status == ValidationStatus.WARNING:
                if overall_status != ValidationStatus.ERROR:
                    overall_status = ValidationStatus.WARNING
                warnings.append(ValidationError(
                    field=field_label,
                    message=msgs[0] if msgs else "Cảnh báo",
                    severity='warning',
                    row_index=row_index
                ))

            if parsed_value is not None:
                parsed_data[field_name] = parsed_value
            elif value:
                parsed_data[field_name] = value

        return RowValidationResult(
            row_index=row_index,
            status=overall_status,
            errors=errors,
            warnings=warnings,
            parsed_data=parsed_data if parsed_data else None
        )

    def validate_batch(self, rows: List[List[str]]) -> List[RowValidationResult]:
        """Validate multiple rows

        Args:
            rows: List of rows, each row is List[str]

        Returns:
            List of RowValidationResult
        """
        results = []
        for row_index, row in enumerate(rows):
            result = self.validate_row(row, row_index)
            results.append(result)
        self._mark_duplicate_rows(results)
        return results

    def _mark_duplicate_rows(self, results: List[RowValidationResult]) -> None:
        seen = {}
        for result in results:
            if not result.is_valid or not result.parsed_data:
                continue
            data = result.parsed_data
            key = (
                data.get('date') or '',
                data.get('project_id') or '',
                data.get('category_id') or '',
                self._normalize_text(data.get('description') or ''),
                data.get('amount') or '',
            )
            if key in seen:
                first_row = seen[key] + 1
                result.warnings.append(ValidationError(
                    field='Dòng',
                    message=f"Nghi trùng với dòng {first_row}",
                    severity='warning',
                    row_index=result.row_index,
                ))
                if result.status == ValidationStatus.VALID:
                    result.status = ValidationStatus.WARNING
            else:
                seen[key] = result.row_index

    def get_summary(self, results: List[RowValidationResult]) -> Dict:
        """Get summary statistics"""
        total = len(results)
        empty = sum(1 for r in results if r.is_empty)
        valid = sum(1 for r in results if r.status == ValidationStatus.VALID)
        warning = sum(1 for r in results if r.status == ValidationStatus.WARNING)
        error = sum(1 for r in results if r.status == ValidationStatus.ERROR)

        return {
            'total': total,
            'empty': empty,
            'valid': valid,
            'warning': warning,
            'error': error,
            'importable': valid + warning,
            'percentage': int((valid + warning) / (total - empty) * 100) if (total - empty) > 0 else 0
        }

    def get_importable_rows(self, results: List[RowValidationResult]) -> List[Dict]:
        """Get rows that can be imported (valid + warning)"""
        return [r.parsed_data for r in results if r.is_valid and r.parsed_data]

    def export_errors(self, results: List[RowValidationResult]) -> str:
        """Export errors as formatted string"""
        error_rows = [r for r in results if r.status == ValidationStatus.ERROR]
        if not error_rows:
            return "Không có lỗi"

        lines = ["=== LỖI VALIDATION ===\n"]
        for r in error_rows:
            lines.append(f"Dòng {r.row_index + 1}:")
            for msg in r.all_messages:
                lines.append(f"  • {msg}")
            lines.append("")

        return "\n".join(lines)
