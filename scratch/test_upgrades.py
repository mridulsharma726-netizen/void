import sys
import os
import time
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "server"))

from backend.llm_client import OllamaClient
from tools.voice_stt import VoiceSTT

def test_dynamic_options():
    print("=== Testing Dynamic LLM Client Options ===")
    client = OllamaClient()
    
    # Test cases: (query, expected_temp, expected_predict, expected_ctx)
    test_cases = [
        ("write a short story about an astronaut looking back at Earth", 0.85, 1024, 4096),
        ("Compose a beautiful poem about code", 0.85, 1024, 4096),
        ("A farmer needs to cross a river with a fox, a goose, and a bag of beans. Solve this step by step.", 0.15, 1024, 4096),
        ("Here is a logic puzzle: A B and C lie or tell truth. Explain the solution.", 0.15, 1024, 4096),
        ("What time is it?", 0.5, 512, 2048),
        ("Hello VOID!", 0.5, 512, 2048)
    ]
    
    all_ok = True
    for query, temp, predict, ctx in test_cases:
        opts = client._get_dynamic_options(query)
        passed = (
            abs(opts.get("temperature", 0.0) - temp) < 0.01 and
            opts.get("num_predict") == predict and
            opts.get("num_ctx") == ctx
        )
        status = "PASS" if passed else "FAIL"
        print(f"Query: '{query[:45]}...' -> Temp={opts.get('temperature')}, Predict={opts.get('num_predict')}, Ctx={opts.get('num_ctx')} [{status}]")
        if not passed:
            all_ok = False
            
    return all_ok

def test_background_emotion():
    print("\n=== Testing Background Emotion Threading ===")
    stt = VoiceSTT()
    
    # Check that calling _analyze_and_process_emotion does not fail
    try:
        # Dummy audio data
        dummy_audio = bytes([0] * 32000) # 1 second
        print("Invoking _analyze_and_process_emotion...")
        stt._analyze_and_process_emotion("hello", dummy_audio, duration=1.0)
        print("Function call complete (passed).")
        return True
    except Exception as e:
        print(f"Failed with exception: {e}")
        return False

if __name__ == "__main__":
    passed_opts = test_dynamic_options()
    passed_emotion = test_background_emotion()
    
    if passed_opts and passed_emotion:
        print("\nALL UPGRADE TESTS PASSED!")
        sys.exit(0)
    else:
        print("\nSOME UPGRADE TESTS FAILED.")
        sys.exit(1)
