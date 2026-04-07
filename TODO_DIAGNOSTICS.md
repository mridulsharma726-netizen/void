# VOID Diagnostics & Self-Repair Fix Plan
## Status: ✅ Step 1 Complete | Repair Next

### ✅ 1. Fix tools/diagnostics.py
   - ✅ psutil/platform system info (CPU%, RAM%, OS)
   - ✅ Exact spec JSON: status/Issues/details
   - ✅ Real checks: backend/STT/TTS/memory/deps/tools/internet
   - ✅ NO "Unknown" ✓

### [ ] 2. Fix tools/self_repair.py
   - Call diagnostics
   - Attempt real fixes (reinit STT/TTS, repair memory)
   - Return actions count

### [ ] 3. Fix intent_detector.py
   - Add "repair", "diagnostics", "scan system" → direct routing

### [ ] 4. Test Commands
   - "run diagnostics" → structured JSON
   - "repair yourself" → repair actions
   - "scan system" → diagnostics

**Priority:** self_repair.py → intent_detector.py → tests
