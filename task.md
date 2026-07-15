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
- [x] Optimize Code Intelligence scanning in `server/routes/code_intelligence.py`
- [x] Create `features_list.md`
- [x] Run pytest test suite to verify no regressions
- [x] Verify Code Intel scans complete in under 2 seconds work

## Security and Compliance
- [x] Implement honest sandbox warning prefix in communication controllers:
  - [x] `tools/email_control.py`
  - [x] `tools/discord_control.py`
  - [x] `tools/telegram_control.py`
  - [x] `tools/slack_control.py`
- [x] Prepend honest warnings to mock database calls in `tools/founder_assistant.py` queries:
  - [x] SkipIt queries (`get_bookings_today`, `get_inactive_listings`, `get_inactive_users`, `generate_weekly_report`)
  - [x] Smart Cart queries (`get_pilot_performance`, `generate_revenue_projections`, `create_store_pitch_deck`)
  - [x] BI recommendations (`business_intelligence_recommendations`)
- [x] Update `server/backend/tools_runtime.py` to prepend warnings to `_weather` mock response.
- [x] Intercept Category (b) and (c) tool executions in `server/routes/chat.py` using `MOCK_OR_UNWIRED_EXPLANATIONS`.
- [x] Verify test suite runs successfully:
  - [x] `pytest tests/test_phase3_workflows.py`
