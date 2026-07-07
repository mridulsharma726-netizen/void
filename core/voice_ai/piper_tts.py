"""
VOID Piper Text-to-Speech (TTS) Module
======================================

Generates speech output offline using Piper TTS and a local ONNX model file,
falling back to pyttsx3 or edge-tts if missing.
"""

import os
import subprocess
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("void.core.voice_ai.piper_tts")

ROOT_DIR = Path(__file__).parent.parent.parent
MODEL_DIR = ROOT_DIR / "memory" / "data" / "models"
PIPER_MODEL_PATH = MODEL_DIR / "en_US-lessac-medium.onnx"
PIPER_CONFIG_PATH = MODEL_DIR / "en_US-lessac-medium.onnx.json"
VENV_SCRIPTS_DIR = ROOT_DIR / "venv" / "Scripts"
PIPER_EXE_PATH = VENV_SCRIPTS_DIR / "piper.exe"

class PiperTTS:
    """Manages offline Piper TTS speech synthesis and audio playback."""
    
    def __init__(self):
        self.exe_path = self._find_piper_exe()
        self.model_path = PIPER_MODEL_PATH
        
        self.ready = False
        if self.exe_path and self.model_path.exists():
            self.ready = True
            logger.info(f"[PIPER TTS] Ready. Using executable {self.exe_path} and model {self.model_path}")
        else:
            logger.warning("[PIPER TTS] Piper executable or voice ONNX model not found. Using pyttsx3/edge-tts fallbacks.")

    def _find_piper_exe(self) -> Optional[str]:
        """Finds the Piper executable."""
        if PIPER_EXE_PATH.exists():
            return str(PIPER_EXE_PATH)
            
        import shutil
        sys_path = shutil.which("piper")
        if sys_path:
            return sys_path
            
        # Also check standard Python scripts folder on Windows
        import sys
        python_dir = Path(sys.executable).parent
        sys_piper = python_dir / "piper.exe"
        if sys_piper.exists():
            return str(sys_piper)
            
        return None

    def speak(self, text: str, output_wav: str = None) -> bool:
        """
        Synthesizes text to speech, plays it locally on the host machine,
        and saves to output_wav if provided. Benchmarks CPU latency.
        """
        if not self.ready:
            logger.debug("[PIPER TTS] Not ready, falling back to legacy speak...")
            return self._fallback_speak(text)
            
        wav_path = output_wav or str(ROOT_DIR / "recordings" / f"tts_{int(time.time())}.wav")
        Path(wav_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Command: piper.exe --model model.onnx --output_file output.wav
        cmd = [
            self.exe_path,
            "--model", str(self.model_path),
            "--output_file", wav_path
        ]
        
        try:
            start_time = time.perf_counter()
            logger.info(f"[PIPER TTS] Synthesizing speech: \"{text}\"")
            
            # Run synthesis
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Feed input text to Piper
            stdout, stderr = process.communicate(input=text, timeout=15)
            
            latency = (time.perf_counter() - start_time) * 1000.0
            logger.info(f"[PIPER TTS] Synthesis subprocess finished in {latency:.2f}ms. Code={process.returncode}")
            
            if process.returncode != 0:
                logger.error(f"[PIPER TTS] Piper execution failed: {stderr}")
                return self._fallback_speak(text)
                
            if Path(wav_path).exists() and Path(wav_path).stat().st_size > 44:
                # Play the generated WAV file using ffplay or winsound
                self._play_wav(wav_path)
                return True
            else:
                logger.error("[PIPER TTS] Output WAV file was not generated or empty.")
                return self._fallback_speak(text)
                
        except subprocess.TimeoutExpired:
            logger.error("[PIPER TTS] Synthesis timed out.")
            return self._fallback_speak(text)
        except Exception as e:
            logger.error(f"[PIPER TTS] Synthesis error: {e}")
            return self._fallback_speak(text)

    def _play_wav(self, wav_path: str):
        """Plays the generated WAV file locally."""
        try:
            # 1. On Windows, winsound is native and fast
            if os.name == 'nt':
                import winsound
                winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
        except Exception as e:
            logger.debug(f"[PIPER TTS] winsound playback failed: {e}")
            
        try:
            # 2. Try playing via ffplay (since edge-tts uses it in VOID)
            # Find ffplay in path
            import shutil
            ffplay_path = shutil.which("ffplay")
            if ffplay_path:
                subprocess.Popen(
                    [ffplay_path, "-nodisp", "-autoexit", "-loglevel", "quiet", wav_path],
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                return
        except Exception as e:
            logger.debug(f"[PIPER TTS] ffplay playback failed: {e}")

    def _fallback_speak(self, text: str) -> bool:
        """Fallback speak using legacy pyttsx3 or edge-tts."""
        try:
            logger.info("[PIPER TTS] Executing legacy TTS fallback speaker...")
            # Try offline pyttsx3 first
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
                logger.info("[PIPER TTS] Fallback pyttsx3 success.")
                return True
            except Exception as tts_err:
                logger.warning(f"[PIPER TTS] Fallback pyttsx3 failed: {tts_err}")
                
            # Try edge-tts
            try:
                from tools.voice_tts import speak as edge_speak
                edge_speak(text)
                logger.info("[PIPER TTS] Fallback edge-tts success.")
                return True
            except Exception as edge_err:
                logger.warning(f"[PIPER TTS] Fallback edge-tts failed: {edge_err}")
                
            return False
        except Exception as fallback_err:
            logger.error(f"[PIPER TTS] All fallbacks failed: {fallback_err}")
            return False
