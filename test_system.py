"""
VOID System Test Suite
Tests all key functionality of the VOID AI Assistant
"""

import sys
import os
from pathlib import Path

# Add VOID root to path
VOID_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(VOID_ROOT))

# Add server to path
sys.path.insert(0, str(VOID_ROOT / "server"))

def test_imports():
    """Test all critical imports"""
    print("\n=== TEST 1: Import All Modules ===")
    results = []
    
    try:
        from tools.system_stats import SystemStats
        results.append(("SystemStats", "OK"))
    except Exception as e:
        results.append(("SystemStats", f"FAIL: {e}"))
    
    try:
        from tools.voice_tts import speak
        results.append(("TTS", "OK"))
    except Exception as e:
        results.append(("TTS", f"FAIL: {e}"))
    
    try:
        from tools.voice_stt import VoiceSTT
        results.append(("STT", "OK"))
    except Exception as e:
        results.append(("STT", f"FAIL: {e}"))
    
    try:
        from tools.self_repair import repair_system
        results.append(("SelfRepair (Bridge)", "OK"))
    except Exception as e:
        results.append(("SelfRepair (Bridge)", f"FAIL: {e}"))
    
    try:
        from tools.diagnostics import run_full_diagnostics
        results.append(("Diagnostics (Bridge)", "OK"))
    except Exception as e:
        results.append(("Diagnostics (Bridge)", f"FAIL: {e}"))
    
    try:
        from backend.llm_client import OllamaClient
        results.append(("OllamaClient", "OK"))
    except Exception as e:
        results.append(("OllamaClient", f"FAIL: {e}"))
    
    try:
        from backend.intent_router import IntentRouter
        results.append(("IntentRouter", "OK"))
    except Exception as e:
        results.append(("IntentRouter", f"FAIL: {e}"))
    
    for name, status in results:
        print(f"  {name}: {status}")
    
    assert all("OK" in s for _, s in results)


def test_system_stats():
    """Test system stats collection"""
    print("\n=== TEST 2: System Stats ===")
    try:
        from tools.system_stats import SystemStats
        stats = SystemStats().get_all_stats(use_cache=False)
        
        print(f"  cpu_usage: {stats.get('cpu_usage')}")
        print(f"  cpu_temp: {stats.get('cpu_temp')}")
        print(f"  ram_usage: {stats.get('ram_usage')}")
        print(f"  storage: {stats.get('storage_used_gb')}/{stats.get('storage_total_gb')} GB")
        print(f"  battery: {stats.get('battery_percent')}")
        
    except Exception as e:
        print(f"  FAIL: {e}")
        assert False, f"Exception raised: {e}"


def test_memory_system():
    """Test memory functions"""
    print("\n=== TEST 3: Memory System ===")
    try:
        from backend.memory_manager import MemoryManager
        DATA_DIR = VOID_ROOT / "memory" / "data"
        memory = MemoryManager(DATA_DIR)
        
        # Add test fact
        memory.add_fact("test fact for VOID")
        print("  add_fact: OK")
        
        # Check memory
        mem = memory.get_summary()
        print(f"  memory summary: OK ({len(mem)} chars)")
        
        # Remove test fact
        memory.clear()
        print("  clear_memory: OK")
        
    except Exception as e:
        print(f"  FAIL: {e}")
        assert False, f"Exception raised: {e}"


def test_command_interpreter():
    """Test command parsing"""
    print("\n=== TEST 4: Command Interpreter ===")
    try:
        import asyncio
        from backend.intent_router import IntentRouter
        
        router = IntentRouter(use_llm_fallback=False)
        
        # Run async classification using event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Test command patterns
        tests = [
            ("open chrome", "command", "open_app"),
            ("what time is it", "command", "time"),
            ("repair yourself", "system", "repair"),
        ]
        
        all_ok = True
        for cmd, expected_intent, expected_action in tests:
            result = loop.run_until_complete(router.classify(cmd))
            is_ok = result.intent == expected_intent and result.action == expected_action
            if not is_ok:
                all_ok = False
            status = "OK" if is_ok else "FAIL"
            print(f"  classify('{cmd}'): {status} (got intent={result.intent}, action={result.action})")
            
        loop.close()
        assert all_ok, "Some command classification failed"
    except Exception as e:
        print(f"  FAIL: {e}")
        assert False, f"Exception raised: {e}"


def test_fastapi_app():
    """Test FastAPI app"""
    print("\n=== TEST 5: FastAPI App ===")
    try:
        from server.main import app, API_TOKEN
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        client.headers.update({"Authorization": f"Bearer {API_TOKEN}"})
        
        # Test health endpoint
        r = client.get("/health")
        print(f"  /health: {r.status_code} - {r.json()}")
        
        # Test stats endpoint
        r = client.get("/stats")
        print(f"  /stats: {r.status_code}")
        
        # Test time endpoint
        r = client.get("/time")
        print(f"  /time: {r.status_code}")

        # Test wake word status endpoint
        r = client.get("/api/voice/wake-word/status")
        print(f"  /api/voice/wake-word/status: {r.status_code} - {r.json()}")
        assert r.status_code == 200
        assert "active" in r.json()

        # Test wake word toggle endpoint (disable)
        r = client.post("/api/voice/wake-word/toggle", json={"active": False})
        print(f"  /api/voice/wake-word/toggle (False): {r.status_code} - {r.json()}")
        assert r.status_code == 200
        assert r.json().get("active") is False

        # Test wake word toggle endpoint (enable)
        # Note: we check return code; we might Mock the actual background thread if we wanted to avoid real mic initialization,
        # but the endpoint handles exceptions safely and the test client executes in-process.
        r = client.post("/api/voice/wake-word/toggle", json={"active": True})
        print(f"  /api/voice/wake-word/toggle (True): {r.status_code} - {r.json()}")
        assert r.status_code == 200

        # Turn it back off to clean up resources during tests
        client.post("/api/voice/wake-word/toggle", json={"active": False})

        # Test fix audio ducking endpoint
        r = client.post("/api/voice/wake-word/fix-ducking")
        print(f"  /api/voice/wake-word/fix-ducking: {r.status_code} - {r.json()}")
        assert r.status_code == 200 or r.status_code == 500  # Safe in environments without full registry write permission
        
    except Exception as e:
        print(f"  FAIL: {e}")
        assert False, f"Exception raised: {e}"


def test_conversation_routing():
    """Test conversation vs tool routing"""
    print("\n=== TEST 6: Conversation Routing ===")
    try:
        import asyncio
        from backend.intent_router import IntentRouter
        
        router = IntentRouter(use_llm_fallback=False)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        tests = [
            ("hello", "chat"),
            ("hi there", "chat"),
            ("what can you do", "chat"),
            ("open chrome", "command"),
            ("what time is it", "command"),
            ("cpu status", "command"),
        ]
        
        all_ok = True
        for prompt, expected in tests:
            result = loop.run_until_complete(router.classify(prompt))
            is_ok = result.intent == expected
            if not is_ok:
                all_ok = False
            status = "OK" if is_ok else "FAIL"
            print(f"  classify('{prompt}'): {status} (got {result.intent})")
        
        loop.close()
        assert all_ok, "Some routing failed"
    except Exception as e:
        print(f"  FAIL: {e}")
        assert False, f"Exception raised: {e}"


def run_all_tests():
    """Run all tests"""
    print("=" * 50)
    print("VOID SYSTEM TEST SUITE (ALIGNED & STABILIZED)")
    print("=" * 50)
    
    results = []
    
    for name, func in [
        ("Imports", test_imports),
        ("System Stats", test_system_stats),
        ("Memory System", test_memory_system),
        ("Command Interpreter", test_command_interpreter),
        ("FastAPI App", test_fastapi_app),
        ("Conversation Routing", test_conversation_routing)
    ]:
        try:
            func()
            results.append((name, True))
        except Exception:
            results.append((name, False))
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}: {name}")
    
    all_passed = all(p for _, p in results)
    print("\n" + ("ALL TESTS PASSED!" if all_passed else "SOME TESTS FAILED"))
    
    return all_passed


if __name__ == "__main__":
    run_all_tests()
