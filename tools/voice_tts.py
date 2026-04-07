"""
VOID TTS (Text-to-Speech) Module
Subprocess-based implementation for stable Windows TTS.
"""

import subprocess
import sys
import os


def speak(text: str) -> dict:
    """
    Speak text using a subprocess to avoid Windows COM threading issues.
    
    Args:
        text: String to speak
        
    Returns:
        dict: {"status": "ok"|"error", "message": "..."}
    """
    if not text or not text.strip():
        return {"status": "error", "message": "Empty text"}

    try:
        script_path = os.path.join(
            os.path.dirname(__file__),
            "tts_speaker.py"
        )

        # Spawn subprocess to run TTS
        subprocess.Popen(
            [sys.executable, script_path, text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        print("[TTS START]", text[:60])

        return {"status": "ok", "message": "Speaking"}

    except Exception as e:
        print("[TTS ERROR]", str(e))
        return {"status": "error", "message": str(e)}


def speak_async(text: str) -> dict:
    """
    Alias for speak() - for backward compatibility.
    """
    return speak(text)


def stop_speaking() -> dict:
    """
    Stop TTS (subprocesses can't be easily stopped, but we return OK).
    
    Returns:
        dict: {"status": "ok"|"error", "message": "..."}
    """
    return {"status": "ok", "message": "Stop not implemented for subprocess TTS"}


def is_speaking() -> bool:
    """
    Check if TTS is currently speaking.
    Note: With subprocess approach, this always returns False.
    """
    return False


class VoiceTTS:
    """
    VoiceTTS class for backward compatibility.
    """
    
    def speak(self, text: str) -> dict:
        """Speak text."""
        return speak(text)
    
    def stop(self) -> dict:
        """Stop speaking."""
        return stop_speaking()
    
    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return is_speaking()


# ========================================
# CONVENIENCE FUNCTIONS
# ========================================
def speak_text(text: str) -> dict:
    """Alias for speak()."""
    return speak(text)


def stop() -> dict:
    """Alias for stop_speaking()."""
    return stop_speaking()


# ========================================
# INITIALIZE ON MODULE LOAD
# ========================================
print("[VOID TTS] Module loaded, subprocess TTS ready")

