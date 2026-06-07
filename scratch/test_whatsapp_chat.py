import json
import requests
import os

config_path = r"c:\Users\HP\OneDrive\Desktop\void\VOID\memory\data\secure_config.json"

if not os.path.exists(config_path):
    print("secure_config.json not found!")
    exit(1)

with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)

token = config.get("api_token", "")
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

payload = {"message": "send a whatsapp message to bhavya canada saying hello"}

print("Sending request to VOID backend...")
response = requests.post("http://127.0.0.1:8002/chat", headers=headers, json=payload)
print(f"Status Code: {response.status_code}")
print("Response JSON:")
print(json.dumps(response.json(), indent=2))
