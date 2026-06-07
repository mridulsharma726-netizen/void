import speech_recognition as sr
import threading
import concurrent.futures
import time
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent

def test_google_dialects():
    wav_path = ROOT_DIR / "test.wav"
    if not wav_path.exists():
        print("test.wav not found in workspace root.")
        return
        
    with open(wav_path, "rb") as f:
        raw_bytes = f.read()
        
    recognizer = sr.Recognizer()
    # Create AudioData directly from raw PCM bytes
    audio = sr.AudioData(raw_bytes, 16000, 2)
        
    dialects = ["en-US", "en-IN", "en-GB"]
    
    def recognize_one(dialect):
        try:
            print(f"Starting recognition for {dialect}...")
            start = time.perf_counter()
            # Pass show_all=True to get detailed alternative hypothesis and confidence
            result = recognizer.recognize_google(audio, language=dialect, show_all=True)
            end = time.perf_counter()
            print(f"Finished {dialect} in {(end - start) * 1000:.2f} ms")
            return dialect, result
        except Exception as e:
            return dialect, {"error": str(e)}
            
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(recognize_one, d) for d in dialects]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
    for dialect, res in results:
        print(f"\nDialect: {dialect}")
        print(f"Result: {res}")

if __name__ == "__main__":
    test_google_dialects()
