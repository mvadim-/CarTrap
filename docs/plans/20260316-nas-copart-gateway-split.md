# NAS-Backed Copart Gateway Split

## Overview
- Винести весь outbound доступ до Copart із AWS у локальний NAS, який має робочу публічну IP-адресу та стабільний доступ до Copart API.
- Залишити AWS primary backend вузлом для `frontend`, auth, Mongo, watchlist state, worker scheduling, notifications і всієї бізнес-логіки.
- Додати вузький `copart-gateway` на NAS, який виконує сирі Copart-запити та повертає raw JSON назад в AWS.
- При недоступності NAS gateway не використовувати direct fallback у Copart; додаток має м’яко деградувати до режиму з уже синхронізованими даними з Mongo.

## Context (from discovery)
- files/components involved:
  - `backend/src/cartrap/modules/copart_provider/client.py`
  - `backend/src/cartrap/modules/copart_provider/service.py`
  - `backend/src/cartrap/modules/search/service.py`
  - `backend/src/cartrap/modules/watchlist/service.py`
  - `backend/src/cartrap/modules/monitoring/service.py`
  - `backend/src/cartrap/worker/main.py`
  - `backend/src/cartrap/modules/search/catalog_refresh.py`
  - `backend/src/cartrap/config.py`
  - `backend/src/cartrap/api/system.py`
  - `frontend/src/App.tsx`
  - `frontend/src/app/useSession.ts`
  - `frontend/src/lib/api.ts`
  - `frontend/src/features/dashboard/DashboardShell.tsx`
  - `frontend/tests/app.test.tsx`
  - `backend/tests/search/test_saved_search_monitoring.py`
  - `docker-compose.yml`
  - `README.md`
- related patterns found:
  - Copart integration already converges through `CopartProvider` and `CopartHttpClient`.
  - `SearchService`, `WatchlistService`, `MonitoringService`, and catalog refresh already depend on provider abstractions rather than raw `httpx` calls.
  - Worker already reads/writes state in Mongo on AWS and can remain the single source of truth for sync state and notifications.
- dependencies identified:
  - FastAPI backend + worker reuse the same backend package.
  - Frontend already consumes backend API only and can surface an offline/live-sync status banner without talking to NAS directly.
  - Deployment will require new NAS runtime secrets and network configuration outside this repository.

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
- maintain backward compatibility for the existing AWS-hosted API contract used by the frontend

## Testing Strategy
- **unit tests**: required for every task (see Development Approach above)
- **backend integration tests**:
  - gateway client request/response mapping
  - gateway-unavailable handling in search/watchlist/monitoring flows
  - saved-search polling behavior during gateway degradation
  - system status exposure for frontend offline-mode UX
- **performance-sensitive transport tests**:
  - connection reuse / keep-alive behavior for repeated AWS-to-NAS calls
  - gzip handling for larger search payloads
- **frontend tests**:
  - offline/live-sync unavailable banner rendering
  - dashboard behavior when cached Mongo-backed data is available but live Copart actions are unavailable
- **e2e tests**: no dedicated Playwright/Cypress suite is currently committed, so rely on backend/frontend automated tests plus manual end-to-end verification after deployment

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with `➕` prefix
- document issues/blockers with `⚠️` prefix
- update plan if implementation deviates from original scope
- keep plan in sync with actual work done

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): code, tests, and documentation changes inside this repository
- **Post-Completion** (no checkboxes): NAS deployment, DNS, router, firewall, TLS, and operational rollout steps outside this codebase

## Implementation Steps

### Task 1: Define shared gateway contract and configuration

**Files:**
- Modify: `backend/src/cartrap/config.py`
- Modify: `backend/src/cartrap/modules/copart_provider/client.py`
- Create: `backend/src/cartrap/modules/copart_provider/errors.py`
- Create: `backend/tests/copart/test_gateway_client_config.py`

- [ ] add gateway-related settings such as `COPART_GATEWAY_BASE_URL`, `COPART_GATEWAY_TOKEN`, timeout settings, and optional compression flags in `backend/src/cartrap/config.py`
- [ ] refactor `backend/src/cartrap/modules/copart_provider/client.py` into a transport-friendly shape where direct Copart HTTP logic and NAS gateway HTTP logic can share a stable interface returning raw payloads plus metadata
- [ ] ensure the AWS-to-NAS transport uses reusable long-lived HTTP clients/connections instead of per-request client recreation, so keep-alive actually improves latency
- [ ] define explicit gateway error types for unavailable gateway, upstream Copart rejection, and malformed gateway responses
- [ ] write tests for configuration parsing and client selection success cases
- [ ] write tests for missing/invalid gateway configuration, error mapping, and repeated-call connection reuse edge cases
- [ ] run tests - must pass before next task

### Task 2: Add NAS gateway service skeleton and raw Copart proxy endpoints

**Files:**
- Create: `backend/src/cartrap/gateway_app.py`
- Create: `backend/src/cartrap/modules/copart_gateway/router.py`
- Create: `backend/src/cartrap/modules/copart_gateway/schemas.py`
- Create: `backend/src/cartrap/modules/copart_gateway/service.py`
- Create: `backend/tests/copart/test_gateway_router.py`
- Modify: `backend/Dockerfile`

- [ ] add a minimal FastAPI gateway entrypoint for NAS deployment that exposes `POST /v1/search`, `POST /v1/lot-details`, `POST /v1/search-count`, and `GET /v1/search-keywords`
- [ ] protect gateway endpoints with bearer-token authentication and keep responses as raw Copart payloads with optional metadata like `etag`
- [ ] ensure gateway responses support efficient payload delivery for large search results, preferring HTTP gzip over manual JSON wrapping
- [ ] write tests for gateway endpoint success paths and raw payload passthrough
- [ ] write tests for auth failures, upstream Copart errors, and malformed request payloads
- [ ] run tests - must pass before next task

### Task 3: Route AWS backend Copart traffic through NAS gateway

**Files:**
- Modify: `backend/src/cartrap/modules/copart_provider/service.py`
- Modify: `backend/src/cartrap/modules/search/service.py`
- Modify: `backend/src/cartrap/modules/watchlist/service.py`
- Modify: `backend/src/cartrap/modules/monitoring/service.py`
- Modify: `backend/src/cartrap/worker/main.py`
- Modify: `backend/src/cartrap/modules/search/catalog_refresh.py`
- Modify: `backend/tests/search/test_search_api.py`
- Modify: `backend/tests/search/test_saved_search_monitoring.py`
- Modify: `backend/tests/watchlist/test_watchlist_api.py`
- Modify: `backend/tests/monitoring/test_change_detection.py`

- [ ] wire `CopartProvider` to prefer NAS gateway transport when `COPART_GATEWAY_BASE_URL` is configured while preserving the existing raw payload contract expected by normalization code
- [ ] keep AWS normalization, snapshot comparison, Mongo writes, and notification flows unchanged apart from transport substitution
- [ ] route all Copart-dependent worker flows through the gateway path, including tracked-lot polling, saved-search polling, and catalog refresh jobs
- [ ] make worker sync cycles treat gateway outages as transient external failures rather than process-fatal errors
- [ ] write tests for search/watchlist/monitoring/saved-search success paths using gateway-backed raw responses
- [ ] write tests for gateway unavailable/error scenarios and verify AWS services degrade predictably without direct Copart fallback
- [ ] run tests - must pass before next task

### Task 4: Expose live-sync availability from backend

**Files:**
- Create: `backend/src/cartrap/modules/system_status/repository.py`
- Create: `backend/src/cartrap/modules/system_status/service.py`
- Modify: `backend/src/cartrap/api/system.py`
- Modify: `backend/src/cartrap/api/router.py`
- Modify: `backend/src/cartrap/modules/search/service.py`
- Modify: `backend/src/cartrap/modules/monitoring/service.py`
- Modify: `backend/src/cartrap/worker/main.py`
- Create: `backend/tests/test_system_status.py`

- [ ] extend system/status API surface so the frontend can detect whether live Copart sync is currently available via NAS gateway
- [ ] define a stable response shape that distinguishes `service healthy` from `live_sync degraded`, without breaking existing health checks
- [ ] persist recent gateway success/failure state in a backend-safe shared store that both web app and worker processes can read/write, rather than relying on in-memory app state
- [ ] update both request-path failures and worker-path failures to record that shared live-sync status consistently
- [ ] write tests for healthy status responses and degraded live-sync state exposure
- [ ] write tests for edge cases such as stale failure markers or partial subsystem availability
- [ ] run tests - must pass before next task

### Task 5: Add frontend offline-mode UX for live Copart outages

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/features/dashboard/DashboardShell.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [ ] fetch backend live-sync status on app bootstrap and after relevant user actions that depend on fresh Copart data
- [ ] show a clear banner/message that the app is operating with locally stored data only when NAS gateway or live sync is unavailable
- [ ] keep previously synced Mongo-backed data visible while surfacing actionable failure messaging for live Copart actions, without requiring broad UI disabling as part of the first implementation
- [ ] write frontend tests for the degraded/offline banner success path and recovery path
- [ ] write frontend tests for user-visible edge cases when live search/watchlist refresh actions fail during degraded mode
- [ ] run tests - must pass before next task

### Task 6: Document NAS deployment and operational workflow

**Files:**
- Modify: `README.md`
- Modify: `backend/README.md`
- Modify: `docker-compose.yml`
- Modify: `ChangeLog.md`

- [ ] document the split deployment model: AWS primary backend plus NAS-hosted `copart-gateway`
- [ ] document required environment variables, bearer auth, gzip expectations, and the no-fallback degraded-mode behavior
- [ ] add a local/docker-friendly way to run the gateway service for development or NAS deployment packaging
- [ ] write/update tests or verification notes for repository-level deployment commands and config examples where applicable
- [ ] run relevant verification commands and record results before closing implementation

### Task 7: Verify acceptance criteria
- [ ] verify all requirements from Overview are implemented
- [ ] verify edge cases are handled
- [ ] run full backend test suite: `./.venv/bin/pytest backend/tests`
- [ ] run frontend tests: `npm --prefix frontend run test`
- [ ] run frontend production build: `npm --prefix frontend run build`

### Task 8: [Final] Update documentation
- [ ] update `README.md` if needed
- [ ] update `AGENTS.md`-adjacent workflow documentation only if new repo-local patterns are discovered
- [ ] move this plan to `docs/plans/completed/` after implementation stabilizes

## Technical Details
- AWS-to-NAS communication should use HTTPS with keep-alive and bearer-token auth; avoid WebSocket complexity because the interaction model is synchronous RPC, not streaming.
- NAS gateway should return raw Copart JSON with minimal wrapping to avoid double serialization overhead and to preserve existing normalization code on AWS.
- Large search responses should rely on standard HTTP compression (`gzip`) at the gateway or reverse proxy layer instead of custom compressed payload fields.
- `CopartProvider` remains the boundary consumed by search/watchlist/monitoring/catalog flows; the transport swap should be hidden behind provider/client selection rather than spread through service code.
- The transport layer must preserve connection reuse semantics; otherwise the current per-call provider/client lifecycle will erase most latency wins from moving Copart access to NAS.
- Degraded mode should be explicit:
  - manual search returns a controlled backend error that frontend can translate into an offline/live-sync message
  - worker records gateway outage and skips sync work for that cycle
  - saved-search polling records degradation without breaking the worker loop
  - Mongo-backed cached/tracked data remains readable
- The health model should separate:
  - core API health (`status=ok`)
  - live sync state (`available` vs `degraded`)
  - and it should be backed by shared persisted status visible to both API and worker processes

## Post-Completion
*Items requiring manual intervention or external systems - no checkboxes, informational only*

**Manual verification**
- Verify NAS public IP still reaches Copart with the same credentials and header profile used by the gateway service.
- Verify AWS public IP cannot call the Copart endpoints directly once the transport switch is enabled, confirming that all live traffic is actually routed through NAS.
- Test dashboard UX from a browser while intentionally shutting down the NAS gateway to confirm offline-mode messaging and cached-data visibility.
- Load-test representative search payload sizes to confirm gzip materially reduces bandwidth and does not cause timeout regressions on NAS hardware.

**External system updates**
- Configure NAS reverse proxy/TLS termination, bearer secret storage, and IP allowlist for the AWS static IP.
- Expose the NAS gateway through router/NAT or a dedicated public hostname and verify certificate renewal.
- Add deployment automation or container restart policy for the NAS gateway.
- Update AWS production `.env` with `COPART_GATEWAY_BASE_URL`, `COPART_GATEWAY_TOKEN`, and gateway-specific timeouts.
- Decide whether NAS gateway logs remain local or are forwarded to centralized logging for troubleshooting.
