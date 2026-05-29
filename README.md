# FT ERP

Web app quản lý chi phí, kho, chứng từ, công trình và kế toán xây dựng.

## Deploy hiện tại

Đường deploy chính:

```text
GitHub main -> Cloud Run source trigger -> Dockerfile -> PythonApplication1/app.py
```

Không dùng Firebase App Hosting cho app Python/Flask này.

Cloud Run chạy entrypoint:

```text
app:create_app()
```

## Cấu trúc hiện tại

```text
PythonApplication1/
  app.py                         # entrypoint ổn định cho Cloud Run
  web_app.py                     # legacy monolith, đang tách dần
  routes/                        # route/API mới hoặc đã tách
    registry.py
    system_routes.py
    construction_rules_routes.py
  modules/                       # logic nghiệp vụ
    system_status.py
    construction_rules.py
    ...
  data/                          # dữ liệu mẫu/quy tắc nghiệp vụ
    accounting.db
    construction_accounting_rules.json
  tests/                         # smoke tests
```

## Quy tắc thêm code mới

- API/route mới thêm vào `PythonApplication1/routes/`.
- Logic nghiệp vụ thêm vào `PythonApplication1/modules/`.
- Dữ liệu nghiệp vụ nhỏ thêm vào `PythonApplication1/data/`.
- Không nhồi thêm code lớn vào `PythonApplication1/web_app.py`.
- Không thêm script patch dùng một lần.
- Không commit secret, API key, mật khẩu, log, backup, file export.

## Lệnh bảo trì

Cài môi trường dev/test:

```bash
make install-dev
```

Rà repo có file lớn/module phình to:

```bash
make audit
```

Chạy smoke test nhanh:

```bash
make smoke
```

Chạy toàn bộ test:

```bash
make test
```

## Endpoint kiểm tra

```text
/healthz
/api/system/status
/api/construction-accounting/rules
/api/construction-accounting/rules/MATERIALS
```

## Tài liệu thêm

- `docs/REFACTOR_PLAN.md` - kế hoạch tách monolith.
- `docs/REPO_HYGIENE.md` - quy tắc giữ repo gọn.
- `docs/DOMAIN_AND_DEPLOY.md` - domain và deploy.
- `ROADMAP.md` - roadmap nghiệp vụ.

## Checklist trước khi push lớn

```text
1. Không thêm workflow deploy trùng.
2. Không thêm script patch tạm.
3. Chạy make audit.
4. Chạy make smoke.
5. Dockerfile vẫn chạy app:create_app().
6. Cloud Run revision xanh sau deploy.
```
