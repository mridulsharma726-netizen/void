import os
import re
import ast
import logging
from typing import Dict, Any, List, Set, Tuple

logger = logging.getLogger("void.code_analyzer")

class CodebaseAnalyzer:
    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.py_files: List[str] = []
        self._find_py_files()

    def _find_py_files(self):
        ignored_dirs = {"venv", ".venv", "node_modules", ".git", "__pycache__", "build", "dist"}
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for f in files:
                if f.endswith(".py"):
                    self.py_files.append(os.path.join(root, f))

    def analyze(self) -> Dict[str, Any]:
        """Perform full static analysis on the codebase."""
        if not self.py_files:
            return {"status": "ok", "health_score": 100, "message": "No Python files found to analyze."}

        dependency_graph: Dict[str, Set[str]] = {}
        todos: List[Dict[str, Any]] = []
        fixmes: List[Dict[str, Any]] = []
        security_risks: List[Dict[str, Any]] = []
        large_functions: List[Dict[str, Any]] = []
        large_classes: List[Dict[str, Any]] = []
        unused_imports: List[Dict[str, Any]] = []
        missing_docs: List[Dict[str, Any]] = []
        
        # Track defined functions/classes to check for dead code
        defined_symbols: Set[str] = set()
        used_symbols: Set[str] = set()
        
        # File contents cache for duplication check
        file_contents: Dict[str, List[str]] = {}

        for filepath in self.py_files:
            rel_path = os.path.relpath(filepath, self.root_dir).replace("\\", "/")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    lines = content.splitlines()
                    file_contents[rel_path] = lines
            except Exception as e:
                logger.error(f"Failed to read '{filepath}': {e}")
                continue

            # 1. Regex checks (TODOs, FIXMEs, hardcoded secrets)
            for idx, line in enumerate(lines, 1):
                if "# todo" in line.lower() or "// todo" in line.lower():
                    todos.append({"file": rel_path, "line": idx, "content": line.strip()})
                if "# fixme" in line.lower() or "// fixme" in line.lower():
                    fixmes.append({"file": rel_path, "line": idx, "content": line.strip()})
                # Check for hardcoded API keys/passwords
                if re.search(r'(?:api_key|password|secret|token)\s*=\s*["\'][a-zA-Z0-9_\-]{16,}["\']', line.lower()):
                    security_risks.append({"file": rel_path, "line": idx, "type": "hardcoded_secret", "content": line.strip()})

            # 2. AST parsing
            try:
                tree = ast.parse(content)
                imports = self._extract_imports(tree)
                dependency_graph[rel_path] = imports

                # Run AST analysis helpers
                self._analyze_ast_nodes(
                    tree, rel_path, lines, defined_symbols, used_symbols,
                    security_risks, large_functions, large_classes, unused_imports, missing_docs
                )
            except Exception as e:
                logger.warning(f"AST parsing failed for '{rel_path}': {e}")

        # 3. Dead code detection
        dead_code = list(defined_symbols - used_symbols)
        # Filter out dunder methods or main/init symbols
        dead_code = [sym for sym in dead_code if not sym.startswith("_") and sym not in {"main", "app", "router"}]

        # 4. Cyclic dependencies
        cycles = self._detect_cycles(dependency_graph)

        # 5. Duplicated code
        duplicates = self._detect_duplicates(file_contents)

        # 6. Calculate health score
        health_score = 100
        health_score -= len(security_risks) * 10
        health_score -= len(cycles) * 5
        health_score -= (len(large_functions) + len(large_classes)) * 2
        health_score -= (len(dead_code) + len(duplicates)) * 2
        health_score -= (len(unused_imports) + len(missing_docs) + len(todos) + len(fixmes)) * 0.5
        health_score = max(0, min(100, int(health_score)))

        explanations = []
        if security_risks: explanations.append(f"⚠️ {len(security_risks)} hardcoded secret or unsafe function risk(s).")
        if cycles: explanations.append(f"⚠️ {len(cycles)} cyclic dependency loop(s).")
        if large_functions or large_classes: explanations.append(f"⚠️ {len(large_functions)} large function(s) and {len(large_classes)} large class(es) detected.")
        if dead_code: explanations.append(f"⚠️ {len(dead_code)} potentially unused function(s) or class(es) (dead code).")
        if duplicates: explanations.append(f"⚠️ {len(duplicates)} duplicated code block(s).")
        if not explanations: explanations.append("✅ Codebase structure conforms to premium modular engineering standards.")

        return {
            "status": "ok",
            "health_score": health_score,
            "summary": " | ".join(explanations),
            "data": {
                "cycles": cycles,
                "dead_code": dead_code[:20],  # limit report size
                "duplicates": duplicates[:10],
                "large_functions": large_functions[:10],
                "large_classes": large_classes[:10],
                "todos": todos[:25],
                "fixmes": fixmes[:25],
                "security_risks": security_risks[:10],
                "unused_imports": unused_imports[:15],
                "missing_docs": missing_docs[:20]
            }
        }

    def _extract_imports(self, tree: ast.AST) -> Set[str]:
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.add(name.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
        return imports

    def _analyze_ast_nodes(
        self, tree: ast.AST, rel_path: str, lines: List[str],
        defined_symbols: Set[str], used_symbols: Set[str],
        security_risks: List[Dict[str, Any]], large_functions: List[Dict[str, Any]],
        large_classes: List[Dict[str, Any]], unused_imports: List[Dict[str, Any]],
        missing_docs: List[Dict[str, Any]]
    ):
        file_imports = set()

        for node in ast.walk(tree):
            # Track defined symbols
            if isinstance(node, ast.FunctionDef):
                defined_symbols.add(node.name)
                # Check large functions
                start_line = node.lineno
                end_line = getattr(node, "end_lineno", start_line + 5)
                length = end_line - start_line + 1
                if length > 50:
                    large_functions.append({"file": rel_path, "name": node.name, "lines": length})
                # Check missing docstring
                if not ast.get_docstring(node):
                    missing_docs.append({"file": rel_path, "type": "function", "name": node.name, "line": start_line})

            elif isinstance(node, ast.ClassDef):
                defined_symbols.add(node.name)
                # Check large classes
                start_line = node.lineno
                end_line = getattr(node, "end_lineno", start_line + 10)
                length = end_line - start_line + 1
                method_count = len([n for n in node.body if isinstance(n, ast.FunctionDef)])
                if length > 300 or method_count > 15:
                    large_classes.append({"file": rel_path, "name": node.name, "lines": length, "methods": method_count})
                # Check missing docstring
                if not ast.get_docstring(node):
                    missing_docs.append({"file": rel_path, "type": "class", "name": node.name, "line": start_line})

            # Track references (to detect dead code)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    used_symbols.add(node.id)

            elif isinstance(node, ast.Attribute):
                used_symbols.add(node.attr)

            # Security risks (unsafe commands / shell=True / eval)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "eval":
                    security_risks.append({"file": rel_path, "line": node.lineno, "type": "unsafe_eval", "content": "Use of eval() detected."})
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "Popen":
                    # Check shell=True kwarg
                    for keyword in node.keywords:
                        if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                            security_risks.append({"file": rel_path, "line": node.lineno, "type": "unsafe_subprocess_shell", "content": "Subprocess shell=True detected."})

            # Track imports for unused imports check
            elif isinstance(node, ast.Import):
                for name in node.names:
                    file_imports.add(name.asname or name.name)
            elif isinstance(node, ast.ImportFrom):
                for name in node.names:
                    file_imports.add(name.asname or name.name)

        # Check unused imports
        for imp in file_imports:
            # If the import name is not referenced in the file content, report it
            # Simple check: name not in Name or Attribute nodes
            if imp not in used_symbols:
                unused_imports.append({"file": rel_path, "name": imp})

    def _detect_cycles(self, graph: Dict[str, Set[str]]) -> List[List[str]]:
        cycles = []
        visited = {}  # 0: unvisited, 1: visiting, 2: visited
        
        def dfs(node: str, path: List[str]):
            visited[node] = 1
            path.append(node)
            
            # Find dependencies of this node (match module name to files in the graph)
            deps = graph.get(node, set())
            for dep in deps:
                # Find matching filepath for this module import
                dep_file = None
                for k in graph.keys():
                    if k.endswith(f"/{dep}.py") or k == f"{dep}.py":
                        dep_file = k
                        break
                
                if dep_file:
                    if visited.get(dep_file, 0) == 1:
                        # Cycle found!
                        cycle_start = path.index(dep_file)
                        cycles.append(path[cycle_start:] + [dep_file])
                    elif visited.get(dep_file, 0) == 0:
                        dfs(dep_file, path)
            
            path.pop()
            visited[node] = 2

        for node in graph:
            if visited.get(node, 0) == 0:
                dfs(node, [])
        return cycles

    def _detect_duplicates(self, file_contents: Dict[str, List[str]], min_lines: int = 6) -> List[Dict[str, Any]]:
        duplicates = []
        hashes: Dict[str, Tuple[str, int]] = {}  # hash -> (file, line_num)

        for rel_path, lines in file_contents.items():
            for i in range(len(lines) - min_lines + 1):
                block = "\n".join([line.strip() for line in lines[i:i + min_lines]])
                # Ignore empty blocks or short comments
                if len(block) < 50 or block.startswith("#") or block.startswith("//"):
                    continue
                
                block_hash = str(hash(block))
                if block_hash in hashes:
                    orig_file, orig_line = hashes[block_hash]
                    if orig_file != rel_path:
                        duplicates.append({
                            "file1": orig_file,
                            "line1": orig_line,
                            "file2": rel_path,
                            "line2": i + 1,
                            "snippet": block[:80] + "..."
                        })
                else:
                    hashes[block_hash] = (rel_path, i + 1)
        return duplicates
