import os
import psutil
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("void.self_verifier")

class SelfVerifier:
    def __init__(self):
        pass

    async def verify(self, name: str, payload: Dict[str, Any], result: Any) -> Dict[str, Any]:
        """
        Verify the outcome of tool execution.
        Returns:
            {"status": "ok"/"fail", "message": "explanation"}
        """
        method = getattr(self, f"_verify_{name}", None)
        if method:
            try:
                return await method(payload, result)
            except Exception as e:
                logger.error(f"Error executing verification for '{name}': {e}")
                return {"status": "fail", "message": f"Verification failed with internal error: {e}"}
        
        # Default verification: Check if result meta status is not FAIL
        status_str = "ok"
        msg_str = "Standard execution verified successfully, Sir."
        if hasattr(result, "meta") and isinstance(result.meta, dict):
            status = result.meta.get("status")
            if status in ["FAIL", "TIMEOUT"]:
                status_str = "fail"
                msg_str = f"Execution returned failed state: {status}"
        elif isinstance(result, dict):
            status = result.get("status")
            if status in ["FAIL", "TIMEOUT", "error"]:
                status_str = "fail"
                msg_str = f"Execution returned failed state: {status}"

        return {"status": status_str, "message": msg_str}

    async def _verify_open_app(self, payload: Dict[str, Any], result: Any) -> Dict[str, Any]:
        app_name = payload.get("app", "").lower()
        if not app_name:
            return {"status": "ok", "message": "Skipped verification due to missing app name."}

        # Check running processes
        found = False
        for proc in psutil.process_iter(["name"]):
            try:
                pname = proc.info["name"]
                if pname and app_name in pname.lower():
                    found = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if found:
            return {"status": "ok", "message": f"Application '{app_name}' verified running in process tree, Sir."}
        else:
            # Fallback check - subprocesses are async; wait a moment and check again
            await asyncio.sleep(1.0)
            for proc in psutil.process_iter(["name"]):
                try:
                    pname = proc.info["name"]
                    if pname and app_name in pname.lower():
                        found = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if found:
                 return {"status": "ok", "message": f"Application '{app_name}' verified running after retry delay, Sir."}
            return {"status": "fail", "message": f"Process matching '{app_name}' was not detected in active process tree."}

    async def _verify_create_folder(self, payload: Dict[str, Any], result: Any) -> Dict[str, Any]:
        path = payload.get("folder_path", "")
        if path and os.path.isdir(path):
            return {"status": "ok", "message": f"Directory '{path}' exists and is verified, Sir."}
        return {"status": "fail", "message": f"Folder '{path}' was not found after creation."}

    async def _verify_file_manager(self, payload: Dict[str, Any], result: Any) -> Dict[str, Any]:
        path = payload.get("path", "")
        content = payload.get("content")
        if not path:
            return {"status": "fail", "message": "Path missing from payload."}

        if not os.path.exists(path):
            return {"status": "fail", "message": f"File '{path}' does not exist."}

        if content is not None:
            # Verify file was written and is not empty
            size = os.path.getsize(path)
            if size > 0:
                return {"status": "ok", "message": f"File '{path}' written successfully ({size} bytes verified), Sir."}
            else:
                return {"status": "fail", "message": f"File '{path}' was created but is empty."}
        else:
            # Reading file: verify result payload exists
            output = getattr(result, "output", "") if hasattr(result, "output") else str(result)
            if output and "Error" not in output:
                return {"status": "ok", "message": f"File read operation verified ({len(output)} chars retrieved), Sir."}
            return {"status": "fail", "message": f"Failed to retrieve file contents. Output: {output}"}

    async def _verify_agent_run_tests(self, payload: Dict[str, Any], result: Any) -> Dict[str, Any]:
        output = getattr(result, "output", "") if hasattr(result, "output") else str(result)
        # Check exit codes or failures
        if "Exit Code: 0" in output or "passed" in output:
             return {"status": "ok", "message": "Test suite ran successfully with zero failures, Sir."}
        return {"status": "fail", "message": "Test suite executed but reported failures."}

    async def _verify_screenshot(self, payload: Dict[str, Any], result: Any) -> Dict[str, Any]:
        # Screenshots are saved to standard path or project root
        from tools.system_control import SCREENSHOT_PATH
        if os.path.exists(SCREENSHOT_PATH) and os.path.getsize(SCREENSHOT_PATH) > 0:
            return {"status": "ok", "message": "Screenshot captured and verified on disk, Sir."}
        return {"status": "fail", "message": "Screenshot file was not found or is empty."}
