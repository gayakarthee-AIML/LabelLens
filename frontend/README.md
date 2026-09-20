# LabelLens — Frontend

React + TypeScript + Vite PWA for Legal Metrology field inspection and compliance
review. This is the inspector-facing client; it holds no compliance logic of its
own beyond client-side image quality pre-checks — OCR, the rule engine, and
barcode verification all run on the backend (`../backend`).

## Stack

- React 18 + TypeScript, Vite build
- `react-router-dom` for routing, role-gated via `ProtectedRoute`
- `recharts` for dashboard/enforcement charts
- `idb` (IndexedDB) for the offline inspection queue
- `vite-plugin-pwa` for the service worker / installable PWA shell

## Setup

```bash
cd frontend
npm install
cp .env.example .env
# edit .env — VITE_API_BASE_URL must point at a running backend (see ../backend/README.md)
npm run dev
```

This environment could not run `npm install` itself (no outbound network access
in the sandbox that generated this code), so the dependency tree has not been
installed or built here — install and run it in your own machine, Colab, or CI.

## Project layout

```
src/
  api/          Typed HTTP client + one module per backend resource
  components/   Presentational + camera components (CameraCapture is the real
                 getUserMedia integration; MultiAngleCapture sequences it)
  context/      AuthContext (session + frontend permission hints),
                 OfflineContext (connectivity + sync queue state)
  pages/        One file per route
  router/       Route table + role gating
  services/     offlineDb.ts (IndexedDB), syncService.ts (drains the queue
                 against the real API), imageQuality.ts (client-side blur/
                 brightness/glare pre-check), serviceWorkerRegistration.ts
  styles/       Design tokens + global stylesheet
  types/        Shared domain types — keep in sync with backend/app/schemas
```

## Role-based login

The login screen offers four access types (Inspector, Senior Inspector,
Administrator, Regulator). Selecting one only chooses which login form is
shown — the value is sent to `POST /auth/login` as a UX hint. **The backend
independently looks up the account and returns its real role**; the frontend
never grants permissions based on what was clicked. See
`src/context/AuthContext.tsx` (`PERMISSIONS` map + `can()`) for the
UI-side hiding logic, and `backend/app/core/rbac.py` for the authoritative
enforcement.

## Offline behavior

- `services/offlineDb.ts` stores inspections in IndexedDB keyed by a
  client-generated UUID until the server assigns a real ID.
- If `POST /inspections` (or any step after it) fails because the API is
  unreachable, `NewInspectionPage` saves the draft — product details and every
  captured image — locally instead of fabricating a result.
- `OfflineContext` listens for the browser `online` event and calls
  `syncService.trySyncPending()`, which replays each queued inspection through
  the real API (create → upload images → analyze) so it ends up in exactly the
  state a live-connected inspection would.

## Connecting to a backend running elsewhere (e.g. Google Colab)

Set `VITE_API_BASE_URL` to the public tunnel URL (e.g. an `ngrok` URL printed
by the Colab notebook in `backend/README.md`) and restart `npm run dev` (Vite
only reads `.env` at startup).
