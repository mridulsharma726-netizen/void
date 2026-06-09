import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "server"))

from server.main import evaluate_math_locally, humanize_tool_output_locally

def run_tests():
    print("--- Running Math Evaluator Tests ---")
    math_tests = [
        ("what is 25 * 4", "The calculation result is 100, Sir."),
        ("calculate (12 + 3) * 5", "The calculation result is 75, Sir."),
        ("solve 2^8", "The calculation result is 256, Sir."),
        ("compute 100 / 4", "The calculation result is 25, Sir."),
        ("what is 2.5 + 2.5", "The calculation result is 5, Sir."),
        ("what is the system stats", None),
        ("hello world", None),
        ("25", None), # single number should not evaluate as math
    ]
    
    for query, expected in math_tests:
        res = evaluate_math_locally(query)
        print(f"Query: {query!r} -> Result: {res!r} | Expected: {expected!r}")
        assert res == expected, f"Math test failed for query: {query}"
        
    print("\n--- Running Local Humanizer Tests ---")
    humanizer_tests = [
        ("time", {}, "02:30 PM | Monday, June 09, 2026", True, "The current time is 02:30 PM | Monday, June 09, 2026, Sir."),
        ("open_app", {"app": "notepad"}, "✅ Opened 'notepad'", True, "I have launched notepad for you, Sir."),
        ("close_app", {"app": "notepad"}, "✅ Closed 'notepad'", True, "I have closed notepad, Sir."),
        ("system_info", {}, "CPU: 12% | RAM: 64% | Disk: 82% | Battery: 95% | Network: Online", True, "Here is the system status, Sir:\nCPU: 12% | RAM: 64% | Disk: 82% | Battery: 95% | Network: Online"),
        ("screenshot", {}, "Screenshot captured successfully.", True, "I have successfully captured a screenshot for you, Sir."),
    ]
    
    for action, params, output, is_success, expected in humanizer_tests:
        res = humanize_tool_output_locally(action, params, output, is_success)
        print(f"Action: {action} -> Result: {res!r} | Expected: {expected!r}")
        assert res == expected, f"Humanizer test failed for action: {action}"
        
    print("\nAll tests passed successfully!")

if __name__ == "__main__":
    run_tests()
