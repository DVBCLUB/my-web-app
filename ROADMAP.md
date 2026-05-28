# FT ERP Improvement Roadmap

Mục tiêu: nâng cấp phần mềm theo từng đợt nhỏ, dễ kiểm tra, không làm sập deploy.

## Đợt 1 - Ổn định vận hành

- Health check `/healthz` cho Cloud Run.
- Endpoint `/api/system/status` để kiểm tra revision, database, số dòng chính.
- Recovery admin bằng biến môi trường `FASTRACK_RECOVERY_USER` và `FASTRACK_RECOVERY_KEY`.
- Rút gọn thương hiệu hiển thị thành `FT ERP`.
- Chuẩn hóa nhập ngày chi `DD/MM/YYYY`.

## Đợt 2 - Dữ liệu và bảo mật

- Chuyển database khỏi `/tmp` sang nơi bền vững hơn.
- Thêm backup định kỳ lên Google Drive hoặc Cloud Storage.
- Log đăng nhập, khóa tài khoản, mở khóa an toàn.
- Màn hình quản trị người dùng rõ hơn.

## Đợt 3 - Nghiệp vụ kế toán/kho/công trình

- Phiếu nhập/xuất kho có số chứng từ tự động.
- Quy trình đề nghị chi -> duyệt -> hạch toán.
- Đối chiếu chứng từ, hóa đơn, chi phí.
- Báo cáo chi phí theo công trình, hạng mục, nhà cung cấp.

## Đợt 4 - Trải nghiệm người dùng

- Giao diện mobile cho thủ kho công trường.
- Import Excel/CSV có kiểm lỗi rõ ràng.
- Bộ lọc ngày/tháng/công trình cho từng bảng.
- In phiếu và xuất PDF.

## Nguyên tắc làm tiếp

1. Mỗi lần sửa một nhóm nhỏ.
2. Sau mỗi commit phải build Cloud Run xanh.
3. Test nhanh: đăng nhập, thêm chi phí, xem danh sách, kiểm `/healthz`.
4. Không hard-code mật khẩu trong GitHub.
