import os
import sys
import shutil
import unittest
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
if str(ROOT_DIR / "server") not in sys.path:
    sys.path.append(str(ROOT_DIR / "server"))

from core.memory.vector_memory import VectorMemory, get_vector_memory, MODEL_DIR, DB_DIR

class TestPhase8VectorMemory(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Ensure model is downloaded/loaded once for tests
        cls.vmem = get_vector_memory()
        
    def setUp(self):
        # We will use a separate test db directory to avoid modifying production data
        self.test_db_dir = ROOT_DIR / "memory" / "data" / "lancedb_test"
        if self.test_db_dir.exists():
            shutil.rmtree(self.test_db_dir)
            
        import lancedb
        self.db = lancedb.connect(str(self.test_db_dir))
        
        # Initialize test tables
        dim = 384
        empty_vector = [0.0] * dim
        
        self.db.create_table(
            "conversations",
            data=[{
                "id": 0,
                "role": "system",
                "content": "initialization placeholder",
                "timestamp": "0.0",
                "vector": empty_vector
            }]
        )
        self.db.create_table(
            "facts",
            data=[{
                "id": 0,
                "fact": "initialization placeholder",
                "timestamp": "0.0",
                "vector": empty_vector
            }]
        )
        
        # Patch the VectorMemory instance to use test DB
        self.vmem.db = self.db
        self.vmem.conv_table = self.db.open_table("conversations")
        self.vmem.facts_table = self.db.open_table("facts")

    def tearDown(self):
        # Close connection and clean up
        if hasattr(self, "db") and self.db:
            # LanceDB connection doesn't require explicit close in simple modes
            pass
        if self.test_db_dir.exists():
            try:
                shutil.rmtree(self.test_db_dir)
            except Exception:
                pass
                
        # Restore production VectorMemory (re-instantiate or re-connect)
        import core.memory.vector_memory as vm
        vm._vector_mem_instance = None

    def test_embedding_generation(self):
        """Verify that embeddings are generated with correct dimension (384)."""
        text = "Hello VOID, remember that my favorite language is Python."
        emb = self.vmem.get_embedding(text)
        self.assertEqual(len(emb), 384)
        self.assertIsInstance(emb, list)
        self.assertIsInstance(emb[0], float)

    def test_insertion_and_retrieval(self):
        """Verify that conversation turns and facts can be inserted and retrieved."""
        # Insert a fact
        success_fact = self.vmem.add_fact(1, "The user lives in New York.")
        self.assertTrue(success_fact)
        
        # Insert an interaction
        success_conv = self.vmem.add_interaction(1, "user", "I want to deploy a Python app.", "123456.0")
        self.assertTrue(success_conv)
        
        # Query similar facts
        similar_facts = self.vmem.query_similar_facts("Where does the user live?")
        self.assertEqual(len(similar_facts), 1)
        self.assertEqual(similar_facts[0]["id"], 1)
        self.assertEqual(similar_facts[0]["fact"], "The user lives in New York.")
        
        # Query similar conversations
        similar_convs = self.vmem.query_similar_conversations("deploying an application")
        self.assertEqual(len(similar_convs), 1)
        self.assertEqual(similar_convs[0]["id"], 1)
        self.assertEqual(similar_convs[0]["content"], "I want to deploy a Python app.")

    def test_retrieval_accuracy(self):
        """Verify that cosine similarity retrieval selects the most semantically relevant text."""
        self.vmem.add_fact(1, "Python is a high-level programming language.")
        self.vmem.add_fact(2, "Pizza is a delicious Italian dish.")
        self.vmem.add_fact(3, "Submarines travel deep under the ocean.")
        
        # Query for coding
        results_code = self.vmem.query_similar_facts("programming languages and coding", limit=1)
        self.assertEqual(results_code[0]["id"], 1)
        
        # Query for food
        results_food = self.vmem.query_similar_facts("what food should I eat?", limit=1)
        self.assertEqual(results_food[0]["id"], 2)

    def test_graceful_degradation_corrupted(self):
        """Verify graceful degradation when LanceDB database is corrupted/empty/missing."""
        # Set database to None (simulate corruption or connection error)
        self.vmem.db = None
        self.vmem.conv_table = None
        self.vmem.facts_table = None
        
        # Operations should return gracefully instead of crashing
        success_fact = self.vmem.add_fact(1, "This should fail gracefully.")
        self.assertFalse(success_fact)
        
        results_facts = self.vmem.query_similar_facts("some query")
        self.assertEqual(results_facts, [])
        
        context = self.vmem.retrieve_context("some query")
        self.assertEqual(context, "")

if __name__ == "__main__":
    unittest.main()
