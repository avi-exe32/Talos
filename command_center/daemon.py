"""
daemon.py — Background Thread for Talos
Phase 3: Runs the continuous supply chain polling loop.
"""
import threading
import time
import requests
import logging
from typing import Dict, Any

import db
from agents import ScoutAgent

logger = logging.getLogger("Daemon")

# Global state dictionary for Streamlit to read from instantly
DAEMON_STATE: Dict[str, Any] = {
    "is_running": False,
    "last_poll_time": None,
    "current_url": None,
    "last_http_status": None,
    "last_payload": None,
    "scout_status": "NOMINAL",
    "scout_reason": "",
    "consecutive_failures": 0,
    "agent_logs": [],
    "mitigation_approved": False  # Flag to prevent button from reappearing after approval
}

class TalosDaemon(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True) # Ensures thread dies when main program exits
        self.scout = ScoutAgent()
        self._stop_event = threading.Event()
        self._first_loop = True
        self._pipeline_triggered = False # Phase 1 Fix: flag to trigger immediate boot poll
        self._cooldown_until = 0.0  # Timestamp until which pipeline is blocked

    def run(self):
        logger.info("Talos Background Daemon started.")
        DAEMON_STATE["is_running"] = True
        DAEMON_STATE["mitigation_approved"] = False  # Ensure clean state on daemon start
        self._pipeline_triggered = False  # Ensure clean state on daemon start
        self._cooldown_until = 0.0  # Ensure clean state on daemon start
        logger.info("[Daemon] State flags reset to clean values.")

        while not self._stop_event.is_set():
            try:
                self._poll_cycle()
            except Exception as e:
                logger.error(f"Daemon crash in poll cycle: {e}")

            # Phase 1 Fix: skip sleep on first iteration so UI gets clean vendor data immediately.
            # Database was reset in main.py lifespan, so first poll fetches pristine state.
            if self._first_loop:
                self._first_loop = False
                logger.info("[Daemon] First poll complete. Clean vendor payload ready for UI.")
            else:
                # 1.5-second sleep interval between polls for faster demo
                self._stop_event.wait(1.5)
            
        DAEMON_STATE["is_running"] = False
        logger.info("Talos Background Daemon stopped.")

    def _poll_cycle(self):
        # 1. ALWAYS query the database for the active URL (Dynamic switching)
        target_url = db.get_active_vendor_url()
        DAEMON_STATE["current_url"] = target_url
        
        # 2. Fetch data from the URL
        payload = None
        http_error = False
        status_code = None
        
        try:
            response = requests.get(target_url, timeout=5)
            status_code = response.status_code
            DAEMON_STATE["last_http_status"] = status_code
            
            if status_code == 200:
                try:
                    payload = response.json()
                except ValueError:
                    # Garbage unparseable text
                    http_error = True
                    clean_text = response.text[:200].replace('\x00', '')
                    payload = {"raw_text": clean_text}
            else:
                http_error = True
        except requests.RequestException as e:
            http_error = True
            DAEMON_STATE["last_http_status"] = "ERROR"
            
        DAEMON_STATE["last_payload"] = payload
        DAEMON_STATE["last_poll_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

        # 3. Pass data to Scout Agent (ONLY if pipeline hasn't been triggered)
        # Once pipeline runs, Scout pauses until user approves
        if self._pipeline_triggered:
            # Pipeline is waiting for approval - don't check for anomalies
            logger.debug("[Daemon] Pipeline pending approval. Scout monitoring paused.")
            scout_result = {"status": "PAUSED", "reason": "Awaiting human authorization", "failures": self.scout.consecutive_failures}
        else:
            # Normal Scout monitoring
            scout_result = self.scout.process_payload(payload, http_error=http_error)
        
        # 4. Update Global State for UI
        DAEMON_STATE["scout_status"] = scout_result["status"]
        DAEMON_STATE["scout_reason"] = scout_result["reason"]
        DAEMON_STATE["consecutive_failures"] = scout_result["failures"]
        
        # Also grab the latest DB logs so the UI can show agent events
        DAEMON_STATE["agent_logs"] = db.get_recent_agent_logs(limit=5)
        
        # 5. Multi-Agent Pipeline Trigger
        if scout_result["status"] == "ESCALATED":
            # Check if mitigation was already approved - never trigger pipeline again
            if DAEMON_STATE["mitigation_approved"]:
                logger.info("[Daemon] Mitigation already approved. Ignoring escalation.")
                return
            
            # Check if we are in cooldown period (prevents re-trigger after authorization)
            current_time = time.time()
            if current_time < self._cooldown_until:
                logger.info(f"[Daemon] Pipeline cooldown active. Ignoring escalation for {int(self._cooldown_until - current_time)} more seconds.")
                return
            
            # Check if we are already waiting for human approval
            pending = db.get_pending_logs()
            if not self._pipeline_triggered and not pending:
                self._pipeline_triggered = True
                logger.info("[Daemon] Initiating Multi-Agent Remediation Pipeline...")
                
                # We need to import the agents here or at the top of the file
                from agents import AnalystAgent, BrokerAgent, ForgeAgent
                
                # Phase 4.1: Analyst
                analyst = AnalystAgent()
                analyst_res = analyst.run(scout_result["payload"])
                
                # Phase 4.2: Broker
                broker = BrokerAgent()
                broker_res = broker.run(analyst_res)
                
                # Phase 4.3: Forge
                forge = ForgeAgent()
                forge.run(broker_res)
                
                logger.info("[Daemon] Pipeline complete. Awaiting human approval (Phase 5).")
            else:
                logger.info("[Daemon] Remediation is Pending. Resuming normal polling of broken stream.")
                
        elif scout_result["status"] == "NOMINAL":
            pending = db.get_pending_logs()
            if pending:
                logger.info("[Daemon] Stream recovered but mitigation is pending human approval. Holding.")
            else:
                self._pipeline_triggered = False  # only reset when nothing is pending

    def stop(self):
        self._stop_event.set()

# Singleton instance
_daemon_instance = None

def start_daemon():
    global _daemon_instance
    if _daemon_instance is None or not _daemon_instance.is_alive():
        _daemon_instance = TalosDaemon()
        _daemon_instance.start()

def stop_daemon():
    global _daemon_instance
    if _daemon_instance is not None and _daemon_instance.is_alive():
        _daemon_instance.stop()
        _daemon_instance.join(timeout=5.0)
