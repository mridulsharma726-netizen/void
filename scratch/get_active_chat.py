import uiautomation as auto
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

def test_get_active_chat():
    win = auto.WindowControl(searchDepth=1, Name="WhatsApp")
    if not win.Exists(0.5):
        for w in auto.GetRootControl().GetChildren():
            if "whatsapp" in w.Name.lower():
                win = w
                break
                
    if not win or not win.Exists(0.5):
        print("WhatsApp not found.")
        return
        
    print("WhatsApp window found:", win.Name)
    
    # Let's search for any elements that might contain the name of the active chat
    # In WhatsApp UWP/Desktop, the top header displays the active chat's name as a TextControl or ButtonControl
    # Let's print all TextControls and ButtonControls in the window to see where the active chat name is!
    print("\n--- ALL TEXT CONTROLS ---")
    texts = win.GetChildren()
    
    def find_all_of_type(control, type_name, results, depth=0):
        if depth > 10:
            return
        if control.ControlTypeName == type_name and control.Name:
            results.append(control)
        for child in control.GetChildren():
            find_all_of_type(child, type_name, results, depth + 1)
            
    text_controls = []
    find_all_of_type(win, "TextControl", text_controls)
    for t in text_controls:
        print(f"TextControl: Name='{t.Name}', AutomationId='{t.AutomationId}'")
        
    button_controls = []
    find_all_of_type(win, "ButtonControl", button_controls)
    print("\n--- ALL BUTTON CONTROLS ---")
    for b in button_controls:
         print(f"ButtonControl: Name='{b.Name}', AutomationId='{b.AutomationId}'")

if __name__ == "__main__":
    test_get_active_chat()
