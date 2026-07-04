import os
import sys
import time
import wave
import queue
import json
import struct
import math
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("void.audio_memory")

ROOT_DIR = Path(__file__).parent.parent.parent
RECORDINGS_DIR = ROOT_DIR / "recordings"

# Ensure directories exist
RECORDINGS_DIR.mkdir(exist_ok=True, parents=True)

class AudioMemoryService:
    """
    Continuous background audio memory service.
    
    Captures mic input, chunks audio by silence or duration,
    saves locally to YYYY/MM/DD/recording_HH-MM-SS.wav,
    and runs offline STT + LLM summarization in a background queue.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.is_enabled = False
        self.device_index = None  # None = default
        self.sample_rate = 16000
        self.channels = 1
        self.mode = "continuous"  # continuous, lecture, meeting, voice_note
        
        # Silence/VAD settings
        self.energy_threshold = 400.0  # RMS threshold for speech
        self.silence_limit_seconds = 15.0  # Seconds of silence to trigger chunking
        self.max_chunk_seconds = 300.0  # 5 minutes max per file
        self.min_speech_seconds = 3.0  # Min speech required to save a recording
        
        # State
        self._recording_thread = None
        self._processing_thread = None
        self._deferred_thread = None
        self._running = False
        self._processing_queue = queue.Queue()
        
        # Active stream buffers
        self._audio_buffer = bytearray()
        self._speech_detected = False
        self._active_speech_duration = 0.0
        self._silence_duration = 0.0
        
        # DSP Filter state
        self._hp_prev_input = 0.0
        self._hp_prev_output = 0.0
        
        self._state_lock = threading.Lock()

    def start(self):
        """Starts the background audio capture and processing loops."""
        with self._state_lock:
            if self._running:
                logger.info("[AUDIO SERVICE] Already running.")
                return
            self._running = True
            
        # Start processing worker thread
        self._processing_thread = threading.Thread(
            target=self._processing_worker,
            daemon=True,
            name="VOID-AudioProcessor"
        )
        self._processing_thread.start()
        
        # Start deferred processing thread
        self._deferred_thread = threading.Thread(
            target=self._deferred_processor_loop,
            daemon=True,
            name="VOID-DeferredProcessor"
        )
        self._deferred_thread.start()
        
        # Start recording thread if enabled
        if self.is_enabled:
            self._start_recording_thread()
            
        logger.info("[AUDIO SERVICE] Service successfully initialized.")

    def stop(self):
        """Stops the background audio capture and processing loops."""
        with self._state_lock:
            self._running = False
        
        self._stop_recording_thread()
        
        # Wait for processor to exit
        if self._processing_thread:
            self._processing_thread.join(timeout=1.0)
            self._processing_thread = None
            
        if self._deferred_thread:
            self._deferred_thread.join(timeout=1.0)
            self._deferred_thread = None
            
        logger.info("[AUDIO SERVICE] Service stopped.")

    def enable_recording(self, enabled: bool):
        """Enables or disables continuous background capture."""
        with self._state_lock:
            if self.is_enabled == enabled:
                return
            self.is_enabled = enabled
            
        if enabled:
            self._start_recording_thread()
        else:
            self._stop_recording_thread()
            
        # Save preference
        try:
            from backend.memory_sqlite import set_preference
            set_preference("bg_recording_enabled", "true" if enabled else "false")
        except Exception as e:
            logger.error(f"Failed to save bg_recording_enabled preference: {e}")

    def get_microphones(self) -> List[Dict[str, Any]]:
        """Lists available input devices."""
        mics = []
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            try:
                # Add default virtual input options or scan
                for i in range(p.get_device_count()):
                    try:
                        info = p.get_device_info_by_index(i)
                        if info.get('maxInputChannels', 0) > 0:
                            mics.append({
                                "index": i,
                                "name": info.get('name'),
                                "is_default": i == p.get_default_input_device_info().get('index')
                            })
                    except Exception:
                        pass
            finally:
                p.terminate()
        except Exception as e:
            logger.warning(f"PyAudio mic scan failed: {e}")
            
        if not mics:
            try:
                import sounddevice as sd
                devices = sd.query_devices()
                default_input = sd.default.device[0]
                for idx, dev in enumerate(devices):
                    if dev.get('max_input_channels', 0) > 0:
                        mics.append({
                            "index": idx,
                            "name": dev.get('name'),
                            "is_default": idx == default_input
                        })
            except Exception as e:
                logger.warning(f"sounddevice mic scan failed: {e}")
                
        return mics

    def select_device(self, index: int):
        """Switches the recording device."""
        with self._state_lock:
            self.device_index = index
            recording_was_active = self._recording_thread is not None
            
        if recording_was_active:
            logger.info(f"[AUDIO SERVICE] Restarting recording stream to switch to device index {index}")
            self._stop_recording_thread()
            self._start_recording_thread()

    def _start_recording_thread(self):
        """Spawns the audio recording loop."""
        self._recording_thread = threading.Thread(
            target=self._recording_loop,
            daemon=True,
            name="VOID-BackgroundRecorder"
        )
        self._recording_thread.start()
        logger.info("[AUDIO SERVICE] Background recording thread spawned.")

    def _stop_recording_thread(self):
        """Gracefully stops the recording thread and flushes any remaining buffer."""
        if self._recording_thread:
            # The loop checks self.is_enabled and self._running
            self._recording_thread.join(timeout=2.0)
            self._recording_thread = None
            
            # Save any remaining buffer as a final chunk
            self._flush_buffer_to_file()
            logger.info("[AUDIO SERVICE] Background recording thread stopped.")

    def _recording_loop(self):
        """Continuously captures audio, running VAD to chunk files."""
        # Detect libraries
        use_sounddevice = False
        try:
            import sounddevice as sd
            use_sounddevice = True
        except ImportError:
            pass
            
        while True:
            with self._state_lock:
                if not self._running or not self.is_enabled:
                    break
            
            # Try PyAudio first if available
            try:
                import pyaudio
                p = pyaudio.PyAudio()
                
                # Open stream
                device_idx = self.device_index
                if device_idx is None:
                    try:
                        device_idx = p.get_default_input_device_info().get('index')
                    except Exception:
                        device_idx = None
                        
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=device_idx,
                    frames_per_buffer=4000
                )
                
                logger.info(f"[AUDIO SERVICE] PyAudio stream opened on device {device_idx}")
                
                self._audio_buffer = bytearray()
                self._speech_detected = False
                self._active_speech_duration = 0.0
                self._silence_duration = 0.0
                
                last_chunk_time = time.time()
                
                while True:
                    with self._state_lock:
                        if not self._running or not self.is_enabled:
                            break
                            
                    data = stream.read(4000, exception_on_overflow=False)
                    self._process_audio_block(data)
                    
                    # Check chunk triggers
                    now = time.time()
                    elapsed = now - last_chunk_time
                    
                    trigger_chunk = False
                    if elapsed >= self.max_chunk_seconds:
                        trigger_chunk = True
                        logger.info(f"[AUDIO SERVICE] Chunk trigger: Max duration reached ({elapsed:.1f}s)")
                    elif self._speech_detected and self._silence_duration >= self.silence_limit_seconds:
                        trigger_chunk = True
                        logger.info(f"[AUDIO SERVICE] Chunk trigger: Silence detected ({self._silence_duration:.1f}s)")
                        
                    if trigger_chunk:
                        self._flush_buffer_to_file()
                        last_chunk_time = time.time()
                        
                stream.stop_stream()
                stream.close()
                p.terminate()
                
            except Exception as e:
                logger.warning(f"[AUDIO SERVICE] PyAudio stream failed: {e}. Trying sounddevice fallback...")
                if use_sounddevice:
                    try:
                        self._recording_loop_sounddevice()
                    except Exception as sd_err:
                        logger.error(f"[AUDIO SERVICE] sounddevice fallback also failed: {sd_err}")
                else:
                    logger.error("[AUDIO SERVICE] No audio libraries available to run background recorder.")
                
                # Sleep 5 seconds before retrying the recording loop
                time.sleep(5.0)

    def _recording_loop_sounddevice(self):
        """Alternative recording loop using sounddevice."""
        import sounddevice as sd
        
        self._audio_buffer = bytearray()
        self._speech_detected = False
        self._active_speech_duration = 0.0
        self._silence_duration = 0.0
        last_chunk_time = time.time()
        
        def callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"[AUDIO SERVICE] sounddevice status: {status}")
            raw_bytes = bytes(indata)
            self._process_audio_block(raw_bytes)
            
        device_idx = self.device_index
        
        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=4000,
                dtype='int16',
                channels=self.channels,
                device=device_idx,
                callback=callback
            ):
                while True:
                    with self._state_lock:
                        if not self._running or not self.is_enabled:
                            break
                            
                    time.sleep(0.1)
                    
                    now = time.time()
                    elapsed = now - last_chunk_time
                    
                    trigger_chunk = False
                    if elapsed >= self.max_chunk_seconds:
                        trigger_chunk = True
                    elif self._speech_detected and self._silence_duration >= self.silence_limit_seconds:
                        trigger_chunk = True
                        
                    if trigger_chunk:
                        self._flush_buffer_to_file()
                        last_chunk_time = time.time()
                        
        except Exception as e:
            logger.error(f"[AUDIO SERVICE] sounddevice loop error: {e}")

    def _process_audio_block(self, data: bytes):
        """Analyzes an audio block for voice activity (RMS) and applies DSP in Lecture/Meeting mode."""
        if self.mode in ["lecture", "meeting"]:
            data = self._apply_dsp(data)
            
        self._audio_buffer.extend(data)
        
        # Calculate RMS
        count = len(data) // 2
        rms = 0
        if count > 0:
            try:
                samples = struct.unpack(f"{count}h", data)
                sum_squares = sum(s * s for s in samples)
                rms = math.sqrt(sum_squares / count)
            except Exception as e:
                logger.debug(f"[AUDIO SERVICE] RMS calculation failed: {e}")
                
        # Check VAD
        block_duration = count / self.sample_rate
        if rms > self.energy_threshold:
            # Speech block
            self._speech_detected = True
            self._active_speech_duration += block_duration
            self._silence_duration = 0.0
        else:
            # Silence block
            if self._speech_detected:
                self._silence_duration += block_duration

    def _flush_buffer_to_file(self):
        """Saves current buffer to WAV file and indexes immediately as 'pending' in SQLite."""
        buffer_to_save = None
        duration = 0.0
        speech_dur = 0.0
        
        with self._state_lock:
            if len(self._audio_buffer) > 0:
                buffer_to_save = bytes(self._audio_buffer)
                duration = len(buffer_to_save) / (self.sample_rate * 2) # 16-bit = 2 bytes/sample
                speech_dur = self._active_speech_duration
                
                # Reset buffers
                self._audio_buffer = bytearray()
                self._speech_detected = False
                self._active_speech_duration = 0.0
                self._silence_duration = 0.0
                
        if not buffer_to_save:
            return
            
        # Check if there is enough speech to warrant saving
        if speech_dur < self.min_speech_seconds:
            logger.info(f"[AUDIO SERVICE] Discarded chunk: Speech duration ({speech_dur:.2f}s) below minimum ({self.min_speech_seconds}s)")
            return
            
        # Save to local file YYYY/MM/DD/recording_HH-MM-SS.wav
        now = datetime.now()
        date_dir = RECORDINGS_DIR / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        
        file_name = f"{self.mode}_{now.strftime('%H-%M-%S')}.wav"
        file_path = date_dir / file_name
        
        try:
            with wave.open(str(file_path), 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2) # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(buffer_to_save)
                
            logger.info(f"[AUDIO SERVICE] Saved chunk to: {file_path} (Duration: {duration:.1f}s, Mode: {self.mode})")
            
            # Add to SQLite immediately as 'pending' (Offline-First resilience)
            try:
                from backend.memory_sqlite import add_audio_recording
                mic_name = self.get_active_mic_name()
                add_audio_recording(
                    recording_path=str(file_path),
                    duration=duration,
                    transcript="",
                    summary="",
                    status="pending",
                    mode=self.mode,
                    mic_used=mic_name,
                    sample_rate=self.sample_rate
                )
            except Exception as dberr:
                logger.error(f"[AUDIO SERVICE] Immediate DB index failed: {dberr}")
            
            # Queue for processing
            self._processing_queue.put({
                "file_path": str(file_path),
                "duration": duration
            })
        except Exception as e:
            logger.error(f"[AUDIO SERVICE] Failed to save WAV file: {e}")

    def _processing_worker(self):
        """Background thread worker that transcribes and summarizes recordings."""
        logger.info("[AUDIO SERVICE] Processing worker started.")
        
        # Load Vosk Model if available
        vosk_model = None
        try:
            import vosk
            from tools.voice_stt import VOSK_MODEL_PATH, ensure_vosk_model
            if ensure_vosk_model():
                vosk_model = vosk.Model(str(VOSK_MODEL_PATH))
                logger.info("[AUDIO SERVICE] Vosk model loaded in processor.")
        except Exception as e:
            logger.warning(f"[AUDIO SERVICE] Could not load Vosk model in processor: {e}")
            
        while True:
            try:
                # Check running flag
                with self._state_lock:
                    if not self._running and self._processing_queue.empty():
                        break
                        
                try:
                    task = self._processing_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                    
                file_path = task["file_path"]
                duration = task["duration"]
                
                logger.info(f"[AUDIO SERVICE] Processing recording: {file_path}")
                
                # Fetch database record to get ID
                rec_id = None
                try:
                    from backend.memory_sqlite import get_audio_recordings
                    all_recs = get_audio_recordings()
                    for r in all_recs:
                        if r["recording_path"] == file_path:
                            rec_id = r["id"]
                            break
                except Exception as e:
                    logger.debug(f"[AUDIO SERVICE] Failed to fetch recording ID from DB: {e}")
                
                # 1. Transcribe
                transcript, words, confidence = self._transcribe_file(file_path, vosk_model)
                
                if not transcript.strip():
                    logger.info(f"[AUDIO SERVICE] Empty transcript for {file_path}.")
                    if rec_id:
                        from backend.memory_sqlite import update_recording_status
                        update_recording_status(rec_id, "completed")
                    self._processing_queue.task_done()
                    continue
                    
                # Save transcript JSON
                transcript_data = {
                    "file_path": file_path,
                    "duration": duration,
                    "transcript": transcript,
                    "confidence": confidence,
                    "words": words
                }
                
                transcript_path = file_path.replace(".wav", "_transcript.json")
                try:
                    with open(transcript_path, "w", encoding="utf-8") as f:
                        json.dump(transcript_data, f, indent=4)
                except Exception as e:
                    logger.error(f"Failed to save transcript JSON: {e}")
                
                if rec_id:
                    from backend.memory_sqlite import update_recording_status
                    update_recording_status(rec_id, "pending_summary")
                    
                # 2. Summarize
                summary_data = self._summarize_transcript(transcript)
                
                # Check if summarization was actually generated or fell back to default
                if summary_data.get("short_summary") == "No summary available.":
                    logger.warning(f"[AUDIO SERVICE] AI summary fell back or failed for {file_path}. Setting status to pending_summary.")
                    if rec_id:
                        from backend.memory_sqlite import update_recording_status
                        update_recording_status(rec_id, "pending_summary")
                else:
                    summary_path = file_path.replace(".wav", "_summary.json")
                    try:
                        with open(summary_path, "w", encoding="utf-8") as f:
                            json.dump(summary_data, f, indent=4)
                    except Exception as e:
                        logger.error(f"Failed to save summary JSON: {e}")
                        
                    # 3. Add to SQLite
                    tasks = summary_data.get("tasks", [])
                    reminders = summary_data.get("reminders", [])
                    names = summary_data.get("people", [])
                    projects = summary_data.get("projects", [])
                    action_items = summary_data.get("action_items", [])
                    keywords = summary_data.get("keywords", [])
                    short_summary = summary_data.get("short_summary", "")
                    detailed_summary = summary_data.get("detailed_summary", "")
                    important_points = summary_data.get("important_points", [])
                    
                    speaker_segments = [{
                        "speaker": "Speaker 1",
                        "start": 0.0,
                        "end": duration,
                        "transcript": transcript
                    }]
                    
                    try:
                        from backend.memory_sqlite import add_audio_recording
                        add_audio_recording(
                            recording_path=file_path,
                            duration=duration,
                            transcript=transcript,
                            summary=detailed_summary if detailed_summary else short_summary,
                            tasks=tasks,
                            reminders=reminders,
                            names=names,
                            projects=projects,
                            action_items=action_items,
                            keywords=keywords,
                            confidence=confidence,
                            speaker_segments=speaker_segments,
                            status="completed",
                            mode=self.mode,
                            mic_used=self.get_active_mic_name(),
                            sample_rate=self.sample_rate,
                            important_points=important_points
                        )
                    except Exception as e:
                        logger.error(f"Failed to index recording in SQLite: {e}")
                        
                self._processing_queue.task_done()
                
            except Exception as e:
                logger.error(f"[AUDIO SERVICE] Error in processing loop: {e}")
                time.sleep(1.0)
                
        logger.info("[AUDIO SERVICE] Processing worker stopped.")

    def start_manual_recording(self, mode: str = "continuous"):
        """Starts a manual recording session with a specific mode."""
        self.mode = mode
        if mode == "lecture":
            self.max_chunk_seconds = 1800.0  # 30 minute segments for lectures
        else:
            self.max_chunk_seconds = 300.0   # 5 minute segments
            
        self.enable_recording(True)
        logger.info(f"[AUDIO SERVICE] Manual recording started (mode={mode}).")

    def stop_manual_recording(self):
        """Stops the manual recording session."""
        self.enable_recording(False)
        logger.info("[AUDIO SERVICE] Manual recording stopped.")

    def get_active_mic_name(self) -> str:
        """Gets the name of the currently active microphone."""
        mics = self.get_microphones()
        selected_idx = self.device_index
        if selected_idx is not None:
            for m in mics:
                if m["index"] == selected_idx:
                    return m["name"]
        else:
            for m in mics:
                if m.get("is_default"):
                    return m["name"]
        return "Default System Microphone"

    def _apply_dsp(self, data: bytes) -> bytes:
        """
        Applies voice-optimized digital signal processing:
        1. Bandpass Filter (300Hz - 3400Hz) to remove background noise.
        2. Software Automatic Gain Control (AGC) to boost distant speakers.
        """
        count = len(data) // 2
        if count <= 0:
            return data
            
        try:
            samples = list(struct.unpack(f"{count}h", data))
            
            # Simple digital high-pass filter (RC filter approximation for 300Hz cut-off)
            alpha = 0.95
            prev_x = self._hp_prev_input
            prev_y = self._hp_prev_output
            
            for i in range(len(samples)):
                x = samples[i]
                y = alpha * (prev_y + x - prev_x)
                prev_x = x
                prev_y = y
                samples[i] = int(y)
                
            self._hp_prev_input = prev_x
            self._hp_prev_output = prev_y
            
            # Calculate RMS loudness for AGC
            sum_squares = sum(s * s for s in samples)
            rms = math.sqrt(sum_squares / count)
            
            # Software Automatic Gain Control (Target RMS: 3500)
            target_rms = 3500.0
            noise_floor = 150.0
            
            if rms > noise_floor:
                gain = target_rms / rms
                gain = min(3.5, max(1.0, gain))
                
                for i in range(len(samples)):
                    val = int(samples[i] * gain)
                    samples[i] = min(32767, max(-32768, val))
                    
            return struct.pack(f"{count}h", *samples)
        except Exception as e:
            logger.debug(f"[AUDIO SERVICE] DSP error: {e}")
            return data

    def _deferred_processor_loop(self):
        """Periodically retries transcription and summarization for pending records."""
        logger.info("[AUDIO SERVICE] Deferred processor loop started.")
        
        vosk_model = None
        
        while True:
            # Check running flag
            with self._state_lock:
                if not self._running:
                    break
            
            try:
                # 1. Scan DB for pending tasks
                from backend.memory_sqlite import get_audio_recordings, add_audio_recording, update_recording_status
                all_recs = get_audio_recordings()
                
                pending_trans = [r for r in all_recs if r.get("status") == "pending"]
                pending_sum = [r for r in all_recs if r.get("status") == "pending_summary"]
                
                # 2. Try to process pending transcriptions
                if pending_trans:
                    if vosk_model is None:
                        try:
                            import vosk
                            from tools.voice_stt import VOSK_MODEL_PATH, ensure_vosk_model
                            if ensure_vosk_model():
                                vosk_model = vosk.Model(str(VOSK_MODEL_PATH))
                        except Exception as e:
                            logger.debug(f"[AUDIO SERVICE] Deferred processing failed to load Vosk model: {e}")
                            
                    if vosk_model is not None:
                        for r in pending_trans:
                            file_path = r["recording_path"]
                            if os.path.exists(file_path):
                                logger.info(f"[AUDIO SERVICE] Deferred processing: transcribing {file_path}")
                                transcript, words, confidence = self._transcribe_file(file_path, vosk_model)
                                if transcript.strip():
                                    transcript_data = {
                                        "file_path": file_path,
                                        "duration": r["duration"],
                                        "transcript": transcript,
                                        "confidence": confidence,
                                        "words": words
                                    }
                                    transcript_path = file_path.replace(".wav", "_transcript.json")
                                    with open(transcript_path, "w", encoding="utf-8") as f:
                                        json.dump(transcript_data, f, indent=4)
                                        
                                    update_recording_status(r["id"], "pending_summary")
                                    r["status"] = "pending_summary"
                                    r["transcript"] = transcript
                                    pending_sum.append(r)
                                    
                # 3. Try to process pending summaries (checks if Ollama is online)
                if pending_sum:
                    from backend.ollama_manager import ollama_manager
                    if ollama_manager.get_status().get("status") == "connected":
                        for r in pending_sum:
                            file_path = r["recording_path"]
                            transcript = r.get("transcript", "")
                            if not transcript:
                                transcript_path = file_path.replace(".wav", "_transcript.json")
                                if os.path.exists(transcript_path):
                                    try:
                                        with open(transcript_path, "r", encoding="utf-8") as f:
                                            td = json.load(f)
                                            transcript = td.get("transcript", "")
                                    except Exception as e:
                                        logger.debug(f"[AUDIO SERVICE] Failed to read transcript JSON: {e}")
                                        
                            if transcript:
                                logger.info(f"[AUDIO SERVICE] Deferred processing: summarizing {file_path}")
                                summary_data = self._summarize_transcript(transcript)
                                if summary_data.get("short_summary") != "No summary available.":
                                    summary_path = file_path.replace(".wav", "_summary.json")
                                    with open(summary_path, "w", encoding="utf-8") as f:
                                        json.dump(summary_data, f, indent=4)
                                        
                                    add_audio_recording(
                                        recording_path=file_path,
                                        duration=r["duration"],
                                        transcript=transcript,
                                        summary=summary_data.get("detailed_summary") or summary_data.get("short_summary"),
                                        tasks=summary_data.get("tasks", []),
                                        reminders=summary_data.get("reminders", []),
                                        names=summary_data.get("people", []),
                                        projects=summary_data.get("projects", []),
                                        action_items=summary_data.get("action_items", []),
                                        keywords=summary_data.get("keywords", []),
                                        confidence=r.get("confidence", 1.0),
                                        speaker_segments=[{
                                            "speaker": "Speaker 1",
                                            "start": 0.0,
                                            "end": r["duration"],
                                            "transcript": transcript
                                        }],
                                        status="completed",
                                        mode=r.get("mode", "continuous"),
                                        mic_used=r.get("mic_used", "Default"),
                                        sample_rate=r.get("sample_rate", 16000),
                                        important_points=summary_data.get("important_points", [])
                                    )
                                    
            except Exception as ex:
                logger.error(f"[AUDIO SERVICE] Error in deferred processor loop: {ex}")
                
            time.sleep(30.0)
            
        logger.info("[AUDIO SERVICE] Deferred processor loop stopped.")

    def _transcribe_file(self, file_path: str, model) -> tuple:
        """Transcribes a WAV file using Vosk (offline-first) with word-level timestamps."""
        transcript_parts = []
        words = []
        confidence_sum = 0.0
        confidence_count = 0
        
        if not model:
            # Fallback: if Vosk is not available, we can't do offline transcription.
            # We could try online SpeechRecognition if internet is available.
            try:
                import speech_recognition as sr
                r = sr.Recognizer()
                with sr.AudioFile(file_path) as source:
                    audio = r.record(source)
                text = r.recognize_google(audio)
                logger.info(f"[AUDIO SERVICE] Online fallback STT: {text}")
                return text, [], 0.8
            except Exception as e:
                logger.error(f"[AUDIO SERVICE] Online fallback STT failed: {e}")
                return "", [], 0.0
                
        try:
            import vosk
            wf = wave.open(file_path, "rb")
            if wf.getnchannels() != self.channels or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                logger.error("[AUDIO SERVICE] Audio file must be WAV format mono PCM.")
                return "", [], 0.0
                
            rec = vosk.KaldiRecognizer(model, wf.getframerate())
            rec.SetWords(True) # Enable word-level timestamps
            
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = res.get("text", "").strip()
                    if text:
                        transcript_parts.append(text)
                    # Extract words
                    for w in res.get("result", []):
                        words.append({
                            "word": w.get("word"),
                            "start": w.get("start"),
                            "end": w.get("end"),
                            "confidence": w.get("conf")
                        })
                        confidence_sum += w.get("conf", 1.0)
                        confidence_count += 1
                        
            # Final result
            res = json.loads(rec.FinalResult())
            text = res.get("text", "").strip()
            if text:
                transcript_parts.append(text)
            for w in res.get("result", []):
                words.append({
                    "word": w.get("word"),
                    "start": w.get("start"),
                    "end": w.get("end"),
                    "confidence": w.get("conf")
                })
                confidence_sum += w.get("conf", 1.0)
                confidence_count += 1
                
            wf.close()
            
            full_transcript = " ".join(transcript_parts).strip()
            avg_confidence = confidence_sum / confidence_count if confidence_count > 0 else 1.0
            
            # Simple punctuation restoration (first letter capitalization, period at end)
            if full_transcript:
                full_transcript = full_transcript[0].upper() + full_transcript[1:] + "."
                
            logger.info(f"[AUDIO SERVICE] Transcribed {len(words)} words. Confidence: {avg_confidence:.2f}")
            return full_transcript, words, avg_confidence
            
        except Exception as e:
            logger.error(f"[AUDIO SERVICE] Vosk transcription failed: {e}")
            return "", [], 0.0

    def _summarize_transcript(self, transcript: str) -> Dict[str, Any]:
        """Asks local Ollama LLM to generate summary and extract metadata."""
        default_summary = {
            "short_summary": "No summary available.",
            "detailed_summary": "No detailed summary available.",
            "tasks": [],
            "reminders": [],
            "people": [],
            "projects": [],
            "action_items": [],
            "keywords": []
        }
        
        try:
            # Setup prompt
            prompt = f"""
Analyze the following transcript of a conversation captured by a background microphone.
Provide a structured analysis in JSON format with the following keys:
- short_summary: A 1-2 sentence summary of the conversation.
- detailed_summary: A detailed paragraph explaining what was discussed.
- tasks: A list of tasks mentioned that the user needs to do.
- reminders: A list of reminders or events mentioned.
- people: A list of people mentioned (names).
- projects: A list of project names mentioned.
- action_items: A list of action items or next steps.
- keywords: A list of 5-8 keywords or tags.

Ensure the output is strictly valid JSON and nothing else. Do not wrap the JSON in markdown code blocks.

Transcript:
{transcript}
"""
            # Call Ollama
            from backend.llm_client import OllamaClient
            client = OllamaClient()
            
            # We can run the request through the client. We want it to bypass system prompt rules
            # so it returns raw JSON. We can call MultiModelRouter directly:
            resp = client.router.chat_sync(
                history=[],
                prompt=prompt,
                system_prompt="You are a precise data extractor. You must output ONLY valid JSON matching the requested schema. Do not output markdown, explanations, or code blocks."
            )
            
            # Parse response
            resp_text = resp.strip()
            
            # Remove markdown code block wraps if present
            if resp_text.startswith("```json"):
                resp_text = resp_text[7:]
            elif resp_text.startswith("```"):
                resp_text = resp_text[3:]
            if resp_text.endswith("```"):
                resp_text = resp_text[:-3]
                
            resp_text = resp_text.strip()
            
            # Try loading JSON
            data = json.loads(resp_text)
            
            # Validate keys
            for key in default_summary:
                if key not in data:
                    data[key] = default_summary[key]
                    
            logger.info("[AUDIO SERVICE] Successfully generated AI summary and metadata.")
            return data
            
        except Exception as e:
            logger.error(f"[AUDIO SERVICE] LLM summarization failed: {e}")
            # Try a simple regex/rule-based fallback
            return default_summary

# Global singleton
audio_memory_service = AudioMemoryService()
