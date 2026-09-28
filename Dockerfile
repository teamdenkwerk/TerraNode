# Backend Dockerfile for TERRANODE
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for GDAL/GEOS/PROJ
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libgeos-dev \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
