FROM python:3.11-slim

WORKDIR /app

# System deps for pdfplumber (uses pdfminer which needs no extra C libs on slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data directory — will be mounted as a volume
RUN mkdir -p /data/uploads /data/exports

ENV DATABASE_PATH=/data/naughtrfp.db
ENV UPLOAD_FOLDER=/data/uploads
ENV EXPORTS_DIR=/data/exports
ENV FLASK_DEBUG=false
ENV FLASK_HOST=0.0.0.0
ENV PORT=5000

EXPOSE 5000

# gthread worker class: handles concurrent SSE streams without blocking other requests.
# Each worker has 8 threads -> 16 concurrent connections total with 2 workers.
# --timeout 300: SSE streams can run 60-90s during RFP processing; default 30s would kill them.
# --keep-alive 65: slightly longer than Nginx's 60s keepalive to avoid race conditions.
CMD ["gunicorn", \
     "--worker-class", "gthread", \
     "--workers", "2", \
     "--threads", "8", \
     "--timeout", "300", \
     "--keep-alive", "65", \
     "--bind", "0.0.0.0:5000", \
     "--log-level", "info", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
