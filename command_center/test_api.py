import traceback
import main
import db
from fastapi.testclient import TestClient

client = TestClient(main.app)

try:
    with client:
        # Insert a fake log
        db.log_agent_event("Scout", "Executed", {"test": "data"})
        
        # Test endpoint
        res = client.get("/api/system_state")
        print("STATUS:", res.status_code)
        if res.status_code != 200:
            print("BODY:", res.text)
except Exception as e:
    print("CAUGHT EXCEPTION:")
    traceback.print_exc()
