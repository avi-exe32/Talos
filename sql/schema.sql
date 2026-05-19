-- =============================================================================
--  TALOS — schema.sql
--  PostgreSQL DDL for Google Cloud SQL (talos-496511:asia-south1:talos-base)
--  Database: talos_app
--  Run this file once to initialize all tables.
--  Safe to re-run: uses DROP IF EXISTS before each CREATE.
-- =============================================================================

-- ── Wipe existing tables (order matters due to no FK constraints) ────────────
DROP TABLE IF EXISTS agent_log;
DROP TABLE IF EXISTS system_config;
DROP TABLE IF EXISTS vendors;
DROP TABLE IF EXISTS inventory;


-- ── 1. inventory ─────────────────────────────────────────────────────────────
--  Tracks current stock levels, consumption rates, and factory danger zones.
CREATE TABLE inventory (
    id                    SERIAL          PRIMARY KEY,
    component_name        TEXT            NOT NULL,
    stock_on_hand         INTEGER         NOT NULL DEFAULT 0,
    daily_consumption_rate INTEGER        NOT NULL DEFAULT 0,
    factory_threshold     INTEGER         NOT NULL DEFAULT 0,   -- units below which production halts
    unit_cost_per_day     NUMERIC(12, 2)  NOT NULL DEFAULT 0.00, -- daily production value at risk
    updated_at            TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  inventory                       IS 'Live component stock tracker for factory floor';
COMMENT ON COLUMN inventory.factory_threshold     IS 'Units below this value trigger a production halt alert';
COMMENT ON COLUMN inventory.unit_cost_per_day     IS 'USD value of daily production dependent on this component';


-- ── 2. vendors ───────────────────────────────────────────────────────────────
--  Supplier profiles for both primary and backup vendors.
CREATE TABLE vendors (
    id                  SERIAL          PRIMARY KEY,
    vendor_name         TEXT            NOT NULL,
    vendor_type         TEXT            NOT NULL
                            CHECK (vendor_type IN ('primary', 'backup')),
    unit_cost           NUMERIC(10, 2)  NOT NULL,
    shipping_lead_days  INTEGER         NOT NULL,
    reliability_score   NUMERIC(4, 3)   NOT NULL
                            CHECK (reliability_score BETWEEN 0.000 AND 1.000),
    stream_url          TEXT            NOT NULL,  -- API endpoint this vendor streams from
    contact_email       TEXT,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  vendors               IS 'Supplier profiles — primary and backup vendors';
COMMENT ON COLUMN vendors.stream_url    IS 'Live API endpoint polled by the daemon ingestion thread';
COMMENT ON COLUMN vendors.reliability_score IS 'Normalized 0–1 score used by Broker Agent ranking formula';


-- ── 3. agent_log ─────────────────────────────────────────────────────────────
--  Full immutable audit trail for every agent action in the pipeline.
CREATE TABLE agent_log (
    id              SERIAL      PRIMARY KEY,
    agent_name      TEXT        NOT NULL
                        CHECK (agent_name IN ('Scout', 'Analyst', 'Broker', 'Forge')),
    lifecycle_state TEXT        NOT NULL DEFAULT 'Pending'
                        CHECK (lifecycle_state IN ('Running', 'Pending', 'Executed', 'Rejected')),
    payload         JSONB,      -- structured agent output; NULL for simple events
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  agent_log                 IS 'Immutable audit trail of every agent event in the pipeline';
COMMENT ON COLUMN agent_log.lifecycle_state IS 'Pending = awaiting gate; Executed = approved; Rejected = blocked';
COMMENT ON COLUMN agent_log.payload         IS 'Full structured JSON output from the agent';

-- Index for fast audit log panel queries (most-recent-first)
CREATE INDEX idx_agent_log_created_at ON agent_log (created_at DESC);
CREATE INDEX idx_agent_log_state      ON agent_log (lifecycle_state);


-- ── 4. system_config ─────────────────────────────────────────────────────────
--  Single-row live circuit breaker. The daemon reads this on every 3s cycle.
--  The Forge Agent + Approval Gate write to this row to switch vendors.
CREATE TABLE system_config (
    id                        INTEGER     PRIMARY KEY DEFAULT 1,
    current_active_vendor_url TEXT        NOT NULL,
    last_updated_by           TEXT        NOT NULL DEFAULT 'system',
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Enforce exactly one row forever
    CONSTRAINT single_row_only CHECK (id = 1)
);

COMMENT ON TABLE  system_config                         IS 'Single-row live circuit breaker — governs which vendor URL the daemon polls';
COMMENT ON COLUMN system_config.current_active_vendor_url IS 'The URL the 3-second daemon thread reads on every cycle';
COMMENT ON COLUMN system_config.last_updated_by         IS 'Audit: system_init | ApprovalGate | ForgeAgent';
