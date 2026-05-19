"""
agents.py — Talos Multi-Agent Logic
Phase 4: Scout, Analyst, Broker, and Forge Agents powered by Gemini.
"""
import os
import json
import logging
from typing import Any, Dict, Optional
import vertexai
from vertexai.generative_models import GenerativeModel
from dotenv import load_dotenv

import db

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Agents")

# Map the credentials path to the OS environment
credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if credentials_path:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

project_id = os.getenv("GCP_PROJECT_ID")
region = os.getenv("GCP_REGION", "asia-south1") 

if project_id and region and credentials_path:
    vertexai.init(project=project_id, location=region)
    
    # We will control the model version via .env to ensure region compatibility
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-002")
    model = GenerativeModel(
        model_name,
        generation_config={"response_mime_type": "application/json"}
    )
    logger.info(f"Vertex AI initialized in {region} using model {model_name}")
else:
    logger.error("Vertex AI env vars missing.")
    model = None

# ─── 1. SCOUT AGENT ──────────────────────────────────────────────────────────

class ScoutAgent:
    """
    The Scout Agent is the frontline observer.
    It inspects incoming data for anomalies (crashes, zeroes, garbage).
    Triggers an escalation if 3 consecutive failures occur.
    """
    def __init__(self):
        self.consecutive_failures = 0
        self.failure_threshold = 3

    def process_payload(self, payload: Optional[Dict[str, Any]], http_error: bool = False) -> Dict[str, Any]:
        is_anomaly = False
        reason = ""

        if http_error or payload is None:
            is_anomaly = True
            reason = "HTTP Request Failed or Payload Unparseable"
        elif payload.get("error_flag") is True or payload.get("stream_health") != "nominal":
            is_anomaly = True
            reason = f"Vendor reported error state: {payload.get('stream_health')}"
        elif payload.get("quantity", -1) == 0:
            is_anomaly = True
            reason = "Critical boundary violation: quantity is 0"

        if is_anomaly:
            self.consecutive_failures += 1
            logger.warning(f"[Scout] Anomaly detected ({self.consecutive_failures}/{self.failure_threshold}): {reason}")
            
            if self.consecutive_failures >= self.failure_threshold:
                logger.error("[Scout] ⚡ ESCALATION TRIGGERED! 3 consecutive failures.")
                alert_payload = {
                    "alert_type": "SUPPLY_CHAIN_CRISIS",
                    "reason": reason,
                    "last_payload": payload or "UNPARSEABLE_GARBAGE",
                    "failures": self.consecutive_failures
                }
                # Log to database as Executed since Scout is just a trigger
                db.log_agent_event("Scout", "Executed", alert_payload)
                failures_count = self.consecutive_failures
                self.consecutive_failures = 0
                return {"status": "ESCALATED", "reason": reason, "failures": failures_count, "payload": alert_payload}
                
            return {"status": "WARNING", "reason": reason, "failures": self.consecutive_failures}
            
        else:
            if self.consecutive_failures > 0:
                logger.info("[Scout] Stream recovered. Resetting failure count.")
            self.consecutive_failures = 0
            return {"status": "NOMINAL", "reason": "Data looks clean", "failures": 0}

# ─── 2. ANALYST AGENT ────────────────────────────────────────────────────────

class AnalystAgent:
    """
    The Mathematician. Evaluates supply chain exposure.
    Queries inventory DB + Scout error log.
    Outputs: hours_until_stockout, projected_loss_usd, summary.
    """
    def run(self, scout_alert: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("[Analyst] Waking up. Querying inventory DB...")
        db.log_agent_event("Analyst", "Running", {"status": "processing"})
        inventory = db.get_inventory()
        
        prompt = f"""
        You are an expert Supply Chain Financial Analyst.
        A critical disruption has occurred.

        [Scout Agent Alert]:
        {json.dumps(scout_alert, indent=2, default=str)}

        [Live Database Inventory Record]:
        {json.dumps(inventory, indent=2, default=str)}

        Calculate the remaining hours until the factory stocks out of this component,
        and calculate the projected financial loss if production stops (based on daily_consumption_rate and unit cost).
        
        You MUST return ONLY a valid JSON object matching this schema:
        {{
            "hours_until_stockout": int,
            "projected_loss_usd": float,
            "summary": "string explaining the exposure"
        }}
        """
        
        response = model.generate_content(prompt)
        result = json.loads(response.text)
        
        db.log_agent_event("Analyst", "Pending", result)
        return result

# ─── 3. BROKER AGENT ─────────────────────────────────────────────────────────

class BrokerAgent:
    """
    The Procurement Officer. Selects the optimal backup vendor.
    Queries vendors DB + Analyst timeline.
    Outputs: selected_vendor_id, justification, draft_po_total.
    """
    def run(self, analyst_report: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("[Broker] Waking up. Querying backup vendors DB...")
        db.log_agent_event("Broker", "Running", {"status": "processing"})
        backup_vendors = db.get_vendors(vendor_type="backup")
        
        prompt = f"""
        You are a ruthless, highly efficient Procurement Officer.
        We have a supply chain crisis. The Analyst has determined our timeline:

        [Analyst Report]:
        {json.dumps(analyst_report, indent=2, default=str)}

        [Available Backup Vendors in DB]:
        {json.dumps(backup_vendors, indent=2, default=str)}

        Select the optimal backup vendor that can prevent a stockout based on lead time, cost, and reliability.
        Draft a Purchase Order total based on the inventory consumption rate for a 7-day supply.
        
        You MUST return ONLY a valid JSON object matching this schema:
        {{
            "selected_vendor_id": "string",
            "justification": "string",
            "draft_po_total": float
        }}
        """
        
        response = model.generate_content(prompt)
        result = json.loads(response.text)
        
        db.log_agent_event("Broker", "Pending", result)
        return result

# ─── 4. FORGE AGENT ──────────────────────────────────────────────────────────

class ForgeAgent:
    """
    The Engineer. Generates the infrastructure patch for the selected vendor.
    Outputs: new_target_url.
    """
    def run(self, broker_report: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("[Forge] Waking up. Generating API patch for selected vendor...")
        db.log_agent_event("Forge", "Running", {"status": "processing"})
        
        # We need the vendor's API URL to generate the patch
        all_vendors = db.get_vendors()
        selected_vendor = next((v for v in all_vendors if str(v["id"]) == str(broker_report["selected_vendor_id"])), None)
        
        target_api_url = selected_vendor["stream_url"] if selected_vendor else "UNKNOWN_API_URL"
        
        prompt = f"""
        You are a Cloud Network Engineer. 
        The Broker has selected a new vendor for failover.
        
        [Broker Selection]:
        {json.dumps(broker_report, indent=2, default=str)}
        
        [Vendor API Endpoint]:
        {target_api_url}

        Generate the infrastructure configuration patch. Since we are using an HTTP router, you just need to output the new target URL.
        
        You MUST return ONLY a valid JSON object matching this schema:
        {{
            "new_target_url": "string (the api_url of the selected vendor)"
        }}
        """
        
        response = model.generate_content(prompt)
        result = json.loads(response.text)
        
        db.log_agent_event("Forge", "Pending", result)
        return result
