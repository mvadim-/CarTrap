# Manual Search Modal, Saved Searches, and Lot Thumbnails

## Overview
- Переробити `Manual Copart Search`, щоб результати пошуку відкривалися в модальному вікні, яке можна закривати і розширити майбутнім фільтруванням без повторного редизайну панелі.
- Додати можливість зберігати manual search як окрему сутність користувача і показувати збережені пошуки в тій самій панелі за патерном, схожим на `Tracked Lots`.
- Показувати thumbnail у `Tracked Lots`, використовуючи Copart payload, щоб картки виглядали інформативніше і ближче до реального lot feed.

## Context (from discovery)
- files/components involved:
  - `frontend/src/features/search/SearchPanel.tsx`
  - `frontend/src/features/watchlist/WatchlistPanel.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/lib/api.ts`
  - `frontend/src/types.ts`
  - `frontend/src/styles.css`
  - `frontend/tests/app.test.tsx`
  - `backend/src/cartrap/modules/search/router.py`
  - `backend/src/cartrap/modules/search/service.py`
  - `backend/src/cartrap/modules/search/repository.py`
  - `backend/src/cartrap/modules/search/models.py`
  - `backend/src/cartrap/modules/search/schemas.py`
  - `backend/src/cartrap/modules/watchlist/service.py`
  - `backend/src/cartrap/modules/watchlist/repository.py`
  - `backend/src/cartrap/modules/watchlist/schemas.py`
  - `backend/src/cartrap/modules/copart_provider/models.py`
  - `backend/src/cartrap/modules/copart_provider/normalizer.py`
  - `backend/tests/search/test_search_api.py`
  - `backend/tests/watchlist/test_watchlist_api.py`
  - `backend/tests/copart/test_api_normalizer.py`
- related patterns found:
  - Search catalog already uses Mongo-backed persistence through a dedicated repository in `search/`.
  - Watchlist cards and search results share the same `.result-card` visual pattern in `frontend/src/styles.css`.
  - `App.tsx` already owns cross-panel state for search results, watchlist data, and authenticated API calls.
- dependencies identified:
  - FastAPI + Pydantic response models for new search persistence endpoints.
  - Mongo collections for user-scoped saved searches.
  - Vitest/Testing Library for frontend regression coverage.
  - Existing backend pytest suites for search, watchlist, and Copart normalizer coverage.

## Development Approach
- **testing approach**: Regular (code first, then tests)
- Рекомендований підхід: зберігати saved searches у backend/Mongo як user-scoped сутність; не обмежуватися frontend-only storage.
- Результати пошуку відображати через окремий modal-компонент із власним open/close state і структурою, придатною для майбутніх filter controls.
- Thumbnail протягнути одним контрактом через Copart normalizer -> search/watchlist serialization -> frontend types/components.
- complete each task fully before moving to the next
- make small, focused changes
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
- **CRITICAL: all tests must pass before starting next task** - no exceptions
- **CRITICAL: update this plan file when scope changes during implementation**
- run tests after each change
- maintain backward compatibility where practical for existing routes

## Testing Strategy
- **unit/integration tests**: `./.venv/bin/pytest backend/tests`
- **frontend app tests**: `npm run test --prefix frontend`
- **production build smoke check**: `npm run build --prefix frontend`
- **e2e tests**: у проєкті окремого browser e2e suite наразі немає; UI regression покривається Vitest app tests

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix
- update plan if implementation deviates from original scope
- keep plan in sync with actual work done

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): зміни в backend/frontend коді, тестах і документації цього репозиторію
- **Post-Completion** (no checkboxes): ручна перевірка UX, майбутні покращення на кшталт filters/search presets management

## Implementation Steps

### Task 1: Add backend contract for saved searches

**Files:**
- Modify: `backend/src/cartrap/modules/search/models.py`
- Modify: `backend/src/cartrap/modules/search/repository.py`
- Modify: `backend/src/cartrap/modules/search/schemas.py`
- Modify: `backend/src/cartrap/modules/search/service.py`
- Modify: `backend/src/cartrap/modules/search/router.py`
- Modify: `backend/tests/search/test_search_api.py`

- [x] define Mongo collection/constants and repository methods for create/list of user saved searches
- [x] add Pydantic schemas and FastAPI endpoints for saving the current manual search payload and listing saved searches for current user
- [x] implement duplicate-handling and minimal normalization for saved search titles/criteria so identical searches are not stored ambiguously
- [x] verify saved-search isolation and duplicate semantics stay scoped per user
- [x] write tests for save/list saved-search functionality (success cases)
- [x] write tests for validation/error cases such as empty criteria, duplicate save attempts, and cross-user visibility
- [x] run tests - must pass before next task

### Task 2: Extend Copart/domain models with thumbnail support

**Files:**
- Modify: `backend/src/cartrap/modules/copart_provider/models.py`
- Modify: `backend/src/cartrap/modules/copart_provider/normalizer.py`
- Modify: `backend/src/cartrap/modules/watchlist/service.py`
- Modify: `backend/src/cartrap/modules/watchlist/schemas.py`
- Modify: `backend/tests/copart/test_api_normalizer.py`
- Modify: `backend/tests/watchlist/test_watchlist_api.py`
- Modify: `backend/tests/watchlist/test_snapshot_storage.py`
- Modify: `backend/tests/search/test_search_api.py`

- [x] add thumbnail field to Copart search result and lot snapshot domain models
- [x] map thumbnail from both search and lot-details payload variants in normalizer helpers with safe fallbacks
- [x] persist/serialize thumbnail through watchlist creation and list responses so tracked lots can render images without extra fetches
- [x] write tests for thumbnail extraction in search and lot-detail normalizers (success cases)
- [x] write tests for watchlist/search API responses with missing and present thumbnail values
- [x] write storage-level regression coverage proving thumbnail is persisted with tracked-lot state
- [x] run tests - must pass before next task

### Task 3: Build modal-based Manual Search UX with saved searches list

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/features/search/SearchPanel.tsx`
- Create: `frontend/src/features/search/SearchResultsModal.tsx`
- Modify: `frontend/src/features/watchlist/WatchlistPanel.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] add frontend API methods/types for saved searches and thumbnail-enabled search/watchlist payloads
- [x] refactor `SearchPanel` so submit opens a dedicated modal with search results, close control, and reserved layout area for future filters
- [x] add save-search action and render saved searches list inside `Manual Copart Search` using the existing card language adapted from tracked lots
- [x] add run/load action for each saved search so the list is an active shortcut, not passive history
- [x] update `WatchlistPanel` cards to render thumbnail, fallback placeholder, and text layout that still works on mobile
- [x] write frontend tests covering modal open/close, save-search listing/re-run, and thumbnail rendering in tracked lots
- [x] write frontend tests for edge cases such as empty results, unavailable thumbnail, and repeated save attempts surfacing backend errors
- [x] run tests - must pass before next task

### Task 4: Verify acceptance criteria
- [x] verify all requirements from Overview are implemented
- [x] verify edge cases are handled
- [x] run full backend test suite: `./.venv/bin/pytest backend/tests`
- [x] run frontend tests: `npm run test --prefix frontend`
- [x] run frontend build smoke check: `npm run build --prefix frontend`

### Task 5: [Final] Update documentation
- [x] update `README.md` if the new saved-search capability or UI behavior should be documented for users/admins
- [x] update `AGENTS.md` if any new repo-specific workflow pattern appears during implementation (not needed)
- [x] move this plan to `docs/plans/completed/`

## Technical Details
- saved search payload:
  - базуватися на поточному `SearchRequest` contract (`make`, `model`, `make_filter`, `model_filter`, `year_from`, `year_to`, optional human-readable label)
  - зберігати user-scoped document з normalized criteria і timestamp fields
- modal interaction flow:
  - submit in `SearchPanel` -> fetch `/api/search` -> store results in `App.tsx` -> open modal
  - close action should only dismiss modal, not discard the last result set unless user runs another search or logs out
- thumbnail contract:
  - backend model should tolerate `null` thumbnail
  - watchlist documents should store thumbnail snapshot at add time so listing stays cheap
- visual/layout considerations:
  - modal needs scroll-safe container and mobile-friendly close action
  - saved searches list should not visually compete with the search form
  - watchlist image slot should keep card height stable even when image is absent

## Post-Completion
*Items requiring manual intervention or external systems - no checkboxes, informational only*

**Manual verification**:
- перевірити, що modal results можна відкрити, закрити і повторно відкрити новим пошуком без stale UI state
- перевірити, що saved search зберігається між refresh/login sessions
- перевірити, що thumbnail у `Tracked Lots` коректно масштабується на desktop і mobile

**External system updates**:
- якщо Copart змінить структуру thumbnail fields, можливо знадобиться ще один normalizer hotfix
