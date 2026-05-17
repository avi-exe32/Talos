"""
test_db.py — Phase 1 Acceptance Test
=====================================
Run this from the command_center/ directory to verify:
  1. Cloud SQL connection is working
  2. All 4 tables exist with correct seed data
  3. All db.py helper functions work correctly

Usage:
    cd command_center
    pip install -r requirements.txt
    python test_db.py
"""

import sys
import os

# Ensure we load the .env from this directory
sys.path.insert(0, os.path.dirname(__file__))

import db

def separator(title: str):
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print('═' * 60)

def run_tests():
    print("\n🛰️  TALOS — Phase 1 Database Acceptance Test")
    print("=" * 60)

    # ── Test 1: Connectivity ──────────────────────────────────────
    separator("TEST 1: DB Connectivity (ping)")
    result = db.ping_db()
    assert result, "❌ FAIL: Cannot connect to Cloud SQL."
    print("✅ PASS: Connected to Cloud SQL successfully.")

    # ── Test 2: system_config ─────────────────────────────────────
    separator("TEST 2: get_active_vendor_url()")
    url = db.get_active_vendor_url()
    print(f"  Active URL → {url}")
    assert isinstance(url, str) and len(url) > 0, "❌ FAIL: URL is empty or wrong type."
    print("✅ PASS: system_config row returned correctly.")

    # ── Test 3: inventory ─────────────────────────────────────────
    separator("TEST 3: get_inventory()")
    inv = db.get_inventory()
    print(f"  Inventory → {inv}")
    assert inv.get("component_name") == "LiDAR Sensor Array", "❌ FAIL: Wrong component name."
    assert inv.get("stock_on_hand") == 847, "❌ FAIL: Wrong stock level."
    assert inv.get("daily_consumption_rate") == 137, "❌ FAIL: Wrong burn rate."
    print("✅ PASS: inventory row verified.")

    # ── Test 4: vendors ───────────────────────────────────────────
    separator("TEST 4: get_vendors()")
    vendors = db.get_vendors()
    print(f"  Total vendors: {len(vendors)}")
    for v in vendors:
        print(f"  [{v['vendor_type'].upper()}] {v['vendor_name']} | reliability={v['reliability_score']}")
    assert len(vendors) == 3, f"❌ FAIL: Expected 3 vendors, got {len(vendors)}."
    backups = db.get_vendors("backup")
    assert len(backups) == 2, f"❌ FAIL: Expected 2 backup vendors, got {len(backups)}."
    print("✅ PASS: vendors table verified.")

    # ── Test 5: log_agent_event ───────────────────────────────────
    separator("TEST 5: log_agent_event() write")
    new_id = db.log_agent_event(
        "Scout",
        "Pending",
        {"test": True, "message": "Phase 1 acceptance test log entry"}
    )
    print(f"  New agent_log row id → {new_id}")
    assert isinstance(new_id, int) and new_id > 0, "❌ FAIL: Invalid row ID returned."
    print("✅ PASS: agent_log write successful.")

    # ── Test 6: get_recent_agent_logs ─────────────────────────────
    separator("TEST 6: get_recent_agent_logs()")
    logs = db.get_recent_agent_logs(limit=5)
    print(f"  Recent log count (up to 5): {len(logs)}")
    assert len(logs) >= 1, "❌ FAIL: No logs returned."
    print(f"  Latest: [{logs[0]['agent_name']}] {logs[0]['lifecycle_state']} @ {logs[0]['created_at']}")
    print("✅ PASS: get_recent_agent_logs returned correctly.")

    # ── Test 7: get_pending_logs ──────────────────────────────────
    separator("TEST 7: get_pending_logs()")
    pending = db.get_pending_logs()
    print(f"  Pending log count: {len(pending)}")
    assert any(p.get("lifecycle_state") == "Pending" for p in pending), \
        "❌ FAIL: Expected at least one Pending log."
    print("✅ PASS: get_pending_logs returned correctly.")

    # ── Test 8: mark_logs_executed ───────────────────────────────
    separator("TEST 8: mark_logs_executed() (cleans up test log)")
    count = db.mark_logs_executed()
    print(f"  Marked {count} Pending log(s) as Executed.")
    assert count >= 1, "❌ FAIL: No logs were marked executed."
    print("✅ PASS: mark_logs_executed worked.")

    # ── All passed ────────────────────────────────────────────────
    print(f"\n{'═' * 60}")
    print("  ✅  ALL PHASE 1 TESTS PASSED — Ready for Phase 2")
    print('═' * 60)

if __name__ == "__main__":
    run_tests()
