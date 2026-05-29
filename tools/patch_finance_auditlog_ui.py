from pathlib import Path

path = Path('PythonApplication1/web_app.py')
text = path.read_text(encoding='utf-8')

old_html = '''            <h3>Audit log</h3>
            <div class="tablewrap"><table><thead><tr><th>Thời điểm</th><th>Hành động</th><th>Bảng</th><th>Chi tiết</th></tr></thead><tbody id="auditRows"></tbody></table></div>'''
new_html = '''            <div class="toolbar"><h3>Nhật ký kiểm soát gần đây</h3><span class="muted">Chỉ hiển thị 8 dòng mới nhất, ẩn chi tiết kỹ thuật dài.</span></div>
            <div class="tablewrap"><table><thead><tr><th>Thời điểm</th><th>Hành động</th><th>Nghiệp vụ</th></tr></thead><tbody id="auditRows"></tbody></table></div>'''
text = text.replace(old_html, new_html)

old_js = """auditRows.innerHTML=(f.audit_log||[]).map(a=>`<tr><td>${esc(a.created_at)}</td><td>${esc(a.action)}</td><td>${esc(a.entity_type)}</td><td>${esc(String(a.detail||'').slice(0,120))}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">Chưa có audit log.</td></tr>';"""
new_js = """auditRows.innerHTML=(f.audit_log||[]).slice(0,8).map(a=>`<tr><td>${esc(a.created_at)}</td><td>${esc(a.action)}</td><td>${esc(a.entity_type||'Hệ thống')}</td></tr>`).join('')||'<tr><td colspan="3" class="empty">Chưa có nhật ký kiểm soát.</td></tr>';"""
if old_js not in text:
    raise SystemExit('Không tìm thấy đoạn render auditRows cũ')
text = text.replace(old_js, new_js)

path.write_text(text, encoding='utf-8')
