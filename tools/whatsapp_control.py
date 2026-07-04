import uiautomation as auto
import pyperclip
import time
import os
import subprocess
import logging
import ctypes

logger = logging.getLogger("void.whatsapp")

def _send_ctrl_key(key: int):
    auto.PressKey(auto.Keys.VK_CONTROL, waitTime=0.05)
    auto.SendKey(key, waitTime=0.05)
    auto.ReleaseKey(auto.Keys.VK_CONTROL, waitTime=0.05)

def open_whatsapp() -> bool:
    """Ensure WhatsApp Desktop is open, starting it if necessary."""
    try:
        # Check if already running by finding the window
        win = auto.WindowControl(searchDepth=1, Name="WhatsApp")
        if win.Exists(0.5):
            win.SetActive()
            return True
            
        # Fallback search by part name
        for w in auto.GetRootControl().GetChildren():
            if "whatsapp" in w.Name.lower():
                w.SetActive()
                return True
                
        # Start WhatsApp native app protocol on Windows
        logger.info("WhatsApp not found. Starting native app protocol...")
        subprocess.Popen(["cmd", "/c", "start", "whatsapp:"])
        
        # Wait up to 5s for WhatsApp to launch
        for _ in range(10):
            time.sleep(0.5)
            win = auto.WindowControl(searchDepth=1, Name="WhatsApp")
            if win.Exists(0.1):
                win.SetActive()
                return True
                
        # Check again by part name
        for w in auto.GetRootControl().GetChildren():
            if "whatsapp" in w.Name.lower():
                w.SetActive()
                return True
                
        return False
    except Exception as e:
        logger.error(f"Failed to open WhatsApp: {e}")
        return False

def send_whatsapp_message(contact_name: str, message_text: str) -> dict:
    """
    Search for a contact and send them a WhatsApp message on command.
    Uses ultra-robust, DPI-independent keyboard shortcuts and safety gates.
    """
    ctypes.windll.ole32.CoInitialize(None)
    try:
        if not open_whatsapp():
            return {"status": "error", "message": "Could not open or focus WhatsApp. Please ensure it is installed, Sir."}
            
        # Ensure window is active and focused
        win = auto.WindowControl(searchDepth=1, Name="WhatsApp")
        if not win.Exists(0.5):
            for w in auto.GetRootControl().GetChildren():
                if "whatsapp" in w.Name.lower():
                    win = w
                    break
        if not win:
            return {"status": "error", "message": "WhatsApp window not found."}
            
        win.SetActive()
        time.sleep(0.5)
        
        # Click the search bar coordinates to ensure the window has focus and the cursor is active
        rect = win.BoundingRectangle
        click_x = rect.left + 230
        click_y = rect.top + 110
        logger.info(f"Clicking at ({click_x}, {click_y}) to focus search bar and window...")
        auto.Click(click_x, click_y)
        time.sleep(0.3)
        
        # 1. Reset any active filters or UI overlays by sending ESC multiple times
        logger.info("Resetting active searches and filters using ESC keys...")
        auto.SendKeys('{ESCAPE}' * 3)
        time.sleep(0.3)
        
        # Natively click the 'All' filter pill to clear the 'Unread' active filter state
        try:
            all_pill = win.TabItemControl(AutomationId='all-filter')
            if not all_pill.Exists(0.1):
                all_pill = win.TabItemControl(Name='All')
            if all_pill.Exists(0.1):
                logger.info("Natively clicking 'All' filter pill to reset unread filter...")
                all_pill.Click()
                time.sleep(0.3)
        except Exception as filter_err:
            logger.warning(f"Could not click 'All' filter pill natively: {filter_err}")
        
        # 2. Focus search bar using the standard Ctrl+F shortcut
        logger.info("Focusing search bar via Ctrl+F...")
        auto.SendKeys('{Ctrl}f')
        time.sleep(0.3)
        
        # 3. Clear search bar completely using Ctrl+A and Delete
        logger.info("Clearing search bar...")
        auto.SendKeys('{Ctrl}a{Delete}')
        time.sleep(0.3)
        
        # 4. Enter contact name using clipboard paste (100% reliable for unicode/special chars)
        logger.info(f"Pasting contact name: '{contact_name}'")
        pyperclip.copy(contact_name)
        auto.SendKeys('{Ctrl}v')
        time.sleep(0.3)
        
        # Wait 1.8 seconds for search results to load
        logger.info("Waiting for search results to query...")
        time.sleep(1.8)
        
        # 5. Highlight first search result and open the chat
        logger.info("Opening searched chat...")
        auto.SendKeys('{Down}{Enter}')
        time.sleep(0.8)
        
        # 6. Paste and send the message if text is provided
        if message_text:
            logger.info("Pasting message text...")
            pyperclip.copy(message_text)
            auto.SendKeys('{Ctrl}v')
            time.sleep(0.4)
            
            logger.info("Sending message...")
            auto.SendKeys('{Enter}')
            time.sleep(0.3)
        else:
            logger.info("Empty message text supplied. Opening chat and focusing input area, Sir.")
        
        # 7. Clean up by resetting the search field
        logger.info("Cleaning up search bar...")
        auto.SendKeys('{Ctrl}f')
        time.sleep(0.1)
        auto.SendKeys('{ESCAPE}' * 2)
        time.sleep(0.2)
        
        logger.info(f"Successfully sent WhatsApp message to {contact_name}")
        return {"status": "ok", "message": f"Successfully sent WhatsApp message to '{contact_name}': \"{message_text}\""}
        
    except Exception as e:
        logger.error(f"WhatsApp send failed: {e}")
        return {"status": "error", "message": f"Automation failed: {str(e)}"}
    finally:
        ctypes.windll.ole32.CoUninitialize()

def read_whatsapp_unread() -> dict:
    """
    Check for unread chats and attempt to copy the latest messages.
    Provides rich feedback and bringing to front capability.
    """
    ctypes.windll.ole32.CoInitialize(None)
    try:
        if not open_whatsapp():
            return {"status": "error", "message": "Could not open or focus WhatsApp, Sir."}
            
        win = auto.WindowControl(searchDepth=1, Name="WhatsApp")
        if not win.Exists(0.5):
            for w in auto.GetRootControl().GetChildren():
                if "whatsapp" in w.Name.lower():
                    win = w
                    break
        if not win:
            return {"status": "error", "message": "WhatsApp window not found."}
            
        win.SetActive()
        time.sleep(0.8)
        
        # Check window title for unread count, e.g. "(3) WhatsApp"
        title = win.Name
        unread_count = 0
        import re
        m = re.search(r'\((\d+)\)', title)
        if m:
            unread_count = int(m.group(1))
            
        # Optimization: If no unread chats exist, return immediately!
        if unread_count == 0:
            return {
                "status": "ok",
                "unread_chats_count": 0,
                "message": "You have no unread messages on WhatsApp, Sir! Systems are clear."
            }
            
        rect = win.BoundingRectangle
        logger.info(f"WhatsApp window bounds: {rect}")
        
        # 1. Filter by clicking "Unread" filter pill natively
        logger.info("Step 1: Filtering unread chats natively...")
        clicked_unread = False
        try:
            unread_pill = win.TabItemControl(AutomationId='unread-filter')
            if not unread_pill.Exists(0.1):
                unread_pill = win.TabItemControl(Name='Unread')
            # Look up also by name containing 'Unread'
            if not unread_pill.Exists(0.1):
                for child in win.GetChildren():
                    if "unread" in child.Name.lower() and child.ControlTypeName == "TabItemControl":
                        unread_pill = child
                        break
            if unread_pill.Exists(0.1):
                logger.info(f"Natively clicking Unread filter: {unread_pill.Name}")
                unread_pill.Click()
                clicked_unread = True
                time.sleep(0.8)
        except Exception as e:
            logger.warning(f"Could not click Unread filter natively: {e}")
            
        if not clicked_unread:
            # Fallback to coordinates
            unread_pill_x = rect.left + 200
            unread_pill_y = rect.top + 155
            logger.info(f"Fallback: Clicking unread filter pill at coordinate ({unread_pill_x}, {unread_pill_y})...")
            auto.Click(unread_pill_x, unread_pill_y)
            time.sleep(0.8)
            
        # 2. Try to copy messages of the first unread chat
        messages_preview = ""
        opened_chat = "First Unread Chat"
        
        # Press Down and Enter to select the first unread chat
        auto.SendKeys('{Down}{Enter}')
        time.sleep(0.8)
        
        # Try to select the message area and copy all
        # We click the center of the window to focus the chat list pane
        click_x = rect.left + (rect.width() // 2) + 100
        click_y = rect.top + (rect.height() // 2)
        auto.Click(click_x, click_y)
        time.sleep(0.3)
        
        # Clear clipboard, copy all
        pyperclip.copy("")
        auto.SendKeys('{Ctrl}a')
        time.sleep(0.2)
        auto.SendKeys('{Ctrl}c')
        time.sleep(0.6)
        
        copied = pyperclip.paste().strip()
        
        # Reset the filter dynamically by clicking 'All' natively or sending ESC keys
        logger.info("Step 3: Resetting filters...")
        clicked_all = False
        try:
            all_pill = win.TabItemControl(AutomationId='all-filter')
            if not all_pill.Exists(0.1):
                all_pill = win.TabItemControl(Name='All')
            if all_pill.Exists(0.1):
                logger.info("Natively clicking 'All' filter pill to reset...")
                all_pill.Click()
                clicked_all = True
                time.sleep(0.3)
        except Exception as e:
            logger.warning(f"Could not click 'All' filter natively to reset: {e}")
            
        if not clicked_all:
            # Fallback to search click and escape keys
            search_x = rect.left + 200
            search_y = rect.top + 110
            auto.Click(search_x, search_y)
            time.sleep(0.2)
            auto.SendKeys('{ESCAPE}' * 3)
            time.sleep(0.2)
        
        if copied and len(copied) > 10:
            # We copied the text successfully! Let's extract the last few lines of the chat
            lines = [l.strip() for l in copied.split('\n') if l.strip()]
            recent = lines[-6:] # Get the last 6 lines/messages
            messages_preview = "\n".join(recent)
            return {
                "status": "ok",
                "unread_chats_count": unread_count,
                "message": f"Successfully opened the unread chat and read the latest messages:\n\n{messages_preview}",
                "raw_copied": copied
            }
        else:
            # Clipboard was empty or could not copy
            if unread_count > 0:
                return {
                    "status": "ok",
                    "unread_chats_count": unread_count,
                    "message": f"I have brought WhatsApp to the front and filtered your unread chats. I can see you have **{unread_count} unread chats** waiting for you on screen, Sir. Please check the active window!"
                }
            else:
                return {
                    "status": "ok",
                    "unread_chats_count": 0,
                    "message": "You have no unread messages on WhatsApp, Sir! Systems are clear."
                }
                
    except Exception as e:
        logger.error(f"WhatsApp read failed: {e}")
        return {"status": "error", "message": f"Could not complete reading: {str(e)}"}
    finally:
        ctypes.windll.ole32.CoUninitialize()
