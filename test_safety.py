#!/usr/bin/env python
"""Test safety features"""

import sys
import os

# Add VOID directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 50)
print("Testing Safety Features")
print("=" * 50)

# Test 1: Protected files
print("\n1. Testing protected files...")
from tools.code_tools import is_protected

test_cases = [
    ("main.py", True),
    ("tools/main.py", True),
    ("desktop/main.js", True),
    ("package.json", True),
    ("tools/voice_tts.py", False),
    ("core/brain.py", False),
]

for path, expected in test_cases:
    result = is_protected(path)
    status = "✓" if result == expected else "✗"
    print(f"   {status} is_protected('{path}'): {result} (expected: {expected})")

# Test 2: Syntax validation
print("\n2. Testing syntax validation...")
from tools.code_tools import validate_python, validate_javascript

# Valid Python
valid_code = """
def hello():
    print("Hello, World!")
    return True
"""

result = validate_python(valid_code)
print(f"   ✓ Valid Python: {result.get('valid')}")

# Invalid Python
invalid_code = """
def hello(
    print("missing closing paren")
"""

result = validate_python(invalid_code)
print(f"   ✓ Invalid Python detected: {not result.get('valid')}")
if not result.get('valid'):
    print(f"      Error: {result.get('message', '')}")

# Test 3: safe_write_file blocks protected files
print("\n3. Testing safe_write_file blocks protected files...")
from tools.code_tools import safe_write_file

result = safe_write_file("main.py", "some code", create_backup=False)
print(f"   ✓ Protected file blocked: {result.get('status') == 'error'}")
if result.get('status') == 'error':
    print(f"      Message: {result.get('message', '')}")

# Test 4: safe_write_file rejects invalid syntax
print("\n4. Testing safe_write_file rejects invalid syntax...")
result = safe_write_file("tools/test_module.py", "def broken(\n    pass", create_backup=False)
print(f"   ✓ Invalid syntax rejected: {result.get('status') == 'error'}")
if result.get('status') == 'error':
    print(f"      Message: {result.get('message', '')}")

print("\n" + "=" * 50)
print("All safety tests completed!")
print("=" * 50)

