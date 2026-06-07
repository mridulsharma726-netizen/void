"""
VOID Wake Word Detector
====================

Continuously listens for the wake word "VOID" to activate hands-free voice control.

Functions:
- listen_for_wake_word() -> bool
- set_wake_word(word: str)
- get_wake_word() -> str
- stop()
"""

import time
import logging
import threading
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

_running = False
_running_lock = threading.Lock()

# Cached recognizer & microphone
_recognizer = None
_microphone = None
_init_lock = threading.Lock()
_calibrated = False


def _init_sr():
    global _recognizer, _microphone, _calibrated
    with _init_lock:
        if _recognizer is None:
            try:
                import speech_recognition as sr
                from tools.voice_stt import get_best_microphone_index
                _recognizer = sr.Recognizer()
                _recognizer.energy_threshold = ENERGY_THRESHOLD
                idx = get_best_microphone_index()
                _microphone = sr.Microphone(device_index=idx)
                logger.info(f"[WAKE WORD] Initialized SpeechRecognition recognizer and microphone with index {idx}")
            except Exception as e:
                logger.error("[WAKE WORD] Init failed: %s", e)

        if _recognizer is not None and not _calibrated and _microphone is not None:
            try:
                logger.info("[WAKE WORD] Calibrating for ambient noise...")
                with _microphone as source:
                    _recognizer.adjust_for_ambient_noise(source, duration=0.5)
                _calibrated = True
                logger.info("[WAKE WORD] Calibration complete")
            except Exception as e:
                logger.warning("[WAKE WORD] Noise calibration failed: %s", e)


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


def stop():
    """Stop the wake word detection loop."""
    global _running
    with _running_lock:
        _running = False
    logger.info("Wake word detection stop requested")


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
    global _running
    with _running_lock:
        _running = True

    try:
        import speech_recognition as sr
    except ImportError:
        logger.error("speech_recognition not installed")
        return False

    _init_sr()
    if _recognizer is None or _microphone is None:
        logger.error("[WAKE WORD] Recognizer or microphone not available")
        return False

    logger.info(f"Listening for wake word '{WAKE_WORD}'...")
    start_time = time.time()

    while True:
        with _running_lock:
            if not _running:
                logger.info("Wake word detection stopped programmatically")
                return False

        # Check timeout
        if timeout and (time.time() - start_time) > timeout:
            logger.info("Wake word listen timed out")
            return False

        try:
            with _microphone as source:
                # listen with small timeout to regularly check _running flag
                audio = _recognizer.listen(
                    source, 
                    phrase_time_limit=phrase_time_limit,
                    timeout=1
                )

            # Offline-first wake word detection
            text = ""
            try:
                text_raw = _recognizer.recognize_vosk(audio)
                import json
                try:
                    res_dict = json.loads(text_raw)
                    text = res_dict.get("text", text_raw).strip().lower()
                except Exception:
                    text = text_raw.strip().lower()
            except Exception:
                # Fallback to Google online recognition
                try:
                    text = _recognizer.recognize_google(audio).lower()
                except Exception:
                    pass

            if text:
                logger.info(f"[WAKE WORD] Heard: {text}")
                if _check_for_wake_word(text):
                    logger.info(f"Wake word '{WAKE_WORD}' detected!")
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
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Wake word loop error: {e}")
            time.sleep(0.5)

    return False


def listen_loop() -> bool:
    """
    Infinite loop listening for wake word.
    Returns only on error or interrupt.
    """
    logger.info("Starting wake word listening loop...")
    global _running
    with _running_lock:
        _running = True

    while True:
        with _running_lock:
            if not _running:
                break
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
    return False


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
        _init_sr()
        if _recognizer is None:
            return False
        
        # Try local first
        try:
            text_raw = _recognizer.recognize_vosk(audio_data)
            import json
            res_dict = json.loads(text_raw)
            text = res_dict.get("text", text_raw).strip().lower()
        except Exception:
            text = _recognizer.recognize_google(audio_data).lower()
            
        return _check_for_wake_word(text)
    except Exception:
        return False
