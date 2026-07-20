FROM python:3.12-slim

LABEL org.opencontainers.image.title="VIT Chain Node"
LABEL org.opencontainers.image.description="VIT Network standalone Proof-of-Storage chain node — Chain ID 7764"
LABEL org.opencontainers.image.source="https://github.com/vitnetwork/vit-chain"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . .

ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Shell form so $PORT expands at runtime (Render injects PORT dynamically)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
