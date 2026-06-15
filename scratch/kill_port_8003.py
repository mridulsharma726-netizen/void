import os
import signal
import socket
import sys

def kill_port_8003():
    import psutil
    for conn in psutil.net_connections():
        if conn.laddr.port == 8003:
            pid = conn.pid
            if pid:
                print(f"Killing process {pid} on port 8003...")
                try:
                    p = psutil.Process(pid)
                    for child in p.children(recursive=True):
                        print(f"Killing child process {child.pid}...")
                        child.kill()
                    p.kill()
                    print(f"Killed process {pid} successfully.")
                except Exception as e:
                    print(f"Error killing process {pid}: {e}")

if __name__ == "__main__":
    kill_port_8003()
