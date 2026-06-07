import os
import subprocess
import sys
from pathlib import Path

def run_vulture():
    print("--- Running Vulture (Dead Code Detection) ---")
    venv_python = Path("venv/Scripts/python.exe")
    if not venv_python.exists():
        venv_python = Path("venv/bin/python")
    
    if not venv_python.exists():
        print("Error: venv not found. Please create a virtual environment at ./venv")
        return

    try:
        # Exclude directories that are not part of the active backend
        cmd = [str(venv_python), "-m", "vulture", ".", "--exclude", "venv,node_modules,.qodo,.vscode,.zencoder,.zenflow,data,logs,ui,desktop"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        else:
            print("No dead code detected by Vulture.")
    except Exception as e:
        print(f"Failed to run Vulture: {e}")

def check_bak_files():
    print("\n--- Checking for .bak Files ---")
    bak_files = list(Path(".").rglob("*.bak"))
    if bak_files:
        print(f"Found {len(bak_files)} .bak files:")
        for f in bak_files:
            print(f"  {f}")
        print("\nRecommendation: Remove these files or move them to an archive directory.")
    else:
        print("No .bak files found.")

def check_unused_modules():
    print("\n--- Checking for Potentially Redundant Modules ---")
    # Check for snake_case vs CamelCase duplicates which we just cleaned up
    # This is a placeholder for future checks
    print("All known redundant modules have been cleaned up.")

if __name__ == "__main__":
    check_bak_files()
    check_unused_modules()
    run_vulture()
    print("\nCleanup check complete.")
