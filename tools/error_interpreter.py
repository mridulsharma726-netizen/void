"""
VOID Error Interpreter Module
===========================

Converts Python exceptions into clear, human-readable English explanations.

Features:
- translate_exception() - Main translation function
- ERROR_MAPPINGS - Dictionary of common error types
- User-friendly error messages for UI display
"""

from typing import Dict, Any, Optional
import traceback
import sys
import os

# ============================================================================
# ERROR MAPPINGS - Common Python errors translated to English
# ============================================================================

ERROR_MAPPINGS: Dict[str, Dict[str, str]] = {
    # Import Errors
    "ImportError": {
        "title": "Missing Module",
        "message": "A required code module is not installed or cannot be found.",
        "action": "Try running: pip install [module-name]",
        "severity": "high"
    },
    "ModuleNotFoundError": {
        "title": "Module Not Found",
        "message": "The system is trying to use a module that doesn't exist.",
        "action": "Install the missing module or check for typos in imports.",
        "severity": "high"
    },
    "ImportError": {
        "title": "Import Failed",
        "message": "Could not load a required component.",
        "action": "Check if all dependencies are installed correctly.",
        "severity": "high"
    },
    
    # File Errors
    "FileNotFoundError": {
        "title": "File Missing",
        "message": "The system couldn't find a file it's looking for.",
        "action": "Check if the file path is correct.",
        "severity": "medium"
    },
    "PermissionError": {
        "title": "Access Denied",
        "message": "The system doesn't have permission to access a file or folder.",
        "action": "Check file permissions or run as administrator.",
        "severity": "high"
    },
    "IOError": {
        "title": "File Operation Failed",
        "message": "Could not read or write to a file.",
        "action": "Check if the file is being used by another program.",
        "severity": "medium"
    },
    "IsADirectoryError": {
        "title": "Expected File, Got Directory",
        "message": "The system tried to open a folder as if it were a file.",
        "action": "Use a file path instead of a folder path.",
        "severity": "low"
    },
    
    # Syntax and Code Errors
    "SyntaxError": {
        "title": "Code Grammar Mistake",
        "message": "There's a typo or grammatical error in the code.",
        "action": "Check for missing parentheses, quotes, or colons.",
        "severity": "high"
    },
    "IndentationError": {
        "title": "Wrong Indentation",
        "message": "Code lines are not aligned correctly.",
        "action": "Check that code blocks are properly indented.",
        "severity": "medium"
    },
    "TabError": {
        "title": "Mixed Tab and Spaces",
        "message": "Inconsistent use of tabs and spaces for indentation.",
        "action": "Use consistent indentation (preferably spaces).",
        "severity": "medium"
    },
    
    # Name Errors
    "NameError": {
        "title": "Undefined Name",
        "message": "The code is using a variable or function that hasn't been defined.",
        "action": "Check for typos or make sure the variable is defined first.",
        "severity": "medium"
    },
    "UnboundLocalError": {
        "title": "Variable Used Before Definition",
        "message": "A variable is being used before it was given a value.",
        "action": "Initialize the variable before using it.",
        "severity": "medium"
    },
    
    # Type Errors
    "TypeError": {
        "title": "Wrong Data Type",
        "message": "An operation was performed on incompatible data types.",
        "action": "Check the types of values being used together.",
        "severity": "medium"
    },
    "ValueError": {
        "title": "Invalid Value",
        "message": "A function received an inappropriate value.",
        "action": "Check the value being passed to the function.",
        "severity": "medium"
    },
    "KeyError": {
        "title": "Missing Dictionary Key",
        "message": "Tried to access a dictionary key that doesn't exist.",
        "action": "Check if the key exists or use .get() method.",
        "severity": "low"
    },
    "IndexError": {
        "title": "List Index Out of Range",
        "message": "Tried to access a position in a list that doesn't exist.",
        "action": "Check the list length before accessing an index.",
        "severity": "low"
    },
    
    # Network Errors
    "ConnectionError": {
        "title": "Connection Failed",
        "message": "Could not connect to a network service.",
        "action": "Check if the service is running and network is available.",
        "severity": "high"
    },
    "TimeoutError": {
        "title": "Request Timed Out",
        "message": "A network request took too long and was cancelled.",
        "action": "Check your internet connection or try again later.",
        "severity": "medium"
    },
    "ConnectionRefusedError": {
        "title": "Connection Refused",
        "message": "The service is not accepting connections.",
        "action": "Make sure the service (like Ollama) is running.",
        "severity": "high"
    },
    "ConnectionResetError": {
        "title": "Connection Reset",
        "message": "The remote server closed the connection unexpectedly.",
        "action": "Try again - this may be a temporary issue.",
        "severity": "medium"
    },
    
    # HTTP Errors
    "HTTPError": {
        "title": "HTTP Request Failed",
        "message": "A web request returned an error response.",
        "action": "Check the URL and try again.",
        "severity": "medium"
    },
    
    # Memory Errors
    "MemoryError": {
        "title": "Out of Memory",
        "message": "The system ran out of available memory.",
        "action": "Close other programs or restart the application.",
        "severity": "critical"
    },
    "RecursionError": {
        "title": "Infinite Loop Detected",
        "message": "A function keeps calling itself forever.",
        "action": "Check for infinite recursion in your code.",
        "severity": "critical"
    },
    
    # Attribute Errors
    "AttributeError": {
        "title": "Object Has No Such Method",
        "message": "Tried to use a function that doesn't exist on an object.",
        "action": "Check the object's available methods.",
        "severity": "medium"
    },
    
    # Runtime Errors
    "RuntimeError": {
        "title": "Runtime Error",
        "message": "An error occurred while the program was running.",
        "action": "Check the error details for more information.",
        "severity": "medium"
    },
    "ZeroDivisionError": {
        "title": "Division by Zero",
        "message": "Tried to divide a number by zero.",
        "action": "Add a check to prevent division by zero.",
        "severity": "medium"
    },
    "OverflowError": {
        "title": "Number Too Large",
        "message": "A number is too big to be handled.",
        "action": "Use a larger data type or check the calculation.",
        "severity": "medium"
    },
    
    # JSON Errors
    "JSONDecodeError": {
        "title": "Invalid JSON",
        "message": "The system received data that isn't in the expected format.",
        "action": "Check that the data is valid JSON.",
        "severity": "medium"
    },
    
    # OS Errors (Windows-specific)
    "OSError": {
        "title": "System Error",
        "message": "An error occurred related to the operating system.",
        "action": "Check system settings and permissions.",
        "severity": "medium"
    },
    "WindowsError": {
        "title": "Windows Error",
        "message": "A Windows-specific error occurred.",
        "action": "Run as administrator or check system settings.",
        "severity": "medium"
    },
}

# Additional context for specific errors
ERROR_CONTEXT: Dict[str, str] = {
    "10061": "The service is not running. Please start Ollama using 'ollama serve'",
    "10060": "Connection timed out. Check your internet connection.",
    "111": "Connection refused. Make sure the service is running.",
    "ECONNREFUSED": "Connection refused. Make sure the service is running.",
    "ETIMEDOUT": "Connection timed out. The service may be busy.",
    "ENOENT": "File or directory not found. Check the path.",
    "EACCES": "Permission denied. Try running as administrator.",
    "ENOTFOUND": "Could not find the server. Check the URL.",
}


# ============================================================================
# TRANSLATION FUNCTIONS
# ============================================================================

def translate_exception(exc: Exception, include_traceback: bool = False) -> Dict[str, Any]:
    """
    Translate a Python exception into human-readable English.
    
    Args:
        exc: The exception object to translate
        include_traceback: Whether to include technical traceback
        
    Returns:
        Dictionary with translated error information
    """
    error_type = type(exc).__name__
    error_message = str(exc)
    
    # Check if we have a mapping for this error type
    if error_type in ERROR_MAPPINGS:
        translation = ERROR_MAPPINGS[error_type]
    else:
        # Generic error response
        translation = {
            "title": "Unknown Error",
            "message": f"An error occurred: {error_message}",
            "action": "Check the error details or try restarting.",
            "severity": "medium"
        }
    
    # Check for specific error codes in the message
    for code, context in ERROR_CONTEXT.items():
        if code in error_message:
            translation["action"] = context
            break
    
    # Check if this is an Ollama-related error
    if "ollama" in error_message.lower() or "11434" in error_message:
        translation["title"] = "Ollama Not Running"
        translation["message"] = "The AI assistant (Ollama) is not available."
        translation["action"] = "Start Ollama by running: ollama serve"
        translation["severity"] = "high"
    
    # Check if this is a FastAPI/backend error
    if "fastapi" in error_message.lower() or "uvicorn" in error_message.lower():
        translation["title"] = "Backend Server Error"
        translation["message"] = "The VOID backend service encountered an error."
        translation["action"] = "Try restarting the VOID backend."
        translation["severity"] = "high"
    
    # Build result
    result = {
        "type": error_type,
        "title": translation["title"],
        "message": translation["message"],
        "action": translation["action"],
        "severity": translation["severity"],
    }
    
    if include_traceback:
        result["traceback"] = traceback.format_exc()
    
    return result


def translate_error_type(error_type: str) -> Dict[str, str]:
    """
    Translate an error type string to human-readable format.
    
    Args:
        error_type: The error type name (e.g., "ConnectionError")
        
    Returns:
        Dictionary with translated error information
    """
    if error_type in ERROR_MAPPINGS:
        return ERROR_MAPPINGS[error_type]
    else:
        return {
            "title": "Unknown Error",
            "message": f"An error of type '{error_type}' occurred.",
            "action": "Check error logs for details.",
            "severity": "medium"
        }


def get_user_friendly_message(error: Any) -> str:
    """
    Get a short, user-friendly error message.
    
    Args:
        error: Exception or error string
        
    Returns:
        Human-readable error message
    """
    if isinstance(error, Exception):
        translated = translate_exception(error)
        return f"{translated['title']}: {translated['message']}"
    elif isinstance(error, str):
        # Try to translate from error string
        for error_type, mapping in ERROR_MAPPINGS.items():
            if error_type.lower() in error.lower():
                return f"{mapping['title']}: {mapping['message']}"
        return error
    else:
        return "An unexpected error occurred."


def format_diagnostics_error(component: str, details: str) -> Dict[str, Any]:
    """
    Format a diagnostics error for user display.
    
    Args:
        component: Name of the component with error
        details: Error details from diagnostics
        
    Returns:
        Formatted error dictionary
    """
    # Map component names to error translations
    component_mappings = {
        "backend": {
            "title": "Backend Service Issue",
            "message": "The VOID backend server is not responding correctly.",
            "action": "Restart the backend server."
        },
        "stt": {
            "title": "Speech Recognition Issue",
            "message": "The voice input feature is not working.",
            "action": "Check microphone permissions and settings."
        },
        "tts": {
            "title": "Voice Output Issue",
            "message": "The text-to-speech feature is not working.",
            "action": "Check audio settings."
        },
        "memory": {
            "title": "Memory Storage Issue",
            "message": "Cannot save or load memory data.",
            "action": "Check file permissions."
        },
        "dependencies": {
            "title": "Missing Dependencies",
            "message": "Some required components are not installed.",
            "action": "Run: pip install -r requirements.txt"
        },
        "tool_modules": {
            "title": "Tool Module Issue",
            "message": "Some VOID tools are not loading properly.",
            "action": "Run diagnostics for more details."
        },
        "internet": {
            "title": "Internet Connection Issue",
            "message": "Cannot connect to the internet.",
            "action": "Check your network connection."
        }
    }
    
    if component in component_mappings:
        result = component_mappings[component].copy()
    else:
        result = {
            "title": f"{component.title()} Issue",
            "message": details,
            "action": "Check system diagnostics."
        }
    
    result["component"] = component
    result["details"] = details
    
    return result


# ============================================================================
# UI ERROR FORMATTING
# ============================================================================

def get_ui_error_response(error: Any) -> Dict[str, Any]:
    """
    Get a formatted error response for UI display.
    
    Args:
        error: Exception, string, or dict
        
    Returns:
        UI-ready error response
    """
    if isinstance(error, Exception):
        translated = translate_exception(error)
        return {
            "reply": f"⚠️ {translated['title']}: {translated['message']}",
            "meta": {
                "error": translated["type"],
                "error_title": translated["title"],
                "error_action": translated["action"],
                "severity": translated["severity"]
            }
        }
    elif isinstance(error, dict):
        # Already formatted error
        return {
            "reply": f"⚠️ {error.get('title', 'Error')}: {error.get('message', 'Unknown error')}",
            "meta": {
                "error": error.get("type", "unknown"),
                "error_title": error.get("title", "Error"),
                "error_action": error.get("action", ""),
                "severity": error.get("severity", "medium")
            }
        }
    else:
        # Plain string
        return {
            "reply": f"⚠️ {error}",
            "meta": {
                "error": "unknown",
                "severity": "medium"
            }
        }


def interpret_error(error_msg: str) -> str:
    """
    Quick error message interpreter - translates common error messages to human-readable format.
    
    Args:
        error_msg: The error message string
        
    Returns:
        Human-readable error explanation
    """
    error_lower = error_msg.lower()
    
    # Regex module error
    if "cannot access local variable 're'" in error_lower or "local variable 're'" in error_lower:
        return (
            "System Error Detected.\n\n"
            "Reason:\n"
            "The Python regex module 're' is being used but was not properly imported.\n\n"
            "Solution:\n"
            "Add 'import re' at the top of the file that uses regex operations."
        )
    
    # Module not found error
    if "modulenotfounderror" in error_lower or "no module named" in error_lower:
        return (
            "System Error Detected.\n\n"
            "Reason:\n"
            "A required Python package is missing.\n\n"
            "Solution:\n"
            "Install the missing package using pip."
        )
    
    # Connection refused
    if "connection refused" in error_lower or "10061" in error_lower:
        return (
            "System Error Detected.\n\n"
            "VOID cannot reach Ollama.\n\n"
            "Solution:\n"
            "Make sure Ollama is running using: ollama serve"
        )
    
    # Connection error
    if "connection" in error_lower and "error" in error_lower:
        return (
            "System Error Detected.\n\n"
            "VOID cannot connect to a service.\n\n"
            "Solution:\n"
            "Check your network connection and ensure the service is running."
        )
    
    # Timeout error
    if "timeout" in error_lower:
        return (
            "System Error Detected.\n\n"
            "A request took too long and timed out.\n\n"
            "Solution:\n"
            "Check your internet connection or try again later."
        )
    
    # Permission denied
    if "permission" in error_lower and "denied" in error_lower:
        return (
            "System Error Detected.\n\n"
            "Access was denied to a resource.\n\n"
            "Solution:\n"
            "Check file permissions or run as administrator."
        )
    
    # File not found
    if "file" in error_lower and "not found" in error_lower:
        return (
            "System Error Detected.\n\n"
            "A required file could not be found.\n\n"
            "Solution:\n"
            "Check if the file path is correct."
        )
    
    # Generic fallback
    return "An unknown system error occurred. Try running diagnostics with 'scan project'."


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    # Test the error interpreter
    import json
    
    # Test with various exceptions
    test_exceptions = [
        ConnectionRefusedError(10061, "Connection refused"),
        FileNotFoundError("test.py"),
        ImportError("No module named 'requests'"),
        TimeoutError(),
        ValueError("invalid value"),
    ]
    
    print("VOID Error Interpreter Test")
    print("=" * 50)
    
    for exc in test_exceptions:
        result = translate_exception(exc)
        print(f"\nOriginal: {type(exc).__name__}: {exc}")
        print(f"Translated: {result['title']}")
        print(f"Message: {result['message']}")
        print(f"Action: {result['action']}")

