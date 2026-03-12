# 2026-03-12 Search Catalog Backend Cache and Dropdown UI

## Goal
- Перевести `Manual Copart Search` з вільних текстових полів на backend-served make/model каталог.
- Тримати каталог у Mongo, а не тягнути Copart `keywords` на кожен вхід у UI.
- Дати адміну кнопку примусового refresh каталогу з live Copart `keywords` endpoint.

## Decisions
- Використати статичний JSON-каталог як startup seed, якщо в Mongo ще немає актуального документа.
- Додати `GET /api/search/catalog` для звичайного читання каталогу frontend-ом.
- Додати `POST /api/admin/search-catalog/refresh` для live rebuild через Copart keywords + NHTSA mapping.
- Передавати у `/api/search` не лише `make` / `model`, а й catalog-derived `make_filter` / `model_filter`, щоб пошук спирався на реальні Copart filter queries.
- У frontend зробити залежні dropdown-и `Make` / `Model` і окрему admin-панель для refresh каталогу.

## Deliverables
- `backend/src/cartrap/modules/search/models.py`
- `backend/src/cartrap/modules/search/repository.py`
- `backend/src/cartrap/modules/search/catalog_refresh.py`
- `backend/src/cartrap/modules/search/service.py`
- `backend/src/cartrap/modules/search/router.py`
- `backend/src/cartrap/modules/admin/router.py`
- `frontend/src/features/search/SearchPanel.tsx`
- `frontend/src/features/admin/AdminSearchCatalogPanel.tsx`

## Validation
- `./.venv/bin/pytest backend/tests`
- `npm --prefix frontend run test -- --run tests/app.test.tsx`
- `npm --prefix frontend run build`

## Outcome
- Search catalog тепер кешується у Mongo і віддається з backend.
- Admin може форсовано перебудувати каталог без ручного редагування коду.
- Search UI вже використовує dropdown-и `Make` / `Model`, що живляться від нашого сервера, а не напряму з Copart.
