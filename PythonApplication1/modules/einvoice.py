"""e-Invoice provider adapter skeleton with local status persistence."""

import json
import os
import urllib.request

from database import get_connection


class EInvoiceManager:
    PROVIDERS = {
        'MISA': os.environ.get('EINVOICE_MISA_URL', ''),
        'VNPT': os.environ.get('EINVOICE_VNPT_URL', ''),
        'VIETTEL': os.environ.get('EINVOICE_VIETTEL_URL', ''),
        'FPT': os.environ.get('EINVOICE_FPT_URL', ''),
    }

    def __init__(self):
        self.conn = get_connection()

    def push_document(self, document_id, provider='MISA'):
        doc = self._get_document(document_id)
        if not doc:
            raise ValueError('Khong tim thay chung tu')
        payload = self._build_payload(doc)
        endpoint = self.PROVIDERS.get(provider.upper()) or os.environ.get('EINVOICE_API_URL', '')
        if not endpoint:
            self._save_status(document_id, provider, 'pending_config', '', '', payload)
            return {'status': 'pending_config', 'message': 'Chua cau hinh endpoint API HĐĐT'}
        token = os.environ.get(f'EINVOICE_{provider.upper()}_TOKEN') or os.environ.get('EINVOICE_API_TOKEN', '')
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'},
            method='POST',
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8') or '{}')
        tax_code = data.get('tax_authority_code') or data.get('ma_cqt') or data.get('code') or ''
        tx_id = data.get('transaction_id') or data.get('id') or ''
        self._save_status(document_id, provider, 'issued', tax_code, tx_id, payload)
        return {'status': 'issued', 'tax_authority_code': tax_code, 'transaction_id': tx_id}

    def _get_document(self, document_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM documents WHERE id = ?', (document_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def _build_payload(self, doc):
        return {
            'document_id': doc['id'],
            'invoice_number': doc.get('doc_number'),
            'invoice_date': doc.get('doc_date'),
            'buyer_name': doc.get('supplier_name'),
            'description': doc.get('description'),
            'total_amount': doc.get('amount') or 0,
        }

    def _save_status(self, document_id, provider, status, tax_authority_code, transaction_id, payload):
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE documents
            SET einvoice_provider = ?, einvoice_status = ?,
                einvoice_tax_authority_code = ?, einvoice_transaction_id = ?,
                einvoice_payload = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (provider, status, tax_authority_code, transaction_id, json.dumps(payload, ensure_ascii=False), document_id))
        self.conn.commit()
