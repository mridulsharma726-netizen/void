import pytest
from fastapi.testclient import TestClient
from server.main import app, API_TOKEN
from backend.memory_manager import MemoryManager
from server.main import DATA_DIR

@pytest.fixture
def client():
    # Setup test memory clean state
    memory = MemoryManager(DATA_DIR)
    memory.clear()
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {API_TOKEN}"})
    return c

def test_system_status(client):
    # 1. "What is my current system status?"
    response = client.post("/chat", json={"message": "What is my current system status?"})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "Telemetry" in data["reply"] or "CPU" in data["reply"]
    assert data["meta"]["intent"] == "system"
    assert data["meta"]["action"] == "stats"

def test_computer_health(client):
    # 2. "Analyze my computer health."
    response = client.post("/chat", json={"message": "Analyze my computer health."})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "Health & Diagnostics" in data["reply"] or "Overall Health" in data["reply"]
    assert data["meta"]["intent"] == "system"
    assert data["meta"]["action"] == "stats"

def test_local_models_discovery(client):
    # 3. "What local AI models are installed?"
    response = client.post("/chat", json={"message": "What local AI models are installed?"})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "Models Configuration" in data["reply"]
    assert data["meta"]["action"] == "discovered-models"

def test_memory_write_and_read(client):
    # 4. "Remember that my deadline is July 10."
    response = client.post("/chat", json={"message": "Remember that my deadline is July 10."})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "stored" in data["reply"].lower()
    assert "deadline is July 10" in data["reply"]
    assert data["meta"]["action"] == "remember"

    # 5. "What is my deadline?"
    response2 = client.post("/chat", json={"message": "What is my deadline?"})
    assert response2.status_code == 200
    data2 = response2.json()
    assert "reply" in data2
    assert "july 10" in data2["reply"].lower()
    assert data2["meta"]["action"] == "recall"

def test_project_scanner(client):
    # 6. "Scan my current project."
    response = client.post("/chat", json={"message": "Scan my current project."})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "Project Scan" in data["reply"]
    assert data["meta"]["action"] == "agent_scan"

def test_project_architecture(client):
    # 7. "Explain my project architecture."
    response = client.post("/chat", json={"message": "Explain my project architecture."})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert data["meta"]["action"] == "agent_explain"

def test_show_todos(client):
    # 8. "Show all TODOs."
    response = client.post("/chat", json={"message": "Show all TODOs."})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "pending action items" in data["reply"].lower() or "todo" in data["reply"].lower()
    assert data["meta"]["action"] == "get_action_items"

def test_list_installed_models(client):
    # 9. "List installed models."
    response = client.post("/chat", json={"message": "List installed models."})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "Models Configuration" in data["reply"]
    assert data["meta"]["action"] == "discovered-models"

def test_show_memory_database(client):
    # Setup a fact first
    client.post("/chat", json={"message": "Remember that my deadline is July 10."})

    # 10. "Show memory database."
    response = client.post("/chat", json={"message": "Show memory database."})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "memory database" in data["reply"].lower()
    assert "deadline is July 10" in data["reply"]
    assert data["meta"]["action"] == "show"
