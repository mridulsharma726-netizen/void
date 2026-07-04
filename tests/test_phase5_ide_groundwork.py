import os
import sys
import shutil
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from server.main import app, API_TOKEN
from tools.filesystem_control import (
    get_active_workspace,
    set_active_workspace,
    validate_path,
    list_directory,
    read_file
)
from backend.intent_router import detect_intent_and_params

@pytest.fixture
def temp_workspace(tmp_path):
    # Set up a temporary workspace directory with some test files
    ws_dir = tmp_path / "test_workspace"
    ws_dir.mkdir()
    
    # Add files/subfolders
    (ws_dir / "subfolder").mkdir()
    (ws_dir / "subfolder" / "nested.txt").write_text("Nested content", encoding="utf-8")
    (ws_dir / "hello.txt").write_text("Hello workspace!", encoding="utf-8")
    (ws_dir / "script.py").write_text("print('VOID')", encoding="utf-8")
    
    # Save original workspace preference to restore later
    from backend.memory_sqlite import get_preference
    original_ws = get_preference("active_workspace")
    
    # Set active workspace to this temp dir
    set_active_workspace(str(ws_dir))
    
    yield ws_dir
    
    # Restore original workspace preference
    if original_ws:
        set_active_workspace(original_ws)
    else:
        # Clear preference if it didn't exist
        from backend.memory_sqlite import init_db
        import sqlite3
        init_db()
        from backend.memory_sqlite import DB_FILE
        conn = sqlite3.connect(str(DB_FILE))
        try:
            conn.execute("DELETE FROM preferences WHERE key = 'active_workspace'")
            conn.commit()
        finally:
            conn.close()

def test_workspace_persistence(temp_workspace):
    # Retrieve active workspace and verify it matches the temp dir
    current_ws = get_active_workspace()
    assert current_ws.resolve() == temp_workspace.resolve()

def test_path_validation_and_traversal(temp_workspace):
    # Safe path inside workspace
    safe_path = temp_workspace / "hello.txt"
    resolved = validate_path("hello.txt")
    assert resolved.resolve() == safe_path.resolve()
    
    # Safe nested path
    safe_nested = temp_workspace / "subfolder" / "nested.txt"
    resolved_nested = validate_path("subfolder/nested.txt")
    assert resolved_nested.resolve() == safe_nested.resolve()
    
    # Traversal attempt: absolute path outside workspace
    outside_abs_path = os.path.abspath(os.path.join(str(temp_workspace), "..", "secret.txt"))
    with pytest.raises(ValueError) as exc:
        validate_path(outside_abs_path)
    assert "Access Denied" in str(exc.value)
    
    # Traversal attempt: relative parent escape (../)
    with pytest.raises(ValueError) as exc:
        validate_path("../hello.txt")
    assert "Access Denied" in str(exc.value)
    
    # Traversal attempt: complex parent path segments
    with pytest.raises(ValueError) as exc:
        validate_path("subfolder/../../hello.txt")
    assert "Access Denied" in str(exc.value)

def test_list_directory_and_read_file(temp_workspace):
    # Test secure list_directory
    res_list = list_directory(".")
    assert res_list["status"] == "ok"
    assert res_list["path"] == "."
    
    file_names = {f["name"] for f in res_list["files"]}
    assert "hello.txt" in file_names
    assert "script.py" in file_names
    assert "subfolder" in file_names
    
    # Test listing nested directory
    res_list_nested = list_directory("subfolder")
    assert res_list_nested["status"] == "ok"
    assert res_list_nested["path"] == "subfolder"
    assert res_list_nested["files"][0]["name"] == "nested.txt"
    
    # Test secure read_file
    res_read = read_file("hello.txt")
    assert res_read["status"] == "ok"
    assert res_read["content"] == "Hello workspace!"
    
    # Test reading nested file
    res_read_nested = read_file("subfolder/nested.txt")
    assert res_read_nested["status"] == "ok"
    assert res_read_nested["content"] == "Nested content"

def test_workspace_api_endpoints(temp_workspace):
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {API_TOKEN}"})
    
    # GET /api/workspace/get
    r = client.get("/api/workspace/get")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["path"] == str(temp_workspace.resolve())
    
    # POST /api/workspace/files/list
    r = client.post("/api/workspace/files/list", json={"path": "."})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert any(f["name"] == "hello.txt" for f in r.json()["files"])
    
    # POST /api/workspace/files/read
    r = client.post("/api/workspace/files/read", json={"path": "hello.txt"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["content"] == "Hello workspace!"
    
    # POST /api/workspace/files/read traversal rejection
    r = client.post("/api/workspace/files/read", json={"path": "../secret.txt"})
    assert r.status_code == 200
    assert r.json()["status"] == "error"
    assert "Access Denied" in r.json()["message"]

def test_router_hooks_classification():
    # 1. open_file / read_file
    res = detect_intent_and_params("open hello.txt")
    assert res["intent"] == "open_file"
    assert res["parameters"]["path"] == "hello.txt"
    
    res = detect_intent_and_params("view file script.py")
    assert res["intent"] == "open_file"
    assert res["parameters"]["path"] == "script.py"
    
    # 2. list_directory
    res = detect_intent_and_params("list the directory subfolder")
    assert res["intent"] == "list_directory"
    assert res["parameters"]["path"] == "subfolder"
    
    res = detect_intent_and_params("show folder")
    assert res["intent"] == "list_directory"
