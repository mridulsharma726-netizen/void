import os
import re
import logging
from PIL import Image, ImageChops
from typing import Dict, Any, List, Optional
from core.vision.screen_ocr import ScreenOCR

logger = logging.getLogger("void.vision.vision_engine")

class VisionEngine:
    def __init__(self):
        self.ocr = ScreenOCR()

    def analyze_screenshot(self, image_path: str) -> Dict[str, Any]:
        """
        Analyze a screenshot file to extract OCR text, locate active windows, 
        and debug any visible error messages.
        """
        if not os.path.exists(image_path):
            return {"status": "error", "message": f"Image file '{image_path}' not found."}

        try:
            img = Image.open(image_path)
            width, height = img.size
        except Exception as e:
            return {"status": "error", "message": f"Failed to load image: {e}"}

        # 1. OCR text extraction
        ocr_res = self.ocr.extract_text_from_image(image_path)
        extracted_text = ocr_res.get("text", "")

        # 2. Scan for error logs / exceptions
        detected_errors = []
        error_keywords = ["error", "exception", "failed", "traceback", "syntaxerror", "warning", "unhandled"]
        for line in extracted_text.splitlines():
            line_lower = line.lower()
            if any(kw in line_lower for kw in error_keywords):
                detected_errors.append(line.strip())

        # 3. Detect visual anomalies (e.g. check for extreme red channels indicating crash windows)
        anomaly_detected = False
        anomaly_reason = ""
        try:
            # Look at a resized version to quickly check colors
            small_img = img.resize((32, 32))
            red_pixels = 0
            for pixel in small_img.getdata():
                # pixel is (R, G, B) or (R, G, B, A)
                r, g, b = pixel[0], pixel[1], pixel[2]
                if r > 180 and g < 60 and b < 60:  # Strong red
                    red_pixels += 1
            if red_pixels > 5:
                anomaly_detected = True
                anomaly_reason = "Significant red indicator blocks detected (potential crash or error modal)."
        except Exception:
            pass

        # 4. Formulate UI structure context
        layout_elements = self.ocr.extract_text_with_bounding_boxes(image_path)
        ui_components = []
        for el in layout_elements[:30]:  # Cap at 30 components for brevity
            ui_components.append(f"Text '{el['text']}' at position x={el['box']['x']}, y={el['box']['y']}")

        summary = (
            f"Image dimensions: {width}x{height}. "
            f"OCR detected {len(extracted_text.split())} words. "
            f"{len(detected_errors)} potential error/exception lines found."
        )

        return {
            "status": "ok",
            "summary": summary,
            "width": width,
            "height": height,
            "ocr_text": extracted_text,
            "detected_errors": detected_errors[:10],
            "anomaly_detected": anomaly_detected,
            "anomaly_reason": anomaly_reason,
            "ui_components": ui_components,
            "ocr_method": ocr_res.get("method", "unknown")
        }

    def explain_ui_screenshot(self, analysis_result: Dict[str, Any]) -> str:
        """Helper to explain the UI layout from screenshot analysis results."""
        ocr_txt = analysis_result.get("ocr_text", "")
        errors = analysis_result.get("detected_errors", [])
        
        explanation = f"🖥️ **Screenshot UI Analysis**, Sir:\n"
        explanation += f"- **Dimensions**: {analysis_result.get('width')}x{analysis_result.get('height')} pixels\n"
        
        if errors:
            explanation += f"- **Error Debugging Mode**: ⚠️ I detected active error text on the screen:\n"
            for err in errors[:5]:
                explanation += f"  - `{err}`\n"
        
        if analysis_result.get("anomaly_detected"):
            explanation += f"- **Visual Alert**: {analysis_result.get('anomaly_reason')}\n"
            
        if ocr_txt:
            explanation += f"- **Primary Text Content**:\n```\n{ocr_txt[:300]}...\n```\n"
        else:
            explanation += f"- **Text Content**: No readable text detected on screen.\n"
            
        return explanation
