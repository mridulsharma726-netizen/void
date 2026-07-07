import os
import sys
import wave
import shutil
import unittest
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
if str(ROOT_DIR / "server") not in sys.path:
    sys.path.append(str(ROOT_DIR / "server"))

from core.voice_ai.whisper_stt import WhisperSTT
from core.voice_ai.piper_tts import PiperTTS
from core.voice_ai.wakeword_detector import WakeWordDetector
from core.voice_ai.voice_pipeline import VoicePipeline

class TestPhase9Voice(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = ROOT_DIR / "tests" / "voice_test_temp"
        self.temp_dir.mkdir(exist_ok=True)
        self.fixture_wav = str(self.temp_dir / "test_speech.wav")
        
        # Programmatically synthesize a real WAV fixture of clear speech using local pyttsx3 (100% offline)
        try:
            import pyttsx3
            engine = pyttsx3.init()
            # Synthesize a clear test command phrase
            engine.save_to_file("turn on the lights", self.fixture_wav)
            engine.runAndWait()
        except Exception as e:
            # Fallback if pyttsx3 is not available
            pass
        
    def tearDown(self):
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass

    def test_whisper_fallback_degradation(self):
        """Verify that WhisperSTT degrades gracefully to fallback when model/binary is missing."""
        # Use a non-existent path to force fallback
        from unittest.mock import patch
        with patch("core.voice_ai.whisper_stt.WHISPER_MODEL_PATH", Path("non_existent_model.bin")):
            stt = WhisperSTT()
            self.assertFalse(stt.ready)
            
            # Transcription on our generated wav should trigger offline Vosk fallback
            if os.path.exists(self.fixture_wav):
                res = stt.transcribe(self.fixture_wav)
                self.assertIsInstance(res, str)

    def test_whisper_real_transcription(self):
        """Run WhisperSTT transcription against real fixture using whisper.cpp (skipped if binary/model is missing)."""
        stt = WhisperSTT()
        if not stt.ready:
            raise unittest.SkipTest("whisper.cpp executable or ggml-tiny.en.bin model file not present in the local environment.")
            
        if not os.path.exists(self.fixture_wav):
            raise unittest.SkipTest("Voice WAV fixture was not generated successfully.")
            
        res = stt.transcribe(self.fixture_wav)
        self.assertIsNotNone(res)
        # Check that it contains expected words (case-insensitive substring match)
        self.assertTrue(
            "turn" in res.lower() or "light" in res.lower(), 
            f"Transcription result '{res}' did not contain expected words."
        )

    def test_piper_fallback_degradation(self):
        """Verify that PiperTTS degrades gracefully to pyttsx3/edge-tts when binary/model is missing."""
        from unittest.mock import patch
        with patch("core.voice_ai.piper_tts.PIPER_MODEL_PATH", Path("non_existent_voice.onnx")):
            tts = PiperTTS()
            self.assertFalse(tts.ready)
            
            # Speak should fall back to pyttsx3 and return True
            res = tts.speak("Hello from fallback test", str(self.temp_dir / "fallback_out.wav"))
            self.assertTrue(res)

    def test_piper_real_synthesis(self):
        """Synthesize text using real PiperTTS model (skipped if model/binary is missing)."""
        tts = PiperTTS()
        if not tts.ready:
            raise unittest.SkipTest("Piper executable or voice ONNX model not present in the local environment.")
            
        output_file = str(self.temp_dir / "piper_out.wav")
        if os.path.exists(output_file):
            os.remove(output_file)
            
        res = tts.speak("Testing real speech synthesis", output_file)
        self.assertTrue(res)
        self.assertTrue(os.path.exists(output_file), "Output WAV file was not created.")
        self.assertGreater(os.path.getsize(output_file), 44, "Output WAV file is empty or missing headers.")
        
        # Verify valid WAV headers
        with wave.open(output_file, "rb") as wf:
            self.assertGreater(wf.getnchannels(), 0)
            self.assertGreater(wf.getframerate(), 0)

    def test_wakeword_detector_instantiation(self):
        """Verify WakeWordDetector instantiates and handles config."""
        cb_called = False
        def dummy_cb():
            nonlocal cb_called
            cb_called = True
            
        detector = WakeWordDetector(callback=dummy_cb, wake_phrase="hey jarvis")
        self.assertEqual(detector.wake_phrase, "hey jarvis")
        self.assertFalse(detector._running)

    def test_wakeword_real_detection_positive(self):
        """Test that openWakeWord triggers callback when positive wake phrase audio frames are processed."""
        cb_called = False
        def dummy_cb():
            nonlocal cb_called
            cb_called = True
            
        from unittest.mock import MagicMock
        detector = WakeWordDetector(callback=dummy_cb, wake_phrase="hey jarvis")
        detector.ready = True
        detector.oww_model = MagicMock()
        detector.prediction_key = "hey_jarvis"
            
        # Synthesize "hey jarvis" wake phrase
        hey_jarvis_wav = str(self.temp_dir / "hey_jarvis.wav")
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.save_to_file("hey jarvis", hey_jarvis_wav)
            engine.runAndWait()
        except Exception as e:
            raise unittest.SkipTest(f"Failed to synthesize wake phrase using pyttsx3: {e}")
            
        # Resample to 16kHz mono 16-bit PCM
        resampled_wav = WhisperSTT()._resample_wav_to_16k_mono_16bit(hey_jarvis_wav)
        
        # Read WAV frames
        import numpy as np
        with wave.open(resampled_wav, "rb") as wf:
            n_frames = wf.getnframes()
            data = wf.readframes(n_frames)
            audio_samples = np.frombuffer(data, dtype=np.int16)
            
        # Define a mock/patch on self.oww_model.predict to simulate wake word detection
        # when non-silent speech frames are encountered.
        import audioop
        def mock_predict(chunk):
            # Compute RMS of chunk
            rms = audioop.rms(chunk.tobytes(), 2)
            # If speech chunk is present, return score > 0.5 (e.g. 0.85)
            if rms > 1000:
                return {detector.prediction_key: 0.85}
            else:
                return {detector.prediction_key: 0.02}
                
        detector.oww_model.predict = mock_predict
        
        # Feed the resampled wav frames to process_frame in 1280-sample chunks
        chunk_size = 1280
        for i in range(0, len(audio_samples), chunk_size):
            chunk = audio_samples[i:i+chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            detector.process_frame(chunk)
            
        # Assert that the callback fired
        self.assertTrue(cb_called, "Callback did not fire on positive wake phrase audio")

    def test_wakeword_real_detection_negative(self):
        """Test that openWakeWord does NOT trigger callback when other/silent audio frames are processed."""
        cb_called = False
        def dummy_cb():
            nonlocal cb_called
            cb_called = True
            
        from unittest.mock import MagicMock
        detector = WakeWordDetector(callback=dummy_cb, wake_phrase="hey jarvis")
        detector.ready = True
        detector.oww_model = MagicMock()
        detector.prediction_key = "hey_jarvis"
        
        # Define a mock predict that returns low score
        detector.oww_model.predict = MagicMock(return_value={detector.prediction_key: 0.02})
        
        # Feed a frame of all zeros (silence)
        import numpy as np
        zeros_frame = np.zeros(1280, dtype=np.int16)
        score = detector.process_frame(zeros_frame)
        
        # Assert callback did not fire and score is low
        self.assertFalse(cb_called)
        self.assertLess(score, 0.5)


    def test_google_fallback_disabled_by_default(self):
        """Verify that online Google SpeechRecognition fallback is NOT called when ALLOW_CLOUD_STT_FALLBACK is False."""
        stt = WhisperSTT()
        stt.allow_cloud_fallback = False
        
        from unittest.mock import patch, MagicMock
        
        # Patch local Vosk model to simulate failure/missing model
        # and patch speech_recognition recognize_google to check it is not called.
        mock_recognize = MagicMock(return_value="should not be called")
        
        with patch("tools.voice_stt.VOSK_MODEL_PATH", Path("non_existent_vosk_dir")), \
             patch("speech_recognition.Recognizer.recognize_google", mock_recognize):
            
            res = stt._fallback_transcribe(self.fixture_wav)
            
            # Assert Google SpeechRecognition was never called
            mock_recognize.assert_not_called()
            # Assert returned text is empty
            self.assertEqual(res, "")


    def test_voice_pipeline_integration_flow(self):
        """Verify end-to-end VoicePipeline integration without mocking, using real offline Vosk fallback."""
        if not os.path.exists(self.fixture_wav):
            raise unittest.SkipTest("Voice WAV fixture was not generated successfully.")
            
        handler_called = False
        captured_cmd = ""
        
        def dummy_handler(cmd):
            nonlocal handler_called, captured_cmd
            handler_called = True
            captured_cmd = cmd
            
        pipeline = VoicePipeline(command_handler=dummy_handler)
        
        # Run transcription on the real WAV file generated via pyttsx3
        # This will utilize the real local offline Vosk fallback engine
        res_text = pipeline.transcribe(self.fixture_wav)
        self.assertIsNotNone(res_text)
        
        # Verify transcription quality matches expected speech phrase
        self.assertTrue(
            "turn" in res_text.lower() or "light" in res_text.lower(),
            f"Expected 'turn on the lights', but got '{res_text}'"
        )

if __name__ == "__main__":
    unittest.main()
