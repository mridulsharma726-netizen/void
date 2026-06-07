import asyncio
import os
import sys

# Add project root and server to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from fastapi.testclient import TestClient
from server.main import app

def main():
    print("=" * 65)
    print("VOID STAGE 7 — SELF-MODIFICATION & DEV MODE INTEGRATION TEST")
    print("=" * 65)
    
    client = TestClient(app)
    
    # 1. Test Dev Mode initially status
    print("\n--- 1. Testing Default Developer Mode Status ---")
    # Reset to disabled first for testing
    from core.brain import disable_developer_mode
    disable_developer_mode()
    
    res = client.post("/chat", json={"message": "show developer mode"})
    print("Response:")
    print(res.json().get("reply"))
    assert "DISABLED" in res.json().get("reply")
    
    # 2. Test block when developer mode is off
    print("\n--- 2. Testing Blocked Action (Self-Repair when Dev Mode is OFF) ---")
    res = client.post("/chat", json={"message": "repair yourself"})
    print("Response:")
    print(res.json().get("reply"))
    assert "Action Denied" in res.json().get("reply")
    
    # 3. Enable Developer Mode
    print("\n--- 3. Enabling Developer Mode ---")
    res = client.post("/chat", json={"message": "enter developer mode"})
    print("Response:")
    print(res.json().get("reply"))
    assert "Enabled" in res.json().get("reply") or "unlocked" in res.json().get("reply").lower()
    
    # 4. Check status again
    print("\n--- 4. Verify Developer Mode is Active ---")
    res = client.post("/chat", json={"message": "developer mode status"})
    print("Response:")
    print(res.json().get("reply"))
    assert "ENABLED" in res.json().get("reply")
    
    # 5. Run self-repair when dev mode is ON
    print("\n--- 5. Executing Self-Repair workflow (Dev Mode ON) ---")
    res = client.post("/chat", json={"message": "repair yourself"})
    print("Response:")
    print(res.json().get("reply"))
    assert "Complete" in res.json().get("reply") or "healthy" in res.json().get("reply").lower()
    
    # 6. Test direct file rewrite intercept block when dev mode is off
    print("\n--- 6. Disabling Dev Mode & Verifying Block on Module Rewrite ---")
    client.post("/chat", json={"message": "exit developer mode"})
    res = client.post("/chat", json={"message": "rewrite module voice_tts"})
    print("Response:")
    print(res.json().get("reply"))
    assert "Action Denied" in res.json().get("reply")
    
    print("\n" + "=" * 65)
    print("VOID STAGE 7 DEV INTERCEPTS: ALL TESTS PASSED CLEANLY")
    print("=" * 65)

if __name__ == "__main__":
    main()
