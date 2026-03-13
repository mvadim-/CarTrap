# Enhance tracked lots tiles with lot details

## Overview
- Розширити `Tracked Lots` tiles новими полями: `Odometer`, `Primary damage`, `Estimated retail value`, `Has Key`, `Drivetrain`, `Highlights`, `Vin`.
- Дані мають приходити з Copart lot-details payload, а `Vin` треба отримувати з `encryptedVIN` через наявний алгоритм декодування у `vin_decoder.py`.
- Зміна має пройти весь ланцюжок: Copart normalizer -> watchlist persistence/API -> frontend tile rendering.

## Context (from discovery)
- files/components involved:
  - `backend/src/cartrap/modules/copart_provider/models.py`
  - `backend/src/cartrap/modules/copart_provider/normalizer.py`
  - `backend/src/cartrap/modules/watchlist/service.py`
  - `backend/src/cartrap/modules/watchlist/schemas.py`
  - `backend/tests/copart/test_api_normalizer.py`
  - `backend/tests/watchlist/test_watchlist_api.py`
  - `frontend/src/types.ts`
  - `frontend/src/features/watchlist/WatchlistPanel.tsx`
  - `frontend/src/styles.css`
  - `frontend/tests/app.test.tsx`
  - `vin_decoder.py`
- related patterns found:
  - `Tracked Lots` уже рендеряться через `WatchlistPanel` як `result-card result-card--media watchlist-card`.
  - `WatchlistService` уже зберігає normalized snapshot у `tracked_lots` і робить lazy media backfill для legacy записів.
  - Copart lot fetch уже централізований у `CopartProvider.fetch_lot()` через `lot-details` endpoint.
  - regression coverage для Copart normalizer і watchlist API вже існує, тож нові поля треба вбудовувати в чинні тести, а не будувати нову тестову інфраструктуру.
- dependencies identified:
  - `vin_decoder.py` містить готову `decode_encrypted_vin(encrypted_vin: str) -> str`.
  - frontend читає watchlist contract через `frontend/src/types.ts`.
  - backend API contract формується через `WatchlistItemResponse` та `WatchlistService.serialize_tracked_lot()`.
  - `WatchlistRepository` не вимагає окремої schema-міграції для нових полів, але backfill-умова має відрізняти "поле відсутнє" від "поле присутнє і legitimately null".

## Development Approach
- **testing approach**: Regular
- complete each task fully before moving to the next
- make small, focused changes
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
  - tests are not optional - they are a required part of the checklist
  - write unit tests for new functions/methods
  - write unit tests for modified functions/methods
  - add new test cases for new code paths
  - update existing test cases if behavior changes
  - tests cover both success and error scenarios
- **CRITICAL: all tests must pass before starting next task** - no exceptions
- **CRITICAL: update this plan file when scope changes during implementation**
- run tests after each change
- maintain backward compatibility
- preferred approach: normalize all new lot-details fields on the backend and expose a clean watchlist contract without leaking `encryptedVIN` to the frontend

## Testing Strategy
- **unit tests**: required for every task
  - extend `backend/tests/copart/test_api_normalizer.py` for extraction/normalization of the new lot-details fields and VIN decoding behavior
  - extend `backend/tests/watchlist/test_watchlist_api.py` for persistence/serialization/backfill of the new watchlist fields
  - extend `frontend/tests/app.test.tsx` for rendering of the enriched `Tracked Lots` tile
- **e2e tests**: not applicable right now; no dedicated Playwright/Cypress suite is committed in this repository

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix
- update plan if implementation deviates from original scope
- keep plan in sync with actual work done

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): tasks achievable within this codebase - code changes, tests, documentation updates
- **Post-Completion** (no checkboxes): items requiring external action - manual testing, changes in consuming projects, deployment configs, third-party verifications

## Implementation Steps

### Task 1: Normalize extended Copart lot-details fields

**Files:**
- Modify: `backend/src/cartrap/modules/copart_provider/models.py`
- Modify: `backend/src/cartrap/modules/copart_provider/normalizer.py`
- Modify: `backend/tests/copart/test_api_normalizer.py`
- Reuse logic from: `vin_decoder.py`

- [x] extend `CopartLotSnapshot` with optional fields for `odometer`, `primary_damage`, `estimated_retail_value`, `has_key`, `drivetrain`, `highlights`, `vin`
- [x] add backend-side extraction helpers in `normalizer.py` that map the actual Copart lot-details keys into the new normalized fields
- [x] extract or mirror the VIN decoder logic into an importable backend-safe helper based on `vin_decoder.py`, while keeping the frontend contract free of `encryptedVIN`
- [x] write tests for successful normalization of all requested fields, including decoded VIN and list/string handling for highlights
- [x] write tests for missing or malformed optional fields so normalization degrades gracefully instead of failing lot fetch
- [x] run tests - must pass before next task: `./.venv/bin/pytest backend/tests/copart/test_api_normalizer.py`

### Task 2: Persist and expose enriched tracked-lot details

**Files:**
- Modify: `backend/src/cartrap/modules/watchlist/service.py`
- Modify: `backend/src/cartrap/modules/watchlist/schemas.py`
- Modify: `backend/src/cartrap/modules/monitoring/service.py`
- Modify: `backend/tests/watchlist/test_watchlist_api.py`
- Modify: `backend/tests/watchlist/test_snapshot_storage.py`
- Modify: `backend/tests/monitoring/test_change_detection.py`

- [x] update tracked-lot creation flow so new normalized lot-details fields are stored alongside existing watchlist state
- [x] extend `WatchlistItemResponse` and `serialize_tracked_lot()` to return the new fields in `/api/watchlist`
- [x] expand lazy backfill behavior so legacy tracked lots missing the new detail-field keys can be refreshed from Copart lot details without overwriting intentionally null values
- [x] keep background polling in `MonitoringService` aligned with the new tracked-lot detail fields so refreshed snapshots do not leave stale values in `tracked_lots`
- [x] write API/storage tests for create/list flows proving the enriched fields are returned and VIN is already decoded
- [x] write API/storage tests for legacy/backfill behavior, intentionally null detail fields, and monitoring updates
- [x] run tests - must pass before next task: `./.venv/bin/pytest backend/tests/copart/test_api_normalizer.py backend/tests/watchlist/test_watchlist_api.py backend/tests/watchlist/test_snapshot_storage.py backend/tests/monitoring/test_change_detection.py`

### Task 3: Render enriched Tracked Lots tiles in frontend

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/features/watchlist/WatchlistPanel.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] extend `WatchlistItem` type with the new backend fields so the frontend contract matches the updated API
- [x] update `WatchlistPanel` tile layout to show `Odometer`, `Primary damage`, `Estimated retail value`, `Has Key`, `Drivetrain`, `Highlights`, `Vin` without breaking the existing media/status/actions structure
- [x] add display fallbacks for absent values and ensure long values like VIN/highlights wrap cleanly on desktop and mobile
- [x] write frontend tests proving the new tracked-lot fields render correctly in the watchlist tile
- [x] write frontend tests for missing-value rendering and ensure existing remove/add flows still work
- [x] run tests - must pass before next task: `npm run test --prefix frontend -- app.test.tsx`

### Task 4: Verify acceptance criteria
- [x] verify all requirements from Overview are implemented
- [x] verify edge cases are handled
- [x] run full test suite: `./.venv/bin/pytest backend/tests/copart/test_api_normalizer.py backend/tests/watchlist/test_watchlist_api.py backend/tests/watchlist/test_snapshot_storage.py backend/tests/monitoring/test_change_detection.py && npm run test --prefix frontend -- app.test.tsx && npm run build --prefix frontend`
- [x] run e2e tests if project has them: `N/A (no committed e2e suite)`
- [x] verify test coverage meets project standard through updated regression tests for backend and frontend touchpoints

### Task 5: [Final] Update documentation
- [x] review `README.md` update need; no change required
- [x] review `AGENTS.md` update need; no new patterns required
- [x] update `ChangeLog.md` with implementation outcomes
- [x] move this plan to `docs/plans/completed/`

## Technical Details
- `Vin` should be derived on the backend from Copart `encryptedVIN`; no need to expose encrypted input to the frontend.
- To avoid brittle imports from the repository root, the decoder logic should live in an importable backend utility module or be moved there with `vin_decoder.py` kept as a thin CLI wrapper if needed.
- `Highlights` may require normalizing either a list payload or a string-like field into a display-friendly list/string representation; pick one canonical backend representation and keep it stable across API responses.
- `Has Key` should be normalized into a nullable boolean or a small canonical string value before it reaches the frontend; choose the representation that best matches existing Pydantic/API conventions and document it in code/tests.
- Legacy tracked lots likely lack all new fields, so watchlist list/backfill logic must key off missing document fields rather than plain `None` checks; otherwise valid unknown values could trigger needless refetches.
- Frontend layout should preserve the current three-zone card structure (`media / body / actions`) and add a compact secondary metadata grid rather than introducing a separate modal.

## Post-Completion
*Items requiring manual intervention or external systems - no checkboxes, informational only*

**Manual verification** (if applicable):
- add a fresh lot to `Tracked Lots` and confirm all new detail fields appear correctly
- open an older tracked lot created before this change and confirm backfill populates the new fields
- verify cards remain readable on narrow mobile widths and with long `Highlights` / `Vin` values

**External system updates** (if applicable):
- if Copart lot-details field names differ in production payloads, adjust the extractor map after inspecting real responses
