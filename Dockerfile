FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2 and other compiled packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use the PORT env var — defaults to 8080 for Cloud Run
ENV PORT=8080

EXPOSE ${PORT}

# Healthcheck built into the container
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

CMD ["sh", "-c", "uvicorn mission_zero:app --host 0.0.0.0 --port ${PORT}"]
