# Deploy FasTrack ERP Web len Firebase + Google Cloud Run

Ung dung nay la Flask nen Firebase Hosting lam domain/HTTPS va rewrite toan bo request sang Cloud Run.

Project dang dung:

- Google/Firebase project: `fastrackerp-6fd5e`
- Cloud Run service: `fastrack-erp-web`
- Region: `asia-southeast1`
- Firebase Hosting: `https://fastrackerp-6fd5e.web.app`
- Cloud Run URL: `https://fastrack-erp-web-538927184603.asia-southeast1.run.app`

## 1. Chuan bi local

```powershell
gcloud auth login
firebase login
gcloud config set project fastrackerp-6fd5e
```

Bat cac API:

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firebasehosting.googleapis.com
```

Tao Artifact Registry neu chua co:

```powershell
gcloud artifacts repositories create fastrack --repository-format=docker --location=asia-southeast1
```

## 2. Build va deploy Cloud Run

```powershell
gcloud builds submit --config cloudbuild.yaml --substitutions _SERVICE=fastrack-erp-web
```

Neu can mo public access:

```powershell
gcloud run services add-iam-policy-binding fastrack-erp-web --region=asia-southeast1 --member=allUsers --role=roles/run.invoker
```

## 3. Deploy Firebase Hosting

```powershell
firebase deploy --only hosting --project fastrackerp-6fd5e
```

Firebase cap URL mien phi:

- `https://fastrackerp-6fd5e.web.app`
- `https://fastrackerp-6fd5e.firebaseapp.com`

## 4. Gan ten mien rieng

Vao Firebase Console -> Hosting -> Add custom domain, roi lam theo DNS record Firebase dua ra.

## 5. GitHub Actions

Workflow `.github/workflows/deploy-google-firebase.yml` se tu deploy khi push vao `main` sau khi repository co cac secrets:

- `GCP_PROJECT_ID`: `fastrackerp-6fd5e`
- `FIREBASE_PROJECT_ID`: `fastrackerp-6fd5e`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`

Service account can quyen toi thieu:

- `roles/cloudbuild.builds.editor`
- `roles/run.admin`
- `roles/artifactregistry.admin`
- `roles/firebasehosting.admin`
- `roles/iam.serviceAccountUser`

## 6. Luu y du lieu

Ban deploy hien tai copy `PythonApplication1/data/accounting.db` tu repo sang `/tmp/fastrack/accounting.db` khi container khoi dong, phu hop de demo va dung ban dau.

Du lieu ghi moi tren Cloud Run van la tam thoi vi `/tmp` co the mat khi instance bi thay. De van hanh ke toan that, nen chuyen persistence sang Cloud SQL hoac Firestore/Cloud Storage theo nghiep vu.
