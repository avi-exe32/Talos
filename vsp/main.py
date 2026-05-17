"""
main.py — Vendor Stream Portal (VSP)
======================================
Phase 2: FastAPI app that simulates a live B2B component shipment stream.

Endpoints:
  GET  /              — API info panel
  GET  /health        — Liveness check
  GET  /stream_primary   — Live shipment stream (corruptible via toggle)
  GET  /stream_backup    — Backup vendor stream (ALWAYS clean, ignores toggle)
  POST /toggle_corruption — Flips IS_CORRUPTED boolean, returns new state

Corruption Modes (randomized when IS_CORRUPTED=True):
  MODE_A — HTTP 500 + plaintext garbage body
  MODE_B — HTTP 200 + unparseable string (looks like truncated XML/binary)
  MODE_C — HTTP 200 + structurally valid JSON but quantity=0 and corrupt name
"""

import random
import string
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse

# ─── Global Corruption State ──────────────────────────────────────────────────
# Simple module-level boolean. FastAPI runs in a single process on Cloud Run
# (one replica), so this is safe for our demo purposes.
IS_CORRUPTED: bool = False

# ─── App Initialization ───────────────────────────────────────────────────────
app = FastAPI(
    title="Talos Vendor Stream Portal",
    description=(
        "Simulates a live B2B component shipment stream. "
        "Use /toggle_corruption to simulate a vendor data failure."
    ),
    version="1.0.0",
)

# ─── Constants ────────────────────────────────────────────────────────────────
PRIMARY_VENDOR_ID   = "VSP-PRIMARY-001"
PRIMARY_VENDOR_NAME = "PrimaryStream Logistics"
BACKUP_VENDOR_ID    = "VSP-BACKUP-002"
BACKUP_VENDOR_NAME  = "NexusLogistics Ltd."
COMPONENT_NAME      = "LiDAR Sensor Array"

# Realistic quantity jitter — simulates live production variance
BASE_QUANTITY    = 847
QUANTITY_JITTER  = 40   # ± 40 units per poll cycle

# ─── Helper: Clean Payload Generators ─────────────────────────────────────────

def _now_iso() -> str:
    """Returns current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _primary_payload() -> dict[str, Any]:
    """Generates a realistic, healthy primary vendor shipment payload."""
    qty = BASE_QUANTITY + random.randint(-QUANTITY_JITTER, QUANTITY_JITTER)
    return {
        "vendor_id":      PRIMARY_VENDOR_ID,
        "vendor_name":    PRIMARY_VENDOR_NAME,
        "component":      COMPONENT_NAME,
        "quantity":       qty,
        "unit":           "units",
        "unit_cost_usd":  142.50,
        "shipment_id":    f"SHP-{int(time.time())}-{random.randint(1000, 9999)}",
        "origin_port":    "Shanghai, CN",
        "destination":    "Chennai, IN",
        "eta_days":       3,
        "stream_health":  "nominal",
        "timestamp":      _now_iso(),
    }


def _backup_payload() -> dict[str, Any]:
    """Generates a realistic, healthy backup vendor shipment payload."""
    qty = BASE_QUANTITY + random.randint(-QUANTITY_JITTER, QUANTITY_JITTER)
    return {
        "vendor_id":      BACKUP_VENDOR_ID,
        "vendor_name":    BACKUP_VENDOR_NAME,
        "component":      COMPONENT_NAME,
        "quantity":       qty,
        "unit":           "units",
        "unit_cost_usd":  156.00,
        "shipment_id":    f"NX-{int(time.time())}-{random.randint(1000, 9999)}",
        "origin_port":    "Singapore, SG",
        "destination":    "Chennai, IN",
        "eta_days":       5,
        "stream_health":  "nominal",
        "timestamp":      _now_iso(),
    }


def _garbage_string(length: int = 120) -> str:
    """Generates random printable garbage — simulates a corrupted data stream."""
    pool = string.printable[:75]  # printable ASCII excluding whitespace control chars
    return "".join(random.choices(pool, k=length))


# ─── Corruption Mode Selector ─────────────────────────────────────────────────

def _corrupt_response() -> Any:
    """
    Randomly selects one of three failure modes and returns the appropriate
    FastAPI response object. Called only when IS_CORRUPTED is True.
    """
    mode = random.choice(["MODE_A", "MODE_B", "MODE_C"])

    if mode == "MODE_A":
        # HTTP 500 — server-side crash simulation
        return PlainTextResponse(
            content=f"FATAL_STREAM_ERROR::{_garbage_string(80)}::upstream_pipe_broken",
            status_code=500,
        )

    elif mode == "MODE_B":
        # HTTP 200 — but body is unparseable garbage (truncated binary/XML mix)
        garbage = f"<?xml \x00\x01 CORRUPT>>{_garbage_string(60)}<<<EOF{_garbage_string(20)}"
        return PlainTextResponse(
            content=garbage,
            status_code=200,
            media_type="text/plain",
        )

    else:  # MODE_C
        # HTTP 200 — looks like JSON but quantity is 0 and component is mangled
        corrupt_payload = {
            "vendor_id":     PRIMARY_VENDOR_ID,
            "vendor_name":   PRIMARY_VENDOR_NAME,
            "component":     f"CORRUPT__{_garbage_string(12)}",
            "quantity":      0,          # ← triggers Scout Agent boundary check
            "unit":          "units",
            "unit_cost_usd": 0.00,
            "shipment_id":   "NULL",
            "stream_health": "DEGRADED",
            "error_flag":    True,
            "timestamp":     _now_iso(),
        }
        return JSONResponse(content=corrupt_payload, status_code=200)


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    """API discovery panel — useful when opening the URL in a browser."""
    return {
        "service":     "Talos Vendor Stream Portal",
        "version":     "1.0.0",
        "status":      "online",
        "is_corrupted": IS_CORRUPTED,
        "endpoints": {
            "GET  /health":             "Liveness check",
            "GET  /stream_primary":     "Primary vendor stream (corruptible)",
            "GET  /stream_backup":      "Backup vendor stream (always clean)",
            "POST /toggle_corruption":  "Flip corruption state",
            "GET  /docs":               "Swagger UI",
        },
    }


@app.get("/health")
def health():
    """Standard liveness probe — Cloud Run and load balancers call this."""
    return {
        "status":       "ok",
        "is_corrupted": IS_CORRUPTED,
        "timestamp":    _now_iso(),
    }


@app.get("/stream_primary")
def stream_primary():
    """
    Primary vendor shipment stream.
    Returns clean JSON when IS_CORRUPTED=False.
    Returns one of three failure modes when IS_CORRUPTED=True.
    The Scout Agent polls this endpoint every 3 seconds.
    """
    global IS_CORRUPTED
    if IS_CORRUPTED:
        return _corrupt_response()
    return JSONResponse(content=_primary_payload(), status_code=200)


@app.get("/stream_backup")
def stream_backup():
    """
    Backup vendor shipment stream.
    ALWAYS returns a clean, healthy payload — the IS_CORRUPTED flag
    has zero effect on this endpoint. This is the Forge Agent's target URL.
    """
    return JSONResponse(content=_backup_payload(), status_code=200)


@app.post("/toggle_corruption")
def toggle_corruption():
    """
    Flips the IS_CORRUPTED boolean.
    Call once to break the primary stream. Call again to restore it.
    Returns the new state so the caller can confirm the flip.
    """
    global IS_CORRUPTED
    IS_CORRUPTED = not IS_CORRUPTED
    action = "CORRUPTION ENABLED  -- /stream_primary will now return failures" \
             if IS_CORRUPTED else \
             "CORRUPTION DISABLED -- /stream_primary is now healthy"
    return {
        "is_corrupted": IS_CORRUPTED,
        "action":       action,
        "timestamp":    _now_iso(),
    }
