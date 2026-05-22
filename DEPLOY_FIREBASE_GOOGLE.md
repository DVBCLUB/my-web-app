# Deploy FasTrack ERP Web lên Firebase + Google Cloud Run

Ứng dụng này là Flask nên Firebase Hosting sẽ làm domain/HTTPS và rewrite toàn bộ request sang Cloud Run.

## 1. Chuẩn bị

```powershell
gcloud auth login
firebase login
gcloud config set project YOUR_PROJECT_ID
firebase use --add
```

Bật các API:

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

Tạo Artifact Registry:

```powershell
gcloud artifacts repositories create fastrack --repository-format=docker --location=asia-southeast1
```

## 2. Build và deploy Cloud Run

```powershell
gcloud builds submit --config cloudbuild.yaml
```

## 3. Deploy Firebase Hosting rewrite

```powershell
firebase deploy --only hosting
```

Sau khi deploy, Firebase cấp URL miễn phí dạng:

- `https://YOUR_PROJECT_ID.web.app`
- `https://YOUR_PROJECT_ID.firebaseapp.com`

## 4. Gắn tên miền

Vào Firebase Console -> Hosting -> Add custom domain, rồi làm theo DNS record Firebase đưa ra.

## Lưu ý dữ liệu

Bản deploy này copy `PythonApplication1/data/accounting.db` từ repo sang `/tmp/fastrack/accounting.db` khi container khởi động. Như vậy web demo có dữ liệu ban đầu từ GitHub.

Dữ liệu ghi mới trên Cloud Run vẫn là tạm thời vì `/tmp` có thể mất khi instance bị thay. Để vận hành kế toán thật cần chuyển persistence sang Cloud SQL hoặc Firestore/Cloud Storage theo nghiệp vụ.

## 5. GitHub Actions

Workflow `.github/workflows/deploy-google-firebase.yml` sẽ tự deploy khi push vào `main`.

Tạo các GitHub repository secrets:

- `GCP_PROJECT_ID`
- `FIREBASE_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`

Service account cần quyền tối thiểu cho Cloud Build, Cloud Run, Artifact Registry và Firebase Hosting deploy.
