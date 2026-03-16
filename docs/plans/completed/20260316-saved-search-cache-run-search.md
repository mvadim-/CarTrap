# Saved Search Cache And Cached Run Search

## Overview
- Add a Mongo-backed cache for saved search result sets so `Run Search` opens cached results instead of triggering a new live Copart request.
- Seed the cache immediately when a user saves a search, so the first modal view is never empty.
- Surface newly discovered lots in the UI with `NEW` indicators and saved-search-level `new_count`, where `NEW` means "appeared since the last time the user viewed this saved search."
- Keep live refresh available inside the results modal via an explicit `Refresh Live` action that updates the cache through the existing AWS -> NAS gateway -> Copart path.

## Context (from discovery)
- Files/components involved:
  - `backend/src/cartrap/modules/search/{router.py,service.py,repository.py,models.py,schemas.py}`
  - `backend/src/cartrap/modules/copart_provider/{service.py,client.py}`
  - `backend/tests/search/{test_search_api.py,test_saved_search_monitoring.py}`
  - `frontend/src/{App.tsx,lib/api.ts,types.ts}`
  - `frontend/src/features/search/{SearchPanel.tsx,SearchResultsModal.tsx}`
  - `frontend/tests/app.test.tsx`
- Related patterns found:
  - manual search already uses a synchronous `POST /api/search` flow and returns normalized lot results
  - saved search polling already stores `result_count`, `search_etag`, and `last_checked_at`
  - degraded/offline status is already exposed through `/api/system/status`
  - frontend already has a saved-search card list and reusable search results modal
- Dependencies identified:
  - `SearchService.search()` and `CopartProvider.search_lots()` for full result fetches
  - worker polling path in `SearchService.poll_due_saved_searches()`
  - Mongo persistence and frontend saved-search rendering/tests

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
- maintain backward compatibility for existing live manual search flow and degraded-mode behavior

## Testing Strategy
- **unit tests**: required for every task
  - backend search repository/service tests for cache persistence, `view`, `refresh-live`, and worker diff logic
  - backend API tests for new saved-search cache endpoints and save-search cache seeding
  - frontend tests for cached modal flow, `NEW` badge visibility, and `Refresh Live`
- **e2e-style frontend tests**:
  - extend `frontend/tests/app.test.tsx` for saved search cache seed, cached `Run Search`, clearing `NEW`, and modal `Refresh Live`

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix
- update plan if implementation deviates from original scope
- keep plan in sync with actual work done

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): code, tests, docs
- **Post-Completion** (no checkboxes): manual deploy, manual UI verification, external environment checks

## Implementation Steps

### Task 1: Add saved-search results cache persistence model

**Files:**
- Modify: `backend/src/cartrap/modules/search/models.py`
- Modify: `backend/src/cartrap/modules/search/repository.py`
- Modify: `backend/src/cartrap/modules/search/schemas.py`
- Create: `backend/tests/search/test_saved_search_cache_repository.py`

- [x] add Mongo collection constants and repository methods for saved-search result cache documents, including `results`, `result_count`, `new_lot_numbers`, `last_synced_at`, `seen_at`, and ownership scoping
- [x] add backend schemas/response models for cached saved-search results and saved-search list metadata (`new_count`, `cached_result_count`, `last_synced_at`)
- [x] ensure repository supports atomic "view and clear NEW markers" updates for one saved search
- [x] write repository/schema tests for create/read/update/clear-view flows and ownership boundaries
- [x] run tests - must pass before next task

### Task 2: Seed cache on save and expose cached saved-search endpoints

**Files:**
- Modify: `backend/src/cartrap/modules/search/service.py`
- Modify: `backend/src/cartrap/modules/search/router.py`
- Modify: `backend/src/cartrap/modules/search/schemas.py`
- Modify: `backend/tests/search/test_search_api.py`

- [x] extend save-search flow so saving a search also seeds cache from the already available normalized live search results
- [x] add `POST /api/search/saved/{id}/view` to return cached results and mark the saved search as seen
- [x] add `POST /api/search/saved/{id}/refresh-live` to perform a fresh gateway-backed search, update cache, and return refreshed modal data
- [x] extend saved-search list responses with `new_count`, `cached_result_count`, and `last_synced_at`
- [x] write API tests for save-search cache seed, cached view, refresh-live success, and not-found/ownership error cases
- [x] run tests - must pass before next task

### Task 3: Update worker polling to refresh cache only when upstream search changes

**Files:**
- Modify: `backend/src/cartrap/modules/search/service.py`
- Modify: `backend/src/cartrap/modules/search/repository.py`
- Modify: `backend/tests/search/test_saved_search_monitoring.py`

- [x] keep the existing cheap `result_count` / `etag` check path and only fetch full results when upstream count/etag changes
- [x] compare previous cached `lot_number` set with fresh results and compute `new_lot_numbers` plus `new_count`
- [x] preserve "seen" semantics so `NEW` means "since last modal view", not simply "from the latest poll cycle"
- [x] ensure push notifications for saved searches still fire when new matches appear, using the cache diff result as the source of truth
- [x] write worker/service tests for unchanged cache, changed cache with new lots, and changed cache with no truly new lot numbers
- [x] run tests - must pass before next task

### Task 4: Switch saved-search UI from live Run Search to cached modal

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/features/search/SearchPanel.tsx`
- Modify: `frontend/src/features/search/SearchResultsModal.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] add frontend API methods and types for saved-search cached view and modal live refresh endpoints
- [x] change `Run Search` so it opens the modal from cached Mongo results instead of calling the generic live `/api/search`
- [x] add saved-search-level `new_count` UI and lot-level `NEW` badges in the modal, clearing them when the modal is opened
- [x] add `Refresh Live` inside the modal and keep cached results visible if live refresh fails or live sync is degraded
- [x] write/update frontend tests for cache-seeded save flow, cached run-search modal, clearing `NEW`, and modal `Refresh Live`
- [x] run tests - must pass before next task

### Task 5: Verify acceptance criteria
- [x] verify saved searches open cached results without hitting the generic live search endpoint
- [x] verify saving a search immediately seeds cache and avoids empty modal state
- [x] verify `NEW` semantics match "since last view" and clear on modal open
- [x] run full backend test suite: `./.venv/bin/pytest backend/tests`
- [x] run frontend tests and build: `npm run test --prefix frontend` and `npm run build --prefix frontend`

### Task 6: [Final] Update documentation
- [x] update `README.md` and/or `backend/README.md` if saved-search cached run behavior becomes user-visible enough to document
- [x] update `ChangeLog.md` for each implementation cycle during execution
- [x] move this plan to `docs/plans/completed/`

## Technical Details
- Cache shape should reuse the normalized manual search result structure already returned by `SearchService.search()` to avoid a second frontend-specific shape.
- `Save Search` should send the currently displayed normalized results back to the backend so cache seeding does not trigger another live Copart request.
- `POST /api/search/saved/{id}/view` should be a mutating endpoint because it clears `NEW` markers / updates `seen_at`.
- `Refresh Live` should update both cache data and saved-search list metadata so the list stays in sync after the modal refresh.
- `NEW` should be computed from `lot_number` diff against the previous cached result set, not from `result_count` alone.
- Degraded/offline mode should still allow cached modal viewing even if live refresh fails.

## Post-Completion
**Documentation note**:
- README/backend README were left unchanged in this cycle because the saved-search cached-run behavior is currently covered by the implementation plan and regression tests, and no broader user-facing setup/ops guidance changed.

**Manual verification**:
- save a new search and confirm the first `Run Search` opens cached results immediately
- let worker detect new lots and confirm saved-search card shows `new_count`
- open the modal and confirm `NEW` badges disappear on subsequent opens until another sync adds new lots
- use `Refresh Live` in the modal and confirm cache/list metadata update without breaking degraded-mode fallback

**External system updates**:
- deploy backend, worker, and frontend together so saved-search API/types/UI stay compatible
- verify NAS gateway remains reachable because both worker refresh and modal live refresh depend on it
