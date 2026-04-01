# Admin Runtime Settings for Polling and Ops Tuning

## Overview
- Винести частину не-секретних operational параметрів з `.env` у поточний `admin command center`, щоб admin міг змінювати runtime-поведінку без code change і без нового deploy.
- Перша ітерація покриває лише safe runtime settings, які реально впливають на polling, freshness і operator workflow: intervals, windows, reminder offsets, retry backoff і invite TTL.
- Джерелом правди для override має стати Mongo-backed runtime settings overlay, а `.env` лишається bootstrap default і fallback.
- Зміни повинні застосовуватись не лише в web API, а й у `worker`, інакше admin UI буде змінювати значення “для вигляду”, але фактичний polling runtime лишиться старим.

## Context (from discovery)
- files/components involved:
  - `backend/src/cartrap/config.py`
  - `backend/src/cartrap/app.py`
  - `backend/src/cartrap/api/dependencies.py`
  - `backend/src/cartrap/worker/main.py`
  - `backend/src/cartrap/api/system.py`
  - `backend/src/cartrap/modules/admin/{router.py,service.py,schemas.py}`
  - `backend/src/cartrap/modules/auth/service.py`
  - `backend/src/cartrap/modules/search/router.py`
  - `backend/src/cartrap/modules/search/service.py`
  - `backend/src/cartrap/modules/watchlist/router.py`
  - `backend/src/cartrap/modules/monitoring/service.py`
  - `backend/src/cartrap/modules/monitoring/job_runtime.py`
  - `backend/src/cartrap/modules/system_status/service.py`
  - `frontend/src/{App.tsx,lib/api.ts,types.ts,styles.css}`
  - `frontend/src/features/admin/`
  - `frontend/tests/app.test.tsx`
  - `backend/tests/admin/`
  - `backend/tests/test_system_status.py`
  - `backend/tests/test_worker_main.py`
- related patterns found:
  - admin functionality already lives under `/api/admin/*`, so runtime settings should extend the existing admin surface instead of creating a new router tree.
  - current settings are read from `request.app.state.settings` in API services and once at worker startup in `backend/src/cartrap/worker/main.py`, so runtime override needs an explicit resolution layer.
  - invite creation currently resolves TTL inside `AuthService` from startup `Settings`, so `invite_ttl_hours` needs runtime-aware wiring through app dependencies and not only through admin endpoints.
  - admin workspace already exists in frontend and can host a dedicated `Runtime Settings` panel without introducing new routing.
  - current operational knobs are split between env-backed config (`saved_search_poll_interval_minutes`, watchlist polling windows, `invite_ttl_hours`) and hardcoded module constants (`LIVE_SYNC_STALE_AFTER`, `AUCTION_REMINDER_OFFSETS_MINUTES`, `DEFAULT_JOB_RETRY_BACKOFF_SECONDS`), with actual consumers spread across `auth`, `search`, `monitoring`, `system_status`, and `worker`.
- dependencies identified:
  - changing effective settings affects `system/status`, admin overview freshness calculations, request-scoped service factories, and worker polling loop behavior.
  - runtime settings UI requires typed metadata: key, label, description, default value, current effective value, bounds, category, and mutability.
  - non-secret allowlist must be enforced server-side; secret or infra settings must remain env-only.

## Development Approach
- **testing approach**: Regular
- **recommended implementation option**: додати Mongo-backed runtime settings overlay з жорстким allowlist і request/cycle-time resolution effective values.
- why this option:
  - не ламає поточний `.env` bootstrap flow і не вимагає міграції всіх settings одразу.
  - дає real runtime effect у web і worker без ручного рестарту процесів.
  - створює foundation для майбутніх admin-configurable settings без відкриття секретів у UI.
- alternative options considered:
  - **Option B: редагувати `.env` з адмінки**
    - pros: один source of truth
    - cons: небезпечно, restart-dependent, конфліктує з deploy/secret management
  - **Option C: винести все у БД одразу**
    - pros: повна runtime configurability
    - cons: занадто широкий scope, високий ризик для secrets і gateway/infra config
- scope першої ітерації:
  - включити лише settings з `restart_required = false`
  - не чіпати secrets, gateway tokens/URLs, JWT secrets, encryption keys, DB/CORS/VAPID config
  - advanced HTTP timeouts/rate limits можна підготувати метаданими, але не обов’язково відкривати в першому UI rollout
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
- **CRITICAL: all tests must pass before starting next task**
- **CRITICAL: update this plan file when scope changes during implementation**
- keep backward compatibility with existing env-only startup flow
- ensure non-admin users cannot see or call runtime settings APIs

## Testing Strategy
- **backend unit/integration tests**:
  - add tests for runtime settings metadata, validation, persistence, default fallback, reset-to-default, and audit metadata
  - add admin API tests for list/update/reset endpoints and admin-only access control
  - extend `test_system_status.py` to verify freshness policies use effective runtime values
  - extend `test_worker_main.py` to verify each poll cycle resolves fresh runtime values instead of using only startup values
  - extend `test_app_boot.py` to verify runtime settings resolver is registered on app state and wired into request-scoped services
  - extend auth/admin invite tests to verify changed `invite_ttl_hours` affects newly created invites
- **frontend integration tests**:
  - extend `frontend/tests/app.test.tsx` for runtime settings panel rendering, edit/save/reset flows, validation errors, and admin-only visibility
  - verify regular users do not trigger runtime settings API calls
- **manual verification**:
  - change poll intervals in admin UI and confirm `/api/system/status` reflects new values
  - run/observe a worker cycle with non-default values
  - reset one setting to default and verify fallback path
- **verification commands**:
  - `./.venv/bin/pytest backend/tests/admin`
  - `./.venv/bin/pytest backend/tests/test_system_status.py backend/tests/test_worker_main.py`
  - `./.venv/bin/pytest backend/tests`
  - `npm --prefix frontend test`
  - `npm --prefix frontend run build`

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with `➕` prefix
- document issues/blockers with `⚠️` prefix
- keep this plan aligned with actual implementation order

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): backend runtime settings domain, effective settings resolution, admin API, frontend settings panel, tests, docs
- **Post-Completion** (no checkboxes): production smoke-checks, ops rollout policy, deciding whether advanced timeout/rate-limit settings should be exposed later

## Implementation Steps

### Task 1: Introduce runtime settings domain and safe allowlist

**Files:**
- Modify: `backend/src/cartrap/config.py`
- Create: `backend/src/cartrap/modules/runtime_settings/{models.py,repository.py,schemas.py,service.py}`
- Create: `backend/tests/runtime_settings/test_runtime_settings_service.py`
- Modify: `backend/tests/test_config.py`

- [ ] define allowlisted runtime setting keys, categories, labels, descriptions, value types, defaults, bounds, and `restart_required` metadata in a dedicated runtime settings domain
- [ ] implement Mongo-backed persistence for overrides and effective-value resolution with fallback to `.env` defaults
- [ ] include audit fields on each override (`updated_by`, `updated_at`) and reset-to-default semantics
- [ ] write tests for metadata resolution, default fallback, valid override persistence, and reset flow
- [ ] write tests for invalid values, out-of-range bounds, and disallowed keys
- [ ] run targeted runtime-settings backend tests - must pass before task 2

### Task 2: Wire effective runtime settings into API and worker execution paths

**Files:**
- Modify: `backend/src/cartrap/app.py`
- Modify: `backend/src/cartrap/api/dependencies.py`
- Modify: `backend/src/cartrap/worker/main.py`
- Modify: `backend/src/cartrap/api/system.py`
- Modify: `backend/src/cartrap/modules/admin/router.py`
- Modify: `backend/src/cartrap/modules/auth/service.py`
- Modify: `backend/src/cartrap/modules/search/router.py`
- Modify: `backend/src/cartrap/modules/search/service.py`
- Modify: `backend/src/cartrap/modules/watchlist/router.py`
- Modify: `backend/src/cartrap/modules/monitoring/service.py`
- Modify: `backend/src/cartrap/modules/admin/service.py`
- Modify: `backend/src/cartrap/modules/system_status/service.py`
- Modify: `backend/tests/test_app_boot.py`
- Modify: `backend/tests/test_system_status.py`
- Modify: `backend/tests/test_worker_main.py`

- [ ] add a runtime settings resolver/service to app state so request-scoped services can read effective values instead of raw startup env only
- [ ] wire `AuthService` and app dependencies so `invite_ttl_hours` is resolved from effective runtime settings when creating new invites
- [ ] update `worker` polling loop so each cycle uses current effective polling settings and does not require process restart for changed runtime overrides
- [ ] replace hardcoded freshness/reminder/backoff reads in affected services with runtime settings resolution where the setting is in the allowlist, including `JobRuntimeService` construction in search/monitoring flows
- [ ] make `/api/system/status` and admin health/overview surfaces report effective values instead of static env-only values
- [ ] write tests for app boot and dependency wiring so web runtime settings resolution cannot silently regress
- [ ] write tests for system-status freshness policy output with overrides applied
- [ ] write tests for worker cycle behavior when runtime settings change between cycles
- [ ] run targeted API/worker tests - must pass before task 3

### Task 3: Add admin runtime settings read/update/reset APIs

**Files:**
- Modify: `backend/src/cartrap/modules/admin/{router.py,service.py,schemas.py}`
- Create: `backend/tests/admin/test_admin_runtime_settings_api.py`
- Modify: `backend/tests/admin/conftest.py`

- [ ] implement `GET /api/admin/runtime-settings` returning grouped setting metadata, default values, effective values, override state, and audit fields
- [ ] implement admin-only bulk update endpoint for safe settings with server-side validation and partial-failure-safe behavior
- [ ] implement reset-to-default endpoint for one setting or a defined set of keys without exposing non-allowlisted config
- [ ] verify invite-related admin flows consume the effective `invite_ttl_hours` value after runtime settings updates
- [ ] ensure responses distinguish `default`, `override`, and `effective` values so the UI can show what is actually active
- [ ] write backend tests for admin-only access control, successful update flow, reset flow, and validation failures
- [ ] run targeted admin runtime-settings API tests - must pass before task 4

### Task 4: Build admin runtime settings panel in the command center

**Files:**
- Create: `frontend/src/features/admin/AdminRuntimeSettingsPanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [ ] add frontend types and API clients for runtime settings list, update, and reset contracts
- [ ] integrate a `Runtime Settings` panel into the existing admin workspace with clear separation between polling/freshness/invite settings and any future advanced knobs
- [ ] render editable controls with labels, help text, bounds hints, effective/default display, dirty-state handling, and reset actions
- [ ] add save/reload/error states that do not regress the rest of the admin command center and keep non-admin flows unchanged
- [ ] write frontend tests for panel render, edit/save/reset flows, validation/error states, and admin-only visibility
- [ ] verify non-admin bootstrap still performs no runtime-settings API calls
- [ ] run frontend tests for runtime settings UI - must pass before task 5

### Task 5: Verify acceptance criteria
- [ ] verify admin can view and modify safe operational settings from the existing admin workspace
- [ ] verify changed settings affect `system/status` and worker behavior without deploy-time env edits
- [ ] verify reset-to-default restores env-backed fallback behavior
- [ ] verify secrets and non-allowlisted infra settings are not exposed in any admin API or UI
- [ ] verify non-admin users cannot access runtime settings APIs or panels
- [ ] run full verification: `./.venv/bin/pytest backend/tests`, `npm --prefix frontend test`, `npm --prefix frontend run build`

### Task 6: [Final] Update documentation
- [ ] update `README.md` with runtime settings behavior and admin-only scope
- [ ] update `docs/backend-api.md` with new admin runtime settings endpoints
- [ ] update `docs/database-schema.md` with runtime settings storage and audit fields
- [ ] update `ChangeLog.md` for each implementation cycle
- [ ] move this plan to `docs/plans/completed/` when implementation is finished

## Technical Details
- initial allowlisted settings for phase 1:
  - `saved_search_poll_interval_minutes`
  - `watchlist_default_poll_interval_minutes`
  - `watchlist_near_auction_poll_interval_minutes`
  - `watchlist_near_auction_window_minutes`
  - `live_sync_stale_after_minutes`
  - `watchlist_auction_reminder_offsets_minutes`
  - `job_retry_backoff_seconds`
  - `invite_ttl_hours`
- consumer mapping that must be covered during implementation:
  - `invite_ttl_hours` -> `AuthService.create_invite()` and admin invite creation flow
  - `job_retry_backoff_seconds` -> `JobRuntimeService` instances created inside search/monitoring services
  - `watchlist_auction_reminder_offsets_minutes` -> `MonitoringService` reminder generation
  - `live_sync_stale_after_minutes` -> `SystemStatusService.get_live_sync_status()`
- likely storage shape:
  - collection: `admin_runtime_settings`
  - one document per key with `key`, `value`, `value_type`, `updated_by`, `updated_at`
  - optional append-only audit collection can be added if change-history depth becomes a requirement during implementation
- effective value resolution:
  - `db override` when present and valid
  - otherwise fallback to `.env` / `Settings`
  - validation stays centralized in runtime settings service rather than duplicated in routers/UI
- worker/runtime application model:
  - web request handlers resolve effective values per request
  - worker resolves effective values per cycle before constructing or refreshing polling/search services
- deliberate non-scope items for first rollout:
  - JWT secrets
  - DB/CORS/VAPID settings
  - gateway base URLs/tokens
  - encryption keys and connector secrets
  - OIDC URLs and redirect URIs
  - most low-level provider HTTP transport knobs unless later promoted into an `Advanced` allowlist

## Post-Completion
- Production smoke-checks:
  - update one safe setting in admin UI
  - confirm `/api/system/status` reflects it
  - confirm a subsequent worker cycle uses it
  - reset to default and confirm fallback
- Ops rollout policy:
  - document which settings are safe for day-to-day tuning
  - restrict advanced settings to top-level admins if exposed later
- Possible follow-up:
  - expose selected timeout/rate-limit knobs in a separate `Advanced Runtime Settings` section once the base overlay pattern proves stable
