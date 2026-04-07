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
    # Try to get desktop path from environment
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if os.path.exists(desktop):
        return desktop
    
    # Try alternative method
    try:
        import ctypes
        from ctypes import wintypes
        
        CSIDL_DESKTOP = 0x0000
        SHGFP_TYPE_CURRENT = 0
        
        buf = wintypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOP, None, SHGFP_TYPE_CURRENT, buf)
        return buf.value
    except:
        return os.path.join(os.path.expanduser("~"), "Desktop")


def find_electron_path():
    """Find the Electron executable path."""
    # Possible paths
    possible_paths = [
        r"C:\Users\HP\OneDrive\Desktop\void\VOID\desktop\node_modules\.bin\electron.cmd",
        r"C:\Users\HP\OneDrive\Desktop\void\VOID\desktop\node_modules\.bin\electron.exe",
        r"C:\Users\HP\OneDrive\Desktop\void\VOID\node_modules\.bin\electron.cmd",
        r"C:\Users\HP\OneDrive\Desktop\void\VOID\desktop\electron.cmd",
        os.path.join(os.path.dirname(__file__), "desktop", "node_modules", ".bin", "electron.cmd"),
    ]
    
    # Try to find the electron executable
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Try to find in node_modules/.bin
    base_path = os.path.dirname(__file__)
    electron_path = os.path.join(base_path, "desktop", "node_modules", ".bin", "electron.cmd")
    if os.path.exists(electron_path):
        return electron_path
    
    # Check if npm is available to launch
    npm_path = shutil.which("npm")
    if npm_path:
        return "npm"
    
    return None


def create_shortcut_pywin32(desktop: str, target: str, working_dir: str, icon: str = None):
    """Create shortcut using pywin32 (if available)."""
    try:
        import winshell
        from win32com.client import Dispatch
        
        shortcut_path = os.path.join(desktop, "VOID Assistant.lnk")
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = working_dir
        
        if icon and os.path.exists(icon):
            shortcut.IconLocation = icon
        
        shortcut.save()
        
        return True, shortcut_path
    except ImportError:
        return False, "pywin32 not installed"
    except Exception as e:
        return False, str(e)


def create_shortcut_ctypes(desktop: str, target: str, working_dir: str, icon: str = None):
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


def create_shortcut_simple(desktop: str, target: str, working_dir: str):
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
    """Main function to create the VOID desktop shortcut."""
    print("=" * 50)
    print("VOID Desktop Shortcut Creator")
    print("=" * 50)
    
    # Get desktop path
    desktop = get_desktop_path()
    print(f"\nDesktop path: {desktop}")
    
    # Find Electron path
    electron_path = find_electron_path()
    if not electron_path:
        print("\n⚠️ Could not find Electron automatically.")
        print("Please enter the path to electron.cmd manually,")
        print("or make sure you're running this from the VOID directory.")
        
        # Try to use npm start as fallback
        electron_path = "npm"
        working_dir = os.path.dirname(__file__)
    else:
        working_dir = os.path.dirname(electron_path)
        if ".bin" in working_dir:
            working_dir = os.path.dirname(working_dir)
    
    print(f"Electron path: {electron_path}")
    print(f"Working directory: {working_dir}")
    
    # Try to create shortcut using different methods
    methods = [
        ("PowerShell", lambda: create_shortcut_simple(desktop, electron_path, working_dir)),
        ("ctypes/VBS", lambda: create_shortcut_ctypes(desktop, electron_path, working_dir, None)),
    ]
    
    success = False
    result_path = None
    
    for method_name, method_func in methods:
        print(f"\nTrying {method_name} method...")
        try:
            success, result_path = method_func()
            if success:
                print(f"✅ Success! Shortcut created: {result_path}")
                break
            else:
                print(f"⚠️ {method_name} failed: {result_path}")
        except Exception as e:
            print(f"❌ Error with {method_name}: {e}")
    
    if success:
        print("\n" + "=" * 50)
        print("✅ VOID Desktop Shortcut Created Successfully!")
        print(f"📍 Location: {result_path}")
        print("\nYou can now double-click the shortcut to launch VOID!")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("❌ Failed to create shortcut automatically.")
        print("\nTo create manually:")
        print("1. Go to your Desktop")
        print("2. Right-click > New > Shortcut")
        print("3. Browse to: " + os.path.dirname(__file__))
        print("4. Name it: VOID Assistant")
        print("=" * 50)


if __name__ == "__main__":
    main()


