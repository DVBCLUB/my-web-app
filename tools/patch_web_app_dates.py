"""
patch_web_app_dates.py
======================
Chạy script này để tự động vá 2 lỗi nhập ngày tháng trong web_app.py:

  Lỗi 1 — bindDateMask: cursor nhảy về cuối mỗi lần gõ; không xử lý paste YYYY-MM-DD
  Lỗi 2 — toIsoDate: nằm ngoài try-catch → lỗi ngày không hợp lệ bị nuốt im lặng

Cách dùng:
    python patch_web_app_dates.py [đường-dẫn/web_app.py]
    (mặc định: web_app.py trong thư mục hiện tại)
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# Patch 1: bindDateMask
# ─────────────────────────────────────────────────────────────────────────────
OLD_MASK = (
    r"const bindDateMask=el=>el&&el.addEventListener('input',()=>"
    r"{let v=el.value.replace(/\D/g,'').slice(0,8);"
    r"if(v.length>=5)v=`${v.slice(0,2)}/${v.slice(2,4)}/${v.slice(4)}`;"
    r"else if(v.length>=3)v=`${v.slice(0,2)}/${v.slice(2)}`;"
    r"el.value=v});"
)

NEW_MASK = (
    # Guard: if element is falsy, do nothing
    "const bindDateMask=el=>{if(!el)return;"
    "el.addEventListener('input',()=>{"
    # Handle paste of YYYY-MM-DD: auto-convert to DD/MM/YYYY
    r"if(/^\d{4}-\d{2}-\d{2}$/.test(el.value)){"
    "const[y,m,d]=el.value.split('-');"
    "el.value=`${d}/${m}/${y}`;return;}"
    # Preserve cursor position while masking
    "const pos=el.selectionStart,oldLen=el.value.length;"
    r"let digits=el.value.replace(/\D/g,'').slice(0,8);"
    "let v=digits.length>4"
    "?`${digits.slice(0,2)}/${digits.slice(2,4)}/${digits.slice(4)}`"
    ":digits.length>2"
    "?`${digits.slice(0,2)}/${digits.slice(2)}`"
    ":digits;"
    "el.value=v;"
    # Restore cursor (setSelectionRange not available on some input types)
    "try{const np=Math.max(0,pos+(v.length-oldLen));"
    "el.setSelectionRange(np,np)}catch(e){}"
    "})}"
    ";"
)

# ─────────────────────────────────────────────────────────────────────────────
# Patch 2: move toIsoDate inside try-catch
# ─────────────────────────────────────────────────────────────────────────────
OLD_SUBMIT = (
    "expenseForm.addEventListener('submit',async e=>{"
    "e.preventDefault();"
    "const data=Object.fromEntries(new FormData(expenseForm).entries());"
    "data.expense_date=toIsoDate(data.expense_date);"
    "try{await api('/api/expenses',"
)

NEW_SUBMIT = (
    "expenseForm.addEventListener('submit',async e=>{"
    "e.preventDefault();"
    "const data=Object.fromEntries(new FormData(expenseForm).entries());"
    # toIsoDate now inside try so validation errors surface as toast
    "try{data.expense_date=toIsoDate(data.expense_date);"
    "await api('/api/expenses',"
)


def patch(src: Path) -> None:
    text = src.read_text(encoding="utf-8")

    hits1 = text.count(OLD_MASK)
    hits2 = text.count(OLD_SUBMIT)

    if hits1 == 0 and hits2 == 0:
        print("⚠  Không tìm thấy đoạn cần vá — file có thể đã được vá hoặc đã thay đổi.")
        return

    errors = []
    if hits1 > 1:
        errors.append(f"bindDateMask: tìm thấy {hits1} lần (kỳ vọng 1)")
    if hits2 > 1:
        errors.append(f"expenseForm submit: tìm thấy {hits2} lần (kỳ vọng 1)")
    if errors:
        print("❌ Lỗi:", "; ".join(errors))
        sys.exit(1)

    # Backup
    backup = src.with_suffix(f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py")
    shutil.copy2(src, backup)
    print(f"✅ Đã sao lưu bản gốc → {backup.name}")

    if hits1 == 1:
        text = text.replace(OLD_MASK, NEW_MASK, 1)
        print("✅ Patch 1 OK — bindDateMask: giữ cursor + xử lý paste YYYY-MM-DD")
    else:
        print("⏭  Patch 1 bỏ qua (không tìm thấy, có thể đã vá)")

    if hits2 == 1:
        text = text.replace(OLD_SUBMIT, NEW_SUBMIT, 1)
        print("✅ Patch 2 OK — toIsoDate đã chuyển vào trong try-catch")
    else:
        print("⏭  Patch 2 bỏ qua (không tìm thấy, có thể đã vá)")

    src.write_text(text, encoding="utf-8")
    print(f"\n✨ Đã ghi {src}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("web_app.py")
    if not target.exists():
        print(f"❌ Không tìm thấy file: {target}")
        sys.exit(1)
    patch(target)
