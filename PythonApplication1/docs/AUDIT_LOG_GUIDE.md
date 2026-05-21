# Audit Log — Purpose and Use Cases

## Mục đích
Audit log ghi lại mọi thao tác quan trọng trên hệ thống để:

- Giám sát hoạt động người dùng (who did what, when).
- Hỗ trợ điều tra sự cố khi có lỗi/khác thường.
- Đảm bảo tuân thủ quy định (compliance, internal controls).
- Hỗ trợ phục hồi (recovery) và đánh giá thay đổi dữ liệu.

## Thông tin thường ghi
- `timestamp`: thời điểm thực hiện.
- `user_id` / `username`: ai thực hiện.
- `action`: hành động (READ, CREATE, UPDATE, DELETE, EXPORT, POST, ROLL_BACK...).
- `target`: đối tượng chịu tác động (table, screen, report, document id).
- `details`: payload chi tiết (có thể là JSON chứa thay đổi, query params, file exported).

## Use cases
1. Bảo mật: phát hiện truy cập bất thường, truy cập trái phép.
2. Vận hành: xác định bước gây lỗi sau khi một báo cáo lệch số.
3. Audit nội bộ/kiểm toán: cung cấp chứng cứ về thay đổi sổ sách.
4. Hỗ trợ người dùng: trả lời câu hỏi "ai đã chỉnh mục này?".
5. Rollback/Recover: xác định thay đổi để thực hiện rollback thủ công nếu cần.

## Gợi ý triển khai thêm (tương lai)
- Thêm filter theo thời gian, user, action, target.
- Thêm chế độ export CSV/Excel cho kiểm toán viên.
- Giữ bản copy log lâu dài (retention policy) hoặc gửi log sang ELK/Cloud SIEM.
- Cân nhắc mask dữ liệu nhạy cảm trong `details` (PII) trước khi lưu.
- Thêm một chế độ alert (email/SMS) khi phát hiện hành động nghiêm trọng.

## Vị trí trong ứng dụng
- `modules/audit_log.py` (nếu có): nơi ghi/đọc log.
- Giao diện `Audit log` trong `ui/main_window.py` hiển thị log, có thể bổ sung filter và export.

---
Đã tạo: 2026-05-20
