<div align="center">

```
 ████████╗ █████╗ ██╗      ██████╗ ███████╗
    ██╔══╝██╔══██╗██║     ██╔═══██╗██╔════╝
    ██║   ███████║██║     ██║   ██║███████╗
    ██║   ██╔══██║██║     ██║   ██║╚════██║
    ██║   ██║  ██║███████╗╚██████╔╝███████║
    ╚═╝   ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚══════╝
```

**Autonomous Multi-Agent AI for Real-Time Supply Chain Defense**

[![Python](https://img.shields.io/badge/Python-3.13-blue?style=flat-square&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Google Cloud](https://img.shields.io/badge/Google_Cloud-Run-orange?style=flat-square&logo=google-cloud)](https://cloud.google.com/run)
[![Gemini](https://img.shields.io/badge/Gemini-1.5_Flash-purple?style=flat-square&logo=google)](https://cloud.google.com/vertex-ai)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue?style=flat-square&logo=postgresql)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[Live Demo](https://talos-command-center-78550706553.asia-south1.run.app) · [Report Bug](https://github.com/avi-exe32/Talos/issues) · [Architecture Docs](#architecture)

</div>

---

## What is Talos?

Manufacturing companies lose millions when vendor data streams fail. A corrupted API, a failed HTTP connection, a zero-quantity anomaly — manual detection takes hours. Production halts. Losses mount.

**Talos eliminates that window entirely.**

It's an autonomous multi-agent AI system that monitors vendor streams in real-time, detects anomalies the moment they appear, orchestrates a full remediation pipeline powered by Google Gemini, and executes a vendor failover — all within seconds, with a human making the final call.

```
Anomaly Detected → Analyst quantifies risk → Broker selects vendor → Forge generates patch → Human approves → Stream switches
```

The entire pipeline from detection to resolution runs in under 60 seconds.

---

## Demo

> Trigger a supply chain crisis, watch the AI pipeline execute, authorize the fix.

| Normal Operation | Crisis Detected | Pipeline Running | Authorized |
|:---:|:---:|:---:|:---:|
| Scout monitoring, NOMINAL | 3 failures → ESCALATED | Analyst → Broker → Forge | Stream switched, NOMINAL |

**Live instance:** [talos-command-center-78550706553.asia-south1.run.app](https://talos-command-center-78550706553.asia-south1.run.app)

---

## How It Works

### The 4-Agent Pipeline

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  SCOUT   │───▶│ ANALYST  │───▶│  BROKER  │───▶│  FORGE   │
│          │    │          │    │          │    │          │
│ Monitors │    │Quantifies│    │ Selects  │    │ Generates│
│  stream  │    │   risk   │    │  vendor  │    │  patch   │
│every 1.5s│    │ & losses │    │optimally │    │   URL    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     │                                                │
     │ 3 consecutive failures                         │
     └────────── triggers pipeline ──────────────────▶│
                                                      │
                                              ┌───────▼──────┐
                                              │    HUMAN     │
                                              │  AUTHORIZE   │
                                              │   BUTTON     │
                                              └──────────────┘
```

**Scout Agent** — Polls the vendor stream every 1.5 seconds. Checks for HTTP failures, corrupted JSON, and zero-quantity violations. Escalates after 3 consecutive failures. No false positives from transient glitches.

**Analyst Agent** — Powered by Gemini 1.5 Flash. Queries the live inventory database, calculates hours until factory stockout, and computes projected financial loss per day. Outputs structured JSON with hard numbers.

**Broker Agent** — Evaluates all backup vendors from the database. Scores each one across reliability, cost, and lead time. Selects the optimal vendor and drafts a Purchase Order total. Ensures selected vendor can deliver before stockout.

**Forge Agent** — Generates the infrastructure patch. Retrieves the selected vendor's API endpoint and outputs the new target URL that gets written to the circuit breaker config.

### Human-in-the-Loop Gate

After all three agents complete, the system **pauses**. The dashboard dims. The AUTHORIZE MITIGATION button appears.

The human reviews everything — financial impact, vendor selection, infrastructure change — then clicks to execute. The system cannot proceed without explicit human authorization.

This isn't just a UX choice. Supply chain switches affect millions in contracts, carry legal and compliance implications, and are irreversible in the short term. The human stays in control.

### The Circuit Breaker

When authorized, Talos writes the new vendor URL to the `system_config` table. On the daemon's next 1.5-second poll cycle, it reads the new URL and switches the stream. No restart. No redeployment. The change is atomic.

---

## Architecture

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, Vanilla JS, CSS3 — terminal-aesthetic dark UI |
| Backend | FastAPI (Python 3.13), Uvicorn, Threading |
| Database | PostgreSQL 15 on Google Cloud SQL |
| AI | Google Gemini 1.5 Flash via Vertex AI (JSON mode) |
| Chatbot | Gemini 2.5 Flash (text mode) |
| Infrastructure | Google Cloud Run, Cloud SQL Connector, IAM |

### Database Schema

```
system_config     → circuit breaker URL (the one config row that controls everything)
inventory         → stock levels, consumption rates, unit costs
vendors           → primary + backup vendor profiles with reliability scores
agent_log         → full audit trail of every agent event (Running → Pending → Executed)
```

### File Structure

```
Talos/
├── command_center/
│   ├── main.py              # FastAPI app — HTTP endpoints, lifespan
│   ├── daemon.py            # Background thread — polls vendor, runs pipeline
│   ├── agents.py            # Scout, Analyst, Broker, Forge — Gemini logic
│   ├── db.py                # PostgreSQL — all queries, zero raw SQL injection
│   ├── templates/
│   │   └── index.html       # Dashboard — polls /api/system_state every second
│   └── requirements.txt
├── sql/
│   ├── schema.sql           # Table definitions
│   └── seed.sql             # Initial vendor + inventory data
└── vsp/                     # Vendor Simulator Portal
    └── main.py              # Simulates primary + backup vendor streams
```

### Data Flow

```
Browser (index.html)
    │ GET /api/system_state every 1s
    ▼
main.py (FastAPI)
    │ reads DAEMON_STATE + DB logs
    ├──────────────────────────────────────┐
    ▼                                      ▼
daemon.py (background thread)          db.py (PostgreSQL)
    │ polls vendor every 1.5s              │ agent_log, system_config
    │ runs Scout                           │ inventory, vendors
    │ triggers pipeline on ESCALATED       │
    ▼                                      │
agents.py (Gemini)                         │
    │ Analyst → Broker → Forge             │
    └──────────────────────────────────────┘
                  │ writes to
                  ▼
           Cloud SQL (PostgreSQL)
                  │
                  ▼
           Vertex AI (Gemini 1.5 Flash)
```

---

## Local Setup

### Prerequisites

- Python 3.13+
- A Google Cloud project with Vertex AI and Cloud SQL enabled
- A service account JSON key with `Vertex AI User` + `Cloud SQL Client` roles

### 1. Clone

```bash
git clone https://github.com/avi-exe32/Talos.git
cd Talos/command_center
```

### 2. Install dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

Create `command_center/.env`:

```env
# Database
DB_HOST=your-cloud-sql-public-ip
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your-password
DB_NAME=talos_app

# Google Cloud
GCP_PROJECT_ID=your-project-id
GCP_REGION=asia-south1
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json
GEMINI_MODEL=gemini-1.5-flash-002

# Connection mode
USE_CONNECTOR=false   # true for Cloud Run, false for local
```

### 4. Initialize database

```bash
python run_sql.py
```

### 5. Run

```bash
python main.py
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080)

---

## Deploy to Cloud Run

```bash
gcloud run deploy talos-command-center \
  --source . \
  --region asia-south1 \
  --add-cloudsql-instances YOUR_PROJECT:asia-south1:YOUR_INSTANCE \
  --set-env-vars USE_CONNECTOR=true \
  --set-env-vars DB_NAME=talos_app \
  --set-env-vars DB_USER=postgres \
  --set-env-vars DB_PASSWORD=your-password \
  --set-env-vars INSTANCE_CONNECTION_NAME=YOUR_PROJECT:asia-south1:YOUR_INSTANCE \
  --set-env-vars GCP_PROJECT_ID=your-project-id \
  --set-env-vars GCP_REGION=asia-south1 \
  --set-env-vars GEMINI_MODEL=gemini-1.5-flash-002 \
  --set-env-vars GOOGLE_APPLICATION_CREDENTIALS="" \
  --min-instances 1 \
  --allow-unauthenticated
```

The `--min-instances 1` is required — it keeps the daemon thread alive permanently. Without it, Cloud Run scales to zero and kills the background thread mid-pipeline.

---

## Running the Demo

1. Open the dashboard. System shows **NOMINAL** — Scout is monitoring the primary vendor stream.

2. Click **VENDOR PORTAL** → go to `/toggle_corruption` → Execute. This corrupts the vendor stream.

3. Watch Scout detect 3 consecutive failures and escalate. The AI Brain panel activates.

4. The pipeline executes automatically:
   - Analyst calculates stockout timeline and financial exposure
   - Broker selects the optimal backup vendor
   - Forge generates the infrastructure patch

5. The **AUTHORIZE MITIGATION** button appears. Review the agent outputs, then click it.

6. Stream switches to the backup vendor. Scout returns to **NOMINAL**. Crisis resolved.

---

## Oracle Chatbot

The floating `◈` button opens the AI Oracle — a Gemini 2.5 Flash powered assistant that explains what's happening in the system in plain English. Ask it anything: what the Scout detected, why the Broker picked a specific vendor, what happens after you press Authorize.

---

## Key Design Decisions

**Why threading instead of async for the daemon?** Gemini API calls are blocking. A background thread handles this naturally without blocking the HTTP server. AsyncIO would require running the daemon in an executor anyway.

**Why 1-second UI polling instead of WebSockets?** Simple, stateless, and works everywhere. For a demo context, 1-second polling feels instant. WebSockets are on the roadmap.

**Why JSON mode for agents?** Every agent produces structured data that the frontend and subsequent agents depend on. JSON mode eliminates parsing errors and hallucinated formats entirely.

**Why Human-in-the-Loop?** Because supply chain switches trigger legal contracts, affect factory operations, and involve millions of dollars. The AI does the analysis. The human makes the call.

---

## Future Roadmap

- Multi-vendor simultaneous monitoring
- Predictive failure detection (ML-based, before failures happen)
- Slack / PagerDuty alert integration
- WebSocket for true real-time push updates
- Role-based access control (RBAC) for enterprise use
- Terraform config generation in Forge agent (real infra patches)
- Cost optimization engine in Broker (multi-factor financial scoring)

---

## Built By

**Avinash** — [avi-exe32](https://github.com/avi-exe32)

Built with FastAPI, Google Gemini, Cloud Run, and way too many late nights debugging daemon thread race conditions.

---

<div align="center">

*Talos — Because supply chains shouldn't depend on someone noticing.*

</div>
