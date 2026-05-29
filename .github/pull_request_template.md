## Mục tiêu thay đổi

Mô tả ngắn thay đổi này làm gì:

-

## Loại thay đổi

- [ ] Sửa lỗi
- [ ] Thêm tính năng
- [ ] Refactor/tinh gọn code
- [ ] Tài liệu/cấu hình
- [ ] Khác

## Checklist bắt buộc

- [ ] Không thêm workflow deploy trùng. Deploy vẫn qua Cloud Run source trigger.
- [ ] Không thêm script patch dùng một lần.
- [ ] Không commit secret, API key, mật khẩu, log, backup, file export.
- [ ] Không nhồi thêm code lớn vào `PythonApplication1/web_app.py` nếu có thể tách module.
- [ ] API/route mới nằm trong `PythonApplication1/routes/`.
- [ ] Logic nghiệp vụ mới nằm trong `PythonApplication1/modules/`.
- [ ] Đã chạy `make preflight` hoặc ghi rõ lý do chưa chạy.

## Test đã chạy

```text
make preflight
```

## Rủi ro / Ghi chú

-
