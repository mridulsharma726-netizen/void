import re
from pathlib import Path
from typing import Dict, Any, List
from server.backend.academic_rag import extract_text_from_file

class TextbookExtractor:
    def __init__(self):
        # Formula matching: LaTeX formats or common mathematical signs
        self.formula_patterns = [
            r"\$\$.*?\$\$",                       # block LaTeX
            r"\$.*?\$",                           # inline LaTeX
            r"\b[A-Za-z_]+\s*=\s*[-+]?\d*\.?\d+(?:\s*[+\-*/]\s*[A-Za-z_0-9]+)*", # simple assignment equations
            r"\b[E|e]\s*=\s*[m|M][c|C]\^2",       # E=mc^2
            r"\\sum_.*?^.*?",                    # sums
            r"\b[a-z0-9]+\^2\s*\+\s*[a-z0-9]+\^2\s*=\s*[a-z0-9]+\^2"  # pythagorean
        ]
        
        # Chapter pattern matching
        self.chapter_patterns = [
            r"(?:Chapter|CHAPTER|Unit|UNIT|Module|MODULE)\s+(?:\d+|[IVXLCDM]+)[\s:-]+([^\n]+)",
            r"^\s*(?:\d+\.\d+)\s+([A-Z][A-Za-z\s]+)$"
        ]
        
        # Concept matching: words in bold, quotes, or followed by "is defined as" or "refers to"
        self.concept_patterns = [
            r"\*\*(.*?)\*\*",
            r"\"([A-Z][A-Za-z\s]{3,30})\"",
            r"\b([A-Z][A-Za-z\s]{3,30})\s+(?:is\s+defined\s+as|refers\s+to|means)\b"
        ]

    def extract(self, file_path: str) -> Dict[str, Any]:
        """
        Parses text/PDF file and returns extracted chapters, formulas, concepts, and topics.
        """
        path = Path(file_path)
        if not path.exists():
            return {"status": "error", "message": f"File {file_path} not found."}

        text = extract_text_from_file(path)
        if not text:
            return {"status": "error", "message": "No text content extracted."}

        # 1. Extract Chapters
        chapters = []
        for pattern in self.chapter_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for m in matches:
                title = m.group(0).strip()
                if title not in chapters:
                    chapters.append(title)

        # 2. Extract Formulas
        formulas = []
        for pattern in self.formula_patterns:
            matches = re.finditer(pattern, text)
            for m in matches:
                expr = m.group(0).strip()
                if expr not in formulas:
                    formulas.append(expr)

        # 3. Extract Concepts
        concepts = []
        for pattern in self.concept_patterns:
            matches = re.finditer(pattern, text)
            for m in matches:
                term = m.group(1).strip()
                if len(term) > 3 and term not in concepts:
                    concepts.append(term)

        # 4. Extract Topics
        # General topics can be mapped from section headers (e.g. markdown headers)
        topics = []
        header_matches = re.finditer(r"^##\s+(.+)$", text, re.MULTILINE)
        for m in header_matches:
            topic = m.group(1).strip()
            if topic not in topics:
                topics.append(topic)

        return {
            "status": "ok",
            "filename": path.name,
            "chapters_count": len(chapters),
            "chapters": chapters[:25],
            "formulas_count": len(formulas),
            "formulas": formulas[:20],
            "concepts_count": len(concepts),
            "concepts": concepts[:30],
            "topics_count": len(topics),
            "topics": topics[:25]
        }
