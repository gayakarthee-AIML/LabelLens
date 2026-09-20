# LabelLens

This is the prototype we built for the SIH internal round! LabelLens is an
AI-assisted Legal Metrology compliance inspector — it scans physical
packages, labels, and e-commerce listings using OCR and computer vision, and
checks them against the **Legal Metrology (Packaged Commodities) Rules,
2011**.

The core design principle: **AI extracts, it never decides.** Every
PASS / FAIL / NEEDS VERIFICATION outcome is produced by a deterministic,
human-editable rule engine — not by a model. AI (OCR, and optionally a
vision model) is only ever used to read what's printed on a label; the
compliance call is always made by code you can read, audit, and change.

## What it does

- **📦 Scan Package** — capture all sides of a physical product, or use
  **spin-scan** (rotate it in front of the camera) instead of individual
  static photos.
- **🏷️ Scan Label** — a lighter single-panel scan for just the label.
- **🌐 E-Commerce Listing** — paste a product listing URL; LabelLens fetches
  the page (with a headless-browser render for JS-heavy sites), extracts
  structured data (JSON-LD, images, price), and runs the same compliance
  checks against it.
- **Mandatory declaration extraction** — Common Name, Net Quantity, MRP,
  Manufacturer/Packer/Importer, Country of Origin, Manufacturing Date,
  Consumer Care, Unit Sale Price — read directly off the label via OCR.
- **Barcode/QR verification** — scanned and cross-checked against a product
  registry, scoped to electronic products only.
- **Font size check** — a separate reference-card calibration flow that
  converts a photo's pixel measurements into real millimetres to check
  Rule 8 minimum text-height requirements.
- **Dynamic rule engine** — compliance rules live in an editable YAML/DB
  source, not hardcoded logic, so they can be updated without a redeploy.
- **Role-based access** — Inspector, Senior Inspector, Administrator, and
  Regulator roles with different permissions.
- **Offline-first PWA** — capture and queue inspections without
  connectivity; sync and analyze once back online.
- **PDF/DOCX inspection reports**, an evidence viewer, and a full audit log.
- **Hindi/English UI** (partial coverage — see `frontend/README.md`).

## Architecture

```
Frontend (React + TS, PWA)  ──HTTP──>  Backend (FastAPI)
                                            │
                          OpenCV preprocessing → PaddleOCR / vision model
                                            │
                              Declaration extraction (regex + spatial
                              pairing over OCR bounding boxes)
                                            │
                       Deterministic rule engine  ←── legal_metrology_rules.yaml
                                            │
                         PASS / FAIL / NEEDS VERIFICATION + evidence
```

See `backend/README.md` and `frontend/README.md` for the full breakdown of
each service.

## Tech stack

**Backend:** FastAPI, PostgreSQL + SQLAlchemy 2.0, Redis, MinIO (S3-compatible
storage), OpenCV, PaddleOCR, Ultralytics YOLO, pyzbar, Playwright (for the
e-commerce listing fetch), ReportLab + python-docx for reports.

**Frontend:** React 18 + TypeScript, Vite, `vite-plugin-pwa`, IndexedDB
(`idb`) for the offline queue, Recharts.

## Quick start

Full setup instructions (Docker Compose, manual venv setup, environment
variables) are in [`backend/README.md`](backend/README.md) and
[`frontend/README.md`](frontend/README.md). The short version:

```bash
# Backend
cd backend
cp .env.example .env
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
docker compose up -d postgres redis minio
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
cp .env.example .env
npm install
npm run dev
```

Then open `http://localhost:5173`.

### Demo accounts

Seeded automatically on first backend startup:

| Role | Official ID | Password |
|---|---|---|
| Inspector | `insp001` | `Inspector@123` |
| Senior Inspector | `sinsp001` | `SeniorInsp@123` |
| Administrator | `admin001` | `Admin@123` |
| Regulator | `reg001` | `Regulator@123` |

## Project structure

```
labellens/
├── backend/          FastAPI service — OCR pipeline, rule engine, RBAC, reports
│   ├── app/
│   │   ├── api/routers/       Auth, inspections, rules, products, dashboard, font-size
│   │   ├── services/          cv, ocr, yolo, barcode, declaration extraction, rule engine,
│   │   │                      e-commerce fetch, PDF/DOCX generation
│   │   ├── rules/              legal_metrology_rules.yaml — editable, versioned rule set
│   │   └── db/                 Models, seed data, migrations
│   └── README.md
└── frontend/          React + TS PWA
    ├── src/
    │   ├── pages/              Inspection flows, dashboard, rule management, etc.
    │   ├── components/         Camera/spin capture, declaration table, rule results
    │   └── services/           Offline queue, sync, image quality pre-checks
    └── README.md
```

## Known limitations (being upfront about it)

- OCR accuracy on real-world labels varies with layout, font, and print
  quality — see `backend/app/services/declaration_service.py` for the
  extraction logic and its documented edge cases.
- The font-size check estimates from pixel measurements calibrated against a
  reference card; it is not a certified physical measurement tool.
- Optional AI-assisted extraction paths (for e-commerce listings, and
  optionally for physical scans via a vision model) always defer the final
  compliance decision to the deterministic rule engine — never to the model
  itself.

## License

TODO — add your team's chosen license here (MIT is a common default for
hackathon submissions).
