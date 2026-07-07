"""
VOID Unified Voice I/O Pipeline Module
======================================

Links the WakeWordDetector, WhisperSTT, and PiperTTS modules together to form a
cohesive, modular, and fault-tolerant local speech interface.
"""

import os
import time
import logging
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("void.core.voice_ai.voice_pipeline")

from core.voice_ai.whisper_stt import WhisperSTT
from core.voice_ai.piper_tts import PiperTTS
from core.voice_ai.wakeword_detector import WakeWordDetector

class VoicePipeline:
    """Orchestrates continuous wake-word monitoring, speech recording, transcription, and synthesis."""
    
    def __init__(self, command_handler: Optional[Callable[[str], None]] = None):
        self.command_handler = command_handler
        self.stt = WhisperSTT()
        self.tts = PiperTTS()
        self.detector = None
        self._listening = False
        
        # Determine overall state
        self.fully_offline_ready = self.stt.ready and self.tts.ready
        logger.info(f"[VOICE PIPELINE] Initialized. Offline Voice Ready: {self.fully_offline_ready}")

    def speak(self, text: str, output_wav: str = None) -> bool:
        """Speak response using Piper TTS (with pyttsx3/edge-tts fallbacks)."""
        try:
            return self.tts.speak(text, output_wav)
        except Exception as e:
            logger.error(f"[VOICE PIPELINE] Speech synthesis failed: {e}")
            return False

    def transcribe(self, wav_path: str) -> str:
        """Transcribe recording using Whisper STT (with Vosk/SR fallbacks)."""
        try:
            res = self.stt.transcribe(wav_path)
            return res or ""
        except Exception as e:
            logger.error(f"[VOICE PIPELINE] Speech transcription failed: {e}")
            return ""

    def start(self, wake_phrase: str = "open void"):
        """Starts the background wake-word detector loop."""
        if self._listening:
            return
            
        # Create wake-word detector callback
        def on_wake_detected():
            logger.info("[VOICE PIPELINE] Wake word triggered! Initiating command recording...")
            self._trigger_command_recording()
            
        try:
            self.detector = WakeWordDetector(callback=on_wake_detected, wake_phrase=wake_phrase)
            self.detector.start()
            self._listening = True
            logger.info("[VOICE PIPELINE] Wake-word listening active.")
        except Exception as e:
            logger.error(f"[VOICE PIPELINE] Failed starting wake-word detector: {e}")
            self._listening = False

    def stop(self):
        """Stops the background wake-word detector loop."""
        if self.detector:
            self.detector.stop()
            self.detector = None
        self._listening = False
        logger.info("[VOICE PIPELINE] Voice pipeline stopped.")

    def _trigger_command_recording(self):
        """Plays activation chime, records voice command, transcribes, and executes handler."""
        # 1. Play activation chime
        try:
            import winsound
            winsound.Beep(2000, 75)
            winsound.Beep(2400, 120)
        except Exception:
            pass
            
        # 2. Record audio command to temporary WAV file
        import tempfile
        import wave
        import pyaudio
        from tools.voice_stt import get_best_microphone_index
        
        temp_wav = Path(tempfile.gettempdir()) / "void_cmd.wav"
        
        # Audio recording params
        chunk = 1024
        sample_format = pyaudio.paInt16
        channels = 1
        fs = 16000
        seconds = 5  # Capture 5 seconds of audio command
        
        p = pyaudio.PyAudio()
        logger.info("[VOICE PIPELINE] Recording command...")
        
        try:
            mic_idx = get_best_microphone_index()
            stream = p.open(
                format=sample_format,
                channels=channels,
                rate=fs,
                frames_per_buffer=chunk,
                input=True,
                input_device_index=mic_idx
            )
            
            frames = []
            for _ in range(0, int(fs / chunk * seconds)):
                data = stream.read(chunk, exception_on_overflow=False)
                frames.append(data)
                
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            # Save recording to WAV
            wf = wave.open(str(temp_wav), 'wb')
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(sample_format))
            wf.setframerate(fs)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            logger.info("[VOICE PIPELINE] Command recording complete. Transcribing...")
            
            # 3. Transcribe using Whisper
            command_text = self.transcribe(str(temp_wav))
            
            # Cleanup temp file
            try:
                os.remove(temp_wav)
            except Exception:
                pass
                
            if command_text and command_text.strip():
                logger.info(f"[VOICE PIPELINE] Command captured: \"{command_text}\"")
                if self.command_handler:
                    self.command_handler(command_text)
            else:
                logger.info("[VOICE PIPELINE] No speech captured or recognized.")
                
        except Exception as e:
            logger.error(f"[VOICE PIPELINE] Command capturing failed: {e}")
            try:
                p.terminate()
            except Exception:
                pass

# Singleton voice pipeline instance
_voice_pipeline_instance: Optional[VoicePipeline] = None

def get_voice_pipeline(command_handler: Optional[Callable[[str], None]] = None) -> VoicePipeline:
    """Returns singleton instance of VoicePipeline."""
    global _voice_pipeline_instance
    if _voice_pipeline_instance is None:
        _voice_pipeline_instance = VoicePipeline(command_handler)
    elif command_handler:
        _voice_pipeline_instance.command_handler = command_handler
    return _voice_pipeline_instance
