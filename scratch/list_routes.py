with open("server/main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print("All FastAPI Routes in server/main.py:")
for i, line in enumerate(lines):
    if "@app.get" in line or "@app.post" in line or "@app.delete" in line or "@app.put" in line:
        print(f"Line {i+1}: {line.strip()}")
