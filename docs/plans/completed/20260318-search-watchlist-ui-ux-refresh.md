# Search And Watchlist UI/UX Refresh

## Overview
- Rework the dashboard so `Search` and `Watchlist` are faster to scan, visually stronger, and less noisy without replacing the existing data contracts or dashboard architecture.
- Apply the agreed sequence from discovery: first improve information hierarchy, then strengthen the visual system, then simplify the screen through progressive disclosure and clearer action priority.
- Keep the implementation frontend-only unless a blocker appears; the current backend payloads already expose the metadata needed for search summaries, watchlist urgency, freshness, and update callouts.

## Context (from discovery)
- Files/components involved:
  - `frontend/src/App.tsx`
  - `frontend/src/styles.css`
  - `frontend/src/features/dashboard/DashboardShell.tsx`
  - `frontend/src/features/search/SearchPanel.tsx`
  - `frontend/src/features/search/SearchResultsModal.tsx`
  - `frontend/src/features/search/SearchFiltersModal.tsx`
  - `frontend/src/features/watchlist/WatchlistPanel.tsx`
  - `frontend/src/features/shared/AsyncStatus.tsx`
  - `frontend/tests/app.test.tsx`
- Related patterns found:
  - `App.tsx` already owns async state for dashboard resources and action-level pending flows, so the refresh can stay within the current state model instead of introducing a new store.
  - `SearchPanel.tsx` already has the right building blocks for a hierarchy-first refactor: filter labels, saved-search metadata, manual-search pending states, and modal-based results.
  - `WatchlistPanel.tsx` already exposes the metadata needed for a compact decision-first card (`sale_date`, `current_bid`, `last_checked_at`, `has_unseen_update`, `latest_changes`), but currently renders too many secondary details at equal visual weight.
  - `styles.css` already defines panel, card, badge, and async-status primitives, but it lacks a stricter tokenized visual hierarchy for action tiers, urgent states, and compact/expanded card modes.
  - `frontend/tests/app.test.tsx` already covers search, watchlist, offline, degraded-mode, and push/admin regressions in one integration-style suite, so the new DOM contract can be verified there without adding another test harness.
- Dependencies identified:
  - The redesign should preserve current API contracts and existing async behavior (`Search Lots`, `Save Search`, `Refresh Live`, `Add Lot`, `Remove`) while changing layout and emphasis.
  - Any disclosure/expand state for watchlist cards should stay local to the component and remain keyboard-accessible.
  - CSS/layout changes must keep the PWA/mobile constraints introduced in recent UX polish work.

## Development Approach
- **testing approach**: Regular
- **recommended implementation option**: hierarchy-first refinement inside existing components, with progressive disclosure for watchlist details and tokenized styling for action/priority states
- why this option:
  - it aligns with the agreed order of work from discovery and solves the biggest usability issue first: weak information hierarchy
  - it keeps risk lower than a full redesign because the current async/data flows remain intact
  - it allows visual and simplification improvements to land on top of clearer structure instead of masking an overloaded layout
- alternative options considered:
  - **Option B: visual redesign first**
    - pros: faster “before/after” impact
    - cons: would leave search/watchlist content hierarchy and scanability problems largely intact
  - **Option C: aggressive simplification first**
    - pros: strongest reduction of noise
    - cons: higher risk of hiding useful auction metadata before a clear default hierarchy is established
- complete each task fully before moving to the next
- make small, focused changes
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
- **CRITICAL: all tests must pass before starting next task**
- **CRITICAL: update this plan file when scope changes during implementation**
- run tests after each change
- maintain backward compatibility with the current frontend API surface and routing

## Testing Strategy
- **unit/component tests**: required for every task
  - extend `frontend/tests/app.test.tsx` for new search layout semantics, saved-search action priority, compact watchlist layout, details disclosure, and urgency/update states
- **visual/regression verification**:
  - run `npm run test --prefix frontend`
  - run `npm run build --prefix frontend`
  - manually verify desktop and narrow mobile layouts after each major UI task because CSS hierarchy changes are only partially covered by DOM tests
- **e2e tests**: none currently committed; rely on component/integration tests plus manual responsive verification for this cycle

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix
- update plan if implementation deviates from original scope
- keep plan in sync with actual work done

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): code changes, tests, docs
- **Post-Completion** (no checkboxes): manual viewport review, stakeholder UX review, deployment smoke check

## Implementation Steps

### Task 1: Establish UI hierarchy tokens and dashboard layout scaffolding

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/tests/app.test.tsx`

- [x] introduce design tokens and refreshed panel/card hierarchy in `frontend/src/styles.css` for clearer action tiers, surface contrast, and compact card rhythm
- [x] adjust wrapper markup/order in `frontend/src/App.tsx` so `Search` and `Watchlist` remain the primary workflows ahead of admin support panels
- [x] write/update frontend tests for the changed search/watchlist hierarchy expectations in `frontend/tests/app.test.tsx`
- [x] run targeted tests before moving to the next task

### Task 2: Recompose the manual search area and saved-search cards

**Files:**
- Modify: `frontend/src/features/search/SearchPanel.tsx`
- Modify: `frontend/src/features/search/SearchResultsModal.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] restructure `frontend/src/features/search/SearchPanel.tsx` so the manual search form reads as one primary workflow: make, model, compact year range, and one dominant `Search Lots` action
- [x] convert the current search summary into a compact criteria bar with clearer filter count/context instead of evenly weighted detail rows
- [x] redesign saved-search cards so `Open Results` becomes the primary action and metadata hierarchy emphasizes criteria summary, match count, freshness, and last sync before secondary actions
- [x] update related modal affordances in `frontend/src/features/search/SearchResultsModal.tsx` so save/refresh actions follow the new primary/secondary hierarchy
- [x] write frontend tests for the new saved-search action semantics and search summary expectations
- [x] run targeted tests before moving to the next task

### Task 3: Convert watchlist cards to compact-first layout with progressive disclosure

**Files:**
- Modify: `frontend/src/features/watchlist/WatchlistPanel.tsx`
- Modify: `frontend/src/features/shared/LotThumbnail.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] rebuild the default watchlist card layout in `frontend/src/features/watchlist/WatchlistPanel.tsx` so the first scan shows title, sale timing, status/update badges, and the top KPI row (`bid`, `last checked`, `odometer`)
- [x] define the frontend urgency rule as UI-only sale-date tiers (`Auction live`, `Sale soon`, `Today`) so the compact card can signal timing without waiting on a new backend contract
- [x] add progressive disclosure for secondary metadata (`primary damage`, `retail`, `drivetrain`, `has key`, `VIN`, `highlights`) instead of rendering all support details at equal weight by default
- [x] add a stronger urgency treatment for near-auction lots and preserve the existing update callout as a high-signal state, not just another detail block
- [x] keep remove and gallery interactions accessible while making destructive/secondary actions visually quieter than decision-driving content, including thumbnail sizing/fallback updates in `frontend/src/features/shared/LotThumbnail.tsx`
- [x] write frontend tests for compact card render, details toggle behavior, updated-lot emphasis, and urgency/edge cases
- [x] run targeted tests before moving to the next task

### Task 4: Polish responsive behavior, motion, and accessibility across the refreshed dashboard

**Files:**
- Modify: `frontend/src/features/search/SearchPanel.tsx`
- Modify: `frontend/src/features/watchlist/WatchlistPanel.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] refine desktop-to-mobile breakpoints so search controls, action rows, and watchlist cards stack intentionally instead of collapsing into crowded rows
- [x] improve focus, disclosure, and reduced-motion-safe transitions so the stronger visual hierarchy also remains keyboard and accessibility friendly
- [x] ensure status pills, update badges, and primary/secondary actions follow one consistent visual language across refreshed sections
- [x] verify empty/loading/error states still feel coherent after the hierarchy and disclosure changes
- [x] write frontend tests for disclosure accessibility semantics and urgency/mobile-oriented DOM behavior that can be asserted
- [x] run targeted tests before final verification

### Task 5: Verify acceptance criteria
- [x] verify the default `Search` view communicates one primary action and one compact summary path
- [x] verify each saved-search card is scannable without reading every secondary action first
- [x] verify the default `Watchlist` card surface highlights sale timing, update state, and decision-driving KPIs before support metadata
- [x] run full frontend test suite: `npm run test --prefix frontend`
- [x] run frontend production build: `npm run build --prefix frontend`

### Task 6: [Final] Update documentation
- [x] update `ChangeLog.md` for each implementation cycle during execution
- [x] leave `README.md` unchanged because the refreshed UX did not alter setup or user-facing operational guidance
- [x] move this plan to `docs/plans/completed/`

## Technical Details
- Prefer CSS variables in `frontend/src/styles.css` for hierarchy control instead of scattering new hard-coded colors and spacings across selectors.
- Keep the current async state model in `frontend/src/App.tsx`; layout changes should not require a new store or a global UI reducer.
- Reuse existing derived values where possible:
  - `activeFilterLabels` for compact filter summary
  - saved-search freshness helpers for card metadata
  - `latest_changes`, `has_unseen_update`, `sale_date`, and `last_checked_at` for watchlist urgency/update emphasis
- `frontend/src/features/shared/LotThumbnail.tsx` is part of the watchlist/search visual contract; thumbnail sizing, fallback behavior, and click affordance should be updated in the same cycle as the compact card layout.
- Implement watchlist disclosure with semantic buttons/`aria-expanded` and per-card local state keyed by tracked lot id.
- Backend currently uses `WATCHLIST_NEAR_AUCTION_WINDOW_MINUTES` for polling/reminders, but that value is not exposed to the frontend.
- This implementation chose explicit UI-only urgency tiers derived from `sale_date` (`Auction live`, `Sale soon`, `Today`) instead of adding a new API/config surface in the same cycle.
- Favor “quiet secondary actions” over adding a complex overflow menu unless layout pressure makes it necessary during implementation.
- Treat mobile as a first-class constraint:
  - avoid 3+ competing action buttons in one row on narrow screens
  - keep card headers readable without text collisions
  - preserve comfortable touch targets for primary actions and disclosure toggles
- No backend contract changes are expected for this cycle; if an implementation detail reveals a missing field, add a scoped follow-up task to this plan before changing API contracts.

## Post-Completion
**Manual verification**:
- compare the refreshed dashboard on desktop and a narrow mobile viewport to confirm the screen now reads as two clear workflows: `Search` and `Watchlist`
- verify a user can identify the next auction time and the latest important change from a watchlist card without expanding details
- verify watchlist urgency treatment against lots inside/outside the chosen threshold so “urgent” copy is predictable and not misleading
- verify keyboard users can open search actions, toggle watchlist details, and operate gallery/remove controls without losing focus context
- verify degraded/offline notices still make sense visually after the hierarchy and token updates

**Stakeholder review**:
- review the new hierarchy with the product owner against the original goals: faster scanning, stronger visual identity, and less screen noise
