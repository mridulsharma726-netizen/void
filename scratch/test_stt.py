import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tools import voice_stt

print("Initializing VoiceSTT...")
res = voice_stt.listen_once(timeout=3, phrase_time_limit=3)
print("STT Result:")
print(res)
