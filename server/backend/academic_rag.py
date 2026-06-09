"""
VOID Academic RAG Engine
========================

Retrieval-Augmented Generation (RAG) system running 100% locally.
Chunks text documents, syllabus files, and lecture notes, building
a fast TF-IDF index in pure Python to support scalable academic tutoring.
"""

import os
import json
import re
import math
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Paths
ROOT_DIR = Path(__file__).parent.parent.parent
DOCS_DIR = ROOT_DIR / "memory" / "academic_documents"
CACHE_FILE = DOCS_DIR / "rag_index_cache.json"

class SimpleTFIDFIndex:
    """Pure-Python TF-IDF index for fast, zero-dependency chunk retrieval."""
    def __init__(self):
        self.documents: List[Dict[str, Any]] = [] # [{id, text, source, tokens}]
        self.vocab = set()
        self.df = {} # Document frequency
        self.doc_count = 0

    def tokenize(self, text: str) -> List[str]:
        # Lowercase and split on words
        words = re.findall(r'\b[a-z0-9]{3,20}\b', text.lower())
        # Filter basic stopwords
        stopwords = {
            'the', 'and', 'a', 'of', 'to', 'is', 'in', 'that', 'it', 'for', 'on', 'with', 
            'as', 'at', 'by', 'an', 'be', 'this', 'are', 'from', 'or', 'you', 'your', 'my'
        }
        return [w for w in words if w not in stopwords]

    def add_chunk(self, text: str, source: str):
        doc_id = len(self.documents)
        tokens = self.tokenize(text)
        if not tokens:
            return
            
        token_counts = {}
        for t in tokens:
            token_counts[t] = token_counts.get(t, 0) + 1
            self.vocab.add(t)
            
        self.documents.append({
            "id": doc_id,
            "text": text,
            "source": source,
            "counts": token_counts,
            "length": len(tokens)
        })

    def finalize(self):
        self.doc_count = len(self.documents)
        self.df = {}
        for doc in self.documents:
            unique_terms = set(doc["counts"].keys())
            for term in unique_terms:
                self.df[term] = self.df.get(term, 0) + 1

    def search(self, query: str, top_n: int = 3) -> List[Dict[str, Any]]:
        query_tokens = self.tokenize(query)
        if not query_tokens or not self.documents:
            return []
            
        scores = []
        for doc in self.documents:
            score = 0.0
            for term in query_tokens:
                if term in doc["counts"] and term in self.df:
                    # Term frequency (normalized by document length)
                    tf = doc["counts"][term] / doc["length"]
                    # Inverse document frequency
                    idf = math.log(1.0 + (self.doc_count / self.df[term]))
                    score += tf * idf
                    
            if score > 0:
                scores.append((doc, score))
                
        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scores[:top_n]]

# --- DOCUMENT PARSERS ---
def extract_text_from_file(file_path: Path) -> str:
    """Extracts raw text from a file. Handles text, md, json, and pdf (safely)."""
    ext = file_path.suffix.lower()
    
    if ext in [".txt", ".md", ".json"]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading {file_path.name}: {e}"
            
    elif ext == ".pdf":
        # Attempt to extract PDF text using PyPDF2 or pypdf
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            pages_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            return "\n\n".join(pages_text)
        except ImportError:
            # Fallback to PyPDF2 if installed
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(str(file_path))
                pages_text = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
                return "\n\n".join(pages_text)
            except Exception:
                return f"[PDF EXTRACTION FAIL] Please install 'pypdf' to index PDF documents: {file_path.name}"
        except Exception as e:
            return f"Error extracting PDF: {e}"
            
    elif ext == ".pptx":
        # Pure-Python zipfile extraction of PPTX slide paragraphs
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(str(file_path), 'r') as zip_ref:
                slide_texts = []
                slide_files = [f for f in zip_ref.namelist() if f.startswith('ppt/slides/slide')]
                
                # Sort numerically
                slide_files.sort(key=lambda x: [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', x)])
                
                for slide_file in slide_files:
                    slide_xml = zip_ref.read(slide_file)
                    root = ET.fromstring(slide_xml)
                    namespaces = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
                    texts = [node.text for node in root.findall('.//a:t', namespaces) if node.text]
                    if texts:
                        slide_texts.append(" ".join(texts))
                        
                return "\n\n--- Slide ---\n\n".join(slide_texts)
        except Exception as e:
            return f"Error extracting PPTX: {str(e)}"
            
    return ""

def generate_chunks(text: str, source_name: str, chunk_size: int = 700, overlap: int = 150) -> List[Dict[str, Any]]:
    """Chunks text into small overlapping paragraphs for precise RAG context injection."""
    chunks = []
    # Strip double spaces
    text_clean = re.sub(r'\s+', ' ', text).strip()
    
    start = 0
    while start < len(text_clean):
        end = start + chunk_size
        # Try to find a sentence boundary near chunk_size
        if end < len(text_clean):
            boundary = text_clean.rfind(". ", start, end)
            if boundary != -1 and boundary > start + chunk_size // 2:
                end = boundary + 1
                
        chunk_text = text_clean[start:end].strip()
        if len(chunk_text) > 40:
            chunks.append({
                "text": chunk_text,
                "source": source_name
            })
            
        start += (chunk_size - overlap)
        if start >= len(text_clean) - overlap:
            break
            
    return chunks

# --- CORE RAG INTERFACE ---
class RAGEngine:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RAGEngine, cls).__new__(cls)
            cls._instance.indexes = {} # subject_id -> SimpleTFIDFIndex
        return cls._instance

    def get_subject_paths(self, subject_id: str) -> Tuple[Path, Path]:
        """Returns subject-scoped document directory and cache file paths."""
        from tools.academic_progress import get_profile_value
        if not subject_id:
            subject_id = get_profile_value("current_subject", "dsa")
        subject_dir = DOCS_DIR / subject_id
        cache_file = subject_dir / "rag_index_cache.json"
        return subject_dir, cache_file

    def rebuild_index(self, subject_id: str = None):
        """Crawls subject-specific doc dir, parses files, creates chunk index, and saves to cache."""
        from tools.academic_progress import get_profile_value
        if not subject_id:
            subject_id = get_profile_value("current_subject", "dsa")
            
        subject_dir, cache_file = self.get_subject_paths(subject_id)
        subject_dir.mkdir(parents=True, exist_ok=True)
        
        index = SimpleTFIDFIndex()
        all_chunks = []
        # Support PDF, TXT, MD
        for ext in ["*.txt", "*.md", "*.pdf"]:
            for path in subject_dir.rglob(ext):
                if path.name == "rag_index_cache.json":
                    continue
                source_name = path.name
                content = extract_text_from_file(path)
                if content and "[PDF EXTRACTION FAIL]" not in content:
                    chunks = generate_chunks(content, source_name)
                    all_chunks.extend(chunks)
                    
        # Load chunks into search index
        for chunk in all_chunks:
            index.add_chunk(chunk["text"], chunk["source"])
            
        index.finalize()
        self.indexes[subject_id] = index
        
        # Save cache
        cache_data = {
            "documents": [
                {
                    "text": doc["text"],
                    "source": doc["source"],
                    "counts": doc["counts"],
                    "length": doc["length"]
                }
                for doc in index.documents
            ],
            "vocab": list(index.vocab),
            "df": index.df,
            "doc_count": index.doc_count
        }
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to cache RAG index for {subject_id}: {e}")

    def load_index(self, subject_id: str = None):
        """Loads search index from cache or rebuilds it if missing."""
        from tools.academic_progress import get_profile_value
        if not subject_id:
            subject_id = get_profile_value("current_subject", "dsa")
            
        if subject_id in self.indexes:
            return
            
        subject_dir, cache_file = self.get_subject_paths(subject_id)
        if not cache_file.exists():
            self.rebuild_index(subject_id)
            return
            
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                
            index = SimpleTFIDFIndex()
            index.vocab = set(cache_data["vocab"])
            index.df = cache_data["df"]
            index.doc_count = cache_data["doc_count"]
            
            for idx, doc in enumerate(cache_data["documents"]):
                index.documents.append({
                    "id": idx,
                    "text": doc["text"],
                    "source": doc["source"],
                    "counts": doc["counts"],
                    "length": doc["length"]
                })
            self.indexes[subject_id] = index
        except Exception as e:
            print(f"Failed to load RAG cache for {subject_id}, rebuilding: {e}")
            self.rebuild_index(subject_id)

    def retrieve_context(self, query: str, subject_id: str = None, count: int = 3) -> str:
        """Retrieves and formats the top N matching chunks for LLM injection."""
        from tools.academic_progress import get_profile_value
        if not subject_id:
            subject_id = get_profile_value("current_subject", "dsa")
            
        self.load_index(subject_id)
        index = self.indexes.get(subject_id)
        
        if not index or not index.documents:
            return f"No local reference context for {subject_id} available."
            
        matches = index.search(query, top_n=count)
        if not matches:
            return f"No local document reference context available for {subject_id} query."
            
        formatted_blocks = []
        for idx, doc in enumerate(matches):
            formatted_blocks.append(
                f"[Source Context #{idx+1} from '{doc['source']}']:\n{doc['text']}"
            )
        return "\n\n".join(formatted_blocks)
