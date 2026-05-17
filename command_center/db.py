"""
db.py — Cloud SQL Connection Engine & All Parameterized Database Helpers
=========================================================================
Supports two connection paths controlled by the USE_CONNECTOR env var:

  USE_CONNECTOR=true  (Cloud Run)
      Uses the Cloud SQL Python Connector (pg8000 driver) to open an
      authenticated TLS tunnel to the instance — no Public IP exposure,
      no VPC peering required.

  USE_CONNECTOR=false  (Local Development)
      Direct TCP connection to the Cloud SQL Public IP via psycopg2.
      Requires the instance's Public IP to allow your local IP in the
      Cloud SQL Authorized Networks list.

All queries use SQLAlchemy Core with named bind parameters (:param)
— zero raw string interpolation, zero SQL injection surface.
"""

import json
import logging
import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Configuration (from environment / .env) ──────────────────────────────────
INSTANCE_CONNECTION_NAME = os.getenv(
    "INSTANCE_CONNECTION_NAME", "talos-496511:asia-south1:talos-base"
)
DB_NAME     = os.getenv("DB_NAME",     "talos_app")
DB_USER     = os.getenv("DB_USER",     "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST     = os.getenv("DB_HOST",     "35.234.215.116")   # Cloud SQL Public IP
DB_PORT     = int(os.getenv("DB_PORT", "5432"))

# Set USE_CONNECTOR=true when running on Cloud Run.
# Set USE_CONNECTOR=false for local dev (direct TCP to Public IP).
USE_CONNECTOR = os.getenv("USE_CONNECTOR", "false").lower() == "true"

# ─── Singleton Engine ─────────────────────────────────────────────────────────
_engine = None


def get_engine():
    """
    Returns a singleton SQLAlchemy engine.
    Thread-safe: module-level singleton is safe for multi-threaded Streamlit.
    """
    global _engine
    if _engine is not None:
        return _engine

    pool_kwargs = dict(
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=2,
        pool_timeout=30,
        pool_recycle=1800,  # Refresh connections every 30 min
        pool_pre_ping=True, # Detect stale connections before handing them out
    )

    if USE_CONNECTOR:
        # ── Cloud Run Path ────────────────────────────────────────────────────
        # Cloud SQL Python Connector handles IAM-auth TLS tunneling to the
        # instance. No public IP in the connection string.
        from google.cloud.sql.connector import Connector

        _connector = Connector()

        def _cloud_getconn():
            return _connector.connect(
                INSTANCE_CONNECTION_NAME,
                "pg8000",
                user=DB_USER,
                password=DB_PASSWORD,
                db=DB_NAME,
            )

        _engine = create_engine(
            "postgresql+pg8000://",
            creator=_cloud_getconn,
            **pool_kwargs,
        )
        logger.info(
            f"[DB] Engine initialized via Cloud SQL Connector → {INSTANCE_CONNECTION_NAME}"
        )

    else:
        # ── Local Development Path ────────────────────────────────────────────
        # Direct TCP to Cloud SQL Public IP. Requires your IP to be in the
        # Cloud SQL Authorized Networks list in GCP Console.
        import psycopg2

        def _local_getconn():
            return psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                dbname=DB_NAME,
                connect_timeout=10,
                sslmode="require",  # Cloud SQL requires SSL even on Public IP
            )

        _engine = create_engine(
            "postgresql+psycopg2://",
            creator=_local_getconn,
            **pool_kwargs,
        )
        logger.info(
            f"[DB] Engine initialized via direct TCP → {DB_HOST}:{DB_PORT}/{DB_NAME}"
        )

    return _engine


# ─── Connection Context Manager ───────────────────────────────────────────────
@contextmanager
def get_conn():
    """
    Yields a SQLAlchemy connection from the pool.
    Auto-commits on success, auto-rolls back on exception.
    Always closes the connection back to the pool.
    """
    engine = get_engine()
    conn = engine.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── Read Helpers ─────────────────────────────────────────────────────────────

def get_active_vendor_url() -> str:
    """
    Read the live circuit-breaker URL from system_config.
    Called by the daemon thread on every 3-second poll cycle.
    """
    with get_conn() as conn:
        result = conn.execute(
            text("SELECT current_active_vendor_url FROM system_config WHERE id = 1")
        )
        row = result.fetchone()
        if row is None:
            raise RuntimeError(
                "[DB] system_config table is empty. Run sql/seed.sql first."
            )
        return row[0]


def get_inventory() -> dict:
    """
    Return the primary inventory row as a plain dict.
    Used by the Analyst Agent for financial exposure calculations.
    """
    with get_conn() as conn:
        result = conn.execute(
            text("SELECT * FROM inventory ORDER BY id LIMIT 1")
        )
        row = result.mappings().fetchone()
        return dict(row) if row else {}


def get_vendors(vendor_type: str = None) -> list[dict]:
    """
    Return active vendor profiles, optionally filtered by type.
    Used by the Broker Agent for ranking and selection.

    Args:
        vendor_type: 'primary' | 'backup' | None (returns all)
    """
    with get_conn() as conn:
        if vendor_type:
            result = conn.execute(
                text(
                    """
                    SELECT * FROM vendors
                    WHERE vendor_type = :vtype
                      AND is_active = TRUE
                    ORDER BY reliability_score DESC
                    """
                ),
                {"vtype": vendor_type},
            )
        else:
            result = conn.execute(
                text(
                    """
                    SELECT * FROM vendors
                    WHERE is_active = TRUE
                    ORDER BY reliability_score DESC
                    """
                )
            )
        return [dict(row) for row in result.mappings().fetchall()]


def get_recent_agent_logs(limit: int = 50) -> list[dict]:
    """
    Return the most recent agent log entries for the UI audit panel.
    Ordered most-recent-first.
    """
    with get_conn() as conn:
        result = conn.execute(
            text(
                """
                SELECT id, agent_name, lifecycle_state, payload, created_at
                FROM agent_log
                ORDER BY created_at DESC
                LIMIT :lim
                """
            ),
            {"lim": limit},
        )
        return [dict(row) for row in result.mappings().fetchall()]


def get_pending_logs() -> list[dict]:
    """
    Return all Pending agent log entries.
    Used by the Approval Gate modal to display agent outputs.
    """
    with get_conn() as conn:
        result = conn.execute(
            text(
                """
                SELECT id, agent_name, lifecycle_state, payload, created_at
                FROM agent_log
                WHERE lifecycle_state = 'Pending'
                ORDER BY created_at ASC
                """
            )
        )
        return [dict(row) for row in result.mappings().fetchall()]


# ─── Write Helpers ────────────────────────────────────────────────────────────

def log_agent_event(agent_name: str, lifecycle_state: str, payload: dict) -> int:
    """
    Insert a new agent audit log entry.
    All agent pipeline functions call this before returning.

    Args:
        agent_name:      'Scout' | 'Analyst' | 'Broker' | 'Forge'
        lifecycle_state: 'Pending' | 'Executed' | 'Rejected'
        payload:         dict — structured agent output

    Returns:
        The new row's id (int)
    """
    with get_conn() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO agent_log (agent_name, lifecycle_state, payload, created_at)
                VALUES (:agent, :state, CAST(:payload AS JSONB), NOW())
                RETURNING id
                """
            ),
            {
                "agent":   agent_name,
                "state":   lifecycle_state,
                "payload": json.dumps(payload),
            },
        )
        new_id = result.fetchone()[0]
        logger.info(f"[DB] Logged {agent_name} event (id={new_id}, state={lifecycle_state})")
        return new_id


def update_active_vendor_url(new_url: str) -> None:
    """
    Approval Gate write: atomically update system_config with the backup URL.
    The daemon thread reads this on its next 3-second cycle.
    """
    with get_conn() as conn:
        conn.execute(
            text(
                """
                UPDATE system_config
                SET current_active_vendor_url = :url,
                    last_updated_by           = 'ApprovalGate',
                    updated_at                = NOW()
                WHERE id = 1
                """
            ),
            {"url": new_url},
        )
    logger.info(f"[DB] system_config circuit-breaker updated → {new_url}")


def mark_logs_executed() -> int:
    """
    Mark all Pending agent logs as Executed after user approval.
    Returns the count of rows updated.
    """
    with get_conn() as conn:
        result = conn.execute(
            text(
                """
                UPDATE agent_log
                SET lifecycle_state = 'Executed'
                WHERE lifecycle_state = 'Pending'
                RETURNING id
                """
            )
        )
        count = len(result.fetchall())
    logger.info(f"[DB] Marked {count} log(s) as Executed.")
    return count


def mark_logs_rejected() -> int:
    """
    Mark all Pending agent logs as Rejected after gate rejection.
    Returns the count of rows updated.
    """
    with get_conn() as conn:
        result = conn.execute(
            text(
                """
                UPDATE agent_log
                SET lifecycle_state = 'Rejected'
                WHERE lifecycle_state = 'Pending'
                RETURNING id
                """
            )
        )
        count = len(result.fetchall())
    logger.info(f"[DB] Marked {count} log(s) as Rejected.")
    return count


# ─── Health Check ─────────────────────────────────────────────────────────────

def ping_db() -> bool:
    """
    Quick connectivity check. Returns True if the DB is reachable.
    Called on startup by the Streamlit app to confirm DB health.
    """
    try:
        with get_conn() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("[DB] Ping successful.")
        return True
    except Exception as exc:
        logger.error(f"[DB] Ping failed: {exc}")
        return False
