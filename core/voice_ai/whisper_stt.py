"""
VOID whisper.cpp Speech-to-Text (STT) Module
===========================================

Transcribes local audio using a whisper.cpp subprocess runner, with
graceful fallbacks to Vosk or online SpeechRecognition.
"""

import os
import subprocess
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("void.core.voice_ai.whisper_stt")

ROOT_DIR = Path(__file__).parent.parent.parent
MODEL_DIR = ROOT_DIR / "memory" / "data" / "models"
WHISPER_MODEL_PATH = MODEL_DIR / "ggml-tiny.en.bin"
BIN_DIR = ROOT_DIR / "memory" / "data" / "bin"
WHISPER_EXE_PATH = BIN_DIR / "whisper.exe"  # Can also be "whisper-cli.exe" or "main.exe"

class WhisperSTT:
    """Manages whisper.cpp CLI compilation/execution and output parsing."""
    
    def __init__(self):
        self.exe_path = self._find_whisper_exe()
        self.model_path = WHISPER_MODEL_PATH
        
        # Verify readiness
        self.ready = False
        if self.exe_path and self.model_path.exists():
            self.ready = True
            logger.info(f"[WHISPER STT] Ready. Using executable {self.exe_path} and model {self.model_path}")
        else:
            logger.warning("[WHISPER STT] whisper.cpp or ggml-tiny.en.bin not found. Speech-to-text will fallback to Vosk/SpeechRecognition.")

    def _find_whisper_exe(self) -> Optional[str]:
        """Finds the whisper.cpp executable in local folder or system PATH."""
        # 1. Check local bin folder
        for name in ["whisper.exe", "whisper-cli.exe", "main.exe", "whisper"]:
            local_path = BIN_DIR / name
            if local_path.exists():
                return str(local_path)
                
        # 2. Check system PATH
        import shutil
        for name in ["whisper-cli", "whisper", "whisper.cpp"]:
            sys_path = shutil.which(name)
            if sys_path:
                return sys_path
                
        return None

    def transcribe(self, wav_path: str) -> Optional[str]:
        """
        Transcribes the given WAV file using whisper.cpp.
        Benchmarks and logs CPU latency.
        """
        if not self.ready:
            logger.debug("[WHISPER STT] Not ready, falling back to legacy Vosk/SR STT...")
            return self._fallback_transcribe(wav_path)
            
        temp_txt = Path(wav_path).with_suffix("")  # whisper.cpp appends .txt automatically to output prefix
        output_txt_file = Path(str(temp_txt) + ".txt")
        
        # Ensure clean state
        if output_txt_file.exists():
            try:
                os.remove(output_txt_file)
            except Exception:
                pass
                
        # Command: whisper.exe -m ggml-tiny.en.bin -f input.wav -otxt -of output_prefix
        cmd = [
            self.exe_path,
            "-m", str(self.model_path),
            "-f", wav_path,
            "-otxt",
            "-of", str(temp_txt)
        ]
        
        try:
            start_time = time.perf_counter()
            logger.info(f"[WHISPER STT] Running whisper.cpp: {' '.join(cmd)}")
            
            # Execute subprocess completely offline, using CPU
            # whisper.cpp is optimized for CPU inference
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                timeout=20
            )
            
            latency = (time.perf_counter() - start_time) * 1000.0
            logger.info(f"[WHISPER STT] Transcription subprocess finished in {latency:.2f}ms. Code={process.returncode}")
            
            if process.returncode != 0:
                logger.error(f"[WHISPER STT] whisper.cpp execution failed: {process.stderr}")
                return self._fallback_transcribe(wav_path)
                
            if output_txt_file.exists():
                with open(output_txt_file, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                
                # Cleanup
                try:
                    os.remove(output_txt_file)
                except Exception:
                    pass
                    
                # whisper.cpp output cleanup (remove timestamps or carriage returns if any)
                clean_text = text.replace("\r", "").replace("\n", " ").strip()
                logger.info(f"[WHISPER STT] Result: \"{clean_text}\"")
                return clean_text
            else:
                logger.error("[WHISPER STT] Output text file was not generated.")
                return self._fallback_transcribe(wav_path)
                
        except subprocess.TimeoutExpired:
            logger.error("[WHISPER STT] Transcription timed out.")
            return self._fallback_transcribe(wav_path)
        except Exception as e:
            logger.error(f"[WHISPER STT] Error running whisper.cpp: {e}")
            return self._fallback_transcribe(wav_path)

    def _fallback_transcribe(self, wav_path: str) -> Optional[str]:
        """Fallback transcription using Vosk or online SpeechRecognition."""
        try:
            logger.info("[WHISPER STT] Executing Vosk/SpeechRecognition fallback transcription...")
            
            # Since VoskSpeechRecognizer listens to PyAudio stream, let's write a simple Vosk wav file reader if possible,

            # or fallback to speech_recognition Google API which has native WAV support
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio = r.record(source)
            try:
                text = r.recognize_google(audio)
                logger.info(f"[WHISPER STT] Fallback recognize_google success: \"{text}\"")
                return text
            except Exception as sr_err:
                logger.warning(f"[WHISPER STT] Fallback recognize_google failed: {sr_err}")
                
            # Try Vosk offline WAV reading if Vosk is installed
            try:
                import vosk
                import wave
                from tools.voice_stt import VOSK_MODEL_PATH
                if VOSK_MODEL_PATH.exists():
                    wf = wave.open(wav_path, "rb")
                    if wf.getnchannels() == 1:
                        model = vosk.Model(str(VOSK_MODEL_PATH))
                        rec = vosk.KaldiRecognizer(model, wf.getframerate())
                        res_text = ""
                        while True:
                            data = wf.readframes(4000)
                            if len(data) == 0:
                                break
                            if rec.AcceptWaveform(data):
                                pass
                        res_json = json.loads(rec.FinalResult())
                        res_text = res_json.get("text", "")
                        wf.close()
                        if res_text:
                            logger.info(f"[WHISPER STT] Fallback Vosk success: \"{res_text}\"")
                            return res_text
            except Exception as vosk_err:
                logger.warning(f"[WHISPER STT] Fallback Vosk failed: {vosk_err}")
                
            return ""
        except Exception as fallback_err:
            logger.error(f"[WHISPER STT] All fallbacks failed: {fallback_err}")
            return ""
