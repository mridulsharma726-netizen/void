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
        logger.info(f"[WHISPER STT DIAGNOSIS] transcribe() called for: {wav_path}. Primary whisper.cpp ready: {self.ready}")
        logger.info(f"[WHISPER STT DIAGNOSIS] Configured Whisper model path: {self.model_path} (File: {os.path.basename(self.model_path) if self.model_path else 'None'}).")
        
        # 1. Check WAV format and log details
        n_channels = 1
        framerate = 16000
        sampwidth = 2
        duration = 0.0
        try:
            import wave
            with wave.open(wav_path, "rb") as wf:
                n_channels = wf.getnchannels()
                framerate = wf.getframerate()
                sampwidth = wf.getsampwidth()
                n_frames = wf.getnframes()
                duration = n_frames / framerate
                logger.info(f"[WHISPER STT DIAGNOSIS] WAV Format: {n_channels} channels, {framerate}Hz, {sampwidth * 8}-bit depth, {n_frames} frames. Chunk boundary duration: {duration:.2f}s.")
        except Exception as e:
            logger.error(f"[WHISPER STT DIAGNOSIS] Failed to inspect WAV details: {e}")

        # 2. Resample to 16kHz mono 16-bit PCM if needed
        active_wav_path = wav_path
        if n_channels != 1 or framerate != 16000 or sampwidth != 2:
            active_wav_path = self._resample_wav_to_16k_mono_16bit(wav_path)

        # 3. Calculate peak amplitude and log it for gain/clipping diagnostics
        try:
            import wave
            import audioop
            with wave.open(active_wav_path, "rb") as wf:
                data = wf.readframes(wf.getnframes())
                if len(data) > 0:
                    peak = audioop.max(data, wf.getsampwidth())
                    max_possible = 32767 if wf.getsampwidth() == 2 else (255 if wf.getsampwidth() == 1 else 8388607)
                    pct = (peak / max_possible) * 100
                    logger.info(f"[WHISPER STT DIAGNOSIS] Audio Levels: Peak Amplitude: {peak} ({pct:.2f}% of max {max_possible}).")
                    if pct > 98.0:
                        logger.warning("[WHISPER STT DIAGNOSIS] Audio clipping detected! Voice signal is too hot.")
                    elif pct < 5.0:
                        logger.warning("[WHISPER STT DIAGNOSIS] Audio signal is extremely quiet! Voice signal is too low.")
        except Exception as e:
            logger.error(f"[WHISPER STT DIAGNOSIS] Failed to calculate peak amplitude: {e}")

        if not self.ready:
            logger.debug("[WHISPER STT DIAGNOSIS] whisper.cpp not ready, entering fallback transcription path.")
            return self._fallback_transcribe(active_wav_path)
            
        temp_txt = Path(active_wav_path).with_suffix("")  # whisper.cpp appends .txt automatically to output prefix
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
            "-f", active_wav_path,
            "-otxt",
            "-of", str(temp_txt)
        ]
        
        try:
            start_time = time.perf_counter()
            logger.info(f"[WHISPER STT DIAGNOSIS] Running whisper.cpp: {' '.join(cmd)}")
            
            # Execute subprocess completely offline, using CPU
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                timeout=20
            )
            
            latency = (time.perf_counter() - start_time) * 1000.0
            logger.info(f"[WHISPER STT DIAGNOSIS] whisper.cpp finished in {latency:.2f}ms. Code={process.returncode}")
            
            if process.returncode != 0:
                logger.error(f"[WHISPER STT DIAGNOSIS] whisper.cpp execution failed: {process.stderr}")
                return self._fallback_transcribe(active_wav_path)
                
            if output_txt_file.exists():
                with open(output_txt_file, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                
                # Cleanup
                try:
                    os.remove(output_txt_file)
                except Exception:
                    pass
                    
                clean_text = text.replace("\r", "").replace("\n", " ").strip()
                logger.info(f"[WHISPER STT DIAGNOSIS] Real whisper.cpp Result: \"{clean_text}\"")
                return clean_text
            else:
                logger.error("[WHISPER STT DIAGNOSIS] Output text file was not generated.")
                return self._fallback_transcribe(active_wav_path)
                
        except subprocess.TimeoutExpired:
            logger.error("[WHISPER STT DIAGNOSIS] Transcription timed out.")
            return self._fallback_transcribe(active_wav_path)
        except Exception as e:
            logger.error(f"[WHISPER STT DIAGNOSIS] Error running whisper.cpp: {e}")
            return self._fallback_transcribe(active_wav_path)

    def _resample_wav_to_16k_mono_16bit(self, wav_path: str) -> str:
        """
        Ensures the WAV file is 16kHz, mono, 16-bit PCM.
        If not, it resamples, downmixes, and returns a corrected temporary path.
        """
        import wave
        import audioop
        import tempfile
        import json
        
        try:
            with wave.open(wav_path, "rb") as wf:
                params = wf.getparams()
                n_channels, sampwidth, framerate, n_frames, comptype, compname = params
                
                # If already correct, do nothing
                if n_channels == 1 and framerate == 16000 and sampwidth == 2:
                    logger.info("[WHISPER STT DIAGNOSIS] WAV format is already 16kHz mono 16-bit PCM.")
                    return wav_path
                    
                logger.info(f"[WHISPER STT DIAGNOSIS] Resampling WAV from {framerate}Hz {n_channels}-ch {sampwidth*8}-bit to 16kHz mono 16-bit PCM...")
                data = wf.readframes(n_frames)
                
                # 1. Convert to mono if stereo/multi-channel
                if n_channels > 1:
                    data = audioop.tomono(data, sampwidth, 0.5, 0.5)
                    n_channels = 1
                    
                # 2. Resample to 16000Hz if different
                if framerate != 16000:
                    state = None
                    data, state = audioop.ratecv(data, sampwidth, 1, framerate, 16000, state)
                    framerate = 16000
                    
                # 3. Convert bit depth to 16-bit (sampwidth = 2) if different
                if sampwidth != 2:
                    data = audioop.lin2lin(data, sampwidth, 2)
                    sampwidth = 2
                    
                # Save resampled WAV over a temporary file
                temp_resampled = Path(tempfile.gettempdir()) / f"resampled_{os.path.basename(wav_path)}"
                with wave.open(str(temp_resampled), "wb") as out_wf:
                    out_wf.setnchannels(1)
                    out_wf.setsampwidth(2)
                    out_wf.setframerate(16000)
                    out_wf.writeframes(data)
                    
                logger.info(f"[WHISPER STT DIAGNOSIS] Resampled WAV successfully saved to {temp_resampled}")
                return str(temp_resampled)
                
        except Exception as e:
            logger.error(f"[WHISPER STT DIAGNOSIS] Resampling failed: {e}")
            return wav_path

    def _fallback_transcribe(self, wav_path: str) -> Optional[str]:
        """Fallback transcription using Vosk or online SpeechRecognition."""
        try:
            logger.info("[WHISPER STT DIAGNOSIS] Entering fallback transcription path.")
            
            # 1. Try online SpeechRecognition (Google API) fallback
            import speech_recognition as sr
            r = sr.Recognizer()
            try:
                logger.info("[WHISPER STT DIAGNOSIS] Attempting SpeechRecognition (Google Cloud Fallback) engine...")
                with sr.AudioFile(wav_path) as source:
                    audio = r.record(source)
                text = r.recognize_google(audio)
                logger.info(f"[WHISPER STT DIAGNOSIS] SpeechRecognition fallback success: \"{text}\"")
                return text
            except Exception as sr_err:
                logger.warning(f"[WHISPER STT DIAGNOSIS] SpeechRecognition fallback failed: {sr_err}")
                
            # 2. Try offline local Vosk fallback
            try:
                import vosk
                import wave
                import json
                from tools.voice_stt import VOSK_MODEL_PATH
                logger.info(f"[WHISPER STT DIAGNOSIS] Attempting local Vosk model fallback ({VOSK_MODEL_PATH})...")
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
                            logger.info(f"[WHISPER STT DIAGNOSIS] Local Vosk fallback success: \"{res_text}\"")
                            return res_text
                else:
                    logger.warning("[WHISPER STT DIAGNOSIS] Local Vosk model folder does not exist.")
            except Exception as vosk_err:
                logger.warning(f"[WHISPER STT DIAGNOSIS] Local Vosk model fallback failed: {vosk_err}")
                
            return ""
        except Exception as fallback_err:
            logger.error(f"[WHISPER STT DIAGNOSIS] All fallback paths failed: {fallback_err}")
            return ""

