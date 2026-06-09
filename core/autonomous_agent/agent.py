import os
import json
import logging
from typing import Dict, Any, List, Optional

from core.autonomous_agent.scanner import ProjectScanner
from core.autonomous_agent.memory import CodebaseMemory
from core.autonomous_agent.lang_detect import detect_language
from core.autonomous_agent.file_engine import AgentFileEngine
from core.autonomous_agent.terminal_engine import AgentTerminalEngine
from core.autonomous_agent.error_analyzer import AgentErrorAnalyzer
from core.autonomous_agent.context_engine import AgentContextEngine
from core.autonomous_agent.git_integration import AgentGitIntegration
from core.autonomous_agent.safety_system import AgentSafetySystem

# Try to import OllamaClient
try:
    from backend.llm_client import OllamaClient
except ImportError:
    # Fallback/standalone client if server is not in import scope
    class OllamaClient:
        async def chat(self, history, prompt):
            return "Standalone placeholder reply."

logger = logging.getLogger("void.autonomous_agent.core")

class AutonomousAgent:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.scanner = ProjectScanner(root_dir)
        self.memory = CodebaseMemory(root_dir)
        self.file_engine = AgentFileEngine(root_dir)
        self.terminal_engine = AgentTerminalEngine(root_dir)
        self.error_analyzer = AgentErrorAnalyzer()
        self.context_engine = AgentContextEngine(root_dir)
        self.git = AgentGitIntegration(root_dir)
        self.safety = AgentSafetySystem(root_dir)
        self.llm = OllamaClient()

    async def scan_and_map(self) -> Dict[str, Any]:
        """Scan project, update frameworks, entry points, and hashes."""
        project_map = self.scanner.scan()
        
        # Update technology stack in memory
        self.memory.set_technology_stack(project_map.get("frameworks", []))
        
        # Track incremental states for scanned files
        for f_info in project_map.get("files", []):
            self.memory.update_file_state(f_info["path"])
            
        return project_map

    async def explain_architecture(self) -> str:
        """Explanatory method to explain codebase structure based on project map."""
        project_map = await self.scan_and_map()
        
        prompt = (
            f"Please explain the architecture of this project based on its scanned project map:\n\n"
            f"[PROJECT MAP]\n{json.dumps(project_map, indent=2)}\n[END PROJECT MAP]\n\n"
            f"Provide a clear, high-level summary of the technologies, directory structure, and entry points. "
            f"Address the user (Sir/Master Mridul) in your premium cybernetic AI assistant persona."
        )
        
        try:
            explanation = await self.llm.chat([], prompt)
            self.memory.set_architecture_summary(explanation)
            return explanation
        except Exception as e:
            return f"Failed to explain architecture: {e}"

    async def generate_plan(self, user_intent: str, context_files: List[str]) -> List[Dict[str, Any]]:
        """Query LLM to generate a plan of action steps."""
        context_data = ""
        for f in context_files:
            res = self.file_engine.read_file(f)
            if res.get("status") == "ok":
                context_data += f"\nFile: {f}\n```\n{res['content']}\n```\n"

        prompt = (
            f"User request: {user_intent}\n\n"
            f"Project files in context:\n{context_data}\n"
            f"Create a structured JSON plan to fulfill the request. The plan must be a list of step objects.\n"
            f"Each step must be one of these types:\n"
            f"- `edit_file`: Requires key `path` and key `content` (full replacement content).\n"
            f"- `create_file`: Requires key `path` and key `content` (initial content).\n"
            f"- `run_command`: Requires key `command`.\n\n"
            f"Respond ONLY with the JSON list of steps. Do not include markdown code block formatting or explanations.\n"
            f"Example format:\n"
            f'[\n  {{"type": "edit_file", "path": "src/app.py", "content": "print(\'hello\')\\n"}},\n  {{"type": "run_command", "command": "python src/app.py"}}\n]'
        )
        
        try:
            resp_str = await self.llm.chat([], prompt)
            
            # Clean response text if LLM output contains markdown ticks
            clean_str = resp_str.strip()
            if clean_str.startswith("```"):
                # Strip leading and trailing block ticks
                lines = clean_str.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_str = "\n".join(lines).strip()
            
            plan = json.loads(clean_str)
            if not isinstance(plan, list):
                plan = []
            return plan
        except Exception as e:
            logger.error(f"Failed to generate implementation plan: {e}")
            return []

    async def execute_plan(self, plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute the steps of an implementation plan."""
        results = []
        
        # Hook Git backup creation to execute before any multi-file rewrite step
        write_steps = [s for s in plan if s.get("type") in ["edit_file", "create_file"]]
        is_multi_file = len(write_steps) > 1
        
        backup_branch = None
        if is_multi_file and self.git.is_git_repo():
            logger.info("[AGENT] Multi-file rewrite detected. Executing git backup branch creation.")
            backup_branch = self.git.create_backup_branch()

        for step in plan:
            step_type = step.get("type")
            
            if step_type in ["edit_file", "create_file"]:
                path = step.get("path")
                content = step.get("content", "")
                
                if step_type == "edit_file":
                    res = self.file_engine.write_file(path, content)
                else:
                    res = self.file_engine.create_file(path, content)
                    
                results.append(res)
                if res.get("status") == "pending_confirmation":
                    return {
                        "status": "pending_confirmation",
                        "pending_step": step,
                        "results": results,
                        "backup_branch": backup_branch
                    }
                if res.get("status") == "error":
                    return {"status": "error", "message": res.get("message"), "results": results}

            elif step_type == "run_command":
                command = step.get("command")
                res = await self.terminal_engine.execute_command(command)
                results.append(res)
                
                if res.get("status") == "pending_confirmation":
                    return {
                        "status": "pending_confirmation",
                        "pending_step": step,
                        "results": results,
                        "backup_branch": backup_branch
                    }
                    
                if res.get("status") == "error":
                    return {"status": "error", "message": res.get("message"), "results": results}
                
                # If command fails, attempt build fix
                if res.get("exit_code", 0) != 0:
                    stderr = res.get("stderr", "")
                    stdout = res.get("stdout", "")
                    fix_res = await self.handle_build_error(stdout + "\n" + stderr)
                    results.append(fix_res)
                    if fix_res.get("status") != "ok":
                        return {"status": "error", "message": "Command failed and build error fix failed.", "results": results}
        
        # Git commit if changes were made
        if self.git.is_git_repo() and self.git.status():
            self.git.add(["."])
            self.git.commit("VOID Auto-Commit: Autonomous Agent code modifications applied.")

        return {
            "status": "ok",
            "results": results,
            "backup_branch": backup_branch
        }

    async def handle_build_error(self, error_logs: str) -> Dict[str, Any]:
        """Parse build error, get LLM suggested fix, and apply it."""
        analysis = await self.error_analyzer.analyze_and_suggest_fix(error_logs, self.llm)
        parsed_errors = analysis.get("parsed_errors", [])
        
        if not parsed_errors:
            return {"status": "error", "message": "Could not identify offending file or error in logs."}
            
        first_err = parsed_errors[0]
        offending_file = first_err.get("file")
        
        # Retrieve current content of offending file
        read_res = self.file_engine.read_file(offending_file)
        if read_res.get("status") != "ok":
            return {"status": "error", "message": f"Failed to read offending file: {offending_file}"}
            
        original_content = read_res.get("content", "")
        
        # Ask LLM for the fixed file content
        prompt = (
            f"The application failed with this error:\n{error_logs}\n\n"
            f"Offending file: {offending_file}\n"
            f"Original file content:\n```\n{original_content}\n```\n\n"
            f"Please output the complete, corrected content of the file. "
            f"Provide ONLY the corrected file content. Do not include markdown code block formatting or explanation."
        )
        
        try:
            fixed_content = await self.llm.chat([], prompt)
            
            clean_content = fixed_content.strip()
            if clean_content.startswith("```"):
                lines = clean_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_content = "\n".join(lines).strip()

            # Write the fixed content
            write_res = self.file_engine.write_file(offending_file, clean_content)
            return {
                "status": "ok",
                "message": f"Applied suggested fix to {offending_file}",
                "write_result": write_res,
                "analysis": analysis.get("explanation")
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to apply error fix: {e}"}

    def _analyze_python_ast(self, content: str) -> str:
        """Parses Python source code AST to collect refactoring hints."""
        import ast
        hints = []
        try:
            tree = ast.parse(content)
        except SyntaxError as se:
            return f"Syntax Error detected at line {se.lineno}: {se.msg}\n"
        except Exception as e:
            return f"AST Parsing failed: {str(e)}\n"
            
        imported_names = set()
        used_names = set()
        defined_funcs = []
        defined_classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    used_names.add(node.id)
            elif isinstance(node, ast.FunctionDef):
                defined_funcs.append(node.name)
            elif isinstance(node, ast.ClassDef):
                defined_classes.append(node.name)
                
        unused_imports = imported_names - used_names
        if unused_imports:
            hints.append(f"- Unused imports detected: {', '.join(unused_imports)}")
        if defined_funcs:
            hints.append(f"- Defined functions: {', '.join(defined_funcs)}")
        if defined_classes:
            hints.append(f"- Defined classes: {', '.join(defined_classes)}")
            
        if not hints:
            return "AST Analysis: Code structure is sound.\n"
        return "AST Analysis:\n" + "\n".join(hints) + "\n"

    async def refactor_code(self, file_path: str) -> Dict[str, Any]:
        """
        Scan a code file for dead code, unused imports, or bad structures,
        and generate a refactored version using LLM guidance.
        """
        # Read the file
        read_res = self.file_engine.read_file(file_path)
        if read_res.get("status") != "ok":
            return {"status": "error", "message": f"Failed to read file for refactoring: {file_path}"}
            
        content = read_res.get("content", "")
        lang = detect_language(file_path)
        
        # AST Parser Analysis for Refactoring Hints
        ast_hints = ""
        if file_path.endswith(".py"):
            ast_hints = self._analyze_python_ast(content)
        prompt = (
            f"You are the refactoring engine for the VOID Operating System.\n"
            f"Target file: {file_path}\n"
            f"Language: {lang}\n"
            f"{ast_hints}\n"
            f"Code content:\n```\n{content}\n```\n\n"
            f"Task: Please identify code smells, unused variables/imports, dead code, and performance bottlenecks. "
            f"Refactor the code to improve its structure, clean up dead segments, and optimize performance. "
            f"Provide ONLY the complete refactored file content. Do not include markdown code block formatting or explanations."
        )
        
        # Perform optional deep syntax check (AST parsing) for Python before sending to LLM
        if lang.lower() in ["python", "py"]:
            import ast
            try:
                ast.parse(content)
            except SyntaxError as syntax_err:
                prompt += f"\nNote: The current file has a SyntaxError: {syntax_err}. Please fix this syntax error during refactoring."
        
        try:
            refactored_content = await self.llm.chat([], prompt)
            clean_content = refactored_content.strip()
            
            # Clean markdown formatting if present
            if clean_content.startswith("```"):
                lines = clean_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_content = "\n".join(lines).strip()
                
            # Perform deep syntax check on refactored content for Python
            if lang.lower() in ["python", "py"]:
                import ast
                try:
                    ast.parse(clean_content)
                except SyntaxError as e:
                    return {"status": "error", "message": f"LLM returned invalid Python syntax: {e}"}
                
            # Perform git backup branch creation first
            backup_branch = None
            if self.git.is_git_repo():
                backup_branch = self.git.create_backup_branch()

            # Perform write
            write_res = self.file_engine.write_file(file_path, clean_content)
            return {
                "status": "ok",
                "message": f"Successfully refactored {file_path}.",
                "refactored": True,
                "backup_branch": backup_branch,
                "write_result": write_res
            }
        except Exception as e:
            logger.error(f"Refactor failed: {e}")
            return {"status": "error", "message": str(e)}

    async def process_intent(self, user_intent: str) -> Dict[str, Any]:
        """Main entry point to parse intent, generate plans, and run modifications."""
        # 1. Scan the project
        await self.scan_and_map()
        
        # 2. Extract context files
        context_files = self.context_engine.get_relevant_files(user_intent)
        
        # 3. Create plan
        plan = await self.generate_plan(user_intent, context_files)
        if not plan:
            return {"status": "error", "message": "Failed to create a valid modification plan."}
            
        # 4. Execute plan
        exec_res = await self.execute_plan(plan)
        return exec_res
