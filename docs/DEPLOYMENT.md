# TERRANODE Production Deployment Guide

**Document Version:** 2026.1  
**Target Systems:** Ubuntu 22.04 LTS / Debian 12 / Docker Enterprise / Windows Server  

---

## 1. Architecture Overview

TERRANODE runs as a containerized micro-service stack composed of:
1. **Frontend**: Vite + React 19 SPA served via high-performance Nginx.
2. **Backend**: FastAPI asynchronous ASGI server running Python 3.11 with GEOS/PROJ/GDAL bindings.
3. **Spatial Persistence**: PostgreSQL 16 + PostGIS 3.4 for spatial indexing, topology, and ACID transaction safety.
4. **Local Datastore**: Deterministic GeoJSON file repository in `data/uploads/` for zero-downtime offline continuity.

---

## 2. Environment Variables

Create a production `.env` file at the root:

```env
# Database Credentials
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=geo_reconciliation
GEO_RECON_DB_DSN=postgresql://postgres:your_secure_password_here@postgis:5432/geo_reconciliation

# Earth Engine / AI Credentials
EE_PROJECT=geo-reconciliation-prod

# Server Settings
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=production
LOG_LEVEL=INFO
```

---

## 3. Local Development Setup

### Backend:
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt

# Run FastAPI with auto-reload
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## 4. Production Container Deployment

### Launching Stack:
```bash
docker compose up -d --build
```

### Applying Schema:
```bash
docker compose exec backend python -m db.apply_schema
```

---

## 5. Health Checks & Telemetry

- **Basic Health:** `GET http://localhost:8000/health`
- **Subsystem Readiness Probe:** `GET http://localhost:8000/health/ready`
- **Production Validation Dashboard:** `GET http://localhost:8000/validation/production`

---

## 6. Backup & Recovery Strategy

### Automated Nightly Database Dump:
```bash
docker exec -t terranode_postgis pg_dump -U postgres -d geo_reconciliation -F c -b -v -f /var/lib/postgresql/data/terranode_backup_$(date +%Y%m%d).dump
```

---

## 7. Troubleshooting & Diagnostics

- **Database unreachable:** The system automatically switches to autonomous local file mode using verified GeoJSON files in `data/uploads/`.
- **CRS Mismatch:** The CRS safety transformer in `backend/crs/transformer.py` auto-detects UTM zone and prevents degree calculations.
