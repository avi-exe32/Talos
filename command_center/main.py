"""
main.py — Talos Command Center (FastAPI)
Phase 3: Serves the dark-mode frontend and the system state API.
"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import daemon
import db

logger = logging.getLogger("Main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Phase 1 Fix: Always boot with a clean slate ──────────────────────────
    # Reset logs + revert to primary URL so ghost data from a previous run
    # never pollutes the live demo. We do this BEFORE the daemon starts so
    # the daemon's very first poll sees a clean database.
    try:
        db.reset_demo()
        logger.info("[Boot] Database reset complete — clean slate for this session.")
    except Exception as e:
        logger.error(f"[Boot] DB reset failed (non-fatal): {e}")

    daemon.start_daemon()
    yield
    # Stop the daemon on server shutdown
    daemon.stop_daemon()

app = FastAPI(
    title="Talos Command Center", 
    lifespan=lifespan,
    docs_url=None, 
    redoc_url=None
)

# Ensure templates directory exists
os.makedirs("templates", exist_ok=True)
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/system_state")
def system_state():
    # Copy the daemon state so we don't mutate the live dictionary
    state = daemon.DAEMON_STATE.copy()

    # Query DB for latest 10 agent logs for the terminal output
    logs = db.get_recent_agent_logs(limit=10)

    # Format dates to string so they can be JSON serialized by FastAPI
    formatted_logs = []
    for log in reversed(logs): # Reverse to show oldest at top, newest at bottom of the terminal log
        formatted_logs.append({
            "id": log["id"],
            "agent": log["agent_name"],
            "state": log["lifecycle_state"],
            "time": log["created_at"].strftime("%H:%M:%S"),
            "payload": log["payload"]
        })

    state["agent_logs"] = formatted_logs

    # PHASE 2 Fix: The AUTHORIZE button ONLY appears when the Forge Agent is Pending.
    # This ensures the human-in-the-loop gate waits for the FULL pipeline to complete,
    # not just the Analyst or Broker. Ignore Pending logs from other agents.
    # If mitigation was already approved, never show the button again until reset.
    if daemon.DAEMON_STATE["mitigation_approved"]:
        state["has_pending"] = False
    else:
        pending_logs = db.get_pending_logs()
        forge_pending = any(log["agent_name"] == "Forge" for log in pending_logs)
        state["has_pending"] = forge_pending

    return state

@app.post("/api/approve_mitigation")
def approve_mitigation():
    try:
        # Set flag FIRST to prevent button from reappearing on next poll
        daemon.DAEMON_STATE["mitigation_approved"] = True
        logger.info("[Approval] Mitigation approved flag set. Button will not reappear until demo reset.")
        
        # Set 10-second cooldown to prevent re-triggering during URL switch
        import time
        daemon._daemon_instance._cooldown_until = time.time() + 10
        logger.info("[Approval] 10-second pipeline cooldown activated to allow URL switch to stabilize.")
        
        # Now execute the mitigation
        new_url = db.execute_pending_mitigation()
        
        return {"status": "success", "new_url": new_url}
    except Exception as e:
        # If execution fails, reset the flag
        daemon.DAEMON_STATE["mitigation_approved"] = False
        return {"status": "error", "message": str(e)}

@app.post("/api/reset_demo")
def reset_demo():
    try:
        db.reset_demo()
        daemon._daemon_instance._pipeline_triggered = False
        daemon._daemon_instance.scout.consecutive_failures = 0
        daemon.DAEMON_STATE["mitigation_approved"] = False  # Reset approval flag
        logger.info("[Reset] Mitigation approval flag reset. Button can appear again.")
        
        # Also ensure the vendor portal is reset back to a clean state
        import requests
        try:
            health_res = requests.get("https://talos-vsp-78550706553.asia-south1.run.app/health", timeout=5).json()
            if health_res.get("is_corrupted"):
                requests.post("https://talos-vsp-78550706553.asia-south1.run.app/toggle_corruption", timeout=5)
        except Exception as e:
            # Ignore VSP reachability errors during reset so we don't crash
            pass
            
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ─── Oracle Chat Stub ──────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    message: str

@app.post("/api/chat")
def oracle_chat(body: ChatMessage):
    """
    Stub endpoint for The Oracle chatbot.
    Returns a mock AI response. Replace with a real LLM call in the next phase.
    """
    user_msg = body.message.strip().lower()
    # Simple keyword-based mock responses for demo purposes
    if any(k in user_msg for k in ["status", "state", "health"]):
        reply = "All primary systems are nominal. Scout Agent is actively monitoring the vendor feed. No anomalies detected in the current cycle."
    elif any(k in user_msg for k in ["vendor", "supply", "stream"]):
        reply = "The primary vendor stream is authenticated and streaming clean inventory telemetry. Circuit-breaker threshold set at 3 consecutive failures."
    elif any(k in user_msg for k in ["agent", "pipeline", "forge", "analyst", "broker"]):
        reply = "The multi-agent pipeline is armed. On detection of supply chain corruption: Scout escalates → Analyst quantifies risk → Broker sources alternatives → Forge generates the patch. Awaiting your authorization."
    elif any(k in user_msg for k in ["mitigation", "approve", "execute"]):
        reply = "Human-in-the-loop gate is active. I cannot execute mitigations autonomously — that requires your explicit authorization via the AUTHORIZE MITIGATION control."
    else:
        reply = f"Acknowledged. Processing query: '{body.message}'. The Oracle is fully operational. Ask me about system status, agent pipeline, or vendor health."

    return {"response": reply}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
