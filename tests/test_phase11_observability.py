import os
import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
if str(ROOT_DIR / "server") not in sys.path:
    sys.path.append(str(ROOT_DIR / "server"))

from server.main import app

class TestPhase11Observability(unittest.TestCase):
    
    def test_prometheus_metrics_endpoint(self):
        """Verify `/metrics` endpoint returns Prometheus-formatted data."""
        client = TestClient(app)
        response = client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        
        # Verify content type is prometheus-compatible text format
        self.assertIn("text/plain", response.headers["content-type"])
        
        # Verify some standard metrics headers are present
        body = response.text
        self.assertIn("# HELP void_chat_latency_seconds", body)
        self.assertIn("# TYPE void_chat_latency_seconds", body)
        self.assertIn("# HELP void_chat_requests_total", body)
        self.assertIn("# TYPE void_chat_requests_total", body)

if __name__ == "__main__":
    unittest.main()
