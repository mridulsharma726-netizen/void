"""
VOID Desktop Shortcut Creator
=========================

Creates a Windows desktop shortcut to launch the VOID Electron app.

Usage:
    python create_shortcut.py

Requirements:
    - Windows OS
    - pywin32 (optional - script will try alternative methods)
"""

import os
import sys
import subprocess
import shutil


def get_desktop_path():
    """Get the Windows desktop path."""
    # Try OneDrive desktop path first (very common on modern Windows systems)
    onedrive_desktop = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
    if os.path.exists(onedrive_desktop):
        return onedrive_desktop
        
    # Try alternative method (Shell API)
    try:
        import ctypes
        from ctypes import wintypes
        
        CSIDL_DESKTOP = 0x0000
        SHGFP_TYPE_CURRENT = 0
        
        buf = wintypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOP, None, SHGFP_TYPE_CURRENT, buf)
        if buf.value and os.path.exists(buf.value):
            return buf.value
    except:
        pass
        
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    return desktop


def find_electron_path():
    """Find the Electron/VOID executable path."""
    # Possible paths (prioritizing the compiled/native executable first)
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "desktop", "dist", "win-unpacked", "VOID.exe"),
        os.path.join(os.path.dirname(__file__), "desktop", "node_modules", "electron", "dist", "electron.exe"),
        os.path.join(os.path.dirname(__file__), "desktop", "node_modules", ".bin", "electron.cmd"),
        r"C:\Users\HP\OneDrive\Desktop\void\VOID\desktop\dist\win-unpacked\VOID.exe",
        r"C:\Users\HP\OneDrive\Desktop\void\VOID\desktop\node_modules\electron\dist\electron.exe",
        r"C:\Users\HP\OneDrive\Desktop\void\VOID\desktop\node_modules\.bin\electron.cmd",
        r"C:\Users\HP\OneDrive\Desktop\void\VOID\desktop\node_modules\.bin\electron.exe",
        r"C:\Users\HP\OneDrive\Desktop\void\VOID\node_modules\.bin\electron.cmd",
        r"C:\Users\HP\OneDrive\Desktop\void\VOID\desktop\electron.cmd",
    ]
    
    # Try to find the electron executable
    for path in possible_paths:
        if os.path.exists(path):
            return path
            
    # Check if npm is available to launch
    npm_path = shutil.which("npm")
    if npm_path:
        return "npm"
        
    return None


def get_startup_path():
    """Get the Windows startup programs path."""
    startup = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    if os.path.exists(startup):
        return startup
    return None


def create_shortcut_pywin32(desktop: str, target: str, working_dir: str, arguments: str = "", icon: str = None):
    """Create shortcut using pywin32 (if available)."""
    try:
        import winshell
        from win32com.client import Dispatch
        
        shortcut_path = os.path.join(desktop, "VOID Assistant.lnk")
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = working_dir
        shortcut.Arguments = arguments
        
        if icon and os.path.exists(icon):
            shortcut.IconLocation = icon
        
        shortcut.save()
        
        return True, shortcut_path
    except ImportError:
        return False, "pywin32 not installed"
    except Exception as e:
        return False, str(e)


def create_shortcut_ctypes(desktop: str, target: str, working_dir: str, arguments: str = "", icon: str = None):
    """Create shortcut using ctypes and Windows Script Host."""
    import ctypes
    from ctypes import wintypes
    
    shortcut_path = os.path.join(desktop, "VOID Assistant.lnk")
    
    # Create the shortcut using VBScript approach via PowerShell
    # This avoids needing pywin32
    vbs_script = f'''
Set WshShell = CreateObject("WScript.Shell")
Set Shortcut = WshShell.CreateShortcut("{shortcut_path}")
Shortcut.TargetPath = "{target}"
Shortcut.WorkingDirectory = "{working_dir}"
Shortcut.Arguments = "{arguments}"
'''
    if icon:
        vbs_script += f'\nShortcut.IconLocation = "{icon}"'
    
    vbs_script += '\nShortcut.Save\n'
    
    # Write temporary VBS file
    vbs_path = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), 'void_shortcut.vbs')
    try:
        with open(vbs_path, 'w') as f:
            f.write(vbs_script)
        
        # Run the VBS script
        subprocess.run(['cscript', '//Nologo', vbs_path], check=True, capture_output=True)
        
        # Clean up
        try:
            os.remove(vbs_path)
        except:
            pass
        
        return True, shortcut_path
    except Exception as e:
        return False, f"VBS method failed: {e}"


def create_shortcut_simple(desktop: str, target: str, working_dir: str, arguments: str = ""):
    """Create a simple .url shortcut (works without special libraries)."""
    shortcut_path = os.path.join(desktop, "VOID Assistant.url")
    
    # Create an Internet Shortcut (.url file)
    # This is a simple text file format
    url_content = f'''[InternetShortcut]
URL=file:///{target.replace(os.sep, '/')}
WorkingDirectory={working_dir}
'''
    
    # Also try .lnk with basic format
    lnk_path = os.path.join(desktop, "VOID Assistant.lnk")
    
    try:
        # Try to create a basic .lnk using PowerShell
        ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{lnk_path}")
$Shortcut.TargetPath = "{target}"
$Shortcut.WorkingDirectory = "{working_dir}"
$Shortcut.Arguments = "{arguments}"
$Shortcut.Save()
'''
        
        # Run PowerShell to create shortcut
        result = subprocess.run(
            ['powershell', '-Command', ps_script],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and os.path.exists(lnk_path):
            return True, lnk_path
    except Exception as e:
        pass
    
    # Fallback: create .url file
    try:
        with open(shortcut_path, 'w') as f:
            f.write(url_content)
        return True, shortcut_path
    except Exception as e:
        return False, str(e)


def main():
    """Main function to create the VOID desktop shortcut and configure autostart."""
    print("=" * 50)
    print("VOID Desktop Shortcut & Autostart Creator")
    print("=" * 50)
    
    # Get paths
    desktop = get_desktop_path()
    startup = get_startup_path()
    print(f"\nDesktop path: {desktop}")
    print(f"Startup path: {startup}")
    
    # Find Electron path
    electron_path = find_electron_path()
    if not electron_path:
        print("\n[WARNING] Could not find Electron or VOID executable automatically.")
        print("Please enter the path to electron.cmd manually,")
        print("or make sure you're running this from the VOID directory.")
        
        # Try to use npm start as fallback
        electron_path = "npm"
    
    # Determine working directory and arguments
    app_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "desktop")
    if electron_path.endswith("VOID.exe") or "win-unpacked" in electron_path:
        working_dir = os.path.dirname(electron_path)
        arguments = ""
    else:
        working_dir = app_dir
        if electron_path == "npm":
            arguments = ""
        elif electron_path.endswith("electron.exe"):
            arguments = f'"{app_dir}"'
        else:
            arguments = ""
    
    print(f"Executable/Target path: {electron_path}")
    print(f"Working directory: {working_dir}")
    print(f"Arguments: {arguments}")
    
    # Create Desktop shortcut
    print("\n--- Creating Desktop Shortcut ---")
    desktop_success = False
    desktop_result_path = None
    
    methods = [
        ("PowerShell", lambda: create_shortcut_simple(desktop, electron_path, working_dir, arguments)),
        ("ctypes/VBS", lambda: create_shortcut_ctypes(desktop, electron_path, working_dir, arguments, None)),
        ("pywin32", lambda: create_shortcut_pywin32(desktop, electron_path, working_dir, arguments, None)),
    ]
    
    for method_name, method_func in methods:
        print(f"Trying {method_name} method...")
        try:
            desktop_success, desktop_result_path = method_func()
            if desktop_success:
                print(f"Success! Desktop shortcut created: {desktop_result_path}")
                break
            else:
                print(f"[INFO] {method_name} failed: {desktop_result_path}")
        except Exception as e:
            print(f"[ERROR] Error with {method_name}: {e}")
            
    # Create Startup shortcut
    startup_success = False
    startup_result_path = None
    if startup:
        print("\n--- Creating Startup Shortcut (Auto-start) ---")
        startup_methods = [
            ("PowerShell", lambda: create_shortcut_simple(startup, electron_path, working_dir, arguments)),
            ("ctypes/VBS", lambda: create_shortcut_ctypes(startup, electron_path, working_dir, arguments, None)),
            ("pywin32", lambda: create_shortcut_pywin32(startup, electron_path, working_dir, arguments, None)),
        ]
        
        for method_name, method_func in startup_methods:
            print(f"Trying {method_name} method for Startup...")
            try:
                startup_success, startup_result_path = method_func()
                if startup_success:
                    print(f"Success! Startup shortcut created: {startup_result_path}")
                    break
                else:
                    print(f"[INFO] {method_name} failed: {startup_result_path}")
            except Exception as e:
                print(f"[ERROR] Error with {method_name}: {e}")
    else:
        print("\n[WARNING] Startup path not found. Cannot configure autostart.")
        
    print("\n" + "=" * 50)
    if desktop_success:
        print("Desktop Shortcut: SUCCESS")
        print(f"Location: {desktop_result_path}")
    else:
        print("Desktop Shortcut: FAILED")
        
    if startup_success:
        print("Startup Auto-Start: SUCCESS")
        print(f"Location: {startup_result_path}")
    else:
        print("Startup Auto-Start: FAILED")
    print("=" * 50)


if __name__ == "__main__":
    main()


