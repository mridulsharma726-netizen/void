from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

IntentType = Literal["command", "chat", "system", "unknown", "deep_research", "academic"]

class ChatRequest(BaseModel):
    text: Optional[str] = None
    message: Optional[str] = None

class TextRequest(BaseModel):
    text: str

class PathRequest(BaseModel):
    path: str

class ToolCall(BaseModel):
    name: str
    input: Dict[str, Any] = Field(default_factory=dict)
    output: str = ""
    meta: Dict[str, Any] = Field(default_factory=dict)

class IntentResult(BaseModel):
    intent: IntentType
    action: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0

class PipelineResponse(BaseModel):
    reply: str
    meta: Dict[str, Any] = Field(default_factory=dict)

class StatsSnapshot(BaseModel):
    uptime: int
    messages: int
    tool_calls: int
    memory_facts: int
    void_level: int
    cpu_usage: Optional[float] = None
    ram_usage: Optional[float] = None
    network_online: bool = True
    storage_used_gb: Optional[float] = None
    storage_total_gb: Optional[float] = None
    battery_percent: Optional[float] = None
    battery_charging: Optional[bool] = None
    gpu_usage: Optional[float] = None

class StreamChunk(BaseModel):
    token: str
    done: bool = False
    tool_calls: List[ToolCall] = Field(default_factory=list)

class CVCSPermissionRequest(BaseModel):
    level: float
    duration_seconds: Optional[float] = 1800.0

class CVCSActionRequest(BaseModel):
    action: str
    target: str
    coords: Optional[List[int]] = None

