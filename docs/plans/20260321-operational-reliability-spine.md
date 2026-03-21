# Operational Reliability Spine For CarTrap

## Overview
- Establish an end-to-end reliability model for the existing `frontend + backend + worker + NAS gateway` stack without rewriting the product around a new queue platform.
- Make cached reads, live refreshes, worker polling, and push-driven revalidation behave predictably under timeout, partial outage, and degraded sync conditions.
- Introduce explicit freshness metadata, controlled refresh execution, support diagnostics, and structured observability so the system can degrade cleanly instead of becoming ambiguous.

## Context (from discovery)
- files/components involved:
  - `backend/src/cartrap/modules/system_status/{service.py,repository.py}`
  - `backend/src/cartrap/api/system.py`
  - `backend/src/cartrap/modules/search/{service.py,router.py,schemas.py,repository.py}`
  - `backend/src/cartrap/modules/watchlist/{service.py,router.py,schemas.py,repository.py}`
  - `backend/src/cartrap/modules/monitoring/{service.py,polling_policy.py,change_detection.py}`
  - `backend/src/cartrap/modules/notifications/service.py`
  - `backend/src/cartrap/modules/copart_gateway/service.py`
  - `backend/src/cartrap/modules/copart_provider/client.py`
  - `backend/src/cartrap/worker/main.py`
  - `backend/src/cartrap/core/logging.py`
  - `frontend/src/{App.tsx,types.ts,lib/api.ts}`
  - `frontend/src/features/search/{SearchPanel.tsx,SearchResultsModal.tsx}`
  - `frontend/src/features/watchlist/WatchlistPanel.tsx`
  - `frontend/src/features/push/PushSettingsModal.tsx`
  - `frontend/src/features/dashboard/AccountMenuSheet.tsx`
  - `frontend/public/sw.js`
  - `frontend/tests/app.test.tsx`
  - `backend/tests/{test_system_status.py,test_worker_main.py}`
  - `backend/tests/search/{test_search_api.py,test_saved_search_monitoring.py}`
  - `backend/tests/monitoring/{test_polling_policy.py,test_change_detection.py}`
  - `backend/tests/notifications/{test_push_delivery.py,test_push_subscriptions.py}`
  - `backend/tests/watchlist/test_watchlist_api.py`
- related patterns found:
  - `SystemStatusService` already tracks `available/degraded` with last success/failure timestamps, but the contract is still too coarse for per-resource freshness and retryability.
  - `SearchService` and `MonitoringService` already mark live-sync success/failure, but refresh lifecycle is implicit and tightly coupled to the read/update flows.
  - `worker/main.py` currently executes one polling loop with summary logging, but there is no explicit job identity, lock/lease model, retry taxonomy, or structured outcome record.
  - `App.tsx` already supports dashboard auto-refresh, hidden-tab attention, offline handling, and local async states, which makes it a good integration point for richer reliability UX instead of a global rewrite.
  - `WatchlistService.list_watchlist()` still performs on-read Copart backfill for missing media/detail fields, so a strict read-path/refresh-path split needs an explicit legacy backfill strategy instead of simply removing that fetch.
  - push revalidation is split between backend notification payloads and `frontend/public/sw.js`, where `refresh_targets` are derived/broadcast to the app shell; reliability changes that touch refresh semantics must keep this path aligned.
  - the product already distinguishes cached data from live refresh in some places, but not through one uniform envelope shared by search, watchlist, and system status.
- dependencies identified:
  - backend response shape changes must be additive until the frontend consumer is updated in the same task; `/system/status.live_sync` and existing saved-search/watchlist fields cannot disappear mid-plan.
  - worker scheduling changes affect `saved searches`, `watchlist`, reminders, and push-triggered refresh semantics together.
  - notification and reminder delivery semantics must remain single-delivery under retry/locking changes; reliability work is not isolated to polling only.
  - diagnostics and observability should use the current FastAPI/worker boundaries instead of introducing a new service prematurely.
  - global backend/gateway health (`live_sync`) must remain conceptually separate from per-resource freshness/trust metadata.
  - PWA reliability UX depends on richer backend metadata; frontend-only polish is not enough for this scope.

## Development Approach
- **testing approach**: Regular
- **recommended implementation option**: add a reliability spine on top of the current architecture by separating `read-path` from `refresh-path`, standardizing freshness metadata through an additive compatibility bridge, and giving worker refresh operations explicit lifecycle semantics
- why this option:
  - it improves the real operational failure modes without forcing a high-risk queue-platform rewrite
  - it preserves the current product shape while making degradation, retries, and support diagnostics predictable
  - it creates a clean base for later security/rate-limit hardening and stronger operational tooling
- alternative options considered:
  - **Option B: freshness-only hardening**
    - pros: fastest path to better data trust
    - cons: leaves worker execution, observability, and supportability too implicit
  - **Option C: queue-first redesign**
    - pros: strongest long-term orchestration model
    - cons: too much architecture cost for the current scale and codebase state
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
- maintain backward compatibility where feasible, but prefer a single coordinated backend+frontend migration over long-lived duplicate contracts
- do not change `live_sync.status` semantics or remove existing response fields until the frontend consumer and tests are updated in the same task

## Testing Strategy
- **backend unit/integration tests**: required for every task
  - extend `backend/tests/test_system_status.py` for richer freshness/status semantics
  - extend `backend/tests/test_worker_main.py` for job execution summaries and degradation handling
  - extend `backend/tests/search/{test_search_api.py,test_saved_search_monitoring.py}` for cached-read vs refresh-path behavior and saved-search polling outcomes
  - extend `backend/tests/watchlist/test_watchlist_api.py` and `backend/tests/monitoring/{test_polling_policy.py,test_change_detection.py}` for watchlist freshness, priority scheduling, and near-auction behavior
  - extend `backend/tests/notifications/{test_push_delivery.py,test_push_subscriptions.py}` for reminder dedupe, push refresh-target compatibility, and delivery behavior under retries/failures
  - extend gateway/client-focused tests if observability or timeout taxonomy changes at the NAS boundary
- **frontend component/integration tests**: required for every UI-affecting task
  - extend `frontend/tests/app.test.tsx` for local reliability states, stale/degraded indicators, refresh-in-progress semantics, and diagnostics surfaces
- **e2e tests**: none currently committed
  - do not introduce a new e2e harness in this cycle
  - compensate with targeted backend tests plus frontend integration coverage and manual responsive checks
- **verification commands**:
  - `./.venv/bin/pytest backend/tests`
  - `npm --prefix frontend run test`
  - `npm --prefix frontend run build`

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix
- update plan if implementation deviates from original scope
- keep plan in sync with actual work done

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): code changes, tests, documentation updates
- **Post-Completion** (no checkboxes): manual outage drills, deployment config rollouts, production monitoring/alarm tuning

## Implementation Steps

### Task 1: Define an additive freshness contract and compatibility bridge

**Files:**
- Create: `backend/src/cartrap/modules/system_status/schemas.py`
- Modify: `backend/src/cartrap/modules/system_status/service.py`
- Modify: `backend/src/cartrap/api/system.py`
- Modify: `backend/src/cartrap/modules/search/schemas.py`
- Modify: `backend/src/cartrap/modules/watchlist/schemas.py`
- Modify: `backend/src/cartrap/modules/search/service.py`
- Modify: `backend/src/cartrap/modules/search/router.py`
- Modify: `backend/src/cartrap/modules/watchlist/service.py`
- Modify: `backend/src/cartrap/modules/watchlist/router.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `backend/tests/test_system_status.py`
- Modify: `backend/tests/search/test_search_api.py`
- Modify: `backend/tests/watchlist/test_watchlist_api.py`
- Modify: `frontend/tests/app.test.tsx`

- [x] define a shared freshness envelope for user-facing resources with fields such as `status`, `last_synced_at`, `stale_after`, `degraded_reason`, and `retryable`, while keeping existing fields intact during the migration
- [x] keep `/system/status.live_sync` as the global backend/gateway health contract and add per-resource freshness metadata separately instead of overloading one status object
- [x] serialize saved-search and watchlist responses with explicit freshness metadata in an additive way so the current UI remains functional during the transition
- [x] write backend tests for system-status success/degraded/stale transitions
- [x] write backend API tests for saved-search and watchlist freshness envelope behavior
- [x] write frontend compatibility tests for the additive contract bridge and unchanged degraded-mode gating
- [x] run targeted backend tests - must pass before task 2

### Task 2: Add explicit refresh execution primitives for worker flows

**Files:**
- Create: `backend/src/cartrap/modules/monitoring/job_runtime.py`
- Modify: `backend/src/cartrap/modules/monitoring/service.py`
- Modify: `backend/src/cartrap/modules/search/service.py`
- Modify: `backend/src/cartrap/modules/notifications/service.py`
- Modify: `backend/src/cartrap/modules/notifications/{models.py,repository.py}`
- Modify: `backend/src/cartrap/worker/main.py`
- Modify: `backend/tests/test_worker_main.py`
- Modify: `backend/tests/search/test_saved_search_monitoring.py`
- Modify: `backend/tests/monitoring/test_change_detection.py`
- Modify: `backend/tests/notifications/test_push_delivery.py`

- [x] introduce shared refresh execution primitives for job identity, lease/lock with TTL, attempt counting, and retry/backoff metadata
- [x] refactor saved-search polling and watchlist polling to report explicit job outcomes instead of silent loop-level side effects
- [x] prevent duplicate concurrent refreshes for the same saved search or tracked lot by enforcing per-resource execution keys
- [x] preserve single-delivery semantics for lot-change and auction-reminder pushes when retries or duplicate execution attempts occur
- [x] write backend tests for worker job lifecycle, duplicate-run protection, and retryable failure handling
- [x] write backend tests for saved-search/watchlist scheduling edge cases plus reminder/push dedupe around due-state recalculation
- [x] run targeted backend tests - must pass before task 3

### Task 3: Separate cached read-path from live refresh-path

**Files:**
- Modify: `backend/src/cartrap/modules/search/service.py`
- Modify: `backend/src/cartrap/modules/search/router.py`
- Modify: `backend/src/cartrap/modules/search/{schemas.py,repository.py}`
- Modify: `backend/src/cartrap/modules/watchlist/service.py`
- Modify: `backend/src/cartrap/modules/watchlist/router.py`
- Modify: `backend/src/cartrap/modules/watchlist/{schemas.py,repository.py}`
- Modify: `backend/src/cartrap/modules/monitoring/service.py`
- Modify: `backend/src/cartrap/modules/system_status/schemas.py`
- Modify: `backend/tests/search/test_search_api.py`
- Modify: `backend/tests/search/test_saved_search_monitoring.py`
- Modify: `backend/tests/watchlist/test_watchlist_api.py`
- Modify: `backend/tests/watchlist/test_snapshot_storage.py`
- Modify: `backend/tests/monitoring/test_change_detection.py`

- [x] ensure dashboard read endpoints always return the latest valid snapshot even when live sync is degraded
- [x] move manual/live refresh operations onto an explicit refresh-path that updates cache/state without making ordinary reads depend on upstream availability
- [x] extract the current watchlist read-time backfill behavior into a background repair or explicitly bounded compatibility path so legacy documents do not lose media/detail enrichment
- [x] classify refresh failures into retryable vs non-retryable groups and persist enough metadata for frontend/operator messaging
- [x] write backend tests for cached-read fallback when gateway/upstream fetch fails
- [x] write backend tests for live refresh success/failure without breaking read access to existing snapshots or legacy watchlist backfill behavior
- [x] run targeted backend tests - must pass before task 4

### Task 4: Implement priority scheduling and data-trust semantics

**Files:**
- Modify: `backend/src/cartrap/modules/monitoring/polling_policy.py`
- Modify: `backend/src/cartrap/modules/monitoring/service.py`
- Modify: `backend/src/cartrap/modules/search/service.py`
- Modify: `backend/src/cartrap/worker/main.py`
- Modify: `backend/tests/monitoring/test_polling_policy.py`
- Modify: `backend/tests/search/test_saved_search_monitoring.py`
- Modify: `backend/tests/test_worker_main.py`
- Modify: `backend/tests/notifications/test_push_delivery.py`

- [x] replace uniform due-processing with priority classes such as `auction_imminent`, `recently_changed`, `normal`, and `cold`
- [x] make near-auction watchlist freshness stricter than saved-search freshness so the system reflects auction-critical urgency
- [x] preserve one-shot auction reminder semantics and push-trigger compatibility while introducing new priority classes
- [x] record per-refresh outcome metadata needed for support diagnostics, stale detection, and derived counters like unseen/new changes
- [x] write backend tests for priority scheduling order and near-auction threshold behavior
- [x] write backend tests for refresh outcome persistence, derived-counter consistency, and reminder dedupe under priority scheduling
- [x] run targeted backend tests - must pass before task 5

### Task 5: Surface local reliability UX and diagnostics in the PWA

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/features/search/SearchPanel.tsx`
- Modify: `frontend/src/features/search/SearchResultsModal.tsx`
- Modify: `frontend/src/features/watchlist/WatchlistPanel.tsx`
- Modify: `frontend/src/features/push/PushSettingsModal.tsx`
- Modify: `frontend/src/features/dashboard/AccountMenuSheet.tsx`
- Modify: `frontend/public/sw.js`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] render local reliability states per saved search, watchlist lot, and results surface using the new backend freshness envelope
- [x] keep the current global live-sync banner semantics intact while adding per-resource trust states on top
- [x] distinguish `Live`, `Cached`, `Refreshing`, `Degraded`, and `Outdated` states without collapsing everything into one global banner
- [x] update manual refresh flows so the UI shows in-flight refresh, last successful sync, retryable failure, and cached-view fallback explicitly
- [x] keep service-worker push revalidation compatible with existing and new `refresh_targets` payloads so push-triggered refresh does not regress during the migration
- [x] expose a compact operator/support diagnostics surface with last successful sync, degraded reason, and refresh backlog summary
- [x] write frontend tests for per-resource reliability states, refresh transitions, and diagnostics visibility
- [x] run frontend tests for the updated dashboard flows - must pass before task 6

### Task 6: Add structured observability and operational diagnostics

**Files:**
- Modify: `backend/src/cartrap/core/logging.py`
- Modify: `backend/src/cartrap/modules/system_status/service.py`
- Modify: `backend/src/cartrap/modules/monitoring/service.py`
- Modify: `backend/src/cartrap/modules/search/service.py`
- Modify: `backend/src/cartrap/modules/copart_gateway/service.py`
- Modify: `backend/src/cartrap/modules/copart_provider/client.py`
- Modify: `backend/src/cartrap/worker/main.py`
- Modify: `docs/backend-api.md`
- Modify: `README.md`
- Modify: `backend/tests/test_worker_main.py`
- Modify: `backend/tests/copart/{test_gateway_router.py,test_gateway_client_config.py}`

- [x] add correlation identifiers and structured event logging across request, refresh, worker, and gateway-adjacent flows
- [x] log refresh start/success/failure events with enough fields to support latency, stale-count, and failure-rate metrics later
- [x] add gateway/client-side timeout and upstream-classification logging so NAS transport failures can be separated from primary-backend logic failures
- [x] document the new reliability contract and operator-facing diagnostics in backend/docs-facing documentation
- [x] write backend tests for structured logging/output contracts where practical
- [x] run targeted backend tests plus doc consistency review - must pass before task 7

### Task 7: Verify acceptance criteria
- [x] verify dashboard read paths still work when live refresh fails or gateway becomes degraded
- [x] verify saved searches and watchlist now expose explicit freshness/trust metadata instead of timestamp-only hints
- [x] verify duplicate concurrent refreshes are blocked and job outcomes are observable
- [x] verify near-auction lots receive stricter freshness handling than normal saved-search polling
- [x] verify push-triggered refresh and auction reminders still fire once with correct `refresh_targets`
- [x] run full backend test suite: `./.venv/bin/pytest backend/tests`
- [x] run full frontend test suite: `npm --prefix frontend run test`
- [x] run frontend production build: `npm --prefix frontend run build`

### Task 8: [Final] Update documentation
- [x] update `ChangeLog.md` for each implementation cycle during execution
- [x] update `README.md` and `docs/backend-api.md` to reflect the finalized reliability contract and diagnostics
- [ ] move this plan to `docs/plans/completed/`

## Technical Details
- Standardize a `freshness envelope` for user-facing resources so the frontend receives:
  - payload data
  - last successful sync timestamp
  - effective status (`live`, `cached`, `refreshing`, `degraded`, `outdated`)
  - stale threshold or derived freshness horizon
  - retryability and degraded reason metadata
- Keep global health and resource freshness separate:
  - `/system/status.live_sync` remains the backend/gateway health contract used by existing degraded-mode UX
  - saved-search/watchlist/search responses carry their own per-resource freshness/trust metadata
- Make contract changes additive first:
  - preserve existing keys like `last_synced_at`, `cached_result_count`, `has_unseen_update`, and current `live_sync.status` semantics until frontend consumers are migrated
  - remove or rename legacy fields only after frontend and tests no longer depend on them
- Treat refresh operations as controlled execution units rather than implicit side effects:
  - resource-scoped execution key
  - lease/lock with TTL
  - retry/backoff with jitter
  - outcome record including duration, attempt count, and classification of failure
- Keep the `NAS gateway` transport-focused:
  - upstream auth and HTTP transport remain there
  - stale/fallback/user-facing degradation decisions remain in the primary backend
- Preserve the current product behavior that cached data remains usable when live sync is unavailable, but make this an explicit contract instead of emergent behavior.
- The current watchlist read path performs opportunistic Copart backfill for legacy/incomplete documents:
  - do not remove this behavior without a compatibility replacement such as background repair or bounded lazy repair
- Push remains a `signal to revalidate`, not a source of truth:
  - UI state is updated only after backend refresh/read confirms the new snapshot
  - service worker payload derivation and backend `refresh_targets` must remain aligned during the migration
- Near-auction lots need stricter freshness policy than generic saved searches:
  - frontend thresholds and backend scheduling should align to avoid contradictory UX

## Post-Completion
*Items requiring manual intervention or external systems - no checkboxes, informational only*

**Manual verification**:
- simulate gateway timeout and confirm dashboard still renders cached watchlist/saved-search data with explicit degraded states
- simulate near-auction lot updates and confirm priority scheduling plus stricter stale treatment are visible in UI and logs
- verify PWA behavior after background/sleep resume, offline/online transitions, and push-triggered refreshes
- verify push-triggered refresh and auction-reminder delivery remain single-fire under retries or repeated worker cycles
- verify support/admin diagnostics are understandable without reading raw server logs

**External system updates**:
- configure production log aggregation/metric extraction to consume the new structured events
- add or tune alerting thresholds for repeated refresh failure, stale backlog growth, and push degradation
- review deployment/runtime config for timeout budgets, lock TTL defaults, and any gateway token-rotation follow-up
