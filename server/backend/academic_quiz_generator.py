"""
VOID Academic Testing & Adaptive Quiz Generator
================================================

Generates structured assessments (Easy, Medium, Hard, Adaptive) including multiple-choice quizzes,
interactive Vivas, assignments, and timed Mock Exams. Evaluates results via LLM.
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional
from backend.llm_client import OllamaClient
from backend.academic_rag import RAGEngine

logger = logging.getLogger("void.academic_quiz")

class QuizGenerator:
    """Orchestrates quiz building, question pooling, and automated grading."""

    def __init__(self):
        self.llm = OllamaClient()

    async def generate_quiz(self, subject_id: str, topic_id: str, difficulty: str = "Medium", count: int = 5) -> List[Dict[str, Any]]:
        """Generates a multiple-choice quiz based on RAG context and active difficulty."""
        # 1. Retrieve RAG context to ensure factual alignment
        rag = RAGEngine()
        context = rag.retrieve_context(f"Concepts definitions examples and practices on {topic_id}", subject_id, count=3)
        
        prompt = f"""
You are an Academic Examiner. Generate a multiple-choice quiz about the topic "{topic_id}" for the subject "{subject_id}".
Generate exactly {count} high-quality questions matching the difficulty level: **"{difficulty}"**.

Difficulty level definitions:
- Easy: Basic terminology, simple syntax, direct recall.
- Medium: Conceptual debugging, tracing small loops/equations, code snippets.
- Hard: Algorithmic complexity, edge-case optimization, structural code architecture.
- Exam Level: Standard university exam style covering deep concepts.
- Interview Level: Data structures, algorithms, runtime tradeoffs, and whiteboard logic.

Output the quiz strictly as a JSON array of questions, formatted like this:
[
  {{
    "id": 1,
    "text": "Question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_option": "The exact matching correct option string",
    "explanation": "One-sentence explanation of why this option is correct."
  }},
  ...
]

Do not include any markup, greetings, or backticks. Output only the raw JSON.

Local Reference Context:
{context}
"""
        try:
            resp = await self.llm.chat([], prompt)
            resp_clean = re.sub(r'```json\s*|\s*```', '', resp).strip()
            json_match = re.search(r'\[\s*\{.*\}\s*\]', resp_clean, re.DOTALL)
            if json_match:
                resp_clean = json_match.group(0)
            
            questions = json.loads(resp_clean)
            return questions
        except Exception as e:
            logger.error(f"Failed to generate quiz: {e}", exc_info=True)
            # Hardcoded fallback questions to prevent crash if Ollama breaks
            return [
                {
                    "id": 1,
                    "text": f"What is the core definition of {topic_id.title()}?",
                    "options": ["A fundamental construct", "A secondary option", "An error indicator", "None of the above"],
                    "correct_option": "A fundamental construct",
                    "explanation": f"The core component represents the fundamental baseline of {topic_id}."
                }
            ]

    async def generate_viva_question(self, subject_id: str, topic_id: str, previous_answers_summary: str = "") -> Dict[str, Any]:
        """Generates a single open-ended Viva question, factoring in previous answers if any."""
        rag = RAGEngine()
        context = rag.retrieve_context(f"Core technical questions about {topic_id}", subject_id, count=2)
        
        prompt = f"""
You are a Strict External Viva Examiner. Ask the student one challenging, conceptual, open-ended question about "{topic_id}" in "{subject_id}".
Keep the question short, specific, and academic. Do not use multiple-choice format.
If the user has completed previous steps, here is the context: {previous_answers_summary or 'Starting new viva.'}

Output the response strictly as a JSON object:
{{
  "question": "The question string",
  "expected_keywords": ["keyword1", "keyword2", "keyword3"],
  "focus_area": "E.g., Time complexity"
}}

Do not use formatting markup. Output raw JSON.

Local context:
{context}
"""
        try:
            resp = await self.llm.chat([], prompt)
            resp_clean = re.sub(r'```json\s*|\s*```', '', resp).strip()
            json_match = re.search(r'\{\s*"question".*\}', resp_clean, re.DOTALL)
            if json_match:
                resp_clean = json_match.group(0)
            return json.loads(resp_clean)
        except Exception as e:
            logger.error(f"Failed to generate viva: {e}")
            return {
                "question": f"Explain the practical significance and common design patterns of {topic_id}.",
                "expected_keywords": [topic_id, "efficiency", "structure"],
                "focus_area": "General Concept"
            }

    async def evaluate_open_ended_response(self, subject_id: str, topic_id: str, question: str, response_text: str) -> Dict[str, Any]:
        """Evaluates an open-ended Viva or assignment answer, returning score (0-10) and feedback."""
        prompt = f"""
You are an Academic Grader. Evaluate the student's answer to the exam question below.
Subject: {subject_id}
Topic: {topic_id}
Question: {question}
Student's Answer: "{response_text}"

Grade their answer strictly out of 10. Be constructive but maintain academic standards.
Output your grading strictly as a JSON object:
{{
  "score": 8.5,
  "feedback": "Two-sentence summary of what they did well and what they missed.",
  "correct_components": ["Point A", "Point B"],
  "missing_components": ["Point C"],
  "passed": true
}}

Ensure "passed" is true if score >= 6.0, false otherwise. Output raw JSON.
"""
        try:
            resp = await self.llm.chat([], prompt)
            resp_clean = re.sub(r'```json\s*|\s*```', '', resp).strip()
            json_match = re.search(r'\{\s*"score".*\}', resp_clean, re.DOTALL)
            if json_match:
                resp_clean = json_match.group(0)
            return json.loads(resp_clean)
        except Exception as e:
            logger.error(f"Grader evaluation failed: {e}")
            return {
                "score": 5.0,
                "feedback": "Evaluation failed due to LLM error. Standard baseline check required, Sir.",
                "correct_components": [],
                "missing_components": ["Check local system logs."],
                "passed": False
            }
