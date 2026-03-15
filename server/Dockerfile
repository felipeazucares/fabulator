# =============================================================================
# Fabulator FastAPI Container
# Base: python:3.12-slim-bookworm — ARM64 native on M5.
#
# Build context is project ROOT (not server/) because requirements.txt
# lives at the root. docker-compose.yml handles this:
#   build:
#     context: .
#     dockerfile: server/Dockerfile
# =============================================================================
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt is at project root
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code (overridden by volume mount in dev — this is for prod)
COPY server/ .

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# watchfiles handles hot-reload under virtiofs without inotify
CMD ["python", "-m", "uvicorn", "app.api:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload", \
     "--reload-dir", "/app"]
