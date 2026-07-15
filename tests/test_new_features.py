import os
import sys
import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure root dir is in path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from server.main import app, API_TOKEN

client = TestClient(app)
client.headers.update({"Authorization": f"Bearer {API_TOKEN}"})

# ==========================================
# === 1. CODE INTELLIGENCE API TESTS ===
# ==========================================

def test_code_intel_scan_invalid_path():
    """Verify scanning an invalid directory returns a 400 error."""
    response = client.post("/api/code-intel/scan", json={"path": "C:\\nonexistent_directory_xyz"})
    assert response.status_code == 400
    assert "Invalid project directory path" in response.json()["detail"]

def test_code_intel_scan_valid_path(tmp_path):
    """Verify scanning a valid directory returns AST stats and tree."""
    # Create temp repository files
    py_dir = tmp_path / "src"
    py_dir.mkdir()
    
    # Python file with docstring
    py_file = py_dir / "main.py"
    py_file.write_text('"""Main docstring"""\ndef test_fn():\n    # TODO: implement logic\n    pass\n')
    
    # JavaScript file
    js_file = py_dir / "index.js"
    js_file.write_text('// FIXME: clean this variable\nconst a = 12;\nimport foo from "bar";\n')
    
    response = client.post("/api/code-intel/scan", json={"path": str(tmp_path)})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "scan_id" in data
    assert data["project_name"] == tmp_path.name
    
    # Check stats
    stats = data["stats"]
    assert stats["total_files"] == 2
    assert stats["total_todos"] == 1
    assert stats["total_fixmes"] == 1
    assert stats["languages"]["Python"] > 0
    assert stats["languages"]["JavaScript"] > 0
    
    # Check tree structure
    tree = data["tree"]
    assert tree["name"] == tmp_path.name
    assert tree["type"] == "directory"
    assert len(tree["children"]) == 1 # 'src' directory
    
    src_node = tree["children"][0]
    assert src_node["name"] == "src"
    assert src_node["type"] == "directory"
    assert len(src_node["children"]) == 2 # main.py, index.js
    
    # Check individual file details
    files = data["files"]
    assert len(files) == 2
    py_data = next(f for f in files if f["path"].endswith("main.py"))
    assert py_data["language"] == "Python"
    assert py_data["todos"] == 1
    assert py_data["health"] == 85 # 100 - 15 points todo density penalty
    
    js_data = next(f for f in files if f["path"].endswith("index.js"))
    assert js_data["language"] == "JavaScript"
    assert js_data["todos"] == 0 # FIXME doesn't count as TODO in health
    
    # Test GET stats
    scan_id = data["scan_id"]
    stats_resp = client.get(f"/api/code-intel/stats/{scan_id}")
    assert stats_resp.status_code == 200
    assert stats_resp.json()["stats"]["total_files"] == 2
    
    # Test GET health
    health_resp = client.get(f"/api/code-intel/health/{scan_id}")
    assert health_resp.status_code == 200
    assert len(health_resp.json()["files"]) == 2


# ==========================================
# === 2. PC CONTROL HUB API TESTS ===
# ==========================================

@patch("tools.pc_control.open_app")
def test_pc_open_app(mock_open):
    """Verify open-app route routes to pc_control tool."""
    mock_open.return_value = {"status": "ok", "message": "Opening chrome"}
    response = client.post("/api/pc/open-app", json={"app_name": "chrome"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_open.assert_called_once_with("chrome")

@patch("tools.pc_control.open_url")
def test_pc_open_url(mock_open):
    """Verify open-url route routes to pc_control tool."""
    mock_open.return_value = {"status": "ok", "message": "Opening https://google.com"}
    response = client.post("/api/pc/open-url", json={"url": "google.com"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_open.assert_called_once_with("google.com")

@patch("tools.pc_control.play_youtube")
def test_pc_play_youtube(mock_play):
    """Verify play-youtube route routes to pc_control tool."""
    mock_play.return_value = {"status": "ok", "message": "Playing cats"}
    response = client.post("/api/pc/play-youtube", json={"query": "cats"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_play.assert_called_once_with("cats")

@patch("tools.pc_control.open_folder")
def test_pc_open_folder(mock_open):
    """Verify open-folder route routes to pc_control tool."""
    mock_open.return_value = {"status": "ok", "message": "Opening downloads"}
    response = client.post("/api/pc/open-folder", json={"folder_name": "downloads"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_open.assert_called_once_with("downloads")

@patch("tools.system_control.close_app")
def test_pc_close_app(mock_close):
    """Verify close-app route routes to system_control tool."""
    mock_close.return_value = {"status": "ok", "message": "Closed spotify"}
    response = client.post("/api/pc/close-app", json={"app_name": "spotify"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_close.assert_called_once_with("spotify")

@patch("tools.system_control.take_screenshot")
def test_pc_run_action_screenshot(mock_screenshot):
    """Verify screenshot utility action is routed."""
    mock_screenshot.return_value = {"status": "ok", "path": "screen.png"}
    response = client.post("/api/pc/run-action", json={"action": "screenshot"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_screenshot.assert_called_once()

@patch("tools.system_stats.get_system_stats")
def test_pc_system_info(mock_stats):
    """Verify system-info retrieves stats successfully."""
    mock_stats.return_value = {"cpu_usage": 15.0, "ram_usage": 45.0, "battery": {"percent": 98}}
    response = client.get("/api/pc/system-info")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["stats"]["cpu_usage"] == 15.0


# ==========================================
# === 3. LIVE INTELLIGENCE API TESTS ===
# ==========================================

@patch("tools.weather_control.get_weather_report")
def test_live_weather(mock_weather):
    """Verify weather details retrieval."""
    mock_weather.return_value = {"location": "Delhi", "temp_c": 32, "condition": "Sunny"}
    response = client.get("/api/live/weather?city=Delhi")
    assert response.status_code == 200
    assert response.json()["weather"]["temp_c"] == 32

@patch("tools.stocks_control.get_stock_quote")
def test_live_stocks(mock_stocks):
    """Verify stock quotes ticker details."""
    mock_stocks.return_value = {"symbol": "AAPL", "price": 182.5, "change": 1.2}
    response = client.get("/api/live/stocks?symbols=AAPL")
    assert response.status_code == 200
    assert len(response.json()["stocks"]) == 1
    assert response.json()["stocks"][0]["symbol"] == "AAPL"

def test_live_time():
    """Verify world clocks return valid string values."""
    response = client.get("/api/live/time?timezones=UTC,Asia/Kolkata")
    assert response.status_code == 200
    assert "UTC" in response.json()["times"]
    assert "Asia/Kolkata" in response.json()["times"]

@patch("search.duckduckgo_provider.get_provider")
def test_live_search(mock_provider):
    """Verify DDG web search is routed."""
    mock_instance = MagicMock()
    mock_instance.search.return_value = [{"title": "Cats", "url": "https://cats.com", "snippet": "Meow"}]
    mock_provider.return_value = mock_instance
    
    response = client.post("/api/live/search", json={"query": "cats", "max_results": 5})
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    assert response.json()["results"][0]["title"] == "Cats"


# ==========================================
# === 4. UI INTEGRATION TESTS ===
# ==========================================

def test_ui_html_integrations():
    """Verify that index.html contains the new nav-items and view elements."""
    html_path = os.path.join(ROOT_DIR, "app", "ui", "index.html")
    assert os.path.exists(html_path)
    
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    # Check Sidebar Items
    assert 'data-view="code-intel"' in html
    assert 'data-view="pc-control"' in html
    assert 'data-view="live-intel"' in html
    
    # Check Center Area views
    assert 'id="view-code-intel"' in html
    assert 'id="view-pc-control"' in html
    assert 'id="view-live-intel"' in html

def test_ui_js_integrations():
    """Verify app.js contains functions and routing cases."""
    js_path = os.path.join(ROOT_DIR, "app", "ui", "app.js")
    assert os.path.exists(js_path)
    
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()
        
    assert "loadCodeIntelView" in js
    assert "loadPCControlView" in js
    assert "loadLiveIntelView" in js
    assert "case 'code-intel':" in js
    assert "case 'pc-control':" in js
    assert "case 'live-intel':" in js

def test_ui_css_integrations():
    """Verify style.css contains new styling classes."""
    css_path = os.path.join(ROOT_DIR, "app", "ui", "style.css")
    assert os.path.exists(css_path)
    
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()
        
    assert ".code-intel-layout" in css
    assert ".pc-control-layout" in css
    assert ".live-intel-layout" in css


# ==========================================
# === 5. REGRESSION & INTEGRITY TESTS ===
# ==========================================

def test_regression_existing_navs():
    """Verify original views and nav components are unaffected."""
    html_path = os.path.join(ROOT_DIR, "app", "ui", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    original_views = [
        "dashboard", "chat", "projects", "editor", "memory", 
        "voice", "tools", "meetings", "automation", "tasks", 
        "recordings", "settings"
    ]
    
    for view in original_views:
        assert f'data-view="{view}"' in html
        assert f'id="view-{view}"' in html
