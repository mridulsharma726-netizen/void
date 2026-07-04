import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from server.main import app, API_TOKEN

def test_automation_status_dynamic():
    """Verify that /automation/status reflects the dynamic state of services."""
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {API_TOKEN}"})
    
    # Mock SystemMetricsCollector.get_services_status to return stopped wake word
    mock_svc = {
        "backend": "running",
        "project_monitor": "stopped",
        "wake_word": "stopped"
    }
    
    with patch("server.backend.metrics_service.SystemMetricsCollector.get_services_status", return_value=mock_svc):
        r = client.get("/automation/status")
        assert r.status_code == 200
        res = r.json()
        
        active = res["active_workflows"]
        
        # Verify status mapping
        sys_diag = next(x for x in active if x["id"] == "sys_diag")
        assert sys_diag["status"] == "Running"
        
        cvcs_scan = next(x for x in active if x["id"] == "cvcs_scan")
        assert cvcs_scan["status"] == "Stopped"
        
        voice_wake = next(x for x in active if x["id"] == "voice_wake")
        assert voice_wake["status"] == "Stopped"
        assert voice_wake["trigger"] == "--"

def test_social_scheduler_option_a_relabel():
    """Verify that Option A labels (drafts, not live post) are returned by the endpoints."""
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {API_TOKEN}"})
    
    # Test schedule (draft creation) response
    payload = {
        "platform": "Twitter/X",
        "content": "This is a test draft content",
        "scheduled_time": "2026-07-05T12:00:00"
    }
    
    # Mock connection to avoid sqlite insertion during test or let it run
    # Let's mock the sqlite operation to keep it isolated
    with patch("core.integrations.social_manager.get_connection") as mock_conn:
        r = client.post("/social/schedule", json=payload)
        assert r.status_code == 200
        assert "Successfully saved draft for Twitter/X" in r.json()["message"]
        
        # Test execute (mark as posted) response
        r2 = client.post("/social/post/42")
        assert r2.status_code == 200
        assert "Post 42 draft marked as posted in your queue" in r2.json()["message"]
