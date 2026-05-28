from pathlib import Path

path = Path('PythonApplication1/web_app.py')
text = path.read_text(encoding='utf-8')

replacements = {
    '<title>FasTrack ERP Web</title>': '<title>FT ERP</title>',
    '<h2>Đăng nhập FasTrack ERP</h2>': '<h2>Đăng nhập FT ERP</h2>',
    '<div class="mobilebar"><strong>FasTrack ERP</strong>': '<div class="mobilebar"><strong>FT ERP</strong>',
    '<div class="brand"><span class="mark">FT</span><span>FasTrack ERP</span></div>': '<div class="brand"><span class="mark">FT</span><span>FT ERP</span></div>',
    "document.getElementById('pageTitle').textContent=viewTitles[id]||'FasTrack ERP';": "document.getElementById('pageTitle').textContent=viewTitles[id]||'FT ERP';",
}
for old, new in replacements.items():
    text = text.replace(old, new)

text = text.replace("const viewTitles={dashboard:'Tổng quan',", "const viewTitles={dashboard:'FT ERP',")
text = text.replace('Quản trị chi phí, công trình, kho và chứng từ trên web.', 'Quản lý chi phí, kho, chứng từ.')

path.write_text(text, encoding='utf-8')
