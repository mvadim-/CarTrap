# Copart Search Hotfix

## Goal
- Прибрати явно некоректний search URL builder для manual search.
- Перевести generated Copart URL на `lotSearchResults`, ближчий до реального `vehicleFinder` flow.
- Додати мінімальну observability для діагностики наступних змін Copart.

## Scope
- Оновити `backend/src/cartrap/modules/search/schemas.py`
- Оновити `backend/src/cartrap/modules/search/service.py`
- Актуалізувати backend search tests

## Verification
- `./.venv/bin/pytest backend/tests/search/test_search_api.py`

## Outcome
- `source_url` більше не будується через застарілий `/search?...`
- У випадку нового збою backend логуватиме проблемний `source_url`
- Локаційний фільтр поки що не мапиться в Copart filter DSL і використовується лише в `displayStr`; це відома технічна межа hotfix
