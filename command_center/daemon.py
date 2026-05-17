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
    "agent_logs": []
}

class TalosDaemon(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True) # Ensures thread dies when main program exits
        self.scout = ScoutAgent()
        self._stop_event = threading.Event()

    def run(self):
        logger.info("Talos Background Daemon started.")
        DAEMON_STATE["is_running"] = True
        
        while not self._stop_event.is_set():
            try:
                self._poll_cycle()
            except Exception as e:
                logger.error(f"Daemon crash in poll cycle: {e}")
            
            # 3-second sleep interval between polls
            self._stop_event.wait(3.0)
            
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
                    payload = {"raw_text": response.text[:200]}
            else:
                http_error = True
        except requests.RequestException as e:
            http_error = True
            DAEMON_STATE["last_http_status"] = "ERROR"
            
        DAEMON_STATE["last_payload"] = payload
        DAEMON_STATE["last_poll_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

        # 3. Pass data to Scout Agent
        scout_result = self.scout.process_payload(payload, http_error=http_error)
        
        # 4. Update Global State for UI
        DAEMON_STATE["scout_status"] = scout_result["status"]
        DAEMON_STATE["scout_reason"] = scout_result["reason"]
        DAEMON_STATE["consecutive_failures"] = scout_result["failures"]
        
        # Also grab the latest 5 DB logs so the UI can show agent events
        DAEMON_STATE["agent_logs"] = db.get_recent_agent_logs(limit=5)

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
