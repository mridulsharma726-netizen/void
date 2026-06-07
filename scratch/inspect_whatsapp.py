import uiautomation as auto
import sys
import os

def inspect():
    print("=== INSPECTING WHATSAPP WINDOW STRUCTURE ===")
    
    # Try to find the window
    win = auto.WindowControl(searchDepth=1, Name="WhatsApp")
    if not win.Exists(1.0):
        print("WhatsApp window not found. Searching by part name...")
        for w in auto.GetRootControl().GetChildren():
            if "whatsapp" in w.Name.lower():
                win = w
                break
                
    if not win or not win.Exists(0.5):
        print("WhatsApp window not found at all.")
        return
        
    print(f"Found Window: Name='{win.Name}', ClassName='{win.ClassName}'")
    
    # Find all Edit controls (usually search bars)
    print("\n--- EDIT CONTROLS ---")
    edits = win.GetChildren()
    # Walk the control tree to find Edits
    def walk(control, depth=0):
        if depth > 10:
            return
        indent = "  " * depth
        control_type = control.ControlTypeName
        name = control.Name
        if "edit" in control_type.lower() or "button" in control_type.lower() or "text" in control_type.lower() or name:
            if name or "edit" in control_type.lower():
                print(f"{indent}{control_type}: Name='{name}', ClassName='{control.ClassName}', AutomationId='{control.AutomationId}'")
        for child in control.GetChildren():
            walk(child, depth + 1)
            
    walk(win)

if __name__ == "__main__":
    inspect()
