"""
VOID Advanced Speech-to-Text (STT) Module
==========================================

Features:
- Non-blocking, queue-based audio streams using `sounddevice` or `pyaudio`.
- Async-compatible listening queue.
- Automatic offline Vosk acoustic model download and extraction.
- **Feedback Suppression Loop**: Discards audio input when VOID is speaking to prevent self-hearing loops.
- Resilient online SpeechRecognition (Google API) fallbacks.
"""

import os
import sys
import json
import time
import queue
import logging
import urllib.request
import zipfile
import threading
import asyncio
import struct
import math
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("void.stt")

# Project paths
ROOT_DIR = Path(__file__).parent.parent
MODEL_DIR = ROOT_DIR / "memory" / "data" / "models"
VOSK_MODEL_PATH = MODEL_DIR / "vosk-model-small-en-us-0.15"
MODEL_ZIP_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"

# Library availability flags
SOUNDDEVICE_AVAILABLE = False
PYAUDIO_AVAILABLE = False
VOSK_AVAILABLE = False
SR_AVAILABLE = False

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    pass

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    pass

try:
    import vosk
    VOSK_AVAILABLE = True
except ImportError:
    pass

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    pass


# ==================== AUTO-DOWNLOAD SYSTEM ====================

_downloading_event = threading.Event()

def _download_and_extract_model():
    """Background thread worker to download and unzip Vosk small model."""
    if _downloading_event.is_set():
        return
    _downloading_event.set()
    
    try:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = MODEL_DIR / "vosk_model.zip"
        
        logger.info(f"[VOSK DOWNLOAD] Starting download of Vosk Model: {MODEL_ZIP_URL}")
        
        # Download stream with chunk status updates
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)
        
        # Pull file
        urllib.request.urlretrieve(MODEL_ZIP_URL, str(zip_path))
        logger.info("[VOSK DOWNLOAD] Complete. Unzipping model...")
        
        # Extract
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(str(MODEL_DIR))
            
        # Clean up zip
        if zip_path.exists():
            os.remove(zip_path)
            
        logger.info(f"[VOSK] Acoustic Model successfully deployed to: {VOSK_MODEL_PATH}")
    except Exception as e:
        logger.error(f"[VOSK DOWNLOAD ERROR] Model setup failed: {e}", exc_info=True)
    finally:
        _downloading_event.clear()

def ensure_vosk_model():
    """Trigger background download if model folder is missing."""
    if not VOSK_MODEL_PATH.exists():
        if not _downloading_event.is_set():
            download_thread = threading.Thread(target=_download_and_extract_model, daemon=True)
            download_thread.start()
            return False
    return VOSK_MODEL_PATH.exists()


def get_best_microphone_index() -> Optional[int]:
    """
    Scans PyAudio/sounddevice and attempts to find a working microphone.
    Returns the index or None to use system default.
    """
    if PYAUDIO_AVAILABLE:
        try:
            p = pyaudio.PyAudio()
            try:
                default_info = p.get_default_input_device_info()
                logger.info(f"[STT] Default mic info: {default_info.get('name')}")
                return default_info.get('index')
            except Exception as e:
                logger.debug(f"[STT] Could not get default PyAudio device: {e}")
                # Iterate and find first working input device
                for i in range(p.get_device_count()):
                    try:
                        dev_info = p.get_device_info_by_index(i)
                        if dev_info.get('maxInputChannels', 0) > 0:
                            logger.info(f"[STT] Found mic info: {dev_info.get('name')} at index {i}")
                            return i
                    except Exception as e:
                        logger.debug(f"[STT] Failed checking PyAudio device info at index {i}: {e}")
            finally:
                p.terminate()
        except Exception as e:
            logger.warning(f"Error checking PyAudio devices: {e}")
            
    if SOUNDDEVICE_AVAILABLE:
        try:
            devices = sd.query_devices()
            default_input = sd.default.device[0]
            if default_input != -1:
                return default_input
            for idx, dev in enumerate(devices):
                if dev.get('max_input_channels', 0) > 0:
                    return idx
        except Exception as e:
            logger.warning(f"Error checking sounddevice devices: {e}")

    return None


# ==================== VOICE INTERRUPT & STATE HELPERS ====================

def is_tts_speaking() -> bool:
    """Safe check to verify if the Text-to-Speech engine is speaking."""
    try:
        from tools.voice_tts import is_speaking
        return is_speaking()
    except Exception as e:
        logger.debug(f"[STT] is_tts_speaking check failed: {e}")
        return False

def stop_tts_speaking():
    """Immediately stop TTS speech to handle interruptions."""
    try:
        from tools.voice_tts import stop_speaking
        stop_speaking()
    except Exception as e:
        logger.debug(f"[STT] stop_tts_speaking check failed: {e}")


# ==================== QUEUE-BASED AUDIO INPUT STREAM ====================

class VoiceSTT:
    """
    Advanced queue-based Speech-to-Text Engine.
    Exposes non-blocking callbacks, async listeners, and feedback guards.
    """
    _instance = None
    _recognizer = None
    _model = None
    _audio_queue = queue.Queue()
    _listening_thread = None
    _running = False
    _current_rms = 0.0
    _lock = threading.Lock()
    _sr_recognizer = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
        
    def __init__(self):
        if self._recognizer is None:
            self._init()

    def _init(self):
        logger.info("[VOID STT] Initializing audio subsystems...")
        ensure_vosk_model()
        
        if VOSK_AVAILABLE and VOSK_MODEL_PATH.exists():
            try:
                self._model = vosk.Model(str(VOSK_MODEL_PATH))
                self._recognizer = vosk.KaldiRecognizer(self._model, 16000)
                logger.info("[VOID STT READY] Local offline Vosk engine active.")
            except Exception as e:
                logger.error(f"[STT INIT ERROR] Failed loading Vosk model: {e}")
                
        # Initialize SpeechRecognition as a secondary online parser
        if SR_AVAILABLE:
            try:
                self._sr_recognizer = sr.Recognizer()
                logger.info("[VOID STT] SpeechRecognition online engine active.")
            except Exception as e:
                logger.error(f"[STT INIT ERROR] Failed loading SpeechRecognition: {e}")

    def start_listening_loop(self):
        """Spawns non-blocking background audio listener stream."""
        if self._running:
            return
        
        self._running = True
        self._listening_thread = threading.Thread(target=self._stream_capture_loop, daemon=True)
        self._listening_thread.start()
        logger.info("[VOID STT] Background recording loop spawned.")

    def stop_listening_loop(self):
        """Stop background recorder."""
        self._running = False
        if self._listening_thread:
            self._listening_thread.join(timeout=1.0)
            self._listening_thread = None
        self._current_rms = 0.0
        logger.info("[VOID STT] Background recording loop stopped.")

    def get_mic_level(self) -> float:
        """Returns the current RMS level (0-32768 range)."""
        if not self._running:
            return 0.0
        return self._current_rms

    def get_mic_status(self) -> dict:
        """Returns microphone active status, raw RMS, and scaled level percentage."""
        active = self._running
        rms = self.get_mic_level()
        level_pct = min(100.0, (rms / 32768.0) * 100.0)
        return {
            "active": active,
            "rms": rms,
            "level_pct": level_pct
        }

    def _stream_capture_loop(self):
        """Captures micro-buffers using sounddevice callbacks in a raw queue thread."""
        if not SOUNDDEVICE_AVAILABLE:
            logger.warning("[STT] sounddevice library not installed. Falling back to PyAudio.")
            self._stream_capture_pyaudio()
            return
            
        def audio_callback(indata, frames, time, status):
            if status:
                logger.warning(f"[STT callback status] {status}")
            
            raw_bytes = bytes(indata)
            
            # Calculate RMS loudness to support voice interruption
            rms = 0
            count = len(raw_bytes) // 2
            if count > 0:
                try:
                    samples = struct.unpack(f"{count}h", raw_bytes)
                    sum_squares = sum(s * s for s in samples)
                    rms = math.sqrt(sum_squares / count)
                except Exception as e:
                    logger.debug(f"Error calculating RMS: {e}")

            # Update current RMS level
            self._current_rms = rms

            # --- FEEDBACK SUPPRESSION / INTERRUPT LOOP ---
            if is_tts_speaking():
                # If user speaks loudly (RMS > 3000), execute voice interrupt
                if rms > 3000:
                    logger.info(f"[VOICE INTERRUPT] Loud speech detected (RMS: {rms:.1f}). Stopping assistant speech.")
                    stop_tts_speaking()
                    # Clear the queue to discard old feedback remnants
                    while not self._audio_queue.empty():
                        try:
                            self._audio_queue.get_nowait()
                        except Exception as e:
                            logger.debug(f"[VOICE INTERRUPT] Error clearing queue: {e}")
                            break
                    # Enqueue this segment as the start of user command
                    self._audio_queue.put(raw_bytes)
                return
                
            self._audio_queue.put(raw_bytes)
            
        try:
            with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16', 
                                   channels=1, callback=audio_callback):
                while self._running:
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"[STT AUDIO RUNTIME ERROR] sounddevice stream failed: {e}")
            # Try PyAudio fallback
            self._stream_capture_pyaudio()

    def _stream_capture_pyaudio(self):
        """Alternative stream capture utilizing PyAudio if sounddevice fails."""
        if not PYAUDIO_AVAILABLE:
            logger.error("[STT] Neither sounddevice nor PyAudio are available.")
            return
            
        try:
            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                            input=True, frames_per_buffer=8000)
                            
            while self._running:
                try:
                    data = stream.read(8000, exception_on_overflow=False)
                    
                    # Calculate RMS loudness
                    rms = 0
                    count = len(data) // 2
                    if count > 0:
                        try:
                            samples = struct.unpack(f"{count}h", data)
                            sum_squares = sum(s * s for s in samples)
                            rms = math.sqrt(sum_squares / count)
                        except Exception as e:
                            pass

                    self._current_rms = rms

                    # --- FEEDBACK SUPPRESSION / INTERRUPT LOOP ---
                    if is_tts_speaking():
                        if rms > 3000:
                            logger.info(f"[VOICE INTERRUPT PY] Loud speech detected (RMS: {rms:.1f}). Stopping speech.")
                            stop_tts_speaking()
                            while not self._audio_queue.empty():
                                try:
                                    self._audio_queue.get_nowait()
                                except Exception as e:
                                    logger.debug(f"[VOICE INTERRUPT] Error clearing queue (PyAudio): {e}")
                                    break
                            self._audio_queue.put(data)
                        continue
                        
                    self._audio_queue.put(data)
                except Exception as e:
                    logger.warning(f"PyAudio capture warning: {e}")
                time.sleep(0.01)
                
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            logger.error(f"[STT AUDIO RUNTIME ERROR] PyAudio stream failed: {e}")

    def _analyze_and_process_emotion(self, text: str, collected_data: bytes, duration: float):
        """Runs the voice analyzer and emotion engine on transcribed speech."""
        if not text or not collected_data:
            return
        try:
            words_count = len(text.split())
            
            # Avoid imports loop
            from tools.voice_analyzer import analyze_audio_segment
            from backend.emotion_engine import EmotionEngine
            
            voice_metrics = analyze_audio_segment(collected_data, duration, words_count)
            engine = EmotionEngine()
            engine.process_turn(text, voice_metrics)
        except Exception as e:
            logger.debug(f"Emotion analysis skipped/failed: {e}")

    def listen_once(self, timeout: int = 5, phrase_time_limit: int = 8) -> Dict[str, Any]:
        """
        Retrieves next voice transaction from Queue (Offline-First).
        If offline Vosk is missing, fallbacks dynamically to online Google API.
        """
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            logger.warning("[STT] Already listening. Rejecting concurrent listen request.")
            return {"status": "error", "text": "STT busy", "confidence": 0.0, "error": "STT engine is busy."}
        
        try:
            # Ensure loops are active
            self.start_listening_loop()
            
            # Clear old audio chunks first
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break
                    
            logger.info(f"[STT] Awaiting active input stream (timeout={timeout}s)...")
            start_time = time.time()
            speech_start_time = None
            
            # We accumulate buffer strings or feed the Vosk recognizer
            collected_data = bytearray()
            
            while time.time() - start_time < timeout:
                # Check interruption
                if is_tts_speaking():
                    # Discard and sleep
                    time.sleep(0.1)
                    continue
                    
                try:
                    data = self._audio_queue.get(timeout=0.5)
                    if speech_start_time is None:
                        speech_start_time = time.time()
                    collected_data.extend(data)
                    
                    # If we have Vosk active, stream process the chunk
                    if self._recognizer is not None:
                        if self._recognizer.AcceptWaveform(bytes(data)):
                            res = json.loads(self._recognizer.Result())
                            text = res.get("text", "").strip()
                            if text:
                                # User spoke! Interrupt TTS just in case
                                stop_tts_speaking()
                                logger.info(f"[STT OFFLINE VOSK] Heard: {text}")
                                
                                # Run emotion analysis in a background thread to prevent lag
                                audio_snapshot = bytes(collected_data)
                                duration = time.time() - (speech_start_time or start_time)
                                threading.Thread(
                                    target=self._analyze_and_process_emotion,
                                    args=(text, audio_snapshot, duration),
                                    daemon=True
                                ).start()
                                
                                return {"status": "ok", "text": text, "status_code": "OK", "confidence": 1.0}
                except queue.Empty:
                    continue
                    
            # Handle final Vosk result if data exists
            if self._recognizer is not None and len(collected_data) > 0:
                res = json.loads(self._recognizer.FinalResult())
                text = res.get("text", "").strip()
                if text:
                    logger.info(f"[STT OFFLINE VOSK FINAL] Heard: {text}")
                    
                    # Run emotion analysis in a background thread to prevent lag
                    audio_snapshot = bytes(collected_data)
                    duration = time.time() - (speech_start_time or start_time)
                    threading.Thread(
                        target=self._analyze_and_process_emotion,
                        args=(text, audio_snapshot, duration),
                        daemon=True
                    ).start()
                    
                    return {"status": "ok", "text": text, "status_code": "OK", "confidence": 1.0}
                    
            # --- ONLINE GOOGLE API FALLBACK ---
            if SR_AVAILABLE and self._sr_recognizer is not None and len(collected_data) > 0:
                try:
                    logger.info("[STT] Falling back to Online Google STT APIs...")
                    audio_data = sr.AudioData(bytes(collected_data), 16000, 2)
                    
                    # Fetch dialects from owner profile
                    try:
                        from backend.owner_profile import OWNER_PROFILE
                        dialects = OWNER_PROFILE.get("preferences", {}).get("preferred_dialects", ["en-US", "en-IN", "en-GB"])
                    except Exception as e:
                        logger.debug(f"[STT] Failed to fetch owner dialects, using defaults: {e}")
                        dialects = ["en-US", "en-IN", "en-GB"]
                    
                    # Recognize multiple dialects in parallel
                    import concurrent.futures
                    results = []
                    
                    def recognize_one(dialect):
                        try:
                            res = self._sr_recognizer.recognize_google(audio_data, language=dialect, show_all=True)
                            if isinstance(res, dict) and "alternative" in res:
                                alternatives = res["alternative"]
                                if alternatives:
                                    best_alt = max(alternatives, key=lambda x: x.get("confidence", 0.0))
                                    return {
                                        "text": best_alt.get("transcript", ""),
                                        "confidence": best_alt.get("confidence", 0.8)
                                    }
                            elif isinstance(res, str):
                                return {"text": res, "confidence": 0.8}
                        except Exception as e:
                            logger.debug(f"[STT] Dialect recognition failed for {dialect}: {e}")
                        return None

                    with concurrent.futures.ThreadPoolExecutor(max_workers=len(dialects)) as executor:
                        futures = [executor.submit(recognize_one, d) for d in dialects]
                        for f in concurrent.futures.as_completed(futures):
                            res = f.result()
                            if res and res["text"]:
                                results.append(res)
                    
                    if results:
                        best_res = max(results, key=lambda x: x["confidence"])
                        text = best_res["text"]
                    else:
                        text = self._sr_recognizer.recognize_google(audio_data) # final fallback

                    logger.info(f"[STT ONLINE GOOGLE] Heard: {text}")
                    
                    # Run emotion analysis in a background thread to prevent lag
                    audio_snapshot = bytes(collected_data)
                    duration = time.time() - (speech_start_time or start_time)
                    threading.Thread(
                        target=self._analyze_and_process_emotion,
                        args=(text, audio_snapshot, duration),
                        daemon=True
                    ).start()
                    
                    return {"status": "ok", "text": text, "status_code": "OK", "confidence": 1.0}
                except Exception as e:
                    logger.warning(f"[STT ONLINE GOOGLE FAILED] resolution error: {e}")
                    
            return {"status": "timeout", "text": "", "status_code": "TIMEOUT", "confidence": 0.0}
        finally:
            self._lock.release()

# Global singleton
stt = None
try:
    stt = VoiceSTT()
except Exception as e:
    logger.warning(f"[STT] Initialization warning: {e}")

def listen_once(timeout=5, phrase_time_limit=8):
    if stt is None:
        return {"status": "error", "text": "STT not available", "confidence": 0.0}
    return stt.listen_once(timeout, phrase_time_limit)

def listen():
    return listen_once()

# Automatically ensure models check on import
ensure_vosk_model()
