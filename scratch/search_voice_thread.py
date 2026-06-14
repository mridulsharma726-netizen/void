with open("server/main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "_voice_thread" in line:
        print(f"Line {i+1}: {line.strip()}")
