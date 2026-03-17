# PWA UX Polish For Search, Watchlist, Push, And Admin Flows

## Overview
- Improve the usability of already implemented dashboard flows without a large redesign by introducing clear loading, refreshing, empty, offline, and error states across the PWA.
- Make saved-search metadata and refresh behavior easier to understand, reduce ambiguity in watchlist cards and actions, surface actionable push diagnostics, and make admin support actions safer and more transparent.
- Keep the work mobile-first for a PWA context: preserve readable density, large tap targets, safe-area-friendly actions, and non-blocking feedback while data loads or refreshes.

## Context (from discovery)
- Files/components involved:
  - `frontend/src/App.tsx`
  - `frontend/src/styles.css`
  - `frontend/src/features/dashboard/DashboardShell.tsx`
  - `frontend/src/features/search/{SearchPanel.tsx,SearchResultsModal.tsx,SearchFiltersModal.tsx}`
  - `frontend/src/features/watchlist/WatchlistPanel.tsx`
  - `frontend/src/features/push/PushSettingsModal.tsx`
  - `frontend/src/features/admin/{AdminInvitesPanel.tsx,AdminSearchCatalogPanel.tsx}`
  - `frontend/src/{types.ts,lib/api.ts}`
  - `frontend/tests/app.test.tsx`
  - `backend/src/cartrap/api/system.py`
  - `backend/src/cartrap/modules/system_status/service.py`
  - `backend/src/cartrap/modules/notifications/{router.py,schemas.py}`
  - `backend/tests/{test_system_status.py,notifications/test_push_subscriptions.py}`
- Related patterns found:
  - app bootstrap already loads watchlist, saved searches, push subscriptions, search catalog, and live-sync status in parallel, but the UI has no shared loading skeleton/progress contract
  - app bootstrap uses `Promise.allSettled(...)`, so partial failures are already technically tolerated in code, but the UI does not expose which panel failed to load or allow a focused retry
  - saved searches already expose `cached_result_count`, `new_count`, `last_synced_at`, cached modal open, and `Refresh Live`, but the card and modal do not distinguish idle vs refreshing vs stale vs failed states
  - manual search and `Save Search` remain synchronous-feeling actions with no explicit in-flight UX beyond the eventual modal/result update
  - live-sync degraded state already exists via `/api/system/status` and is surfaced as a top banner
  - push backend already exposes subscription config, current subscriptions, and `POST /api/notifications/test`, but the frontend settings modal does not expose diagnostics or test delivery
  - admin panels currently support invite creation and catalog refresh, but feedback is very thin and there is no explicit progress/safety UX
- Dependencies identified:
  - frontend state ownership remains in `App.tsx` today, so async UX likely needs either local action-state props or a small shared helper
  - search/watchlist actions depend on live Copart sync and should keep cached/current data visible while refresh operations are in flight
  - browser-level offline/online state is separate from backend live-sync degradation and should not be conflated in UX copy
  - any system/push diagnostic additions must stay compatible with existing backend tests and auth boundaries

## Development Approach
- **testing approach**: Regular
- **recommended implementation option**: introduce a small shared async-state/presentation layer, then apply it incrementally to saved-search, watchlist, push, and admin flows
- why this option:
  - it solves the real usability gap, which is inconsistent request feedback, without forcing a broad dashboard rewrite
  - it keeps copy, layout, and pending/error behavior consistent across desktop and mobile
  - it leaves room for small backend additions only where frontend diagnostics need extra data
- alternative options considered:
  - **Option B: only patch each flow locally**
    - pros: fastest initial changes
    - cons: inconsistent UX contract, repeated pending/error logic, harder tests
  - **Option C: broader dashboard redesign first**
    - pros: best visual cohesion
    - cons: higher risk, slower delivery, scope drift away from flow polish
- complete each task fully before moving to the next
- make small, focused changes
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
- **CRITICAL: all tests must pass before starting next task**
- **CRITICAL: update this plan file when scope changes during implementation**
- run tests after each change
- maintain backward compatibility with current auth, saved-search cache, and live-sync degraded behavior

## Testing Strategy
- **unit/component tests**: required for every task
  - extend `frontend/tests/app.test.tsx` for bootstrap loading states, action-level pending states, retry/error messaging, saved-search refresh UX, watchlist action feedback, push diagnostics, and admin panel behavior
  - extend backend tests only if system-status or notifications payloads change
- **UI behavior coverage**:
  - loading skeletons/spinners appear during initial data fetch and action-level requests
  - previous data stays visible during refresh when appropriate
  - buttons disable while pending and re-enable on completion/failure
  - error surfaces are actionable and do not silently collapse content
- **build verification**:
  - run `npm run test --prefix frontend`
  - run `npm run build --prefix frontend`
  - run targeted backend tests if API/schema payloads change: `./.venv/bin/pytest backend/tests/test_system_status.py backend/tests/notifications/test_push_subscriptions.py`

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix
- update plan if implementation deviates from original scope
- keep plan in sync with actual work done

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): code, tests, docs
- **Post-Completion** (no checkboxes): manual device checks, deployment validation, stakeholder UX review

## Implementation Steps

### Task 1: Add shared async feedback primitives for dashboard flows

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Create: `frontend/src/features/shared/AsyncStatus.tsx`
- Modify: `frontend/tests/app.test.tsx`

- [x] add a small shared UI primitive for inline loading, refreshing, empty, and error feedback that can render spinner and optional progress-bar variants
- [x] introduce action-level pending state ownership in `App.tsx` for bootstrap load, saved-search actions, watchlist mutations, push actions, and admin actions
- [x] add partial-bootstrap error handling so search, watchlist, push, and admin-related panels can show local load failures and retry independently instead of failing silently
- [x] add consistent disabled/busy semantics (`aria-busy`, button disabling, preserved previous data during refresh where needed)
- [x] write frontend tests for initial bootstrap loading and action-level busy/disabled behavior
- [x] write frontend tests for shared error/retry presentation and partial-bootstrap failure edge cases
- [x] run tests - must pass before next task

### Task 2: Clarify saved-search metadata and refresh/error states

**Files:**
- Modify: `frontend/src/features/search/SearchPanel.tsx`
- Modify: `frontend/src/features/search/SearchResultsModal.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] add explicit pending/success/error UX for manual `Search Lots` and `Save Search`, including button busy states and preserved form context while requests are in flight
- [x] add explicit card-level metadata hierarchy for saved searches: result count, new count, last synced, sync freshness, and degraded/offline hints
- [x] change `Run Search` and modal `Refresh Live` UX to show inline pending states instead of silent waiting, while keeping cached results visible during refresh
- [x] replace raw failure text with actionable inline error blocks that separate cached-view availability from live-refresh failure
- [x] improve mobile readability of saved-search cards and modal toolbar with stacked actions, stable headers, and clearer tap targets
- [x] write frontend tests for manual search/save busy states plus saved-search open/refresh pending, cached-content preservation, and failure/retry messaging
- [x] run tests - must pass before next task

### Task 3: Improve watchlist clarity and mutation feedback

**Files:**
- Modify: `frontend/src/features/watchlist/WatchlistPanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] add clearer watchlist metadata such as `last_checked_at` / freshness and stronger distinction between lot status, sale timing, and support details
- [x] add pending feedback for `Add Lot`, `Add to Watchlist`, and `Remove`, including duplicate-submit prevention and non-blocking inline progress
- [x] improve empty/error copy for add-by-lot-number failures so users understand whether the problem is validation, live-sync outage, or gateway failure
- [x] tighten mobile card layout for scanability: priority-first fields, less competition between thumbnail, summary, and action buttons
- [x] write frontend tests for watchlist add/remove pending states and more specific failure messaging
- [x] run tests - must pass before next task

### Task 4: Surface push diagnostics and support-friendly admin UX

**Files:**
- Modify: `frontend/src/features/push/PushSettingsModal.tsx`
- Modify: `frontend/src/features/admin/AdminInvitesPanel.tsx`
- Modify: `frontend/src/features/admin/AdminSearchCatalogPanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`
- Modify: `backend/src/cartrap/modules/notifications/{router.py,schemas.py}` (only if frontend needs a typed response for test-push UX)
- Modify: `backend/tests/notifications/test_push_subscriptions.py` (only if API contract changes)

- [x] expose push diagnostics in settings: permission state explanation, secure-context/support status, current-device clarity, and last-known server config readiness
- [x] wire the existing backend test-push capability into the frontend with explicit success/failure delivery feedback
- [x] improve subscription list readability by masking long endpoints, showing timestamps/device hints, and identifying the current browser when possible
- [x] upgrade admin panels with action-level busy states, clearer success/error messages, copy-invite affordances, expiry visibility, and safer catalog refresh feedback
- [x] write frontend tests for push diagnostic states, test-push flow, and admin action pending/success/failure UX
- [x] write/update backend tests only if notification API response shape changes
- [x] run tests - must pass before next task

### Task 5: Polish mobile/PWA behavior and degraded-mode messaging

**Files:**
- Modify: `frontend/src/features/dashboard/DashboardShell.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/tests/app.test.tsx`
- Modify: `backend/src/cartrap/api/system.py` (only if richer diagnostics are added)
- Modify: `backend/src/cartrap/modules/system_status/service.py` (only if richer diagnostics are added)
- Modify: `backend/tests/test_system_status.py` (only if system-status payload changes)

- [x] refine the global live-sync banner and related inline notices so users understand what still works, what is stale, and which actions are retryable
- [x] add browser offline/online UX so the app can distinguish “device/network offline” from “backend live sync degraded” and offer the right recovery copy
- [x] ensure mobile layouts respect PWA constraints: full-width buttons where needed, less modal-toolbar crowding, readable safe-area spacing, and lower scroll friction
- [x] add subtle progress affordances for longer operations at panel/modal level without blocking the whole dashboard
- [x] verify all new feedback patterns remain accessible with keyboard navigation, screen-reader-friendly status announcements, and reduced-motion-safe animation behavior
- [x] write frontend tests for degraded-mode messaging, browser-offline messaging, and mobile-oriented action layout regressions where feasible
- [x] run tests - must pass before next task

### Task 6: Verify acceptance criteria
- [x] verify every targeted flow has explicit loading, refreshing, success, empty, and error states where applicable
- [x] verify saved-search and watchlist actions preserve useful current data during refresh/failure instead of blanking panels
- [x] verify push settings allow a user to diagnose why push is unavailable on this device/browser
- [x] verify admin actions provide enough feedback for safe support usage on desktop and mobile
- [x] run full frontend test suite: `npm run test --prefix frontend`
- [x] run frontend production build: `npm run build --prefix frontend`
- [x] run backend diagnostics-related tests if touched: not needed in this frontend-only implementation cycle

### Task 7: [Final] Update documentation
- [x] update `ChangeLog.md` for each implementation cycle during execution
- [x] update `README.md` and/or `docs/backend-api.md` if new user-visible/admin-visible diagnostics or flows are introduced
- [x] move this plan to `docs/plans/completed/`

## Technical Details
- Prefer local, flow-specific pending flags in `App.tsx` keyed by action name over introducing a heavier global state library.
- Keep previously loaded data visible during refresh and show a lightweight "Updating..." affordance instead of clearing panels.
- Shared async UI should support at least:
  - inline spinner + label
  - thin progress bar for panel/modal-level loading
  - retry-capable error state
  - muted empty state with next-step guidance
  - panel-level retry affordance for bootstrap failures that affect only one data source
- Saved-search cards should make freshness obvious:
  - distinguish "never synced", "cached", "refreshing", and "live sync unavailable"
  - avoid relying on raw timestamps alone; pair them with short status copy
- Manual search UX should distinguish between:
  - first search request in progress
  - save-search in progress
  - search failed but form state preserved for quick correction/retry
- Watchlist cards should prioritize the fields that drive decisions on mobile:
  - lot number / title
  - sale timing
  - bid/status
  - freshness / last checked
- Push diagnostics should explain the full chain:
  - browser support
  - secure context requirement
  - permission state
  - backend VAPID/server readiness
  - registered device count
  - test delivery result
- Admin support tooling should focus on low-risk, high-signal actions:
  - visible pending state
  - copyable invite link
  - expiry timestamp
  - refresh completion state and catalog freshness
- Additional usability improvements to include while implementing:
  - disable duplicate submissions during in-flight requests
  - convert long endpoint or URL strings into truncated text with copy affordance where helpful
  - preserve modal scroll/body context during refreshes
  - use concise status copy instead of generic "failed" wherever live-sync degradation is the real cause
  - clearly separate browser-offline state from backend sync outage in copy and UI treatment
  - preserve user-entered form values and panel context when load/action requests fail
  - keep motion subtle and safe when adding loading animations
  - keep touch targets comfortable for mobile PWA use

## Post-Completion
**Documentation note**:
- `README.md` and `docs/backend-api.md` were left unchanged in this cycle because the implementation stayed within existing frontend flows and did not introduce new setup, deployment, or backend API requirements.

**Manual verification**:
- test initial dashboard load with one failed bootstrap dependency and confirm only the affected panel shows retry/error UI
- test saved-search open and `Refresh Live` on desktop and a narrow mobile viewport
- test manual search and `Save Search` while throttling network to confirm busy states and preserved form/results context
- test add/remove watchlist flows with both success and degraded live-sync failures
- test push diagnostics in three states: unsupported browser, permission denied, and configured/granted
- test browser offline/online transitions in standalone/mobile-like mode and confirm copy differs from backend degraded mode
- test admin invite generation and catalog refresh on mobile-width layout for button spacing and message clarity

**External system updates**:
- if push test UX adds or changes API payloads, deploy backend and frontend together
- verify service-worker and HTTPS behavior in the real deployed PWA, not only in local test mocks
