with open("app/ui/app.js", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "health-details" in line:
        print(f"Line {i+1}: {line.strip()}")
