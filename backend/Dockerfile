FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEVPILOT_DATA_DIR=/data
WORKDIR /app
COPY backend/pyproject.toml backend/requirements.lock ./
COPY backend/app ./app
RUN pip install --no-cache-dir -c requirements.lock . \
    && useradd --create-home --uid 10001 appuser \
    && mkdir /data && chown appuser:appuser /data
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Opt-in trusted worker image; API service never receives the Docker socket.
FROM runtime AS sandbox-worker
USER root
RUN apt-get update && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*
CMD ["python", "-m", "app.worker"]
