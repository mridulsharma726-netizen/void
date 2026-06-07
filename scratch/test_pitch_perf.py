import time
import os
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "server"))

from tools.voice_analyzer import analyze_audio_segment
from backend.emotion_engine import EmotionEngine

def benchmark():
    # Read test.wav if it exists
    wav_path = ROOT_DIR / "test.wav"
    if wav_path.exists():
        with open(wav_path, "rb") as f:
            audio_bytes = f.read()
    else:
        # Create dummy audio bytes (e.g. 5 seconds of 16kHz 16-bit mono audio)
        audio_bytes = bytes([0] * (5 * 16000 * 2))
    
    print(f"Audio length: {len(audio_bytes)} bytes")
    
    # Measure voice analysis
    start = time.perf_counter()
    metrics = analyze_audio_segment(audio_bytes, duration=5.0, word_count=10)
    end = time.perf_counter()
    print(f"Voice analysis took: {(end - start) * 1000:.2f} ms")
    print(f"Metrics: {metrics}")
    
    # Measure emotion engine
    engine = EmotionEngine()
    start = time.perf_counter()
    state = engine.process_turn("This is a test message to analyze emotion", metrics)
    end = time.perf_counter()
    print(f"Emotion engine process_turn took: {(end - start) * 1000:.2f} ms")
    print(f"Active mood state: {state}")

if __name__ == "__main__":
    benchmark()
