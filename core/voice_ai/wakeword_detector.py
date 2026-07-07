"""
VOID openWakeWord Wake-Word Detector Module
==========================================

Listens continuously to the default microphone, running local ONNX models on CPU
via openWakeWord. Upon detection, it triggers a callback.
"""

import os
import sys
import time
import logging
import threading
import numpy as np
from pathlib import Path
from typing import Callable, Optional, List

logger = logging.getLogger("void.core.voice_ai.wakeword_detector")

OPENWAKEWORD_AVAILABLE = False
try:
    import openwakeword
    OPENWAKEWORD_AVAILABLE = True
except ImportError:
    logger.warning("[WAKEWORD DETECTOR] openwakeword not installed. Fallback mode will be active.")

class WakeWordDetector:
    """Continuous mic stream listener running openWakeWord model for offline activation."""
    
    def __init__(self, callback: Callable[[], None], wake_phrase: str = "open void"):
        self.callback = callback
        self.wake_phrase = wake_phrase
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        self.ready = False
        self.oww_model = None
        
        if OPENWAKEWORD_AVAILABLE:
            try:
                # openWakeWord packages several models. Let's see if we use a bundled one
                # or a custom wake word. Standard bundled models: 'alexa', 'hey_jarvis', 'hey_mycroft', 'weather'
                # To support custom configurable phrases, we can use the default models or download/define one.
                # For offline safety, we prioritize bundled models like 'hey_jarvis' (closest to open void).
                # We can also check if a custom model exists at memory/data/models/wake_words/
                self._load_model()
                self.ready = True
                logger.info(f"[WAKEWORD DETECTOR] openWakeWord model loaded successfully for '{self.wake_phrase}'")
            except Exception as e:
                logger.error(f"[WAKEWORD DETECTOR] Failed loading openWakeWord: {e}")
                self.ready = False

    def _load_model(self):
        """Loads the openWakeWord ONNX model."""
        import openwakeword
        from openwakeword.model import Model
        
        # Determine model to load
        # Default bundled models in openwakeword package: 'alexa', 'hey_mycroft', 'hey_jarvis', 'hey_snips'
        # We can map 'open void' or 'hey jarvis' or load a custom model
        model_name = "hey_jarvis"
        if "alexa" in self.wake_phrase.lower():
            model_name = "alexa"
        elif "mycroft" in self.wake_phrase.lower():
            model_name = "hey_mycroft"
            
        # Instantiate model
        self.oww_model = Model(wakeword_models=[model_name], inference_framework="onnxruntime")
        self.prediction_key = model_name

    def start(self):
        """Starts the background listening thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="VOID-WakeWordDetect")
        self._thread.start()
        logger.info("[WAKEWORD DETECTOR] Listening thread started.")

    def stop(self):
        """Stops the background listening thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("[WAKEWORD DETECTOR] Listening thread stopped.")

    def _listen_loop(self):
        """Continuously reads microphone stream and runs openWakeWord inference."""
        import pyaudio
        
        chunk_size = 1280  # openWakeWord expects 1280 samples (80 ms of audio at 16kHz)
        p = None
        stream = None
        
        try:
            from tools.voice_stt import get_best_microphone_index
            mic_idx = get_best_microphone_index()
            
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=mic_idx,
                frames_per_buffer=chunk_size
            )
            
            logger.info("[WAKEWORD DETECTOR] Microphone stream successfully opened.")
            
            # Warmup model
            if self.oww_model:
                self.oww_model.predict(np.zeros(1280, dtype=np.int16))
                
            while self._running:
                try:
                    data = stream.read(chunk_size, exception_on_overflow=False)
                    if not data:
                        continue
                        
                    # Convert to numpy int16 array
                    audio_frame = np.frombuffer(data, dtype=np.int16)
                    
                    # Run prediction
                    if self.oww_model:
                        prediction = self.oww_model.predict(audio_frame)
                        score = prediction.get(self.prediction_key, 0.0)
                        
                        if score > 0.5:
                            logger.info(f"[WAKEWORD DETECTOR] Wake word detected! Score: {score:.4f}")
                            # Trigger callback
                            self.callback()
                            # Cool-down to avoid double trigger
                            time.sleep(1.5)
                            
                except Exception as loop_err:
                    logger.debug(f"[WAKEWORD DETECTOR] Audio loop warning: {loop_err}")
                    time.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"[WAKEWORD DETECTOR] Failed to open microphone or initialize audio: {e}")
            # Degrade gracefully: sleep and check if running
            while self._running:
                time.sleep(0.5)
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if p:
                try:
                    p.terminate()
                except Exception:
                    pass
            logger.info("[WAKEWORD DETECTOR] Microphone stream closed.")
