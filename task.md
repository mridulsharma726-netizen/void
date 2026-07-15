# VOID Major Feature Upgrade — Task Tracker

## Backend Routes
- [x] Create `server/routes/code_intelligence.py` (Code Intel API)
- [x] Create `server/routes/pc_hub.py` (PC Control API)
- [x] Create `server/routes/live_intel.py` (Live Intel API)
- [x] Modify `server/main.py` to register all 3 new routers

## Frontend — HTML
- [x] Add 3 new nav items to sidebar in `index.html`
- [x] Add `#view-code-intel` workspace view
- [x] Add `#view-pc-control` workspace view
- [x] Add `#view-live-intel` workspace view

## Frontend — JavaScript
- [x] Add Code Intel JS functions to `app.js`
- [x] Add PC Control JS functions to `app.js`
- [x] Add Live Intel JS functions to `app.js`
- [x] Update `handleNavSwitch()` for 3 new views

## Frontend — CSS
- [x] Add Code Intel styles to `style.css`
- [x] Optimize CPU thread counts in `launcher.py` and `server/main.py`
- [ ] Optimize Code Intelligence scanning in `server/routes/code_intelligence.py`
- [ ] Create `features_list.md`
- [ ] Run pytest test suite to verify no regressions
- [ ] Verify Code Intel scans complete in under 2 seconds work
