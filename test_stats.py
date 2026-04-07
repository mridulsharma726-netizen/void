from tools.system_stats import SystemStats

s = SystemStats()
stats = s.get_all_stats(use_cache=False)

print("=== System Stats Test ===")
print(f"cpu_usage: {stats.get('cpu_usage')}")
print(f"cpu_temp: {stats.get('cpu_temp')}")
print(f"gpu_usage: {stats.get('gpu_usage')}")
print(f"gpu_temp: {stats.get('gpu_temp')}")
print(f"ram_usage: {stats.get('ram_usage')}")
print(f"ram_used_gb: {stats.get('ram_used_gb')}")
print(f"ram_total_gb: {stats.get('ram_total_gb')}")
print(f"storage_used_gb: {stats.get('storage_used_gb')}")
print(f"storage_total_gb: {stats.get('storage_total_gb')}")
print(f"battery_percent: {stats.get('battery_percent')}")

