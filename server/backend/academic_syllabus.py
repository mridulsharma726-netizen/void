"""
VOID Academic Curriculum Builder & Syllabus Generator
======================================================

Generates a structured syllabus (Units -> Chapters -> Subtopics) for any subject,
runs Deep Research, saves study material, and populates the local RAG database.
"""

import asyncio
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, List
from backend.llm_client import OllamaClient
from backend.deep_research import ResearchManager
from backend.academic_rag import RAGEngine
from tools.academic_progress import save_curriculum, SUPPORTED_SUBJECTS

logger = logging.getLogger("void.academic_syllabus")

# Dynamic state tracked by frontend
ACTIVE_ACADEMIC_RESEARCH = {
    "active": False,
    "subject_id": "",
    "status": "Idle",
    "logs": []
}

async def update_research_progress(subject_id: str, status: str, log_msg: str = None):
    global ACTIVE_ACADEMIC_RESEARCH
    ACTIVE_ACADEMIC_RESEARCH["active"] = True
    ACTIVE_ACADEMIC_RESEARCH["subject_id"] = subject_id
    ACTIVE_ACADEMIC_RESEARCH["status"] = status
    if log_msg:
        ACTIVE_ACADEMIC_RESEARCH["logs"].append(log_msg)
        logger.info(f"[ACAD RESEARCH: {subject_id}] {log_msg}")

async def build_subject_curriculum(subject_id: str) -> Dict[str, Any]:
    """Runs deep research, maps structured syllabus, writes text files, and indices RAG."""
    global ACTIVE_ACADEMIC_RESEARCH
    
    subject_name = SUPPORTED_SUBJECTS.get(subject_id)
    if not subject_name:
        subject_name = subject_id.replace("_", " ").title()
        
    ACTIVE_ACADEMIC_RESEARCH["logs"] = []
    await update_research_progress(subject_id, "Initializing", f"Starting deep research for {subject_name}...")
    
    try:
        # Step 1: Run Deep Research to generate a complete report
        await update_research_progress(subject_id, "Deep Researching", "Gathering internet & academic references...")
        research_mgr = ResearchManager()
        # Since ResearchManager runs a long-running crawler, we await it
        report = await research_mgr.run_workflow(subject_name)
        
        # Save report to docs folder
        docs_dir = Path(__file__).parent.parent.parent / "memory" / "academic_documents" / subject_id
        docs_dir.mkdir(parents=True, exist_ok=True)
        report_path = docs_dir / "deep_research_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        await update_research_progress(subject_id, "Deep Researching", f"Saved deep research report to {report_path.name}")
        
        # Step 2: Use LLM to structure a formal syllabus matching the findings
        await update_research_progress(subject_id, "Mapping Syllabus", "Generating curriculum units, chapters, and subtopics...")
        llm = OllamaClient()
        
        syllabus_prompt = f"""
You are an Academic Director. Map out a formal university syllabus for the subject '{subject_name}' based on modern academic curricula.
The syllabus MUST contain exactly 4 Units, and each Unit MUST contain exactly 3 Chapters.
For each Chapter, specify a list of exactly 4 detailed Subtopics.

Output the curriculum strictly as a JSON object of this format:
{{
  "units": [
    {{
      "unit_title": "Unit 1: [Title]",
      "chapters": [
        {{
          "chapter_title": "Chapter 1: [Title]",
          "subtopics": ["Subtopic A", "Subtopic B", "Subtopic C", "Subtopic D"]
        }},
        ...
      ]
    }},
    ...
  ]
}}

Output ONLY the raw JSON block. No introductory remarks, no greetings, no backticks or markdown containers.
"""
        resp = await llm.chat([], syllabus_prompt)
        # Parse JSON from response
        resp_clean = re.sub(r'```json\s*|\s*```', '', resp).strip()
        json_match = re.search(r'\{\s*"units".*\}', resp_clean, re.DOTALL)
        if json_match:
            resp_clean = json_match.group(0)
            
        curriculum_data = json.loads(resp_clean)
        units = curriculum_data.get("units", [])
        
        # Save structured curriculum to SQLite database
        save_curriculum(subject_id, units)
        await update_research_progress(subject_id, "Mapping Syllabus", "Syllabus saved to database successfully.")
        
        # Step 3: Generate detailed study summaries for each unit as local textbooks
        await update_research_progress(subject_id, "Writing Study Guides", "Compiling local knowledge summaries and practice exercises...")
        for idx, unit in enumerate(units):
            unit_title = unit.get("unit_title", f"Unit {idx+1}")
            await update_research_progress(subject_id, "Writing Study Guides", f"Writing summary for {unit_title}...")
            
            guide_prompt = f"""
Write an exhaustive, high-quality, academic study guide and reference guide for: "{unit_title}" in the subject "{subject_name}".
Make sure to cover the following chapters and subtopics:
{json.dumps(unit.get('chapters', []))}

Include:
1. Deep conceptual explanations.
2. Formal definitions of key terms.
3. Code examples, formulas, or practical exercises (if applicable).
4. Recommended exam review questions.

Keep the content highly detailed and technical. Write at least 800 words. Format as clean Markdown.
Do not write conversational introductions or greetings. Start directly with the title.
"""
            guide_content = await llm.chat([], guide_prompt)
            guide_path = docs_dir / f"unit_{idx+1}_study_guide.md"
            with open(guide_path, "w", encoding="utf-8") as f:
                f.write(guide_content)
                
        # Step 4: Re-index dynamic RAG
        await update_research_progress(subject_id, "Indexing Documents", "Re-indexing subject-specific TF-IDF RAG system...")
        rag = RAGEngine()
        rag.rebuild_index(subject_id)
        
        await update_research_progress(subject_id, "Completed", f"Deep research and curriculum mapping for {subject_name} completed successfully! VOID is now ready to teach this subject.")
        
        # Announce completion through voice if voice system is available
        try:
            from tools.voice_tts import speak
            speak(f"Deep research on {subject_name} is complete, Sir. I have structured the curriculum and compiled the reference materials.")
        except Exception:
            pass
            
        ACTIVE_ACADEMIC_RESEARCH["active"] = False
        return {"status": "ok", "units": units}
        
    except Exception as e:
        logger.error(f"Failed to build subject curriculum: {e}", exc_info=True)
        await update_research_progress(subject_id, "Failed", f"Error during research phase: {str(e)}")
        ACTIVE_ACADEMIC_RESEARCH["active"] = False
        return {"status": "error", "message": str(e)}
