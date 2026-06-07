"""
VOID Computer Vision Control Module
==================================
Handles fast screen capturing (mss), foreground window bounds extraction,
local OCR text extraction (Tesseract with EasyOCR fallback), and template matching.
"""

import os
import time
import logging
import ctypes
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("void.cvcs.cv_control")

# Setup screenshot paths
ROOT_DIR = Path(__file__).parent.parent
SCREENSHOT_DIR = ROOT_DIR / "memory" / "data" / "screenshots"

# Import optional libraries
try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    # Under Windows, if Tesseract isn't in default path, users might need to specify it:
    # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
    easyocr_reader = None # Initialize lazily to prevent start-up lag
except ImportError:
    EASYOCR_AVAILABLE = False
    easyocr_reader = None


def get_foreground_window_bounds() -> Optional[Dict[str, int]]:
    """
    Retrieve foreground window coordinates on Windows.
    Returns: {"left": int, "top": int, "width": int, "height": int}
    """
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return None
            
        rect = ctypes.wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            # On Windows 10/11, DWM borders can add invisible padding.
            # We fetch raw coordinates first
            left = rect.left
            top = rect.top
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            return {
                "left": max(0, left),
                "top": max(0, top),
                "width": max(100, width),
                "height": max(100, height)
            }
    except Exception as e:
        logger.error(f"[CV-CONTROL] Failed retrieving foreground window bounds: {e}")
    return None


def take_screenshot(filename: Optional[str] = None, monitor_index: int = 1) -> Dict[str, Any]:
    """
    High-performance capture of the selected monitor screen using mss.
    Saves screenshot as PNG.
    """
    if not MSS_AVAILABLE or not PIL_AVAILABLE:
        return {
            "status": "error",
            "message": "mss or Pillow libraries are not available in active environment."
        }
        
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        if not filename:
            filename = "current.png"
        elif not filename.endswith(".png"):
            filename = f"{filename}.png"
            
        filepath = SCREENSHOT_DIR / filename
        
        with mss.mss() as sct:
            monitors = sct.monitors
            if len(monitors) <= monitor_index:
                # Fallback to monitor 0 (virtual screen covering all displays) or 1
                monitor_index = 1 if len(monitors) > 1 else 0
                
            monitor = monitors[monitor_index]
            
            # Capture
            sct_img = sct.grab(monitor)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            img.save(str(filepath), "PNG")
            
            return {
                "status": "ok",
                "message": f"Captured monitor {monitor_index}",
                "filepath": str(filepath),
                "width": sct_img.width,
                "height": sct_img.height,
                "monitor": monitor_index
            }
    except Exception as e:
        logger.error(f"[CV-CONTROL] Screen capture failed: {e}")
        return {"status": "error", "message": f"Capture failed: {str(e)}"}


def crop_image(filepath: str, bounds: Dict[str, int]) -> Optional[str]:
    """
    Crop an image file to specific bounding boxes (e.g. active window) and save it.
    """
    if not PIL_AVAILABLE or not os.path.exists(filepath):
        return None
        
    try:
        img = Image.open(filepath)
        left = bounds.get("left", 0)
        top = bounds.get("top", 0)
        width = bounds.get("width", img.width)
        height = bounds.get("height", img.height)
        
        # Calculate box
        box = (left, top, min(img.width, left + width), min(img.height, top + height))
        cropped = img.crop(box)
        
        cropped_path = str(Path(filepath).parent / f"cropped_{Path(filepath).name}")
        cropped.save(cropped_path)
        return cropped_path
    except Exception as e:
        logger.error(f"[CV-CONTROL] Cropping image failed: {e}")
    return None


def init_easyocr():
    """Lazily load the EasyOCR Reader instance to conserve startup latency."""
    global easyocr_reader
    if EASYOCR_AVAILABLE and easyocr_reader is None:
        try:
            logger.info("[CV-CONTROL] Initializing EasyOCR reader (English)...")
            easyocr_reader = easyocr.Reader(['en'], gpu=False) # CPU-only safe default
        except Exception as e:
            logger.error(f"[CV-CONTROL] Failed initializing EasyOCR: {e}")


def scan_ocr_text(image_path: str) -> List[Dict[str, Any]]:
    """
    Analyze image using local OCR engines.
    Tesseract is executed first. EasyOCR is run as a fallback
    if average Tesseract word confidence falls below 80% or if few words are found.
    """
    results = []
    
    if not PIL_AVAILABLE or not os.path.exists(image_path):
        return results
        
    tesseract_success = False
    
    # 1. Primary OCR: PyTesseract
    if PYTESSERACT_AVAILABLE:
        try:
            img = Image.open(image_path)
            # Fetch structured OCR data: positions, heights, contents, confidences
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
            word_count = len(data.get("text", []))
            total_conf = 0
            valid_words = 0
            
            for i in range(word_count):
                word = str(data["text"][i]).strip()
                conf = float(data["conf"][i])
                
                # Exclude spaces or empty detections (-1 conf)
                if word and conf >= 0:
                    total_conf += conf
                    valid_words += 1
                    
                    x = int(data["left"][i])
                    y = int(data["top"][i])
                    w = int(data["width"][i])
                    h = int(data["height"][i])
                    
                    results.append({
                        "text": word,
                        "confidence": conf / 100.0,
                        "box": {"x": x, "y": y, "width": w, "height": h},
                        "center": (x + w // 2, y + h // 2),
                        "engine": "tesseract"
                    })
                    
            avg_confidence = (total_conf / valid_words) if valid_words > 0 else 0.0
            logger.info(f"[CV-CONTROL] Tesseract scan completed. Words: {valid_words}, Avg Conf: {avg_confidence:.2f}%")
            
            # Deem successful if we found text with reasonable confidence
            if valid_words > 0 and avg_confidence >= 80.0:
                tesseract_success = True
                
        except Exception as e:
            logger.warning(f"[CV-CONTROL] Tesseract run encountered errors: {e}. Falling back.")
            
    # 2. Secondary/Fallback OCR: EasyOCR
    if not tesseract_success and EASYOCR_AVAILABLE:
        try:
            init_easyocr()
            if easyocr_reader:
                logger.info("[CV-CONTROL] Low confidence/Tesseract missing. Activating EasyOCR fallback...")
                easy_results = easyocr_reader.readtext(image_path)
                
                # Clear results to overwrite with higher-fidelity predictions
                results = []
                
                for (bbox, text, prob) in easy_results:
                    # easyocr bbox format: [[x0, y0], [x1, y1], [x2, y2], [x3, y3]]
                    x = int(bbox[0][0])
                    y = int(bbox[0][1])
                    w = int(bbox[1][0] - bbox[0][0])
                    h = int(bbox[2][1] - bbox[1][1])
                    
                    results.append({
                        "text": text,
                        "confidence": float(prob),
                        "box": {"x": x, "y": y, "width": w, "height": h},
                        "center": (x + w // 2, y + h // 2),
                        "engine": "easyocr"
                    })
                logger.info(f"[CV-CONTROL] EasyOCR scan complete. BBoxes found: {len(results)}")
        except Exception as e:
            logger.error(f"[CV-CONTROL] EasyOCR fallback execution failed: {e}")
            
    return results


def find_text_coordinates(query: str, image_path: str) -> List[Dict[str, Any]]:
    """
    Search parsed OCR elements for specific text queries.
    Supports partial phrase matches.
    """
    matches = []
    query_lower = query.lower().strip()
    
    ocr_data = scan_ocr_text(image_path)
    if not ocr_data:
        return []
        
    for item in ocr_data:
        item_text = item["text"].lower()
        if query_lower in item_text or item_text in query_lower:
            matches.append(item)
            
    return matches


if __name__ == "__main__":
    # Standard script verify
    logging.basicConfig(level=logging.INFO)
    print("CV Control diagnostics:")
    print(f"mss Available: {MSS_AVAILABLE}")
    print(f"PIL Available: {PIL_AVAILABLE}")
    print(f"pytesseract Available: {PYTESSERACT_AVAILABLE}")
    print(f"easyocr Available: {EASYOCR_AVAILABLE}")
    
    if MSS_AVAILABLE:
        res = take_screenshot()
        print(f"Screenshot result: {res}")
        if res["status"] == "ok":
            bounds = get_foreground_window_bounds()
            print(f"Active foreground window bounds: {bounds}")
            if bounds:
                cropped = crop_image(res["filepath"], bounds)
                print(f"Cropped Active Window path: {cropped}")
