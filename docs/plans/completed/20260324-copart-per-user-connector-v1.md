# Copart Per-User Connector V1

## Overview
- Замінити поточну глобальну Copart session-конфігурацію на `per-user` connector, де кожен користувач CarTrap має власне підключення до Copart.
- Побудувати V1 без зберігання Copart password після успішного bootstrap: система зберігає лише зашифрований session bundle і переводить connection у `reconnect_required`, коли upstream auth більше не валідний.
- Реалізувати flow через наявну split-архітектуру `frontend -> AWS backend -> NAS copart-gateway -> Copart`, не використовуючи browser popup/webview interception.
- Зберегти поточну ідею degraded-mode: user-specific auth issue має відображатись окремо від gateway/global outage.
- Перед повним rollout пройти окремий feasibility gate для native `login -> challenge -> lot-details` replay; якщо plain HTTP execution не проходить стабільно, execution strategy треба переглянути до початку domain/UI rollout.

## Context (from discovery)
- files/components involved:
  - `frontend/src/App.tsx`
  - `frontend/src/types.ts`
  - `frontend/src/lib/api.ts`
  - `frontend/src/features/dashboard/AccountMenuSheet.tsx`
  - `frontend/tests/app.test.tsx`
  - `backend/src/cartrap/api/router.py`
  - `backend/src/cartrap/config.py`
  - `backend/src/cartrap/modules/copart_provider/client.py`
  - `backend/src/cartrap/modules/copart_provider/service.py`
  - `backend/src/cartrap/modules/copart_gateway/{router.py,schemas.py,service.py}`
  - `backend/src/cartrap/modules/search/service.py`
  - `backend/src/cartrap/modules/watchlist/service.py`
  - `backend/src/cartrap/modules/monitoring/service.py`
  - `backend/src/cartrap/worker/main.py`
  - `backend/src/cartrap/db/mongo.py`
  - `backend/tests/copart/{test_gateway_router.py,test_gateway_backed_services.py,test_http_client.py}`
  - `backend/tests/search/test_search_api.py`
  - `backend/tests/watchlist/test_watchlist_api.py`
  - `backend/tests/monitoring/test_change_detection.py`
- related patterns found:
  - Поточний Copart transport уже зібраний у `CopartHttpClient` і gateway proxy, тому user-scoped session execution можна додати як новий transport path без переписування нормалізації payload-ів.
  - Reliability spine вже розділяє cached read-path і live refresh-path; це дозволяє м’яко додати `reconnect_required` без лому існуючого cached UX.
  - Frontend already surfaces resource-level diagnostics and account-level reliability summary, тож connector status природно лягає в account/settings surface.
- dependencies identified:
  - Mongo є центральним persistence layer для backend + worker shared state.
  - NAS gateway already exists as dedicated Copart execution plane protected bearer-auth контрактом.
  - Copart native login flow з Charles показує, що робоча session складається не з одного токена, а з `SessionID + Imperva cookies + x-d-token + device/app headers + challenge side effects`.

## Development Approach
- **testing approach**: Regular (code first, then tests)
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
- maintain backward compatibility for current frontend API contracts where possible; any new connector fields should be additive

## Testing Strategy
- **unit tests**: required for every task (see Development Approach above)
- **feasibility tests**:
  - native login bootstrap + challenge replay + lot-details smoke path
  - extraction of rotated `SessionID`, Imperva cookies, `x-d-token`, and `ins-sess`
  - explicit signal when plain HTTP replay is insufficient and browser/native fallback is required
- **backend integration tests**:
  - gateway bootstrap success/failure and challenge replay
  - encrypted session bundle persistence/update semantics
  - user-scoped lot-details/search execution through gateway
  - transition to `reconnect_required` on auth failure
  - separation of `gateway unavailable` vs `connection auth invalid`
- **frontend tests**:
  - account/settings connector status rendering
  - reconnect-required system notice
  - disabled/guarded live actions when connection requires re-login
  - successful connect/reconnect/disconnect happy paths with mocked API
- **worker regression tests**:
  - saved-search/watchlist monitoring skips user resources with `reconnect_required`
  - transient gateway outages do not permanently invalidate user connections
- **e2e tests**: dedicated browser e2e suite is not committed, so rely on backend/frontend automated tests plus manual verification after deployment

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with `➕` prefix
- document issues/blockers with `⚠️` prefix
- update plan if implementation deviates from original scope
- keep plan in sync with actual work done

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): code, tests, documentation changes inside this repository
- **Post-Completion** (no checkboxes): Copart account validation, NAS secret rotation, production rollout, and upstream behavior checks outside this repository

## Implementation Steps

### Task 0: Prove gateway feasibility for native login, challenge, and lot-details replay

**Files:**
- Modify: `backend/src/cartrap/modules/copart_gateway/service.py`
- Modify: `backend/src/cartrap/modules/copart_provider/client.py`
- Create: `backend/tests/copart/test_gateway_connector_flow.py` (implemented as the feasibility + gateway contract suite)
- Modify: `docs/plans/20260324-copart-per-user-connector-v1.md`

- [x] prototype isolated helper methods for `login -> challenge -> lot-details` replay using the observed native Copart flow
- [x] verify whether plain HTTP execution can preserve `SessionID`, Imperva cookies, `x-d-token`, and `ins-sess` without browser automation
- [x] define explicit go/no-go criteria for continuing with HTTP-only gateway execution and update this plan immediately if fallback is required
- [x] write feasibility tests for happy-path login/challenge/lot-details replay
- [x] write feasibility tests for challenge failure, auth failure, and rotated-session extraction edge cases
- [x] run tests - must pass before task 1

### Task 1: Define provider-connection domain model and repository

**Files:**
- Create: `backend/src/cartrap/modules/provider_connections/models.py`
- Create: `backend/src/cartrap/modules/provider_connections/repository.py`
- Create: `backend/src/cartrap/modules/provider_connections/schemas.py`
- Create: `backend/src/cartrap/modules/provider_connections/service.py`
- Modify: `backend/src/cartrap/db/mongo.py`
- Create: `backend/tests/provider_connections/test_repository.py`

- [x] create `provider_connections` domain objects with statuses `connected`, `expiring`, `reconnect_required`, `disconnected`, and `error`
- [x] define the invariant of exactly one active connection per `(user_id, provider)` and codify reconnect/account-switch replacement policy for existing saved searches and tracked lots
- [x] define Mongo persistence shape for connection metadata, encrypted session bundle, `bundle_version`, expiry timestamps, and last error state
- [x] add repository helpers for create/update/disconnect/find-by-user-provider and compare-and-swap bundle refresh writes
- [x] write repository tests for create/update/disconnect success paths
- [x] write repository tests for state transitions, unique active connection semantics, and stale-version edge cases
- [x] run tests - must pass before task 2

### Task 2: Add backend API surface for connect/reconnect/disconnect/status

**Files:**
- Create: `backend/src/cartrap/modules/provider_connections/router.py`
- Modify: `backend/src/cartrap/api/router.py`
- Modify: `backend/src/cartrap/api/dependencies.py`
- Create: `backend/tests/provider_connections/test_router.py`

- [x] add authenticated endpoints for listing user provider connections and returning additive connector status payloads
- [x] add `connect`, `reconnect`, and `disconnect` handlers for Copart connections
- [x] ensure connect/reconnect request bodies are never logged and redact credentials from error/log paths
- [x] write API tests for list/connect/reconnect/disconnect success cases, including replacement of an existing active Copart connection for the same user
- [x] write API tests for auth failures, invalid payloads, and not-found/ownership edge cases
- [x] run tests - must pass before task 3

### Task 3: Extend NAS gateway with connector bootstrap, verify, and execute contracts

**Files:**
- Modify: `backend/src/cartrap/config.py`
- Modify: `backend/src/cartrap/modules/copart_gateway/schemas.py`
- Modify: `backend/src/cartrap/modules/copart_gateway/router.py`
- Modify: `backend/src/cartrap/modules/copart_gateway/service.py`
- Create: `backend/tests/copart/test_gateway_connector_flow.py`
- Modify: `backend/tests/test_config.py`

- [x] add gateway request/response schemas for `bootstrap`, `verify`, and user-scoped `execute` operations using encrypted session bundle payloads
- [x] implement gateway service methods for native-style login bootstrap, challenge replay, verify call, and session bundle re-encryption
- [x] add connector-related settings for gateway encryption key/version, session-expiring threshold, mobile app-profile defaults, and connect rate-limit knobs
- [x] keep existing raw proxy endpoints working while introducing the new connector-specific internal contract
- [x] write gateway tests for bootstrap/verify/execute success paths with mocked upstream responses and config-backed encryption/profile setup
- [x] write gateway tests for invalid credentials, challenge failure, malformed bundle, and upstream auth expiry cases
- [x] run tests - must pass before task 4

### Task 4: Refactor Copart client/transport to support mutable user-scoped session bundles

**Files:**
- Modify: `backend/src/cartrap/modules/copart_provider/client.py`
- Modify: `backend/src/cartrap/modules/copart_provider/service.py`
- Modify: `backend/tests/copart/test_http_client.py`

- [x] extract a reusable session-bundle/header-profile model covering `SessionID`, Imperva cookies, `x-d-token`, `deviceid`, `ins-sess`, and mobile header profile
- [x] add transport support for executing requests from a supplied session bundle and returning rotated bundle state when upstream changes cookies/tokens
- [x] keep current env-based direct/gateway fallback available for admin/legacy flows until the new connector path is fully wired
- [x] write transport tests for bundle-based lot-details/search execution success and bundle rotation updates
- [x] write transport tests for auth/session failures, missing bundle fields, and challenge-sensitive edge cases
- [x] run tests - must pass before task 5

### Task 5: Route manual lot-details and search through user provider connections

**Files:**
- Modify: `backend/src/cartrap/modules/search/service.py`
- Modify: `backend/src/cartrap/modules/watchlist/service.py`
- Modify: `backend/src/cartrap/modules/search/router.py`
- Modify: `backend/src/cartrap/modules/watchlist/router.py`
- Modify: `backend/src/cartrap/modules/search/schemas.py`
- Modify: `backend/src/cartrap/modules/watchlist/schemas.py`
- Modify: `backend/src/cartrap/modules/provider_connections/service.py`
- Modify: `backend/tests/search/test_search_api.py`
- Modify: `backend/tests/watchlist/test_watchlist_api.py`

- [x] resolve active Copart connection for the authenticated user before any live Copart search or explicit watchlist refresh call
- [x] extend search/watchlist payloads with additive connection diagnostics for `connection_missing` and `reconnect_required` so cached read-paths can explain live-action failures
- [x] short-circuit live actions with a controlled domain error when the user has no connection or `reconnect_required`
- [x] persist updated encrypted bundle metadata after successful live operations using compare-and-swap or retry-on-version-conflict semantics
- [x] write API/service tests for user-scoped search/watchlist live success cases
- [x] write API/service tests for `connection_missing`, `reconnect_required`, gateway-vs-auth-failure distinctions, and stale-bundle-write conflicts
- [x] run tests - must pass before task 6

### Task 6: Integrate worker and monitoring paths with connector state

**Files:**
- Modify: `backend/src/cartrap/modules/monitoring/service.py`
- Modify: `backend/src/cartrap/worker/main.py`
- Modify: `backend/src/cartrap/modules/provider_connections/service.py`
- Modify: `backend/tests/monitoring/test_change_detection.py`
- Modify: `backend/tests/test_worker_main.py`

- [x] make saved-search and tracked-lot polling resolve the owning user’s Copart connection before attempting live refresh
- [x] treat `reconnect_required` as a user-scoped blocking condition that records refresh failure metadata without poisoning global live-sync status
- [x] ensure transient gateway/network outages remain retryable external failures and do not invalidate provider connections
- [x] ensure worker refreshes use version-aware bundle updates and do not clobber concurrent user-driven session refreshes
- [x] write worker/monitoring tests for skip semantics and retry behavior when user connections are invalid
- [x] write worker/monitoring tests distinguishing auth invalidation from gateway unavailability and validating version-conflict retry behavior
- [x] run tests - must pass before task 7

### Task 7: Add frontend connector management UX and system notice

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/features/dashboard/AccountMenuSheet.tsx`
- Modify: `frontend/src/features/search/SearchPanel.tsx`
- Modify: `frontend/src/features/search/SearchResultsModal.tsx`
- Modify: `frontend/src/features/watchlist/WatchlistPanel.tsx`
- Create: `frontend/src/features/integrations/CopartConnectionCard.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] add frontend types/API helpers for listing, connecting, reconnecting, and disconnecting Copart provider connections
- [x] render account/settings connector surface with `Connected`, `Expiring soon`, `Reconnect required`, and `Disconnected` states
- [x] surface additive resource-level `connection_missing` / `reconnect_required` diagnostics in saved-search and watchlist flows without regressing cached-data UX
- [x] show persistent account-level notice when Copart requires re-login and action-level messaging on affected live surfaces
- [x] write frontend tests for connector status rendering and connect/reconnect/disconnect success flows
- [x] write frontend tests for reconnect-required notice, resource-level diagnostics, and guarded live action behavior
- [x] run tests - must pass before task 8

### Task 8: Harden observability and secret-handling rules

**Files:**
- Modify: `backend/src/cartrap/core/logging.py`
- Modify: `backend/src/cartrap/modules/provider_connections/service.py`
- Modify: `backend/src/cartrap/modules/copart_gateway/service.py`
- Modify: `backend/tests/provider_connections/test_router.py`

- [x] add redaction for Copart credentials, session cookies, and `x-d-token` in structured logs
- [x] log connector lifecycle events (`connect.success`, `connect.failed`, `execute.auth_invalid`, `disconnect.success`) with safe metadata only
- [x] ensure error surfaces returned to frontend are domain-safe and never leak raw upstream session artifacts
- [x] ensure repeated background auth failures do not create noisy duplicate state transitions or contradictory connector notices for the same connection
- [x] write tests asserting redaction and safe error mapping behavior
- [x] write tests for connector lifecycle event logging and duplicate-state suppression where practical
- [x] run tests - must pass before task 9

### Task 9: Verify acceptance criteria
- [x] verify all requirements from Overview are implemented
- [x] verify user-specific auth failures do not masquerade as global gateway degradation
- [x] verify legacy saved searches and tracked lots remain readable and surface `connection_missing` until the user connects Copart
- [x] run backend test suite segments covering provider-connections, copart, search, watchlist, monitoring, and worker
- [x] run frontend tests: `npm --prefix frontend run test -- app.test.tsx`
- [x] run frontend production build: `npm --prefix frontend run build`

### Task 10: [Final] Update documentation
- [x] update `README.md` with per-user Copart connector behavior and reconnect expectations
- [x] update `docs/backend-api.md` with provider-connections endpoints and error taxonomy
- [x] update `ChangeLog.md` and move this plan to `docs/plans/completed/` after implementation stabilizes

## Technical Details
- Copart auth for V1 should be modeled as a mutable `session bundle`, not a single token.
- The bundle must include:
  - `SessionID`
  - Imperva cookies (`incap_ses_*`, `nlbi_*`, `visid_incap_*`)
  - `x-d-token`
  - `deviceid`
  - `ins-sess`
  - stable mobile headers (`devicename`, `sitecode`, `company`, `os`, `languagecode`, `clientappversion`, `User-Agent`)
- Gateway bootstrap flow should follow the observed native shape:
  - create/generate device-scoped IDs
  - obtain initial Imperva cookies
  - `POST /mds-api/v1/member/login`
  - run identity/bootstrap endpoints
  - execute challenge flow
  - verify bundle with `me-info` or `lot-details`
- `session_expires_at` should be derived from upstream `Set-Cookie: SessionID=... Expires=...` when present.
- Connector invariant:
  - exactly one active Copart connection per `(user_id, provider)`
  - reconnect/account-switch replaces the existing active connection in place
  - existing saved searches and tracked lots owned by that user automatically bind to the latest active connection for `provider=copart`
- Session bundle writes must be versioned:
  - persist `bundle_version`
  - gateway execute/verify calls may return rotated bundle state
  - backend/worker writes must use compare-and-swap or explicit retry on stale version
- Status policy:
  - `connected`: latest verify or execute succeeded
  - `expiring`: expiry threshold reached but session still works
  - `reconnect_required`: upstream auth invalid or expiry passed
  - `disconnected`: user intentionally removed connector
  - `error`: bundle corruption/decryption/config issue
- Error semantics:
  - user auth invalidation must be additive resource-level failure metadata
  - resources without an active Copart connection should expose `connection_missing` in additive refresh diagnostics rather than failing as generic 5xx errors
  - gateway outage remains a system/live-sync degradation signal
  - cached read-paths remain accessible even when connector auth is invalid
- Rollout behavior:
  - existing users will initially have no active Copart connection after deployment
  - pre-existing saved searches and tracked lots should remain readable and show controlled `connection_missing` guidance until the user connects
  - no destructive migration of saved-search/watchlist data is required; only additive refresh metadata should change
- Retention behavior:
  - active connection record keeps the latest ciphertext only
  - disconnected connections should clear ciphertext promptly
  - long-lived errored/disconnected metadata may be retained temporarily for audit/debug, then cleaned up by policy outside V1 scope

## Post-Completion
*Items requiring manual intervention or external systems - no checkboxes, informational only*

**Manual verification**
- Validate that a fresh Copart account can connect, search, and fetch lot details from the deployed NAS gateway.
- Verify reconnect UX by intentionally invalidating the session and confirming the app shows `Reconnect required` in account/settings and on affected live actions.
- Confirm cached saved-search/watchlist data remains visible while explicit live actions are blocked by connector auth issues.
- Confirm pre-existing users with saved searches/watchlist but no connector see controlled `connection_missing` UX immediately after rollout.
- Validate multiple users with separate Copart accounts do not share session state.

**External system updates**
- Provision and rotate a dedicated gateway encryption key for session bundle ciphertext.
- Review NAS secret storage and process environment handling for `x-d-token` / app-profile configuration.
- Verify Copart native login/challenge behavior in production-like conditions after any app version bump.
- Decide whether connector lifecycle logs should be forwarded from NAS to centralized observability.
- Rotate the Copart credentials, cookies, and tokens exposed during Charles-based discovery before any production use.
