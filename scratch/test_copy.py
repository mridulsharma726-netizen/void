import pyperclip
import time
import uiautomation as auto

def test_copy():
    auto.SetGlobalSearchTimeout(3.0)
    print("Searching for WhatsApp window...")
    # Get the window by checking for both "WhatsApp" or windows containing "WhatsApp"
    win = auto.WindowControl(searchDepth=1, Name="WhatsApp")
    if not win.Exists(3.0):
        # Fallback: search for window containing WhatsApp
        for w in auto.GetRootControl().GetChildren():
            if "whatsapp" in w.Name.lower():
                win = w
                break
                
    if not win or not win.Exists(0.5):
        print("WhatsApp window not found!")
        return
        
    print(f"Found window: '{win.Name}'. Activating...")
    win.SetActive()
    time.sleep(1.0)
    
    # Click center of the window
    rect = win.BoundingRectangle
    click_x = rect.left + (rect.width() // 2)
    click_y = rect.top + (rect.height() // 2)
    print(f"Clicking center of WhatsApp window at ({click_x}, {click_y})...")
    auto.Click(click_x, click_y)
    time.sleep(0.5)
    
    # Clear clipboard
    pyperclip.copy("")
    
    # Send Ctrl+A and Ctrl+C
    print("Sending Ctrl+A and Ctrl+C using uiautomation...")
    auto.SendKeys('^a')
    time.sleep(0.2)
    auto.SendKeys('^c')
    time.sleep(0.5)
    
    copied_text = pyperclip.paste()
    print(f"\n--- Clipboard Content (Length={len(copied_text)}) ---")
    print(copied_text[:1000])

if __name__ == "__main__":
    test_copy()
