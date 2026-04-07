import asyncio
import edge_tts

async def main():
    text = "Hello Mridul sir. VOID is online."
    voice = "en-IN-PrabhatNeural"
    out = "test.wav"

    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(out)
    print("Saved:", out)

asyncio.run(main())
