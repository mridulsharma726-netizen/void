import os
import sys
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from server.main import app, API_TOKEN
from server.backend.providers.ollama_local import OllamaProvider
from server.backend.providers.router import MultiModelRouter
from server.backend.metrics_service import SystemMetricsCollector
from server.backend.deep_research import SourceCollector, EvidenceAnalyzer, ResearchMemory, CitationManager

def test_metrics_service_db_and_monitor():
    collector = SystemMetricsCollector()
    stats = collector.get_memory_statistics()
    assert "database_size_bytes" in stats
    
    services = collector.get_services_status()
    assert "project_monitor" in services
    assert services["project_monitor"] in ["running", "stopped"]

def test_recent_activity_endpoint():
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {API_TOKEN}"})
    
    r = client.get("/api/dashboard/recent-activity")
    assert r.status_code == 200
    res_data = r.json()
    assert isinstance(res_data, list)
    assert len(res_data) > 0
    assert "time" in res_data[0]
    assert "event" in res_data[0]
    assert "status" in res_data[0]

def test_ollama_truncation():
    provider = OllamaProvider(model="qwen2.5:0.5b")
    history = [
        {"role": "user", "content": "hello " * 2000},
        {"role": "assistant", "content": "hi " * 2000}
    ]
    prompt = "how are you?"
    pruned, clean_prompt = provider._truncate_to_context_limit(history, prompt, "system prompt", 4096)
    assert len(pruned) < len(history)
    assert clean_prompt == prompt

@pytest.mark.anyio
async def test_ollama_error_handling():
    provider = OllamaProvider(model="qwen2.5:0.5b")
    import requests
    with patch("requests.post", side_effect=requests.exceptions.Timeout("Connection timed out")):
        with pytest.raises(asyncio.TimeoutError):
            await provider.chat([], "test prompt")

@pytest.mark.anyio
async def test_chat_sync_executor():
    router = MultiModelRouter()
    mock_prov = MagicMock()
    
    # We must patch the async chat method to return a coroutine
    async def dummy_chat(history, prompt, system_prompt=None):
        return "Mocked chat response"
    mock_prov.chat = dummy_chat
    
    with patch.object(router, "select_provider_and_model", return_value=("Local", mock_prov, "qwen2.5:0.5b", "reason")):
        res = router.chat_sync([], "sync prompt")
        assert res == "Mocked chat response"

@pytest.mark.anyio
async def test_query_decomposition_deep_research():
    memory = ResearchMemory()
    citation = CitationManager()
    collector = SourceCollector(memory, citation)
    
    # Mock OllamaClient.chat to return decomposed queries
    async def dummy_chat(history, prompt, system_prompt=None):
        return "query 1\nquery 2\nquery 3"
    
    async def mock_progress(msg, speak_msg=None):
        pass
        
    with patch("server.backend.providers.ollama_local.OllamaProvider.chat", dummy_chat):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<div class="result"><a class="result__url" href="https://example.com/url1">title1</a><a class="result__snippet">snippet1</a></div>'
        
        with patch("requests.get", return_value=mock_resp):
            sources = await collector.collect_sources("decomposed query test", mock_progress)
            assert len(sources) > 0
            assert sources[0]["url"] == "https://example.com/url1"
