import sys
import time
import subprocess
import requests
from pathlib import Path

# Add project root and server to path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "server"))

from server.main import get_or_generate_api_token

def test_logging():
    token = get_or_generate_api_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    cmd = [
        sys.executable, "-m", "uvicorn",
        "server.main:app",
        "--host", "127.0.0.1",
        "--port", "8003"
    ]
    
    print("Starting test VOID server on port 8003...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    # Poll health endpoint for up to 25 seconds
    health_ok = False
    for i in range(25):
        try:
            r = requests.get("http://127.0.0.1:8003/health", timeout=1)
            if r.status_code == 200:
                health_ok = True
                print("Server is up and healthy!")
                break
        except Exception:
            pass
        time.sleep(1)
        
    if not health_ok:
        print("Server failed to start up within 25 seconds.")
        proc.terminate()
        sys.exit(1)
    
    try:
        payload = {"message": "what is 25 * 4"}
        print("Sending chat request 'what is 25 * 4'...")
        r = requests.post("http://127.0.0.1:8003/chat", json=payload, headers=headers, timeout=5)
        print(f"Server response: {r.status_code} | {r.json()}")
        
        # Shutdown server
        proc.terminate()
        proc.wait(timeout=5)
        
        stdout_content = proc.stdout.read()
        print("\n--- Captured Server Output ---")
        print(stdout_content)
        print("------------------------------")
        
        # Verify execution log presence
        assert "--- Chat Request Execution Log ---" in stdout_content, "Missing execution log header"
        assert "Intent Detected: math_calculation" in stdout_content, "Incorrect or missing intent log"
        assert "Execution Path: DIRECT_TOOL" in stdout_content, "Incorrect or missing execution path log"
        assert "Tool Used: math_evaluator" in stdout_content, "Incorrect or missing tool log"
        assert "Success or Failure: Success" in stdout_content, "Incorrect or missing status log"
        
        print("\nLog verification passed successfully!")
    except Exception as e:
        proc.terminate()
        proc.kill()
        print(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_logging()
