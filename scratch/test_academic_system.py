import sys
import os
import asyncio

# Setup paths
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT)
sys.path.append(os.path.join(ROOT, "server"))

from tools.academic_progress import (
    init_db, set_profile_value, get_profile_value, 
    mark_topic_completed, record_knowledge_gap, 
    record_viva_result, get_academic_summary, get_completed_topics
)
from server.backend.intent_router import IntentRouter
from server.backend.academic_rag import RAGEngine, generate_chunks

async def test_academic_db():
    print("=== Testing Academic Progress SQL DB ===")
    init_db()
    
    # Test profile keys
    set_profile_value("current_subject", "dsa")
    set_profile_value("current_chapter", "red_black_trees")
    print(f"  Profile Subject: {get_profile_value('current_subject')}")
    print(f"  Profile Chapter: {get_profile_value('current_chapter')}")
    
    # Test completed topics
    mark_topic_completed("dsa", "arrays", 5)
    mark_topic_completed("dsa", "linked_lists", 4)
    completed = get_completed_topics("dsa")
    print(f"  Completed Topics: {[c['topic_id'] for c in completed]}")
    
    # Test knowledge gap logging
    record_knowledge_gap("dsa", "graphs", "High")
    record_knowledge_gap("dsa", "graphs", "High") # Increment
    
    # Test viva score evaluation
    record_viva_result("dsa", "red_black_trees", 8.5, "Good understanding of balance rotations.")
    record_viva_result("dsa", "heaps", 4.0, "Failed to explain heapify complexity.") # Should create a knowledge gap
    
    summary = get_academic_summary()
    print("  Dashboard Summary:")
    print(f"    Active Subject: {summary['current_subject']}")
    print(f"    Completed count: {summary['completed_count']}")
    print(f"    Gaps count: {summary['gaps_count']}")
    print(f"    Vivas taken: {summary['vivas_taken']}")
    print(f"    Average Score: {summary['average_score']}")
    print(f"    Weak Areas: {summary['weak_areas']}")
    print()

async def test_intent_routing():
    print("=== Testing Academic Intent Routing ===")
    router = IntentRouter()
    
    queries = [
        "viva me on python",
        "teach me operating systems scheduling",
        "DBMS normalization procedure lab experiment",
        "show my study roadmap for AI ML",
        "what is polymorphism?", # Normal quick academic answer
        "hello void how are you?" # Normal chat (should bypass)
    ]
    
    for q in queries:
        res = await router.classify(q)
        print(f"  Query: \"{q}\"")
        print(f"    -> Intent: {res.intent}")
    print()

async def test_tfidf_rag():
    print("=== Testing TF-IDF Chunk RAG Engine ===")
    sample_text = (
        "Operating systems coordinate system hardware. Process scheduling is critical. "
        "Shortest Job First (SJF) is a scheduling algorithm that selects the process "
        "with the smallest execution time. Paging is a memory management scheme that "
        "eliminates the need for contiguous allocation of physical memory."
    )
    
    # Check chunks generator
    chunks = generate_chunks(sample_text, "test_doc.txt", chunk_size=150, overlap=30)
    print(f"  Generated {len(chunks)} chunks from sample text:")
    for i, c in enumerate(chunks[:2]):
        print(f"    Chunk #{i+1}: \"{c['text']}\"")
        
    engine = RAGEngine()
    # Mock documents list for indexing
    from server.backend.academic_rag import SimpleTFIDFIndex
    index = SimpleTFIDFIndex()
    index.add_chunk("Shortest Job First is a CPU scheduling algorithm.", "scheduling.txt")
    index.add_chunk("Paging manages physical memory in contiguous chunks.", "memory.txt")
    index.finalize()
    engine.indexes["dsa"] = index
    engine.loaded = True
    
    res = engine.retrieve_context("Tell me about CPU scheduling algorithms")
    print("\n  RAG Query Match:")
    print(res)
    print()

async def main():
    await test_academic_db()
    await test_intent_routing()
    await test_tfidf_rag()

if __name__ == "__main__":
    asyncio.run(main())
