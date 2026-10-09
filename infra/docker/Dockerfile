# SOVEREIGN API — Python 3.12 slim image
# Multi-stage build: install deps, copy app, run as non-root user.

FROM python:3.12-slim AS base

# Install system deps required by PyMuPDF, tesseract, qpdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    qpdf \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 sovereign
WORKDIR /app

# Install Python deps
COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache .

# Copy application code
COPY --chown=sovereign:sovereign sovereign/ ./sovereign/
COPY --chown=sovereign:sovereign alembic/ ./alembic/
COPY --chown=sovereign:sovereign alembic.ini ./
COPY --chown=sovereign:sovereign configs/ ./configs/
COPY --chown=sovereign:sovereign scripts/ ./scripts/
COPY --chown=sovereign:sovereign Makefile ./

# Create data directories
RUN mkdir -p /var/lib/sovereign/objects /var/lib/sovereign/data && \
    chown -sovereign:sovereign /var/lib/sovereign

USER sovereign

EXPOSE 8000

ENV SOVEREIGN_ENV=prod
ENV DATABASE_URL=mongodb://sovereign:sovereign@mongo:27017/sovereign?authSource=admin
ENV QDRANT_URL=http://qdrant:6333
ENV OBJECT_STORE_FS_ROOT=/var/lib/sovereign/objects

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://127.0.0.1:8000/healthz').raise_for_status()"

CMD ["python", "-m", "uvicorn", "sovereign.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
