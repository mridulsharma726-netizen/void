"""
VOID Academic Intelligence Engine
=================================

Routes incoming academic commands and questions, queries RAG textbook context,
applies selected Teaching Modes, and parses Viva grading outputs.
"""

import logging
import re
import json
from typing import Dict, Any, Tuple
from backend.llm_client import OllamaClient
from backend.academic_rag import RAGEngine
from tools.academic_progress import (
    get_profile_value, set_profile_value, 
    record_viva_result, get_academic_summary
)

logger = logging.getLogger("void.academic_engine")

class AcademicEngine:
    """Orchestrates RAG indexing, active mode prompting, and grading execution."""

    SUBJECTS = {
        "maths": ["math", "mathematics", "calculus", "linear algebra", "matrices"],
        "business_stats": ["business stats", "business statistics", "correlation", "regression analysis"],
        "applied_stats": ["applied stats", "applied statistics", "hypothesis testing", "anova", "chi square"],
        "critical_thinking": ["critical thinking", "logic", "syllogism", "fallacy", "argumentation"],
        "c_programming": ["c programming", "pointers", "structs in c", "malloc", "gcc"],
        "python": ["python", "list comprehension", "decorators", "pandas", "numpy"],
        "oop": ["oop", "object oriented", "polymorphism", "inheritance", "encapsulation", "classes"],
        "dsa": ["dsa", "data structures", "algorithms", "stacks", "queues", "trees", "graphs", "sorting", "searching"],
        "dbms": ["database", "dbms", "sql", "normalization", "transactions", "acid", "indexing"],
        "adv_dbms": ["advanced database", "adv dbms", "distributed database", "nosql", "sharding"],
        "web_tech": ["web tech", "web technology", "html", "css", "javascript", "react", "node"],
        "os": ["operating systems", "os", "concurrency", "deadlock", "scheduling", "memory management", "paging"],
        "networks": ["networks", "computer networks", "tcp", "ip", "routing", "http", "dns", "layers"],
        "software_eng": ["software engineering", "sdlc", "agile", "uml", "design patterns", "testing"],
        "mobile_dev": ["mobile app", "mobile dev", "flutter", "react native", "android", "ios"],
        "ai_ml": ["ai", "ml", "machine learning", "neural network", "regression", "classification", "deep learning"],
        "ethical_hacking": ["ethical hacking", "cybersecurity", "penetration testing", "sql injection", "nmap", "wireshark"],
        "indian_constitution": ["constitution", "indian constitution", "preamble", "fundamental rights", "parliament"],
        "design_thinking": ["design thinking", "empathize", "ideate", "prototype", "user centric"],
        "analog_devices": ["analog", "analog devices", "diode", "transistor", "op amp", "amplifiers"]
    }

    MODE_PROMPTS = {
        "quick_answer": """
You are an Academic Tutor. Provide a direct, clear, and concise answer to the user's question.
If explaining a technical concept, include exactly one simple diagram or short code block.
Keep the answer under 150 words.
""",
        "teacher": """
You are a friendly, expert Professor. Break down the concept step-by-step:
1. Explain it using a simple real-world analogy.
2. Provide a clear, technical step-by-step breakdown.
3. Show a short, highly-commented code example or numerical application.
4. End with one quick multiple-choice question to test their understanding.
""",
        "practice": """
You are an Exam Coach. Generate exactly one challenging problem for the student to solve based on the topic.
Do NOT provide the solution or code in your message. Ask the student to reply with their solution.
""",
        "exam": """
You are a Strict External Viva Examiner. 
If the student is starting a new viva, ask them exactly one clear question to begin.
If they are answering a previous question, grade their answer out of 10.
You MUST output the grading tag exactly as: [VIVA SCORE: X/10] (where X is the integer score) followed by a 2-sentence explanation of what they missed, and then ask the NEXT question.
Keep the tone formal and academic.
""",
        "lab": """
You are a Lab Instructor. Provide a structured lab guide for this experiment:
1. Objective
2. Algorithm/Procedure
3. Completed code/commands with line-by-line comments
4. Expected Output
5. 3 troubleshooting tips for common compiler/runtime errors.
""",
        "roadmap": """
You are a Project Mentor. Generate a complete weekly roadmap study path.
Break down the topic into:
- Week 1: Core Fundamentals & Exercises
- Week 2: Practical Implementation & Mini Project
- Week 3: Interview questions & Placement preparation
Provide references to documentation or recommended studies.
"""
    }

    def detect_subject(self, text: str) -> str:
        """Heuristically detects which subject is active based on query text."""
        lower = text.lower()
        for subj, keywords in self.SUBJECTS.items():
            if any(kw in lower for kw in keywords):
                # Update current subject in database
                set_profile_value("current_subject", subj)
                return subj
        return get_profile_value("current_subject", "programming")

    def detect_mode(self, text: str) -> str:
        """Determines the active Teaching Mode based on triggers."""
        lower = text.lower()
        if any(kw in lower for kw in ["viva", "test me", "test my", "take a viva", "quiz me"]):
            return "exam"
        elif any(kw in lower for kw in ["teach me", "explain", "lesson"]):
            return "teacher"
        elif any(kw in lower for kw in ["practice", "exercise", "question for me"]):
            return "practice"
        elif any(kw in lower for kw in ["lab", "experiment"]):
            return "lab"
        elif any(kw in lower for kw in ["roadmap", "path", "roadmap study"]):
            return "roadmap"
        return "quick_answer"

    async def execute_query(self, query_text: str) -> Dict[str, Any]:
        """Main entry point. Queries RAG context and runs Ollama with mode system prompts."""
        subject = self.detect_subject(query_text)
        mode = self.detect_mode(query_text)
        
        # 1. Retrieve local document context (RAG)
        rag_engine = RAGEngine()
        context = rag_engine.retrieve_context(query_text, subject_id=subject, count=3)
        
        # 2. Get learning statistics
        stats = get_academic_summary()
        stats_str = (
            f"Current Subject: {stats['current_subject']}\n"
            f"Active Chapter/Topic: {stats['current_chapter']}\n"
            f"Completed Topics: {stats['completed_count']}\n"
            f"Current Knowledge Gaps: {', '.join(stats['weak_areas']) if stats['weak_areas'] else 'None'}"
        )
        
        # 3. Assemble system instructions
        base_prompt = self.MODE_PROMPTS.get(mode, self.MODE_PROMPTS["quick_answer"])
        system_instruction = f"""
{base_prompt}

Local Reference Document Context:
{context}

Student Profile & Stats:
{stats_str}

Remember: Be encouraging and clear. If they perform poorly in exam mode, tell them the correct step.
"""
        
        try:
            llm = OllamaClient()
            # Set the custom instruction as history to inject system prompt
            history = [{"role": "system", "content": system_instruction}]
            reply = await llm.chat(history, query_text)
            
            # 4. Check if we need to parse and record a viva score
            meta = {
                "intent": "academic",
                "subject": subject,
                "mode": mode
            }
            
            score_match = re.search(r'\[VIVA SCORE:\s*(\d+(?:\.\d+)?)/10\]', reply)
            if score_match:
                score = float(score_match.group(1))
                # Record result in database
                record_viva_result(subject, stats['current_chapter'], score, reply)
                meta["viva_score"] = score
                
                # Strip out the ugly formatting tags for a premium display
                reply = re.sub(r'\[VIVA SCORE:\s*\d+(?:\.\d+)?/10\]', f"⭐ **Score: {score}/10**", reply)
                
            # Update chapter name if user explicitly specified one
            chapter_match = re.search(r'(?:chapter|topic)\s+([a-zA-Z0-9_\-\s]+)', query_text, re.I)
            if chapter_match:
                new_chapter = chapter_match.group(1).strip()
                set_profile_value("current_chapter", new_chapter)
                
            return {
                "reply": reply,
                "meta": meta
            }
        except Exception as e:
            logger.error(f"Academic Engine query fail: {e}", exc_info=True)
            return {
                "reply": "I couldn't query the academic tutoring core. Check local model connection, Sir.",
                "meta": {"error": str(e)}
            }
