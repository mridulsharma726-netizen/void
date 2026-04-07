# VOID Autonomous Agent Upgrade Plan

## Objective
Upgrade VOID into a controlled autonomous agent with developer mode, self-repair, and safe file editing capabilities.

---

## PART 1 — EXTEND brain.py
**File**: `VOID/core/brain.py`

Add to existing brain.py:
- `developer_mode = False` (global state)
- `developer_mode_lock` (thread safety)
- Methods:
  - `enter_developer_mode()` - Enable developer mode
  - `exit_developer_mode()` - Disable developer mode
  - `is_developer_mode()` - Check status
  - `create_plan(task)` - Create structured plan
  - `execute_plan(plan)` - Execute plan steps
  - `reflect_on_result(result)` - Analyze execution

**Constraint**: Do NOT modify existing chat reasoning logic.

---

## PART 2 — MODIFY main.py (INTERCEPT LAYER)
**File**: `VOID/main.py`

Before LLM execution in `/chat` endpoint:
- Add deterministic intercept for commands:
  - "enter developer mode" → `brain.enter_developer_mode()`
  - "exit developer mode" → `brain.exit_developer_mode()`
  - "repair yourself" → Run repair workflow
  - "analyze system" → Run diagnostics
  - "modify file" → Route to file_manager
  - "apply patch" → Route to file_manager

- If matched: bypass LLM, return structured response
- If not matched: continue existing flow exactly as before

**Constraint**: Do NOT alter response format `{"reply": "...", "meta": {...}}`

---

## PART 3 — CREATE tools/file_manager.py
**File**: `VOID/tools/file_manager.py` (NEW)

Implement:
- `read_file(path)` - Read file content
- `write_file(path, content)` - Write with backup
- `apply_patch(path, diff)` - Apply diff
- `generate_diff(original, modified)` - Create diff
- `backup_file(path)` - Create backup
- `restore_backup(path)` - Restore from backup
- `list_directory(path)` - List directory

Safety:
- `ALLOWED_PATHS = ["VOID/tools", "VOID/"]`
- Block: venv, node_modules, system folders, Windows root, Electron, desktop

Requirements:
- Create backup before any write
- Generate diff preview before modification
- Require `developer_mode = True` for modifications

---

## PART 4 — EXTEND self_repair.py
**File**: `VOID/tools/self_repair.py`

Add:
- `run_diagnostics()` - Check import errors, missing modules, broken tools, error logs, endpoint integrity
- `generate_repair_plan(issues)` - Create step-by-step plan

Flow for "repair yourself":
1. Check `developer_mode` - if False, return "Enter developer mode first."
2. Run diagnostics
3. Generate repair plan
4. Show plan
5. Ask confirmation (via response)
6. Apply changes via file_manager
7. Log everything
8. Return summary

---

## PART 5 — MODIFY workflow_engine.py
**File**: `VOID/workflows/workflow_engine.py`

Add:
- Multi-step plan execution support
- Tool-based execution
- Step result memory
- Failure retry logic (max 2 retries)

**Constraint**: DO NOT break existing workflows.

---

## SECURITY RULES
- No file modification without `developer_mode = True`
- Always show diff before write
- Always create backup before write
- Log all modifications to `logs/brain.log`

---

## LOGGING
File: `VOID/logs/brain.log` (create if not exists)
Log:
- Developer mode entry/exit
- File modifications
- Repair actions
- Diagnostics results

---

## SUCCESS CRITERIA
- VOID chats normally (unchanged)
- Developer mode activates only on command
- All existing endpoints remain functional
- Voice system undisturbed
- UI undisturbed
- Memory system undisturbed
- Workflow system undisturbed

---

## Files to Modify:
1. `VOID/core/brain.py` - Extend
2. `VOID/main.py` - Add intercept
3. `VOID/tools/file_manager.py` - Create NEW
4. `VOID/tools/self_repair.py` - Extend
5. `VOID/workflows/workflow_engine.py` - Extend

---

## Do NOT:
- Create duplicate brain systems
- Replace chat logic
- Modify response format
- Break existing tools
- Add auto-repair without confirmation
- Add unrestricted file access

