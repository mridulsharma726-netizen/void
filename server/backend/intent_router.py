import asyncio
import logging
import re
from typing import Dict, Tuple, Optional

from backend.schemas import IntentResult

logger = logging.getLogger("void.intent_router")

class IntentRouter:
    """Hybrid intent router: rules first → LLM fallback.
    
    Guards against false positives by checking for conversational context
    before applying command patterns.
    """

    PREFIX = r"^(?:just\s+|please\s+|can\s+you\s+|do\s+one\s+thing\s+(?:and\s+)?|go\s+ahead\s+and\s+|void\s*,\s*|void\s+)?"
    SUFFIX = r"\s*(?:please|sir)?$"

    SYSTEM_PATTERNS = [
        PREFIX + r"clear\s+(?:memory|conversation)" + SUFFIX,
        PREFIX + r"(?:show|get)\s+(?:memory|facts)" + SUFFIX,
        PREFIX + r"(?:repair|fix|debug|diagnostics?)\s+(?:yourself|void|system|self)" + SUFFIX,
        PREFIX + r"(?:remember|store)\s+(.+)" + SUFFIX,
        PREFIX + r"forget\s+(.+)" + SUFFIX,
    ]

    # Tightened command patterns — each requires specific structure
    COMMAND_PATTERNS = {
        "time": [
            PREFIX + r"(?:what(?:'s|\s+is)?\s+(?:the\s+)?)?time(?:\s+is\s+it)?" + SUFFIX,
            PREFIX + r"(?:tell\s+(?:me\s+)?the\s+)?clock" + SUFFIX,
            PREFIX + r"(?:what(?:'s|\s+is)?\s+(?:the\s+)?)?date(?:\s+is\s+it|\s+today)?" + SUFFIX,
            PREFIX + r"(?:show|get|tell\s+(?:me\s+)?the\s+)?date" + SUFFIX
        ],
        "system_info": [
            PREFIX + r"(?:system|cpu|ram|disk|battery|network|wifi)\s+(?:info|status|stats|usage|level)" + SUFFIX,
            PREFIX + r"(?:show|get)\s+(?:system|cpu|ram|disk|battery|network|wifi)\s*(?:info|status|stats|usage|level)?" + SUFFIX,
            PREFIX + r"battery(?:\s+status|\s+level)?" + SUFFIX,
            PREFIX + r"network(?:\s+status)?" + SUFFIX
        ],
        "open_app": [PREFIX + r"(?:open|launch|start)\s+([a-zA-Z0-9]+(?:\s+[a-zA-Z0-9]+)*)" + SUFFIX],
        "close_app": [PREFIX + r"close\s+(?:kill\s+|quit\s+)?([a-zA-Z0-9]+)" + SUFFIX],
        "open_url": [PREFIX + r"(?:open|visit|go\s+to)\s+(https?://\S+|www\.\S+|\S+\.(?:com|org|net|io|dev))" + SUFFIX],
        "search_google": [PREFIX + r"(?:search\s+(?:for|google)\s+|google\s+)(.+)" + SUFFIX],
        "play_youtube": [PREFIX + r"(?:play|watch)\s+(?:youtube|yt)\s+(.+)" + SUFFIX],
        "open_folder": [
            PREFIX + r"open\s+(.+)\s+folder" + SUFFIX,
            PREFIX + r"(?:open\s+)?(?:any\s+)?folder\s+(?:that's\s+|thats\s+)?(?:on\s+|in\s+)?(.+)" + SUFFIX,
            PREFIX + r"open\s+file\s+(.+)" + SUFFIX,
            PREFIX + r"open\s+folder\s+(.+)" + SUFFIX
        ],
        "run_command": [PREFIX + r"(?:run|execute|cmd|shell)\s+(.+)" + SUFFIX],
        "file_manager": [PREFIX + r"(?:create|write|save)\s+file\s+(.+)\s+with\s+(.+)" + SUFFIX, PREFIX + r"(?:read|get)\s+file\s+(.+)" + SUFFIX],
        "repair_self": [PREFIX + r"repair\s+(?:yourself|void|system|self)" + SUFFIX],
        "change_motd": [PREFIX + r"(?:change|set|update|refresh)\s+(?:the\s+)?(?:message\s+of\s+the\s+day|motd)(?:\s+(?:to|on\s+the\s+panel\s+to|on\s+panel\s+to|to\s+be))?\s*(.*)" + SUFFIX],
        "send_whatsapp": [
            # 1. Send to [contact] saying/with/text [message] (Explicit "to" required)
            PREFIX + r"(?:send|write|type)\s+(?:a\s+)?(?:whatsapp(?:\s+message)?|message)(?:\s+on\s+whatsapp)?\s+to\s+([a-zA-Z0-9\s]+)\s+(?:saying|with|text)\s+(.+)" + SUFFIX,
            # 2. Send to [contact] : [message] (Explicit "to" required)
            PREFIX + r"(?:send|write|type)\s+(?:a\s+)?(?:whatsapp(?:\s+message)?|message)(?:\s+on\s+whatsapp)?\s+to\s+([a-zA-Z0-9\s]+)\s*:\s*(.+)" + SUFFIX,
            # 3. Whatsapp/message to [contact] saying/with/text [message]
            PREFIX + r"(?:whatsapp|message)\s+to\s+([a-zA-Z0-9\s]+)\s+(?:saying|with|text)\s+(.+)" + SUFFIX,
            # 4. Send to [contact] (No message specified, e.g. "send a whatsapp message to dad")
            PREFIX + r"(?:send|write|type)\s+(?:a\s+)?(?:whatsapp(?:\s+message)?|message)(?:\s+on\s+whatsapp)?\s+to\s+([a-zA-Z0-9\s]+)" + SUFFIX,
            # 5. Send [contact] [message] (No "to", e.g. "send dad hello")
            PREFIX + r"(?:send|write|type)\s+(?:a\s+)?(?:whatsapp(?:\s+message)?|message)(?:\s+on\s+whatsapp)?\s+([a-zA-Z0-9]+)\s+(.+)" + SUFFIX,
            # 6. Whatsapp [contact] [message]
            PREFIX + r"whatsapp\s+([a-zA-Z0-9]+)\s+(.+)" + SUFFIX,
            # 7. Generic send whatsapp command (No contact, no message)
            PREFIX + r"(?:send|write|type)\s+(?:a\s+)?(?:whatsapp(?:\s+message)?|message)(?:\s+on\s+whatsapp)?" + SUFFIX,
            PREFIX + r"whatsapp\s+(?:message)?" + SUFFIX,
            # 8. Multi-step conversational send (e.g. "write a leave application and send it to mridul on whatsapp")
            PREFIX + r".*?(?:send|whatsapp|message)\s+(?:it\s+)?to\s+([a-zA-Z0-9\s]+)\s+(?:on|via|through)\s+whatsapp" + SUFFIX,
        ],
        "read_whatsapp": [
            PREFIX + r"(?:read|check|show|get)\s+(?:my\s+)?(?:unread\s+)?(?:messages|chats|whatsapp)(?:\s+(?:on|in|from)\s+whatsapp)?" + SUFFIX,
            PREFIX + r"(?:read|check|show|get)\s+(?:my\s+)?(?:whatsapp)\s+(?:unread\s+)?(?:messages|chats)" + SUFFIX,
            PREFIX + r"(?:open\s+)?whatsapp\s+(?:and\s+)?(?:read|check|show|get)\s+(?:my\s+)?(?:unread\s+)?(?:messages|chats)" + SUFFIX
        ],
        "find_file": [
            PREFIX + r"(?:find|search\s+for)\s+(?:my\s+)?([a-zA-Z0-9\s_\-\.]+)(?:\s+file|\s+folder|\s+project)?" + SUFFIX
        ],
        "move_file_bulk": [
            PREFIX + r"move\s+(?:all\s+)?([a-zA-Z0-9\s_\-\.]+)?\s*(?:from\s+)?([a-zA-Z0-9\s_\-\.]+)\s+(?:to\s+)?([a-zA-Z0-9\s_\-\.]+)" + SUFFIX
        ],
        "clean_duplicates": [
            PREFIX + r"(?:delete|remove|clean)\s+duplicates?\s*(?:in\s+)?([a-zA-Z0-9\s_\-\.]+)?(?:\s+(?:pdf|pdfs|files))?" + SUFFIX
        ],
        "create_folder": [
            PREFIX + r"(?:create|make)\s+(?:a\s+)?(?:folder|directory)(?:\s+for|\s+named|\s+called)?\s+(.+)" + SUFFIX
        ],
        "arrange_windows": [
            PREFIX + r"(?:arrange|split|tile|cascade|maximize|minimize)\s+(?:all\s+)?(?:windows|screen|apps)(?:\s+side-by-side)?" + SUFFIX
        ],
        "launch_workspace": [
            PREFIX + r"(?:launch|open|start)\s+([a-zA-Z0-9]+)\s+workspace" + SUFFIX
        ],
        "research_competitors": [
            PREFIX + r"(?:research|investigate)(?:\s+competitors\s+of)?\s+(.+)" + SUFFIX
        ],
        "open_tabs": [
            PREFIX + r"open\s+(\d+)\s+tabs\s+(?:about|on|for)\s+(.+)" + SUFFIX
        ],
        "download_file": [
            PREFIX + r"download\s+(https?://\S+|\S+\.pdf)" + SUFFIX
        ],
        "create_presentation": [
            PREFIX + r"(?:create|make)\s+(?:a\s+)?(?:presentation|deck|slides?)(?:\s+(?:about|for|on))?\s+(.+)" + SUFFIX
        ],
        "manage_email": [
            PREFIX + r"(?:summarize|check|read)\s+(?:today's\s+|my\s+)*(?:inbox|email|emails?)" + SUFFIX,
            PREFIX + r"(?:reply|draft)\s+(?:to\s+)?(?:email\s+|mail\s+)?(\S+)(?:\s+(?:saying|with|instructing|say)\s+(.+))?" + SUFFIX,
            PREFIX + r"reply\s+to\s+(?:all\s+)?important\s+emails?" + SUFFIX
        ],
        "manage_calendar": [
            PREFIX + r"(?:plan|view|show)\s+(?:my\s+)?(?:week|calendar)" + SUFFIX,
            PREFIX + r"(?:block|schedule|add)\s+(?:coding\s+time|event|meeting)(?:\s+every\s+([a-zA-Z0-9\s]+))?(?:\s+(?:at|from)\s+([a-zA-Z0-9\s:]+))?" + SUFFIX,
            PREFIX + r"(?:schedule|block)\s+(.+)" + SUFFIX
        ],
        "skipit_assistant": [
            PREFIX + r"(?:how\s+many\s+)?bookings\s+(?:created\s+)?today" + SUFFIX,
            PREFIX + r"(?:which\s+)?listings\s+(?:are\s+)?inactive" + SUFFIX,
            PREFIX + r"(?:generate\s+)?(?:weekly\s+)?investor\s+report" + SUFFIX,
            PREFIX + r"find\s+users\s+(?:who\s+)?(?:have\s+not|haven't)\s+rented\s+(?:in\s+)?(\d+)\s+days" + SUFFIX
        ],
        "smart_cart_assistant": [
            PREFIX + r"(?:show\s+)?pilot\s+store\s+performance" + SUFFIX,
            PREFIX + r"(?:generate\s+)?revenue\s+projections?" + SUFFIX,
            PREFIX + r"(?:create|make)\s+(?:a\s+)?(?:store\s+)?pitch\s+deck" + SUFFIX
        ],
        "business_intelligence": [
            PREFIX + r"(?:analyze\s+)?startup\s+performance" + SUFFIX,
            PREFIX + r"(?:give\s+me\s+)?(?:startup\s+)?recommendations" + SUFFIX,
            PREFIX + r"(?:view\s+)?business\s+intelligence" + SUFFIX
        ],
        "agent_network": [
            PREFIX + r"(?:spawn|start|run|initialize|launch)\s+(?:the\s+)?agent\s+network" + SUFFIX,
            PREFIX + r"(?:ask|tell)\s+(research|coding|testing|security|planner)\s+agent\s+(?:to\s+)?(.+)" + SUFFIX,
            PREFIX + r"show\s+(?:the\s+)?agent\s+network\s*(?:status|list)?" + SUFFIX,
            PREFIX + r"list\s+(?:active\s+)?agents" + SUFFIX
        ],
        "cvcs_click": [
            PREFIX + r"(?:click|press|tap)(?:\s+(?:on|the|button))?\s+(.+)" + SUFFIX
        ],
        "cvcs_type": [
            PREFIX + r"(?:type|write|input)\s+(.+)" + SUFFIX
        ],
        "cvcs_read_screen": [
            PREFIX + r"(?:what\s+is\s+on\s+(?:my\s+)?screen|read\s+(?:my\s+)?screen|scan\s+(?:my\s+)?screen|analyze\s+(?:my\s+)?screen)" + SUFFIX,
            PREFIX + r"what\s+(?:can\s+you\s+)?see\s+(?:on\s+(?:my\s+)?)?screen" + SUFFIX
        ],
        "cvcs_set_permission": [
            PREFIX + r"(?:set|change|update)\s+(?:permission\s+level|permissions?|control\s+mode)\s+(?:to\s+)?(\d+\.?\d*)" + SUFFIX
        ],
        "agent_scan": [
            PREFIX + r"scan\s+(?:this\s+)?(?:project|codebase|folder)" + SUFFIX,
            PREFIX + r"project\s+scan" + SUFFIX
        ],
        "agent_explain": [
            PREFIX + r"explain\s+(?:the\s+)?(?:codebase\s+)?architecture" + SUFFIX,
            PREFIX + r"explain\s+(?:the\s+)?codebase" + SUFFIX
        ],
        "agent_code": [
            PREFIX + r"(?:add|create|modify|fix|write)\s+(?:code|feature|forgot\s+password|stub|forgot\s+password\s+stub|to|file|bug)\s+(.+)" + SUFFIX
        ],
        "agent_run_tests": [
            PREFIX + r"(?:run|execute)\s+tests?" + SUFFIX,
            PREFIX + r"run\s+test\s+suite" + SUFFIX
        ],
        "agent_fix_errors": [
            PREFIX + r"fix\s+(?:the\s+)?(?:build\s+)?errors?" + SUFFIX,
            PREFIX + r"fix\s+errors?\s+with\s+logs?\s+(.+)" + SUFFIX
        ],
        "agent_refactor": [
            PREFIX + r"(?:refactor|optimize|clean\s+up)\s+(?:code\s+in\s+)?(?:file\s+)?([^\s]+)" + SUFFIX
        ],
        "start_meeting": [
            PREFIX + r"(?:start|begin)\s+(?:a\s+)?meeting" + SUFFIX,
            PREFIX + r"meeting\s+start" + SUFFIX
        ],
        "stop_meeting": [
            PREFIX + r"(?:stop|end|finish)\s+(?:the\s+)?meeting" + SUFFIX,
            PREFIX + r"meeting\s+(?:is\s+)?(?:over|ended|done)" + SUFFIX
        ],
        "recall_meeting": [
            PREFIX + r"(?:what\s+happened\s+in|summarize|show)\s+(?:the\s+)?(?:meeting|yesterday's\s+meeting|today's\s+meeting)\s*(.*)" + SUFFIX,
            PREFIX + r"(?:find|search)\s+meetings?\s+(?:about|on|regarding)\s+(.+)" + SUFFIX
        ],
        "get_action_items": [
            PREFIX + r"(?:show|get|what\s+are)\s+(?:my\s+)?(?:pending\s+tasks|action\s+items)" + SUFFIX,
            PREFIX + r"which\s+(?:tasks|action\s+items)\s+are\s+(?:overdue|pending)" + SUFFIX
        ],
        "register_project": [
            PREFIX + r"(?:track|register|monitor|analyze)\s+(?:this\s+)?(?:project|folder|codebase)(?:\s+(.+))?" + SUFFIX,
            PREFIX + r"start\s+tracking\s+(?:project\s+)?(.+)?" + SUFFIX,
            PREFIX + r"analyze\s+(?:project\s+)?(.+)" + SUFFIX
        ],
        "scan_project_changes": [
            PREFIX + r"(?:scan|check|detect)\s+(?:project\s+)?changes?(?:\s+(?:in|for)\s+(.+))?" + SUFFIX,
            PREFIX + r"what\s+(?:has\s+)?changed\s+(?:in\s+(?:the\s+)?project|since\s+last\s+(?:scan|time))" + SUFFIX
        ],
        "get_project_status": [
            PREFIX + r"(?:what\s+is\s+)?(?:the\s+)?status\s+(?:of\s+)?(.+)" + SUFFIX,
            PREFIX + r"(?:show|get)\s+(?:the\s+)?project\s+(?:status|info|profile)(?:\s+(?:of|for)\s+(.+))?" + SUFFIX
        ],
        "query_recent_work": [
            PREFIX + r"what\s+did\s+(?:i|we)\s+work\s+on\s+(.+)" + SUFFIX,
            PREFIX + r"(?:show|get)\s+(?:my\s+)?recent\s+(?:work|changes|activity)(?:\s+(.+))?" + SUFFIX
        ],
        "continue_where_left_off": [
            PREFIX + r"(?:continue\s+where\s+(?:i|we)\s+left\s+off|what\s+was\s+i\s+working\s+on\s+yesterday|what\s+was\s+i\s+working\s+on|show\s+today's\s+progress)" + SUFFIX
        ],
        "screenshot": [
            PREFIX + r"(?:take\s+)?screenshot" + SUFFIX
        ],
        "lock_computer": [
            PREFIX + r"(?:lock\s+)(?:the\s+)?(?:computer|pc|system|workstation)" + SUFFIX
        ],
        "press_key": [
            PREFIX + r"(?:press|send\s+key)\s+(.+)" + SUFFIX,
            PREFIX + r"hotkey\s+(.+)" + SUFFIX
        ],
        "mouse_control": [
            PREFIX + r"move\s+mouse\s+to\s+(\d+)\s*,\s*(\d+)" + SUFFIX,
            PREFIX + r"scroll\s+(up|down)" + SUFFIX,
            PREFIX + r"double\s+click" + SUFFIX,
            PREFIX + r"right\s+click" + SUFFIX,
            PREFIX + r"click" + SUFFIX
        ],
        "check_file_exists": [
            PREFIX + r"check\s+file\s+exists?\s+(.+)" + SUFFIX
        ],
        "list_directory": [
            PREFIX + r"(?:list|show)\s+(?:directory|folder|dir)\s*(.+)??" + SUFFIX
        ],
    }
    
    # Words that indicate conversational/abstract usage of action verbs
    CONVERSATIONAL_TARGETS = {
        "your", "my", "his", "her", "their", "our", "its",
        "a", "an", "the", "this", "that", "these", "those",
        "mind", "heart", "eyes", "mouth", "door", "way", "conversation",
        "discussion", "topic", "idea", "ideas", "thinking", "thought",
        "possibility", "possibilities", "up", "about", "with", "into",
        "new", "more", "some", "any", "what", "why", "how",
    }
    
    # Known app names that are valid targets for open/launch/start
    KNOWN_APPS = {
        "chrome", "firefox", "edge", "safari", "brave", "opera",
        "notepad", "calculator", "calc", "terminal", "cmd", "powershell",
        "vscode", "code", "explorer", "spotify", "discord", "steam",
        "teams", "zoom", "word", "excel", "powerpoint", "paint",
        "settings", "vlc", "obs", "blender", "photoshop", "gimp",
        "slack", "telegram", "whatsapp", "notion", "obsidian",
    }
    
    def __init__(self, use_llm_fallback: bool = False):
        self.use_llm_fallback = use_llm_fallback
    
    async def classify(self, text: str) -> IntentResult:
        raw = text.strip()
        lower = raw.lower()
        if not lower:
            return IntentResult(intent="chat")
            
        # Check deep research triggers immediately to bypass all normal pipelines
        from backend.deep_research import ResearchIntentDetector
        if ResearchIntentDetector.is_deep_research(raw):
            topic = ResearchIntentDetector.extract_topic(raw)
            logger.info(f"[DEEP RESEARCH INTENT DETECTED] Topic: {topic}")
            return IntentResult(intent="deep_research", params={"topic": topic})
        
        # Check academic triggers immediately
        academic_keywords = [
            "viva", "test me", "test my", "quiz me", "teach me", "explain", "lesson",
            "practice question", "lab assistant", "lab experiment", "study roadmap",
            "dsa lesson", "dbms lab", "os lab", "explain polymorphism", "explain encapsulation"
        ]
        if any(kw in lower for kw in academic_keywords):
            logger.info(f"[ACADEMIC INTENT DETECTED] Query: {raw}")
            return IntentResult(intent="academic")
        
        # Rules first
        result = self._classify_rules(lower, raw)
        if result.intent != "unknown":
            logger.debug(f"Rule: {result.intent}")
            return result
        
        # LLM fallback
        if self.use_llm_fallback:
            llm_intent = await self._classify_llm(raw)
            if llm_intent.intent != "chat":
                logger.info(f"LLM fallback: {llm_intent.intent}")
                return llm_intent
        
        return IntentResult(intent="chat")
    
    def _is_conversational(self, text: str) -> bool:
        """Check if text looks like natural conversation rather than a command."""
        # Questions are almost never commands
        if "?" in text:
            return True
        
        # Sentences with personal pronouns + abstract context
        conversational_phrases = [
            r"\bi\s+(?:think|feel|believe|want|need|like|love|hate|wish|hope|know|am|was|have|had)\b",
            r"\b(?:can|could|would|should)\s+you\s+(?:tell|explain|describe|help)\b",
            r"\b(?:what|why|how|where|when|who)\s+(?:is|are|was|were|do|does|did|can|could|would|should)\b",
            r"\b(?:tell|explain|describe)\s+(?:me|us)\s+(?:about|how|why|what)\b",
            r"\bdo\s+you\s+(?:know|think|believe|remember)\b",
            r"\b(?:is|are)\s+(?:it|there|this|that)\b",
            r"\b(?:which|how\s+much|how\s+close|what\s+is\s+the\s+biggest|what\s+is\s+left)\b",
            r"\b(?:blocker|blockers|auth|authentication|database|payment|payments|sqlite|launch|completion|completed)\b",
            r"\b(?:write|create|draft|generate|make|plan|summarize|explain)\s+(?:[\w\s]{0,20})\s*(?:email|proposal|story|poem|essay|letter|report|article|post|blog|summary|meeting|plan|code|function|program|script|class|test|ui|app|dashboard|website|readme|codebase|architecture|project)\b"
        ]
        for pattern in conversational_phrases:
            if re.search(pattern, text, re.I):
                return True
        
        return False
    
    def _classify_rules(self, lower: str, raw: str) -> IntentResult:
        # Greetings/Chat shortcut — deterministic bypass
        greetings = ["hi", "hello", "hey", "yo", "greetings", "good morning", "good afternoon", "good evening", "how are you"]
        if lower in greetings or any(lower.startswith(g + " ") for g in greetings):
            return IntentResult(intent="chat")

        # System commands (these are specific enough to not need guards)
        for pattern in self.SYSTEM_PATTERNS:
            match = re.search(pattern, lower)
            if match:
                action = self._map_system(lower)
                return IntentResult(intent="system", action=action, params=self._system_params(match))
        
        # Safe, unambiguous commands — check before conversational guard
        for action in [
            "time", "system_info", "repair_self", "change_motd", "send_whatsapp", "read_whatsapp",
            "find_file", "move_file_bulk", "clean_duplicates", "create_folder", "open_folder", "arrange_windows",
            "launch_workspace", "research_competitors", "open_tabs", "download_file",
            "create_presentation", "manage_email", "manage_calendar",
            "skipit_assistant", "smart_cart_assistant", "business_intelligence", "agent_network",
            "cvcs_read_screen", "cvcs_set_permission",
            "agent_scan", "agent_explain", "agent_code", "agent_run_tests", "agent_fix_errors", "agent_refactor",
            "start_meeting", "stop_meeting", "recall_meeting", "get_action_items",
            "register_project", "scan_project_changes", "get_project_status", "query_recent_work", "continue_where_left_off",
            "screenshot", "lock_computer", "press_key", "mouse_control", "check_file_exists", "list_directory"
        ]:
            if action in self.COMMAND_PATTERNS:
                for pat in self.COMMAND_PATTERNS[action]:
                    match = re.search(pat, lower)
                    if match:
                        params = self._command_params(action, match, raw)
                        return IntentResult(intent="command", action=action, params=params)
        
        # Conversational guard — if text looks like natural speech, skip remaining commands
        if self._is_conversational(lower):
            return IntentResult(intent="unknown")  # Falls through to chat
        
        # Other commands — with extra validation
        for action, patterns in self.COMMAND_PATTERNS.items():
            if action in [
                "time", "system_info", "repair_self", "send_whatsapp", "read_whatsapp",
                "find_file", "move_file_bulk", "clean_duplicates", "create_folder", "open_folder", "arrange_windows",
                "launch_workspace", "research_competitors", "open_tabs", "download_file",
                "create_presentation", "manage_email", "manage_calendar",
                "skipit_assistant", "smart_cart_assistant", "business_intelligence", "agent_network",
                "cvcs_read_screen", "cvcs_set_permission",
                "agent_scan", "agent_explain", "agent_code", "agent_run_tests", "agent_fix_errors", "agent_refactor",
                "start_meeting", "stop_meeting", "recall_meeting", "get_action_items",
                "register_project", "scan_project_changes", "get_project_status", "query_recent_work",
                "screenshot", "lock_computer", "press_key", "mouse_control", "check_file_exists", "list_directory"
            ]:
                continue
            for pat in patterns:
                match = re.search(pat, lower)
                if match:
                    # Extra validation for ambiguous commands
                    if action == "open_app":
                        target = self._extract_target(match)
                        if target and (any(w in self.CONVERSATIONAL_TARGETS for w in target.lower().split()) or target.lower() in self.CONVERSATIONAL_TARGETS):
                            continue  # "open your mind" → not a command
                        if target and target.lower() not in self.KNOWN_APPS:
                            # Unknown app: only treat as command if the sentence is short/imperative
                            words = lower.split()
                            if len(words) > 5:
                                continue  # Long sentence with "open" is probably conversational
                    
                    if action == "run_command":
                        # run_command is dangerous — only allow if very explicitly a command
                        target = self._extract_target(match)
                        if not target or len(target.split()) > 8:
                            continue  # Too long/vague to be a real command
                    
                    params = self._command_params(action, match, raw)
                    return IntentResult(intent="command", action=action, params=params)
        
        return IntentResult(intent="unknown")
    
    def _extract_target(self, match) -> str:
        """Extract the first captured group from a regex match."""
        groups = match.groups()
        for g in groups:
            if g and g.strip():
                return g.strip()
        return ""
    
    def _map_system(self, lower: str) -> str:
        if "clear" in lower: return "clear_memory"
        if "show" in lower: return "show_memory"
        if "repair" in lower or "fix" in lower: return "repair"
        if "diagnostics" in lower or "debug" in lower: return "diagnostics"
        return "system"
    
    def _system_params(self, match) -> Dict[str, str]:
        groups = match.groups()
        return {"fact": groups[0].strip()} if groups and groups[0] else {}
    
    def _command_params(self, action: str, match, raw: str) -> Dict:
        groups = match.groups()
        target = groups[0].strip() if groups and groups[0] else raw
        
        if action == "open_app":
            if any(x in target for x in ['http', '.com']): 
                return {"url": "https://" + target}
            return {"app": target}
        elif action == "close_app":
            return {"app": target}
        elif action in ["search_google", "play_youtube"]:
            return {"query": target}
        elif action == "run_command":
            return {"command": target}
        elif action == "change_motd":
            return {"motd": target}
        elif action == "send_whatsapp":
            contact_val = groups[0].strip() if groups and groups[0] else ""
            message_val = groups[1].strip() if len(groups) > 1 and groups[1] else ""
            # If no message is captured but the prompt mentions "leave" or "not well", draft a professional request
            if not message_val and ("leave" in raw.lower() or "not well" in raw.lower()):
                message_val = "Respected Sir, I am requesting leave from work due to not feeling well. Requesting your kind approval. Thanks, Mridul."
            return {"contact": contact_val, "message": message_val}
        elif action == "read_whatsapp":
            return {}
        elif action == "find_file":
            return {"query": target}
        elif action == "move_file_bulk":
            ext_val = groups[0].strip() if groups and groups[0] else ""
            src_val = groups[1].strip() if len(groups) > 1 and groups[1] else ""
            tgt_val = groups[2].strip() if len(groups) > 2 and groups[2] else ""
            return {"extension": ext_val, "source": src_val, "target": tgt_val}
        elif action == "clean_duplicates":
            folder_val = groups[0].strip() if groups and groups[0] else ""
            return {"folder": folder_val}
        elif action == "create_folder":
            return {"folder_path": target}
        elif action == "open_folder":
            return {"path": target}
        elif action == "arrange_windows":
            mode = "tile"
            if "split" in raw.lower() or "side-by-side" in raw.lower():
                mode = "split"
            elif "maximize" in raw.lower():
                mode = "maximize-all"
            elif "minimize" in raw.lower():
                mode = "minimize-all"
            return {"layout": mode}
        elif action == "launch_workspace":
            return {"workspace_name": target}
        elif action == "research_competitors":
            return {"query": target}
        elif action == "open_tabs":
            count_val = int(groups[0].strip()) if groups and groups[0] else 5
            topic_val = groups[1].strip() if len(groups) > 1 and groups[1] else ""
            return {"count": count_val, "topic": topic_val}
        elif action == "download_file":
            return {"url": target}
        elif action == "file_manager":
            if "with" in raw.lower():
                path_val = groups[0].strip() if groups and groups[0] else ""
                content_val = groups[1].strip() if len(groups) > 1 and groups[1] else ""
                return {"path": path_val, "content": content_val}
            return {"path": target}
        elif action == "create_presentation":
            return {"topic": target}
        elif action == "manage_email":
            if "summarize" in raw.lower() or "check" in raw.lower() or "read" in raw.lower() or "all important" in raw.lower():
                return {"sub_action": "summarize"}
            else:
                email_id = groups[0].strip() if groups and groups[0] else ""
                instructions = groups[1].strip() if len(groups) > 1 and groups[1] else "Standard professional reply"
                return {"sub_action": "draft", "email_id": email_id, "instructions": instructions}
        elif action == "manage_calendar":
            if "plan" in raw.lower() or "view" in raw.lower() or "show" in raw.lower():
                return {"sub_action": "plan_week"}
            else:
                return {"sub_action": "schedule_event", "raw_text": raw}
        elif action == "skipit_assistant":
            if "booking" in raw.lower():
                return {"sub_action": "bookings_today"}
            elif "listing" in raw.lower() or "inactive" in raw.lower() and "user" not in raw.lower():
                return {"sub_action": "inactive_listings"}
            elif "user" in raw.lower():
                days_val = int(groups[0].strip()) if groups and groups[0] else 60
                return {"sub_action": "inactive_users", "days": days_val}
            else:
                return {"sub_action": "weekly_report"}
        elif action == "smart_cart_assistant":
            if "pilot" in raw.lower() or "performance" in raw.lower():
                return {"sub_action": "pilot_performance"}
            elif "projection" in raw.lower() or "revenue" in raw.lower():
                return {"sub_action": "revenue_projections"}
            else:
                return {"sub_action": "store_pitch_deck"}
        elif action == "business_intelligence":
            return {}
        elif action == "agent_network":
            if "spawn" in raw.lower() or "start" in raw.lower() or "run" in raw.lower() or "initialize" in raw.lower() or "launch" in raw.lower():
                return {"sub_action": "spawn_network"}
            elif "ask" in raw.lower() or "tell" in raw.lower():
                agent_val = groups[0].strip() if groups and groups[0] else ""
                inst_val = groups[1].strip() if len(groups) > 1 and groups[1] else ""
                return {"sub_action": "ask_agent", "agent_type": agent_val, "agent_instruction": inst_val}
            elif "list" in raw.lower():
                return {"sub_action": "list_agents"}
            else:
                return {"sub_action": "status"}
        elif action == "cvcs_click":
            return {"query": target}
        elif action == "cvcs_type":
            return {"text": target}
        elif action == "cvcs_read_screen":
            return {}
        elif action == "cvcs_set_permission":
            # Extract numbers if present, else fallback to 2.0
            clean_tgt = "".join([c for c in target if c.isdigit() or c == '.'])
            return {"level": float(clean_tgt) if clean_tgt else 2.0}
        elif action == "agent_code":
            return {"instructions": target}
        elif action == "agent_fix_errors":
            return {"logs": target}
        elif action == "agent_refactor":
            return {"file_path": target}
        elif action in ["agent_scan", "agent_explain", "agent_run_tests", "start_meeting", "stop_meeting", "get_action_items", "screenshot", "lock_computer"]:
            return {}
        elif action == "press_key":
            return {"key": target}
        elif action == "mouse_control":
            raw_lower = raw.lower()
            if "move" in raw_lower:
                return {"action": "move", "x": int(groups[0]) if len(groups) > 0 else 0, "y": int(groups[1]) if len(groups) > 1 else 0}
            elif "scroll" in raw_lower:
                direction = groups[0].strip() if groups else "up"
                amt = 200 if direction == "up" else -200
                return {"action": "scroll", "amount": amt}
            elif "double" in raw_lower:
                return {"action": "double_click"}
            elif "right" in raw_lower:
                return {"action": "right_click"}
            else:
                return {"action": "click"}
        elif action == "check_file_exists":
            return {"path": target}
        elif action == "list_directory":
            return {"path": groups[0].strip() if groups and groups[0] else ""}
        elif action == "recall_meeting":
            return {"query": target}
        elif action == "register_project":
            return {"path": target if target else ""}
        elif action == "scan_project_changes":
            return {"project_id": target if target else ""}
        elif action == "get_project_status":
            return {"project_name": target if target else ""}
        elif action == "query_recent_work":
            return {"timeframe": target if target else "today"}
        elif action == "continue_where_left_off":
            return {"project_id": target if target else ""}
        return {"raw": raw}
    
    @staticmethod
    async def _classify_llm(text: str) -> IntentResult:
        """Static LLM fallback (lazy, no deps)."""
        try:
            from backend.llm_client import OllamaClient
            llm = OllamaClient()
            llm.timeout = 3.0
            prompt = f'Classify "{text}" → intent: time/system_info/open_app/open_url/search_google/system/chat. JSON: {{"intent":"name"}}'
            resp = await llm.chat([], prompt)
            m = re.search(r'"intent"\s*:\s*"([^"]+)"', resp, re.I)
            return IntentResult(intent=m.group(1)) if m else IntentResult(intent="chat")
        except:
            return IntentResult(intent="chat")
