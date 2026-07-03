import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, BackgroundTasks
from pydantic import BaseModel

from server.dependencies import (
    VoidSingletons, PermissionManager, DATA_DIR, ROOT_DIR, STATS
)

logger = logging.getLogger("void.routes.academic")

router = APIRouter()


class SelectSubjectRequest(BaseModel):
    subject_id: str


class StartTestRequest(BaseModel):
    subject_id: str
    topic_id: str
    difficulty: str
    count: int = 5


class SubmitTestRequest(BaseModel):
    subject_id: str
    topic_id: str
    test_type: str
    score: float
    correct_count: int
    wrong_count: int
    skipped_count: int
    time_taken: int
    feedback: str


class SubmitVivaRequest(BaseModel):
    subject_id: str
    topic_id: str
    question: str
    response_text: str


class AddSubjectRequest(BaseModel):
    subject_name: str


class RemoveSubjectRequest(BaseModel):
    subject_id: str


class FlashcardCreateRequest(BaseModel):
    subject_id: str
    topic_id: str
    front: str
    back: str


class FlashcardReviewRequest(BaseModel):
    card_id: int
    quality: int


@router.get("/api/tools")
async def get_all_tools_metadata():
    from core.tools.tool_orchestrator import ToolOrchestrator
    orchestrator = ToolOrchestrator()
    return {"status": "ok", "tools": orchestrator.list_all_tools()}

# /repair and /diagnostics extracted to routes/admin.py


# [Extracted Chat Route Block]


# [Extracted Projects Route Block]

# ProjectScanRequest moved to routes/projects.py


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]


@router.get("/meetings/list")
async def list_meetings():
    from backend.memory_sqlite import get_recent_meetings
    try:
        return get_recent_meetings(limit=50)
    except Exception as e:
        logger.error(f"Failed to list meetings: {e}")
        return []


@router.post("/meetings/start")
async def start_meeting_endpoint():
    from tools.meeting_assistant import start_meeting
    try:
        res = start_meeting()
        return res
    except Exception as e:
        logger.error(f"Failed to start meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/meetings/stop")
async def stop_meeting_endpoint():
    from tools.meeting_assistant import stop_meeting
    try:
        res = stop_meeting()
        return res
    except Exception as e:
        logger.error(f"Failed to stop meeting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meetings/action-items")
async def get_meetings_action_items():
    from tools.meeting_assistant import get_action_items
    try:
        res = get_action_items()
        return res
    except Exception as e:
        logger.error(f"Failed to get meeting action items: {e}")
        return {"action_items": []}

# === AUTOMATION API ===

# [Extracted Automation Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


# [Extracted Academic Route Block]


@router.get("/academic/summary")
async def get_academic_summary_endpoint():
    """Returns the current progress statistics for the dashboard."""
    from tools.academic_progress import get_academic_summary
    return get_academic_summary()


@router.get("/analytics/summary")
async def get_analytics_summary_endpoint():
    """Returns productivity and study logs summary data."""
    from core.analytics.productivity_tracker import ProductivityTracker
    tracker = ProductivityTracker()
    return tracker.get_summary_stats()


@router.post("/academic/rebuild")
async def rebuild_academic_index(subject_id: str = None):
    """Triggers a rebuild of the local RAG index cache."""
    from backend.academic_rag import RAGEngine
    try:
        engine = RAGEngine()
        engine.rebuild_index(subject_id)
        return {"status": "ok", "message": f"Academic document index for {subject_id or 'default'} rebuilt successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/academic/upload")
async def upload_academic_document(file: UploadFile = File(...)):
    """Uploads a PDF, TXT, or MD textbook/note to active subject doc folder and rebuilds RAG index."""
    from backend.academic_rag import DOCS_DIR, RAGEngine
    from tools.academic_progress import get_profile_value
    
    subject_id = get_profile_value("current_subject", "dsa")
    subject_dir = DOCS_DIR / subject_id
    subject_dir.mkdir(parents=True, exist_ok=True)
    
    ext = Path(file.filename).suffix.lower()
    if ext not in [".txt", ".md", ".pdf", ".pptx"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Only PDF, TXT, MD, and PPTX files are allowed.")
        
    target_path = subject_dir / file.filename
    try:
        with open(target_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        engine = RAGEngine()
        engine.rebuild_index(subject_id)
        
        # Extract textbook features
        from core.academic.textbook_extractor import TextbookExtractor
        extractor = TextbookExtractor()
        extracted_data = extractor.extract(str(target_path))
        
        return {
            "status": "ok",
            "filename": file.filename,
            "message": f"Successfully uploaded '{file.filename}' to {subject_id} and rebuilt the academic search index.",
            "extracted": extracted_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")


@router.get("/academic/subjects")
async def get_subjects_endpoint():
    """Returns dynamic subject registry progress states."""
    from tools.academic_progress import get_subjects_list
    return get_subjects_list()


@router.post("/academic/select")
async def select_subject_endpoint(req: SelectSubjectRequest):
    """Sets active subject profile metadata."""
    from tools.academic_progress import set_profile_value
    set_profile_value("current_subject", req.subject_id)
    return {"status": "ok", "current_subject": req.subject_id}


@router.get("/academic/curriculum")
async def get_curriculum_endpoint(subject_id: str):
    """Returns curriculum accordion structure for active subject."""
    from tools.academic_progress import get_curriculum
    return get_curriculum(subject_id)


@router.post("/academic/research-start")
async def research_start_endpoint(req: SelectSubjectRequest, background_tasks: BackgroundTasks):
    """Triggers asynchronous academic Deep Research syllabus mapping."""
    from server.backend.academic_syllabus import build_subject_curriculum
    background_tasks.add_task(build_subject_curriculum, req.subject_id)
    return {"status": "ok", "message": f"Academic research started for {req.subject_id} in background."}


@router.get("/academic/research-status")
async def get_research_status_endpoint():
    """Returns dynamic progress logs of the syllabus builder."""
    from server.backend.academic_syllabus import ACTIVE_ACADEMIC_RESEARCH
    return ACTIVE_ACADEMIC_RESEARCH


@router.post("/academic/test/start")
async def start_test_endpoint(req: StartTestRequest):
    """Generates MCQs for active topic/difficulty tier."""
    from server.backend.academic_quiz_generator import QuizGenerator
    quiz_gen = QuizGenerator()
    questions = await quiz_gen.generate_quiz(req.subject_id, req.topic_id, req.difficulty, req.count)
    return {"status": "ok", "questions": questions}


@router.post("/academic/test/submit")
async def submit_test_endpoint(req: SubmitTestRequest):
    """Records MCQ quiz results to SQLite test history."""
    from tools.academic_progress import save_test_result
    save_test_result(
        req.subject_id, req.topic_id, req.test_type, req.score,
        req.correct_count, req.wrong_count, req.skipped_count,
        req.time_taken, req.feedback
    )
    try:
        from backend import memory_sqlite
        memory_sqlite.add_xp(int(req.score * 5))
    except Exception as e:
        logger.error(f"Failed to award XP for MCQ test: {e}")
    return {"status": "ok", "message": "Test result recorded successfully."}


@router.post("/academic/test/submit-viva")
async def submit_viva_endpoint(req: SubmitVivaRequest):
    """Evaluates viva response via LLM and logs scorecard."""
    from server.backend.academic_quiz_generator import QuizGenerator
    from tools.academic_progress import save_test_result
    quiz_gen = QuizGenerator()
    
    eval_result = await quiz_gen.evaluate_open_ended_response(
        req.subject_id, req.topic_id, req.question, req.response_text
    )
    
    score = eval_result.get("score", 5.0)
    feedback = eval_result.get("feedback", "No feedback provided.")
    passed = eval_result.get("passed", False)
    
    save_test_result(
        req.subject_id, req.topic_id, "viva", score,
        1 if passed else 0, 0 if passed else 1, 0,
        30, feedback
    )
    try:
        from backend import memory_sqlite
        memory_sqlite.add_xp(int(score * 8))
    except Exception as e:
        logger.error(f"Failed to award XP for viva test: {e}")
    
    return {
        "status": "ok",
        "score": score,
        "feedback": feedback,
        "passed": passed,
        "correct_components": eval_result.get("correct_components", []),
        "missing_components": eval_result.get("missing_components", [])
    }


@router.post("/academic/subjects/add")
async def add_subject_endpoint(req: AddSubjectRequest):
    """Dynamically registers a new subject in the registry database."""
    from tools.academic_progress import get_connection
    import re
    # Create clean subject_id from name
    subject_id = re.sub(r'[^a-zA-Z0-9]', '_', req.subject_name.strip().lower())
    subject_id = re.sub(r'_+', '_', subject_id).strip('_')
    
    if not subject_id:
        raise HTTPException(status_code=400, detail="Invalid subject name.")
        
    try:
        with get_connection() as conn:
            exists = conn.execute("SELECT 1 FROM subjects WHERE subject_id = ?", (subject_id,)).fetchone()
            if exists:
                raise HTTPException(status_code=400, detail="Subject already exists.")
            conn.execute(
                "INSERT INTO subjects (subject_id, subject_name) VALUES (?, ?)",
                (subject_id, req.subject_name.strip())
            )
            conn.commit()
        return {"status": "ok", "subject_id": subject_id, "subject_name": req.subject_name.strip()}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/academic/subjects/remove")
async def remove_subject_endpoint(req: RemoveSubjectRequest):
    """Deletes a subject and purges all related curriculum and test records."""
    from tools.academic_progress import get_connection
    import shutil
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM subjects WHERE subject_id = ?", (req.subject_id,))
            conn.execute("DELETE FROM curriculum WHERE subject_id = ?", (req.subject_id,))
            conn.execute("DELETE FROM completed_topics WHERE subject_id = ?", (req.subject_id,))
            conn.execute("DELETE FROM knowledge_gaps WHERE subject_id = ?", (req.subject_id,))
            conn.execute("DELETE FROM test_history WHERE subject_id = ?", (req.subject_id,))
            conn.commit()
            
        # Clean up files from disk
        docs_dir = Path(__file__).parent.parent / "memory" / "academic_documents" / req.subject_id
        if docs_dir.exists():
            shutil.rmtree(docs_dir)
            
        return {"status": "ok", "message": f"Subject {req.subject_id} and all its data removed successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/academic/flashcards")
async def create_flashcard_endpoint(req: FlashcardCreateRequest):
    from tools.academic_progress import add_flashcard
    ok = add_flashcard(req.subject_id, req.topic_id, req.front, req.back)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to create flashcard.")
    return {"status": "ok", "message": "Flashcard created successfully."}


@router.get("/academic/flashcards/due")
async def get_due_flashcards_endpoint(subject_id: str = None):
    from tools.academic_progress import get_due_flashcards
    return get_due_flashcards(subject_id)


@router.post("/academic/flashcards/review")
async def review_flashcard_endpoint(req: FlashcardReviewRequest):
    if req.quality < 0 or req.quality > 5:
        raise HTTPException(status_code=400, detail="Quality score must be between 0 and 5 inclusive.")
    from tools.academic_progress import review_flashcard
    res = review_flashcard(req.card_id, req.quality)
    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message"))
    return res


@router.get("/academic/schedule")
async def get_study_schedule_endpoint(subject_id: str = None):
    from tools.academic_progress import generate_study_schedule
    return generate_study_schedule(subject_id)


@router.get("/academic/emotion")
async def get_academic_emotion_endpoint():
    """Returns the user's estimated emotional state and voice features."""
    from backend.emotion_engine import ACTIVE_MOOD
    return ACTIVE_MOOD

# === COMPUTER VISION & CONTROL SYSTEMS (CVCS) ROUTES ===

# [Extracted Automation Route Block]


# [Extracted Automation Route Block]


# [Extracted Automation Route Block]


# [Extracted Automation Route Block]


# [Extracted Automation Route Block]


# [Extracted Automation Route Block]


@router.get("/gamification/xp")
async def get_gamification_xp():
    try:
        from backend import memory_sqlite
        xp_data = memory_sqlite.get_xp()
        streaks = memory_sqlite.get_streaks()
        max_streak = 0
        if streaks:
            max_streak = max([s.get("streak_count", 0) for s in streaks])
        return {"status": "ok", "points": xp_data.get("points", 0), "level": xp_data.get("level", 1), "streak": max_streak}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/gamification/achievements")
async def get_gamification_achievements():
    try:
        from backend import memory_sqlite
        achievements = memory_sqlite.get_achievements()
        return {"status": "ok", "achievements": achievements}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8003)

