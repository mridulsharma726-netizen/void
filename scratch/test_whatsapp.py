import uiautomation as auto
import sys
import time

def inspect_whatsapp():
    auto.SetGlobalSearchTimeout(3.0)
    print("Searching for WhatsApp window...")
    # Native WhatsApp on Windows 10/11 is a UWP app, usually named "WhatsApp"
    whatsapp_win = auto.WindowControl(searchDepth=1, Name="WhatsApp")
    
    if not whatsapp_win.Exists(3.0):
        print("WhatsApp window not found! Please make sure WhatsApp is running and not minimized.")
        return
        
    print("Found WhatsApp main window!")
    whatsapp_win.SetActive()
    time.sleep(0.5)
    
    # Print direct children controls
    print("\n--- Direct Children Controls ---")
    for idx, child in enumerate(whatsapp_win.GetChildren()):
        print(f"Child {idx}: Name='{child.Name}', ControlType={child.ControlTypeName}, ClassName='{child.ClassName}'")
        
    # Search for lists or items
    print("\n--- Searching for chat list elements ---")
    # Chat items in WhatsApp usually have a ControlType of List or ListItem or Custom
    # Let's search for controls of type ListItem
    list_items = whatsapp_win.GetChildren()
    for item in list_items:
        # Search recursively up to depth 4 for list items or text
        pass

if __name__ == "__main__":
    inspect_whatsapp()
