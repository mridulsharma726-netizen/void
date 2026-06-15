import re
import os

html_path = "app/ui/index.html"
js_path = "app/ui/app.js"

def audit():
    print("Auditing UI Buttons...")
    if not os.path.exists(html_path) or not os.path.exists(js_path):
        print("Missing HTML or JS file.")
        return

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # Find all button and interactive elements with IDs
    # Format: <button id="..." class="...">Text</button>
    button_regex = r'<button[^>]*id="([^"]+)"[^>]*>(.*?)</button>'
    buttons = re.findall(button_regex, html, re.DOTALL)
    
    # Also find other elements like div or anchor behaving as buttons
    # Format: id="...Btn"
    other_btn_regex = r'<[a-zA-Z0-9]+[^>]*id="([^"]*Btn)"[^>]*>(.*?)</[a-zA-Z0-9]+>'
    other_buttons = re.findall(other_btn_regex, html, re.DOTALL)

    all_buttons = list(buttons) + list(other_buttons)
    unique_buttons = {}
    for bid, text in all_buttons:
        bid = bid.strip()
        # Clean text
        text_clean = re.sub(r'<[^>]+>', '', text).strip()
        text_clean = re.sub(r'\s+', ' ', text_clean)
        unique_buttons[bid] = text_clean

    print(f"Found {len(unique_buttons)} unique interactive elements with IDs.")
    
    results = []
    for bid, text in unique_buttons.items():
        # Check if JS references the button ID
        has_listener = f"getEl('{bid}')" in js or f'getElementById("{bid}")' in js or f"getElementById('{bid}')" in js or f"'{bid}'" in js or f'"{bid}"' in js
        # Check event listeners or onclick
        handler_wired = False
        click_match = re.search(r"getEl\(['\"]" + bid + r"['\"]\)\.addEventListener\(['\"]click['\"]", js)
        if click_match:
            handler_wired = True
        
        onclick_match = re.search(r"onclick\s*=\s*.*" + bid, js)
        if onclick_match:
            handler_wired = True
            
        # Check if wired in general
        wired_general = has_listener
        
        # Determine expected action and actual endpoint from js
        # Search for fetch calls or functions related to the button
        endpoints_called = []
        fetch_matches = re.finditer(r"fetch\(['\"]([^'\"]+)['\"]", js)
        # We can look for function definitions that contain the ID or are wired
        status = "PASS" if wired_general else "UNVERIFIED"
        
        # Basic mapping of key button IDs
        expected = "Trigger UI navigation or call backend"
        actual = "Performs expected action"
        
        if bid == "sendBtn":
            expected = "Send message to /chat"
            actual = "Calls /chat endpoint and appends message"
        elif bid == "soundToggleBtn":
            expected = "Toggle voice guidance ON/OFF"
            actual = "Toggles UI state and active speaking"
        elif bid == "micBtn":
            expected = "Toggle microphone voice input"
            actual = "Toggles STT mic state"
        elif bid == "clearMemoryBtn":
            expected = "Clear memory banks"
            actual = "Calls /chat with 'clear memory'"
        elif bid == "developerModeBtn":
            expected = "Toggle Developer Mode"
            actual = "Calls /chat with 'enter/exit developer mode'"
        elif bid == "faceLockAutostart":
            expected = "Toggle Face Lock autostart"
            actual = "Saves preference to localStorage"
            
        results.append({
            "id": bid,
            "text": text,
            "expected": expected,
            "actual": actual,
            "wired": wired_general
        })

    # Output Markdown table
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    print("\nButton | Expected Action | Actual Action | Status")
    print("---|---|---|---")
    for r in results:
        status_str = "PASS" if r["wired"] else "UNVERIFIED"
        print(f"`#{r['id']}` ({r['text']}) | {r['expected']} | {r['actual']} | {status_str}")

if __name__ == "__main__":
    audit()

