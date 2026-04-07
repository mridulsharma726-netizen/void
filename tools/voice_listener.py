"""
VOID Voice Listener
================

Continuous voice loop that waits for wake word, then captures commands.

Functions:
- start_voice_loop() -> Optional[str]
- stop_voice_loop()
- is_listening() -> bool
- set_activation_phrase(phrase: str)
"""

import time
import threading
import logging
from typing import Optional, Callable

# Configure logging
logger = logging.getLogger("VOID-VoiceListener")

# State
_listening = False
_running = False
_activation_phrase = "activated"
_command_callback: Optional[Callable[[str], None]] = None


def set_activation_phrase(phrase: str):
    """Set the phrase VOID says when activated."""
    global _activation_phrase
    _activation_phrase = phrase


def set_command_callback(callback: Callable[[str], None]):
    """Set callback for when command is captured."""
    global _command_callback
    _command_callback = callback


def is_listening() -> bool:
    """Check if voice loop is active."""
    return _listening


def stop_voice_loop():
    """Stop the voice loop."""
    global _running, _listening
    _running = False
    _listening = False
    logger.info("Voice loop stop requested")


def _speak(text: str):
    """Speak text using TTS if available."""
    try:
        from tools.voice_tts import speak
        speak(text)
    except Exception as e:
        logger.warning(f"TTS not available: {e}")


def start_voice_loop() -> Optional[str]:
    """
    Start the voice loop - waits for wake word, then captures command.
    
    This is a blocking function that runs until wake word detected
    and command captured, or loop is stopped.
    
    Returns:
        Captured command text, or None if stopped
    """
    global _listening, _running
    
    if _listening:
        logger.warning("Voice loop already running")
        return None
    
    _running = True
    _listening = True
    
    logger.info("[VOICE LOOP] Starting...")
    
    try:
        from tools.wake_word import listen_for_wake_word
        logger.info("[VOICE LOOP] Wake word detector ready")
    except ImportError:
        logger.error("[VOICE LOOP] Wake word module not available")
        _listening = False
        return None
    
    while _running:
        if not _running:
            break
            
        logger.info("[VOICE LOOP] Waiting for wake word...")
        
        # Listen for wake word (with timeout to allow checking _running)
        wake_detected = listen_for_wake_word(timeout=10)
        
        if not _running:
            break
            
        if wake_detected:
            logger.info("[VOICE LOOP] Wake word detected!")
            
            # Optional: speak activation phrase
            if _activation_phrase:
                _speak(_activation_phrase)
            
            # Now listen for the actual command
            try:
                from tools.voice_stt import VoiceSTT
                
                stt = VoiceSTT()
                logger.info("[VOICE LOOP] Listening for command...")
                
                # Listen with reasonable timeout
                result = stt.listen_once(timeout=5, phrase_time_limit=6)
                
                if isinstance(result, dict):
                    command = result.get("text", "")
                else:
                    command = result
                
                if command and command.strip():
                    logger.info(f"[VOICE LOOP] Captured: {command}")
                    
                    # Run callback if set
                    if _command_callback:
                        _command_callback(command)
                    
                    _listening = False
                    return command.strip()
                else:
                    logger.info("[VOICE LOOP] No command captured")
                    
            except Exception as e:
                logger.error(f"[VOICE LOOP] Command listen error: {e}")
        
        # Small delay before retry
        time.sleep(0.5)
    
    _listening = False
    logger.info("[VOICE LOOP] Stopped")
    return None


def start_voice_loop_thread() -> threading.Thread:
    """
    Start voice loop in a background thread.
    
    Returns:
        The thread object
    """
    thread = threading.Thread(
        target=voice_loop_wrapper,
        daemon=True,
        name="VOID-VoiceLoop"
    )
    thread.start()
    logger.info("[VOICE LOOP] Started in background thread")
    return thread


def voice_loop_wrapper():
    """
    Wrapper for voice loop that handles continuous operation.
    """
    global _running
    
    logger.info("[VOICE LOOP] Wrapper starting...")
    
    while _running:
        try:
            command = start_voice_loop()
            
            if command:
                logger.info(f"[VOICE LOOP] Got command: {command}")
                
                # Small delay before listening again
                time.sleep(1)
            else:
                # Loop was stopped or interrupted
                if not _running:
                    break
                # Otherwise continue listening
                time.sleep(0.5)
                
        except Exception as e:
            logger.error(f"[VOICE LOOP] Wrapper error: {e}")
            time.sleep(1)
    
    logger.info("[VOICE LOOP] Wrapper ended")


# Alternative: single command capture mode
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
        from tools.voice_stt import VoiceSTT
        
        stt = VoiceSTT()
        result = stt.listen_once(timeout=timeout, phrase_time_limit=phrase_time_limit)
        
        if isinstance(result, dict):
            return result.get("text", "").strip()
        elif result:
            return str(result).strip()
        
        return None
        
    except Exception as e:
        logger.error(f"Listen for command error: {e}")
        return None


def activate_and_listen() -> Optional[str]:
    """
    Single activation: wake word + command.
    Blocks until command captured or timeout.
    
    Returns:
        Command text or None
    """
    # First listen for wake word
    from tools.wake_word import listen_for_wake_word
    
    wake_detected = listen_for_wake_word(timeout=15)
    
    if not wake_detected:
        return None
    
    # Got wake word, now listen for command
    _speak(_activation_phrase)
    
    return listen_for_command()


if __name__ == "__main__":
    # Test voice loop
    print("Testing voice listener...")
    print("Say 'VOID' to activate, then give a command")
    
    # Set activation phrase
    set_activation_phrase("Yes?")
    
    # Start listening
    command = start_voice_loop()
    
    if command:
        print(f"Captured command: {command}")
    else:
        print("No command captured")

