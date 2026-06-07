import uiautomation as auto
import sys

def walk_tree(control, depth=0, max_depth=12, f=None):
    if depth > max_depth:
        return
        
    indent = "  " * depth
    name = control.Name
    ctrl_type = control.ControlTypeName
    cls_name = control.ClassName
    
    # Only print interesting controls or limit output length
    line = f"{indent}Type={ctrl_type}, Name='{name}', Class='{cls_name}'"
    print(line)
    if f:
        f.write(line + "\n")
        
    for child in control.GetChildren():
        walk_tree(child, depth + 1, max_depth, f)

if __name__ == "__main__":
    auto.SetGlobalSearchTimeout(3.0)
    print("Searching for WhatsApp window...")
    win = auto.WindowControl(searchDepth=1, Name="WhatsApp")
    
    if not win.Exists(3.0):
        print("WhatsApp window not found!")
        sys.exit(1)
        
    print("Walking WhatsApp UI tree (this might take a few seconds)...")
    with open("whatsapp_tree.txt", "w", encoding="utf-8") as f:
        walk_tree(win, depth=0, max_depth=8, f=f)
    print("Done! Tree saved to whatsapp_tree.txt")
