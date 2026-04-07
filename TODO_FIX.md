# VOID Fix Plan

## Tasks:
- [x] 1. Update core/brain.py - add explicit OLLAMA_URL, logging, explicit error messages
- [x] 2. Update main.py - add [VOID CHAT INPUT], [VOID CHAT OUTPUT], [VOID STT RESULT] logging
- [x] 3. Update tools/voice_stt.py - return JSON with status on exceptions
- [x] 4. Update ui/app.js - add [VOID MIC RESPONSE] logging

## Changes Summary:
1. brain.py: Added [VOID BRAIN INIT] startup logs showing OLLAMA_URL & MODEL, [VOID BRAIN REQUEST]/[VOID BRAIN RESPONSE]/[VOID BRAIN OUTPUT]/[VOID BRAIN ERROR] structured logging
2. main.py: [VOID CHAT INPUT]/[VOID CHAT OUTPUT] on ALL code paths (fast paths, memory, LLM, tool calls), [VOID STT RESULT] on /listen endpoint
3. voice_stt.py: All exception paths already return {"status": "error", "text": "..."} - confirmed correct
4. app.js: Changed STT log to [VOID MIC RESPONSE] format with JSON.stringify, added [VOID STATS POLLING] confirmation log
