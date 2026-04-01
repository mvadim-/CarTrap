# Admin Command Center Expansion

## Overview
- Розширити поточну адмінку з двох support-панелей (`Generate Invites`, `Search Catalog`) до повноцінного `admin command center` всередині існуючого dashboard, без окремого frontend-продукту.
- Додати оглядову статистику по користувачах, системних ресурсах і операційному стану платформи, використовуючи дані з уже наявних Mongo collections.
- Реалізувати `root-mode` керування користувачами для admin-акаунтів: account actions, provider actions, resource cleanup і повне видалення користувача з пов’язаними даними.
- Побудувати UX як desktop-optimized operations workspace, який коректно відкривається на всіх платформах, але не підпорядковується mobile-first layout constraints.

## Context (from discovery)
- files/components involved:
  - `backend/src/cartrap/modules/admin/router.py`
  - `backend/src/cartrap/modules/auth/{models.py,schemas.py,repository.py,service.py}`
  - `backend/src/cartrap/modules/search/repository.py`
  - `backend/src/cartrap/modules/watchlist/repository.py`
  - `backend/src/cartrap/modules/provider_connections/repository.py`
  - `backend/src/cartrap/modules/notifications/repository.py`
  - `backend/src/cartrap/modules/system_status/service.py`
  - `backend/src/cartrap/api/{router.py,dependencies.py}`
  - `frontend/src/App.tsx`
  - `frontend/src/lib/api.ts`
  - `frontend/src/types.ts`
  - `frontend/src/features/dashboard/DashboardShell.tsx`
  - `frontend/src/features/admin/{AdminInvitesPanel.tsx,AdminSearchCatalogPanel.tsx}`
  - `frontend/src/features/shared/mobileFullscreen.ts`
  - `frontend/tests/app.test.tsx`
  - `backend/tests/auth/test_rbac.py`
- related patterns found:
  - admin-доступ уже централізовано через `require_admin`, тому нові admin contracts природно лягають у `/api/admin/*`.
  - поточна адмінка живе всередині `App.tsx` як `dashboard-grid__support`, тобто правильний напрямок для розширення це evolution існуючого dashboard, а не окремий route tree.
  - frontend вже використовує `createPortal` для важких surfaces (`AccountMenuSheet`, `PushSettingsModal`, `ManualSearchScreen`, `TrackLotModal`), тому той самий патерн підходить для `AdminUserDetailSurface`.
  - schema вже містить ключові джерела для admin analytics: `users`, `invites`, `provider_connections`, `saved_searches`, `tracked_lots`, `lot_snapshots`, `push_subscriptions`.
  - user model має лише `status=active`; для block/unblock і root ops потрібно розширити auth domain та перевірити всі місця, де статус впливає на login/access.
  - invite flow зараз підтримує create/revoke, але не list/reissue/admin-side orchestration; це треба добудувати для operator workflow.
  - репозиторії переважно owner-scoped; для admin detail/list потрібні нові cross-user read methods та aggregation use-cases.
- dependencies identified:
  - зміни в `auth` торкнуться login, token refresh, `get_current_user`, RBAC tests і admin ops.
  - `delete user` повинен координувати видалення документів у `users`, `provider_connections`, `saved_searches`, `saved_search_results_cache`, `tracked_lots`, `lot_snapshots`, `push_subscriptions`, а також пов’язаних invite records за погодженим правилом.
  - frontend admin workspace залежить від нових aggregate endpoints; збирати detail surface з багатьох існуючих endpoint-ів не варто.
  - через desktop-optimized admin UX потрібен окремий layout/state layer, який не повинен ламати існуючий dashboard для звичайних user-акаунтів.

## Development Approach
- **testing approach**: Regular
- **recommended implementation option**: розширити поточний dashboard до `admin command center` і винести глибокі операційні сценарії в portal-based detail surface з єдиним admin API façade на бекенді.
- why this option:
  - зберігає один application shell і не дублює routing/layout logic.
  - використовує вже наявні role-gated patterns і portal surfaces.
  - дозволяє поступово вводити admin analytics та destructive ops без переписування всієї навігації.
- alternative options considered:
  - **Option B: окремий admin route tree**
    - pros: чистіше розділення user/admin workspace
    - cons: більша вартість state/routing duplication і більший ризик розходження UX
  - **Option C: hybrid summary + окремий admin workspace**
    - pros: добра масштабованість
    - cons: найбільша складність і підтримка двох interaction models
- admin UX приймається як desktop-optimized:
  - на desktop основний сценарій це `directory + right-side detail inspector`
  - на вузьких viewport detail surface може переходити у full-width overlay без окремого mobile-first redesign
- root-mode actions допускають звичайний confirm dialog без reason logging, але:
  - danger actions мають бути чітко візуально відділені
  - optimistic UI для destructive actions не використовується
  - після виконання action треба синхронно оновлювати overview, directory і відкритий detail state
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
- **CRITICAL: all tests must pass before starting next task**
- **CRITICAL: update this plan file when scope changes during implementation**
- підтримувати backward compatibility для non-admin dashboard flows; user-facing сценарії не повинні змінити поведінку через появу admin workspace
- `role != admin` є жорстким інваріантом цього плану:
  - non-admin session не повинна викликати жодного нового `/api/admin/*` endpoint
  - non-admin dashboard bootstrap не повинен чекати admin resources і не повинен отримати нові loading/error states через admin feature set
  - layout, composition і interaction model звичайного dashboard мають лишитися еквівалентними поточній поведінці, окрім окремо погоджених shared bugfixes

## Testing Strategy
- **backend unit/integration tests**:
  - розширити `backend/tests/auth/test_rbac.py` і додати admin-focused tests для нових admin endpoints і blocked-user behavior
  - додати окремі тести для admin aggregates, filters, root actions і cascading delete semantics
  - покрити success/error/permission cases для кожного destructive action
- **frontend integration tests**:
  - розширити `frontend/tests/app.test.tsx` для admin overview, directory filters, detail surface і destructive flows
  - перевірити, що non-admin не бачить admin workspace і не може викликати admin actions
  - перевірити, що non-admin login/dashboard flow не робить admin API requests і не отримує додаткових bootstrap delays або admin-derived errors
- **manual verification**:
  - login як admin і як user
  - review user directory з різними filters/search
  - open user detail і виконати representative safe + dangerous ops
  - verify desktop/tablet/narrow viewport rendering для admin surfaces
- **verification commands**:
  - `./.venv/bin/pytest backend/tests/auth`
  - `./.venv/bin/pytest backend/tests`
  - `npm --prefix frontend run test`
  - `npm --prefix frontend run build`

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with `➕` prefix
- document issues/blockers with `⚠️` prefix
- keep this plan aligned with actual implementation order

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): backend contracts, frontend admin workspace, tests, docs
- **Post-Completion** (no checkboxes): production smoke-checks, admin-permission rollout policy, operator training on root actions

## Implementation Steps

### Task 1: Expand auth/admin domain for managed user lifecycle

**Files:**
- Modify: `backend/src/cartrap/modules/auth/{models.py,schemas.py,repository.py,service.py}`
- Modify: `backend/src/cartrap/api/dependencies.py`
- Modify: `backend/tests/auth/{test_login.py,test_rbac.py}`

- [ ] add explicit user-status model for admin-managed lifecycle, including blocked/disabled semantics used by login and token-backed access checks
- [ ] add admin-safe user serialization payloads for directory/detail responses without exposing credential material
- [ ] make auth flows reject blocked users consistently for login and current-user resolution
- [ ] write backend tests for blocked-user login/access behavior and unchanged admin/user RBAC
- [ ] run targeted auth tests - must pass before task 2

### Task 2: Add admin service layer and aggregate read contracts

**Files:**
- Create: `backend/src/cartrap/modules/admin/service.py`
- Create: `backend/src/cartrap/modules/admin/schemas.py`
- Modify: `backend/src/cartrap/modules/admin/router.py`
- Modify: `backend/src/cartrap/api/router.py`
- Modify: `backend/src/cartrap/modules/auth/repository.py`
- Modify: `backend/src/cartrap/modules/search/repository.py`
- Modify: `backend/src/cartrap/modules/watchlist/repository.py`
- Modify: `backend/src/cartrap/modules/provider_connections/repository.py`
- Modify: `backend/src/cartrap/modules/notifications/repository.py`
- Create: `backend/tests/admin/test_admin_overview_api.py`

- [ ] introduce `AdminService` as orchestration layer over auth, invites, provider connections, saved searches, watchlist, notifications, and system status repositories
- [ ] implement `GET /api/admin/overview` with top-level user, invite, provider, search, watchlist, push, and live-sync metrics
- [ ] implement `GET /api/admin/system-health` for operator-facing health signals kept separate from overview counters
- [ ] add repository support for cross-user counts and aggregate reads needed by overview/system-health without leaking admin logic into unrelated routers
- [ ] write backend tests for overview/system-health success cases, empty-state behavior, and admin-only access control
- [ ] run targeted admin aggregate tests - must pass before task 3

### Task 3: Add admin user directory and detail aggregate endpoints

**Files:**
- Modify: `backend/src/cartrap/modules/admin/{service.py,schemas.py,router.py}`
- Modify: `backend/src/cartrap/modules/auth/repository.py`
- Modify: `backend/src/cartrap/modules/search/repository.py`
- Modify: `backend/src/cartrap/modules/watchlist/repository.py`
- Modify: `backend/src/cartrap/modules/provider_connections/repository.py`
- Modify: `backend/src/cartrap/modules/notifications/repository.py`
- Create: `backend/tests/admin/test_admin_users_api.py`

- [ ] implement `GET /api/admin/users` with search, filters, sorting, pagination, and directory-row counters for providers, saved searches, tracked lots, and push devices
- [ ] implement `GET /api/admin/users/{user_id}` returning one aggregate payload for account summary, invites, provider connections, saved searches, watchlist snapshot, push subscriptions, and recent activity hints
- [ ] define stable filter vocabulary for role, status, provider state, push presence, saved-search presence, watchlist presence, and last-login recency
- [ ] write backend tests for directory filtering/sorting/pagination and detail aggregate shape across representative user states
- [ ] run targeted admin users tests - must pass before task 4

### Task 4: Implement root-mode admin actions with safe cascading behavior

**Files:**
- Modify: `backend/src/cartrap/modules/admin/{service.py,schemas.py,router.py}`
- Modify: `backend/src/cartrap/modules/auth/repository.py`
- Modify: `backend/src/cartrap/modules/search/repository.py`
- Modify: `backend/src/cartrap/modules/watchlist/repository.py`
- Modify: `backend/src/cartrap/modules/provider_connections/repository.py`
- Modify: `backend/src/cartrap/modules/notifications/repository.py`
- Create: `backend/tests/admin/test_admin_actions_api.py`

- [ ] implement account actions: block/unblock user, promote/demote role, regenerate/reset auth entrypoints as agreed for current auth model
- [ ] implement provider actions: disconnect provider, disconnect all providers, force diagnostics refresh/revalidation hooks where feasible
- [ ] implement resource actions: delete single/all saved searches, single/all tracked lots, single/all push subscriptions, snapshot purge flows
- [ ] implement `delete user and all related data` with deterministic cascading cleanup across all owned collections and clear not-found/conflict responses
- [ ] write backend tests for success cases, forbidden cases, invalid targets, and cascade-delete integrity across related collections
- [ ] run targeted admin actions tests - must pass before task 5

### Task 5: Extend frontend types/api layer for admin workspace contracts

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/tests/app.test.tsx`

- [ ] add frontend types for admin overview, system health, directory rows, detail payload, filters, and action responses
- [ ] add `lib/api.ts` methods for admin overview, system health, users list/detail, and root actions with consistent error handling
- [ ] introduce admin-specific state management in `App.tsx` without regressing non-admin dashboard bootstrap and refresh flows
- [ ] keep admin resources out of shared bootstrap/loading orchestration for regular users so `role != admin` never waits on admin network calls
- [ ] write frontend tests for admin data loading states, retry paths, and API integration boundaries
- [ ] run frontend tests covering new admin state scaffolding - must pass before task 6

### Task 6: Build desktop-optimized admin overview and directory panels

**Files:**
- Create: `frontend/src/features/admin/AdminOverviewPanel.tsx`
- Create: `frontend/src/features/admin/AdminUserDirectoryPanel.tsx`
- Create: `frontend/src/features/admin/adminFormatting.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/features/dashboard/DashboardShell.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [ ] add an admin workspace zone to the existing dashboard shell with clear visual separation from ordinary user panels
- [ ] render top-level admin overview metrics and system health summary as desktop-first operational panels
- [ ] implement searchable/filterable user directory with high-density row layout and selected-user state handoff
- [ ] keep the admin workspace available only for `admin` role while preserving current layout behavior and panel composition for regular users
- [ ] write frontend tests for overview rendering, directory interactions, filter/search behavior, and non-admin invisibility
- [ ] run frontend tests for admin panel rendering - must pass before task 7

### Task 7: Build admin user detail surface and danger-zone UX

**Files:**
- Create: `frontend/src/features/admin/AdminUserDetailSurface.tsx`
- Create: `frontend/src/features/admin/AdminActionConfirmDialog.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [ ] implement a right-side inspector on desktop and overlay fallback on narrow widths for user detail drilldown
- [ ] render account, invites, provider connections, saved searches, watchlist, push subscriptions, and danger-zone sections from the aggregate detail payload
- [ ] add explicit confirm dialogs for destructive/root actions without reason logging, including clear copy of target user/action scope
- [ ] wire post-action refresh so overview, directory, and open detail data stay consistent after each operation
- [ ] write frontend tests for detail loading, destructive confirms, action success/error states, and cross-panel refresh behavior
- [ ] run frontend tests for detail surface flows - must pass before task 8

### Task 8: Fold existing admin panels into the new workspace and finish documentation

**Files:**
- Modify: `frontend/src/features/admin/{AdminInvitesPanel.tsx,AdminSearchCatalogPanel.tsx}`
- Modify: `frontend/src/App.tsx`
- Modify: `README.md`
- Modify: `docs/backend-api.md`
- Modify: `docs/database-schema.md`
- Modify: `ChangeLog.md`
- Modify: `frontend/tests/app.test.tsx`

- [ ] integrate existing invite generation and search-catalog refresh panels into the new admin workspace information architecture
- [ ] document new admin endpoints, user lifecycle statuses, and root-action semantics in repository docs
- [ ] verify existing admin-only diagnostics/settings interactions still coexist with the expanded admin workspace
- [ ] verify non-admin dashboard/request behavior remains unchanged after admin workspace integration
- [ ] write/update frontend tests for legacy admin panels inside the new composition
- [ ] run full verification: `./.venv/bin/pytest backend/tests`, `npm --prefix frontend run test`, `npm --prefix frontend run build`

### Task 9: Verify acceptance criteria
- [ ] verify admin users can see platform-wide statistics sourced from current Mongo-backed system data
- [ ] verify admin can search/filter users and inspect one aggregated user detail surface
- [ ] verify root actions work with expected confirms and deterministic cascade effects
- [ ] verify blocked/non-admin users cannot access admin workspace or admin APIs
- [ ] verify non-admin login and dashboard bootstrap perform no admin endpoint calls and surface no new admin-related loading or error states
- [ ] verify admin workspace remains usable across desktop, tablet, and narrow-width viewport contexts

### Task 10: [Final] Update documentation
- [ ] update `ChangeLog.md` for each implementation cycle during execution
- [ ] move this plan to `docs/plans/completed/` when implementation is finished

## Technical Details
- Proposed admin API surface:
  - `GET /api/admin/overview`
  - `GET /api/admin/system-health`
  - `GET /api/admin/users`
  - `GET /api/admin/users/{user_id}`
  - `POST /api/admin/users/{user_id}/actions/{action}`
  - `GET /api/admin/invites`
  - existing `POST /api/admin/invites`
  - existing `DELETE /api/admin/invites/{invite_id}`
  - existing `POST /api/admin/search-catalog/refresh`
- Frontend bootstrap invariant:
  - admin resources must be loaded only after `isAdmin === true` is known
  - non-admin sessions must not subscribe to admin loading/error state or admin retry flows
  - ordinary dashboard resources (`saved searches`, `watchlist`, `provider connections`, `subscriptions`, `search catalog` as currently used) remain the only shared bootstrap contract
- Proposed overview domains:
  - users: total, admins, regular users, active last 24h/7d, blocked
  - invites: pending, accepted, revoked, expired
  - providers: connected, reconnect required, disconnected users
  - search/watchlist: total saved searches, total tracked lots, unseen updates, stale/problem counts where available
  - push: users without push, total subscriptions
  - system: live-sync summary and recent degraded state
- Proposed directory row shape:
  - `id`, `email`, `role`, `status`, `created_at`, `last_login_at`
  - counts: `provider_connections`, `saved_searches`, `tracked_lots`, `push_subscriptions`
  - flags: `has_pending_invite`, `has_reconnect_required_provider`, `has_unseen_watchlist_updates`
- Proposed detail sections:
  - account summary
  - invite history
  - provider connections
  - saved searches
  - tracked lots
  - push subscriptions
  - danger zone
- Deletion semantics to enforce in service layer:
  - deleting a user must also delete owned provider connections, saved searches, saved-search cache documents, tracked lots, lot snapshots, and push subscriptions
  - role demotion from `admin` to `user` must guard against removing the last remaining admin account
  - block/unblock should not silently invalidate existing authorization checks; auth flows must enforce the chosen status model consistently

## Post-Completion
- Manual verification from a real admin account in a staging-like environment:
  - review large user directory with realistic data density
  - execute one representative safe action and one destructive action
  - verify post-action counters reconcile with Mongo state
- Rollout note:
  - root-mode actions materially raise operational risk; before production enablement, agree on who may use admin accounts and whether root actions should be feature-flagged for first rollout
