import re
from typing import List, Dict, Any

# Regex patterns for various tracebacks
PYTHON_PATTERN = re.compile(
    r'File "([^"]+)", line (\d+)(?:, in (.+))?\n\s*(.+)',
    re.MULTILINE
)
JS_PATTERN = re.compile(
    r'at\s+(?:[^\s(]+)?\s*\(?([^:\n\s]+):(\d+):(\d+)\)?',
    re.MULTILINE
)
DART_PATTERN = re.compile(
    r'([^:\n\s]+\.dart):(\d+):(\d+):\s*Error:\s*(.+)',
    re.MULTILINE
)
GENERIC_PATTERN = re.compile(
    r'([^:\n\s]+):(\d+):(?:\d+:)?\s*error:\s*(.+)',
    re.IGNORECASE | re.MULTILINE
)

class AgentErrorAnalyzer:
    def __init__(self):
        pass

    def parse_build_logs(self, logs: str) -> List[Dict[str, Any]]:
        """
        Scan build logs or tracebacks and identify offending file names,
        line numbers, and error messages.
        """
        errors = []
        
        # 1. Check Python
        for match in PYTHON_PATTERN.finditer(logs):
            errors.append({
                "language": "Python",
                "file": match.group(1).replace("\\", "/"),
                "line": int(match.group(2)),
                "function": match.group(3) or "unknown",
                "message": match.group(4).strip()
            })

        # 2. Check JavaScript/Node
        for match in JS_PATTERN.finditer(logs):
            # Exclude node internal modules (e.g., node:internal/modules/cjs/loader)
            file_path = match.group(1)
            if "node:internal" not in file_path and not file_path.startswith("internal/"):
                errors.append({
                    "language": "JavaScript/TypeScript",
                    "file": file_path.replace("\\", "/"),
                    "line": int(match.group(2)),
                    "column": int(match.group(3)),
                    "message": "Runtime error or stack trace entry"
                })

        # 3. Check Dart/Flutter
        for match in DART_PATTERN.finditer(logs):
            errors.append({
                "language": "Dart/Flutter",
                "file": match.group(1).replace("\\", "/"),
                "line": int(match.group(2)),
                "column": int(match.group(3)),
                "message": match.group(4).strip()
            })

        # 4. Check Generic C/C++/Go/Rust style (file:line:error)
        for match in GENERIC_PATTERN.finditer(logs):
            # Ensure file is not just a drive letter on Windows (like C:)
            if len(match.group(1)) > 1:
                errors.append({
                    "language": "C/C++/Go/Rust",
                    "file": match.group(1).replace("\\", "/"),
                    "line": int(match.group(2)),
                    "message": match.group(3).strip()
                })

        # Deduplicate errors based on file, line, and message
        unique_errors = []
        seen = set()
        for err in errors:
            key = (err["file"], err["line"], err.get("message", ""))
            if key not in seen:
                seen.add(key)
                unique_errors.append(err)

        return unique_errors

    async def analyze_and_suggest_fix(self, logs: str, llm_client: Any) -> Dict[str, Any]:
        """
        Interprets error logs using the LLM client and returns explanation & proposed fix.
        """
        parsed_errors = self.parse_build_logs(logs)
        
        # Prepare content for LLM
        errors_summary = ""
        if parsed_errors:
            errors_summary = "Parsed Errors:\n"
            for i, err in enumerate(parsed_errors, 1):
                errors_summary += f"{i}. File: {err['file']}, Line: {err['line']}, Msg: {err.get('message', '')}\n"
        
        prompt = (
            f"The application encountered build/execution errors. Please analyze the following log:\n\n"
            f"[LOGS]\n{logs}\n[END LOGS]\n\n"
            f"{errors_summary}\n"
            f"Address the user (Sir/Master Mridul) in your premium cybernetic AI assistant persona. "
            f"Explain the root cause of the error in simple terms and provide a step-by-step resolution path. "
            f"Suggest the exact code fix required for the main offending file. "
            f"Structure your response under distinct sections: **Root Cause**, **Suggested Fix**, and **Code Snippet**."
        )

        try:
            explanation = await llm_client.chat([], prompt)
        except Exception as e:
            explanation = f"I failed to analyze the build errors due to an LLM client issue, Sir. Raw: {e}"

        return {
            "parsed_errors": parsed_errors,
            "explanation": explanation
        }
