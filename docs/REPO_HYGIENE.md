# Repo Hygiene Guide

Mục tiêu: giữ repo gọn, build nhanh, dễ sửa lỗi và dễ thêm tính năng.

## Đường deploy duy nhất

```text
GitHub main -> Cloud Run source trigger -> Dockerfile -> PythonApplication1/app.py
```

Không tạo thêm GitHub Actions deploy, Cloud Build YAML deploy riêng, hoặc Firebase App Hosting cho app Python này nếu không có lý do rõ ràng.

## Không commit các loại file này

- File log, cache, backup, export.
- File Excel/PDF/DOCX sinh ra trong quá trình dùng app.
- SQLite WAL/SHM sidecar.
- File zip/rar/7z tạm.
- Script patch dùng một lần.
- Workflow tự sửa code tạm thời.

## Quy tắc thêm code mới

- Route/API mới: thêm vào `PythonApplication1/routes/`.
- Logic nghiệp vụ: thêm/sửa trong `PythonApplication1/modules/`.
- Dữ liệu nghiệp vụ chuẩn: thêm vào `PythonApplication1/data/` nếu nhỏ và cần cho app.
- Không nhồi thêm HTML/CSS/JS lớn vào `web_app.py`.
- Không thêm secret/mật khẩu/API key vào repo.

## Quy tắc xóa file

Chỉ xóa ngay nếu chắc chắn là:

- File tạm/chạy một lần.
- Workflow deploy cũ không dùng.
- File sinh tự động đã có trong `.gitignore` hoặc `.dockerignore`.

Không xóa ngay nếu là:

- Database mẫu.
- Module nghiệp vụ.
- File cấu hình Docker/Cloud Run đang dùng.
- File dữ liệu quy tắc nghiệp vụ.

## Checklist trước khi merge/push lớn

```text
1. Dockerfile còn chạy app:create_app()
2. Không có workflow deploy trùng
3. Không có script patch tạm
4. Không có file dữ liệu nặng bị commit nhầm
5. Cloud Run revision xanh
6. /healthz trả ok
```
