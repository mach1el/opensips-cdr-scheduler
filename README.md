# Data Export & Retention Service

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.12+-brightgreen)](#)

A small Python daemon that **runs every day** to:

- Export data from a database table to **CSV files**
- Keep only the **last N days** of data (default **7 days**) both in:
  - The **database** (by deleting older rows)
  - The **CSV exports** (by removing older files)

Packaged as a **Docker container** so you can drop it into any environment as a housekeeping service.

---

## Features

- ✅ Daily scheduled export job (e.g. export **yesterday’s** data)
- ✅ Daily cleanup job to keep only the **last 7 days** of data
- ✅ CSV exports with automatic filename pattern:  
  `TABLE_NAME_YYYY-MM-DD.csv`
- ✅ Configurable via environment variables (table name, timestamp column, retention days, run hours, export directory)
- ✅ Works nicely with Docker / Podman
- ✅ Database-agnostic in design (example uses PostgreSQL via `psycopg2`)

---

## Architecture

The service is a simple Python script using:

- `APScheduler` – to schedule **cron-style** daily jobs
- `psycopg2` – PostgreSQL client (can be swapped with another DB driver)
- `csv` – built-in CSV writer

Two jobs are registered:

1. **Export job** (`export_daily_data`)
   - Runs every day at `EXPORT_HOUR` (default: `01:00`)
   - Exports rows where `TIMESTAMP_COLUMN` is in **yesterday’s** range
   - Writes them to a CSV in `EXPORT_DIR`

2. **Cleanup job** (`cleanup_old_data`)
   - Runs every day at `CLEANUP_HOUR` (default: `02:00`)
   - Deletes rows older than `RETENTION_DAYS`
   - Deletes CSV files older than `RETENTION_DAYS`

---

## Directory Structure

Example layout:

```text
data-export-service/
  service.py          # main scheduler & job logic
  requirements.txt    # dependencies
  Dockerfile          # container image definition
  exports/            # CSV output directory (local, mounted into container)
  README.md
```

The `exports/` directory will be created automatically if it doesn’t exist.

---

## Requirements

If you want to run it **without Docker**, you need:

- Python 3.10+ (example uses 3.12)
- PostgreSQL client libraries (if using psycopg2)
- Python packages from `requirements.txt`, e.g.:

```txt
APScheduler
psycopg2-binary
python-dateutil
```

---

## Configuration

All configuration is done via **environment variables**.

| Variable           | Required | Default                                      | Description                                                                 |
|--------------------|----------|----------------------------------------------|-----------------------------------------------------------------------------|
| `DATABASE_URL`     | ✅        | _none_                                      | DB connection string, e.g. `postgresql://user:pass@host:5432/dbname`       |
| `TABLE_NAME`       | ✅        | `events`                                    | Table to export and clean up                                                |
| `TIMESTAMP_COLUMN` | ✅        | `created_at`                                | Timestamp column used for date filtering                                    |
| `EXPORT_DIR`       | ❌        | `./exports` (or `/app/exports` in container) | Directory where CSV files are stored                                       |
| `RETENTION_DAYS`   | ❌        | `7`                                         | Number of days to keep in DB and CSV exports                               |
| `EXPORT_HOUR`      | ❌        | `1`                                         | Hour (0–23) when daily export job runs                                     |
| `CLEANUP_HOUR`     | ❌        | `2`                                         | Hour (0–23) when cleanup job runs                                          |

> 💡 Time zone: the scheduler uses the container’s local time. When running in Docker, set the container’s time zone if you need to align with a specific region.

---

## Running Locally (without Docker)

From the project directory:

```bash
pip install -r requirements.txt

export DATABASE_URL="postgresql://user:pass@localhost:5432/mydb"
export TABLE_NAME="events"
export TIMESTAMP_COLUMN="created_at"
export EXPORT_DIR="./exports"
export RETENTION_DAYS=7
export EXPORT_HOUR=1
export CLEANUP_HOUR=2

python service.py
```

You’ll see logs like:

```text
[SERVICE] Scheduler started
[SERVICE] Daily export at 01:00
[SERVICE] Daily cleanup at 02:00
[SERVICE] Keeping last 7 days of data
```

---

## Docker Image

### Dockerfile

The included `Dockerfile`:

- Uses `python:3.12-slim`
- Installs build tools & `libpq-dev` for `psycopg2`
- Copies `service.py` and `requirements.txt`
- Sets `EXPORT_DIR=/app/exports`
- Runs `python service.py`

Example:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends   build-essential   libpq-dev   && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY service.py .

RUN useradd -r -u 1000 appuser && chown -R appuser /app
USER appuser

ENV EXPORT_DIR=/app/exports

CMD ["python", "service.py"]
```

---

### Build the Image

```bash
docker build -t data-export-service .
# or
podman build -t data-export-service .
```

---

### Run Container (simple example)

```bash
docker run -d   --name data-export-service   -e DATABASE_URL="postgresql://user:pass@dbhost:5432/mydb"   -e TABLE_NAME="events"   -e TIMESTAMP_COLUMN="created_at"   -e RETENTION_DAYS=7   -e EXPORT_HOUR=1   -e CLEANUP_HOUR=2   -v "$(pwd)/exports:/app/exports"   --restart unless-stopped   data-export-service
```

What this does:

- Connects to your database using `DATABASE_URL`
- Runs export at **01:00** and cleanup at **02:00**
- Persists CSV files to the host’s `./exports` directory
- Automatically restarts unless you stop it

---

## Docker Compose

Example `docker-compose.yml`:

```yaml
version: "3.9"

services:
  data-export-service:
    build: .
    container_name: data-export-service
    environment:
      DATABASE_URL: "postgresql://user:pass@dbhost:5432/mydb"
      TABLE_NAME: "events"
      TIMESTAMP_COLUMN: "created_at"
      RETENTION_DAYS: "7"
      EXPORT_HOUR: "1"
      CLEANUP_HOUR: "2"
      EXPORT_DIR: "/app/exports"
    volumes:
      - ./exports:/app/exports
    restart: unless-stopped
```

Run:

```bash
docker compose up -d
# or: podman compose up -d
```

---

## Data Retention Logic

- **Database**
  - Each day, `cleanup_old_data` deletes rows where `TIMESTAMP_COLUMN` is older than `RETENTION_DAYS` days.
  - This ensures you always keep a **rolling window** of recent data (e.g. last 7 days).

- **CSV files**
  - CSV files follow the pattern:  
    `TABLE_NAME_YYYY-MM-DD.csv`
  - The cleanup job parses the date from the filename and deletes any CSV older than `RETENTION_DAYS` days.

You can change `RETENTION_DAYS` at any time; the next cleanup run will adjust accordingly.

---

## Customization

You can easily adapt this service by modifying `service.py`:

- Change the **SELECT query** to filter by additional columns
- Export a subset of columns instead of `SELECT *`
- Use another DB backend:
  - Replace `psycopg2` and `DATABASE_URL` format
  - Swap `get_connection()` implementation
- Add more scheduled jobs (e.g. weekly summary export)

---

## Troubleshooting

- **No CSV files generated**
  - Check that:
    - `DATABASE_URL` is correct
    - `TABLE_NAME` and `TIMESTAMP_COLUMN` exist
    - There was actually data for **yesterday** in the table

- **Permission errors on exports**
  - Ensure the host directory mounted to `/app/exports` is writeable by the container user (UID 1000 in this Dockerfile).

- **Time zone mismatch**
  - By default, container time is usually UTC.
  - If you want local time (e.g. Asia/Ho_Chi_Minh), set TZ in the container and ensure `tzdata` is installed, or manage offset at the database/query level.

---

## License

Add your preferred license information here (MIT, Apache-2.0, proprietary, etc.).
