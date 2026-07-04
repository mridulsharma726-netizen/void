import logging
import asyncio
import os
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from server.dependencies import (
    VoidSingletons, PermissionManager, DATA_DIR, ROOT_DIR, STATS
)

# Voice tool imports
from tools.voice_tts import speak as tts_speak, stop as tts_stop, is_speaking as tts_is_speaking
from tools.voice_stt import listen_once

logger = logging.getLogger("void.routes.voice")

router = APIRouter()


class PersonalityRequest(BaseModel):
    name: str


@router.post("/speak")
async def speak(req: Dict[str, str]):
    text = req.get("text", "")
    if not text: return {"reply": "Nothing to say", "meta": {"status": "error"}}
    try:
        tts_speak(text)
        return {"reply": "Speaking...", "meta": {"text": text}}
    except Exception as e:
        return {"reply": "TTS error", "meta": {"error": str(e)}}


@router.post("/stop-speak")
async def stop_speak():
    try:
        tts_stop()
        return {"reply": "Stopped speaking", "meta": {"status": "ok"}}
    except Exception as e:
        return {"reply": "Stop error", "meta": {"error": str(e)}}


@router.get("/speak-status")
async def speak_status():
    try:
        return {"speaking": tts_is_speaking()}
    except Exception as e:
        return {"speaking": False, "error": str(e)}


@router.get("/voice/personalities")
async def get_voice_personalities():
    from core.voice_ai.voice_profile import VoiceProfileManager
    mgr = VoiceProfileManager()
    return mgr.list_personalities()



# [Extracted Voice Route Block]


@router.post("/voice/personalities")
async def set_voice_personality(req: PersonalityRequest):
    from core.voice_ai.voice_profile import VoiceProfileManager
    mgr = VoiceProfileManager()
    res = mgr.set_personality(req.name)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

# ProfileRequest moved to routes/memory.py


# [Extracted Memory Route Block]


# [Extracted Memory Route Block]


# [Extracted Automation Route Block]


# [Extracted Automation Route Block]


# [Extracted Automation Route Block]


# [Extracted Automation Route Block]


@router.get("/listen")
async def listen():
    try:
        res = await asyncio.to_thread(listen_once)
        return {"reply": res.get("text", ""), "meta": res}
    except Exception as e:
        return {"reply": "STT error", "meta": {"error": str(e)}}


@router.get("/mic-level")
async def mic_level():
    try:
        from tools.voice_stt import stt
        if stt:
            return stt.get_mic_status()
        return {"active": False, "rms": 0.0, "level_pct": 0.0}
    except Exception as e:
        return {"active": False, "rms": 0.0, "level_pct": 0.0, "error": str(e)}


@router.get("/api/voice/wake-word/status")
async def get_wake_word_status():
    try:
        from tools.voice_listener import is_listening
        return {"active": is_listening()}
    except Exception as e:
        logger.error(f"Error checking wake word status: {e}")
        return {"active": False, "error": str(e)}


@router.post("/api/voice/wake-word/toggle")
async def toggle_wake_word(req: dict = None):
    global _voice_thread
    try:
        from tools.voice_listener import is_listening, stop_voice_loop, start_voice_loop_thread
        
        target = None
        if req and "active" in req:
            target = req["active"]
            
        current = is_listening()
        if target is None:
            target = not current
            
        if target == current:
            return {"active": current}
            
        if target:
            from tools.voice_listener import set_command_callback, set_activation_phrase
            from server.main import process_voice_command
            set_activation_phrase("Yes?")
            set_command_callback(process_voice_command)
            _voice_thread = start_voice_loop_thread()
            # Wait briefly to let it start and set _listening = True
            await asyncio.sleep(0.5)
        else:
            stop_voice_loop()
            # Wait briefly to let it stop
            await asyncio.sleep(0.5)
            
        return {"active": is_listening()}
    except Exception as e:
        logger.error(f"Error toggling wake word: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/voice/wake-word/fix-ducking")
async def fix_audio_ducking():
    try:
        import platform
        if platform.system() != "Windows":
            return {"status": "error", "message": "Audio ducking configuration is only supported on Windows."}
            
        import winreg
        key_path = r"Software\Microsoft\Multimedia\Audio"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        except FileNotFoundError:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            
        # 3 = Do nothing when communications activity is detected
        winreg.SetValueEx(key, "UserDuckingPreference", 0, winreg.REG_DWORD, 3)
        winreg.CloseKey(key)
        
        logger.info("[VOICE ENGINE] Registry fix applied: UserDuckingPreference set to 3 (Do nothing)")
        return {"status": "success", "message": "Windows Communications Ducking preference updated to 'Do Nothing'. Please restart the system or browser/application for the changes to fully apply."}
    except Exception as e:
        logger.error(f"Failed to fix audio ducking: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update registry: {str(e)}")


# ===========================================================================
# OLLAMA & AUDIO RECORDING & GLOBAL SEARCH ENDPOINTS (Phase 3)
# ===========================================================================


# [Extracted Chat Route Block]


# [Extracted Chat Route Block]


@router.get("/api/recordings")
async def get_recordings_list(q: str = "", limit: int = 50, offset: int = 0):
    try:
        from backend.memory_sqlite import get_audio_recordings
        recordings = get_audio_recordings(search_query=q, limit=limit, offset=offset)
        return {"status": "ok", "recordings": recordings}
    except Exception as e:
        logger.error(f"Error listing recordings: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/api/recordings/{id}")
async def get_recording_detail(id: int):
    try:
        from backend.memory_sqlite import get_audio_recording
        recording = get_audio_recording(id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
            
        # Load word-level timestamps from transcript JSON if available
        words = []
        import json
        json_path = recording["recording_path"].replace(".wav", "_transcript.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    words = data.get("words", [])
            except Exception as ex:
                logger.warning(f"Could not read transcript JSON: {ex}")
        recording["words"] = words
        
        return {"status": "ok", "recording": recording}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recording detail: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/api/recordings/{id}/audio")
async def get_recording_audio(id: int):
    try:
        from backend.memory_sqlite import get_audio_recording
        recording = get_audio_recording(id)
        if not recording or not os.path.exists(recording["recording_path"]):
            raise HTTPException(status_code=404, detail="Audio file not found")
        from fastapi.responses import FileResponse
        return FileResponse(recording["recording_path"], media_type="audio/wav")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming recording audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/recordings/{id}")
async def delete_recording(id: int):
    try:
        from backend.memory_sqlite import get_audio_recording, delete_audio_recording
        recording = get_audio_recording(id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
        
        # Delete local files
        path = recording["recording_path"]
        for suffix in [".wav", "_transcript.json", "_summary.json"]:
            file_to_del = path if suffix == ".wav" else path.replace(".wav", suffix)
            try:
                if os.path.exists(file_to_del):
                    os.remove(file_to_del)
            except Exception as e:
                logger.warning(f"Could not delete file {file_to_del}: {e}")
                
        success = delete_audio_recording(id)
        return {"status": "ok" if success else "error"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting recording: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/recordings/toggle")
async def toggle_recordings(req: dict = None):
    try:
        from backend.audio_memory_service import audio_memory_service
        active = req.get("active") if req else None
        if active is None:
            active = not audio_memory_service.is_enabled
        audio_memory_service.enable_recording(active)
        return {"status": "ok", "active": audio_memory_service.is_enabled}
    except Exception as e:
        logger.error(f"Error toggling background recording: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/api/recordings/status")
async def get_recordings_status():
    try:
        from backend.audio_memory_service import audio_memory_service
        mics = audio_memory_service.get_microphones()
        return {
            "status": "ok",
            "active": audio_memory_service.is_enabled,
            "microphones": mics,
            "current_device": audio_memory_service.device_index
        }
    except Exception as e:
        logger.error(f"Error getting recordings status: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/recordings/select-device")
async def select_recording_device(req: dict = None):
    try:
        index = req.get("index") if req else None
        if index is None:
            raise HTTPException(status_code=400, detail="index is required")
        from backend.audio_memory_service import audio_memory_service
        audio_memory_service.select_device(index)
        return {"status": "ok", "current_device": audio_memory_service.device_index}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selecting recording device: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/recordings/{id}/favorite")
async def toggle_favorite_recording(id: int):
    try:
        from backend.memory_sqlite import toggle_audio_recording_favorite
        success = toggle_audio_recording_favorite(id)
        return {"status": "ok" if success else "error"}
    except Exception as e:
        logger.error(f"Error favoriting recording {id}: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/recordings/{id}/pin")
async def toggle_pin_recording(id: int):
    try:
        from backend.memory_sqlite import toggle_audio_recording_pinned
        success = toggle_pin_recording(id)
        return {"status": "ok" if success else "error"}
    except Exception as e:
        logger.error(f"Error pinning recording {id}: {e}")
        return {"status": "error", "message": str(e)}

# /api/metrics extracted to routes/admin.py


@router.post("/api/recordings/start")
async def start_recording_api(req: dict = None):
    try:
        mode = req.get("mode", "continuous") if req else "continuous"
        from backend.audio_memory_service import audio_memory_service
        audio_memory_service.start_manual_recording(mode)
        return {"status": "ok", "active": True, "mode": mode}
    except Exception as e:
        logger.error(f"Error starting manual recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/recordings/stop")
async def stop_recording_api():
    try:
        from backend.audio_memory_service import audio_memory_service
        audio_memory_service.stop_manual_recording()
        return {"status": "ok", "active": False}
    except Exception as e:
        logger.error(f"Error stopping manual recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/recordings/{id}/bookmark")
async def add_recording_bookmark_api(id: int, req: dict = None):
    try:
        timestamp = req.get("timestamp", 0.0) if req else 0.0
        label = req.get("label", "Bookmark") if req else "Bookmark"
        from backend.memory_sqlite import add_bookmark
        success = add_bookmark(id, timestamp, label)
        return {"status": "ok" if success else "error"}
    except Exception as e:
        logger.error(f"Error adding bookmark: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/recordings/{id}/rename")
async def rename_recording_api(id: int, req: dict = None):
    try:
        title = req.get("title") if req else None
        if not title:
            raise HTTPException(status_code=400, detail="title is required")
        from backend.memory_sqlite import get_audio_recording
        recording = get_audio_recording(id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
        
        old_path = Path(recording["recording_path"])
        import re
        clean_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title)
        new_name = f"{clean_title}.wav"
        new_path = old_path.parent / new_name
        
        if old_path.exists():
            os.rename(old_path, new_path)
            
        for suffix in ["_transcript.json", "_summary.json"]:
            old_json = Path(str(old_path).replace(".wav", suffix))
            new_json = Path(str(new_path).replace(".wav", suffix))
            if old_json.exists():
                os.rename(old_json, new_json)
                
        from backend.memory_sqlite import DB_FILE
        import sqlite3
        conn = sqlite3.connect(str(DB_FILE))
        cursor = conn.cursor()
        cursor.execute("UPDATE audio_recordings SET recording_path = ? WHERE id = ?", (str(new_path), id))
        conn.commit()
        conn.close()
        
        return {"status": "ok", "new_path": str(new_path)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renaming recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/recordings/{id}/export/{format}")
async def export_recording_api(id: int, format: str):
    try:
        from backend.memory_sqlite import get_audio_recording
        recording = get_audio_recording(id)
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")
            
        if format == "audio":
            if not os.path.exists(recording["recording_path"]):
                raise HTTPException(status_code=404, detail="Audio file not found")
            from fastapi.responses import FileResponse
            return FileResponse(recording["recording_path"], filename=os.path.basename(recording["recording_path"]))
            
        elif format == "transcript":
            from fastapi.responses import PlainTextResponse
            content = recording.get("transcript", "")
            return PlainTextResponse(content, headers={"Content-Disposition": f"attachment; filename=transcript_{id}.txt"})
            
        elif format == "summary":
            from fastapi.responses import PlainTextResponse
            content = f"# Summary for Recording #{id}\n\n"
            content += f"**Timestamp**: {recording.get('timestamp')}\n"
            content += f"**Duration**: {recording.get('duration')} seconds\n"
            content += f"**Mode**: {recording.get('mode')}\n\n"
            content += f"## AI Summary\n{recording.get('summary')}\n\n"
            
            content += "## Action Items\n"
            for item in recording.get("action_items", []):
                content += f"- [ ] {item}\n"
            content += "\n"
            
            content += "## Tasks Detected\n"
            for item in recording.get("tasks", []):
                content += f"- {item}\n"
            content += "\n"
            
            content += "## People Mentioned\n"
            content += ", ".join(recording.get("names", [])) + "\n\n"
            
            content += "## Keywords\n"
            content += ", ".join(recording.get("keywords", [])) + "\n"
            
            return PlainTextResponse(content, headers={"Content-Disposition": f"attachment; filename=summary_{id}.md"})
            
        else:
            raise HTTPException(status_code=400, detail="Invalid export format")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# [Extracted Chat Route Block]


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]


# [Extracted Projects Route Block]

