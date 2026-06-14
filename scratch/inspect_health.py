with open("server/main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '@app.get("/tools/health")' in line:
        print(f"Line {i+1} for tools health:")
        for j in range(max(0, i-2), min(len(lines), i+25)):
            print(f"{j+1}: {lines[j]}", end="")
    if '@app.get("/system/health-details")' in line:
        print(f"\nLine {i+1} for system health-details:")
        for j in range(max(0, i-2), min(len(lines), i+80)):
            print(f"{j+1}: {lines[j]}", end="")
