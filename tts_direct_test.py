import os
import asyncio
import tempfile
import subprocess
import edge_tts

FFPLAY_PATH = r"C:\Users\HP\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffplay.exe"

async def main():
    print("FFPLAY:", FFPLAY_PATH)
    print("exists:", os.path.exists(FFPLAY_PATH))

    out = os.path.join(tempfile.gettempdir(), "void_test.wav")

    communicate = edge_tts.Communicate(
        text="Hello Mridul sir. VOID direct test.",
        voice="en-IN-PrabhatNeural"
    )
    await communicate.save(out)

    print("saved:", out)
    print("size:", os.path.getsize(out))

    print("playing with ffplay...")
    subprocess.run([FFPLAY_PATH, "-nodisp", "-autoexit", out])

asyncio.run(main())
