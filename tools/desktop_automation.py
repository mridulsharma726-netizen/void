import os
import shutil
import logging
import ctypes
import pyautogui
from typing import Dict, Any, Optional, List

logger = logging.getLogger("void.desktop_automation")

# win32 constants
SW_RESTORE = 9

def get_active_window_title() -> str:
    """Read foreground window title using native User32."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                return buffer.value.strip()
    except Exception as e:
        logger.error(f"Failed to read foreground window title: {e}")
    return "Unknown Window"

def switch_to_window(title_query: str) -> bool:
    """Switch focus to visible window containing query string."""
    try:
        from tools.window_helper import get_visible_windows
        user32 = ctypes.windll.user32
        visible = get_visible_windows()
        for w in visible:
            if title_query.lower() in w["title"].lower():
                hwnd = w["hwnd"]
                if user32.IsIconic(hwnd):
                    user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
                return True
    except Exception as e:
        logger.error(f"Failed to switch to window '{title_query}': {e}")
    return False

def read_clipboard() -> str:
    """Read text content from Windows Clipboard with tkinter fallback."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        # Configure ctypes to avoid 64-bit truncation
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = ctypes.c_void_p
        
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        
        if not user32.OpenClipboard(0):
            raise RuntimeError("Could not open clipboard")
            
        data = ""
        try:
            handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
            if handle:
                ptr = kernel32.GlobalLock(handle)
                if ptr:
                    try:
                        data = ctypes.wstring_at(ptr)
                    finally:
                        kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
        if data:
            return data
    except Exception:
        pass

    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        data = root.clipboard_get()
        root.destroy()
        return data
    except Exception:
        return ""

def write_clipboard(text: str) -> bool:
    """Write text content to Windows Clipboard with tkinter fallback."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        # Configure ctypes to avoid 64-bit truncation
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        
        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = wintypes.BOOL
        
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        
        user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        
        if not user32.OpenClipboard(0):
            raise RuntimeError("Could not open clipboard")
            
        try:
            user32.EmptyClipboard()
            count = len(text) + 1
            h_mem = kernel32.GlobalAlloc(0x0002, count * 2)  # GMEM_MOVEABLE
            if not h_mem:
                raise RuntimeError("GlobalAlloc failed")
                
            p_mem = kernel32.GlobalLock(h_mem)
            if p_mem:
                try:
                    # Map the pointer to a wchar array and assign the string value
                    buf = (ctypes.c_wchar * count).from_address(p_mem)
                    buf.value = text
                finally:
                    kernel32.GlobalUnlock(h_mem)
            
            user32.SetClipboardData(13, h_mem)
        finally:
            user32.CloseClipboard()
        return True
    except Exception:
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            root.destroy()
            return True
        except Exception:
            return False

def rename_file(old_path: str, new_path: str) -> Dict[str, Any]:
    """Rename a file or folder."""
    try:
        os.rename(old_path, new_path)
        return {"status": "ok", "message": f"Successfully renamed '{old_path}' to '{new_path}', Sir."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def move_file(source: str, destination: str) -> Dict[str, Any]:
    """Move a file or folder."""
    try:
        shutil.move(source, destination)
        return {"status": "ok", "message": f"Successfully moved '{source}' to '{destination}', Sir."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def delete_file_gated(path: str) -> Dict[str, Any]:
    """Delete a file or folder with user approval gate."""
    try:
        from backend.fs_tools import request_approval
        approved = await request_approval("delete_file", path, "This is a potentially destructive action, Sir.")
        if not approved:
            return {"status": "error", "message": "File deletion request denied by user, Sir."}
        
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return {"status": "ok", "message": f"File '{path}' deleted successfully, Sir."}
    except Exception as e:
        return {"status": "error", "message": f"Deletion failed: {e}"}

def simulate_keyboard(text: str, hotkey: Optional[str] = None) -> Dict[str, Any]:
    """Simulate keyboard presses or type values."""
    try:
        if hotkey:
            keys = [k.strip().lower() for k in hotkey.split("+")]
            pyautogui.hotkey(*keys)
            return {"status": "ok", "message": f"Hotkeys '{hotkey}' simulated."}
        else:
            pyautogui.write(text, interval=0.01)
            return {"status": "ok", "message": f"Simulated text input: '{text}'."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def simulate_mouse(action: str, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
    """Simulate mouse actions (click, move, right_click)."""
    try:
        act = action.lower().strip()
        if x is not None and y is not None:
            pyautogui.moveTo(x, y)
        
        if act == "click":
            pyautogui.click()
        elif act == "right_click":
            pyautogui.rightClick()
        elif act == "double_click":
            pyautogui.doubleClick()
            
        return {"status": "ok", "message": f"Simulated mouse action: {act}."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
