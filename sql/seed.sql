-- =============================================================================
--  TALOS — seed.sql
--  Realistic seed data for all 4 tables.
--  Run AFTER schema.sql.
--
--  IMPORTANT: After Phase 2 (VSP deployed), replace every occurrence of
--  <VSP_CLOUD_RUN_URL> with your actual Cloud Run service URL, e.g.:
--    https://talos-vsp-xxxxxxxx-uc.a.run.app
-- =============================================================================

-- ── 1. Inventory ─────────────────────────────────────────────────────────────
--  847 LiDAR units on hand, burning 137/day, halt threshold at 200 units.
--  Daily production value: $694,167 (used by Analyst Agent for financial math)
INSERT INTO inventory
    (component_name, stock_on_hand, daily_consumption_rate, factory_threshold, unit_cost_per_day)
VALUES
    ('LiDAR Sensor Array', 847, 137, 200, 694166.67);


-- ── 2. Vendors ───────────────────────────────────────────────────────────────
--  1 primary vendor (corruptible) + 2 ranked backup options.
--  stream_url placeholders will be updated after VSP Cloud Run deploy.
INSERT INTO vendors
    (vendor_name, vendor_type, unit_cost, shipping_lead_days, reliability_score, stream_url, contact_email)
VALUES
    (
        'PrimaryStream Logistics',
        'primary',
        142.50,
        3,
        0.940,
        'https://<VSP_CLOUD_RUN_URL>/stream_primary',
        'ops@primarystream.io'
    ),
    (
        'NexusLogistics Ltd.',
        'backup',
        156.00,
        5,
        0.890,
        'https://<VSP_CLOUD_RUN_URL>/stream_backup',
        'supply@nexuslogistics.com'
    ),
    (
        'ApexFreight Solutions',
        'backup',
        168.75,
        7,
        0.820,
        'https://<VSP_CLOUD_RUN_URL>/stream_backup',
        'orders@apexfreight.net'
    );


-- ── 3. system_config ─────────────────────────────────────────────────────────
--  Bootstraps the circuit breaker to point at the primary stream.
--  Uses ON CONFLICT so this is safe to re-run without duplicating the row.
INSERT INTO system_config (id, current_active_vendor_url, last_updated_by)
VALUES (
    1,
    'https://<VSP_CLOUD_RUN_URL>/stream_primary',
    'system_init'
)
ON CONFLICT (id) DO UPDATE
    SET current_active_vendor_url = EXCLUDED.current_active_vendor_url,
        last_updated_by           = EXCLUDED.last_updated_by,
        updated_at                = NOW();


-- ── 4. agent_log ─────────────────────────────────────────────────────────────
--  Seed one bootstrap event so the audit log panel isn't empty on first load.
INSERT INTO agent_log (agent_name, lifecycle_state, payload)
VALUES (
    'Scout',
    'Executed',
    '{"event": "system_bootstrap", "message": "Talos Command Center initialized. Monitoring primary stream.", "demo_mode": false}'::jsonb
);


-- ── Verification Queries ─────────────────────────────────────────────────────
--  Uncomment and run these to confirm seed data loaded correctly:
--
-- SELECT * FROM inventory;
-- SELECT id, vendor_name, vendor_type, reliability_score, stream_url FROM vendors;
-- SELECT * FROM system_config;
-- SELECT * FROM agent_log;
