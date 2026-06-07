import uiautomation as auto
import sys

def get_all_descendants(ctrl, depth=0, max_depth=6):
    if depth > max_depth:
        return []
    descendants = []
    try:
        children = ctrl.GetChildren()
        for child in children:
            descendants.append(child)
            descendants.extend(get_all_descendants(child, depth + 1, max_depth))
    except:
        pass
    return descendants

def test_read():
    auto.SetGlobalSearchTimeout(3.0)
    print("Searching for WhatsApp window...")
    win = auto.WindowControl(searchDepth=1, Name="WhatsApp")
    
    if not win.Exists(3.0):
        print("WhatsApp window not found!")
        sys.exit(1)
        
    print("Searching for descendant elements...")
    text_controls = get_all_descendants(win, depth=0, max_depth=6)
    
    print(f"Found {len(text_controls)} descendants in total.")
    
    print("\n--- Printing first 50 Text/ListItem Controls ---")
    count = 0
    for ctrl in text_controls:
        # Check if control is TextControl or ListItemControl or has text in Name
        if ctrl.ControlTypeName in ["TextControl", "ListItemControl", "ButtonControl", "CustomControl"]:
            name = ctrl.Name.strip()
            if name:
                print(f"Type={ctrl.ControlTypeName}, Name='{name}'")
                count += 1
                if count >= 60:
                    break

if __name__ == "__main__":
    test_read()
