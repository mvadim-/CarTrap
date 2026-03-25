# IAAI + Multi-Auction Support

## Overview
- Додати IAAI як другий аукціон поряд із Copart без форку продукту на окремі вертикалі.
- Нормалізувати Copart та IAAI у спільний multi-auction contract для search, saved searches, watchlist і worker refresh.
- Додати IAAI connector у PWA settings за аналогією з Copart і показувати в кожному лоті, з якого саме аукціону він прийшов.
- Рекомендований напрям: один saved search може працювати по кількох вибраних аукціонах, а кожен lot повинен мати `provider`, `lot_key` і provider-specific identity, щоб не ламати унікальність, кэш і watchlist.

## Context (from discovery)
- files/components involved:
  - `Temp/Login-flow-iaai`
  - `backend/src/cartrap/modules/provider_connections/{models.py,schemas.py,service.py,router.py}`
  - `backend/src/cartrap/modules/search/{schemas.py,service.py,repository.py,router.py}`
  - `backend/src/cartrap/modules/watchlist/{schemas.py,service.py,repository.py,router.py}`
  - `backend/src/cartrap/modules/copart_provider/{client.py,models.py,normalizer.py,service.py}`
  - `backend/src/cartrap/worker/main.py`
  - `backend/src/cartrap/modules/monitoring/service.py`
  - `frontend/src/{App.tsx,types.ts,lib/api.ts}`
  - `frontend/src/features/dashboard/AccountMenuSheet.tsx`
  - `frontend/src/features/integrations/CopartConnectionCard.tsx`
  - `frontend/src/features/search/{SearchPanel.tsx,SearchResultsModal.tsx}`
  - `frontend/src/features/watchlist/WatchlistPanel.tsx`
  - `frontend/tests/app.test.tsx`
- IAAI flow facts from `Temp/Login-flow-iaai`:
  - login починається з `login.iaai.com/.well-known/openid-configuration`, далі йде OIDC authorization-code + PKCE flow через `/connect/authorize` і `/connect/token`
  - `/connect/token` повертає `access_token`, `refresh_token`, `expires_in=3600`, `scope` з `offline_access`; це вказує, що silent refresh можна робити без повторного введення password
  - після login мобільний застосунок викликає `mappproxy.iaai.com` із `Authorization: Bearer ...`, але також стабільно шле mobile headers (`tenant`, `apikey`, `deviceid`, `x-user-id`, `x-request-type`, `x-app-version`, `x-country`, `x-language`, `x-datetime`) і iaai/Imperva cookies
  - search використовує `POST /api/mobilesearch/search`; response містить `vehicles[]` з полями `id` (inventory id), `stockNumber`, `itemId`, `auctionDateTime`, `vehiclePrimaryImageUrl`, `odoValue`, `currency`, `branchName`, `city`, `state`, `market`
  - lot details використовують `GET /api/mobileinventory/GetInventoryDetails/{inventoryId}`; response містить `inventoryResult.attributes`, `saleInformation`, `vehicleInformation`, `imageDimensions.keys`
  - bid/watch enrichment іде окремо через `GET /Bidding/GetAuctionInformation` і `POST /Watch/GetVehiclesWatchStatusNew`
  - у login flow видно Imperva/WAF call `/A-would-they-here-beathe-and-should-mis-fore-Cas`; тому feasibility треба перевіряти до початку великого refactor
- related patterns found:
  - `provider_connections` уже дає базовий user-scoped connector lifecycle, але сервіс, роутер, повідомлення і client factories все ще Copart-specific
  - search/watchlist contracts зараз заточені під один аукціон: результат ідентифікується лише через `lot_number`, add-from-search працює через `lot_url`, а `connection_diagnostic` існує лише як один об'єкт
  - saved-search cache зберігає `new_lot_numbers`; цього недостатньо для mixed Copart + IAAI results
  - watchlist має unique index `("owner_user_id", "lot_number")`, що зламається при однакових lot numbers між різними аукціонами
  - current frontend copy і UX жорстко прив'язані до Copart (`Open Copart lot`, `Copart action blocked`, `Connect Copart`)
  - `search/catalog`, `SearchCatalogRefreshJob` і `ManualSearchScreen` зараз Copart-only не лише по назві, а й по shape даних; для IAAI треба або provider-aware catalog contract, або явний fallback без каталогу
  - `POST /api/search/watchlist` і `POST /api/watchlist` зараз зав'язані на `lot_url` / Copart-style `lot_number`, тоді як IAAI search/details оперують насамперед `inventoryId` + `stockNumber`
- dependencies identified:
  - Mongo persistence для saved searches, result cache, watchlist, snapshots і provider connections
  - existing Copart connector split architecture already solved encryption, reconnect semantics and user ownership rules
  - frontend state currently assumes one connector card and one connection diagnostic
- assumptions and inferences:
  - inference: IAAI should prefer encrypted storage of refresh-capable auth bundle (`access_token`, `refresh_token`, token expiry, cookies, user/tenant/device metadata), not Copart-style cookie-only bundle
  - assumption: user-facing search should support selected providers and merged results, because the request explicitly requires showing auction source on saved-search result rows
  - assumption: existing make/model/year/drivetrain user filters can be mapped into provider-specific payload builders without introducing a full IAAI catalog in the first iteration
  - open question to verify during implementation: canonical external IAAI lot deep link is not present in the trace, so the URL strategy must be confirmed before wiring the "open lot" CTA

## Development Approach
- **testing approach**: Regular (code first, then tests)
- start with an explicit feasibility gate for IAAI auth/search/details replay before touching frontend contracts
- introduce provider-agnostic lot identity first, then plug IAAI into that contract; do not layer IAAI on top of `CopartSearchResult` / `CopartLotSnapshot`
- decouple internal lot identity from `lot_url`: use `provider`, `provider_lot_id`, `lot_key` and keep external URL as presentation metadata
- treat mixed-provider refresh as partial-success capable:
  - if one selected provider succeeds and another fails, keep successful results and surface provider-level diagnostics instead of failing the whole saved search
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
- **CRITICAL: all tests must pass before starting next task**
- **CRITICAL: update this plan file when scope changes during implementation**
- maintain backward compatibility for existing Copart data by backfilling missing provider fields to `copart`

## Testing Strategy
- **IAAI feasibility tests**
  - OIDC login bootstrap with PKCE replay
  - refresh-token exchange and access-token rotation
  - authenticated `mobilesearch` and `GetInventoryDetails` replay with captured headers/cookies
  - explicit failure mapping for invalid credentials, expired refresh token, and WAF/Imperva rejection
- **backend unit/integration tests**
  - provider-agnostic lot/result serializers
  - composite `lot_key` generation and migration/backfill behavior
  - saved-search merge and `new_lot_keys` detection across multiple providers
  - watchlist uniqueness and refresh by provider-specific identity
  - connector state transitions for both Copart and IAAI
- **frontend tests**
  - settings modal with two connectors
  - manual search provider selection and mixed-result rendering
  - auction badge rendering in saved-search results and watchlist items
  - provider-aware action blocking copy and partial-provider failure UX
- **worker regression tests**
  - polling mixed-provider saved searches without collapsing all results on single-provider failure
  - refresh flows use the correct connector per tracked lot / saved search
- **manual verification**
  - connect Copart only, IAAI only, and both together
  - run one saved search against both providers and verify result rows display correct auction source
  - add one IAAI result and one Copart result to watchlist and verify they coexist without key collisions

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with `➕` prefix
- document issues/blockers with `⚠️` prefix
- keep this plan aligned with actual implementation order

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): code, tests, migrations/backfills, docs inside this repository
- **Post-Completion** (no checkboxes): production credential validation, real-account smoke tests, and any infra routing decision if IAAI needs a dedicated gateway

## Implementation Steps

### Task 0: Prove IAAI connector feasibility and define the stored auth bundle

**Files:**
- Create: `backend/src/cartrap/modules/iaai_provider/client.py`
- Create: `backend/src/cartrap/modules/iaai_provider/errors.py`
- Create: `backend/tests/iaai/test_http_client.py`
- Modify: `docs/plans/20260325-iaai-multi-auction-support.md`

- [x] replay the OIDC login flow from `Temp/Login-flow-iaai` and isolate the minimum required bootstrap sequence, including Imperva-related pre-login calls if they are mandatory
- [x] verify whether `refresh_token` can renew `access_token` without password and define reconnect criteria when refresh fails
- [x] define the encrypted IAAI session bundle shape: tokens, token expiry, cookies, tenant, `x-user-id`, device metadata, and mobile header profile
- [x] codify safe error taxonomy for invalid credentials, refresh failure, token expiry, and WAF rejection
- [x] write feasibility tests for login success, refresh success, invalid credentials, and auth-invalid-after-refresh edge cases
- [x] run tests - must pass before task 1

### Task 1: Introduce provider-agnostic lot identity and normalized result models

**Files:**
- Create: `backend/src/cartrap/modules/auction_domain/models.py`
- Modify: `backend/src/cartrap/modules/copart_provider/models.py`
- Modify: `backend/src/cartrap/modules/search/service.py`
- Modify: `backend/src/cartrap/modules/watchlist/service.py`
- Modify: `frontend/src/types.ts`
- Create: `backend/tests/auction_domain/test_models.py`

- [x] create shared `AuctionSearchResult` / `AuctionLotSnapshot` models with additive fields such as `provider`, `auction_label`, `provider_lot_id`, and `lot_key`
- [x] define a single composite identity helper used everywhere results are deduplicated or compared (`lot_key`, not plain `lot_number`)
- [x] adapt existing Copart serializers to emit the shared models without regressing current API shape
- [x] backfill legacy Copart-only documents in code paths to default missing provider fields to `copart`
- [x] write tests for composite identity generation and backward-compatible Copart serialization
- [x] write tests for mixed-provider dedupe semantics where `lot_number` is identical but provider differs
- [x] run tests - must pass before task 2

### Task 2: Generalize provider-connections and add IAAI connector endpoints

**Files:**
- Modify: `backend/src/cartrap/modules/provider_connections/{models.py,schemas.py,service.py,router.py,repository.py}`
- Modify: `backend/src/cartrap/api/router.py`
- Modify: `backend/src/cartrap/api/dependencies.py`
- Modify: `backend/src/cartrap/config.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/types.ts`
- Create: `backend/tests/provider_connections/test_iaai_router.py`

- [x] add `PROVIDER_IAAI` and move provider-specific connect/reconnect/disconnect behavior behind a registry/factory instead of Copart-only branches
- [x] add `POST /api/provider-connections/iaai/connect`, `POST /api/provider-connections/iaai/reconnect`, and `DELETE /api/provider-connections/iaai`
- [x] generalize connection diagnostics and helper copy so the service can describe either provider without hard-coded "Copart" strings
- [x] support encrypted storage and bundle metadata for both providers while preserving one active connection per `(user_id, provider)`
- [x] write API tests for IAAI connect/reconnect/disconnect success paths and provider isolation from Copart
- [x] write API tests for invalid IAAI credentials, refresh-invalid reconnect cases, and missing-connection errors
- [x] run tests - must pass before task 3

### Task 3: Implement IAAI search/details normalizers and provider service

**Files:**
- Create: `backend/src/cartrap/modules/iaai_provider/{models.py,normalizer.py,service.py}`
- Create: `backend/tests/iaai/test_normalizer.py`
- Modify: `backend/src/cartrap/modules/provider_connections/service.py`

- [x] implement IAAI request builders that map current CarTrap criteria into `/api/mobilesearch/search` payloads
- [x] normalize IAAI `vehicles[]` into the shared search-result model, including `stockNumber -> lot_number`, `id -> provider_lot_id`, `auctionDateTime -> sale_date`, `vehiclePrimaryImageUrl -> thumbnail_url`, and provider/auction labels
- [x] normalize `GetInventoryDetails/{inventoryId}` into the shared lot-snapshot model, including image extraction from `imageDimensions.keys`
- [x] define IAAI status derivation from sale/bid fields and keep provider-specific raw values in additive fields when exact parity is not possible
- [x] confirm and implement external IAAI lot URL generation, or explicitly return `null` plus provider-specific ref until the deep link is verified
- [x] write tests for IAAI search normalization success cases
- [x] write tests for lot-details normalization, status derivation, image extraction, and missing-field edge cases
- [x] run tests - must pass before task 4

### Task 4: Refactor search and saved-search cache for selected providers and mixed results

**Files:**
- Modify: `backend/src/cartrap/modules/search/{schemas.py,service.py,repository.py,router.py}`
- Modify: `backend/src/cartrap/modules/search/catalog_refresh.py`
- Modify: `backend/src/cartrap/modules/search/models.py`
- Modify: `frontend/src/{types.ts,lib/api.ts,App.tsx}`
- Modify: `frontend/src/features/search/{ManualSearchScreen.tsx,SearchPanel.tsx,SearchResultsModal.tsx}`
- Modify: `backend/tests/search/test_search_api.py`

- [x] define provider-aware manual-search input strategy: reusable catalog for both providers, separate catalogs per provider, or IAAI free-text fallback for v1
- [x] evolve `/search/catalog` and frontend catalog state so the UI no longer assumes a single Copart make/model source
- [x] extend search criteria with selected providers, and include provider selection in saved-search `criteria_key`
- [x] fan out live search across selected providers, merge results by `lot_key`, and sort them in a provider-agnostic way
- [x] replace `new_lot_numbers` with `new_lot_keys` in saved-search cache and `is_new` logic
- [x] replace the singular saved-search `connection_diagnostic`/`external_url` contract with provider-aware diagnostics and external links, while keeping single-provider backward compatibility where practical
- [x] add provider-level diagnostics to search/saved-search responses so partial-provider failures can be shown without discarding successful results
- [x] update frontend manual-search UX so users can choose one or both auctions, and result rows render auction/source metadata
- [x] write backend tests for mixed Copart + IAAI search merge, partial-provider failure behavior, catalog contract evolution, and `new_lot_keys` detection
- [x] write frontend tests for provider selection, provider-aware catalog/fallback behavior, mixed-result rendering, and provider-aware saved-search actions
- [x] run tests - must pass before task 5

### Task 5: Refactor watchlist and snapshot persistence to provider-aware identities

**Files:**
- Modify: `backend/src/cartrap/modules/search/{schemas.py,router.py,service.py}`
- Modify: `backend/src/cartrap/modules/watchlist/{schemas.py,service.py,repository.py}`
- Modify: `backend/src/cartrap/modules/watchlist/models.py`
- Modify: `frontend/src/{types.ts,lib/api.ts}`
- Modify: `frontend/src/features/watchlist/WatchlistPanel.tsx`
- Modify: `backend/tests/watchlist/test_watchlist_api.py`

- [x] change watchlist uniqueness from `(owner_user_id, lot_number)` to a provider-aware key and preserve existing Copart items via backfill/defaults
- [x] update `/search/watchlist` and `/watchlist` create contracts to accept provider-aware identifiers (`provider`, `provider_lot_id`, optional `lot_url`) instead of relying only on `lot_url`
- [x] update add-from-search to use provider-aware identifiers rather than assuming every provider has a verified public lot URL at add time
- [x] store provider metadata on tracked lots and snapshots so refresh always routes through the correct connector/service
- [x] render auction/source information on watchlist cards and keep deep links/additional details provider-aware
- [x] write backend tests for mixed-provider watchlist coexistence and refresh routing
- [x] write frontend tests for auction badges and provider-aware watchlist actions
- [x] run tests - must pass before task 6

### Task 6: Add IAAI connector UI in settings and generalize provider-aware copy

**Files:**
- Modify: `frontend/src/features/dashboard/AccountMenuSheet.tsx`
- Create: `frontend/src/features/integrations/ProviderConnectionCard.tsx`
- Modify: `frontend/src/features/integrations/CopartConnectionCard.tsx`
- Modify: `frontend/src/{App.tsx,types.ts,styles.css}`
- Modify: `frontend/tests/app.test.tsx`

- [x] either generalize the existing connection card or add a reusable provider card so Copart and IAAI use the same settings surface
- [x] show both connectors in Account/Settings with correct provider names, helper text, and status pills
- [x] replace Copart-only UI copy in search/watchlist actions with provider-aware or provider-specific messaging
- [x] show auction/source pill on saved-search result rows and any lot rows where cross-provider context matters
- [x] write frontend tests for loading, connecting, reconnecting, and disconnecting both providers
- [x] write frontend tests for provider-aware blocking copy and auction badge rendering in saved-search results
- [x] run tests - must pass before task 7

### Task 7: Update worker, monitoring, docs, and migration notes

**Files:**
- Modify: `backend/src/cartrap/worker/main.py`
- Modify: `backend/src/cartrap/modules/monitoring/service.py`
- Modify: `docs/backend-api.md`
- Modify: `docs/database-schema.md`
- Modify: `README.md`
- Modify: `ChangeLog.md`
- Modify: `backend/tests/{test_worker_main.py,monitoring/test_change_detection.py}`

- [x] make background refresh resolve the correct provider set for each saved search and the correct provider identity for each tracked lot
- [x] ensure provider-specific auth failures surface as item/search-level diagnostics instead of poisoning unrelated providers
- [x] document new API contracts, provider-aware identifiers, and migration/backfill expectations
- [x] write worker and monitoring tests for mixed-provider polling and partial-provider degradation
- [x] run backend test segments covering provider connections, IAAI, search, watchlist, monitoring, and worker
- [x] run frontend tests and production build
- [x] update this plan and `ChangeLog.md` once implementation stabilizes

## Post-Completion
- Repository implementation is complete; the remaining items are environment-specific validation and rollout decisions.
- Manual smoke-test a real IAAI account from the deployment environment to confirm Imperva/WAF does not block the chosen transport.
- Confirm the canonical public IAAI lot URL pattern before finalizing "Open lot" CTAs.
- Decision on 2026-03-25: route IAAI through a dedicated NAS-hosted `iaai_gateway` instead of AWS direct egress, because production bootstrap hits Imperva/WAF on the main backend path.
- Follow-up completed on 2026-03-25: `iaai_gateway` bootstrap now replays Imperva preflight + browser callback continuity, emits correlation-aware step diagnostics, and intentionally ignores caller `client_ip` because IAAI observes NAS egress rather than the AWS/frontend source address.
