"""
demo_fixtures.py — Static Pre-Canned Agent Responses for DEMO_MODE=true
=========================================================================
When DEMO_MODE=true (env var), every agent call returns one of these dicts
immediately — no Gemini API call, no DB read, no network dependency.

This guarantees a rock-solid demo presentation path regardless of live
network conditions or API quota limits.

Usage (in agents.py):
    if DEMO_MODE:
        return ANALYST_FIXTURE
"""

import os

# ─── Global flag — set DEMO_MODE=true in your .env or Cloud Run env vars ─────
DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"


# ─── Scout Agent Fixture ──────────────────────────────────────────────────────
SCOUT_ERROR_FIXTURE: dict = {
    "agent":                "Scout",
    "failure_count":        3,
    "error_type":           "STREAM_CORRUPTION",
    "last_http_status":     500,
    "last_error":           "JSONDecodeError: Expecting value: line 1 column 1 (char 0)",
    "failed_url":           "https://<VSP_CLOUD_RUN_URL>/stream_primary",
    "consecutive_failures": 3,
    "timestamp":            "2026-05-17T10:42:01Z",
    "escalation_triggered": True,
    "demo_mode":            True,
}


# ─── Analyst Agent Fixture ────────────────────────────────────────────────────
ANALYST_FIXTURE: dict = {
    "agent":                     "Analyst",
    "impact_score":              87,
    "days_to_stockout":          4,
    "days_to_threshold_breach":  4,
    "current_stock":             847,
    "daily_burn_rate":           137,
    "factory_threshold":         200,
    "financial_exposure_usd":    4165000.00,
    "daily_production_loss_usd": 694166.67,
    "executive_summary": (
        "With 847 LiDAR Sensor Array units on hand and a daily burn rate of 137 units, "
        "the factory will breach its critical halt threshold of 200 units in approximately "
        "4.7 days, generating an estimated $4.17M total financial exposure at $694,167 per day "
        "in lost production value. "
        "Immediate procurement of a minimum 1,200-unit emergency order from a pre-qualified "
        "backup supplier is required to prevent an unrecoverable production stoppage."
    ),
    "recommendation":  "Escalate to Broker Agent for immediate vendor re-routing.",
    "confidence":      0.94,
    "demo_mode":       True,
}


# ─── Broker Agent Fixture ─────────────────────────────────────────────────────
BROKER_FIXTURE: dict = {
    "agent":              "Broker",
    "selected_vendor":    "NexusLogistics Ltd.",
    "selected_vendor_id": 2,
    "backup_stream_url":  "https://<VSP_CLOUD_RUN_URL>/stream_backup",
    "unit_cost":          156.00,
    "shipping_lead_days": 5,
    "reliability_score":  0.890,
    "ranking_score":      0.847,
    "ranking_breakdown": {
        "reliability_weight": 0.50,
        "cost_weight":        0.30,
        "lead_time_weight":   0.20,
    },
    "justification": (
        "NexusLogistics Ltd. achieves the highest composite ranking score of 0.847, "
        "combining a best-in-class 89% reliability rating with a competitive per-unit cost "
        "only 9.5% above the primary vendor, and a 5-day lead time that prevents threshold "
        "breach by a 2-day margin — making it the optimal emergency procurement choice."
    ),
    "transaction_id": "TXN-2026-NX-00491-TALOS",
    "draft_po": {
        "po_number":          "PO-TALOS-2026-0517",
        "vendor":             "NexusLogistics Ltd.",
        "component":          "LiDAR Sensor Array",
        "quantity_ordered":   1200,
        "unit_cost_usd":      156.00,
        "total_value_usd":    187200.00,
        "currency":           "USD",
        "requested_delivery": "2026-05-22",
        "payment_terms":      "NET-30",
        "incoterms":          "DDP",
        "authorization_ref":  "AUTO-BROKER-TALOS-v1",
    },
    "vendors_evaluated": 2,
    "demo_mode":         True,
}


# ─── Forge Agent Fixture ──────────────────────────────────────────────────────
FORGE_FIXTURE: dict = {
    "agent":    "Forge",
    "old_url":  "https://<VSP_CLOUD_RUN_URL>/stream_primary",
    "new_url":  "https://<VSP_CLOUD_RUN_URL>/stream_backup",
    "new_config": {
        "current_active_vendor_url": "https://<VSP_CLOUD_RUN_URL>/stream_backup",
    },
    "change_summary": (
        "Infrastructure routing updated: the daemon ingestion thread will switch from "
        "the corrupted PrimaryStream Logistics endpoint to NexusLogistics Ltd.'s backup "
        "stream on the next 3-second poll cycle. "
        "No Cloud Run restart or redeployment required — change is atomic via system_config."
    ),
    "config_delta": {
        "table":  "system_config",
        "row_id": 1,
        "field":  "current_active_vendor_url",
        "before": "https://<VSP_CLOUD_RUN_URL>/stream_primary",
        "after":  "https://<VSP_CLOUD_RUN_URL>/stream_backup",
    },
    "drafted_by": "ForgeAgent-TALOS-v1",
    "requires_approval": True,
    "demo_mode":         True,
}
