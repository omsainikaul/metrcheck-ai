# ============================================================
# Stage 1 — Build React/Vite frontend
# ============================================================
FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json ./
COPY frontend/package-lock.json ./

RUN npm ci

COPY frontend/ ./

RUN npm run build


# ============================================================
# Stage 2 — Production application
# ============================================================
FROM python:3.11-slim

# System dependencies for:
# - PaddleOCR
# - OpenCV
# - Nginx
# - healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    libgl1 \
    libstdc++6 \
    fonts-dejavu \
    curl \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Backend
# ------------------------------------------------------------
WORKDIR /backend

COPY backend/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# ------------------------------------------------------------
# Frontend
# ------------------------------------------------------------
COPY --from=frontend-builder /frontend/dist /usr/share/nginx/html

# ------------------------------------------------------------
# Nginx configuration
# ------------------------------------------------------------
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Remove the default nginx configuration if present
RUN rm -f /etc/nginx/sites-enabled/default

# ------------------------------------------------------------
# Runtime configuration
# ------------------------------------------------------------
ENV PYTHONUNBUFFERED=1 \
    OCR_ENGINE=paddleocr \
    UPLOAD_DIR=/data/uploads \
    DATABASE_PATH=/data/metrc_check.db

EXPOSE 80

# Start FastAPI and Nginx in the same container
CMD ["bash", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000 & backend_pid=$!; nginx -g 'daemon off;' & nginx_pid=$!; trap 'kill $backend_pid $nginx_pid 2>/dev/null || true' SIGTERM SIGINT; wait -n $backend_pid $nginx_pid; status=$?; kill $backend_pid $nginx_pid 2>/dev/null || true; exit $status"]