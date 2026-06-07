import ctypes
import logging
import time
import subprocess
from typing import Dict, Any, List, Tuple
from pathlib import Path

logger = logging.getLogger("void.window_helper")

# Win32 Constants
SW_MAXIMIZE = 3
SW_MINIMIZE = 6
SW_RESTORE = 9
GWL_STYLE = -16
WS_VISIBLE = 0x10000000
WS_EX_TOOLWINDOW = 0x00000080

# Load User32
user32 = ctypes.windll.user32

def get_screen_resolution() -> Tuple[int, int]:
    """Retrieve primary monitor resolution."""
    width = user32.GetSystemMetrics(0)
    height = user32.GetSystemMetrics(1)
    return width, height

def get_visible_windows() -> List[Dict[str, Any]]:
    """Walk all open, visible top-level windows with non-empty titles."""
    windows = []
    
    # Callback prototype
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    
    def enum_callback(hwnd, lParam):
        # Filter: Must be visible and not a tool window
        if user32.IsWindowVisible(hwnd):
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            ex_style = user32.GetWindowLongW(hwnd, -20)
            
            # Skip hidden, child, or tool windows
            if not (ex_style & WS_EX_TOOLWINDOW):
                # Retrieve title length
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value.strip()
                    
                    # Exclude standard shell, taskbar, or system overlays
                    exclusions = ["Program Manager", "Start", "Windows Input Experience", "Settings"]
                    if title and title not in exclusions:
                        windows.append({
                            "hwnd": hwnd,
                            "title": title
                        })
        return True
        
    user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
    return windows

def arrange_windows(layout: str) -> Dict[str, Any]:
    """
    Arrange visible windows dynamically into layout formats.
    Supported: 'side-by-side' (split), 'tile' (grid), 'cascade', 'maximize-all'.
    """
    try:
        visible = get_visible_windows()
        # Exclude our own Electron interface or specific backend items if visible
        visible = [w for w in visible if "void" not in w["title"].lower()]
        
        if not visible:
            return {"status": "ok", "message": "There are no active, visible windows to arrange, Sir."}
            
        screen_w, screen_h = get_screen_resolution()
        # Reserve bottom taskbar height approx 40px
        usable_h = screen_h - 50
        
        count = len(visible)
        
        if layout == "maximize-all":
            for w in visible:
                user32.ShowWindow(w["hwnd"], SW_MAXIMIZE)
            return {"status": "ok", "message": f"Successfully maximized **{count} windows**, Sir."}
            
        elif layout == "minimize-all":
            for w in visible:
                user32.ShowWindow(w["hwnd"], SW_MINIMIZE)
            return {"status": "ok", "message": f"Successfully minimized **{count} windows**."}
            
        elif layout in ["side-by-side", "split", "tile"]:
            if count == 1:
                # Maximize the single window
                user32.ShowWindow(visible[0]["hwnd"], SW_MAXIMIZE)
                return {"status": "ok", "message": f"Only 1 visible window ('{visible[0]['title']}') found. Maximized it, Sir."}
                
            elif count == 2 or layout == "split":
                # Split vertically (left & right half)
                half_w = screen_w // 2
                
                # Left window
                user32.ShowWindow(visible[0]["hwnd"], SW_RESTORE)
                user32.SetWindowPos(visible[0]["hwnd"], 0, 0, 0, half_w, usable_h, 0x0040)
                
                # Right window (limit split to first 2 visible windows for cleanliness)
                user32.ShowWindow(visible[1]["hwnd"], SW_RESTORE)
                user32.SetWindowPos(visible[1]["hwnd"], 0, half_w, 0, half_w, usable_h, 0x0040)
                
                # Minimize other windows to avoid clutter
                for w in visible[2:]:
                    user32.ShowWindow(w["hwnd"], SW_MINIMIZE)
                    
                return {
                    "status": "ok",
                    "message": f"Split screen complete, Sir. Placed **'{visible[0]['title']}'** on the left and **'{visible[1]['title']}'** on the right."
                }
                
            else:
                # Grid Tile (up to 4 windows)
                grid_count = min(count, 4)
                cols = 2 if grid_count > 2 else grid_count
                rows = 2 if grid_count > 2 else 1
                
                w_width = screen_w // cols
                w_height = usable_h // rows
                
                for idx in range(grid_count):
                    w = visible[idx]
                    col = idx % cols
                    row = idx // cols
                    
                    x = col * w_width
                    y = row * w_height
                    
                    user32.ShowWindow(w["hwnd"], SW_RESTORE)
                    user32.SetWindowPos(w["hwnd"], 0, x, y, w_width, w_height, 0x0040)
                    
                # Minimize anything beyond the grid cap
                for w in visible[grid_count:]:
                    user32.ShowWindow(w["hwnd"], SW_MINIMIZE)
                    
                return {"status": "ok", "message": f"Tiled **{grid_count} windows** in a beautiful {cols}x{rows} grid layout, Sir."}
                
        else:
            return {"status": "error", "message": f"Unsupported window layout mode: '{layout}'."}
            
    except Exception as e:
        logger.error(f"Window layout change failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Could not arrange windows: {str(e)}"}

def launch_workspace(workspace_name: str) -> Dict[str, Any]:
    """
    Launch pre-defined engineering and startup workspaces.
    Supported: 'skipit', 'smart_cart', 'all'.
    """
    name = workspace_name.lower().strip()
    try:
        if "skipit" in name:
            # 1. Open codebase folder
            skipit_dir = "C:\\Users\\HP\\OneDrive\\Desktop\\void\\VOID" # Default path or workspace path
            subprocess.Popen(["explorer", skipit_dir], shell=True)
            
            # 2. Launch standard browser portals
            chrome_cmd = "start chrome https://github.com http://localhost:3000"
            subprocess.Popen(["cmd", "/c", chrome_cmd], shell=True)
            
            # 3. Open VS Code
            subprocess.Popen(["cmd", "/c", "code", skipit_dir], shell=True)
            
            return {
                "status": "ok",
                "message": "Initialized **SkipIt Development Workspace**, Sir. Opened Codebase, VS Code, and Chrome portals."
            }
            
        elif "smart" in name or "cart" in name:
            # Smart Cart Workspace
            subprocess.Popen(["cmd", "/c", "start chrome https://smartcart-admin.local"], shell=True)
            return {
                "status": "ok",
                "message": "Initialized **Smart Cart Portal**, Sir. Standing by on store pilots."
            }
            
        else:
            # Generic dev workspace
            subprocess.Popen(["cmd", "/c", "start chrome https://github.com"], shell=True)
            return {
                "status": "ok",
                "message": f"Initialized generic workspace for **'{workspace_name}'**, Sir."
            }
            
    except Exception as e:
        logger.error(f"Workspace launch failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to initialize workspace: {str(e)}"}
