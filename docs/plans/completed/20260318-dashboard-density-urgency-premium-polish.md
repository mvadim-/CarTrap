# Dashboard Density, Urgency, And Premium Finish Polish

## Overview
- Apply a second dashboard polish pass on top of the just-finished search/watchlist hierarchy refresh, focusing on three agreed goals together: tighter density, stronger urgency signaling in watchlist, and a more premium visual finish.
- Reduce vertical and horizontal slack in the hero, user card, search form, saved-search cards, and watchlist KPI blocks so the screen feels more operational and less stretched.
- Keep the work frontend-only unless a clearly justified product need appears; the expected improvements should be achievable with current dashboard data and component boundaries.

## Context (from discovery)
- Files/components involved:
  - `frontend/src/App.tsx`
  - `frontend/src/styles.css`
  - `frontend/src/features/dashboard/DashboardShell.tsx`
  - `frontend/src/features/search/SearchPanel.tsx`
  - `frontend/src/features/search/SearchResultsModal.tsx`
  - `frontend/src/features/search/SearchFiltersModal.tsx`
  - `frontend/src/features/watchlist/WatchlistPanel.tsx`
  - `frontend/src/features/shared/LotThumbnail.tsx`
  - `frontend/src/features/admin/{AdminInvitesPanel.tsx,AdminSearchCatalogPanel.tsx}`
  - `frontend/src/features/push/PushSettingsModal.tsx`
  - `frontend/tests/app.test.tsx`
  - `docs/plans/completed/20260318-search-watchlist-ui-ux-refresh.md`
- Related patterns found:
  - the first refresh already established a better information hierarchy, compact summary bars, saved-search primary actions, compact-first watchlist cards, and urgency badges
  - the current screen still shows visible density issues: hero area remains tall, user card is larger than necessary, search controls still consume a lot of height, and watchlist KPI boxes/actions are visually heavier than the underlying importance warrants
  - watchlist urgency is present but still secondary; sale timing does not yet dominate the card strongly enough for an auction-monitoring workflow
  - current styling has stronger tokens than before, but the visual language still leans more “soft and spacious” than “tight, premium, operational”
- Dependencies identified:
  - density changes will mostly live in `styles.css`, but some markup adjustments in `DashboardShell.tsx`, `SearchPanel.tsx`, and `WatchlistPanel.tsx` may be needed to avoid brittle CSS-only hacks
  - watchlist urgency improvements should build on the existing UI-only timing tiers (`Auction live`, `Sale soon`, `Today`) unless a new backend-exposed threshold becomes explicitly required later
  - search density polish is not complete if `SearchFiltersModal.tsx` keeps the old roomy layout and toolbar treatment; modal surfaces need to stay visually aligned with the denser main panel
  - even if the primary focus is `Search` + `Watchlist`, admin panels and `PushSettingsModal` share the same dashboard visual language and can look visually stale unless the plan either includes them or explicitly freezes them; this plan includes a light consistency pass instead of a full admin redesign
  - tests already exercise the main dashboard DOM contract, so the follow-up pass should extend `frontend/tests/app.test.tsx` instead of introducing a new testing layer

## Development Approach
- **testing approach**: Regular
- **recommended implementation option**: one structured polish pass in the order `density -> urgency emphasis -> premium finish`, with each stage preserving the previous hierarchy gains
- why this option:
  - it addresses the most visible remaining weaknesses first instead of jumping to purely decorative styling
  - urgency improvements will read better once card density and spacing are tightened
  - premium finish is safer after layout and action weight have settled, because typography, shadows, and surfaces can then reinforce a stable structure instead of masking layout issues
- alternative options considered:
  - **Option B: premium visual finish first**
    - pros: fastest “wow” delta
    - cons: risks decorating an interface that still feels slightly oversized and too soft
  - **Option C: urgency-only follow-up**
    - pros: high immediate product value for watchlist users
    - cons: leaves the rest of the screen visually uneven, especially hero/search/saved-search density
- complete each task fully before moving to the next
- make small, focused changes
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
- **CRITICAL: all tests must pass before starting next task**
- **CRITICAL: update this plan file when scope changes during implementation**
- run tests after each change
- maintain backward compatibility with existing dashboard flows, routing, and API contracts

## Testing Strategy
- **unit/component tests**: required for every task
  - extend `frontend/tests/app.test.tsx` for any changed action labels, urgency wording, compact card/disclosure semantics, and stronger hero/user-card layout assumptions that can be asserted via DOM structure
- **build verification**:
  - run `npm run test --prefix frontend`
  - run `npm run build --prefix frontend`
- **manual verification**:
  - compare desktop and narrow mobile screenshots after each major task because density and premium-finish changes are partly visual and only partially testable through DOM assertions
- **e2e tests**: none currently committed; do not add a new e2e harness in this cycle

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with ➕ prefix
- document issues/blockers with ⚠️ prefix
- update plan if implementation deviates from original scope
- keep plan in sync with actual work done

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): frontend code changes, tests, docs
- **Post-Completion** (no checkboxes): manual stakeholder review and visual sign-off

## Implementation Steps

### Task 1: Tighten dashboard chrome and top-level density

**Files:**
- Modify: `frontend/src/features/dashboard/DashboardShell.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] reduce vertical slack in the hero and user card so the primary dashboard content starts higher on the page without making the screen feel cramped
- [x] rebalance panel ordering and top-level spacing in `frontend/src/App.tsx` / `frontend/src/features/dashboard/DashboardShell.tsx` so search/watchlist remain visually dominant and support chrome becomes quieter
- [x] tighten global spacing, panel padding, and button heights in `frontend/src/styles.css` for a denser operational layout
- [x] write/update frontend tests for any changed top-level headings, ordering assumptions, or primary action labels
- [x] run tests - must pass before next task

### Task 2: Compact the search workflow and saved-search cards further

**Files:**
- Modify: `frontend/src/features/search/SearchPanel.tsx`
- Modify: `frontend/src/features/search/SearchResultsModal.tsx`
- Modify: `frontend/src/features/search/SearchFiltersModal.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] reduce the height and visual bulk of the manual search controls while preserving readability and comfortable touch targets
- [x] make the model field and action column feel less constrained at common desktop widths, including any necessary layout tweaks for summary and filters
- [x] compress saved-search cards so criteria, filters, and freshness metadata read faster with less empty space and weaker secondary actions
- [x] align `frontend/src/features/search/SearchFiltersModal.tsx` with the denser search treatment so filter selection does not feel like a fallback to the previous visual system
- [x] ensure modal action hierarchy and spacing remain consistent with the denser dashboard treatment
- [x] write frontend tests for any changed saved-search copy or button semantics
- [x] run tests - must pass before next task

### Task 3: Make watchlist urgency the dominant signal

**Files:**
- Modify: `frontend/src/features/watchlist/WatchlistPanel.tsx`
- Modify: `frontend/src/features/shared/LotThumbnail.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] increase the visual priority of sale timing so `Auction live`, `Sale soon`, and `Today` become the first-read signal on watchlist cards
- [x] refine urgency presentation with tighter sale-time composition, stronger timing badges/strips, and quieter support metadata so the card reads like an auction-monitoring tool
- [x] reduce the weight of `Show details` and `Remove` relative to sale timing, title, and KPI blocks
- [x] compact the `Add by Lot Number` intake row so the watchlist entry workflow matches the denser card treatment instead of keeping oversized form chrome above the list
- [x] compact watchlist KPI boxes and thumbnail treatment so cards consume less height while still supporting image recognition and disclosure
- [x] write frontend tests for urgency wording/state and any changed disclosure/action semantics
- [x] run tests - must pass before next task

### Task 4: Apply premium visual finish without regressing utility

**Files:**
- Modify: `frontend/src/features/dashboard/DashboardShell.tsx`
- Modify: `frontend/src/features/search/SearchPanel.tsx`
- Modify: `frontend/src/features/watchlist/WatchlistPanel.tsx`
- Modify: `frontend/src/features/admin/AdminInvitesPanel.tsx`
- Modify: `frontend/src/features/admin/AdminSearchCatalogPanel.tsx`
- Modify: `frontend/src/features/push/PushSettingsModal.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/app.test.tsx`

- [x] strengthen the premium feel through typography weight, contrast tuning, surface treatment, border/shadow restraint, and more intentional visual rhythm
- [x] reduce the remaining “milky/empty” feel by tightening panel interiors and sharpening contrast between primary and secondary elements
- [x] ensure all badges, pills, KPI cards, and action buttons follow one more cohesive visual language across the dashboard
- [x] apply a lightweight consistency pass to admin panels and `PushSettingsModal` so support surfaces do not visually lag behind the main dashboard after the premium finish lands
- [x] keep motion subtle and accessibility-safe while polishing hover/focus interactions
- [x] write frontend tests only where the premium-finish pass changes semantics or user-facing labels; avoid brittle style-only assertions
- [x] run tests - must pass before next task

### Task 5: Verify acceptance criteria
- [ ] verify the hero and user card no longer dominate the first screen more than search/watchlist content
- [ ] verify saved-search and watchlist cards feel denser and require less scanning time than the current implementation
- [ ] verify watchlist urgency is immediately legible before secondary details or actions
- [x] run full frontend test suite: `npm run test --prefix frontend`
- [x] run frontend production build: `npm run build --prefix frontend`
- ⚠️ Local headed smoke-check against the real dashboard was blocked in this environment because frontend auth calls to `http://127.0.0.1:8000/api/auth/login` returned `ERR_CONNECTION_REFUSED`, so visual acceptance still needs a live backend-backed browser check.

### Task 6: [Final] Update documentation
- [x] update `ChangeLog.md` for each implementation cycle during execution
- [x] update this plan if the chosen urgency treatment or visual direction changes during implementation
- [x] move this plan to `docs/plans/completed/`

## Technical Details
- Prefer editing layout structure only where CSS cannot cleanly solve the density issue; avoid broad JSX churn for style-only wins.
- Preserve the current primary workflow contract:
  - `Search Lots` remains the dominant search CTA
  - `Open Results` remains the primary saved-search action
  - watchlist disclosure stays available but secondary
- Urgency should stay product-driven rather than animation-driven:
  - use timing placement, typography, color emphasis, and card structure before adding countdown gimmicks
  - if a countdown is introduced, keep it subtle and avoid per-second re-render noise
- Premium finish should not mean “heavier”:
  - fewer giant pills
  - less padding where it does not buy clarity
  - stronger contrast where it helps scanability
  - more deliberate typography and spacing rhythm
- Mobile remains a first-class constraint:
  - compact density on desktop must still unwrap cleanly on narrow screens
  - actions must remain tap-friendly after height reductions
  - watchlist urgency treatment must remain legible on stacked cards
- No backend contract changes are expected in this cycle.

## Post-Completion
**Manual verification**:
- compare before/after screenshots at desktop and mobile widths to confirm density improved without making forms feel cramped
- verify sale timing is the first thing the eye catches on urgent watchlist cards
- verify the user card and hero no longer compete with operational content for attention
- verify `SearchFiltersModal`, admin panels, and settings surfaces still feel visually consistent with the polished dashboard rather than like older UI leftovers
- verify keyboard focus, disclosure toggles, and action buttons remain usable after density reductions

**Stakeholder review**:
- review the final screen specifically against these three goals: tighter density, stronger watchlist urgency, and more premium visual finish
