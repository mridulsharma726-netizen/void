import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

import requests

logger = logging.getLogger("void.llm")

_PROJECT_FILES_CACHE = {}

# Import the rich owner profile
try:
    from backend.owner_profile import get_owner_system_prompt
    _BASE_PROMPT = get_owner_system_prompt()
except ImportError:
    _BASE_PROMPT = "You are VOID, a highly advanced AI system. Your creator and master is Mridul Sharma. Keep responses concise."

# Append anti-raw-data instructions
SYSTEM_PROMPT = _BASE_PROMPT + """

RESPONSE FORMATTING RULES:
- NEVER output raw JSON, Python dicts, file paths, status codes, or technical error strings.
- NEVER say things like "{'status': 'ok'}" or "HTTP 500" or "Error: connection refused".
- Always speak naturally, like a human assistant would.
- If a tool/action succeeded, describe the outcome naturally (e.g., "Chrome is open now, Sir." not "✅ Opened 'chrome'").
- If a tool/action failed, explain what went wrong simply (e.g., "I couldn't open that app, Sir. It might not be installed." not "❌ Failed to open 'app': FileNotFoundError").
- Use markdown formatting when helpful: **bold** for emphasis, `code` for technical terms, bullet lists for multiple items.
- Keep responses concise — 1-3 sentences for simple things, more for complex explanations."""

class OllamaClient:
    def __init__(self, model: str = "llama3.2:3b", base_url: str = "http://127.0.0.1:11434"):
        self.model = model
        self.chat_url = f"{base_url}/api/chat"
        self.tags_url = f"{base_url}/api/tags"
        self.timeout = 90  # Increase to 90s to allow model loading under heavy load
        self.system_prompt = SYSTEM_PROMPT
        self.model_detected = False
        self._detect_model()

    def _detect_model(self):
        try:
            resp = requests.get(self.tags_url, timeout=5.0)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                for fast_model in ["qwen2.5:0.5b", "qwen2.5:1.5b"]:
                    if fast_model in models or f"{fast_model}:latest" in models:
                        self.model = fast_model
                        logger.info(f"[LLM] Auto-selected fast model: {self.model}")
                        break
                self.model_detected = True
        except Exception as e:
            logger.debug(f"[LLM] Model detection failed: {e}")

    def classify_intent(self, user_text: str) -> Dict[str, Any]:
        """Classifies the query intent for diagnostics logging."""
        text_lower = user_text.lower()
        
        project_keywords = [
            "project", "codebase", "files", "build", "blocker", "authentication", 
            "database", "databases", "payment", "completion", "launch", "auth", "sqlite", 
            "progress", "completed", "complete", "todo", "todos", "bug", "bugs",
            "changed", "changes", "yesterday", "voice functionality", "diagnostics"
        ]
        is_project_query = any(kw in text_lower for kw in project_keywords)
        
        file_commands = [
            "find file", "search for file", "read file", "write file", "save file", 
            "list directory", "list folder", "show directory", "show folder", 
            "open folder", "open file"
        ]
        is_file_command = any(cmd in text_lower for cmd in file_commands)
        
        automation_keywords = [
            "open", "launch", "close", "kill", "start", "run", "execute", "cmd", "shell",
            "whatsapp", "arrange windows", "split windows", "tile windows", 
            "schedule", "calendar", "email", "spawn", "refactor", "optimize"
        ]
        is_automation = any(kw in text_lower for kw in automation_keywords)
        
        if is_project_query:
            return {
                "intent": "PROJECT_QUERY",
                "confidence": 0.95 if any(w in text_lower for w in ["voice", "database", "files", "diagnostics"]) else 0.80,
                "reason": f"Matches project keywords: {[kw for kw in project_keywords if kw in text_lower]}"
            }
        elif is_file_command:
            return {
                "intent": "FILE_COMMAND",
                "confidence": 0.90,
                "reason": "Matches file command patterns"
            }
        elif is_automation:
            return {
                "intent": "AUTOMATION",
                "confidence": 0.85,
                "reason": "Matches automation/control keywords"
            }
        else:
            return {
                "intent": "GENERAL_CHAT",
                "confidence": 0.70,
                "reason": "Default conversational fallback"
            }

    async def available(self) -> bool:
        try:
            requests.get(self.tags_url, timeout=2.0)
            return True
        except:
            return False

    async def warmup(self) -> bool:
        try:
            await self.chat([], "ping")
            return True
        except:
            return False

    def _get_dynamic_options(self, user_text: str) -> Dict[str, Any]:
        """Analyzes prompt content to return optimal parameters for Ollama."""
        text_lower = user_text.lower()
        
        # Check for Creative Writing intent
        creative_keywords = [
            "write a story", "write a poem", "compose", "creative writing", "write a song", 
            "create a story", "tell a story", "fictional", "write an essay", "poetry",
            "screenplay", "script", "creative content"
        ]
        is_creative = any(kw in text_lower for kw in creative_keywords) or (
            "write" in text_lower and any(w in text_lower for w in ["story", "poem", "song", "script", "novel", "lyrics", "fiction"])
        )
        
        # Check for Logic Puzzle / Reasoning intent
        puzzle_keywords = [
            "puzzle", "riddle", "logic", "solve", "math", "reasoning", "step by step",
            "explain why", "prove", "algorithmic", "how to solve"
        ]
        is_puzzle = any(kw in text_lower for kw in puzzle_keywords)
        
        if is_creative:
            return {
                "temperature": 0.85,
                "num_predict": 1024,
                "num_ctx": 4096,
                "num_thread": 4
            }
        elif is_puzzle:
            return {
                "temperature": 0.15,
                "num_predict": 1024,
                "num_ctx": 4096,
                "num_thread": 4
            }
        else:
            return {
                "temperature": 0.7,
                "num_predict": 512,
                "num_ctx": 4096,
                "num_thread": 4
            }

    def build_context_prompt(self, user_text: str) -> str:
        """Dynamically inserts relevant stored memories/facts and project intelligence into system prompt context."""
        try:
            from backend.memory_manager import query_semantic_facts
            # Retrieve semantic matches
            relevant_facts = query_semantic_facts(user_text, limit=3)
            
            # Retrieve preferred user context profile
            try:
                from backend.owner_profile import get_preference_context
                pref_context = get_preference_context()
            except ImportError:
                pref_context = "No stored memory yet."
                
            memory_block = []
            if relevant_facts:
                memory_block.append("Relevant Stored Facts:\n" + "\n".join(f"- {fact}" for fact in relevant_facts))
            if pref_context and pref_context != "No stored memory yet.":
                memory_block.append(f"User Profile & Preferences:\n{pref_context}")
                
            # --- STAGE 1: INTENT CLASSIFICATION ---
            intent_info = self.classify_intent(user_text)
            logger.info(
                f"\n[INTENT]\n"
                f"Detected Intent: {intent_info['intent']}\n"
                f"Confidence: {intent_info['confidence']:.2f}\n"
                f"Reason: {intent_info['reason']}\n"
            )

            # --- STAGE 2: PROJECT DETECTION ---
            import os
            from backend.memory_sqlite import get_active_project, get_project_files, get_pending_action_items
            
            active_proj = get_active_project()
            if active_proj:
                proj_path_check = active_proj.get("path")
                if not proj_path_check or not os.path.isdir(proj_path_check):
                    logger.warning(f"[PROJECT DETECTION] Active project path does not exist: {proj_path_check}")
                    active_proj = None
            
            project_found_str = "Yes" if active_proj else "No"
            proj_name = active_proj.get("name", "None") if active_proj else "None"
            proj_path = active_proj.get("path", "None") if active_proj else "None"
            logger.info(
                f"\n[PROJECT]\n"
                f"Project Found: {project_found_str}\n"
                f"Project Name: {proj_name}\n"
                f"Project Path: {proj_path}\n"
            )

            # --- STAGE 3: RETRIEVAL LAYER ---
            all_files = []
            relevant_files = []
            blockers = []
            dependencies = []
            databases_detected = []
            
            if active_proj:
                proj_id = active_proj["project_id"]
                import time
                now = time.time()
                if proj_id in _PROJECT_FILES_CACHE and (now - _PROJECT_FILES_CACHE[proj_id][0]) < 30.0:
                    all_files = _PROJECT_FILES_CACHE[proj_id][1]
                else:
                    all_files = get_project_files(proj_id)
                    _PROJECT_FILES_CACHE[proj_id] = (now, all_files)
                
                # Check for files
                import re
                query_words = [w for w in re.split(r'\W+', user_text.lower()) if len(w) > 2]
                for f in all_files:
                    f_path = f["path"].lower()
                    if len(all_files) <= 50 or any(qw in f_path for qw in query_words):
                        relevant_files.append(f["path"])
                relevant_files = relevant_files[:40]
                
                # Retrieve blockers
                from tools.project_intelligence import detect_project_blockers
                try:
                    blockers = detect_project_blockers(active_proj["path"])
                except Exception:
                    pass
                if not blockers:
                    try:
                        import json
                        blockers = json.loads(active_proj.get("blockers", "[]"))
                    except:
                        pass
                
                # Retrieve package/project dependencies
                req_file = os.path.join(active_proj["path"], "requirements.txt")
                if os.path.isfile(req_file):
                    try:
                        with open(req_file, "r", encoding="utf-8") as f:
                            for line in f:
                                dep = line.strip().split("==")[0].strip()
                                if dep and not dep.startswith("#"):
                                    dependencies.append(dep)
                    except:
                        pass
                
                # Find database files on disk dynamically to ensure actual databases list
                ignored_dirs = {"node_modules", "venv", ".venv", ".git", "dist", "build", "__pycache__", ".cache"}
                for root, dirs, files_list in os.walk(active_proj["path"]):
                    dirs[:] = [d for d in dirs if d not in ignored_dirs]
                    for filename in files_list:
                        ext = os.path.splitext(filename)[1].lower()
                        if ext in [".db", ".sqlite", ".sqlite3"]:
                            databases_detected.append(filename)
                databases_detected = sorted(list(set(databases_detected)))
                
                # Calculate completion percentage
                import json
                try:
                    f_completed = json.loads(active_proj.get("features_completed", "[]"))
                    f_wip = json.loads(active_proj.get("features_progress", "[]"))
                    f_planned = json.loads(active_proj.get("features_planned", "[]"))
                except:
                    f_completed, f_wip, f_planned = [], [], []

                total_f = len(f_completed) + len(f_wip) + len(f_planned)
                completion_pct = 0
                if total_f > 0:
                    completion_pct = round((len(f_completed) / total_f) * 100)
                else:
                    all_items = get_pending_action_items()
                    if len(all_files) > 0:
                        completion_pct = max(20, 95 - (len(all_items) * 3))
                        completion_pct = min(95, completion_pct)
                
                proj_context = (
                    f"[ACTIVE PROJECT INTELLIGENCE]\n"
                    f"Project Name: {active_proj.get('name')}\n"
                    f"Path: {active_proj.get('path')}\n"
                    f"Purpose: {active_proj.get('purpose', 'Unknown')}\n"
                    f"Architecture: {active_proj.get('architecture', 'Unknown')}\n"
                    f"Technologies: {active_proj.get('technologies', '[]')}\n"
                    f"Estimated Completion: {completion_pct}%\n"
                    f"Completed Modules: {active_proj.get('features_completed', '[]')}\n"
                    f"Pending Modules: {active_proj.get('features_planned', '[]')}\n"
                    f"Goals: {active_proj.get('goals', '[]')}\n"
                    f"Known Bugs: {active_proj.get('known_bugs', '[]')}\n"
                    f"Development History: {active_proj.get('development_history', '[]')}\n"
                    f"Current Blockers: {blockers}\n"
                    f"Dependencies: {dependencies}\n"
                    f"Databases Detected: {databases_detected}\n"
                    f"Relevant Files: {', '.join(relevant_files) if relevant_files else 'None'}\n"
                    f"[END ACTIVE PROJECT INTELLIGENCE]\n\n"
                    f"Safety Rules for Project Q&A:\n"
                    f"- Use the provided [ACTIVE PROJECT INTELLIGENCE] context to answer user questions about the project, files, blockers, or progress.\n"
                    f"- Never guess or make assumptions about file paths, databases, APIs, or features.\n"
                    f"- If the requested information is not explicitly clear or available in the project context, say: 'I do not have enough project data to determine that.'\n"
                    f"- Never delete or modify project files without explicit user approval."
                )
                memory_block.append(proj_context)
            else:
                proj_context = (
                    f"[ACTIVE PROJECT INTELLIGENCE]\n"
                    f"No active project is currently scanned or tracked.\n"
                    f"[END ACTIVE PROJECT INTELLIGENCE]\n\n"
                    f"Safety Rules for Project Q&A:\n"
                    f"- Since there is no active project scanned, you MUST say exactly: 'I do not have enough project data to determine that.'\n"
                    f"- Do not make any assumptions or guess anything."
                )
                memory_block.append(proj_context)
                
            logger.info(
                f"\n[RETRIEVAL]\n"
                f"Files Retrieved: {len(all_files) if active_proj else 0}\n"
                f"Blockers Retrieved: {len(blockers)}\n"
                f"Dependencies Retrieved: {len(dependencies)}\n"
                f"Memory Records Retrieved: {len(relevant_facts)}\n"
            )

            # --- STAGE 5: LLM ENFORCEMENT ---
            sys_prompt = self.system_prompt
            if intent_info["intent"] == "PROJECT_QUERY":
                sys_prompt += """
                
CRITICAL RULES FOR PROJECT QUESTIONS (STRICT COMPLIANCE REQUIRED):
1. Never answer using general knowledge or fabricate details.
2. Use ONLY the explicitly provided [ACTIVE PROJECT INTELLIGENCE] context.
3. If the context has no files, no databases, or does not contain direct evidence to answer the user's question, you MUST respond with exactly: "I do not have enough project data to determine that."
4. Never fabricate file names, databases, blockers, meetings, dependencies, or diagnostics.
5. For example, if asked about database files, only list the files explicitly given in 'Databases Detected'. If none are listed, say "I do not have enough project data to determine that."
"""

            enriched_context = ""
            if memory_block:
                enriched_context = "\n\n[MEMORY CONTEXT]\n" + "\n\n".join(memory_block) + "\n[END MEMORY CONTEXT]"

            # --- STAGE 4: CONTEXT INJECTION ---
            logger.info(
                f"\n[CONTEXT]\n"
                f"Context Length: {len(enriched_context)}\n"
                f"Project Data Injected: {'Yes' if active_proj else 'No'}\n"
                f"Files Injected: {len(relevant_files) if active_proj else 0}\n"
                f"Blockers Injected: {len(blockers)}\n"
            )
            
            return sys_prompt + enriched_context
        except Exception as e:
            logger.error(f"Failed to build enriched context prompt: {e}")
        return self.system_prompt

    async def chat(self, history: List[Dict], user_text: str) -> str:
        if not self.model_detected:
            self._detect_model()

        # --- STAGE 6: EVIDENCE REQUIREMENT ---
        intent_info = self.classify_intent(user_text)
        if intent_info["intent"] == "PROJECT_QUERY":
            from backend.memory_sqlite import get_active_project, get_project_files
            active_proj = get_active_project()
            if active_proj:
                import os
                if not active_proj.get("path") or not os.path.isdir(active_proj["path"]):
                    active_proj = None
            
            has_evidence = False
            if active_proj:
                proj_id = active_proj["project_id"]
                all_files = get_project_files(proj_id)
                if all_files:
                    stopwords = {
                        "what", "is", "the", "are", "by", "used", "in", "of", "and", "or", "for", "to", "with", 
                        "a", "an", "on", "at", "handle", "list", "show", "get", "find", "inspect", "all",
                        "project", "projects", "file", "files", "codebase", "program", "script", "folder",
                        "directory", "directories", "workspace", "workspaces", "system", "systems", "void"
                    }
                    query_words = [w for w in re.split(r'\W+', user_text.lower()) if len(w) > 2 and w not in stopwords]
                    
                    if not query_words:
                        has_evidence = True
                    else:
                        relevant_files = [f["path"] for f in all_files if any(qw in f["path"].lower() for qw in query_words)]
                        
                        # Find database files on disk dynamically to ensure actual databases list
                        db_files = []
                        ignored_dirs = {"node_modules", "venv", ".venv", ".git", "dist", "build", "__pycache__", ".cache"}
                        for root, dirs, files_list in os.walk(active_proj["path"]):
                            dirs[:] = [d for d in dirs if d not in ignored_dirs]
                            for filename in files_list:
                                ext = os.path.splitext(filename)[1].lower()
                                if ext in [".db", ".sqlite", ".sqlite3"]:
                                    db_files.append(filename.lower())
                        
                        relevant_dbs = [db for db in db_files if any(qw in db for qw in query_words)]
                        
                        purpose = active_proj.get("purpose", "").lower()
                        techs = active_proj.get("technologies", "").lower()
                        blockers_str = active_proj.get("blockers", "").lower()
                        
                        has_matching_meta = any(qw in purpose or qw in techs or qw in blockers_str for qw in query_words)
                        
                        if "diagnostics" in query_words or "voice" in query_words:
                            if any("voice" in f["path"].lower() or "tts" in f["path"].lower() or "stt" in f["path"].lower() for f in all_files):
                                has_evidence = True
                        
                        if relevant_files or relevant_dbs or has_matching_meta:
                            has_evidence = True
            
            if not has_evidence:
                logger.info("[EVIDENCE CHECK] No evidence found in project for query. Returning fallback response.")
                # We still generate the logs and print final prompt as requested
                system_prompt = self.build_context_prompt(user_text)
                logger.info(
                    f"\n--- FINAL PROMPT SENT TO OLLAMA ---\n"
                    f"Model: {self.model}\n"
                    f"System Prompt:\n{system_prompt}\n"
                    f"User Message:\n{user_text}\n"
                    f"----------------------------------\n"
                )
                return "I do not have enough project data to determine that."

        system_prompt = self.build_context_prompt(user_text)
        messages = [{"role": "system", "content": system_prompt}] + history[-5:] + [{"role": "user", "content": user_text}]
        options = self._get_dynamic_options(user_text)
        
        # Log final prompt sent to Ollama
        logger.info(
            f"\n--- FINAL PROMPT SENT TO OLLAMA ---\n"
            f"Model: {self.model}\n"
            f"System Prompt:\n{system_prompt}\n"
            f"User Message:\n{user_text}\n"
            f"----------------------------------\n"
        )
        try:
            resp = await asyncio.to_thread(lambda: requests.post(
                self.chat_url, 
                json={
                    "model": self.model, 
                    "messages": messages, 
                    "stream": False,
                    "options": options
                }, 
                timeout=(3.0, self.timeout)
            ))
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"[LLM ERROR] Chat failed: {e}", exc_info=True)
            return "I'm having a brief connection issue, Sir. Give me a moment."

    async def summarize_tool_output(self, user_request: str, action_name: str, raw_output: str, is_success: bool = True) -> str:
        """Pass raw tool output through LLM to produce a natural, human-friendly response."""
        if not is_success:
            try:
                from tools.error_interpreter import interpret_error
                friendly_error = interpret_error(raw_output)
            except Exception:
                friendly_error = "An unexpected error occurred during execution."

            prompt = (
                f"The user asked: \"{user_request}\"\n"
                f"I executed the action '{action_name}' but it failed with this raw error: {raw_output}\n"
                f"Human-friendly explanation of the issue: {friendly_error}\n\n"
                f"Respond to the user with a respectful, concise explanation of the failure and what they can do next, "
                f"speaking in your premium cybernetic AI assistant persona (addressing them as Sir/Master Mridul). "
                f"Be direct, polite, and explain the next step. Do NOT include raw traceback text or JSON."
            )
        else:
            prompt = (
                f"The user asked: \"{user_request}\"\n"
                f"I executed the action '{action_name}' and got this raw result: {raw_output}\n\n"
                f"Respond naturally to the user about what happened. Be concise and conversational. "
                f"Do NOT include the raw output — describe the outcome in plain English, "
                f"speaking in your premium cybernetic AI assistant persona (addressing them as Sir/Master Mridul)."
            )
        return await self.chat([], prompt)

    async def chat_stream(self, history: List[Dict], user_text: str) -> AsyncGenerator[str, None]:
        if not self.model_detected:
            self._detect_model()

        # --- STAGE 6: EVIDENCE REQUIREMENT ---
        intent_info = self.classify_intent(user_text)
        if intent_info["intent"] == "PROJECT_QUERY":
            from backend.memory_sqlite import get_active_project, get_project_files
            active_proj = get_active_project()
            if active_proj:
                import os
                if not active_proj.get("path") or not os.path.isdir(active_proj["path"]):
                    active_proj = None
            
            has_evidence = False
            if active_proj:
                proj_id = active_proj["project_id"]
                all_files = get_project_files(proj_id)
                if all_files:
                    stopwords = {
                        "what", "is", "the", "are", "by", "used", "in", "of", "and", "or", "for", "to", "with", 
                        "a", "an", "on", "at", "handle", "list", "show", "get", "find", "inspect", "all",
                        "project", "projects", "file", "files", "codebase", "program", "script", "folder",
                        "directory", "directories", "workspace", "workspaces", "system", "systems", "void"
                    }
                    query_words = [w for w in re.split(r'\W+', user_text.lower()) if len(w) > 2 and w not in stopwords]
                    
                    if not query_words:
                        has_evidence = True
                    else:
                        relevant_files = [f["path"] for f in all_files if any(qw in f["path"].lower() for qw in query_words)]
                        
                        # Find database files on disk dynamically to ensure actual databases list
                        db_files = []
                        ignored_dirs = {"node_modules", "venv", ".venv", ".git", "dist", "build", "__pycache__", ".cache"}
                        for root, dirs, files_list in os.walk(active_proj["path"]):
                            dirs[:] = [d for d in dirs if d not in ignored_dirs]
                            for filename in files_list:
                                ext = os.path.splitext(filename)[1].lower()
                                if ext in [".db", ".sqlite", ".sqlite3"]:
                                    db_files.append(filename.lower())
                        
                        relevant_dbs = [db for db in db_files if any(qw in db for qw in query_words)]
                        
                        purpose = active_proj.get("purpose", "").lower()
                        techs = active_proj.get("technologies", "").lower()
                        blockers_str = active_proj.get("blockers", "").lower()
                        
                        has_matching_meta = any(qw in purpose or qw in techs or qw in blockers_str for qw in query_words)
                        
                        if "diagnostics" in query_words or "voice" in query_words:
                            if any("voice" in f["path"].lower() or "tts" in f["path"].lower() or "stt" in f["path"].lower() for f in all_files):
                                has_evidence = True
                        
                        if relevant_files or relevant_dbs or has_matching_meta:
                            has_evidence = True
            
            if not has_evidence:
                logger.info("[EVIDENCE CHECK] No evidence found in project for query. Returning fallback response.")
                # We still generate the logs and print final prompt as requested
                system_prompt = self.build_context_prompt(user_text)
                logger.info(
                    f"\n--- FINAL PROMPT SENT TO OLLAMA ---\n"
                    f"Model: {self.model}\n"
                    f"System Prompt:\n{system_prompt}\n"
                    f"User Message:\n{user_text}\n"
                    f"----------------------------------\n"
                )
                yield "I do not have enough project data to determine that."
                return

        system_prompt = self.build_context_prompt(user_text)
        messages = [{"role": "system", "content": system_prompt}] + history[-5:] + [{"role": "user", "content": user_text}]
        options = self._get_dynamic_options(user_text)
        
        # Log final prompt sent to Ollama
        logger.info(
            f"\n--- FINAL PROMPT SENT TO OLLAMA ---\n"
            f"Model: {self.model}\n"
            f"System Prompt:\n{system_prompt}\n"
            f"User Message:\n{user_text}\n"
            f"----------------------------------\n"
        )
        try:
            resp = await asyncio.to_thread(lambda: requests.post(
                self.chat_url, 
                json={
                    "model": self.model, 
                    "messages": messages, 
                    "stream": True,
                    "options": options
                }, 
                stream=True, 
                timeout=(3.0, self.timeout)
            ))
            
            def read_lines():
                return list(resp.iter_lines())
                
            lines = await asyncio.to_thread(read_lines)
            for line in lines:
                if line:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
        except Exception as e:
            logger.error(f"[LLM ERROR] Chat stream failed: {e}", exc_info=True)
            yield "Stream interrupted. Please try again, Sir."

    def generate(self, prompt: str, system_prompt: Optional[str] = None, format: Optional[str] = None, timeout: Optional[float] = None) -> str:
        """
        Synchronously generates a response using Ollama's /api/generate endpoint.
        """
        if not self.model_detected:
            self._detect_model()
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if format:
            payload["format"] = format
            
        url = self.chat_url.replace("/chat", "/generate")
        timeout_val = timeout if timeout is not None else self.timeout
        try:
            resp = requests.post(url, json=payload, timeout=timeout_val)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            logger.error(f"[LLM ERROR] Generate failed: {e}", exc_info=True)
            raise e
