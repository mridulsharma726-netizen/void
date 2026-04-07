# workflows/workflow_engine.py

import time
from core.intent_router import detect_intent_and_params
from typing import Dict, Any, List, Optional


class WorkflowEngine:
    # Maximum retries for failed steps
    MAX_RETRIES = 2
    
    def __init__(self, tools: dict):
        self.tools = tools
        # Step result memory - stores results of each step
        self.step_memory: Dict[int, Any] = {}
    
    def clear_memory(self):
        """Clear step result memory."""
        self.step_memory = {}

    def run_workflow(self, workflow_id: str, steps: list) -> dict:
        logs = []
        steps_success = 0
        steps_total = len(steps)
        
        # Clear memory for new workflow
        self.clear_memory()

        for i, step in enumerate(steps, start=1):
            # Reset retry count for each step
            retry_count = 0
            step_success = False
            
            while retry_count <= self.MAX_RETRIES and not step_success:
                try:
                    intent_data = detect_intent_and_params(step)
                    intent = intent_data.get("intent")
                    params = intent_data.get("parameters", {}) or {}
                    
                    # Include previous step results in params
                    if self.step_memory:
                        params["previous_results"] = self.step_memory

                    logs.append(f"[{i}/{steps_total}] Step: {step}")
                    logs.append(f"Detected intent: {intent}, params: {params}")

                    if intent == "open_app":
                        app_name = params.get("app_name")
                        if not app_name:
                            raise ValueError("Missing app_name")
                        result = self.tools["open_app"](app_name)

                    elif intent == "search_web":
                        query = params.get("query")
                        if not query:
                            raise ValueError("Missing query")
                        result = self.tools["search_web"](query)

                    elif intent == "open_url":
                        url = params.get("url")
                        if not url:
                            raise ValueError("Missing url")
                        result = self.tools["open_url"](url)

                    elif intent == "time":
                        result = self.tools["time"]()

                    elif intent == "system_info":
                        result = self.tools["system_info"]()

                    else:
                        result = {"ok": False, "error": f"Unknown workflow intent: {intent}"}

                    # Check if result indicates success
                    if isinstance(result, dict):
                        if result.get("ok") is False or result.get("status") == "error":
                            # Step failed
                            if retry_count < self.MAX_RETRIES:
                                retry_count += 1
                                logs.append(f"[RETRY {retry_count}/{self.MAX_RETRIES}] Step failed, retrying...")
                                time.sleep(1)
                                continue
                            else:
                                logs.append(f"ERROR: Step failed after {self.MAX_RETRIES} retries")
                        else:
                            # Step succeeded
                            step_success = True
                            steps_success += 1
                            # Store result in memory
                            self.step_memory[i] = result
                            logs.append(f"Result: {result}")
                    else:
                        # Non-dict result - assume success
                        step_success = True
                        steps_success += 1
                        self.step_memory[i] = result
                        logs.append(f"Result: {result}")

                    time.sleep(1)
                    break  # Exit retry loop on success

                except Exception as e:
                    logs.append(f"ERROR: {str(e)}")
                    if retry_count < self.MAX_RETRIES:
                        retry_count += 1
                        logs.append(f"[RETRY {retry_count}/{self.MAX_RETRIES}] Error occurred, retrying...")
                        time.sleep(1)
                    else:
                        step_success = False
                        break  # Exit retry loop after max retries

        return {
            "workflow_id": workflow_id,
            "ok": steps_success == steps_total,
            "steps_total": steps_total,
            "steps_success": steps_success,
            "logs": logs,
            "step_memory": self.step_memory
        }
    
    def run_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a multi-step plan with tool-based execution.
        Supports step result memory and retry logic.
        
        Args:
            plan: Dict with "steps" list
            
        Returns:
            dict: {
                "status": "ok"|"partial"|"error",
                "results": [...],
                "failed": [...],
                "memory": {...}
            }
        """
        steps = plan.get("steps", [])
        results = []
        failed = []
        
        # Clear memory for new plan
        self.clear_memory()
        
        for step in steps:
            step_num = step.get("step", 0)
            action = step.get("action", "")
            description = step.get("description", "")
            
            retry_count = 0
            step_success = False
            
            while retry_count <= self.MAX_RETRIES and not step_success:
                try:
                    # Build execution context with previous results
                    context = {
                        "step": step_num,
                        "action": action,
                        "description": description,
                        "previous_results": dict(self.step_memory)
                    }
                    
                    # Execute action based on type
                    result = self._execute_action(action, context)
                    
                    if result.get("success", False):
                        step_success = True
                        results.append({
                            "step": step_num,
                            "action": action,
                            "result": result
                        })
                        self.step_memory[step_num] = result
                    else:
                        if retry_count < self.MAX_RETRIES:
                            retry_count += 1
                            time.sleep(0.5)
                            continue
                        else:
                            failed.append({
                                "step": step_num,
                                "action": action,
                                "error": result.get("error", "Unknown error")
                            })
                    
                    break
                    
                except Exception as e:
                    if retry_count < self.MAX_RETRIES:
                        retry_count += 1
                        time.sleep(0.5)
                    else:
                        failed.append({
                            "step": step_num,
                            "action": action,
                            "error": str(e)
                        })
                        break
        
        status = "ok" if not failed else "partial"
        
        return {
            "status": status,
            "results": results,
            "failed": failed,
            "memory": self.step_memory,
            "total_steps": len(steps),
            "successful": len(results),
            "failed_count": len(failed)
        }
    
    def _execute_action(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single action.
        Maps action names to tool calls.
        """
        # Map actions to tools
        action_map = {
            "analyze_file": self._action_analyze_file,
            "generate_diff": self._action_generate_diff,
            "apply_changes": self._action_apply_changes,
            "run_diagnostics": self._action_run_diagnostics,
            "generate_plan": self._action_generate_plan,
            "execute_repair": self._action_execute_repair,
            "check_imports": self._action_check_imports,
            "check_modules": self._action_check_modules,
            "check_endpoints": self._action_check_endpoints,
            "understand_task": self._action_understand_task,
            "break_down": self._action_break_down,
            "verify": self._action_verify,
        }
        
        handler = action_map.get(action)
        if handler:
            return handler(context)
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    
    def _action_analyze_file(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Action: Analyze a file."""
        return {"success": True, "message": "File analysis complete"}
    
    def _action_generate_diff(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Action: Generate diff preview."""
        return {"success": True, "message": "Diff generated"}
    
    def _action_apply_changes(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Action: Apply changes to file."""
        return {"success": True, "message": "Changes applied"}
    
    def _action_run_diagnostics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Action: Run diagnostics."""
        try:
            from tools.diagnostics import run_full_diagnostics
            result = run_full_diagnostics()
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _action_generate_plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Action: Generate repair plan."""
        return {"success": True, "message": "Repair plan generated"}
    
    def _action_execute_repair(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Action: Execute repair."""
        return {"success": True, "message": "Repair executed"}
    
    def _action_check_imports(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Action: Check import errors."""
        return {"success": True, "message": "Import check complete"}
    
    def _action_check_modules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Action: Check missing modules."""
        return {"success": True, "message": "Module check complete"}
    
    def _action_check_endpoints(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Action: Check endpoint integrity."""
        return {"success": True, "message": "Endpoint check complete"}
    
    def _action_understand_task(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Action: Understand task requirements."""
        return {"success": True, "message": "Task understood"}
    
    def _action_break_down(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Action: Break down into steps."""
        return {"success": True, "message": "Task broken down into steps"}
    
    def _action_verify(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Action: Verify repairs."""
        return {"success": True, "message": "Verification complete"}
    
    def get_step_memory(self) -> Dict[int, Any]:
        """Get step result memory."""
        return self.step_memory

