from pathlib import Path
from datetime import date
import re
import unicodedata


class OCRTool:
    """Trích xuất văn bản từ PDF/ảnh, ưu tiên hóa đơn tiếng Việt scan."""

    @staticmethod
    def extract_text(file_path):
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        suffix = path.suffix.lower()
        if suffix == '.pdf':
            return OCRTool._extract_pdf(path)
        return OCRTool._extract_image(path)

    @staticmethod
    def _extract_pdf(path):
        text = OCRTool._extract_pdf_text(path)
        if text.strip():
            return text
        return OCRTool._ocr_pdf_pages(path)

    @staticmethod
    def _extract_pdf_text(path):
        pages = []
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                for index, page in enumerate(pdf.pages, 1):
                    text = page.extract_text(x_tolerance=1, y_tolerance=3) or ''
                    if text.strip():
                        pages.append(f"--- Trang {index} ---\n{text.strip()}")
        except Exception:
            try:
                from pypdf import PdfReader
            except Exception:
                from PyPDF2 import PdfReader
            reader = PdfReader(str(path))
            for index, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ''
                if text.strip():
                    pages.append(f"--- Trang {index} ---\n{text.strip()}")
        return "\n\n".join(pages)

    @staticmethod
    def _ocr_pdf_pages(path):
        try:
            import pytesseract
            import pypdfium2 as pdfium
        except Exception as exc:
            raise RuntimeError("PDF này là bản scan. Cần pypdfium2, pytesseract và Tesseract OCR để nhận diện chữ.") from exc
        exe = OCRTool._find_tesseract()
        if exe:
            pytesseract.pytesseract.tesseract_cmd = exe
        pdf = pdfium.PdfDocument(str(path))
        pages = []
        for index in range(len(pdf)):
            page = pdf[index]
            bitmap = page.render(scale=3.2)
            image = bitmap.to_pil()
            text = OCRTool._ocr_image_with_preprocessing(image, pytesseract)
            if text:
                pages.append(f"--- Trang {index + 1} OCR ---\n{text}")
        return "\n\n".join(pages) or "Không nhận diện được chữ trong PDF scan. Hãy kiểm tra chất lượng ảnh hoặc gói ngôn ngữ OCR tiếng Việt."

    @staticmethod
    def _extract_image(path):
        try:
            import pytesseract
            from PIL import Image
        except Exception as exc:
            raise RuntimeError("Chưa có OCR ảnh. Cài pytesseract và Tesseract OCR để đọc chữ từ hình ảnh.") from exc
        exe = OCRTool._find_tesseract()
        if exe:
            pytesseract.pytesseract.tesseract_cmd = exe
        image = Image.open(path)
        return OCRTool._ocr_image_with_preprocessing(image, pytesseract)

    @staticmethod
    def _ocr_image_with_preprocessing(image, pytesseract):
        lang = OCRTool._best_tesseract_lang(pytesseract)
        variants = OCRTool._preprocess_image_variants(image)
        tessdata_config = OCRTool._tessdata_config()
        configs = (
            f'{tessdata_config} --oem 3 --psm 6 -c preserve_interword_spaces=1'.strip(),
            f'{tessdata_config} --oem 3 --psm 4 -c preserve_interword_spaces=1'.strip(),
            f'{tessdata_config} --oem 3 --psm 11'.strip(),
        )
        best_text = ''
        best_score = -1
        for variant in variants:
            for config in configs:
                try:
                    text = pytesseract.image_to_string(variant, lang=lang, config=config).strip()
                except Exception:
                    fallback_lang = 'vie' if lang != 'vie' and 'vie' in OCRTool._available_tesseract_langs(pytesseract) else lang
                    text = pytesseract.image_to_string(variant, lang=fallback_lang, config=config).strip()
                score = OCRTool._ocr_text_score(text)
                if score > best_score:
                    best_text = text
                    best_score = score
        return best_text

    @staticmethod
    def _preprocess_image_variants(image):
        try:
            from PIL import ImageOps, ImageFilter
        except Exception:
            return [image]
        source = ImageOps.exif_transpose(image).convert('RGB')
        max_side = max(source.size)
        if max_side and max_side < 2200:
            scale = min(3.0, 2200 / max_side)
            source = source.resize((int(source.width * scale), int(source.height * scale)))
        gray = ImageOps.grayscale(source)
        gray = ImageOps.autocontrast(gray)
        sharp = gray.filter(ImageFilter.MedianFilter(size=3)).filter(ImageFilter.SHARPEN)
        threshold = sharp.point(lambda p: 255 if p > 165 else 0)
        high_contrast = ImageOps.autocontrast(threshold)
        return [gray, sharp, high_contrast]

    @staticmethod
    def _best_tesseract_lang(pytesseract):
        langs = OCRTool._available_tesseract_langs(pytesseract)
        if {'vie', 'eng'}.issubset(langs):
            return 'vie+eng'
        if 'vie' in langs:
            return 'vie'
        return 'eng'

    @staticmethod
    def _available_tesseract_langs(pytesseract):
        local_langs = OCRTool._local_tessdata_langs()
        if local_langs:
            return local_langs
        try:
            return set(pytesseract.get_languages(config=OCRTool._tessdata_config()))
        except Exception:
            return set()

    @staticmethod
    def _local_tessdata_langs():
        tessdata_dir = Path(__file__).resolve().parents[1] / 'tessdata'
        if not tessdata_dir.exists():
            return set()
        return {path.stem for path in tessdata_dir.glob('*.traineddata')}

    @staticmethod
    def _tessdata_config():
        tessdata_dir = Path(__file__).resolve().parents[1] / 'tessdata'
        if tessdata_dir.exists():
            return f'--tessdata-dir {tessdata_dir}'
        return ''

    @staticmethod
    def _ocr_text_score(text):
        if not text:
            return 0
        vietnamese_chars = 'ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ'
        vietnamese_hits = sum(1 for ch in text if ch in vietnamese_chars)
        alpha = sum(1 for ch in text if ch.isalpha())
        return len(text.strip()) + vietnamese_hits * 6 + alpha

    @staticmethod
    def _find_tesseract():
        import shutil
        candidates = [
            shutil.which('tesseract'),
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return ''


class InvoiceOCRParser:
    """Pipeline: raw OCR text -> structured invoice data -> draft expense."""

    PATTERNS = {
        'tax_code': r'\b\d{10}(?:-\d{3})?\b',
        'invoice_number': r'(?:số\s*hóa\s*đơn|số\s*hoá\s*đơn|số\s*hđ|invoice\s*no\.?|no\.?|number)\s*[:.]?\s*([A-Z0-9\-/\.]{3,})',
        'invoice_date': r'(?:ngày|date|dated)\s*[:.]?\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})',
        'amount_before_vat': r'(?:tiền\s*hàng|chưa\s*thuế|trước\s*thuế|subtotal|amount before vat)\s*[:.]?\s*([0-9.,]+)',
        'vat_amount': r'(?:thuế\s*gtgt|vat|tax amount)\s*[0-9%]*\s*[:.]?\s*([0-9.,]+)',
        'total_amount': r'(?:tổng\s*tiền|tổng\s*cộng|total|grand total|cộng\s*tiền\s*thanh\s*toán|tổng\s*cộng\s*tiền\s*thanh\s*toán)\s*[:.]?\s*([0-9.,]+)',
        'supplier_name': r'(?:đơn\s*vị\s*bán|người\s*bán|seller|vendor|công\s*ty)\s*[:.]?\s*(.{5,80}?)(?:\n|mã\s*số\s*thuế|mst|tax)',
    }
    ASCII_PATTERNS = {
        'tax_code': r'(?:ma\s*so\s*thue|mst|tax\s*code)?\s*[:.]?\s*(\b\d{10}(?:-\d{3})?\b)',
        'invoice_number': r'(?:so\s*hoa\s*don|so\s*hd|invoice\s*no\.?|number)\s*[:.]?\s*([A-Z0-9\-/\.]{3,})',
        'invoice_date': r'(?:ngay\s*hoa\s*don|ngay|date|dated)\s*[:.]?\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})',
        'amount_before_vat': r'(?:tien\s*hang|chua\s*thue|truoc\s*thue|subtotal|amount before vat)\s*[:.]?\s*([0-9.,]+)',
        'vat_amount': r'(?:thue\s*gtgt|vat|tax amount)\s*[0-9%]*\s*[:.]?\s*([0-9.,]+)',
        'total_amount': r'(?:tong\s*tien|tong\s*cong|tong\s*tien\s*thanh\s*toan|total|grand total)\s*[:.]?\s*([0-9.,]+)',
        'supplier_name': r'(?:don\s*vi\s*ban|nguoi\s*ban|seller|vendor|cong\s*ty)\s*[:.]?\s*(.{5,80}?)(?:\n|ma\s*so\s*thue|mst|tax)',
    }

    def parse(self, raw_text):
        text = raw_text or ''
        ascii_text = self._strip_accents(text)
        raw_matches = {}
        parsed = {}
        for key, pattern in self.PATTERNS.items():
            match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
            if not match:
                match = re.search(self.ASCII_PATTERNS.get(key, pattern), ascii_text, flags=re.IGNORECASE | re.MULTILINE)
            raw = self._match_value(match)
            raw_matches[key] = raw
            parsed[key] = raw or None

        for key in ('amount_before_vat', 'vat_amount', 'total_amount'):
            parsed[key] = self._parse_number(parsed.get(key))
        parsed['invoice_date'] = self._normalize_date(parsed.get('invoice_date'))
        parsed['vat_rate'] = self._infer_vat_rate(parsed.get('amount_before_vat'), parsed.get('vat_amount'))

        important = ['invoice_number', 'invoice_date', 'supplier_name', 'tax_code', 'total_amount', 'vat_rate']
        filled = sum(1 for key in important if parsed.get(key) not in (None, '', 0))
        parsed['confidence'] = min(1.0, filled / len(important))
        parsed['raw_matches'] = raw_matches
        return parsed

    def _strip_accents(self, value):
        normalized = unicodedata.normalize('NFD', value or '')
        return ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')

    def _match_value(self, match):
        if not match:
            return ''
        if match.lastindex:
            return (match.group(1) or '').strip()
        return (match.group(0) or '').strip()

    def to_draft_expense(self, parsed, project_id=None, category_id=None):
        supplier = parsed.get('supplier_name') or 'Nhà cung cấp OCR'
        number = parsed.get('invoice_number') or 'Chưa có số HĐ'
        return {
            'expense_date': parsed.get('invoice_date') or date.today().isoformat(),
            'project_id': project_id,
            'category_id': category_id,
            'description': f"[OCR] {supplier} - {number}",
            'amount': parsed.get('total_amount') or parsed.get('amount_before_vat') or 0,
            'paid_by': supplier,
            'payment_method': 'Chưa xác định',
            'status': 'draft',
            'notes': f"MST: {parsed.get('tax_code') or ''} | VAT: {parsed.get('vat_rate') or ''}% | Confidence: {parsed.get('confidence', 0):.0%}",
        }

    def _parse_number(self, value):
        if not value:
            return None
        text = str(value).replace(' ', '')
        comma = text.rfind(',')
        dot = text.rfind('.')
        if comma > -1 and dot > -1:
            decimal = ',' if comma > dot else '.'
            thousand = '.' if decimal == ',' else ','
            text = text.replace(thousand, '').replace(decimal, '.')
        elif comma > -1:
            parts = text.split(',')
            text = ''.join(parts) if len(parts[-1]) == 3 and len(parts) > 1 else text.replace(',', '.')
        elif dot > -1:
            parts = text.split('.')
            text = ''.join(parts) if len(parts[-1]) == 3 and len(parts) > 1 else text
        try:
            return float(text)
        except ValueError:
            return None

    def _normalize_date(self, value):
        from datetime import datetime
        if not value:
            return None
        text = str(value).replace('.', '/').replace('-', '/')
        for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y/%m/%d'):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        return None

    def _infer_vat_rate(self, before_vat, vat_amount):
        if not before_vat or vat_amount is None:
            return None
        rate = round(vat_amount / before_vat * 100)
        return rate if rate in (0, 5, 8, 10) else None
