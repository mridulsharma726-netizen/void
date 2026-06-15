import logging
import threading
import subprocess
import tempfile
import os
import asyncio
import shutil
import re
from typing import Optional

logger = logging.getLogger("void.tts")

_FFPLAY_HARDCODED = r"C:\Users\HP\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffplay.exe"
FFPLAY_PATH = shutil.which("ffplay") or (_FFPLAY_HARDCODED if os.path.exists(_FFPLAY_HARDCODED) else None)
VOICE = "en-US-GuyNeural"  # Default neural voice

# Global process and locks
_ffplay_process: Optional[subprocess.Popen] = None
_process_lock = threading.Lock()
_speak_thread: Optional[threading.Thread] = None
_is_speaking = threading.Event()
_stop_flag = threading.Event()

# Session ID lock and counter to prevent overlapping speech
_speech_session_id = 0
_session_lock = threading.Lock()

# Fallback pyttsx3 engine
_fallback_engine = None
_fallback_lock = threading.Lock()

def _get_fallback_engine():
    global _fallback_engine
    if _fallback_engine is None:
        import pyttsx3
        _fallback_engine = pyttsx3.init()
        _fallback_engine.setProperty("rate", 180)
    return _fallback_engine


def clean_text_for_speech(text: str) -> str:
    if not text:
        return ""
    
    # 1. Replace code blocks (e.g. ```python ... ```)
    text = re.sub(r'```[\s\S]*?```', ' Code block displayed on screen. ', text)
    
    # 2. Replace markdown links [Anchor Text](URL) with just Anchor Text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # 3. Replace mathematical arrows/symbols with friendly equivalents
    text = text.replace(r'$\rightarrow$', ' to ')
    text = text.replace(r'\rightarrow', ' to ')
    text = text.replace('->', ' to ')
    
    # 4. Remove other markdown structures:
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'(?m)^#+\s+', '', text)
    text = re.sub(r'(?m)^\s*[-*+]\s+', ', ', text)
    text = re.sub(r'(?m)^\s*\d+[\.)]\s+', ', ', text)
    
    # Process newlines into sentence/paragraph pauses (commas)
    cleaned_lines = []
    for line in text.split('\n'):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if line_stripped[-1] not in '.!?,:;-':
            line_stripped += ','
        cleaned_lines.append(line_stripped)
    text = ' '.join(cleaned_lines)

    # 5. Remove common emojis and non-speech symbols
    emoji_pattern = re.compile(
        "["
        "\U00010000-\U0010FFFF"  # Emoji ranges
        "\u2600-\u27BF"          # Misc Symbols & Dingbats
        "\u2300-\u23FF"          # Miscellaneous Technical
        "\u2B50"                 # Medium White Star
        "\u2B06"                 # Upwards Black Arrow
        "\u2190-\u21FF"          # Arrows
        "\ufe00-\ufe0f"          # Variant selectors
        "]+", flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    
    common_ui_symbols = ["🔓", "🔒", "🤖", "⚠️", "✅", "❌", "🔧", "💻", "💥", "🚀", "💡", "📅", "✉️", "🔍", "⚙️", "📈", "📉", "🛡️"]
    for sym in common_ui_symbols:
        text = text.replace(sym, "")
    text = text.replace('\ufe0f', '')  # Explicit secondary strip
    
    # 6. Clean up whitespace and punctuation flow
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*,\s*,+', ',', text)
    text = re.sub(r'\s*\.\s*\.+', '.', text)
    text = re.sub(r'\s+([,.\!\?])', r'\1', text)
    text = text.lstrip(', ')
    
    return text.strip()


def speak(text: str) -> dict:
    if not text or not text.strip():
        return {"status": "error", "message": "Empty text", "status_code": "FAIL"}

    cleaned = clean_text_for_speech(text)
    if not cleaned or not cleaned.strip():
        logger.warning(f"TTS skipped: text became empty after cleaning. Original: {text}")
        return {"status": "ok", "message": "Nothing to speak after cleaning", "status_code": "OK"}

    try:
        stop_speaking()
        _stop_flag.clear()

        global _speech_session_id
        with _session_lock:
            _speech_session_id += 1
            current_session = _speech_session_id

        def _runner(session_id: int) -> None:
            global _ffplay_process
            
            with _session_lock:
                if session_id != _speech_session_id:
                    return
                    
            _is_speaking.set()

            edge_tts_success = False
            temp_wav = None
            try:
                # Try edge-tts first
                try:
                    import edge_tts

                    # Setup temp wav path
                    temp_dir = tempfile.gettempdir()
                    temp_wav = os.path.join(temp_dir, f"void_tts_{os.getpid()}_{session_id}.wav")

                    # Generate wav synchronously
                    async def _generate():
                        communicate = edge_tts.Communicate(cleaned, VOICE)
                        await communicate.save(temp_wav)

                    # Run in a new event loop
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(_generate())
                    finally:
                        loop.close()

                    with _session_lock:
                        if session_id != _speech_session_id:
                            return

                    # Verify file generated
                    if os.path.exists(temp_wav) and os.path.getsize(temp_wav) > 0:
                        edge_tts_success = True

                except Exception as e:
                    logger.warning("edge-tts generation failed: %s. Falling back to pyttsx3.", e)

                if edge_tts_success and FFPLAY_PATH and os.path.exists(FFPLAY_PATH):
                    try:
                        # Spawn ffplay subprocess
                        with _session_lock:
                            if session_id != _speech_session_id:
                                return
                                
                        proc = None
                        with _process_lock:
                            if not _stop_flag.is_set():
                                _ffplay_process = subprocess.Popen(
                                    [FFPLAY_PATH, "-nodisp", "-autoexit", temp_wav],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL
                                )
                                proc = _ffplay_process

                        if proc:
                            proc.wait()
                    except Exception as e:
                        logger.error("ffplay execution failed: %s. Falling back to pyttsx3.", e)
                        edge_tts_success = False
                    finally:
                        with _process_lock:
                            _ffplay_process = None
                else:
                    edge_tts_success = False

                # Fallback to pyttsx3 if edge-tts/ffplay failed
                if not edge_tts_success:
                    try:
                        with _session_lock:
                            if session_id != _speech_session_id:
                                return
                        with _fallback_lock:
                            engine = _get_fallback_engine()
                            engine.say(cleaned)
                            if not _stop_flag.is_set():
                                engine.runAndWait()
                    except Exception as exc:
                        logger.exception("Fallback pyttsx3 runtime failed: %s", exc)

            finally:
                # Clean up temp file
                try:
                    if temp_wav and os.path.exists(temp_wav):
                        os.remove(temp_wav)
                except Exception:
                    pass
                # Always clear speaking flag on exit if session matches
                with _session_lock:
                    if session_id == _speech_session_id:
                        _is_speaking.clear()

        global _speak_thread
        _speak_thread = threading.Thread(target=_runner, args=(current_session,), daemon=True)
        _speak_thread.start()
        logger.info("TTS started")
        return {"status": "ok", "message": "Speaking", "status_code": "OK"}
    except Exception as e:
        logger.exception("TTS start failed: %s", e)
        return {"status": "error", "message": str(e), "status_code": "FAIL"}


def speak_async(text: str) -> dict:
    """
    Alias for speak() - for backward compatibility.
    """
    return speak(text)


def stop_speaking() -> dict:
    try:
        _stop_flag.set()

        # Kill ffplay subprocess if active
        with _process_lock:
            global _ffplay_process
            if _ffplay_process:
                try:
                    _ffplay_process.kill()
                except Exception:
                    pass
                _ffplay_process = None

        # Also stop fallback pyttsx3 engine
        try:
            if _fallback_engine is not None:
                with _fallback_lock:
                    _fallback_engine.stop()
        except Exception:
            pass

        _is_speaking.clear()
        logger.info("TTS stopped")
        return {"status": "ok", "message": "Stopped", "status_code": "OK"}
    except Exception as exc:
        logger.exception("TTS stop failed: %s", exc)
        return {"status": "error", "message": str(exc), "status_code": "FAIL"}


def is_speaking() -> bool:
    return _is_speaking.is_set()


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


def speak_text(text: str) -> dict:
    return speak(text)


def stop() -> dict:
    return stop_speaking()


logger.info("[VOID TTS] Module loaded")
