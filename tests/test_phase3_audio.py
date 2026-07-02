import os
import sys
import json
import unittest
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
if str(ROOT_DIR / "server") not in sys.path:
    sys.path.append(str(ROOT_DIR / "server"))

from server.backend.ollama_manager import OllamaConnectionManager, ollama_manager
from server.backend.audio_memory_service import AudioMemoryService, audio_memory_service
from server.backend.memory_sqlite import (
    init_db,
    add_audio_recording,
    get_audio_recordings,
    get_audio_recording,
    delete_audio_recording,
    toggle_audio_recording_favorite,
    toggle_audio_recording_pinned,
    semantic_search_recordings
)

class TestPhase3Audio(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_ollama_manager_singleton(self):
        """Verify OllamaConnectionManager is a singleton and can check status."""
        mgr = OllamaConnectionManager()
        self.assertIs(mgr, ollama_manager)
        
        status = mgr.get_status()
        self.assertIn("status", status)
        self.assertIn("active_model", status)
        self.assertIn("error_message", status)

    def test_audio_service_singleton(self):
        """Verify AudioMemoryService is a singleton and can list microphones."""
        service = AudioMemoryService()
        self.assertIs(service, audio_memory_service)
        
        # Test toggle
        initial_state = service.is_enabled
        service.enable_recording(not initial_state)
        self.assertEqual(service.is_enabled, not initial_state)
        
        # Restore
        service.enable_recording(initial_state)
        
        # Microphones check
        mics = service.get_microphones()
        self.assertIsInstance(mics, list)

    def test_database_persistence_and_search(self):
        """Verify that we can insert, query, favorite, pin, and search recordings."""
        test_path = str(ROOT_DIR / "tests" / "test_dummy_recording.wav")
        
        # Clean up if exists from prior failed test
        recordings = get_audio_recordings()
        for r in recordings:
            if r["recording_path"] == test_path:
                delete_audio_recording(r["id"])
                
        # Insert test recording
        success = add_audio_recording(
            recording_path=test_path,
            duration=15.5,
            transcript="We need to focus on the payment gateway integration for the Netizen project.",
            summary="Discussion about the Netizen project's payment gateway integration.",
            tasks=["Implement Stripe webhook handler", "Update checkout page design"],
            reminders=["Deploy staging on Friday"],
            names=["Mridul", "John"],
            projects=["Netizen"],
            action_items=["Mridul to configure Stripe keys"],
            keywords=["Netizen", "payment", "Stripe", "gateway"],
            embedding=[0.1] * 128, # mock embedding
            confidence=0.95
        )
        self.assertTrue(success)
        
        # Query list
        recs = get_audio_recordings(search_query="Netizen")
        self.assertGreaterEqual(len(recs), 1)
        
        # Get specific recording
        target_rec = None
        for r in recs:
            if r["recording_path"] == test_path:
                target_rec = r
                break
                
        self.assertIsNotNone(target_rec)
        self.assertEqual(target_rec["duration"], 15.5)
        self.assertIn("payment gateway", target_rec["transcript"])
        self.assertIn("Netizen", target_rec["projects"])
        self.assertIn("Stripe", target_rec["keywords"])
        
        # Test favorite toggle
        self.assertFalse(target_rec["is_favorite"])
        fav_ok = toggle_audio_recording_favorite(target_rec["id"])
        self.assertTrue(fav_ok)
        
        updated_rec = get_audio_recording(target_rec["id"])
        self.assertTrue(updated_rec["is_favorite"])
        
        # Test pin toggle
        self.assertFalse(target_rec["is_pinned"])
        pin_ok = toggle_audio_recording_pinned(target_rec["id"])
        self.assertTrue(pin_ok)
        
        updated_rec = get_audio_recording(target_rec["id"])
        self.assertTrue(updated_rec["is_pinned"])
        
        # Test semantic search
        matches = semantic_search_recordings("payment checkout integration", limit=3)
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["id"], target_rec["id"])
        
        # Test delete
        del_ok = delete_audio_recording(target_rec["id"])
        self.assertTrue(del_ok)
        
        deleted_rec = get_audio_recording(target_rec["id"])
        self.assertIsNone(deleted_rec)

    def test_metrics_collector(self):
        """Verify that SystemMetricsCollector collects all required metrics."""
        from server.backend.metrics_service import metrics_collector
        data = metrics_collector.collect_all()
        
        self.assertIn("system", data)
        self.assertIn("network", data)
        self.assertIn("services", data)
        self.assertIn("memory_stats", data)
        
        # Check system keys
        sys_keys = data["system"]
        self.assertIn("cpu_usage", sys_keys)
        self.assertIn("ram_usage_pct", sys_keys)
        self.assertIn("disk_usage_pct", sys_keys)
        
        # Check services keys
        services = data["services"]
        self.assertIn("backend", services)
        self.assertIn("database", services)
        self.assertIn("recording_service", services)
        self.assertIn("wake_word", services)

    def test_audio_dsp_and_modes(self):
        """Verify AudioMemoryService DSP (AGC and filter) and manual recording modes."""
        service = AudioMemoryService()
        
        # Test mode setting
        service.start_manual_recording("lecture")
        self.assertEqual(service.mode, "lecture")
        self.assertEqual(service.max_chunk_seconds, 1800.0)
        self.assertTrue(service.is_enabled)
        
        # Stop
        service.stop_manual_recording()
        self.assertFalse(service.is_enabled)
        
        # Test DSP on dummy 16-bit PCM bytes
        # 1000 samples of quiet alternating AC audio (values = [200, -200])
        import struct
        quiet_pcm = struct.pack("1000h", *([200, -200] * 500))
        processed = service._apply_dsp(quiet_pcm)
        
        # Since it is quiet (but above noise floor), the AGC should boost it (processed values should be larger than 200)
        processed_samples = struct.unpack("1000h", processed)
        self.assertGreater(abs(processed_samples[10]), 200)

    def test_deferred_processing_and_offline_mode(self):
        """Verify offline pending status and deferred processing loop."""
        service = AudioMemoryService()
        test_path = str(ROOT_DIR / "tests" / "test_deferred_rec.wav")
        
        # Remove if exists
        recordings = get_audio_recordings()
        for r in recordings:
            if r["recording_path"] == test_path:
                delete_audio_recording(r["id"])
                
        # Simulate immediate save as 'pending'
        # In a real offline scenario, the WAV is saved and add_audio_recording is called with status='pending'
        from backend.memory_sqlite import add_audio_recording
        success = add_audio_recording(
            recording_path=test_path,
            duration=5.0,
            transcript="",
            summary="",
            status="pending",
            mode="lecture",
            mic_used="Test Mic",
            sample_rate=16000
        )
        self.assertTrue(success)
        
        # Verify it is in database as pending
        recs = get_audio_recordings()
        target = None
        for r in recs:
            if r["recording_path"] == test_path:
                target = r
                break
                
        self.assertIsNotNone(target)
        self.assertEqual(target["status"], "pending")
        self.assertEqual(target["mode"], "lecture")
        self.assertEqual(target["mic_used"], "Test Mic")
        
        # Verify we can update its status to 'completed'
        from backend.memory_sqlite import update_recording_status
        up_ok = update_recording_status(target["id"], "completed")
        self.assertTrue(up_ok)
        
        updated = get_audio_recording(target["id"])
        self.assertEqual(updated["status"], "completed")
        
        # Test bookmarking
        from backend.memory_sqlite import add_bookmark
        bm_ok = add_bookmark(target["id"], 2.5, "Important Definition")
        self.assertTrue(bm_ok)
        
        bookmarked = get_audio_recording(target["id"])
        self.assertEqual(len(bookmarked["bookmarks"]), 1)
        self.assertEqual(bookmarked["bookmarks"][0]["label"], "Important Definition")
        self.assertEqual(bookmarked["bookmarks"][0]["timestamp"], 2.5)
        
        # Clean up
        delete_audio_recording(target["id"])

if __name__ == "__main__":
    unittest.main()
