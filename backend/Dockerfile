# ─── Backend: FastAPI + Socket.IO ─────────────────────────────────────────────
FROM python:3.11-slim AS backend

WORKDIR /app

# System deps for audio processing, PDF, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (from repo root)
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code and legacy static assets
COPY backend/ ./
COPY frontend ./frontend

# Create required directories
RUN mkdir -p logs frontend/assets

EXPOSE 5000

CMD ["python", "-m", "uvicorn", "main:asgi_app", "--host", "0.0.0.0", "--port", "5000"]
