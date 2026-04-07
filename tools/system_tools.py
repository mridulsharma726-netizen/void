import platform
import psutil
import datetime
import os
import webbrowser
import subprocess

def get_system_info():
    """Get system information: OS, processor, RAM, cores, threads."""
    info = {
        "OS": platform.system() + " " + platform.release(),
        "Processor": platform.processor(),
        "RAM": f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
        "Cores": psutil.cpu_count(logical=False),
        "Threads": psutil.cpu_count(logical=True)
    }
    return "\n".join(f"{k}: {v}" for k, v in info.items())

def get_time():
    """Get current time."""
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")

def open_app(app_name):
    """Open an application by name."""
    try:
        if platform.system() == "Windows":
            os.startfile(app_name)
        else:
            subprocess.run(["open", app_name])  # macOS
        return f"Opened {app_name}"
    except Exception as e:
        return f"Failed to open {app_name}: {e}"

def open_url(url):
    """Open a URL in default browser."""
    try:
        webbrowser.open(url)
        return f"Opened {url}"
    except Exception as e:
        return f"Failed to open {url}: {e}"

def search_web(query):
    """Search web using default browser."""
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    return open_url(url)
