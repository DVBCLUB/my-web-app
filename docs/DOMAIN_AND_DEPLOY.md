# Domain & Deploy Guide for FT ERP

## Hướng deploy hiện tại

Đang dùng luồng chính:

```text
GitHub main -> Cloud Build -> Dockerfile -> Cloud Run service fastrack-erp-web
```

Không dùng Firebase App Hosting cho app Python/Flask.

## URL hiện tại

Cloud Run mặc định tạo URL dài dạng:

```text
https://fastrack-erp-web-...asia-southeast1.run.app
```

Không thể rút ngắn URL này bằng code Python. Muốn tên ngắn cần dùng một trong hai cách dưới đây.

## Cách 1: dùng Firebase Hosting domain

Repo đã có `firebase.json` rewrite về Cloud Run service `fastrack-erp-web` tại region `asia-southeast1`.

Sau khi deploy Firebase Hosting, có thể dùng URL ngắn hơn dạng:

```text
https://<project-id>.web.app
https://<project-id>.firebaseapp.com
```

Lệnh triển khai nếu dùng Firebase CLI:

```bash
firebase deploy --only hosting
```

## Cách 2: dùng domain riêng

Ví dụ:

```text
erp.congty.com
ketoan.congty.com
ft.congty.com
```

Các bước tổng quát:

1. Vào Google Cloud Console -> Cloud Run -> fastrack-erp-web.
2. Chọn Manage custom domains hoặc Domain mappings.
3. Thêm domain/subdomain muốn dùng.
4. Google sẽ đưa bản ghi DNS.
5. Vào nơi mua domain, thêm bản ghi DNS theo hướng dẫn.
6. Chờ xác minh và cấp SSL.

## Gợi ý tên ngắn

- `ft.company.vn`
- `erp.company.vn`
- `kho.company.vn`
- `ketoan.company.vn`
- `xaydung.company.vn`

## Lưu ý

- Code chỉ đổi được tên hiển thị trong app, không đổi được URL Cloud Run.
- Muốn đổi URL phải cấu hình domain/DNS trong Google Cloud hoặc Firebase.
- Không dùng lại Firebase App Hosting cho app Flask hiện tại.
