"""
run_sql.py — Execute schema.sql and seed.sql against Cloud SQL
Uses psycopg2 directly to handle multi-statement DDL without splitting.
Run from the command_center/ directory: python run_sql.py
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DB_HOST     = os.getenv("DB_HOST",     "35.234.215.116")
DB_PORT     = int(os.getenv("DB_PORT", "5432"))
DB_USER     = os.getenv("DB_USER",     "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME     = os.getenv("DB_NAME",     "talos_app")

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "sql", "schema.sql")
SEED_PATH   = os.path.join(os.path.dirname(__file__), "..", "sql", "seed.sql")


def get_raw_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=DB_PASSWORD, dbname=DB_NAME,
        sslmode="require", connect_timeout=10,
    )


def run_file(path: str, label: str):
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    print(f"\n> Running {label}...")
    conn = get_raw_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print(f"[OK] {label} completed successfully.")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


if __name__ == "__main__":
    print("[TALOS] Cloud SQL Schema + Seed Runner")
    print("=" * 50)
    run_file(SCHEMA_PATH, "schema.sql")
    run_file(SEED_PATH,   "seed.sql")
    print("\n[DONE] All done. Run test_db.py to verify.")
