import sys
import os
import asyncio
import math
import struct

# Setup paths
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(ROOT)
sys.path.append(os.path.join(ROOT, "server"))

from tools.voice_analyzer import estimate_pitch, calculate_rms, calculate_wpm, analyze_audio_segment
from backend.emotion_engine import EmotionEngine, ACTIVE_MOOD

def generate_mock_sine_wave(frequency: float, duration: float, sample_rate: int = 16000) -> bytes:
    """Generates a dummy sine wave PCM buffer at a specific frequency for pitch test."""
    num_samples = int(sample_rate * duration)
    amplitude = 12000 # High volume
    data = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        sample = int(amplitude * math.sin(2.0 * math.pi * frequency * t))
        data.extend(struct.pack("h", sample))
    return bytes(data)

def test_voice_analyzer():
    print("=== Testing Voice Feature Extraction ===")
    
    # Generate 150Hz mock voice segment
    target_freq = 150.0
    audio_bytes = generate_mock_sine_wave(target_freq, 0.4)
    
    # Extract features
    pitch = estimate_pitch(audio_bytes)
    rms = calculate_rms(audio_bytes)
    wpm = calculate_wpm(10, 3.0) # 10 words spoken in 3 seconds -> 200 WPM
    
    print(f"  Sine wave frequency: {target_freq} Hz")
    print(f"  -> Extracted Pitch:  {pitch:.1f} Hz")
    print(f"  -> Extracted RMS:    {rms:.1f}")
    print(f"  -> Extracted WPM:    {wpm:.1f} WPM")
    
    combined = analyze_audio_segment(audio_bytes, 3.0, 10)
    print("  Combined Audio Analysis:")
    print(f"    Pitch Level:  {combined['pitch_level']} ({combined['pitch_hz']} Hz)")
    print(f"    Energy Level: {combined['energy_level']} ({combined['energy_rms']} RMS)")
    print(f"    WPM Level:    {combined['wpm']} WPM")
    print()

def test_emotion_scoring():
    print("=== Testing Emotion Scoring & Confidence Calculations ===")
    engine = EmotionEngine()
    
    test_cases = [
        # Lexical stressed + high pitch + fast WPM
        ("This code is broken and it fails every time. Why is it failing?", 
         {"pitch_hz": 230.0, "pitch_level": "Elevated", "energy_rms": 4500.0, "energy_level": "High", "wpm": 210.0}),
         
        # Lexical confused + slow WPM
        ("I don't understand how this heapify works. Can you explain why it does that?", 
         {"pitch_hz": 120.0, "pitch_level": "Normal", "energy_rms": 1500.0, "energy_level": "Normal", "wpm": 95.0}),
         
        # Lexical motivated + normal voice
        ("Great! I am excited to learn how to make custom roadmaps.", 
         {"pitch_hz": 160.0, "pitch_level": "Normal", "energy_rms": 2500.0, "energy_level": "Normal", "wpm": 140.0}),
         
        # Normal chat
        ("hello void whats up?", None)
    ]
    
    for text, voice_metrics in test_cases:
        res = engine.process_turn(text, voice_metrics)
        modifier = EmotionEngine.get_system_prompt_modifier()
        print(f"  Input Text: \"{text}\"")
        if voice_metrics:
            print(f"    Voice metrics: Pitch={voice_metrics['pitch_hz']}Hz, WPM={voice_metrics['wpm']}")
        print(f"    -> Estimated Mood: {res['mood']} ({res['confidence']}%)")
        print(f"    -> Adaptive State: {res['adaptive_state']}")
        if modifier:
            print(f"    -> Prompt Modifier: \"{modifier.strip()[:100]}...\"")
        print()

def main():
    test_voice_analyzer()
    test_emotion_scoring()

if __name__ == "__main__":
    main()
