import os
import sys

# Add VOID root to path
VOID_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, VOID_ROOT)

from tools.project_intelligence import register_project

def run_tests():
    print("Testing robust path resolution...")
    
    # Test "the void project.'"
    res1 = register_project("the void project.'")
    print("Result for \"the void project.'\":", res1.get("status"), res1.get("message") if res1.get("status") == "error" else "SUCCESS")
    
    # Test '"the void project"'
    res2 = register_project('"the void project"')
    print("Result for '\"the void project\"':", res2.get("status"), res2.get("message") if res2.get("status") == "error" else "SUCCESS")

if __name__ == "__main__":
    run_tests()
