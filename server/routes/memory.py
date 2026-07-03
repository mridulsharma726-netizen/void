import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from server.dependencies import (
    VoidSingletons, PermissionManager, DATA_DIR, _get_memory
)

logger = logging.getLogger("void.routes.memory")

router = APIRouter()

class ProfileRequest(BaseModel):
    key: str
    value: str

class AddMemoryRequest(BaseModel):
    fact: str
    importance: int = 5

class DeleteMemoryRequest(BaseModel):
    fact: str


@router.post("/memory/profile")
async def update_profile_value(req: ProfileRequest):
    from backend.memory_sqlite import set_profile_value
    ok = set_profile_value(req.key, req.value)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update profile value.")
    return {"status": "ok", "message": f"Updated profile key '{req.key}'."}


@router.get("/memory/profile/{key}")
async def get_profile_value_endpoint(key: str):
    from backend.memory_sqlite import get_profile_value
    val = get_profile_value(key)
    if val is None:
        raise HTTPException(status_code=404, detail=f"Profile key '{key}' not found.")
    return {"status": "ok", "key": key, "value": val}


@router.get("/memory/list")
async def list_memories():
    from backend.memory_sqlite import get_all_facts
    try:
        facts = get_all_facts()
        return {"status": "ok", "facts": facts}
    except Exception as e:
        logger.error(f"Failed to load memories: {e}")
        return {"status": "error", "facts": []}


@router.post("/memory/add")
async def add_memory_endpoint(req: AddMemoryRequest):
    from backend.memory_sqlite import add_fact
    try:
        ok = add_fact(req.fact, req.importance)
        if ok:
            return {"status": "ok", "message": "Fact added to memory banks."}
        else:
            raise HTTPException(status_code=500, detail="Failed to add fact.")
    except Exception as e:
        logger.error(f"Failed to add memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/delete")
async def delete_memory_endpoint(req: DeleteMemoryRequest):
    from backend.memory_sqlite import remove_fact
    try:
        ok = remove_fact(req.fact)
        if ok:
            return {"status": "ok", "message": "Fact removed from memory banks."}
        else:
            raise HTTPException(status_code=500, detail="Fact not found or could not be deleted.")
    except Exception as e:
        logger.error(f"Failed to delete memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === MEETINGS API ===
