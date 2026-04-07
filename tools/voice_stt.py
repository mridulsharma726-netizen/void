"""
VOID STT (Speech-to-Text) Module
Safe import with fallback.
"""

SR_AVAILABLE = False
sr = None

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    pass

# Import TTS state checker (safe)
def is_speaking():
    try:
        from tools.voice_tts import is_speaking
        return is_speaking()
    except:
        return False

class VoiceSTT:
    """
    Safe STT with TTS coordination and module check.
    """
    
    _instance = None
    _recognizer = None
    _microphone = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if VoiceSTT._recognizer is None:
            self._init()
    
    def _init(self):
        "Initialize recognizer and microphone if available."

        if not SR_AVAILABLE:
            print("[VOID STT] SpeechRecognition not available")
            return

        try:
            VoiceSTT._recognizer = sr.Recognizer()
            VoiceSTT._microphone = sr.Microphone()
            
            # Calibrate for ambient noise
            with VoiceSTT._microphone as source:
                VoiceSTT._recognizer.adjust_for_ambient_noise(source, duration=0.5)
            
            print("[VOID STT READY] Speech recognition initialized")
        except Exception as e:
            print(f"[STT ERROR] Init failed: {e}")
            VoiceSTT._recognizer = None
            VoiceSTT._microphone = None
    
    def listen_once(self, timeout=5, phrase_time_limit=8):
        """
        Listen for speech and return recognized text.
        SAFE: Checks module availability and TTS state.
        """
        
        # Check module availability
        if not SR_AVAILABLE:
            return {"status": "error", "text": "SpeechRecognition not available"}
        
        # CRITICAL: Check if TTS is speaking
        if is_speaking():
            print("[STT] Skipping - TTS is speaking")
            return {"status": "error", "text": "TTS is speaking, cannot listen"}
        
        if not VoiceSTT._recognizer or not VoiceSTT._microphone:
            print("[STT ERROR] Not initialized")
            return {"status": "error", "text": "Speech recognition not initialized"}
        
        try:
            with VoiceSTT._microphone as source:
                print(f"[STT] Listening...")
                audio = VoiceSTT._recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )
            
            print("[STT] Processing...")
            text = VoiceSTT._recognizer.recognize_google(audio)
            print(f"[STT] Recognized: {text}")
            return {"status": "ok", "text": text}
            
        except sr.WaitTimeoutError:
            print("[STT] Timeout - No speech detected")
            return {"status": "timeout", "text": "No speech detected"}
        except sr.UnknownValueError:
            print("[STT] Speech not understood")
            return {"status": "error", "text": "Could not understand speech"}
        except sr.RequestError as e:
            print(f"[STT ERROR] API error: {e}")
            return {"status": "error", "text": f"Speech API error: {str(e)}"}
        except Exception as e:
            print(f"[STT ERROR] {e}")
            return {"status": "error", "text": str(e)}

# Global singleton
stt = VoiceSTT() if SR_AVAILABLE else None

def listen_once(timeout=5, phrase_time_limit=8):
    "Listen for speech if available."

    if stt is None:
        return {"status": "error", "text": "STT not available"}
    return stt.listen_once(timeout, phrase_time_limit)

def listen():
    "Compatibility wrapper."

    return listen_once()
