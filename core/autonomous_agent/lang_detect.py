import os
import re
from typing import Optional

# Extension mappings to languages
EXT_MAPPING = {
    ".py": "Python",
    ".pyw": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".dart": "Dart",
    ".java": "Java",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".sql": "SQL",
    ".sh": "Bash",
    ".bash": "Bash",
}

SHEBANG_MAPPING = {
    r"^#!.*/python": "Python",
    r"^#!.*/node": "JavaScript",
    r"^#!.*/sh": "Bash",
    r"^#!.*/bash": "Bash",
}

def detect_language(file_path: str) -> str:
    """
    Detect the programming language of a file based on extension and content.
    Returns "Unknown" if the language cannot be identified.
    """
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    # 1. Match extension
    if ext in EXT_MAPPING:
        # Check if Dart is a Flutter project file
        if ext == ".dart":
            # If pubspec.yaml exists in the hierarchy, it's Flutter (Dart)
            # Otherwise it's Dart. Let's return "Flutter (Dart)" for .dart if we want
            # to distinguish, or just "Dart" / "Flutter (Dart)".
            # Let's detect if "flutter" dependency is in pubspec or treat all as Dart/Flutter.
            # The prompt requested: Dart, Flutter (Dart). So we can default to "Dart" and if we detect Flutter, "Flutter (Dart)".
            # We can check parent dirs for pubspec.yaml containing "flutter:"
            curr_dir = os.path.dirname(os.path.abspath(file_path))
            for _ in range(5): # Go up to 5 levels
                pubspec = os.path.join(curr_dir, "pubspec.yaml")
                if os.path.exists(pubspec):
                    try:
                        with open(pubspec, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            if "flutter:" in content:
                                return "Flutter (Dart)"
                    except Exception:
                        pass
                    break
                parent = os.path.dirname(curr_dir)
                if parent == curr_dir:
                    break
                curr_dir = parent
            return "Dart"
        return EXT_MAPPING[ext]
        
    # 2. Shebang matching for extensionless or script files
    if os.path.exists(file_path) and os.path.isfile(file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                first_line = f.readline().strip()
                if first_line.startswith("#!"):
                    for pattern, lang in SHEBANG_MAPPING.items():
                        if re.search(pattern, first_line):
                            return lang
        except Exception:
            pass
            
    return "Unknown"
