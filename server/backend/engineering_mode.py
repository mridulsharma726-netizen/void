"""
VOID Engineering Intelligence Mode
====================================

Activated when the user requests software engineering tasks:
  - "Build a website"
  - "Create a REST API"
  - "Debug this FastAPI code"
  - "Review my architecture"
  - "Generate a backend for my app"

Capabilities:
  - Project structure analysis
  - Dependency graph mapping
  - Tech stack detection
  - Architecture suggestion (via Ollama)
  - Step-by-step code generation planning
  - Integration with existing tools/project_intelligence.py

Usage:
    from server.backend.engineering_mode import EngineeringMode, get_engineering_mode

    eng = get_engineering_mode()
    plan = eng.plan_code_generation("Build a REST API for a todo app", project_path=".")
    print(plan.steps)
"""

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("void.engineering_mode")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class FileNode:
    """Represents a file or directory in the project graph."""
    name: str
    path: str
    file_type: str          # 'file' | 'directory'
    language: Optional[str] = None
    size_bytes: int = 0
    imports: List[str] = field(default_factory=list)


@dataclass
class EngineeringPlan:
    """A structured plan returned by the engineering mode."""
    task: str
    tech_stack: List[str]
    steps: List[str]
    files_to_create: List[Dict[str, str]]   # [{path, description}]
    files_to_modify: List[Dict[str, str]]   # [{path, change_summary}]
    estimated_complexity: str               # 'low' | 'medium' | 'high'
    architecture_notes: str
    dependencies_needed: List[str]
    raw_llm_output: str = ""


@dataclass
class ProjectAnalysis:
    """Analysis result for an existing project directory."""
    root_path: str
    file_count: int
    directory_count: int
    tech_stack: List[str]
    main_languages: List[str]
    entry_points: List[str]
    dependencies: Dict[str, List[str]]      # language → [deps]
    key_files: List[str]
    architecture_summary: str


# ---------------------------------------------------------------------------
# Language / tech detection helpers
# ---------------------------------------------------------------------------
_LANG_MAP: Dict[str, str] = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "React", ".tsx": "React/TypeScript", ".html": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".java": "Java", ".cs": "C#",
    ".go": "Go", ".rs": "Rust", ".cpp": "C++", ".c": "C",
    ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".kt": "Kotlin",
    ".dart": "Dart", ".vue": "Vue",
}

_FRAMEWORK_SIGNALS: List[tuple] = [
    ("package.json",    "Node.js"),
    ("next.config.js",  "Next.js"),
    ("vite.config.js",  "Vite"),
    ("angular.json",    "Angular"),
    ("pubspec.yaml",    "Flutter"),
    ("Cargo.toml",      "Rust/Cargo"),
    ("go.mod",          "Go Modules"),
    ("pom.xml",         "Maven/Java"),
    ("requirements.txt","Python/pip"),
    ("pyproject.toml",  "Python/pyproject"),
    ("Gemfile",         "Ruby/Bundler"),
    ("composer.json",   "PHP/Composer"),
    ("build.gradle",    "Gradle"),
    ("CMakeLists.txt",  "CMake"),
]

_IGNORE_DIRS = {
    "__pycache__", "node_modules", ".git", ".venv", "venv",
    ".mypy_cache", "dist", "build", ".next", "target", "bin", "obj",
}


def _detect_language(ext: str) -> Optional[str]:
    return _LANG_MAP.get(ext.lower())


def _detect_tech_stack(root: Path) -> List[str]:
    tech: List[str] = []
    for filename, framework in _FRAMEWORK_SIGNALS:
        if (root / filename).exists():
            tech.append(framework)
    return tech


def _parse_python_imports(filepath: Path) -> List[str]:
    """Extract top-level import names from a Python file."""
    imports: List[str] = []
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("import "):
                    imports.append(line.split()[1].split(".")[0])
                elif line.startswith("from "):
                    parts = line.split()
                    if len(parts) >= 2:
                        imports.append(parts[1].split(".")[0])
    except Exception:
        pass
    return imports[:10]


# ---------------------------------------------------------------------------
# Engineering Mode class
# ---------------------------------------------------------------------------
class EngineeringMode:
    """
    Core engineering intelligence capability for VOID.
    Uses Ollama for reasoning and existing project tools for analysis.
    """

    def __init__(self):
        self._llm = None   # lazy
        self._active = False

    def _get_llm(self):
        if self._llm is None:
            try:
                from backend.llm_client import OllamaClient
                self._llm = OllamaClient()
            except Exception as exc:
                logger.warning(f"[ENG] LLM client unavailable: {exc}")
        return self._llm

    # ------------------------------------------------------------------
    # Project analysis
    # ------------------------------------------------------------------
    def analyze_project(self, path: str = ".") -> ProjectAnalysis:
        """
        Analyse an existing project directory.
        Returns a ProjectAnalysis with structure, tech stack, and summary.
        """
        root = Path(path).resolve()
        if not root.exists():
            raise FileNotFoundError(f"Project path does not exist: {root}")

        logger.info(f"[ENG] Analysing project at: {root}")

        file_count = 0
        dir_count = 0
        lang_counts: Dict[str, int] = {}
        entry_points: List[str] = []
        key_files: List[str] = []
        python_deps: List[str] = []

        # Walk the project tree
        for item in root.rglob("*"):
            # Skip ignored directories
            if any(part in _IGNORE_DIRS for part in item.parts):
                continue
            if item.is_dir():
                dir_count += 1
            elif item.is_file():
                file_count += 1
                lang = _detect_language(item.suffix)
                if lang:
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1
                # Identify entry points
                if item.name in ("main.py", "app.py", "index.js", "index.ts",
                                  "server.js", "server.py", "manage.py", "main.go"):
                    entry_points.append(str(item.relative_to(root)))
                # Key config files
                if item.name in ("package.json", "requirements.txt", "Cargo.toml",
                                  "go.mod", "pyproject.toml", "Dockerfile"):
                    key_files.append(str(item.relative_to(root)))
                # Python imports from main files
                if item.suffix == ".py" and file_count <= 50:
                    python_deps.extend(_parse_python_imports(item))

        main_langs = sorted(lang_counts, key=lang_counts.get, reverse=True)[:3]
        tech_stack = _detect_tech_stack(root)

        # Build architecture summary
        summary_parts = []
        if main_langs:
            summary_parts.append(f"Primary languages: {', '.join(main_langs)}")
        if tech_stack:
            summary_parts.append(f"Frameworks/tools: {', '.join(tech_stack)}")
        if entry_points:
            summary_parts.append(f"Entry points: {', '.join(entry_points[:3])}")
        summary = ". ".join(summary_parts) + f". {file_count} files across {dir_count} directories."

        return ProjectAnalysis(
            root_path=str(root),
            file_count=file_count,
            directory_count=dir_count,
            tech_stack=tech_stack,
            main_languages=main_langs,
            entry_points=entry_points,
            dependencies={"python": list(set(python_deps))[:20]},
            key_files=key_files,
            architecture_summary=summary,
        )

    # ------------------------------------------------------------------
    # Code generation planning
    # ------------------------------------------------------------------
    def plan_code_generation(
        self,
        task: str,
        project_path: Optional[str] = None,
        context: str = "",
    ) -> EngineeringPlan:
        """
        Generate a structured implementation plan for a coding task.

        Args:
            task:         Natural language description of what to build.
            project_path: Path to an existing project for context (optional).
            context:      Additional context string (optional).

        Returns:
            EngineeringPlan with steps, files, tech recommendations.
        """
        logger.info(f"[ENG] Planning: '{task[:80]}'")
        t0 = time.perf_counter()

        # Optional project context
        project_summary = ""
        if project_path:
            try:
                analysis = self.analyze_project(project_path)
                project_summary = analysis.architecture_summary
            except Exception as exc:
                logger.warning(f"[ENG] Project analysis failed: {exc}")

        # Build LLM prompt
        prompt = self._build_planning_prompt(task, project_summary, context)
        llm_output = self._ask_llm(prompt)

        # Parse LLM output into structured plan
        plan = self._parse_plan(task, llm_output)
        elapsed = (time.perf_counter() - t0) * 1000
        logger.info(f"[ENG] Plan generated in {elapsed:.0f}ms — {len(plan.steps)} steps")
        return plan

    def suggest_architecture(self, requirements: str) -> str:
        """
        Ask Ollama to suggest an architecture for the given requirements.
        Returns a markdown-formatted architecture suggestion.
        """
        prompt = (
            "You are a senior software architect. "
            "Given the following requirements, suggest a clean, modern architecture. "
            "Include: tech stack, folder structure, key components, data flow, "
            "and potential pitfalls. Be specific and practical.\n\n"
            f"Requirements:\n{requirements}\n\n"
            "Architecture Suggestion:"
        )
        return self._ask_llm(prompt) or "Unable to generate architecture suggestion."

    def debug_assistance(self, code: str, error: str, language: str = "Python") -> str:
        """
        Provide debugging assistance for a code snippet + error message.
        """
        prompt = (
            f"You are an expert {language} developer. "
            f"Debug the following code and error.\n\n"
            f"CODE:\n```{language.lower()}\n{code[:2000]}\n```\n\n"
            f"ERROR:\n{error[:500]}\n\n"
            "Provide:\n"
            "1. Root cause of the error\n"
            "2. Exact fix with corrected code\n"
            "3. Explanation of why this happened\n"
            "4. How to prevent this in the future"
        )
        return self._ask_llm(prompt) or "Unable to generate debug assistance."

    def review_architecture(self, description: str) -> str:
        """
        Review a described architecture and provide improvement suggestions.
        """
        prompt = (
            "You are a senior software architect performing a code review. "
            "Review the following architecture and identify:\n"
            "1. Potential bottlenecks\n"
            "2. Security concerns\n"
            "3. Scalability issues\n"
            "4. Missing best practices\n"
            "5. Specific improvement recommendations\n\n"
            f"Architecture to review:\n{description}\n\n"
            "Review:"
        )
        return self._ask_llm(prompt) or "Unable to generate architecture review."

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_planning_prompt(self, task: str, project_ctx: str, extra_ctx: str) -> str:
        ctx_section = ""
        if project_ctx:
            ctx_section += f"\nExisting project context:\n{project_ctx}\n"
        if extra_ctx:
            ctx_section += f"\nAdditional context:\n{extra_ctx}\n"

        return (
            "You are a senior software engineer creating a detailed implementation plan.\n"
            f"Task: {task}\n"
            f"{ctx_section}\n"
            "Provide a structured plan with:\n"
            "1. Recommended tech stack (be specific about versions/frameworks)\n"
            "2. Step-by-step implementation steps (numbered list)\n"
            "3. Files to create (format: `path/to/file.ext` — description)\n"
            "4. Files to modify (if any existing project)\n"
            "5. External dependencies needed (e.g. npm packages, pip packages)\n"
            "6. Complexity estimate: low / medium / high\n"
            "7. Key architecture decisions and trade-offs\n\n"
            "Be specific, practical, and actionable. "
            "Prefer modern, widely-used tools. Avoid unnecessary complexity."
        )

    def _ask_llm(self, prompt: str) -> str:
        """Ask the LLM and return the response string."""
        llm = self._get_llm()
        if not llm:
            return ""
        try:
            response = llm.chat(prompt, system_override=(
                "You are VOID Engineering Mode — a senior software architect and developer. "
                "Provide precise, actionable, production-quality technical guidance."
            ))
            if isinstance(response, dict):
                return response.get("content") or response.get("message") or str(response)
            return str(response)
        except Exception as exc:
            logger.warning(f"[ENG] LLM call failed: {exc}")
            return ""

    def _parse_plan(self, task: str, llm_output: str) -> EngineeringPlan:
        """Parse LLM text output into an EngineeringPlan dataclass."""
        import re

        steps: List[str] = []
        files_to_create: List[Dict[str, str]] = []
        deps: List[str] = []
        complexity = "medium"
        tech_stack: List[str] = []
        arch_notes = ""

        if llm_output:
            # Extract numbered steps
            for m in re.finditer(r"^\d+\.\s+(.+)", llm_output, re.MULTILINE):
                text = m.group(1).strip()
                if text:
                    steps.append(text)

            # Extract file paths (backtick-quoted paths)
            for m in re.finditer(r"`([^`]+\.\w+)`\s*[—\-]\s*(.+)", llm_output):
                files_to_create.append({
                    "path": m.group(1).strip(),
                    "description": m.group(2).strip(),
                })

            # Detect complexity
            for word in ("high", "medium", "low"):
                if word in llm_output.lower():
                    complexity = word
                    break

            # Extract dependency mentions
            for pattern in (r"pip install ([\w\-]+)", r"npm install ([\w\-@/]+)"):
                for m in re.finditer(pattern, llm_output, re.IGNORECASE):
                    deps.append(m.group(1))

            arch_notes = llm_output[:600] if not steps else ""

        if not steps:
            steps = [
                "Analyse requirements and define scope",
                "Set up project structure and dependencies",
                "Implement core functionality",
                "Add error handling and validation",
                "Write tests",
                "Review and document",
            ]

        return EngineeringPlan(
            task=task,
            tech_stack=tech_stack,
            steps=steps,
            files_to_create=files_to_create,
            files_to_modify=[],
            estimated_complexity=complexity,
            architecture_notes=arch_notes,
            dependencies_needed=list(set(deps)),
            raw_llm_output=llm_output,
        )

    def status(self) -> Dict[str, Any]:
        """Return engineering mode status for the monitoring dashboard."""
        return {
            "active": self._active,
            "llm_available": self._get_llm() is not None,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_eng_mode: Optional[EngineeringMode] = None

def get_engineering_mode() -> EngineeringMode:
    """Return (or create) the EngineeringMode singleton."""
    global _eng_mode
    if _eng_mode is None:
        _eng_mode = EngineeringMode()
    return _eng_mode
