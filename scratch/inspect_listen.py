with open("server/main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '@app.get("/listen")' in line:
        print(f"Line {i+1}:")
        for j in range(max(0, i-2), min(len(lines), i+30)):
            print(f"{j+1}: {lines[j]}", end="")
