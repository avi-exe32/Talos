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
        
        # Resume Scout monitoring after approval
        daemon._daemon_instance._pipeline_triggered = False
        logger.info("[Approval] Scout monitoring resumed.")
        
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
    The Oracle - AI-powered assistant that explains Talos system operations.
    Uses Gemini to provide dynamic, context-aware responses about the system.
    """
    try:
        # Import Gemini components to create a text-only model for chat
        from agents import project_id, region, model_name
        import vertexai
        from vertexai.generative_models import GenerativeModel
        
        if project_id is None or region is None:
            return {"response": "The Oracle is currently offline. Gemini AI model is not configured. Please check your GCP credentials and model settings."}
        
        # Create a separate model instance for chat that returns plain text (not JSON)
        chat_model = GenerativeModel(model_name)
        
        # Get current system state for context
        current_state = daemon.DAEMON_STATE.copy()
        recent_logs = db.get_recent_agent_logs(limit=5)
        
        # Build context about current system state
        system_context = f"""
        Current System State:
        - Scout Status: {current_state.get('scout_status', 'UNKNOWN')}
        - Scout Reason: {current_state.get('scout_reason', 'N/A')}
        - Consecutive Failures: {current_state.get('consecutive_failures', 0)}
        - Active URL: {current_state.get('current_url', 'N/A')}
        - Last HTTP Status: {current_state.get('last_http_status', 'N/A')}
        - Recent Agent Activity: {len(recent_logs)} logs in database
        """
        
        prompt = f"""You are "The Oracle" - an AI assistant for the Talos autonomous supply chain defense system.

TALOS SYSTEM OVERVIEW:
Talos is a multi-agent AI system that monitors supply chain vendor streams and automatically responds to disruptions.

THE AGENTS:
1. Scout Agent: Frontline monitor that watches the vendor data stream 24/7. Detects anomalies like HTTP failures, corrupted data, or zero quantities. Escalates after 3 consecutive failures.

2. Analyst Agent: The mathematician. When Scout escalates, Analyst queries the inventory database to calculate:
   - Hours until factory stockout
   - Projected financial loss in USD
   - Risk assessment summary

3. Broker Agent: The procurement officer. Evaluates backup vendors from the database based on:
   - Lead time (can they deliver before stockout?)
   - Cost per unit
   - Reliability score
   Selects optimal vendor and drafts a Purchase Order.

4. Forge Agent: The engineer. Generates the infrastructure patch to switch the system to the backup vendor's API endpoint.

HUMAN-IN-THE-LOOP GATE:
After all three agents complete their analysis, the system pauses and presents an "AUTHORIZE MITIGATION" button. The human operator must approve before the vendor switch executes. This ensures human oversight for critical supply chain decisions.

{system_context}

USER QUESTION: {body.message}

Provide a helpful, medium-length explanation (2-3 paragraphs) that answers their question. Be technical but clear. If they ask about current status, use the system state above. Keep responses focused and informative, not too brief or too verbose.

IMPORTANT: Write in plain, natural language. No markdown formatting, no backticks, no code blocks, no escape characters. Just clean, readable sentences like a human analyst would write."""

        response = chat_model.generate_content(prompt)
        reply = response.text.strip()
        
        # Clean up any markdown artifacts or escape characters
        reply = reply.replace('```', '').replace('`', '')
        reply = reply.replace('\\n', ' ').replace('\n\n', '\n')
        reply = reply.replace('**', '').replace('__', '')
        reply = ' '.join(reply.split())  # Normalize whitespace
        
        return {"response": reply}
        
    except Exception as e:
        logger.error(f"Oracle chat error: {e}")
        # Fallback response if Gemini fails
        return {"response": "The Oracle is temporarily unavailable. Please try again in a moment."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
