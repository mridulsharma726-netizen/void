import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from server.main import app, API_TOKEN
from tools.terminal_tools import _is_command_allowed

@pytest.fixture
def client():
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {API_TOKEN}"})
    return c

def test_cors_origin_allowlist():
    # CORS Origin allowlist verification
    c = TestClient(app)
    # Origin from allowlist
    response = c.options("/health", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization"
    })
    assert response.status_code == 200 or response.status_code == 204
    assert "access-control-allow-origin" in response.headers
    
    # Origin NOT in allowlist
    response_bad = c.options("/health", headers={
        "Origin": "http://evil-site.com",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization"
    })
    assert "access-control-allow-origin" not in response_bad.headers or response_bad.headers["access-control-allow-origin"] != "http://evil-site.com"

def test_api_token_protection():
    c = TestClient(app)
    # Test endpoint without token
    response = c.post("/api/terminal/run", json={"command": "git status"})
    assert response.status_code == 403 or response.status_code == 401

    # Test with correct token
    c.headers.update({"Authorization": f"Bearer {API_TOKEN}"})
    # Since executing terminal command requires WebSocket approval, it will return wait/rejected/error, but not 403/401
    response = c.post("/api/terminal/run", json={"command": "git status"})
    assert response.status_code == 200

def test_terminal_allowlist():
    # Verify is_command_allowed logic directly
    assert _is_command_allowed("git status") is True
    assert _is_command_allowed("echo hello") is True
    assert _is_command_allowed("rm -rf /") is False
    assert _is_command_allowed("curl http://malicious.com") is False

def test_websocket_authorization():
    c = TestClient(app)
    
    # Correct token
    with c.websocket_connect(f"/ws/approval?token={API_TOKEN}") as websocket:
        # Connected successfully
        pass
        
    # Missing token
    with pytest.raises(Exception):
        with c.websocket_connect("/ws/approval") as websocket:
            pass

    # Invalid token
    with pytest.raises(Exception):
        with c.websocket_connect("/ws/approval?token=wrong_token") as websocket:
            pass
