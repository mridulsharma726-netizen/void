"""
VOID Voice Listener Adapter
===========================

Continuous voice loop using the new unified core VoicePipeline.
Provides a backward-compatible interface for the FastAPI backend and test suites.
"""

import time
import threading
import logging
from typing import Optional, Callable
from core.voice_ai.voice_pipeline import get_voice_pipeline

# Configure logging
logger = logging.getLogger("VOID-VoiceListener")

# State
_running = False
_listening = False
_activation_phrase = "Yes?"
_command_callback: Optional[Callable[[str], None]] = None
_state_lock = threading.Lock()
_pipeline = None

def set_activation_phrase(phrase: str):
    """Set the phrase VOID says when activated."""
    global _activation_phrase
    with _state_lock:
        _activation_phrase = phrase
    logger.info(f"Activation phrase set to: {phrase}")

def set_command_callback(callback: Callable[[str], None]):
    """Set callback for when command is captured."""
    global _command_callback
    with _state_lock:
        _command_callback = callback
    # Also update pipeline callback
    pipeline = get_voice_pipeline()
    pipeline.command_handler = callback

def is_listening() -> bool:
    """Check if voice loop is active."""
    with _state_lock:
        return _listening

def stop_voice_loop():
    """Stop the voice loop."""
    global _running, _listening
    with _state_lock:
        _running = False
        _listening = False
        
    try:
        pipeline = get_voice_pipeline()
        pipeline.stop()
    except Exception as e:
        logger.warning(f"Error stopping voice pipeline: {e}")
        
    logger.info("Voice loop stop requested")

def _speak(text: str):
    """Speak text using pipeline."""
    try:
        pipeline = get_voice_pipeline()
        pipeline.speak(text)
    except Exception as e:
        logger.warning(f"TTS speak failed: {e}")

def start_voice_loop() -> Optional[str]:
    """
    Start the voice loop - waits for wake word, then captures command.
    Fallback wrapper for tests.
    """
    global _listening, _running
    with _state_lock:
        if _listening:
            logger.warning("Voice loop already running")
            return None
        _running = True
        _listening = True
        
    logger.info("[VOICE LOOP] Starting voice loop using new VoicePipeline...")
    
    try:
        pipeline = get_voice_pipeline()
        # Feed callback
        def pipe_cb(cmd):
            global _command_callback
            if _command_callback:
                _command_callback(cmd)
                
        pipeline.command_handler = pipe_cb
        pipeline.start(wake_phrase="hey_jarvis")  # Map to openWakeWord hey_jarvis model
        
        # Keep loop alive until stopped
        while True:
            with _state_lock:
                if not _running:
                    break
            time.sleep(0.5)
            
    except Exception as e:
        logger.error(f"[VOICE LOOP] Failed initializing voice pipeline: {e}. Degrading to text-only mode.")
        stop_voice_loop()
    finally:
        with _state_lock:
            _listening = False
            
    return None

def start_voice_loop_thread() -> threading.Thread:
    """Start voice loop in a background thread."""
    global _running
    with _state_lock:
        _running = True
    thread = threading.Thread(
        target=voice_loop_wrapper,
        daemon=True,
        name="VOID-VoiceLoop"
    )
    thread.start()
    logger.info("[VOICE LOOP] Started in background thread")
    return thread

def voice_loop_wrapper():
    """Wrapper for voice loop that handles continuous operation."""
    logger.info("[VOICE LOOP] Wrapper starting...")
    try:
        start_voice_loop()
    except Exception as e:
        logger.error(f"[VOICE LOOP] Wrapper encountered fatal error: {e}. Voice disabled.")

def listen_for_command(timeout: int = 5, phrase_time_limit: int = 6) -> Optional[str]:
    """
    Listen for a single voice command (without wake word).
    
    Args:
        timeout: Max seconds to wait for speech
        phrase_time_limit: Max seconds of speech to capture
        
    Returns:
        Command text or None
    """
    try:
        from tools.voice_stt import listen_once
        result = listen_once(timeout=timeout, phrase_time_limit=phrase_time_limit)

        if isinstance(result, dict):
            return result.get("text", "").strip()
        elif result:
            return str(result).strip()

        return None

    except Exception as e:
        logger.error(f"Listen for command error: {e}")
        return None
