"""
main.py — Talos Command Center (FastAPI)
Phase 3: Serves the dark-mode frontend and the system state API.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import daemon
import db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the daemon on server boot
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
    
    # Check if the Forge agent specifically has finished and is pending approval
    pending_logs = db.get_pending_logs()
    state["has_pending"] = any(log.get("agent_name") == "Forge" for log in pending_logs)
    
    return state

@app.post("/api/approve_mitigation")
def approve_mitigation():
    try:
        new_url = db.execute_pending_mitigation()
        return {"status": "success", "new_url": new_url}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/reset_demo")
def reset_demo():
    try:
        db.reset_demo()
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
