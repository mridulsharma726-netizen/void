# VOID Electron Production Refactor - TODO
===============================

**Status:** Approved - Overwrite current with 32-file production Electron app

**Goal:** Electron desktop app auto-launches FastAPI backend → HUD UI "Online"

## Plan Details:
- Backend: FastAPI subprocess (core 8 tools)
- Frontend: Electron HUD (stats/chat/voice)
- Build: .exe installer (electron-builder)
- Total: 32 files, scalable

## Steps:
- [ ] 1. package.json (Electron + builder)
- [ ] 2. src/main.js (Electron + backend spawn)
- [ ] 3. src/preload.js
- [ ] 4. src/renderer/ (index.html, app.js, style.css HUD)
- [ ] 5. src/backend/server.py (FastAPI core)
- [ ] 6. src/backend/requirements.txt
- [ ] 7. src/backend/core/ (memory, brain, router)
- [ ] 8. src/backend/tools/ (8 core: stats, voice, etc.)
- [ ] 9. electron-builder.yml (.exe)
- [ ] 10. README.md + launcher.bat
- [ ] 11. Migrate data/logs
- [ ] 12. Test build/run
- [ ] 13. package + dist VOID.exe

**Progress:** 0/13 | Est: 30min build time

*2024-10-25*
