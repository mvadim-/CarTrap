# IAAI Gateway Bootstrap Hardening

## Overview
- Довести до production-ready стану шлях `AWS backend -> iaai-gateway -> IAAI` для connector bootstrap, не ламаючи існуючий Copart gateway.
- Закрити поточний blocker: `iaai-gateway` уже отримує `POST /v1/connector/bootstrap`, але bootstrap падає після `GET /Identity/Account/Login`, що вказує на неповний Imperva/browser replay.
- Зберегти split-архітектуру: весь anti-bot / browser-like bootstrap залишається на NAS-hosted `iaai-gateway`, а AWS backend працює тільки через gateway transport.

## Context (current production state)
- `backend` на AWS уже бачить `IAAI_GATEWAY_BASE_URL` і доходить до `iaai-gateway`; інфраструктурний етап більше не є blocker.
- `iaai-gateway` успішно проходить:
  - `GET /.well-known/openid-configuration` -> `200`
  - `GET /connect/authorize` -> `302`
  - `GET /Identity/Account/Login` -> `200`
- Після цього `POST /v1/connector/bootstrap` повертає `502`, тобто збоїть уже внутрішній bootstrap flow до моменту отримання робочого auth bundle.
- Поточний `backend/src/cartrap/modules/iaai_provider/client.py` відтворює лише спрощену частину OIDC flow і не реплеїть весь Imperva/browser pre-login sequence з `Temp/Login-flow-iaai`.
- Поточний direct bootstrap path приймає `client_ip`, але фактично не використовує його в IAAI requests; це треба або свідомо відкинути, або включити в replay/headers strategy, якщо upstream heuristics від нього залежать.
- У trace `Temp/Login-flow-iaai` є додаткові anti-bot елементи:
  - Imperva pre-login call `/A-would-they-here-beathe-and-should-mis-fore-Cas`
  - anti-bot cookies на кшталт `reese84`, `incap_ses_*`, `visid_incap_*`
  - browser/mobile-shaped headers, referer/origin continuity і cookie carry-over між authorize/login/submit/callback
- Висновок: потрібен окремий follow-up hardening саме для IAAI bootstrap replay, а не чергові зміни в AWS/NAS routing.

## Development Approach
- **testing approach**: Regular (code first, then tests)
- спочатку додати step-level diagnostics, щоб точно бачити, на якому етапі валиться bootstrap у production
- після цього імплементувати мінімально необхідний Imperva/browser replay, а не випадкове розширення заголовків
- не виносити anti-bot state у frontend або AWS backend; він повинен жити всередині `iaai-gateway` encrypted session bundle
- не логувати raw cookies, tokens або password; у діагностиці залишати лише safe step names, status codes і sanitized hints
- зберегти end-to-end correlation між `provider_connections` на AWS і `iaai-gateway` на NAS, щоб production failures можна було звести в один trace без ручного звіряння логів
- update this plan if по trace або прод-логах відкриються додаткові обов'язкові preflight steps

## Testing Strategy
- **backend unit/integration tests**
  - step-aware bootstrap failure classification
  - correlation-id propagation and safe diagnostic surfacing across backend/gateway boundary
  - Imperva preflight replay and cookie persistence
  - `client_ip` propagation behavior, якщо його використання стане частиною bootstrap strategy
  - login submit/callback success path with browser-like headers
  - session bundle completeness for immediate `search` / `lot-details` execute calls
- **gateway regression tests**
  - `bootstrap -> verify -> execute(search)` happy path через gateway contract
  - invalid credentials vs upstream rejected vs WAF/anti-bot blocked mapping
  - refresh/reauth path when stored auth bundle expires or becomes incomplete
- **manual verification**
  - connect IAAI from production frontend against NAS gateway
  - immediately run IAAI search after connect
  - open one IAAI lot details fetch through gateway-backed connector
  - verify logs contain step-aware diagnostics without leaking secrets

## Progress Tracking
- mark completed items with `[x]` immediately when done
- add newly discovered tasks with `➕` prefix
- document blockers with `⚠️` prefix
- keep this plan aligned with actual gateway hardening work

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): code, tests, docs, diagnostics, gateway behavior changes in this repository
- **Post-Completion** (no checkboxes): live-account smoke tests, reverse-proxy hardening, optional browser-assisted fallback decision

## Implementation Steps

### Task 0: Add step-level bootstrap diagnostics and explicit failure mapping

**Files:**
- Modify: `backend/src/cartrap/modules/iaai_provider/client.py`
- Modify: `backend/src/cartrap/modules/iaai_provider/errors.py`
- Modify: `backend/src/cartrap/modules/iaai_gateway/router.py`
- Modify: `backend/src/cartrap/modules/iaai_gateway/schemas.py`
- Modify: `backend/src/cartrap/modules/provider_connections/service.py`
- Modify: `backend/src/cartrap/modules/provider_connections/router.py`
- Modify: `backend/tests/iaai/test_http_client.py`
- Modify: `backend/tests/iaai/test_gateway_router.py`
- Modify: `backend/tests/provider_connections/test_iaai_router.py`

- [x] add explicit bootstrap steps such as `oidc_metadata`, `authorize`, `login_page`, `imperva_preflight`, `login_submit`, `authorize_callback`, `token_exchange`
- [x] surface sanitized step-aware diagnostics from `iaai-gateway` back to backend/provider-connections mapping
- [x] propagate a correlation identifier from AWS backend to NAS gateway so one failed connect attempt can be traced end-to-end
- [x] ensure failures that are configuration/transport errors are separated from upstream anti-bot/auth failures
- [x] add regression tests for step-aware error mapping and safe diagnostic payloads
- [x] run targeted tests and keep them green before moving to Task 1

### Task 1: Replay Imperva pre-login flow and persist anti-bot cookie state

**Files:**
- Modify: `backend/src/cartrap/modules/iaai_provider/client.py`
- Modify: `backend/tests/iaai/test_http_client.py`
- Reference: `Temp/Login-flow-iaai`

- [x] codify the minimum required Imperva preflight sequence observed in `Temp/Login-flow-iaai`
- [x] preserve required anti-bot cookies and related request continuity across preflight, login page, and submit steps
- [x] decide explicitly whether `client_ip` should influence replay headers/calls; if yes, codify and test it, if no, document why it is intentionally ignored
- [x] keep replay logic isolated so non-gateway/backend code does not need to understand Imperva details
- [x] add tests covering successful anti-bot state carry-over and failure when mandatory preflight state is missing
- [x] run targeted tests and keep them green before moving to Task 2

### Task 2: Harden browser-like login submit and authorize callback follow-up

**Files:**
- Modify: `backend/src/cartrap/modules/iaai_provider/client.py`
- Modify: `backend/tests/iaai/test_http_client.py`
- Modify: `backend/tests/iaai/test_gateway_connector_flow.py`

- [x] align login submit and callback requests with captured browser/mobile headers where they materially affect auth success
- [x] preserve antiforgery/session cookies across login form submit, authorize callback, and token exchange
- [x] normalize redirect and callback handling so partial relative URLs or hidden-form transitions do not break bootstrap
- [x] add regression tests for successful callback completion and expected failure mapping when callback state is invalid
- [x] run targeted tests and keep them green before moving to Task 3

### Task 3: Verify post-bootstrap connector lifecycle against real gateway-backed execute paths

**Files:**
- Modify: `backend/src/cartrap/modules/iaai_provider/client.py`
- Modify: `backend/src/cartrap/modules/iaai_gateway/service.py`
- Modify: `backend/tests/iaai/test_gateway_connector_flow.py`
- Modify: `backend/tests/iaai/test_gateway_client_config.py`

- [x] ensure the stored encrypted session bundle contains everything required for immediate `verify`, `search`, and `lot-details` execute calls
- [x] harden refresh/reauth rules when the bootstrap bundle is stale, partially missing, or rejected by upstream
- [x] add regression tests for bootstrap-to-execute continuity and reauth edge cases
- [x] run targeted tests and keep them green before moving to Task 4

### Task 4: Update operator docs and rollout notes

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/20260325-iaai-multi-auction-support.md`
- Modify: `docs/plans/20260325-iaai-gateway-bootstrap-hardening.md`
- Modify: `ChangeLog.md`

- [x] document the final IAAI gateway deployment/runtime requirements and expected diagnostics
- [x] sync the main multi-auction plan with the actual bootstrap hardening outcome
- [x] capture production rollout notes, known limitations, and recovery steps
- [x] update `ChangeLog.md`

## Outcome Notes
- Bootstrap hardening now replays the observed login sequence up to token exchange, including the Imperva `/A-would-they-here-beathe-and-should-mis-fore-Cas` GET+POST pair and cookie carry-over into login submit/callback.
- AWS `provider_connections` now propagates a correlation id into `iaai-gateway`, while NAS returns sanitized `step`, `failure_class`, `error_code`, and optional upstream status without leaking cookies/tokens/passwords.
- `client_ip` was explicitly kept out of IAAI upstream replay: the effective source IP is the NAS egress address, so injecting caller IP into synthetic browser/mobile headers would not improve realism.
- Session-bundle validation now fails fast if anti-bot cookies or required mobile header profile fields are missing before an execute path tries to hit IAAI.

## Post-Completion
- Run a real-account smoke test from production frontend against NAS-hosted `iaai-gateway`.
- Decide whether IAAI still needs a browser-assisted fallback if Imperva behavior changes again.
- Harden `iaai-gw` reverse proxy with tighter exposure rules, rate limiting, and optionally a less chatty public surface than the current open `/health`.
