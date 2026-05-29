# FT ERP Refactor Plan

Mục tiêu: giảm phình code, dễ sửa lỗi, dễ thêm tính năng, không làm sập Cloud Run.

## Nguyên tắc bắt buộc từ giai đoạn này

1. Không thêm workflow/script vá tạm để tự sửa `web_app.py`.
2. Không nhồi thêm HTML/CSS/JS lớn trực tiếp vào `web_app.py` nếu có thể tách.
3. Mỗi đợt refactor chỉ đổi một nhóm nhỏ và phải deploy xanh.
4. Không xóa file dữ liệu hoặc module nghiệp vụ nếu chưa xác minh dependency.
5. Cloud Run chỉ chạy qua entrypoint ổn định `app:create_app()`.

## Trạng thái hiện tại

- `PythonApplication1/app.py` là entrypoint mới.
- `Dockerfile` đã trỏ Gunicorn về `app:create_app()`.
- `PythonApplication1/web_app.py` vẫn là legacy monolith chứa route, HTML, CSS, JS.

## Cấu trúc mục tiêu

```text
PythonApplication1/
  app.py
  routes/
    auth_routes.py
    expense_routes.py
    inventory_routes.py
    project_routes.py
    accounting_routes.py
    finance_routes.py
    construction_routes.py
    system_routes.py
  templates/
    index.html
  static/
    css/app.css
    js/app.js
    service-worker.js
  modules/
    ... business modules ...
  data/
    accounting.db
    construction_accounting_rules.json
```

## Lộ trình triển khai

### Đợt 1 - Ổn định entrypoint và deploy

- Thêm `app.py`.
- Dockerfile chạy `app:create_app()`.
- Không thay đổi logic nghiệp vụ.

### Đợt 2 - Tách static frontend

- Tách `INDEX_HTML` ra `templates/index.html`.
- Tách CSS ra `static/css/app.css`.
- Tách JS ra `static/js/app.js`.
- Giữ route cũ trả cùng giao diện.

### Đợt 3 - Tách API route theo nghiệp vụ

- Tách auth/system trước vì ít phụ thuộc.
- Sau đó tách expenses, inventory, projects, construction, accounting, finance.
- Dùng Flask Blueprint.

### Đợt 4 - Giảm dependency nặng

- Kiểm tra thư viện không dùng: OCR, PDF, matplotlib, reportlab.
- Chỉ bỏ khi chắc chắn không ảnh hưởng chức năng.

### Đợt 5 - Test tối thiểu

- Test `/healthz`.
- Test đăng nhập.
- Test thêm chi phí ngày `DD/MM/YYYY`.
- Test dashboard load.

## Checklist sau mỗi lần sửa

```text
1. Cloud Build xanh
2. Cloud Run revision xanh
3. /healthz trả ok
4. Đăng nhập được
5. Mở Chi phí được
6. Thử nhập ngày chi dạng 28052026
```
