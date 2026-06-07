"""
VOID Voice Namespace
===================

Exposes wake word detectors, voice listener loops, STT offline models, and SAPI TTS speaker.
"""

from tools.voice_tts import speak, stop as stop_speaking
from tools.voice_stt import listen_once, listen
from tools.voice_listener import start_voice_loop
from tools.wake_word import listen_for_wake_word
