"""
agents.py — Talos Multi-Agent Logic
Phase 3: Implements the ScoutAgent.
"""
import logging
from typing import Any, Dict, Optional
import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Scout")

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
        """
        Inspects the payload. Returns a status dictionary.
        """
        is_anomaly = False
        reason = ""

        # 1. Check for complete HTTP failure or parsing failure
        if http_error or payload is None:
            is_anomaly = True
            reason = "HTTP Request Failed or Payload Unparseable"
        
        # 2. Check for explicit error flags or zero quantity
        elif payload.get("error_flag") is True or payload.get("stream_health") != "nominal":
            is_anomaly = True
            reason = f"Vendor reported error state: {payload.get('stream_health')}"
        elif payload.get("quantity", -1) == 0:
            is_anomaly = True
            reason = "Critical boundary violation: quantity is 0"

        # Handle the result
        if is_anomaly:
            self.consecutive_failures += 1
            logger.warning(f"Anomaly detected ({self.consecutive_failures}/{self.failure_threshold}): {reason}")
            
            # Circuit Breaker Trigger
            if self.consecutive_failures >= self.failure_threshold:
                logger.error("⚡ ESCALATION TRIGGERED! 3 consecutive failures.")
                alert_payload = {
                    "alert_type": "SUPPLY_CHAIN_CRISIS",
                    "reason": reason,
                    "last_payload": payload or "UNPARSEABLE_GARBAGE",
                    "failures": self.consecutive_failures
                }
                # Log to database for the Analyst agent to pick up
                db.log_agent_event(
                    agent_name="Scout",
                    lifecycle_state="Pending",
                    payload=alert_payload
                )
                self.consecutive_failures = 0 # Reset after triggering
                
                return {"status": "ESCALATED", "reason": reason, "failures": 3}
                
            return {"status": "WARNING", "reason": reason, "failures": self.consecutive_failures}
            
        else:
            # Healthy payload resets the failure count
            if self.consecutive_failures > 0:
                logger.info("Stream recovered. Resetting failure count to 0.")
            self.consecutive_failures = 0
            return {"status": "NOMINAL", "reason": "Data looks clean", "failures": 0}
