# RapidGo — Edmonton ETS Analytics

Web dashboard for **Edmonton Transit System (ETS)** using open city data: live GTFS-Realtime vehicle positions and delays, static schedules, and collision hotspots from [Edmonton Open Data](https://data.edmonton.ca).

## Features

- Live bus map (GTFS-RT vehicle positions)
- Route shapes and stops (static GTFS)
- Delay analytics by hour, route ranking, 7×24 heatmap (from locally collected RT data)
- Collision heatmap (annual open data — safety context, not live traffic)
- Delay prediction per route/hour (historical median → optional sklearn model)

## Data sources

| Data | URL |
|------|-----|
| Static GTFS | https://gtfs.edmonton.ca/TMGTFSRealTimeWebService/GTFS/gtfs.zip |
| Vehicle positions | http://gtfs.edmonton.ca/TMGTFSRealTimeWebService/Vehicle/VehiclePositions.pb |
| Trip updates (delays) | http://gtfs.edmonton.ca/TMGTFSRealTimeWebService/TripUpdate/TripUpdates.pb |
| Service alerts | http://gtfs.edmonton.ca/TMGTFSRealTimeWebService/Alert/Alerts.pb |
| Collisions (location names, geocoded) | https://data.edmonton.ca (dataset `mf6n-s5ts`) |

Use under the [City of Edmonton Open Data Agreement](https://www.edmonton.ca/transportation/Web-version2.1-OpenDataAgreement.pdf). Poll GTFS-RT every **30–60 seconds** only.

**Note:** The city does not publish historical on-time performance. RapidGo builds delay history by polling GTFS-RT continuously. Charts and predictions improve after several days of uptime.

## Prerequisites

- Docker Desktop (for PostgreSQL)
- Python 3.11+
- Node.js 20+

## Quick start

### 1. Database

```bash
docker compose up -d
```

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
copy .env.example .env          # or use provided .env

alembic upgrade head
python -m app.ingest.gtfs_static
python -m app.ingest.socrata_collisions   # geocodes top sites via Nominatim (~1/sec); re-run to cache more

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API starts a background job that polls GTFS-RT every 45 seconds.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### One-time admin (optional)

```bash
curl -X POST http://localhost:8000/api/admin/refresh-gtfs
curl -X POST http://localhost:8000/api/admin/refresh-collisions
curl -X POST http://localhost:8000/api/analytics/recompute-aggregates
curl -X POST http://localhost:8000/api/predict/train
```

## Run poller 24/7

For production delay history, keep the API running (or run the standalone poller):

```bash
cd backend
python -m app.ingest.gtfs_rt_poller
```

Recompute prediction aggregates nightly (also scheduled at 3:00 AM when using `uvicorn`):

```bash
python -m app.analytics.train
```

## Project layout

```
RapidGo/
  backend/          FastAPI + SQLAlchemy + GTFS ingest
  frontend/         React + Vite + Leaflet + Recharts
  docker-compose.yml
```

## API highlights

- `GET /api/routes` — all routes
- `GET /api/vehicles` — live bus positions
- `GET /api/analytics/route/{id}/delays-by-hour`
- `GET /api/analytics/route/{id}/heatmap`
- `GET /api/predict?route_id=...&hour=17`
- `GET /health`

## Deploy notes

- **Backend + DB:** Railway, Render, or Fly.io with managed Postgres; set `DATABASE_URL`.
- **Frontend:** Build with `npm run build`, host on Vercel/Netlify; set API proxy or `VITE_API_URL`.
- Run RT poller continuously; without it, maps work only while the feed is polled and analytics stay empty.

## License

Application code: your choice. Transit and city data: Edmonton open data terms.
