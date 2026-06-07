import logging
import re
from typing import Any, Dict, List
from pydantic import BaseModel, Field

logger = logging.getLogger("void.validator")

class ResponseValidator:
    """Enhanced validation with Pydantic + rules."""
    
    MAX_REPLY_LEN = 2000
    FALLBACKS = {
        "empty": "Apologies Sir, I was unable to generate a response.",
        "error": "Security protocols engaged. Safe mode active.",
        "tool_fail": "I am experiencing some issues with my sub-routines, Sir.",
        "llm_timeout": "My processing units are slightly delayed, Sir.",
    }
    
    def validate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive response validation."""
        reply = str(payload.get("reply", "")).strip()
        meta = payload.get("meta", {})
        
        issues = []
        
        # 1. Basic checks
        if not reply:
            issues.append("empty_reply")
        if len(reply) > self.MAX_REPLY_LEN:
            reply = reply[:self.MAX_REPLY_LEN] + "... (truncated)"
            issues.append("too_long")
        
        # 2. Tool status check
        tool_calls = meta.get("tool_calls", [])
        tool_failures = 0
        statuses = []
        for call in tool_calls:
            status = call.get("meta", {}).get("status", "unknown")
            statuses.append(status)
            if status in ["FAIL", "TIMEOUT", "ERROR"]:
                tool_failures += 1
        
        if tool_failures > 0:
            issues.append(f"tools_failed:{tool_failures}")
        
        # 3. Error content scan - only flag actual error markers or failure prefixes
        error_prefixes = ["error:", "failed:", "fail:", "exception occurred:", "critical failure:"]
        has_errors = any(reply.lower().startswith(prefix) for prefix in error_prefixes)
        
        # Or if it matches system-level errors like connection refused/ollama missing
        system_patterns = [r"^ollama.*not.*found", r"^connection.*refused", r"^failed to connect"]
        if not has_errors:
            has_errors = any(re.search(p, reply, re.I) for p in system_patterns)
            
        if has_errors:
            issues.append("contains_error")
        
        # 4. Final validation
        validated = len(issues) == 0
        final_meta = {
            **meta,
            "validated": validated,
            "validation_issues": issues,
            "tool_statuses": statuses,
        }
        
        if not validated:
            logger.warning(f"Validation failed: {issues}. Using fallback.")
            reply = self._get_fallback(issues)
        
        logger.debug(f"Validation: {'PASS' if validated else 'FAIL'} ({len(issues)} issues)")
        return {"reply": reply, "meta": final_meta}
    
    def _get_fallback(self, issues: List[str]) -> str:
        """Intelligent fallback based on issues."""
        if "empty_reply" in issues:
            return self.FALLBACKS["empty"]
        if "tools_failed" in str(issues):
            return self.FALLBACKS["tool_fail"]
        return self.FALLBACKS["error"]
