# MemAgent Backend - deploy separately (Cloud Run, Railway, Render, etc.)
# Build from repo root: docker build -f backend/Dockerfile .
FROM python:3.11-slim

WORKDIR /app

# Install uv for fast, reproducible installs
RUN pip install --no-cache-dir uv

# Copy backend and install dependencies + app (no dev)
COPY backend/ .
RUN uv sync --no-dev

# Temp dir for generated images
RUN mkdir -p /app/tmp/images

# Non-root user (optional, uncomment for stricter security)
# RUN useradd -m appuser && chown -R appuser /app
# USER appuser

EXPOSE 8000

# Production: set env vars (BACKEND_URL, DATABASE_URL, CORS_ORIGINS, etc.)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
