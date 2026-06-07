import os
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("void.screen_ocr")

# Setup screenshot paths
ROOT_DIR = Path(__file__).parent.parent
SCREENSHOT_DIR = ROOT_DIR / "memory" / "data" / "screenshots"

try:
    from tools.cv_control import take_screenshot, scan_ocr_text, get_foreground_window_bounds, MSS_AVAILABLE, PYTESSERACT_AVAILABLE
    CVCS_LIBS_AVAILABLE = True
except ImportError:
    CVCS_LIBS_AVAILABLE = False
    MSS_AVAILABLE = False
    PYTESSERACT_AVAILABLE = False

try:
    from server.backend.screen_monitor import get_monitor_instance
except ImportError:
    get_monitor_instance = None

def get_screen_context_for_llm(filename: str = "current.png") -> str:
    """
    Takes a screenshot, runs OCR, groups text spatially, and returns it.
    If OCR libraries or dependencies are missing, returns a mock diagnostic screen context.
    """
    if not CVCS_LIBS_AVAILABLE or not MSS_AVAILABLE:
        return _get_mock_context("MSS/CVCS libraries missing")
        
    try:
        shot = take_screenshot(filename)
        if shot["status"] != "ok":
            return _get_mock_context(f"Screenshot failed: {shot.get('message')}")
            
        filepath = shot["filepath"]
        words = scan_ocr_text(filepath)
        
        if not words:
            return _get_mock_context("No text detected or OCR engine failed (missing tesseract binaries)")
            
        # Group words into lines based on vertical closeness (within 15 pixels)
        # Sort words first by y coordinate
        sorted_words = sorted(words, key=lambda w: (w["box"]["y"], w["box"]["x"]))
        
        lines: List[List[Dict[str, Any]]] = []
        for word in sorted_words:
            added = False
            for line in lines:
                # If word y-coordinate is within 15px of the average y-coordinate of the line
                avg_y = sum(w["box"]["y"] for w in line) / len(line)
                if abs(word["box"]["y"] - avg_y) <= 15:
                    line.append(word)
                    added = True
                    break
            if not added:
                lines.append([word])
                
        # Format the lines sorted left-to-right
        formatted_lines = []
        for line in lines:
            sorted_line = sorted(line, key=lambda w: w["box"]["x"])
            line_str = " ".join(w["text"] for w in sorted_line)
            formatted_lines.append(line_str)
            
        screen_text = "\n".join(formatted_lines)
        
        title = ""
        if get_monitor_instance:
            try:
                title = get_monitor_instance().get_foreground_window_title()
            except Exception:
                pass
                
        bounds = None
        try:
            bounds = get_foreground_window_bounds()
        except Exception:
            pass
            
        return (
            f"[Screen Content (OCR Extracted)]\n"
            f"- Active Window: {title or 'Unknown'}\n"
            f"- Bounds: {bounds or 'Unknown'}\n"
            f"- Scanned Text Content:\n{screen_text}\n"
            f"[End Screen Content]"
        )
        
    except Exception as e:
        logger.error(f"Failed to extract screen OCR: {e}")
        return _get_mock_context(str(e))

def _get_mock_context(reason: str) -> str:
    """Returns a realistic mock context for computer vision when dependencies are missing."""
    title = "Visual Studio Code - project_map.json"
    if get_monitor_instance:
        try:
            active_title = get_monitor_instance().get_foreground_window_title()
            if active_title:
                title = active_title
        except Exception:
            pass
            
    return (
        f"[Screen Content (Simulated diagnostics fallback - {reason})]\n"
        f"- Active Window: {title}\n"
        f"- Visible Editor Content:\n"
        f"  line 1: {{\n"
        f"  line 2:   \"version\": \"VOID X v1.0\",\n"
        f"  line 3:   \"status\": \"operational\",\n"
        f"  line 4:   \"refactoring_enabled\": true,\n"
        f"  line 5:   \"voice_personalities\": [\"Professional\", \"Teacher\", \"Founder\", \"Developer\", \"Motivator\", \"Researcher\"]\n"
        f"  line 6: }}\n"
        f"[End Screen Content]"
    )
