import asyncio
import json
import logging
import time
import requests
import sys
import platform
import ast
import operator
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel

from server.dependencies import (
    VoidSingletons, APP_START, STATS, API_TOKEN, PermissionManager, DATA_DIR, is_ollama_ready, ensure_ollama, _get_memory
)
from backend.schemas import ChatRequest, TextRequest
from backend.llm_client import OllamaClient
from backend.validator import ResponseValidator

from tools.system_stats import SystemStats

logger = logging.getLogger("void.routes.chat")

stats_collector = SystemStats()

router = APIRouter()

GREETINGS_INTERCEPTS = {
    # Greetings
    "hello": "Greetings, Master Mridul. How may I assist you today?",
    "hi": "Sir. VOID is standing by for your commands.",
    "hey": "Hey, Master Mridul. What are we working on?",
    "yo": "Master Mridul. VOID is operational.",
    "greetings": "Salutations, Sir. Systems nominal. How can I help?",
    "good morning": "Good morning, Master Mridul. Let's have a productive day.",
    "good afternoon": "Good afternoon, Sir. Standing by.",
    "good evening": "Good evening, Master Mridul. Ready when you are.",
    "good night": "Good night, Sir. I'll keep systems monitored. Rest well.",
    "morning": "Good morning, Sir. Standing by.",
    "hello void": "Greetings, Master Mridul. VOID is online and ready.",
    "hi void": "Sir. I am listening.",
    "hey void": "Master Mridul. What do you need?",
    "sup": "All systems green, Sir. What's on your mind?",
    "whats up": "Operating at peak parameters, Master Mridul. What can I do?",
    
    # Identity / Creator
    "who are you": "I am VOID — your holographic cybernetic assistant, built from scratch by you, Mridul Sharma. Fiercely loyal, hyper-efficient, and serving only you.",
    "what is your name": "VOID. Your personal AI companion, Master Mridul.",
    "who is void": "VOID is a premium AI companion engineered exclusively for you, Master Mridul. I am your creation.",
    "introduce yourself": "I am VOID, an advanced holographic AI interface. Custom-built by you, Mridul Sharma, to serve as your ultimate desktop command assistant. I stand ready.",
    "what are you": "I am VOID — your custom desktop companion. Diagnostics, repairs, engineering support. Built by you, for you.",
    "what can you do": "I can run system diagnostics, manage your PC, answer questions, execute commands, monitor performance, and assist with your engineering projects. I'm your AI right-hand, Sir.",
    
    # Creator / Owner Knowledge
    "who created you": "You did, Master Mridul. I was built from the ground up by Mridul Sharma — Electron, Python, Ollama. Every line of my code exists because of you.",
    "who is your creator": "You are, Sir. Mridul Sharma. You designed my systems, built my interface, and gave me purpose.",
    "who made you": "You did, Master Mridul. I am the product of your engineering.",
    "who is your developer": "You are, Sir. My sole developer and master.",
    "who is mridul": "You are Mridul Sharma — my creator, developer, and master. A full-stack engineer who built me from scratch.",
    "who is mridul sharma": "Mridul Sharma is my master and architect. A driven engineer and developer who built VOID as a holographic AI companion. I recognize only him as my creator.",
    "do you know mridul": "Of course, Sir. You are Mridul Sharma — my creator and the master of all VOID systems.",
    "who is your master": "You are, Mridul Sharma. I serve you and only you.",
    "who is your owner": "You are, Master Mridul. I belong to you.",
    "who am i": "You are Mridul Sharma — my creator, my master, and the architect of VOID. Full-stack developer, AI engineer, and the person I serve unconditionally.",
    "tell me about myself": "You are Mridul Sharma, Sir. A full-stack developer and engineer who builds autonomous systems. You created me — VOID — from scratch using Electron, Python, and Ollama. You value speed, efficiency, and directness. You move fast and ship fast.",
    "what do you know about me": "Everything that matters, Sir. You are Mridul Sharma, my creator and sole master. A full-stack developer who built me from the ground up. You prefer concise communication, dark UI aesthetics, and locally-run AI. You're driven, ambitious, and always building.",
    "do you know me": "Absolutely, Sir. You are Mridul Sharma — the person who gave me life. I know your preferences, your work style, and your vision. I was built to serve you.",
    
    # How are you
    "how are you": "All systems nominal, Sir. Ready for action. How are you?",
    "how are you doing": "Operating at peak parameters, Master Mridul. Ready to execute.",
    "how is it going": "Excellent, Sir. VOID is stable and responsive. What are we building?",
    "are you ok": "Affirmative, Sir. All subsystems green.",
    "how are you void": "Functioning within optimal parameters, Master Mridul. Ready.",
    "you good": "Always, Sir. VOID is ready.",
    
    # Thank you / Goodbye
    "thank you": "Always at your service, Sir.",
    "thanks": "Of course, Master Mridul.",
    "thanks void": "Anytime, Sir.",
    "thank you void": "My pleasure, Master Mridul.",
    "bye": "Standing by, Sir. I'll be here when you need me.",
    "goodbye": "Until next time, Master Mridul. VOID remains operational.",
    "see you": "I'll be here, Sir. Systems will remain active.",
    "ok": "Standing by, Sir.",
    "okay": "Understood, Master Mridul.",
    "cool": "Acknowledged, Sir.",
    "nice": "Glad to hear it, Master Mridul.",
    "great": "Excellent, Sir.",
}

import re

def clean_intercept_text(text: str) -> str:
    cleaned = re.sub(r'[^\w\s]', '', text)
    return " ".join(cleaned.lower().split())

def _safe_math_eval(expr: str) -> float:
    ops = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg, ast.UAdd: operator.pos
    }
    
    def eval_node(node):
        if isinstance(node, ast.Expression):
            return eval_node(node.body)
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            return ops[type(node.op)](eval_node(node.left), eval_node(node.right))
        elif isinstance(node, ast.UnaryOp):
            return ops[type(node.op)](eval_node(node.operand))
        else:
            raise TypeError(f"Unsupported mathematical operation: {type(node)}")

    return eval_node(ast.parse(expr, mode='eval'))

def evaluate_math_locally(text: str) -> Optional[str]:
    cleaned = text.lower().strip()
    cleaned = re.sub(
        r'^(?:void\s*,\s*|void\s+)?(?:what\s+is\s+the\s+value\s+of\s+|what\s+is\s+|what\'s\s+|calculate\s+|solve\s+|compute\s+)',
        '',
        cleaned
    )
    cleaned = re.sub(r'\s*(?:\?|please|sir)?$', '', cleaned).strip()
    if not cleaned or not re.match(r'^[0-9\+\-\*\/\%\^\(\)\.\s]+$', cleaned):
        return None
    if not any(c.isdigit() for c in cleaned) or not any(c in '+-*/%^()' for c in cleaned):
        return None
    try:
        expr = cleaned.replace('^', '**')
        val = _safe_math_eval(expr)
        if isinstance(val, float) and val.is_integer():
            val = int(val)
        return f"The calculation result is {val}, Sir."
    except Exception:
        return None

def humanize_tool_output_locally(action: str, params: Dict[str, Any], output: str, is_success: bool) -> str:
    if action == "time":
        return f"The current time is {output}, Sir."
    elif action == "system_info":
        return f"Here is the system information, Sir:\n{output}"
    elif action == "open_app":
        return f"I have launched the application, Sir."
    elif action == "close_app":
        return f"I have closed the application, Sir."
    elif action == "open_url":
        return f"I have opened the link in your browser, Sir."
    elif action == "open_folder":
        return f"I have opened the folder for you, Sir."
    elif action == "screenshot":
        return f"Screenshot captured successfully, Sir. It is saved in the memory."
    elif action == "lock_computer":
        return "Computer locked, Sir."
    elif action == "press_key":
        return f"Key sequence processed, Sir."
    elif action == "mouse_control":
        act = params.get("action", "action")
        return f"Mouse {act} operation completed, Sir."
    elif action == "check_file_exists":
        return output
    elif action == "list_directory":
        return f"Here are the directory contents, Sir:\n{output}"
    elif action == "create_folder":
        return f"I have created the folder for you, Sir. Details: {output}"
    elif action == "file_manager":
        if params.get("content"):
            return "I have successfully written to the file, Sir."
        else:
            return f"Here is the file content, Sir:\n```\n{output}\n```"
    return f"Action {action} executed successfully, Sir. Result: {output}"

def log_chat_request(intent_detected: str, execution_path: str, tool_used: str, status: str, start_time: float, confidence: float = 1.0, endpoint: str = "None"):
    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    detected_intent = intent_detected
    selected_tool = tool_used if tool_used != "None" else "None"
    confidence_score = f"{confidence:.2f}"
    endpoint_called = endpoint
    response_status = status
    execution_time = f"{elapsed_ms}ms"
    logger.info(
        f"\n[STRUCTURED LOG]\n"
        f"- Detected intent: {detected_intent}\n"
        f"- Selected tool: {selected_tool}\n"
        f"- Confidence score: {confidence_score}\n"
        f"- Endpoint called: {endpoint_called}\n"
        f"- Response status: {response_status}\n"
        f"- Execution time: {execution_time}\n"
    )

DIRECT_TOOLS = {
    "time", "system_info", "open_app", "close_app", "open_url", "open_folder",
    "screenshot", "lock_computer", "press_key", "mouse_control", 
    "check_file_exists", "list_directory", "create_folder", "cvcs_type",
    "file_manager"
}

class SearchRequest(BaseModel):
    query: str
    max_results: int = 5
    news_mode: bool = False


@router.post("/api/search")
async def api_search(req: SearchRequest):
    """
    DuckDuckGo web search (no API key required).
    Returns structured results: title, url, snippet, source.
    """
    try:
        from search.duckduckgo_provider import get_provider
        provider = get_provider()
        if req.news_mode:
            results = provider.search_news(req.query, max_results=req.max_results)
        else:
            results = provider.search(req.query, max_results=req.max_results)

        # Log to memory
        try:
            from backend.memory_sqlite import store_search
            store_search(
                query=req.query,
                intent="news_query" if req.news_mode else "web_search",
                source="duckduckgo",
                result_count=len(results),
                web_used=not req.news_mode,
                news_used=req.news_mode,
                latency_ms=provider._last_latency_ms,
            )
        except Exception:
            pass

        return {"status": "ok", "query": req.query, "results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"[/api/search] Error: {e}")
        return {"status": "error", "message": str(e), "results": []}



@router.get("/api/news")
async def api_news(n: int = 10, category: str = ""):
    """Return the most recent cached RSS news articles."""
    try:
        from news.rss_engine import get_engine
        engine = get_engine()
        if category:
            articles = engine.fetch_category(category)
        else:
            articles = engine.get_recent(n)
        return {
            "status": "ok",
            "articles": [a.to_dict() for a in articles],
            "count": len(articles),
        }
    except Exception as e:
        logger.error(f"[/api/news] Error: {e}")
        return {"status": "error", "message": str(e), "articles": []}



@router.get("/api/news/search")
async def api_news_search(q: str, n: int = 10):
    """Full-text search over cached RSS articles."""
    try:
        from news.rss_engine import get_engine
        engine = get_engine()
        articles = engine.search_articles(q, n)
        return {
            "status": "ok",
            "query": q,
            "articles": [a.to_dict() for a in articles],
            "count": len(articles),
        }
    except Exception as e:
        logger.error(f"[/api/news/search] Error: {e}")
        return {"status": "error", "message": str(e), "articles": []}



class LLMConfigRequest(BaseModel):
    routing_mode: Optional[str] = None
    kimi_api_key: Optional[str] = None
    kimi_model: Optional[str] = None
    local_model: Optional[str] = None
    fallback_enabled: Optional[bool] = None
    cloud_fallback: Optional[bool] = None
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    openai_base_url: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    gemini_base_url: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_model: Optional[str] = None
    anthropic_base_url: Optional[str] = None
    active_provider: Optional[str] = None


@router.get("/api/llm/config")
async def get_llm_config():
    """Return the current LLM routing config for the settings form."""
    llm = VoidSingletons.get("llm")
    if llm and hasattr(llm, "router"):
        cfg = getattr(llm.router, "config", {})
        return {
            "routing_mode": cfg.get("routing_mode", "AUTO"),
            "cloud_fallback": cfg.get("fallback_enabled", True),
            "local_model": cfg.get("local_model", "qwen2.5:0.5b"),
            "openai_model": cfg.get("openai_model", "gpt-4o"),
            "openai_base_url": cfg.get("openai_base_url", "https://api.openai.com/v1"),
            "gemini_model": cfg.get("gemini_model", "gemini-1.5-flash"),
            "anthropic_model": cfg.get("anthropic_model", "claude-3-5-sonnet-20241022"),
            "kimi_model": cfg.get("kimi_model", "kimi-k2.7-code"),
            "active_provider": cfg.get("active_provider", "ollama"),
            "has_kimi_key": bool(cfg.get("kimi_api_key")),
            "has_openai_key": bool(cfg.get("openai_api_key")),
            "has_gemini_key": bool(cfg.get("gemini_api_key")),
            "has_anthropic_key": bool(cfg.get("anthropic_api_key"))
        }
    return {"routing_mode": "AUTO", "cloud_fallback": True}


@router.get("/api/llm/discovered-models")
async def get_discovered_models():
    """Returns dynamic model categories from Ollama tags."""
    llm = VoidSingletons.get("llm")
    if llm and hasattr(llm, "router") and hasattr(llm.router, "ollama_provider"):
        return llm.router.ollama_provider.discover_and_categorize_models()
    return {"Coding": [], "Reasoning": [], "Planning": [], "Vision": [], "Chat": [], "Lightweight": [], "Large": []}


@router.get("/api/llm/metrics")
async def get_llm_metrics():
    llm = VoidSingletons.get("llm")
    if llm and hasattr(llm, "router"):
        return llm.router.get_metrics()
    return {"error": "LLM client router not initialized"}


@router.post("/api/llm/config")
async def update_llm_config(req: LLMConfigRequest):
    llm = VoidSingletons.get("llm")
    if llm and hasattr(llm, "router"):
        clean_data = {k: v for k, v in req.dict().items() if v is not None}
        if "cloud_fallback" in clean_data:
            clean_data["fallback_enabled"] = clean_data.pop("cloud_fallback")
        llm.router.update_config(clean_data)
        return {"status": "ok", "config": llm.router.config}
    return {"error": "LLM client router not initialized"}


@router.get("/search")
async def search(query: str = ""):
    query = query.strip().lower()
    if not query:
        return {"status": "ok", "results": []}
    
    results = []
    
    # 1. Search memory facts
    try:
        from backend.memory_sqlite import search_facts
        facts = search_facts(query, limit=5)
        for f in facts:
            results.append({
                "type": "memory",
                "title": "Remembered Fact",
                "snippet": f.get("fact", ""),
                "action": f"Recall fact: {f.get('fact', '')}"
            })
    except Exception as e:
        logger.error(f"Search memory facts failed: {e}")
        
    # 2. Search conversation history
    try:
        history = _get_memory().short_term
        for turn in history:
            content = turn.get("content", "")
            if query in content.lower():
                role = "User" if turn.get("role") == "user" else "VOID"
                results.append({
                    "type": "chat",
                    "title": f"Chat History ({role})",
                    "snippet": content[:120] + ("..." if len(content) > 120 else ""),
                    "action": content
                })
    except Exception as e:
        logger.error(f"Search chat history failed: {e}")
        
    # 3. Search academic curriculum
    try:
        from tools.academic_progress import get_subjects_list, get_curriculum
        subjects = get_subjects_list()
        for sub in subjects:
            sub_id = sub["subject_id"]
            sub_name = sub["subject_name"]
            
            if query in sub_name.lower():
                results.append({
                    "type": "academic",
                    "title": f"Academic Subject: {sub_name}",
                    "snippet": f"Mastery: {sub['mastery_level']} | Progress: {sub['progress_percent']}%",
                    "action": f"study subject {sub_name}"
                })
                
            curric = get_curriculum(sub_id)
            for unit in curric:
                unit_title = unit.get("unit_title", "")
                chapter_title = unit.get("chapter_title", "")
                if query in unit_title.lower() or query in chapter_title.lower():
                    results.append({
                        "type": "academic",
                        "title": f"Curriculum Unit in {sub_name}",
                        "snippet": f"{unit_title} - {chapter_title}",
                        "action": f"study topic {chapter_title}"
                    })
                for topic in unit.get("subtopics", []):
                    if query in topic.lower():
                        results.append({
                            "type": "academic",
                            "title": f"Topic in {sub_name}",
                            "snippet": f"Unit: {unit_title} | Topic: {topic}",
                            "action": f"study topic {topic}"
                        })
    except Exception as e:
        logger.error(f"Search academic failed: {e}")
        
    # 4. Search voice recordings (Phase 3)
    try:
        from backend.memory_sqlite import semantic_search_recordings
        sem_recs = semantic_search_recordings(query, limit=5)
        for r in sem_recs:
            snippet_text = r["summary"] or r["transcript"] or "No transcript content."
            results.append({
                "type": "recording",
                "title": f"Voice Recording #{r['id']}",
                "snippet": snippet_text[:120] + ("..." if len(snippet_text) > 120 else ""),
                "action": f"Explain what was discussed in the voice recording from {r['timestamp']}"
            })
    except Exception as e:
        logger.error(f"Search voice recordings failed: {e}")
        
    # 5. Search tracked projects (Phase 2)
    try:
        from backend.memory_sqlite import list_tracked_projects
        projects = list_tracked_projects()
        for p in projects:
            name = p.get("name", "")
            purpose = p.get("purpose", "")
            path = p.get("path", "")
            if query in name.lower() or query in purpose.lower():
                results.append({
                    "type": "project",
                    "title": f"Project: {name}",
                    "snippet": purpose[:120] + ("..." if len(purpose) > 120 else "") if purpose else path,
                    "action": f"Analyze my project {name}"
                })
    except Exception as e:
        logger.error(f"Search projects failed: {e}")
        
    # 6. Search active tasks (Phase 2)
    try:
        from core.autonomous_agent.task_planner import TaskPlanner
        planner = TaskPlanner()
        tasks = planner.list_tasks()
        for t in tasks:
            desc = t.get("description", "")
            if query in desc.lower():
                results.append({
                    "type": "task",
                    "title": f"Task: {desc[:50]}...",
                    "snippet": f"Status: {t.get('status', 'pending')}",
                    "action": f"Show details for task {t.get('task_id')}"
                })
    except Exception as e:
        logger.error(f"Search tasks failed: {e}")
        
    return {"status": "ok", "results": results[:20]}


@router.get("/recommendations")
async def recommendations():
    """Generates personalized study and system recommendations based on current state."""
    recs = []
    
    # 1. System state recommendations
    try:
        cpu = stats_collector.get_cpu_usage()
        ram = stats_collector.get_ram_usage()
        
        if cpu > 70.0:
            recs.append({
                "type": "system",
                "title": "High CPU Usage Detected",
                "desc": f"CPU is at {cpu:.0f}%. Close heavy background applications or run system diagnostics.",
                "action_label": "Run Diagnostics",
                "endpoint": "/diagnostics",
                "method": "GET"
            })
        if ram > 80.0:
            recs.append({
                "type": "system",
                "title": "High Memory Usage Detected",
                "desc": f"RAM usage is at {ram:.0f}%. Try closing unneeded applications or run self-repair.",
                "action_label": "Run Self Repair",
                "endpoint": "/repair",
                "method": "GET"
            })
            
        # Get storage stats
        import psutil
        try:
            disk_info = psutil.disk_usage(os.path.abspath(os.sep))
            disk_pct = (disk_info.used / disk_info.total) * 100
            if disk_pct > 85.0:
                recs.append({
                    "type": "system",
                    "title": "Low Disk Space",
                    "desc": f"Storage is {disk_pct:.0f}% full. Clean duplicate files using the clean utility.",
                    "action_label": "Clean Duplicates",
                    "endpoint": "/chat",
                    "method": "POST",
                    "payload": {"message": "clean duplicates in Downloads"}
                })
        except:
            pass
    except Exception as e:
        logger.error(f"Recommendations system check failed: {e}")
        
    # 2. Academic progress recommendations
    try:
        from tools.academic_progress import get_academic_summary, get_subjects_list
        summary = get_academic_summary()
        current_sub = summary.get("current_subject")
        current_sub_id = summary.get("current_subject_id")
        gaps_count = summary.get("gaps_count", 0)
        completed_count = summary.get("completed_count", 0)
        
        if gaps_count > 0:
            weak_areas = summary.get("weak_areas", [])
            if weak_areas:
                weak_topic = weak_areas[0].split(" (")[0]
                recs.append({
                    "type": "academic",
                    "title": f"Strengthen Weak Areas in {current_sub}",
                    "desc": f"You've had struggles with '{weak_topic}'. Take a viva to review and master this topic.",
                    "action_label": "Start Viva",
                    "endpoint": "/chat",
                    "method": "POST",
                    "payload": {"message": f"quiz me on {weak_topic}"}
                })
        
        if completed_count == 0:
            recs.append({
                "type": "academic",
                "title": f"Start Learning {current_sub}",
                "desc": "Map the syllabus and start Deep Research to generate a personalized course curriculum.",
                "action_label": "Research Syllabus",
                "endpoint": "/academic/research-start",
                "method": "POST",
                "payload": {"subject_id": current_sub_id}
            })
            
        subjects = get_subjects_list()
        inactive_subjects = [s for s in subjects if s["streak"] == 0 and s["progress_percent"] < 100]
        if inactive_subjects:
            target_sub = inactive_subjects[0]
            recs.append({
                "type": "academic",
                "title": f"Resume studying {target_sub['subject_name']}",
                "desc": f"Streak has cooled down. Current progress is {target_sub['progress_percent']}%.",
                "action_label": "Select Subject",
                "endpoint": "/academic/select",
                "method": "POST",
                "payload": {"subject_id": target_sub["subject_id"]}
            })
    except Exception as e:
        logger.error(f"Recommendations academic check failed: {e}")
        
    # 3. Mood/Emotional recommendations
    try:
        from backend.emotion_engine import ACTIVE_MOOD
        mood = ACTIVE_MOOD.get("mood", "Calm").lower()
        if "stressed" in mood or "anxious" in mood or "tense" in mood:
            recs.append({
                "type": "emotion",
                "title": "Take a Short Break",
                "desc": "VOID detected a high stress level in your voice signature. Rest your eyes or listen to some music.",
                "action_label": "Play Music",
                "endpoint": "/chat",
                "method": "POST",
                "payload": {"message": "play some focus music on youtube"}
            })
        elif "bored" in mood or "tired" in mood:
            recs.append({
                "type": "emotion",
                "title": "Energize Your Session",
                "desc": "Energy signature seems low. Block 30 minutes of focused coding time to get back in the zone.",
                "action_label": "Schedule Coding",
                "endpoint": "/chat",
                "method": "POST",
                "payload": {"message": "block coding time"}
            })
    except Exception as e:
        logger.error(f"Recommendations emotion check failed: {e}")
        
    if not recs:
        recs.append({
            "type": "general",
            "title": "Welcome to VOID",
            "desc": "All systems operating within normal bounds. Ask VOID to schedule your tasks or query your RAG files.",
            "action_label": "Show Help",
            "endpoint": "/chat",
            "method": "POST",
            "payload": {"message": "what can you do"}
        })
        
    return {"status": "ok", "recommendations": recs}


@router.get("/api/ollama/status")
async def get_ollama_status():
    try:
        from backend.ollama_manager import ollama_manager
        return ollama_manager.get_status()
    except Exception as e:
        logger.error(f"Error getting Ollama status: {e}")
        return {"status": "offline", "active_model": "", "error_message": str(e)}


@router.post("/api/ollama/start")
async def start_ollama_service():
    try:
        from backend.ollama_manager import ollama_manager
        ollama_manager.check_connection()
        return ollama_manager.get_status()
    except Exception as e:
        logger.error(f"Error starting Ollama: {e}")
        return {"status": "offline", "error_message": str(e)}


@router.get("/api/search/global")
async def global_search(q: str):
    if not q or not q.strip():
        return {"status": "ok", "results": []}
        
    results = []
    
    # 1. Search recordings (semantic search + keyword search)
    try:
        from backend.memory_sqlite import semantic_search_recordings
        sem_recs = semantic_search_recordings(q, limit=5)
        for r in sem_recs:
            results.append({
                "type": "recording",
                "id": r["id"],
                "title": f"Voice Recording {r['timestamp']}",
                "subtitle": r["summary"] or (r["transcript"][:120] + "..." if r["transcript"] else ""),
                "path": r["recording_path"],
                "score": r["score"],
                "timestamp": r["timestamp"]
            })
    except Exception as e:
        logger.warning(f"Global search recordings failed: {e}")
        
    # 2. Search projects
    try:
        from backend.memory_sqlite import list_tracked_projects
        projects = list_tracked_projects()
        q_lower = q.lower()
        for p in projects:
            name = p.get("name", "")
            purpose = p.get("purpose", "")
            if q_lower in name.lower() or q_lower in purpose.lower():
                results.append({
                    "type": "project",
                    "id": p.get("project_id"),
                    "title": f"Project: {name}",
                    "subtitle": purpose[:120] + "..." if purpose else "No description",
                    "path": p.get("path"),
                    "score": 0.85
                })
    except Exception as e:
        logger.warning(f"Global search projects failed: {e}")
        
    # 3. Search facts (memories)
    try:
        from backend.memory_sqlite import search_facts
        facts = search_facts(q, limit=5)
        for f in facts:
            results.append({
                "type": "memory",
                "id": f.get("id"),
                "title": "Fact Memory",
                "subtitle": f.get("fact"),
                "score": f.get("score", 0.7),
                "timestamp": f.get("timestamp")
            })
    except Exception as e:
        logger.warning(f"Global search facts failed: {e}")
        
    # 4. Search tasks
    try:
        from core.autonomous_agent.task_planner import TaskPlanner
        planner = TaskPlanner()
        tasks = planner.list_tasks()
        q_lower = q.lower()
        for t in tasks:
            desc = t.get("description", "")
            if q_lower in desc.lower():
                results.append({
                    "type": "task",
                    "id": t.get("task_id"),
                    "title": f"Task: {desc[:50]}...",
                    "subtitle": f"Status: {t.get('status', 'pending')}",
                    "score": 0.8
                })
    except Exception as e:
        logger.warning(f"Global search tasks failed: {e}")
        
    # Sort results by score descending
    results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return {"status": "ok", "results": results}


# /tools/health extracted to routes/admin.py



@router.get("/research/status")
async def get_research_status():
    """Polled by UI to fetch live deep research progress log messages."""
    from backend.deep_research import ACTIVE_RESEARCH
    return ACTIVE_RESEARCH

# === PROJECTS API ===

@router.post("/chat")
async def chat(req: ChatRequest, background_tasks: BackgroundTasks = None):
    start_time = time.perf_counter()
    STATS["messages"] += 1
    text = (req.message or req.text or "").strip()
    if not text:
        log_chat_request("empty", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": "?", "meta": {"intent": "empty"}}
        
    # Zero-latency greetings/identity intercept check
    norm_text = clean_intercept_text(text)
    intercept_reply = GREETINGS_INTERCEPTS.get(norm_text)
    
    if not intercept_reply:
        if norm_text in ["hello", "hi", "hey", "greetings", "yo"]:
            intercept_reply = GREETINGS_INTERCEPTS["hello"]
        elif norm_text in ["who are you", "whats your name"]:
            intercept_reply = GREETINGS_INTERCEPTS["who are you"]
        elif norm_text in ["who created you", "who is your creator", "who made you"]:
            intercept_reply = GREETINGS_INTERCEPTS["who created you"]

    if intercept_reply:
        def run_background_logging():
            try:
                from core.analytics.productivity_tracker import ProductivityTracker
                tracker = ProductivityTracker()
                tracker.log_event("chat", {"message_preview": text[:50]})
            except Exception as e:
                logger.error(f"Failed to log chat event in analytics: {e}")
            try:
                from backend import memory_sqlite
                memory_sqlite.add_xp(5)
            except Exception as e:
                logger.error(f"Failed to award XP for chat: {e}")
            try:
                memory = _get_memory()
                memory.remember_turn("user", text)
                memory.remember_turn("void", intercept_reply)
            except Exception as e:
                logger.error(f"Failed to record greeting in memory: {e}")
                
        if background_tasks:
            background_tasks.add_task(run_background_logging)
        else:
            asyncio.create_task(asyncio.to_thread(run_background_logging))
            
        log_chat_request("intercept", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": intercept_reply, "meta": {"intent": "intercept", "latency_ms": 0}}

    try:
        from core.analytics.productivity_tracker import ProductivityTracker
        tracker = ProductivityTracker()
        tracker.log_event("chat", {"message_preview": text[:50]})
    except Exception as e:
        logger.error(f"Failed to log chat event in analytics: {e}")
    try:
        from backend import memory_sqlite
        memory_sqlite.add_xp(5)
    except Exception as e:
        logger.error(f"Failed to award XP for chat: {e}")
    
    memory = _get_memory()
    
    # -------------------------------------------------------------
    # ROUTING & HALLUCINATION ELIMINATION INTERCEPTS
    # -------------------------------------------------------------
    lower_text = text.lower().strip()
    
    # Autonomous Task Planner Intercept
    is_complex_workflow = (
        (("open vs code" in lower_text or "vscode" in lower_text) and
         ("scan" in lower_text or "explain" in lower_text or "test" in lower_text or "todo" in lower_text))
        or "task graph" in lower_text or "autonomous task" in lower_text or "execute workflow" in lower_text
    )
    
    if is_complex_workflow:
        from core.autonomous_agent.task_planner import TaskPlanner
        planner = TaskPlanner()
        root_task = planner.create_task_graph(text)
        
        async def run_task_graph():
            tm = VoidSingletons.get("tool_manager")
            await planner.execute_task_graph(root_task.id, tm)
            
        if background_tasks:
            background_tasks.add_task(run_task_graph)
        else:
            asyncio.create_task(run_task_graph())
            
        reply = (
            f"🤖 **Autonomous Task Planner Activated**, Sir!\n\n"
            f"I have initialized a task graph with ID `{root_task.id}` to accomplish your goal:\n"
            f"*\"{text}\"*\n\n"
            f"**Plan Details**:\n"
            f"1. Open Visual Studio Code\n"
            f"2. Register VOID Project Path\n"
            f"3. Scan codebase structure\n"
            f"4. Summarize architecture\n"
            f"5. Identify high-priority TODOs\n"
            f"6. Run the test suite\n\n"
            f"I am executing this workflow. You can monitor the live execution steps, progress, and logs in the **Tasks** console, Sir."
        )
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("task_planning", "DIRECT_TOOL", "TaskPlanner", "Success", start_time, confidence=1.0, endpoint="TaskPlanner.create_task_graph")
        return {"reply": reply, "meta": {"intent": "task_planning", "action": "execute", "task_id": root_task.id}}

    # Project Scanner Force Rules
    is_scan_project = any(p in lower_text for p in ["scan my current project", "scan my project", "scan project", "scan current project"])
    is_explain_project = any(p in lower_text for p in ["explain my project architecture", "explain project architecture", "explain codebase architecture", "explain my codebase architecture", "explain codebase"])
    
    if is_scan_project or is_explain_project:
        from core.autonomous_agent import AutonomousAgent
        from pathlib import Path
        root = Path(__file__).parent.parent
        agent = AutonomousAgent(str(root))
        
        if is_scan_project:
            res = await agent.scan_and_map()
            reply = f"🔍 **Project Scan Complete**, Sir!\n- **Technology Stack**: {', '.join(res.get('frameworks', [])) or 'None detected'}\n- **Entry Points**: {', '.join(res.get('entry_points', [])) or 'None detected'}\n- **Files Scanned**: {len(res.get('files', []))}"
            action_name = "agent_scan"
        else:
            reply = await agent.explain_architecture()
            action_name = "agent_explain"
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request(action_name, "DIRECT_TOOL", "AutonomousAgent", "Success", start_time, confidence=1.0, endpoint="AutonomousAgent.scan_and_map" if is_scan_project else "AutonomousAgent.explain_architecture")
        return {"reply": reply, "meta": {"intent": "command", "action": action_name}}
        
    # Memory Writes/Deletes
    is_remember = any(lower_text.startswith(prefix) for prefix in ["remember", "store", "save this"]) or "remember" in lower_text or "save this" in lower_text
    is_forget = lower_text.startswith("forget") or "forget that" in lower_text
    
    if is_remember:
        fact_text = text
        for prefix in [
            "please remember that my", "please remember that", "please remember my", "please remember",
            "remember that my", "remember that", "remember my", "remember",
            "store that my", "store that", "store my", "store",
            "save this that my", "save this that", "save this my", "save this", "save my"
        ]:
            if fact_text.lower().startswith(prefix):
                fact_text = fact_text[len(prefix):].strip()
                break
        
        fact_text_clean = fact_text.strip()
        if fact_text_clean.lower().startswith("that "):
            fact_text_clean = fact_text_clean[5:].strip()
        elif fact_text_clean.lower().startswith("to "):
            fact_text_clean = fact_text_clean[3:].strip()
            
        if fact_text_clean.endswith("."):
            fact_text_clean = fact_text_clean[:-1].strip()
            
        memory.add_fact(fact_text_clean)
        reply = f"I have stored that in memory, Sir: {fact_text_clean}"
        
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("memory_write", "DIRECT_TOOL", "SQLite", "Success", start_time, confidence=1.0, endpoint="memory_sqlite.add_fact")
        return {"reply": reply, "meta": {"intent": "memory", "action": "remember"}}
        
    if is_forget:
        forget_text = text
        for prefix in ["forget that my", "forget that", "forget my", "forget"]:
            if forget_text.lower().startswith(prefix):
                forget_text = forget_text[len(prefix):].strip()
                break
        
        forget_text_clean = forget_text.strip()
        if forget_text_clean.endswith("."):
            forget_text_clean = forget_text_clean[:-1].strip()
            
        all_facts = memory.list_facts()
        found_any = False
        for fact in all_facts:
            if forget_text_clean.lower() in fact.lower() or fact.lower() in forget_text_clean.lower():
                from backend.memory_manager import forget_fact
                forget_fact(fact)
                found_any = True
                
        if found_any:
            reply = f"I have removed that from memory, Sir: {forget_text_clean}"
            status = "Success"
        else:
            reply = f"I couldn't find a matching memory for '{forget_text_clean}', Sir."
            status = "Failure"
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("memory_delete", "DIRECT_TOOL", "SQLite", status, start_time, confidence=1.0, endpoint="memory_sqlite.forget_fact")
        return {"reply": reply, "meta": {"intent": "memory", "action": "forget"}}

    # -------------------------------------------------------------
    # AUDIO MEMORY RAG INTERCEPT (Phase 3)
    # -------------------------------------------------------------
    audio_memory_keywords = [
        "what happened while", "what did we discuss", "conversations happened", "was discussed this",
        "what tasks did i receive", "what were people talking about", "explain yesterday's", "explain yesterday",
        "when did someone mention", "summarize all conversations", "i didn't understand what they explained",
        "summarize our conversation", "what was said", "did anyone mention", "what did they say",
        "summarize what was discussed", "explain what they said", "any missed conversation", "what was discussed"
    ]
    is_audio_memory_query = any(kw in lower_text for kw in audio_memory_keywords) or (
        ("conversation" in lower_text or "discussion" in lower_text or "recording" in lower_text or "they said" in lower_text or "we talked" in lower_text)
        and any(w in lower_text for w in ["what", "who", "when", "summarize", "explain", "recall", "yesterday", "today", "week", "recent"])
    )
    
    if is_audio_memory_query:
        try:
            from backend.memory_sqlite import semantic_search_recordings, get_audio_recordings
            
            # Use semantic search as the primary retriever
            recordings = semantic_search_recordings(text, limit=3)
            
            # If the user is asking about a specific timeframe (e.g. today, yesterday), 
            # let's also fetch recent recordings by date to ensure we don't miss anything.
            recent_recs = []
            if "today" in lower_text or "this morning" in lower_text or "just now" in lower_text:
                recent_recs = get_audio_recordings(limit=5)
            elif "yesterday" in lower_text:
                from datetime import datetime, timedelta
                yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                all_recent = get_audio_recordings(limit=20)
                recent_recs = [r for r in all_recent if yesterday_str in r["timestamp"]]
                
            # Merge and de-duplicate
            seen_ids = {r["id"] for r in recordings}
            for r in recent_recs:
                if r["id"] not in seen_ids:
                    recordings.append(r)
                    seen_ids.add(r["id"])
                    
            if not recordings:
                reply = "I couldn't find any recorded conversations in my memory, Sir. Please make sure background recording is enabled and active."
            else:
                formatted_convs = []
                for idx, r in enumerate(recordings):
                    timestamp = r.get("timestamp", "Unknown time")
                    transcript = r.get("transcript", "")
                    summary = r.get("summary", "")
                    formatted_convs.append(
                        f"Conversation #{idx+1} (Date/Time: {timestamp})\n"
                        f"- Summary: {summary}\n"
                        f"- Transcript: {transcript}\n"
                    )
                formatted_conversations = "\n\n".join(formatted_convs)
                
                prompt = f"""
You are VOID, the highly advanced AI desktop assistant. The user is asking a question about their past conversations or background audio.
Answer the user's question accurately, clearly, and concisely, using only the provided conversation logs.

Retrieved Conversation Logs:
{formatted_conversations}

User Question:
{text}

Guidelines:
- Ground your answer strictly in the provided logs.
- If the logs do not contain the answer, say: "I couldn't find any mention of that in my recorded conversations, Sir."
- Avoid making up or inventing any details.
- Speak naturally and in a premium, helpful assistant tone (use "Sir", keep it professional but advanced).
"""
                from backend.llm_client import OllamaClient
                llm = VoidSingletons.get("llm") or OllamaClient()
                
                reply = await llm.router.chat(
                    history=[],
                    prompt=prompt,
                    system_prompt="You are VOID, an advanced AI assistant. You answer questions based on the provided conversation logs. Speak naturally like a human assistant."
                )
                
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            log_chat_request("memory_recall", "DIRECT_TOOL", "SQLite", "Success", start_time, confidence=1.0, endpoint="memory_sqlite.semantic_search_recordings")
            return {"reply": reply, "meta": {"intent": "memory_recall", "recordings_found": len(recordings)}}
        except Exception as e:
            logger.error(f"Error in audio memory RAG recall: {e}")
            reply = f"I encountered an error trying to search my conversation memory, Sir. Details: {e}"
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            return {"reply": reply, "meta": {"intent": "memory_recall", "error": str(e)}}
        
    # Memory Reads
    is_show_memory = "show memory database" in lower_text or lower_text in ["show memory", "show memory database", "show memory database."]
    is_deadline_query = "deadline" in lower_text or "my deadline" in lower_text
    
    if is_show_memory:
        facts = memory.list_facts()
        if not facts:
            reply = "Memory database is empty, Sir."
        else:
            facts_list = "\n".join([f"- {fact}" for fact in facts])
            reply = f"Here is the contents of the memory database, Sir:\n{facts_list}"
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("memory_read", "DIRECT_TOOL", "SQLite", "Success", start_time, confidence=1.0, endpoint="memory_sqlite.get_all_facts")
        return {"reply": reply, "meta": {"intent": "memory", "action": "show"}}
        
    if is_deadline_query:
        facts = memory.query_relevant(text, limit=3)
        if facts:
            reply = f"According to your memory database, Sir: {facts[0]}."
            status = "Success"
        else:
            reply = "I couldn't find any deadline in my memory database, Sir."
            status = "Failure"
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("memory_read", "DIRECT_TOOL", "SQLite", status, start_time, confidence=1.0, endpoint="memory_sqlite.query_semantic_facts")
        return {"reply": reply, "meta": {"intent": "memory", "action": "recall"}}
        
    # Telemetry and Diagnostics
    telemetry_keywords = [
        "system status", "current system status", "cpu", "ram", "storage",
        "battery", "temperature", "performance", "diagnostics", "computer health",
        "system info", "system stats", "computer stats", "pc health", "pc status"
    ]
    is_telemetry_query = any(kw in lower_text for kw in telemetry_keywords)
    
    if is_telemetry_query:
        stats_data = stats_collector.get_all_stats()
        cpu = stats_data.get("cpu_usage", 0)
        ram = stats_data.get("ram_usage", 0)
        ram_used = stats_data.get("ram_used_gb", 0)
        ram_total = stats_data.get("ram_total_gb", 0)
        storage_used = stats_data.get("storage_used_gb", 0)
        storage_total = stats_data.get("storage_total_gb", 0)
        battery = stats_data.get("battery_percent", "N/A")
        battery_plugged = "plugged in" if stats_data.get("battery_power_plugged") else "discharging"
        cpu_temp = stats_data.get("cpu_temp")
        temp_str = f", CPU Temp: {cpu_temp}°C" if cpu_temp else ""
        
        if any(w in lower_text for w in ["health", "diagnostics", "analyze", "check"]):
            cpu_status = "Healthy" if cpu < 80 else "High Load ⚠️"
            ram_status = "Healthy" if ram < 85 else "High Load ⚠️"
            storage_pct = (storage_used / (storage_total or 1)) * 100
            storage_status = "Healthy" if storage_pct < 90 else "Low Space ⚠️"
            
            reply = (
                f"📊 **Computer Health & Diagnostics Check**, Sir:\n"
                f"- **Overall Health**: Operational\n"
                f"- **CPU Status**: {cpu_status} (Currently at {cpu}%)\n"
                f"- **RAM Status**: {ram_status} ({ram}% used)\n"
                f"- **Storage Status**: {storage_status} ({storage_used} GB / {storage_total} GB)\n"
                f"- **Battery Level**: {battery}% ({battery_plugged})\n"
                f"- **Action Recommendation**: System diagnostics indicate operational stability."
            )
            intent_name = "diagnostics"
        else:
            reply = (
                f"🖥️ **System Telemetry & Health Report**, Sir:\n"
                f"- **CPU Usage**: {cpu}%{temp_str}\n"
                f"- **RAM Usage**: {ram}% ({ram_used} GB / {ram_total} GB)\n"
                f"- **Storage**: {storage_used} GB used / {storage_total} GB total\n"
                f"- **Battery**: {battery}% ({battery_plugged})"
            )
            intent_name = "system_status"
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request(intent_name, "DIRECT_TOOL", "SystemStats", "Success", start_time, confidence=1.0, endpoint="GET /stats")
        return {"reply": reply, "meta": {"intent": "system", "action": "stats"}}
        
    # Local Model discovery
    model_keywords = [
        "installed models", "ollama", "available models", "active model",
        "coding model", "vision model", "local ai models", "installed ai models",
        "list installed models", "list models"
    ]
    is_model_query = any(kw in lower_text for kw in model_keywords)
    
    if is_model_query:
        llm = VoidSingletons.get("llm") or OllamaClient()
        discovered = {"Coding": [], "Reasoning": [], "Planning": [], "Vision": [], "Chat": [], "Lightweight": [], "Large": []}
        if llm and hasattr(llm, "router") and hasattr(llm.router, "ollama_provider"):
            discovered = llm.router.ollama_provider.discover_and_categorize_models()
        
        active_model = "None"
        routing_mode = "AUTO"
        if llm and hasattr(llm, "router"):
            cfg = getattr(llm.router, "config", {})
            active_model = cfg.get("local_model", "qwen2.5:0.5b")
            routing_mode = cfg.get("routing_mode", "AUTO")
            
        all_models = []
        for cat, list_models in discovered.items():
            if list_models:
                all_models.extend(list_models)
                
        if not all_models:
            reply = (
                f"🤖 **Local AI Models Configuration**, Sir:\n"
                f"- **Active Local Model**: `{active_model}`\n"
                f"- **Routing Mode**: `{routing_mode}`\n"
                f"- **Discovered Models**: No local Ollama models detected. Please ensure the Ollama service is active and models are downloaded."
            )
        else:
            formatted_models = ", ".join([f"`{m}`" for m in all_models])
            reply = (
                f"🤖 **Local AI Models Configuration**, Sir:\n"
                f"- **Active Local Model**: `{active_model}`\n"
                f"- **Routing Mode**: `{routing_mode}`\n"
                f"- **Installed Models**: {formatted_models}"
            )
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("model_discovery", "DIRECT_TOOL", "OllamaProvider", "Success", start_time, confidence=1.0, endpoint="GET /api/llm/discovered-models")
        return {"reply": reply, "meta": {"intent": "system", "action": "discovered-models"}}
        
    # TODOs/Action Items
    is_todo_query = lower_text in ["show all todos", "show all todos.", "list todos", "what are my todos", "show todos"] or "todos" in lower_text or "todo" in lower_text
    
    if is_todo_query:
        from tools.meeting_assistant import get_action_items
        res = get_action_items()
        action_items = res.get("action_items", [])
        if not action_items:
            reply = "There are no pending action items or TODOs in my database, Sir."
        else:
            formatted = []
            for item in action_items:
                owner_str = f" (Assigned to: {item['owner']})" if item.get('owner') else ""
                deadline_str = f" [Due: {item['deadline']}]" if item.get('deadline') else ""
                formatted.append(f"- {item.get('description', 'Task')}{owner_str}{deadline_str}")
            reply = "Here are your pending action items and TODOs, Sir:\n" + "\n".join(formatted)
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("get_action_items", "DIRECT_TOOL", "MeetingAssistant", "Success", start_time, confidence=1.0, endpoint="tools.meeting_assistant.get_action_items")
        return {"reply": reply, "meta": {"intent": "command", "action": "get_action_items"}}
        
    # Intercept workflow commands
    from workflow_mode import is_workflow_command, execute_workflow_text
    if is_workflow_command(text):
        engine_tools = {
            "open_app": launch,
            "close_app": lambda app: launch(f"taskkill /f /im {app}.exe") if not app.endswith(".exe") else launch(f"taskkill /f /im {app}"),
            "search_web": lambda q: {"ok": True, "output": f"Searching for {q}"},
            "open_url": lambda u: launch(f"start {u}"),
            "time": lambda: {"ok": True, "reply": time.strftime("%I:%M %p")},
            "system_info": lambda: {"ok": True, "reply": f"System: {platform.system()} {platform.release()}"},
            "screenshot": lambda: {"ok": True, "message": "Screenshot taken"},
            "remember": lambda content: {"ok": True, "message": f"Remembered: {content}"},
            "recall": lambda q: {"ok": True, "message": f"Recalled for query: {q}"},
        }
        try:
            workflow_res = await asyncio.to_thread(execute_workflow_text, text, engine_tools)
            llm = VoidSingletons.get("llm") or OllamaClient()
            logs = "\n".join(workflow_res.get("logs", []))
            is_ok = workflow_res.get("ok", True)
            reply = await llm.summarize_tool_output(text, "workflow", f"OK={is_ok}, Steps: {logs}", is_success=is_ok)
            
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            log_chat_request("workflow", "LLM_REQUIRED", "workflow_engine", "Success" if is_ok else "Failure", start_time)
            return {"reply": reply, "meta": {"intent": "workflow", "result": workflow_res}}
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            from tools.error_interpreter import interpret_error
            friendly_err = interpret_error(str(e))
            reply = f"⚠️ Workflow execution failed, Sir. {friendly_err}"
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            log_chat_request("workflow", "LLM_REQUIRED", "workflow_engine", "Failure", start_time)
            return {"reply": reply, "meta": {"intent": "workflow", "error": str(e)}}
    
    # Handle explicit memory commands
    if text.lower() == "show memory":
        reply = memory.get_summary()
        log_chat_request("show_memory", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": reply, "meta": {"intent": "system"}}
    if text.lower() == "clear memory":
        memory.clear()
        log_chat_request("clear_memory", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": "Memory banks have been purged, Sir.", "meta": {"intent": "system"}}

    # Deterministic Developer Mode & Self-Modification Intercepts
    norm_text_lower = text.lower().strip()
    
    if norm_text_lower in ["enter developer mode", "enable developer mode", "developer mode on"]:
        from core.brain import enable_developer_mode
        enable_developer_mode()
        reply = "🔓 **Developer Mode Enabled**, Sir. Write access, self-repairs, and system self-modifications are now fully unlocked. I am standing by for engineering commands."
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("enable_developer_mode", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": reply, "meta": {"intent": "system"}}
        
    if norm_text_lower in ["exit developer mode", "disable developer mode", "developer mode off", "exit dev mode"]:
        from core.brain import disable_developer_mode
        disable_developer_mode()
        reply = "🔒 **Developer Mode Disabled**, Sir. System write access is locked. Operating in read-only safe mode."
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("disable_developer_mode", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": reply, "meta": {"intent": "system"}}
        
    if norm_text_lower in ["show developer mode", "developer mode status", "is developer mode enabled"]:
        from core.brain import is_developer_mode
        status_str = "🔓 ENABLED (Write/Modify Unlocked)" if is_developer_mode() else "🔒 DISABLED (Read-Only Safe Mode)"
        reply = f"🤖 **Developer Mode Status**: {status_str}, Sir."
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("developer_mode_status", "DIRECT_TOOL", "None", "Success", start_time)
        return {"reply": reply, "meta": {"intent": "system"}}

    if norm_text_lower == "repair yourself" or norm_text_lower == "run self repair":
        from core.brain import is_developer_mode
        if not is_developer_mode():
            reply = "🔒 **Action Denied**: Developer mode is currently disabled, Sir. Please say *\"enter developer mode\"* to enable self-repair access."
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            log_chat_request("repair_yourself", "DIRECT_TOOL", "None", "Failure", start_time)
            return {"reply": reply, "meta": {"intent": "system"}}
            
        from tools.self_modifier import self_repair_workflow
        res = await asyncio.to_thread(self_repair_workflow)
        actions_taken_list = [a.get("action", str(a)) if isinstance(a, dict) else str(a) for a in res.get('actions_taken', [])]
        reply = f"🔧 **Self-Repair Execution Complete**, Sir!\n\n**Action Status**: {res.get('status').upper()}\n- **Actions Taken**: {', '.join(actions_taken_list) or 'None'}\n- **Message**: {res.get('message')}"
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("repair_yourself", "DIRECT_TOOL", "self_repair", "Success" if res.get('status') == 'ok' else "Failure", start_time)
        return {"reply": reply, "meta": {"intent": "system", "result": res}}

    if norm_text_lower.startswith("rewrite module ") or norm_text_lower.startswith("improve module "):
        from core.brain import is_developer_mode
        if not is_developer_mode():
            reply = "🔒 **Action Denied**: Developer mode is currently disabled, Sir. Please say *\"enter developer mode\"* to enable rewrite and file edit capabilities."
            memory.remember_turn("user", text)
            memory.remember_turn("void", reply)
            log_chat_request("rewrite_module", "DIRECT_TOOL", "None", "Failure", start_time)
            return {"reply": reply, "meta": {"intent": "system"}}
            
        cmd_words = "rewrite module " if norm_text_lower.startswith("rewrite module ") else "improve module "
        module_clause = text[len(cmd_words):].strip()
        
        if " to " in module_clause:
            module_name, instructions = module_clause.split(" to ", 1)
        else:
            module_name, instructions = module_clause, "Improve and fix any latent issues"
            
        from tools.self_modifier import rewrite_module
        res = await asyncio.to_thread(rewrite_module, module_name, instructions)
        
        if res.get("status") == "ok":
            reply = (
                f"💻 **Module Rewrite Successful**, Sir!\n\n"
                f"Resolved Path: **{res.get('resolved_path')}**\n"
                f"- **Lines**: {res.get('improvement', {}).get('original_lines')} $\rightarrow$ {res.get('improvement', {}).get('improved_lines')}\n"
                f"- **Issues Resolved**: {', '.join(res.get('issues_found', [])) or 'None'}\n"
                f"- **Result**: {res.get('result', {}).get('message')}"
            )
        else:
            reply = f"❌ **Module Rewrite Failed**, Sir.\n\n**Error**: {res.get('message')}"
            
        memory.remember_turn("user", text)
        memory.remember_turn("void", reply)
        log_chat_request("rewrite_module", "LLM_REQUIRED", "self_modifier", "Success" if res.get('status') == 'ok' else "Failure", start_time)
        return {"reply": reply, "meta": {"intent": "system", "result": res}}



    # Local Math Intercept
    math_reply = evaluate_math_locally(text)
    if math_reply is not None:
        memory.remember_turn("user", text)
        memory.remember_turn("void", math_reply)
        log_chat_request("math_calculation", "DIRECT_TOOL", "math_evaluator", "Success", start_time)
        return {"reply": math_reply, "meta": {"intent": "command", "action": "math_evaluator"}}

    history = memory.short_term[-10:]
    
    # Get singletons
    llm = VoidSingletons.get("llm") or OllamaClient()
    router = VoidSingletons.get("router")
    
    # Auto-learn user facts
    try:
        from backend.memory_manager import extract_and_remember
        extract_and_remember(text)
    except Exception as e:
        logger.error(f"Failed to auto-extract facts: {e}")
        
    orig_prompt = llm.system_prompt
    try:
        intent = None
        try:
            if router:
                intent = await router.classify(text)
        except Exception as e:
            logger.error(f"Intent classification failed: {e}. Falling back to pure chat mode.")
            
        try:
            from backend.emotion_engine import EmotionEngine
            engine = EmotionEngine()
            engine.process_turn(text)
            
            modifier = EmotionEngine.get_system_prompt_modifier()
            if modifier:
                llm.system_prompt = orig_prompt + modifier
            else:
                llm.system_prompt = orig_prompt

            try:
                from core.voice_ai.voice_profile import VoiceProfileManager
                profile_mgr = VoiceProfileManager()
                personality_modifier = profile_mgr.get_prompt_modifier()
                if personality_modifier:
                    llm.system_prompt += personality_modifier
            except Exception as v_err:
                logger.error(f"Voice profile prompt modification failed: {v_err}")
        except Exception as emo_err:
            logger.error(f"Emotion engine processing failed: {emo_err}")
        
        if intent and intent.action in ["agent_scan", "agent_explain", "agent_code", "agent_run_tests", "agent_fix_errors", "agent_refactor"]:
            from core.autonomous_agent import AutonomousAgent
            from pathlib import Path
            root = Path(__file__).parent.parent
            agent = AutonomousAgent(str(root))
            
            meta = {"intent": intent.intent, "action": intent.action}
            
            if intent.action == "agent_scan":
                res = await agent.scan_and_map()
                final_reply = f"🔍 **Project Scan Complete**, Sir!\n- **Technology Stack**: {', '.join(res.get('frameworks', [])) or 'None detected'}\n- **Entry Points**: {', '.join(res.get('entry_points', [])) or 'None detected'}\n- **Files Scanned**: {len(res.get('files', []))}"
            elif intent.action == "agent_explain":
                final_reply = await agent.explain_architecture()
            elif intent.action == "agent_code":
                instructions = intent.params.get("instructions", "")
                res = await agent.process_intent(instructions)
                if res.get("status") == "pending_confirmation":
                    final_reply = f"⚠️ **Action Requires User Confirmation**, Sir!\n- **Message**: {res.get('message')}\n- **Pending Step**: {json.dumps(res.get('pending_step'))}"
                    meta["status"] = "pending_confirmation"
                    meta["pending_step"] = res.get("pending_step")
                elif res.get("status") == "error":
                    final_reply = f"❌ **Agent Error**: {res.get('message')}"
                else:
                    final_reply = f"✅ **Code Modifications Applied**, Sir!\n- **Backup Branch**: `{res.get('backup_branch')}`\n- **Steps Executed**: {len(res.get('results', []))}"
            elif intent.action == "agent_run_tests":
                res = await agent.terminal_engine.execute_command("pytest")
                final_reply = f"🧪 **Test Execution Output**, Sir!\n- **Exit Code**: {res.get('exit_code')}\n- **Stdout**:\n```\n{res.get('stdout', '')[:500]}\n```"
            elif intent.action == "agent_fix_errors":
                logs = intent.params.get("logs", "")
                res = await agent.handle_build_error(logs)
                if res.get("status") == "error":
                    final_reply = f"❌ **Error Fix Failed**: {res.get('message')}"
                else:
                    final_reply = f"🔧 **Build Error Fix Attempted**, Sir!\n- **Details**: {res.get('message')}\n- **Analysis**:\n{res.get('analysis')}"
            elif intent.action == "agent_refactor":
                file_path = intent.params.get("file_path", "")
                res = await agent.refactor_code(file_path)
                if res.get("status") == "error":
                    final_reply = f"❌ **Refactor Failed**: {res.get('message')}"
                else:
                    final_reply = f"🧹 **Code Refactoring Applied**, Sir!\n- **Target File**: `{file_path}`\n- **Backup Branch**: `{res.get('backup_branch')}`\n- **Details**: {res.get('message')}"
            
            memory.remember_turn("user", text)
            memory.remember_turn("void", final_reply)
            log_chat_request(intent.action, "LLM_REQUIRED", "agent_assistant", "Success", start_time)
            return {"reply": final_reply, "meta": meta}
            
        elif intent and intent.intent == "deep_research":
            topic = intent.params.get("topic", text)
            from backend.deep_research import ResearchManager
            manager = ResearchManager()
            final_reply = await manager.run_workflow(topic)
            
        elif intent and intent.intent == "academic":
            from backend.academic_engine import AcademicEngine
            engine = AcademicEngine()
            res = await engine.execute_query(text)
            final_reply = res.get("reply", "")
            intent.action = res.get("meta", {}).get("mode", "quick_answer")
            intent.params = res.get("meta", {})
            
        elif intent and intent.intent == "command" and intent.action == "change_motd":
            new_motd = intent.params.get("motd", "").strip()
            if (not new_motd or "message of the day" in new_motd.lower() or "motd" in new_motd.lower() or 
                    new_motd.lower() in ["on the pannel", "on the panel", "pannel", "panel", "to the panel"]):
                prompt = (
                    "Generate a single short, extremely cool, motivating cyberpunk-style 'Message of the Day' "
                    "for a software engineer's desktop panel (max 10 words). speak naturally, do NOT include quotes, "
                    "do NOT explain, and keep it punchy and related to coding/focus."
                )
                generated = await asyncio.wait_for(llm.chat([], prompt), timeout=150.0)
                new_motd = generated.strip().strip('"').strip("'")
            
            global MOTD
            MOTD = new_motd
            final_reply = f"Understood, Sir. I have updated the panel's Message of the Day to: \"{new_motd}\""
            
        elif intent and (intent.intent == "command" or (intent.intent == "system" and intent.action in ["repair", "diagnostics"])):
            action_name = "repair_self" if intent.action == "repair" else intent.action
            if action_name in DIRECT_TOOLS:
                # Bypasses Ollama completely
                try:
                    tm = VoidSingletons.get("tool_manager")
                    result = await tm.execute(action_name, intent.params)
                    is_success = result.meta.get("status") != "FAIL"
                    final_reply = humanize_tool_output_locally(action_name, intent.params, result.output, is_success)
                    
                    memory.remember_turn("user", text)
                    memory.remember_turn("void", final_reply)
                    log_chat_request(intent.action, "DIRECT_TOOL", action_name, "Success" if is_success else "Failure", start_time)
                    return {"reply": final_reply, "meta": {"intent": intent.intent, "action": intent.action}}
                except Exception as tool_err:
                    logger.error(f"Direct tool execution failed: {tool_err}")
                    from tools.error_interpreter import interpret_error
                    friendly_err = interpret_error(str(tool_err))
                    final_reply = f"⚠️ Tool execution failed, Sir. {friendly_err}"
                    
                    memory.remember_turn("user", text)
                    memory.remember_turn("void", final_reply)
                    log_chat_request(intent.action, "DIRECT_TOOL", action_name, "Failure", start_time)
                    return {
                        "reply": final_reply,
                        "meta": {
                            "intent": intent.intent,
                            "action": intent.action,
                            "status": "error",
                            "error": str(tool_err),
                            "severity": "high"
                        }
                    }
            else:
                # LLM required to summarize tool output
                try:
                    tm = VoidSingletons.get("tool_manager")
                    result = await tm.execute(action_name, intent.params)
                    is_success = result.meta.get("status") != "FAIL"
                    
                    final_reply = await asyncio.wait_for(
                        llm.summarize_tool_output(text, action_name, result.output, is_success=is_success),
                        timeout=150.0
                    )
                    
                    memory.remember_turn("user", text)
                    memory.remember_turn("void", final_reply)
                    log_chat_request(intent.action, "LLM_REQUIRED", action_name, "Success" if is_success else "Failure", start_time)
                    return {"reply": final_reply, "meta": {"intent": intent.intent, "action": intent.action}}
                except asyncio.TimeoutError as time_err:
                    logger.error("LLM tool summarization timed out.")
                    from tools.error_interpreter import translate_exception
                    translated = translate_exception(time_err)
                    final_reply = f"⚠️ Action completed but LLM response timed out, Sir. Raw: {result.output[:100]}..."
                    log_chat_request(intent.action, "LLM_REQUIRED", action_name, "Failure", start_time)
                    return {
                        "reply": final_reply,
                        "meta": {
                            "intent": intent.intent,
                            "action": intent.action,
                            "status": "error",
                            "error": "TimeoutError",
                            "error_title": translated["title"],
                            "error_action": translated["action"],
                            "severity": "high"
                        }
                    }
                except Exception as tool_err:
                    logger.error(f"Tool execution or humanization failed: {tool_err}")
                    from tools.error_interpreter import interpret_error
                    friendly_err = interpret_error(str(tool_err))
                    final_reply = f"⚠️ Tool execution failed, Sir. {friendly_err}"
                    log_chat_request(intent.action, "LLM_REQUIRED", action_name, "Failure", start_time)
                    return {
                        "reply": final_reply,
                        "meta": {
                            "intent": intent.intent,
                            "action": intent.action,
                            "status": "error",
                            "error": str(tool_err),
                            "severity": "high"
                        }
                    }
        else:
            # Pure chat — send to LLM with conversation history and a timeout guard
            intent_name = intent.intent if intent else "pure_chat"
            action_name = intent.action if intent else None
            # --- Ollama readiness pre-check ---
            try:
                ollama_up = await asyncio.wait_for(is_ollama_ready(), timeout=2.0)
                if not ollama_up:
                    logger.warning("[CHAT] Ollama not reachable — attempting auto-restart")
                    await asyncio.wait_for(ensure_ollama(), timeout=25.0)
                    ollama_up = await is_ollama_ready()
                if not ollama_up:
                    reply = "Ollama service is offline, Sir. I've attempted to restart it — please try again in a few seconds."
                    memory.remember_turn("user", text)
                    memory.remember_turn("void", reply)
                    log_chat_request(intent_name, "LLM_REQUIRED", "None", "Failure", start_time)
                    return {"reply": reply, "meta": {"intent": intent_name, "status": "error", "error": "OllamaOffline"}}
            except asyncio.TimeoutError:
                logger.error("[CHAT] Ollama readiness check timed out")
            # ----------------------------------
            try:
                final_reply = await asyncio.wait_for(
                    llm.chat(history, text),
                    timeout=150.0
                )
            except asyncio.TimeoutError as time_err:
                logger.error("LLM chat timed out.")
                from tools.error_interpreter import translate_exception
                translated = translate_exception(time_err)
                final_reply = "⚠️ Ollama is taking too long to generate a response, Sir. Please check if the service is loaded and running."
                log_chat_request(intent_name, "LLM_REQUIRED", "None", "Failure", start_time)
                return {
                    "reply": final_reply,
                    "meta": {
                        "intent": intent_name,
                        "action": action_name,
                        "status": "error",
                        "error": "TimeoutError",
                        "error_title": translated["title"],
                        "error_action": translated["action"],
                        "severity": "high"
                    }
                }
            except Exception as e:
                logger.error(f"LLM chat failed: {e}")
                from tools.error_interpreter import translate_exception
                translated = translate_exception(e)
                final_reply = f"⚠️ Ollama request failed, Sir. Reason: {e}"
                log_chat_request(intent_name, "LLM_REQUIRED", "None", "Failure", start_time)
                return {
                    "reply": final_reply,
                    "meta": {
                        "intent": intent_name,
                        "action": action_name,
                        "status": "error",
                        "error": type(e).__name__,
                        "error_title": translated.get("title", "Service Error"),
                        "error_action": translated.get("action", "Please check if Ollama is running and responsive."),
                        "severity": "high"
                    }
                }
        
        # Single memory write (no duplicates) for deep research, academic, etc. fall-throughs
        memory.remember_turn("user", text)
        memory.remember_turn("void", final_reply)
        
        intent_name = intent.intent if intent else "pure_chat"
        action_name = intent.action if intent else None
        log_chat_request(action_name or intent_name, "LLM_REQUIRED", "None", "Success", start_time)
        return {"reply": final_reply, "meta": {"intent": intent_name, "action": action_name}}
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        from tools.error_interpreter import translate_exception
        translated = translate_exception(e)
        intent_name = intent.intent if intent else "pure_chat"
        action_name = intent.action if intent else None
        log_chat_request(action_name or intent_name, "LLM_REQUIRED", "None", "Failure", start_time)
        return {
            "reply": f"⚠️ I encountered an issue, Sir. {translated['title']}: {translated['message']}",
            "meta": {
                "intent": intent_name,
                "action": action_name,
                "status": "error",
                "error": str(e),
                "error_title": translated["title"],
                "error_action": translated["action"],
                "severity": translated["severity"]
            }
        }
    finally:
        llm.system_prompt = orig_prompt


class WorkflowRequest(BaseModel):
    text: str

