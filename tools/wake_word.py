"""
VOID Wake Word Detector
====================

Continuously listens for the wake word "VOID" to activate hands-free voice control.

Functions:
- listen_for_wake_word() -> bool
- set_wake_word(word: str)
- get_wake_word() -> str
"""

import time
import logging
from typing import Optional, Callable

# Configure logging
logger = logging.getLogger("VOID-WakeWord")

# Default wake word
WAKE_WORD = "void"

# Recognition settings
PHRASE_TIME_LIMIT = 3  # seconds
ENERGY_THRESHOLD = 300  # minimum audio energy to register as speech

# Callback for wake word detection
_wake_callback: Optional[Callable[[], None]] = None


def set_wake_word(word: str):
    """Set the wake word."""
    global WAKE_WORD
    WAKE_WORD = word.lower().strip()
    logger.info(f"Wake word set to: {WAKE_WORD}")


def get_wake_word() -> str:
    """Get current wake word."""
    return WAKE_WORD


def set_wake_callback(callback: Callable[[], None]):
    """Set callback function to run when wake word is detected."""
    global _wake_callback
    _wake_callback = callback


def _check_for_wake_word(text: str) -> bool:
    """Check if text contains wake word."""
    if not text:
        return False
    return WAKE_WORD in text.lower()


def listen_for_wake_word(timeout: Optional[float] = None, 
                        phrase_time_limit: int = PHRASE_TIME_LIMIT) -> bool:
    """
    Listen for the wake word once.
    
    Args:
        timeout: Maximum time to listen (None = infinite)
        phrase_time_limit: Max duration of speech to capture
        
    Returns:
        True if wake word detected
    """
    try:
        import speech_recognition as sr
        
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()
        
        logger.info("Adjusting for ambient noise...")
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
        
        logger.info(f"Listening for wake word '{WAKE_WORD}'...")
        
        start_time = time.time()
        
        while True:
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                logger.info("Wake word listen timed out")
                return False
            
            try:
                with microphone as source:
                    audio = recognizer.listen(
                        source, 
                        phrase_time_limit=phrase_time_limit,
                        timeout=1
                    )
                
                # Try to recognize
                text = recognizer.recognize_google(audio).lower()
                logger.debug(f"Heard: {text}")
                
                if _check_for_wake_word(text):
                    logger.info(f"Wake word '{WAKE_WORD}' detected!")
                    
                    # Run callback if set
                    if _wake_callback:
                        try:
                            _wake_callback()
                        except Exception as e:
                            logger.error(f"Wake callback error: {e}")
                    
                    return True
                    
            except sr.WaitTimeoutError:
                # No speech detected, continue listening
                continue
            except sr.UnknownValueError:
                # Could not understand audio
                continue
            except sr.RequestError as e:
                logger.error(f"Recognition error: {e}")
                # Small delay before retry
                time.sleep(0.5)
                
    except ImportError:
        logger.error("speech_recognition not installed")
        return False
    except Exception as e:
        logger.error(f"Wake word error: {e}")
        return False


def listen_loop() -> bool:
    """
    Infinite loop listening for wake word.
    Returns only on error or interrupt.
    """
    logger.info("Starting wake word listening loop...")
    
    while True:
        try:
            result = listen_for_wake_word()
            if result:
                return True
        except KeyboardInterrupt:
            logger.info("Wake word loop interrupted")
            return False
        except Exception as e:
            logger.error(f"Wake word loop error: {e}")
            time.sleep(1)


def detect_wake_word_from_audio(audio_data) -> bool:
    """
    Detect wake word from already captured audio.
    
    Args:
        audio_data: Audio data to analyze
        
    Returns:
        True if wake word detected
    """
    try:
        import speech_recognition as sr
        
        recognizer = sr.Recognizer()
        text = recognizer.recognize_google(audio_data).lower()
        
        return _check_for_wake_word(text)
        
    except Exception:
        return False


if __name__ == "__main__":
    # Test wake word detection
    print("Testing wake word detection...")
    print("Say the wake word to activate")
    
    result = listen_for_wake_word(timeout=30)
    
    if result:
        print("WAKE WORD DETECTED!")
    else:
        print("Timeout - no wake word detected")

