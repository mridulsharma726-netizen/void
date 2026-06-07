import threading
import uiautomation as auto
import ctypes

def task():
    try:
        # Initialize COM
        ctypes.windll.ole32.CoInitialize(None)
        print("COM Initialized!")
        
        # Test finding WhatsApp window
        win = auto.WindowControl(searchDepth=1, Name="WhatsApp")
        exists = win.Exists(0.1)
        print(f"WhatsApp exists? {exists}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        ctypes.windll.ole32.CoUninitialize()
        print("COM Uninitialized!")

t = threading.Thread(target=task)
t.start()
t.join()
