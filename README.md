# Border Security Surveillance System

AI-powered border surveillance platform: border officers upload CCTV footage, the
backend runs real computer-vision models over it (people & faces, vehicles &
number plates, drones/aerial intrusions, vandalism/anomalous activity) and the
operations dashboard shows detections, alerts, event history and analytics.

There is no mock inference anywhere: every detection, alert and analytic in the UI
comes from a model actually run over the uploaded video on the server.

## What it detects

| Capability | Model | Source |
| --- | --- | --- |
| People, vehicles (car/bus/truck/motorcycle/bicycle), weapon-like objects (knife, bat, scissors) | YOLOv8n (COCO) | `ultralytics/assets` release |
| Faces | YuNet ONNX | OpenCV Zoo |
| Number plate localisation | YOLOv11n plate detector | `morsetechlab/yolov11-license-plate-detection` |
| Number plate text | EasyOCR (`english_g2`) | JaidedAI EasyOCR |
| Drones / UAVs (Shahed 136/238, MQ-9, DJI Mavic, Mohajer-6) | YOLOv8 UAV fine-tune | `Tuzelkhan/drone-yolov8` |
| Vandalism / abnormal motion | MOG2 background subtraction + robust motion-energy z-score, correlated with person boxes | in-repo (`app/ai/vandalism.py`) |

Weights are **not** committed. They are downloaded on first use (or explicitly via
the models script / System status page) into `BSS_MODELS_DIR`.

## Architecture

```
backend/app
  config.py                environment-driven settings
  db.py  models.py         SQLAlchemy (SQLite WAL) persistence
  schemas.py               API contracts
  security.py  deps.py     JWT auth (header or query token for media)
  events.py                in-process event bus -> WebSocket
  ai/registry.py           model download + lazy load lifecycle
  ai/detectors.py          per-frame detectors (objects, faces, plates+OCR, drones)
  ai/vandalism.py          motion-anomaly detector
  ai/pipeline.py           frame sampling, tracking, annotation, summary
  services/processing.py   background worker: analyse -> persist -> publish
  services/alert_rules.py  detection -> alert severity rules + cooldowns
  services/settings_service.py  runtime-tunable settings
  routers/                 auth, videos, detections, alerts, analytics, system, media, ws
frontend/src
  lib/api.ts               typed API client (incl. upload progress, media URLs)
  state/AuthContext.tsx    session handling
  state/LiveContext.tsx    WebSocket progress, live alerts, toasts
  components/              app shell, alert toasts, shared UI primitives
  pages/                   login, dashboard, upload, viewer, detections,
                           alerts, history, analytics, system status, settings
```

Flow: upload → job queued → worker samples frames → detectors + tracker →
detections and alerts persisted with snapshots → progress/detection/alert events
pushed over `/api/ws` → dashboard and alert toasts update live → annotated MP4 and
JSON report available for download.

## Requirements

- Python 3.10+
- Node 20+
- `ffmpeg` (with libx264) — OpenCV cannot encode H.264, so annotated renders are
  transcoded with ffmpeg to play in browsers. Without it the render still exists
  but Chrome/Safari will not decode it.
- ~2.5 GB disk for model weights, sample footage and renders
- CPU-only is fine (that is the default configuration)

## Setup

### 1. Configuration

```bash
cp .env.example .env
# edit .env: set BSS_SECRET_KEY and BSS_ADMIN_PASSWORD at minimum
```

`.env` is git-ignored; no credentials live in source.

Key variables:

| Variable | Meaning |
| --- | --- |
| `BSS_SECRET_KEY` | JWT signing key (required in production) |
| `BSS_ADMIN_USERNAME` / `BSS_ADMIN_PASSWORD` | bootstrap officer account created on first start |
| `BSS_DATA_DIR` / `BSS_MODELS_DIR` | uploads, renders, snapshots, DB / model weights |
| `BSS_DATABASE_URL` | defaults to SQLite inside the data dir |
| `BSS_FRAME_STRIDE` | analyse every Nth frame (speed vs. sensitivity) |
| `BSS_*_CONFIDENCE` | per-detector thresholds |
| `BSS_ENABLE_PLATE_OCR` / `BSS_WRITE_ANNOTATED_VIDEO` | optional heavy outputs |
| `BSS_CORS_ORIGINS` | comma-separated allowed origins |
| `VITE_API_BASE_URL` | frontend API base (leave empty to use the dev proxy) |

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu   # CPU-only; omit the index-url for CUDA wheels
pip install -r requirements.txt
python scripts/download_models.py          # ~250 MB, one-off
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

API docs: <http://localhost:8000/docs> · health: <http://localhost:8000/api/health>

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173> and sign in with `BSS_ADMIN_USERNAME` /
`BSS_ADMIN_PASSWORD`. The Vite dev server proxies `/api` (including the WebSocket)
to `http://127.0.0.1:8000`.

## Using the system

1. **Upload footage** — drag a clip in, set checkpoint/notes, submit. Upload
   progress is real (XHR progress events).
2. **Watch the analysis** — the clip page and dashboard stream live progress,
   detection counts, people-in-frame and the anomaly score over the WebSocket.
   New alerts appear as toasts on any page.
3. **Review** — the viewer plays the original or the annotated render; clicking a
   detection or alert timestamp seeks the player to that moment. Snapshots are
   stored per detection.
4. **Act** — acknowledge alerts individually or in bulk on the alert desk.
5. **Analyse** — detection/alert trends, category mix, severity mix, checkpoint
   hotspots, recent plate reads and inference throughput.
6. **Tune** — Settings changes thresholds, stride, OCR/render outputs and alert
   rules for subsequent jobs; re-analyse a clip to apply them.
7. **Export** — per-clip JSON report with metadata, detections and alerts.

## API overview

```
POST   /api/auth/login                    -> JWT
GET    /api/auth/me
POST   /api/videos                        multipart upload (+ auto-process)
GET    /api/videos                        filter by status/search, paginated
GET    /api/videos/{id}
POST   /api/videos/{id}/reprocess
DELETE /api/videos/{id}
GET    /api/videos/{id}/stream?annotated= range-capable playback
GET    /api/videos/{id}/export            JSON report
GET    /api/detections                    filter by video/category/confidence/search
GET    /api/detections/categories
GET    /api/alerts                        filter by severity/acknowledged
GET    /api/alerts/live
POST   /api/alerts/{id}/acknowledge
POST   /api/alerts/acknowledge-all
GET    /api/alerts/video/{id}/timeline
GET    /api/analytics/dashboard
GET    /api/analytics?days=
GET    /api/system/status
POST   /api/system/models/download
GET    /api/settings   PUT /api/settings
GET    /api/media/snapshots/{name}
WS     /api/ws?token=                     progress, detections, alerts, completion
GET    /api/health                        public
```

## Tests, lint, types

```bash
cd backend && source .venv/bin/activate
pytest -q          # 26 tests: API contract + AI components
ruff check . && ruff format --check .

cd ../frontend
npm run typecheck
npm run lint
npm run build
```

## Performance notes

On a 2-core CPU the pipeline runs roughly 3–4 sampled frames/second with all
detectors plus OCR enabled. To speed up demos raise `BSS_FRAME_STRIDE`, disable
`BSS_ENABLE_PLATE_OCR`, or disable `BSS_WRITE_ANNOTATED_VIDEO`. A CUDA GPU is used
automatically when available (`torch.cuda`), which is 10–30× faster.

## Production notes

- Set a strong `BSS_SECRET_KEY`, change the bootstrap admin password, restrict
  `BSS_CORS_ORIGINS`.
- Serve `frontend/dist` from a reverse proxy that also fronts the API over TLS.
- SQLite (WAL) suits a single node; point `BSS_DATABASE_URL` at PostgreSQL for
  multi-node deployments.
- The processing worker is in-process and single-threaded by design (CPU-bound
  inference); scale it out to a task queue (Celery/RQ) before running many
  concurrent officers.
- Persist `BSS_DATA_DIR` and `BSS_MODELS_DIR` on durable volumes.
