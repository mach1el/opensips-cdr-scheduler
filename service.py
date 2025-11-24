import os
import csv
from datetime import datetime, date, time, timedelta

import psycopg2
from apscheduler.schedulers.blocking import BlockingScheduler


# =========================
# Configuration
# =========================

DATABASE_URL = os.getenv(
  "DATABASE_URL",
  "postgresql://user:password@localhost:5432/mydb"
)

EXPORT_DIR = os.getenv("EXPORT_DIR", "./exports")
TABLE_NAME = os.getenv("TABLE_NAME", "events")
TIMESTAMP_COLUMN = os.getenv("TIMESTAMP_COLUMN", "created_at")

# How many days of data to keep (DB + CSV)
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))

# At what time of day to run jobs (24h format)
EXPORT_HOUR = int(os.getenv("EXPORT_HOUR", "1"))    # 01:00
CLEANUP_HOUR = int(os.getenv("CLEANUP_HOUR", "2"))  # 02:00


# =========================
# DB helpers
# =========================

def get_connection():
  """
  Open a new DB connection.
  """
  return psycopg2.connect(DATABASE_URL)


# =========================
# Job: Export data to CSV
# =========================

def export_daily_data():
  """
  Export yesterday's data into a CSV file.
  Example filename: events_2025-11-23.csv
  """
  os.makedirs(EXPORT_DIR, exist_ok=True)

  today = date.today()
  export_date = today - timedelta(days=1)

  start_dt = datetime.combine(export_date, time.min)
  end_dt = datetime.combine(export_date + timedelta(days=1), time.min)

  file_name = f"{TABLE_NAME}_{export_date.isoformat()}.csv"
  file_path = os.path.join(EXPORT_DIR, file_name)

  print(f"[EXPORT] Exporting data for {export_date} to {file_path}")

  query = f"""
    SELECT *
    FROM {TABLE_NAME}
    WHERE {TIMESTAMP_COLUMN} >= %s
      AND {TIMESTAMP_COLUMN} < %s
  """

  try:
    with get_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(query, (start_dt, end_dt))
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]

    # Write CSV
    with open(file_path, "w", newline="", encoding="utf-8") as f:
      writer = csv.writer(f)
      writer.writerow(cols)
      writer.writerows(rows)

    print(f"[EXPORT] Wrote {len(rows)} rows to {file_path}")
  except Exception as exc:
    print(f"[EXPORT] ERROR: {exc}")


# =========================
# Job: Cleanup old data
# =========================

def cleanup_old_data():
  """
  Delete DB rows older than RETENTION_DAYS
  and remove CSV files older than RETENTION_DAYS.
  """
  # --- DB cleanup ---
  cutoff_dt = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
  print(f"[CLEANUP] Deleting DB rows older than {cutoff_dt}")

  delete_query = f"""
    DELETE FROM {TABLE_NAME}
    WHERE {TIMESTAMP_COLUMN} < %s
  """

  deleted_rows = 0
  try:
    with get_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(delete_query, (cutoff_dt,))
        deleted_rows = cur.rowcount
      conn.commit()
    print(f"[CLEANUP] Deleted {deleted_rows} rows from DB")
  except Exception as exc:
    print(f"[CLEANUP] DB ERROR: {exc}")

  # --- CSV cleanup ---
  # try:
  #   os.makedirs(EXPORT_DIR, exist_ok=True)
  #   cutoff_date = date.today() - timedelta(days=RETENTION_DAYS)

  #   print(f"[CLEANUP] Removing CSV files older than {cutoff_date}")

  #   for fname in os.listdir(EXPORT_DIR):
  #     if not fname.startswith(f"{TABLE_NAME}_") or not fname.endswith(".csv"):
  #       continue

  #     # Expect format: TABLE_NAME_YYYY-MM-DD.csv
  #     date_str = fname[len(TABLE_NAME) + 1:-4]
  #     try:
  #       f_date = date.fromisoformat(date_str)
  #     except ValueError:
  #       # Skip files that don't follow naming convention
  #       continue

  #     if f_date < cutoff_date:
  #       f_path = os.path.join(EXPORT_DIR, fname)
  #       try:
  #         os.remove(f_path)
  #         print(f"[CLEANUP] Removed old file {f_path}")
  #       except Exception as exc:
  #         print(f"[CLEANUP] Failed to remove {f_path}: {exc}")
  # except Exception as exc:
  #   print(f"[CLEANUP] FILE ERROR: {exc}")


# =========================
# Scheduler setup
# =========================

def main():
  scheduler = BlockingScheduler()

  # Run export job every day at EXPORT_HOUR
  scheduler.add_job(
    export_daily_data,
    "cron",
    hour=EXPORT_HOUR,
    minute=0,
    id="daily_export"
  )

  # Run cleanup job every day at CLEANUP_HOUR
  scheduler.add_job(
    cleanup_old_data,
    "cron",
    hour=CLEANUP_HOUR,
    minute=0,
    id="daily_cleanup"
  )

  print("[SERVICE] Scheduler started")
  print(f"[SERVICE] Daily export at {EXPORT_HOUR:02d}:00")
  print(f"[SERVICE] Daily cleanup at {CLEANUP_HOUR:02d}:00")
  print(f"[SERVICE] Keeping last {RETENTION_DAYS} days of data")

  try:
    scheduler.start()
  except (KeyboardInterrupt, SystemExit):
    print("[SERVICE] Scheduler stopped")


if __name__ == "__main__":
  main()
