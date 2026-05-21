"""QR generation for printed accounting documents."""

import hashlib
from pathlib import Path

from database import get_connection


class QRVerificationManager:
    def __init__(self, output_dir='documents/qr'):
        self.conn = get_connection()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def payload_for_document(self, document_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, doc_number, doc_date, amount, qr_token FROM documents WHERE id = ?', (document_id,))
        doc = cursor.fetchone()
        if not doc:
            raise ValueError('Khong tim thay chung tu')
        token = doc['qr_token'] or self._ensure_token(document_id, doc['doc_number'], doc['doc_date'], doc['amount'])
        return f"FasTrackERP|DOC={doc['id']}|NO={doc['doc_number'] or ''}|DATE={doc['doc_date'] or ''}|AMT={doc['amount'] or 0}|TOKEN={token}"

    def create_qr_for_document(self, document_id):
        payload = self.payload_for_document(document_id)
        path = self.output_dir / f"document_{document_id}_qr.png"
        try:
            import qrcode
            img = qrcode.make(payload)
            img.save(path)
        except ImportError:
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (360, 120), 'white')
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), payload[:120], fill='black')
            img.save(path)
        return str(path), payload

    def _ensure_token(self, document_id, doc_number, doc_date, amount):
        raw = f"{document_id}|{doc_number}|{doc_date}|{amount}"
        token = hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]
        cursor = self.conn.cursor()
        cursor.execute('UPDATE documents SET qr_token = ? WHERE id = ?', (token, document_id))
        self.conn.commit()
        return token
