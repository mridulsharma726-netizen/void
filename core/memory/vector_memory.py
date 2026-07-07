"""
VOID Local Vector Memory & RAG Module
====================================

Manages persistent semantic indexing of conversations and facts completely offline
using LanceDB and a local sentence-transformers model running on CPU.
"""

import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("void.core.memory.vector_memory")

# Fallback indicators
LANCEDB_AVAILABLE = False
SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import lancedb
    LANCEDB_AVAILABLE = True
except ImportError:
    logger.warning("[VECTOR MEMORY] lancedb not installed. Degrading to mock vector storage.")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    logger.warning("[VECTOR MEMORY] sentence-transformers not installed. Degrading to mock embeddings.")

# Paths
ROOT_DIR = Path(__file__).parent.parent.parent
DB_DIR = ROOT_DIR / "memory" / "data" / "lancedb"
MODEL_DIR = ROOT_DIR / "memory" / "data" / "models" / "all-MiniLM-L6-v2"

# Embedding model singleton
_model_instance: Optional[Any] = None

def get_embedding_model() -> Optional[Any]:
    """Retrieves or loads the local embedding model on CPU."""
    global _model_instance
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        return None
        
    if _model_instance is not None:
        return _model_instance
        
    try:
        start_time = time.perf_counter()
        if MODEL_DIR.exists() and any(MODEL_DIR.iterdir()):
            logger.info(f"[VECTOR MEMORY] Loading local embedding model from: {MODEL_DIR}")
            _model_instance = SentenceTransformer(str(MODEL_DIR), device="cpu")
        else:
            logger.info(f"[VECTOR MEMORY] Local model folder empty. Downloading all-MiniLM-L6-v2...")
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
            model.save(str(MODEL_DIR))
            _model_instance = model
            
        latency = (time.perf_counter() - start_time) * 1000.0
        logger.info(f"[VECTOR MEMORY] Model loaded in {latency:.2f}ms.")
        return _model_instance
    except Exception as e:
        logger.error(f"[VECTOR MEMORY] Failed to load embedding model: {e}")
        return None

class VectorMemory:
    """Handles semantic memory insertions and queries via LanceDB."""
    
    def __init__(self):
        self.db = None
        self.conv_table = None
        self.facts_table = None
        
        if not LANCEDB_AVAILABLE:
            logger.warning("[VECTOR MEMORY] Initializing in degraded/mock mode.")
            return
            
        try:
            DB_DIR.mkdir(parents=True, exist_ok=True)
            self.db = lancedb.connect(str(DB_DIR))
            
            # Setup tables
            self._ensure_tables()
        except Exception as e:
            logger.error(f"[VECTOR MEMORY] Failed to connect to LanceDB: {e}")
            self.db = None

    def _ensure_tables(self):
        if not self.db:
            return
            
        # 384 dimensions for all-MiniLM-L6-v2
        dim = 384
        empty_vector = [0.0] * dim
        
        # 1. Conversations table
        if "conversations" not in self.db.table_names():
            logger.info("[VECTOR MEMORY] Creating conversations table...")
            self.db.create_table(
                "conversations",
                data=[{
                    "id": 0,
                    "role": "system",
                    "content": "initialization placeholder",
                    "timestamp": str(time.time()),
                    "vector": empty_vector
                }]
            )
        self.conv_table = self.db.open_table("conversations")
        
        # 2. Facts table
        if "facts" not in self.db.table_names():
            logger.info("[VECTOR MEMORY] Creating facts table...")
            self.db.create_table(
                "facts",
                data=[{
                    "id": 0,
                    "fact": "initialization placeholder",
                    "timestamp": str(time.time()),
                    "vector": empty_vector
                }]
            )
        self.facts_table = self.db.open_table("facts")

    def get_embedding(self, text: str) -> List[float]:
        """Generates a text embedding vector. Benchmarks and logs latency."""
        model = get_embedding_model()
        if not model:
            return [0.0] * 384
            
        try:
            start_time = time.perf_counter()
            # Encode on CPU
            vector = model.encode(text, convert_to_numpy=True).tolist()
            latency = (time.perf_counter() - start_time) * 1000.0
            logger.debug(f"[VECTOR MEMORY] Embedding generated in {latency:.2f}ms for text length {len(text)}")
            return vector
        except Exception as e:
            logger.error(f"[VECTOR MEMORY] Embedding generation failed: {e}")
            return [0.0] * 384

    def add_interaction(self, msg_id: int, role: str, content: str, timestamp: str = None) -> bool:
        """Add a conversation turn to the LanceDB index."""
        if not self.db or not self.conv_table:
            return False
            
        try:
            ts = timestamp or str(time.time())
            vector = self.get_embedding(content)
            self.conv_table.add([{
                "id": msg_id,
                "role": role,
                "content": content,
                "timestamp": ts,
                "vector": vector
            }])
            logger.info(f"[VECTOR MEMORY] Indexed interaction ID {msg_id}")
            return True
        except Exception as e:
            logger.error(f"[VECTOR MEMORY] Failed to index interaction {msg_id}: {e}")
            return False

    def add_fact(self, fact_id: int, fact: str, timestamp: str = None) -> bool:
        """Add a general fact to the LanceDB index."""
        if not self.db or not self.facts_table:
            return False
            
        try:
            ts = timestamp or str(time.time())
            vector = self.get_embedding(fact)
            self.facts_table.add([{
                "id": fact_id,
                "fact": fact,
                "timestamp": ts,
                "vector": vector
            }])
            logger.info(f"[VECTOR MEMORY] Indexed fact ID {fact_id}")
            return True
        except Exception as e:
            logger.error(f"[VECTOR MEMORY] Failed to index fact {fact_id}: {e}")
            return False

    def query_similar_conversations(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Find top-k relevant past conversation interactions."""
        if not self.db or not self.conv_table:
            return []
            
        try:
            vector = self.get_embedding(query)
            # Search using cosine distance (LanceDB's search handles L2/cosine, default L2)
            results = self.conv_table.search(vector).limit(limit + 1).to_list()
            # Filter placeholder entry with ID 0
            filtered = [r for r in results if r["id"] != 0][:limit]
            return filtered
        except Exception as e:
            logger.error(f"[VECTOR MEMORY] Conversation search failed: {e}")
            return []

    def query_similar_facts(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Find top-k relevant facts."""
        if not self.db or not self.facts_table:
            return []
            
        try:
            vector = self.get_embedding(query)
            results = self.facts_table.search(vector).limit(limit + 1).to_list()
            filtered = [r for r in results if r["id"] != 0][:limit]
            return filtered
        except Exception as e:
            logger.error(f"[VECTOR MEMORY] Facts search failed: {e}")
            return []

    def retrieve_context(self, query: str, limit: int = 3) -> str:
        """Retrieves and formats unified semantic context for injection into LLM prompts."""
        if not LANCEDB_AVAILABLE or not SENTENCE_TRANSFORMERS_AVAILABLE:
            return ""
            
        facts = self.query_similar_facts(query, limit=limit)
        convs = self.query_similar_conversations(query, limit=limit)
        
        context_parts = []
        
        if facts:
            context_parts.append("### Relevant Memory Facts:")
            for f in facts:
                context_parts.append(f"- {f['fact']}")
                
        if convs:
            context_parts.append("### Relevant Past Interactions:")
            for c in convs:
                # Format turn
                context_parts.append(f"- **{c['role'].capitalize()}**: {c['content']}")
                
        if context_parts:
            return "\n".join(context_parts)
            
        return ""

# Singleton instance
_vector_mem_instance: Optional[VectorMemory] = None

def get_vector_memory() -> VectorMemory:
    """Returns singleton instance of VectorMemory."""
    global _vector_mem_instance
    if _vector_mem_instance is None:
        _vector_mem_instance = VectorMemory()
    return _vector_mem_instance
