import os
import re

dir_path = "server/backend"
pattern = re.compile(r"from\s+backend\.([a-zA-Z0-9_]+)\s+import")

for filename in os.listdir(dir_path):
    if filename.endswith(".py"):
        file_path = os.path.join(dir_path, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        new_content = pattern.sub(r"from .\1 import", content)
        
        if new_content != content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Refactored: {filename}")
