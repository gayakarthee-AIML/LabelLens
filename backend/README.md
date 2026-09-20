# LabelLens — Backend

FastAPI service implementing the real AI/CV pipeline, rule engine, RBAC, and
report generation behind the LabelLens frontend.

## Stack

- FastAPI + Pydantic v2, JWT auth (python-jose), RBAC (`app/core/rbac.py`)
- SQLAlchemy 2.0 + PostgreSQL, Alembic migrations
- Redis (cache / future session revocation list — see `auth.py` logout note)
- MinIO / any S3-compatible store for original + processed images (`boto3`)
- OpenCV (`cv_service.py`) — denoise, CLAHE contrast, perspective correction,
  blur/brightness/glare quality analysis
- Ultralytics YOLO (`yolo_service.py`) — label/barcode region detection
- PaddleOCR (`ocr_service.py`) — multilingual text recognition
- pyzbar (`barcode_service.py`) — EAN/UPC/QR decode + registry cross-check
- Configurable rule engine (`rule_engine.py`) reading
  `app/rules/legal_metrology_rules.yaml` (seeded into Postgres)
- ReportLab (`pdf_service.py`) and python-docx (`docx_service.py`) reports
- Kafka-ready event bus (`event_bus.py`), no-op until `KAFKA_ENABLED=true`

## Important honesty notes

This code was written in a sandboxed environment with **no outbound network
access**, so none of it has been `pip install`-ed or executed here. It is
written against each library's real, documented API (PaddleOCR, ultralytics,
pyzbar, reportlab, python-docx, boto3, SQLAlchemy 2.0) rather than guessed —
but you should expect the normal amount of first-run debugging any new
FastAPI + native-CV-library project needs. Two things to know going in:

1. **YOLO weights.** `yolo_service.py` looks for a trained model at
   `YOLO_WEIGHTS_PATH`. No such model is included (training one needs a
   labeled dataset of package photos this project doesn't have). Until you
   train and drop one in, region detection degrades to "treat the whole
   image as one region" — OCR still runs for real over the full frame, it's
   just not pre-cropped to label/barcode sub-regions.
2. **PaddleOCR first run.** PaddleOCR downloads detection/recognition/
   classification model weights per language the first time each language is
   used. That means the container's first OCR call per language will be slow
   and needs internet access at *runtime* (this is normal for PaddleOCR, not
   specific to this project).

## Local setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d postgres redis minio   # or run these three yourself
cp .env.example .env                         # edit DATABASE_URL/etc. if not using docker-compose defaults
uvicorn app.main:app --reload
```

On startup in `ENVIRONMENT=development`, the app auto-creates tables and
seeds:
- One demo account per role (see `app/db/seed.py` for the printed
  credentials — `insp001` / `sinsp001` / `admin001` / `reg001`)
- The Legal Metrology rule set from `app/rules/legal_metrology_rules.yaml`
- Two sample product-registry entries for barcode cross-check testing

For anything beyond local dev, generate a real Alembic migration instead of
relying on `Base.metadata.create_all`:

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
```

## Running via Docker Compose (API + Postgres + Redis + MinIO)

```bash
docker compose up --build
```

## Running from Google Colab and exposing a public URL

Since Colab notebooks aren't reachable directly, tunnel the FastAPI port:

```python
!pip install fastapi uvicorn pyngrok -q
# ... pip install -r requirements.txt, clone/upload this backend/ folder ...

from pyngrok import ngrok
public_url = ngrok.connect(8000)
print(public_url)  # paste this into frontend/.env as VITE_API_BASE_URL=<public_url>/api/v1

!uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Colab has no persistent Postgres/Redis/MinIO — for a quick end-to-end demo,
point `DATABASE_URL` at a free-tier hosted Postgres (e.g. Neon, Supabase) and
`S3_ENDPOINT_URL` at a free-tier S3-compatible bucket, or run
`docker compose up -d postgres redis minio` in the same Colab VM if Docker is
available in your runtime.

## RBAC — how role selection on the frontend actually gets enforced

1. Frontend login screen: role is a **UI hint** for which form to show.
2. `POST /auth/login` looks the account up by `officialId` only, verifies the
   password, and issues a JWT carrying the account's real `role` from the
   `users` table.
3. Every protected endpoint depends on `require_roles(...)` or
   `require_permission(...)` (`app/core/rbac.py`), which reads the role off
   the authenticated `User` row fetched fresh from the database on each
   request (`app/api/deps.py::get_current_user`) — never off the login
   request body, and never off a role claim alone without re-verifying
   against the user record.

## API surface (all under `/api/v1`)

```
POST   /auth/login
POST   /auth/refresh
POST   /auth/logout
GET    /auth/me

POST   /inspections
POST   /inspections/{id}/images
POST   /inspections/{id}/analyze
POST   /inspections/{id}/verify
POST   /inspections/{id}/finalize
GET    /inspections/{id}
GET    /inspections
GET    /inspections/{id}/report.pdf
GET    /inspections/{id}/report.docx

GET    /rules
POST   /rules
PATCH  /rules/{ruleId}
POST   /rules/{ruleId}/toggle
GET    /rules/export
POST   /rules/import
GET    /rules/history

GET    /products/{barcode}
GET    /products/{barcode}/history

GET    /dashboard/summary
GET    /dashboard/enforcement

POST   /font-size/check              # reference-card font-size calibration — separate from /inspections analysis
GET    /font-size/standards
POST   /font-size/standards
PATCH  /font-size/standards/{standardId}
```

## Language scope (OCR)

Per the brief, PaddleOCR is run only against **English and Hindi** —
`Settings.paddleocr_langs` (default `en,hi`). See `app/services/ocr_service.py`.

## Font size checking — reference-card method

A separate feature/button from OCR-based declaration extraction, per the
brief. The inspector photographs a standard ID-1 reference card (e.g. a
debit/credit card, 85.60mm × 53.98mm by default — configurable) alongside
the declaration text. `app/services/font_size_service.py` detects the card
by aspect ratio, derives a millimetres-per-pixel scale from its known real
size, and converts OCR bounding-box heights into millimetres, which are then
compared against configurable minimum-height standards
(`app/rules/font_size_standards.yaml`, editable via `/font-size/standards`
— same dynamic-rule/ETL pattern as the compliance rules).

## QR/barcode scanning — electronics only

Per the brief, barcode/QR scanning and registry cross-checking is only
performed for electronic products (`Settings.electronic_categories`, default
`Electronics,Electronics Accessory,Electronic Appliance`). For any other
category, the barcode capture step is skipped client-side and the backend
reports `registryMatch: "NOT_APPLICABLE"` rather than attempting a scan.

## Consumer Lite

Out of scope, and nothing in this backend implements it — no consumer role,
no consumer endpoints, no consumer tables.
