# Saved Search Inbox Mobile Refresh

## Overview
- Rework the mobile dashboard so the default landing experience prioritizes returning to saved searches instead of presenting the manual search form and hero marketing copy.
- Replace the current hero + user-summary block with a compact shell header, a hamburger-driven account menu, and a saved-search inbox that surfaces the most actionable items first.
- Move manual search into a secondary full-screen flow opened from a sticky `New Search` CTA while preserving the existing search, saved-search, and cached-results backend contracts.

## Context (from discovery)
- files/components involved:
  - `frontend/src/App.tsx`
  - `frontend/src/features/dashboard/DashboardShell.tsx`
  - `frontend/src/features/search/SearchPanel.tsx`
  - `frontend/src/features/search/SearchResultsModal.tsx`
  - `frontend/src/features/search/SearchFiltersModal.tsx`
  - `frontend/src/styles.css`
  - `frontend/tests/app.test.tsx`
- related patterns found:
  - `App.tsx` already owns session role detection, settings modal state, pull-to-refresh guards, and all dashboard resource loaders, so this redesign can stay frontend-only within the existing state model.
  - `DashboardShell.tsx` currently renders the large `CarTrap dispatch board` hero and inline user actions; these are the primary sources of wasted vertical space on mobile.
  - `SearchPanel.tsx` already has the data needed for a saved-search inbox (`new_count`, `cached_result_count`, `last_synced_at`, `external_url`) and already treats saved-search viewing as a cached modal flow.
  - `SearchPanel.tsx` also owns the full manual-search form, filter modal, and search results modal, making it the natural place to introduce a secondary full-screen `New Search` flow without changing API contracts.
  - `frontend/tests/app.test.tsx` currently asserts the hero text and inline `Open Results` button, so the redesign will require integration-test updates rather than a new test harness.
- dependencies identified:
  - preserve current API contracts for `searchLots`, `saveSearch`, `viewSavedSearch`, `refreshSavedSearchLive`, and `deleteSavedSearch`
  - preserve cached-result semantics where opening a saved search clears the list-level `NEW` count after view
  - keep device-offline messaging for all users, but move live-sync/system status details out of the main dashboard surface and into the admin account menu
  - keep pull-to-refresh, search filters, and results/save modals compatible with the new shell layout

## Development Approach
- **testing approach**: Regular
- **recommended implementation option**: shell-first frontend refactor with a saved-search inbox as the default screen and a full-screen secondary `New Search` flow
- why this option:
  - it matches the agreed primary mobile workflow: returning to saved searches faster than creating a new one
  - it removes the largest usability problem first: wasted above-the-fold space caused by the hero and inline account card
  - it keeps risk lower than a broader information-architecture rewrite because the existing async/resource model and backend contracts remain intact
- alternative options considered:
  - **Option B: saved-search inbox with inline collapsed manual-search accordion**
    - pros: fewer overlay states, shorter implementation path
    - cons: manual-search UI would still compete for vertical space on the main screen
  - **Option C: top-level segmented navigation for `Saved` and `New Search`**
    - pros: explicit two-mode mental model
    - cons: heavier navigation change and more chrome than needed for the agreed use case
- complete each task fully before moving to the next
- make small, focused changes
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
  - tests are not optional - they are a required part of the checklist
  - write unit/integration tests for new view-state helpers and modified UI behavior
  - update integration coverage when layout semantics or interaction targets change
  - cover both success and edge/error scenarios (role differences, offline/degraded states, empty lists, failed actions)
- **CRITICAL: all tests must pass before starting next task**
- **CRITICAL: update this plan file when scope changes during implementation**
- run tests after each change
- maintain backward compatibility with current frontend API surface and hash-routing flow

## Testing Strategy
- **unit/component tests**: required for every task
  - extend `frontend/tests/app.test.tsx` for shell/header rendering, account-menu interactions, saved-search inbox filters/order, title-block opening behavior, and secondary `New Search` flow
  - add smaller focused tests only if extracting pure helpers or isolated components materially reduces app-test complexity
- **e2e tests**: none currently committed
  - rely on the existing Vitest integration suite plus manual viewport verification for this cycle
- **visual/regression verification**:
  - run `npm run test --prefix frontend -- app.test.tsx` after each task
  - run `npm run test --prefix frontend` before final acceptance
  - run `npm run build --prefix frontend` before closing the cycle
  - manually verify narrow mobile layout, safe-area spacing, menu sheet behavior, and full-screen `New Search` flow

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix
- update plan if implementation deviates from original scope
- keep plan in sync with actual work done

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): code changes, tests, documentation updates
- **Post-Completion** (no checkboxes): manual mobile verification, stakeholder UX review, deployment smoke checks

## Implementation Steps

### Task 1: Replace the hero shell with a compact header and account menu

**Files:**
- Create: `frontend/src/features/dashboard/AccountMenuSheet.tsx`
- Modify: `frontend/src/features/dashboard/DashboardShell.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] create `frontend/src/features/dashboard/AccountMenuSheet.tsx` to render the hamburger-triggered account sheet with email, role label, `Settings`, and `Log Out`
- [x] refactor `frontend/src/features/dashboard/DashboardShell.tsx` to remove the hero/user-summary card and replace it with a compact header that exposes a hamburger trigger instead of inline account actions
- [x] update `frontend/src/App.tsx` to control the account-menu open state, keep admin-only live-sync/system details inside the account sheet, and remove the current global degraded live-sync banner from the main dashboard surface while leaving device-offline messaging global
- [x] write tests for compact shell rendering and user account-menu actions in `frontend/tests/app.test.tsx`
- [x] write tests for admin-only system-status visibility in the account menu, device-offline banner retention, and absence of dashboard-level live-sync status in `frontend/tests/app.test.tsx`
- [x] run `npm run test --prefix frontend -- app.test.tsx` - must pass before task 2

### Task 2: Recompose `SearchPanel` into a saved-search inbox with quick filters

**Files:**
- Modify: `frontend/src/features/search/SearchPanel.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] reorder `frontend/src/features/search/SearchPanel.tsx` so `Saved Searches` becomes the default primary section and manual-search affordances are removed from the main dashboard surface
- [x] add inbox-level derived state in `frontend/src/features/search/SearchPanel.tsx` for quick filters (`All`, `New`, `Needs refresh`) and default ordering that surfaces `NEW` items before lower-priority rows
- [x] define `Needs refresh` as a deterministic UI-only heuristic (`last_synced_at` missing or older than 24 hours`) and keep it behind a local constant so the rule is explicit in code and tests
- [x] redesign saved-search cards in `frontend/src/features/search/SearchPanel.tsx` so the title block is the primary tap target, the summary is compact, and secondary actions move into an overflow menu instead of inline buttons
- [x] replace the current empty saved-search placeholder with an inbox empty state that includes a primary path to `New Search`
- [x] write tests for inbox filters/order and title-block opening behavior in `frontend/tests/app.test.tsx`
- [x] write tests for overflow-menu secondary actions, `Needs refresh` matching, and empty-state CTA behavior in `frontend/tests/app.test.tsx`
- [x] run `npm run test --prefix frontend -- app.test.tsx` - must pass before task 3

### Task 3: Move manual search into a secondary full-screen `New Search` flow

**Files:**
- Create: `frontend/src/features/search/ManualSearchScreen.tsx`
- Modify: `frontend/src/features/search/SearchPanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/features/search/SearchFiltersModal.tsx`
- Modify: `frontend/src/features/search/SearchResultsModal.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] create `frontend/src/features/search/ManualSearchScreen.tsx` to host the existing make/model/year/filter form as a dedicated full-screen composer opened from a sticky `New Search` CTA
- [x] refactor `frontend/src/features/search/SearchPanel.tsx` to launch and close the secondary `New Search` flow while preserving current search, save-search, and cached-results modal behavior
- [x] update `frontend/src/App.tsx` so pull-to-refresh and other shell-level touch handling are disabled while the full-screen `New Search` flow is open, not only while `PushSettingsModal` is open
- [x] ensure `frontend/src/features/search/SearchFiltersModal.tsx` and `frontend/src/features/search/SearchResultsModal.tsx` remain coherent within the new full-screen flow, including return-to-inbox behavior after a saved search is created
- [x] write tests for opening/closing the `New Search` screen, running a manual search, and saving back into the inbox in `frontend/tests/app.test.tsx`
- [x] write tests for edge cases in the secondary flow (catalog unavailable, action failure, cancel/back behavior, pull-to-refresh suppression while open) in `frontend/tests/app.test.tsx`
- [x] run `npm run test --prefix frontend -- app.test.tsx` - must pass before task 4

### Task 4: Polish responsive behavior, sticky actions, and accessibility semantics

**Files:**
- Modify: `frontend/src/features/dashboard/DashboardShell.tsx`
- Modify: `frontend/src/features/search/SearchPanel.tsx`
- Modify: `frontend/src/features/search/ManualSearchScreen.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] refine `frontend/src/styles.css` for iPhone-safe spacing, sticky `New Search` CTA behavior, touch-target sizing, overflow-menu layout, and bottom-sheet/full-screen overlay rhythm
- [x] ensure header/menu/search interactions remain keyboard- and screen-reader-accessible with clear labels, focus management, and reduced-motion-safe transitions
- [x] verify offline/error states still communicate correctly within the new shell hierarchy, and that degraded live-sync information is available only through admin account surfaces or action-level error messages
- [x] write tests for accessibility-oriented semantics (menu trigger, dialog/sheet visibility, sticky CTA presence, role-specific content) in `frontend/tests/app.test.tsx`
- [x] write tests for offline banner retention, removal of the dashboard-level degraded banner, and action-level degraded-state messaging after the shell/search reordering in `frontend/tests/app.test.tsx`
- [x] run `npm run test --prefix frontend -- app.test.tsx` - must pass before task 5

### Task 5: Verify acceptance criteria
- [x] verify the default mobile dashboard now prioritizes saved searches over manual-search controls
- [x] verify saved-search cards can be opened from the title block without relying on a separate `Open Results` button
- [x] verify `Settings`, `Log Out`, and admin-only system status are reachable from the hamburger menu and no longer consume primary dashboard space
- [x] verify the `New Search` flow is secondary, full-screen, and returns cleanly to the inbox after save/cancel
- [x] run full frontend test suite: `npm run test --prefix frontend`
- [x] run frontend production build: `npm run build --prefix frontend`

### Task 6: [Final] Update documentation
- [x] update `ChangeLog.md` for each implementation cycle during execution
- [x] update `README.md` only if the mobile dashboard workflow or operator instructions need user-facing documentation
- [x] move this plan to `docs/plans/completed/`

## Technical Details
- keep the redesign frontend-only unless implementation reveals a blocker; existing saved-search payloads already include the metadata needed for inbox ordering and compact summaries
- preserve `PushSettingsModal` ownership in `App.tsx`; the new account menu should open settings without breaking the current modal lifecycle or pull-to-refresh guards
- keep device-offline messaging visible to all users because it changes what actions are possible; move `live_sync` status, timestamps, and error text into the admin account menu and rely on action-level error copy for non-admin degraded scenarios
- derive inbox quick filters client-side from existing fields:
  - `New`: `item.new_count > 0`
  - `Needs refresh`: `last_synced_at` missing or older than 24 hours, without adding a new backend field in this cycle
  - default ordering should keep `NEW` items ahead of other rows while preserving stable, comprehensible secondary sort behavior
- avoid premature abstraction, but if `SearchPanel.tsx` becomes hard to maintain, extract focused components (`AccountMenuSheet`, `ManualSearchScreen`) rather than introducing a broad UI state layer
- preserve saved-search side effects:
  - opening cached results still clears list-level `NEW` counts
  - `Refresh Live`, `Open URL`, and `Delete` remain available as secondary actions
  - saving a new search should return the user to the inbox with a visible success cue/highlight for the newly created item
- keep mobile as the reference layout:
  - design for thumb reach and safe-area spacing first
  - do not reintroduce tall hero blocks or multiple competing primary CTAs on the main screen
  - ensure the sticky `New Search` CTA does not obscure the last saved-search card or modal/sheet controls

## Post-Completion
**Manual verification**:
- verify the first mobile viewport on iPhone-sized dimensions shows the compact header, quick filters, and at least the first saved-search card without exposing manual-search form fields
- verify the hamburger menu works for both `user` and `admin` roles, with admin-only system status visible only inside the menu
- verify an empty saved-search inbox offers an obvious `New Search` entry point instead of a dead-end placeholder
- verify the saved-search overflow menu remains easy to use on touch devices and does not conflict with the title-block primary action
- verify the sticky `New Search` CTA respects safe-area insets and does not cover content when scrolling to the end of the inbox
- verify creating, saving, cancelling, and reopening the secondary `New Search` flow preserves search form context and does not regress results/save modal behavior
- verify device-offline and action-level degraded scenarios still explain why search/refresh actions may be limited without restoring a global dashboard system-status banner

**External system updates**:
- none expected; backend contracts and deployment configuration should remain unchanged for this cycle
