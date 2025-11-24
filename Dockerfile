FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build tools only if your deps need them (psycopg2 does)
RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service
COPY service.py .

# Non-root user
RUN useradd -r -u 1000 appuser && chown -R appuser /app
USER appuser

# Default export directory inside container
ENV EXPORT_DIR=/app/exports

# Start the scheduler service
CMD ["python", "service.py"]
