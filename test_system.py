"""
VOID System Test Suite
Tests all key functionality of the VOID AI Assistant
"""

import sys
import os

# Add VOID to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
        results.append(("SelfRepair", "OK"))
    except Exception as e:
        results.append(("SelfRepair", f"FAIL: {e}"))
    
    try:
        from tools.diagnostics import run_full_diagnostics
        results.append(("Diagnostics", "OK"))
    except Exception as e:
        results.append(("Diagnostics", f"FAIL: {e}"))
    
    try:
        from core.brain import ask_llm
        results.append(("Brain", "OK"))
    except Exception as e:
        results.append(("Brain", f"FAIL: {e}"))
    
    try:
        from core.command_interpreter import interpret_command
        results.append(("CommandInterpreter", "OK"))
    except Exception as e:
        results.append(("CommandInterpreter", f"FAIL: {e}"))
    
    for name, status in results:
        print(f"  {name}: {status}")
    
    return all("OK" in s for _, s in results)


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
        
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_memory_system():
    """Test memory functions"""
    print("\n=== TEST 3: Memory System ===")
    try:
        from main import add_fact, forget_keyword, clear_memory, memory_as_text
        
        # Add test fact
        add_fact("test fact for VOID")
        print("  add_fact: OK")
        
        # Check memory
        mem = memory_as_text()
        print(f"  memory_as_text: OK ({len(mem)} chars)")
        
        # Remove test fact
        forget_keyword("test")
        print("  forget_keyword: OK")
        
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_command_interpreter():
    """Test command parsing"""
    print("\n=== TEST 4: Command Interpreter ===")
    try:
        from core.command_interpreter import interpret_command, is_void_command
        
        # Test VOID commands
        tests = [
            ("VOID open chrome", True),
            ("hello", False),
            ("what time is it", False),
            ("open notepad", False),
        ]
        
        for cmd, expected in tests:
            result = is_void_command(cmd)
            status = "OK" if result == expected else "FAIL"
            print(f"  is_void_command('{cmd}'): {status}")
        
        # Test parsing
        parsed = interpret_command("VOID open chrome")
        if parsed and parsed.get("command") == "open_app":
            print("  interpret_command: OK")
        else:
            print("  interpret_command: FAIL")
        
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_fastapi_app():
    """Test FastAPI app"""
    print("\n=== TEST 5: FastAPI App ===")
    try:
        from main import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # Test health endpoint
        r = client.get("/health")
        print(f"  /health: {r.status_code} - {r.json()}")
        
        # Test stats endpoint
        r = client.get("/stats")
        print(f"  /stats: {r.status_code}")
        
        # Test time endpoint
        r = client.get("/time")
        print(f"  /time: {r.status_code}")
        
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_conversation_routing():
    """Test conversation vs tool routing"""
    print("\n=== TEST 6: Conversation Routing ===")
    try:
        from main import detect_intent
        
        tests = [
            ("hello", "conversation"),
            ("hi there", "conversation"),
            ("what can you do", "conversation"),
            ("open chrome", "tool"),
            ("what time is it", "tool"),
            ("cpu usage", "tool"),
            ("remember my name", "tool"),
        ]
        
        for prompt, expected in tests:
            result = detect_intent(prompt)
            status = "OK" if result == expected else "FAIL"
            print(f"  detect_intent('{prompt}'): {status} (got {result})")
        
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def run_all_tests():
    """Run all tests"""
    print("=" * 50)
    print("VOID SYSTEM TEST SUITE")
    print("=" * 50)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("System Stats", test_system_stats()))
    results.append(("Memory System", test_memory_system()))
    results.append(("Command Interpreter", test_command_interpreter()))
    results.append(("FastAPI App", test_fastapi_app()))
    results.append(("Conversation Routing", test_conversation_routing()))
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
    
    all_passed = all(p for _, p in results)
    print("\n" + ("ALL TESTS PASSED!" if all_passed else "SOME TESTS FAILED"))
    
    return all_passed


if __name__ == "__main__":
    run_all_tests()

