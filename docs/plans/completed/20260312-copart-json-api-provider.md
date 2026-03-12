# Copart JSON API Provider Refactor

## Goal
- Замінити HTML scraping Copart на роботу через JSON API.
- Прибрати parser/fixtures, які були потрібні лише для HTML сторінок.
- Зберегти поточні search, watchlist і monitoring flows поверх нового provider contract.

## Scope
- `backend/src/cartrap/modules/copart_provider/*`
- `backend/src/cartrap/modules/search/*`
- `backend/src/cartrap/config.py`
- `frontend/src/features/search/SearchPanel.tsx`
- `frontend/src/App.tsx`
- `frontend/src/lib/api.ts`
- таргетовані backend/frontend tests

## Decisions
- Copart search і single-lot fetch обидва йдуть через `mmember.copart.com/srch/?services=bidIncrementsBySiteV2`
- `fetch_lot()` витягує `lot_number` з URL/identifier і робить lookup через той самий JSON endpoint
- Copart auth/session headers конфігуруються через `.env`, а не hardcode в коді
- HTML parser code і `beautifulsoup4` dependency видалені

## Verification
- `./.venv/bin/pytest backend/tests/copart/test_http_client.py backend/tests/copart/test_api_normalizer.py backend/tests/search/test_search_api.py backend/tests/watchlist/test_watchlist_api.py backend/tests/test_config.py`
- `npm --prefix frontend run test -- --run tests/app.test.tsx`

## Outcome
- provider більше не залежить від anti-bot-prone lot/search page HTML parsing
- search UI працює з більш структурованими make/model/year filters
- кодова база очищена від parser layer, HTML fixtures і `beautifulsoup4`
