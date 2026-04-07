"""
VOID TTS Subprocess Speaker
Safe pyttsx3 launcher - fails gracefully if module missing.
"""

try:
    import pyttsx3
    PYTTsx3_AVAILABLE = True
except ImportError:
    PYTTsx3_AVAILABLE = False

import sys

# Get text from command line arguments
text = " ".join(sys.argv[1:])

if not text:
    print("[TTS SPEAKER] No text provided")
    sys.exit(0)

if not PYTTsx3_AVAILABLE:
    print("[TTS SPEAKER ERROR] pyttsx3 not available")
    sys.exit(1)

try:
    # Initialize engine
    engine = pyttsx3.init()
    engine.setProperty("rate", 175)
    engine.setProperty("volume", 1.0)
    
    # Set voice
    voices = engine.getProperty("voices")
    if voices:
        engine.setProperty("voice", voices[0].id)
    
    # Speak and wait
    engine.say(text)
    engine.runAndWait()
    
    print("[TTS SPEAKER] Speech complete")
    
except Exception as e:
    print(f"[TTS SPEAKER ERROR] {str(e)}")
    sys.exit(1)
