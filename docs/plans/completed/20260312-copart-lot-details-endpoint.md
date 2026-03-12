# Copart Lot Details Endpoint

## Goal
- Перевести `fetch_lot()` з search-based lookup на окремий Copart lot details endpoint.

## Scope
- `backend/src/cartrap/modules/copart_provider/client.py`
- `backend/src/cartrap/modules/copart_provider/service.py`
- `backend/src/cartrap/modules/copart_provider/normalizer.py`
- backend copart/config tests

## Decisions
- Search лишається на `/srch/?services=bidIncrementsBySiteV2`
- Single lot fetch переходить на `/lots-api/v1/lot-details?services=bidIncrementsBySiteV2`
- Lot response нормалізується з `lotDetails` object без fallback через search docs

## Verification
- `./.venv/bin/pytest backend/tests/copart/test_http_client.py backend/tests/copart/test_api_normalizer.py backend/tests/watchlist/test_watchlist_api.py backend/tests/test_config.py`

## Outcome
- `add by lot number` і monitoring більше не залежать від search lookup для окремого лота
- provider має чітке розділення між search endpoint і lot details endpoint
