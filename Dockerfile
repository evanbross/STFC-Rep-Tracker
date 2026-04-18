# ── Stage 1: build the React frontend ────────────────────────────────────────
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ── Stage 2: Python API ───────────────────────────────────────────────────────
FROM python:3.12-slim AS api
WORKDIR /app

# libffi is needed by the cryptography package (cert generation).
# No other native deps — psycopg2-binary ships its own libpq.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-docker.txt ./
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copy application source
COPY . .

# Replace source tree's frontend/dist with the built output from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create directories that are expected at runtime
RUN mkdir -p Screenshots app/screen_snippets certs

ENV FLASK_ENV=production
ENV DISABLE_CAPTURE=true
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 7300

# 2 workers is enough for a single-user local deployment.
# The PostgreSQL advisory lock in Database.init_database() serialises
# startup across workers so there's no DDL race condition.
CMD ["gunicorn", \
     "--workers", "2", \
     "--bind", "0.0.0.0:7300", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "main:app"]
