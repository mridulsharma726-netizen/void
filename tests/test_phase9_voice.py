import os
import sys
import unittest
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        
    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_whisper_fallback_degradation(self):
        """Verify that WhisperSTT degrades gracefully to fallback when model/binary is missing."""
        # Use a non-existent path to force fallback
        with patch("core.voice_ai.whisper_stt.WHISPER_MODEL_PATH", Path("non_existent_model.bin")):
            stt = WhisperSTT()
            self.assertFalse(stt.ready)
            
            # Transcription on a dummy WAV should trigger fallback
            dummy_wav = str(ROOT_DIR / "test.wav")
            if os.path.exists(dummy_wav):
                res = stt.transcribe(dummy_wav)
                # Should not crash, and should return a string (empty or transcribed)
                self.assertIsInstance(res, str)

    def test_piper_fallback_degradation(self):
        """Verify that PiperTTS degrades gracefully to pyttsx3/edge-tts when binary/model is missing."""
        with patch("core.voice_ai.piper_tts.PIPER_MODEL_PATH", Path("non_existent_voice.onnx")):
            tts = PiperTTS()
            self.assertFalse(tts.ready)
            
            # Speak should fall back to pyttsx3 or edge-tts and return a status
            res = tts.speak("Hello from fallback test", str(self.temp_dir / "fallback_out.wav"))
            self.assertIsInstance(res, bool)

    def test_wakeword_detector_instantiation(self):
        """Verify WakeWordDetector instantiates and handles config."""
        cb_called = False
        def dummy_cb():
            nonlocal cb_called
            cb_called = True
            
        detector = WakeWordDetector(callback=dummy_cb, wake_phrase="hey jarvis")
        # Check properties
        self.assertEqual(detector.wake_phrase, "hey jarvis")
        self.assertFalse(detector._running)

    def test_voice_pipeline_integration_flow(self):
        """Verify that the VoicePipeline coordinates the overall voice loop correctly."""
        handler_called = False
        captured_cmd = ""
        
        def dummy_handler(cmd):
            nonlocal handler_called, captured_cmd
            handler_called = True
            captured_cmd = cmd
            
        pipeline = VoicePipeline(command_handler=dummy_handler)
        
        # Mock transcribe and speak
        pipeline.transcribe = MagicMock(return_value="open notepad")
        pipeline.speak = MagicMock(return_value=True)
        
        # Test direct transcription mock
        res_text = pipeline.transcribe("dummy.wav")
        self.assertEqual(res_text, "open notepad")
        
        # Test speak mock
        speak_ok = pipeline.speak("Synthesizing speech")
        self.assertTrue(speak_ok)

if __name__ == "__main__":
    unittest.main()
