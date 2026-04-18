# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Use /app as workdir so .venv paths match the runtime stage
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./

# Install dependencies (CPU-only torch — avoids downloading 2GB of CUDA packages)
RUN uv sync --no-dev --no-install-project \
    --extra-index-url https://download.pytorch.org/whl/cpu

COPY app/ app/

RUN uv sync --no-dev \
    --extra-index-url https://download.pytorch.org/whl/cpu

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy virtual environment and app code from builder (paths stay identical)
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app   /app/app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV HF_HOME=/app/.cache/huggingface

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/live').read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
