import os
import sys
import json
import unittest
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent

class TestPhase12Packaging(unittest.TestCase):
    
    def test_electron_builder_config(self):
        """Verify that electron-builder is configured correctly in package.json."""
        pkg_json_path = ROOT_DIR / "desktop" / "package.json"
        self.assertTrue(pkg_json_path.exists(), "desktop/package.json does not exist")
        
        with open(pkg_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.assertIn("build", data)
        build_cfg = data["build"]
        self.assertEqual(build_cfg.get("appId"), "com.void.desktop")
        self.assertEqual(build_cfg.get("productName"), "VOID")
        self.assertIn("win", build_cfg)
        self.assertEqual(build_cfg["win"].get("target"), "nsis")

    def test_local_assets_containment(self):
        """Confirm that CodeMirror files exist locally in the UI folder."""
        cm_dir = ROOT_DIR / "app" / "ui" / "lib" / "codemirror"
        self.assertTrue(cm_dir.exists(), "CodeMirror lib folder is missing")
        
        expected_files = [
            "codemirror.min.css",
            "dracula.min.css",
            "codemirror.min.js",
            "javascript.min.js",
            "python.min.js",
            "xml.min.js",
            "css.min.js"
        ]
        
        for name in expected_files:
            file_path = cm_dir / name
            self.assertTrue(file_path.exists(), f"Missing local CodeMirror asset: {name}")
            self.assertGreater(file_path.stat().st_size, 0, f"Local CodeMirror asset is empty: {name}")

    def test_no_cdn_references(self):
        """Confirm that app/ui/index.html has zero CDN dependencies for scripts or styles."""
        html_path = ROOT_DIR / "app" / "ui" / "index.html"
        self.assertTrue(html_path.exists(), "app/ui/index.html is missing")
        
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Ensure CodeMirror is not loaded from cdnjs
        self.assertNotIn("https://cdnjs.cloudflare.com", content, "Found external CDN reference to cdnjs in index.html")
        self.assertNotIn("unpkg.com", content, "Found external CDN reference to unpkg in index.html")
        
        # Verify local script references are present
        self.assertIn("lib/codemirror/codemirror.min.js", content)
        self.assertIn("lib/codemirror/javascript.min.js", content)

    def test_no_external_font_cdn(self):
        """Confirm that no googleapis.com / gstatic.com / any external host string appears in index.html or loaded CSS."""
        html_path = ROOT_DIR / "app" / "ui" / "index.html"
        self.assertTrue(html_path.exists(), "app/ui/index.html is missing")
        
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        self.assertNotIn("googleapis.com", content, "Found external Google Fonts API reference in index.html")
        self.assertNotIn("gstatic.com", content, "Found external Google Fonts Static reference in index.html")
        
        # Also check local fonts.css
        css_path = ROOT_DIR / "app" / "ui" / "lib" / "fonts" / "fonts.css"
        self.assertTrue(css_path.exists(), "Local fonts.css is missing")
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
        self.assertNotIn("googleapis.com", css_content, "Found external Google Fonts API reference in fonts.css")
        self.assertNotIn("gstatic.com", css_content, "Found external Google Fonts Static reference in fonts.css")

if __name__ == "__main__":
    unittest.main()

