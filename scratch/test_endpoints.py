import requests
import json

API_BASE = "http://127.0.0.1:8002"
TOKEN = "531f3d7a63681c59f03673f539f539796f664e4a9ca507890e50f58fb979490a"
headers = {"Authorization": f"Bearer {TOKEN}"}

endpoints = [
    ("/health", "GET", None),
    ("/stats", "GET", None),
    ("/time", "GET", None),
    ("/system-info", "GET", None),
    ("/recommendations", "GET", None),
    ("/speak-status", "GET", None),
    ("/voice/personalities", "GET", None),
    ("/social/queue", "GET", None),
    ("/tools/health", "GET", None),
    ("/diagnostics", "GET", None),
    ("/projects/list", "GET", None),
    ("/memory/list", "GET", None),
    ("/meetings/list", "GET", None),
    ("/automation/status", "GET", None),
    ("/system/health-details", "GET", None),
    ("/academic/summary", "GET", None),
    ("/analytics/summary", "GET", None),
    ("/academic/subjects", "GET", None),
    ("/academic/curriculum", "GET", None),
    ("/academic/schedule", "GET", None),
    ("/academic/emotion", "GET", None),
    ("/cvcs/status", "GET", None),
    ("/system/ping-services", "GET", None),
    ("/gamification/xp", "GET", None),
    ("/gamification/achievements", "GET", None)
]

print("Starting endpoint verification tests...\n")

results = []
for path, method, payload in endpoints:
    url = f"{API_BASE}{path}"
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=5.0)
        else:
            r = requests.post(url, headers=headers, json=payload, timeout=5.0)
        
        status = r.status_code
        try:
            res_json = r.json()
            is_error = "error" in res_json or (isinstance(res_json, dict) and res_json.get("status") == "error")
            snippet = str(res_json)[:100] + "..." if len(str(res_json)) > 100 else str(res_json)
        except:
            is_error = False
            snippet = r.text[:100] + "..." if len(r.text) > 100 else r.text
            
        results.append({
            "endpoint": path,
            "status_code": status,
            "ok": status == 200 and not is_error,
            "response": snippet
        })
    except Exception as e:
        results.append({
            "endpoint": path,
            "status_code": "FAILED",
            "ok": False,
            "response": str(e)
        })

print(f"{'Endpoint':<35} | {'Status':<10} | {'Success':<8} | {'Response Snippet'}")
print("-" * 100)
for res in results:
    success_str = "YES" if res["ok"] else "NO"
    print(f"{res['endpoint']:<35} | {res['status_code']:<10} | {success_str:<8} | {res['response']}")
