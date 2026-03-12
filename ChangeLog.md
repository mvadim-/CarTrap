# Change Log

## [2026-03-11 15:12] Планування MVP для Copart PWA
- Створено базовий `ChangeLog.md` для подальшої фіксації кожного циклу змін.
- Додано план імплементації MVP у `docs/plans/20260311-copart-pwa-mvp.md`.
- Зафіксовано погоджену архітектуру: PWA frontend, Python backend, окремий worker, MongoDB, Docker Compose.
- Відображено ключові функції першої версії: invite-based auth, ролі `admin`/`user`, ручний пошук, watchlist, adaptive polling, web push.

## [2026-03-11 15:19] Початковий scaffold для Task 1
- Додано базовий `README.md`, `.env.example` та `docker-compose.yml` для стеку `mongodb`, `backend`, `worker`, `frontend`.
- Ініціалізовано Python backend scaffold: `backend/pyproject.toml`, пакет `cartrap`, мінімальний FastAPI health endpoint, placeholder worker і smoke test для імпорту.
- Ініціалізовано frontend scaffold: `package.json`, `vite.config.ts`, `tsconfig.json`, базовий React/Vite placeholder і тест конфігурації.
- Зафіксовано обмеження поточної перевірки: локально відсутній `pytest`, frontend залежності ще не встановлювалися.

## [2026-03-11 15:27] Task 2: backend app factory, config і локальне test environment
- Додано backend application factory та інфраструктурні модулі: `backend/src/cartrap/app.py`, `api/router.py`, `api/system.py`, `config.py`, `db/mongo.py`, `core/logging.py`.
- Розширено backend тести: `backend/tests/test_app_boot.py`, `backend/tests/test_config.py`; виправлено сумісність із локальним `Python 3.9`.
- Створено локальне `.venv`, встановлено Python-залежності для backend тестів і npm-залежності для frontend.
- Оновлено `README.md`, `.gitignore` і додано `backend/setup.py`, щоб локальний dev/test workflow був відтворюваним.
- Виконано перевірки: `./.venv/bin/pytest backend/tests` -> `6 passed`, `npm run test` у `frontend/` -> `1 passed`.

## [2026-03-11 15:35] Task 3: invite auth, JWT і RBAC
- Додано auth/admin backend модулі: `backend/src/cartrap/modules/auth/*`, `backend/src/cartrap/modules/admin/router.py`, а також `backend/src/cartrap/api/dependencies.py`.
- Реалізовано bootstrap admin через env, invite create/revoke, accept invite, login, refresh token і bearer-based role guards.
- Розширено backend конфіг: JWT secrets, token TTL, invite TTL, bootstrap admin credentials; додано залежності `PyJWT`, `email-validator`, `mongomock`.
- Підготовлено локальний `.venv` workflow до editable install: створено `backend/README.md`, оновлено `pip` у `.venv` до `26.0.1`, підтверджено `pip install -e './backend[dev]'`.
- Додано auth/RBAC тестове покриття: `backend/tests/auth/test_invites.py`, `test_login.py`, `test_rbac.py`; повний backend suite проходить: `./.venv/bin/pytest backend/tests` -> `13 passed`.

## [2026-03-11 15:48] Task 4: Copart provider, parser і fixtures
- Додано `copart_provider` модуль: `backend/src/cartrap/modules/copart_provider/client.py`, `parser.py`, `normalizer.py`, `models.py`, `service.py`.
- Винесено HTML parsing у окремий анти-корупційний шар з підтримкою embedded JSON для сторінки лота і результатів пошуку.
- Додано тестові фікстури Copart HTML: `backend/tests/fixtures/copart/lot_page.html` і `search_results.html`.
- Додано parser tests: `backend/tests/copart/test_parser_lot_page.py` і `test_search_parser.py`, включно з failure scenarios.
- Розширено backend залежності для scraping: `beautifulsoup4` як runtime dependency; підтверджено оновлення `.venv` через `pip install -e './backend[dev]'`.
- Виконано повний backend suite: `./.venv/bin/pytest backend/tests` -> `17 passed`.

## [2026-03-11 15:54] Task 5: watchlist і lot snapshots
- Додано watchlist backend модулі: `backend/src/cartrap/modules/watchlist/models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`.
- Реалізовано `tracked_lots` і `lot_snapshots` у MongoDB з user-scoped CRUD для watchlist через `/api/watchlist`.
- Додавання лота тепер одразу тягне snapshot через `copart_provider`, зберігає поточний стан у `tracked_lots` і окремий initial snapshot в `lot_snapshots`.
- Покрито edge cases: duplicate lot, upstream fetch failure, видалення чужого tracked lot, перевірка початкового snapshot storage.
- Додано тести: `backend/tests/watchlist/test_watchlist_api.py`, `backend/tests/watchlist/test_snapshot_storage.py`.
- Виконано повний backend suite: `./.venv/bin/pytest backend/tests` -> `22 passed`.

## [2026-03-11 15:55] Task 6: manual search API і add-from-search flow
- Додано search backend модуль: `backend/src/cartrap/modules/search/schemas.py`, `service.py`, `router.py`.
- Реалізовано `/api/search` з підтримкою `search_url` або базових фільтрів (`query`, `location`) і нормалізованою відповіддю по лотах.
- Реалізовано `/api/search/watchlist`, який перевикористовує `WatchlistService.add_tracked_lot` замість дублювання логіки додавання лота.
- Оновлено `backend/src/cartrap/api/router.py` для підключення search і watchlist модулів до загального API.
- Додано тестове покриття `backend/tests/search/test_search_api.py` для success, empty-results, invalid-filters, provider-failure і add-from-search сценаріїв.
- Виконано повний backend suite: `./.venv/bin/pytest backend/tests` -> `27 passed`.

## [2026-03-11 16:15] Task 7-8: monitoring worker і push subscriptions
- Додано monitoring backend модуль: `backend/src/cartrap/modules/monitoring/polling_policy.py`, `change_detection.py`, `service.py`, а також worker entrypoint `backend/src/cartrap/worker/main.py`.
- Реалізовано adaptive polling, compare logic для snapshot-ів, обробку parser/provider failure без перетирання останнього валідного стану та генерацію change events.
- Додано notifications backend модуль: `backend/src/cartrap/modules/notifications/models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`.
- Реалізовано API для push subscriptions: `GET/POST/DELETE /api/notifications/subscriptions`.
- Інтегровано monitoring з notification delivery: change events тепер можуть бути доставлені через абстракцію `WebPushSender`, а невалідні subscriptions автоматично видаляються після failure.
- Додано тести: `backend/tests/monitoring/test_polling_policy.py`, `test_change_detection.py`, `backend/tests/notifications/test_push_subscriptions.py`, `test_push_delivery.py`.
- Виконано повний backend suite: `./.venv/bin/pytest backend/tests` -> `36 passed`.

## [2026-03-11 16:25] Task 9: PWA frontend shell і основні user flows
- Перебудовано frontend shell у повноцінний PWA-клієнт: `frontend/src/App.tsx`, `src/app/router.tsx`, `src/app/useSession.ts`, `src/lib/api.ts`, `src/lib/session.ts`, `src/types.ts`.
- Додано feature UI для auth, admin invites, manual search, watchlist і push subscriptions: `frontend/src/features/**`.
- Додано PWA assets: `frontend/public/manifest.webmanifest`, `frontend/src/sw.ts` і новий візуальний шар `frontend/src/styles.css`.
- Реалізовано role-aware dashboard, invite acceptance screen, login flow, admin invite generation, manual search, add-from-search, watchlist remove і client-side push subscribe UX.
- Оновлено frontend test setup (`frontend/package.json`, `tsconfig.json`, `vite.config.ts`) і додано `frontend/tests/app.test.tsx` замість базового конфіг-тесту.
- Виконано перевірки: `npm run test` -> `3 passed`, `npm run build` -> успішний production build.

## [2026-03-11 16:41] Task 10: Docker hardening і runtime smoke check
- Додано `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf` і `.dockerignore`.
- Оновлено `docker-compose.yml` на image builds для `backend`, `worker`, `frontend` і статичний frontend runtime через nginx.
- Розширено `.env.example` та `README.md` під runtime secrets, bootstrap admin і Docker workflow.
- Додано smoke test `backend/tests/integration/test_dockerized_api.py`.
- Локальні перевірки пройдено: `./.venv/bin/pytest backend/tests` -> `37 passed`, `npm run test` -> `3 passed`, `npm run build` -> успішно, `docker compose config` -> успішно.
- Runtime smoke check пройдено: `docker compose build backend frontend worker` -> успішно, `docker compose up -d` -> стек піднявся, `curl http://localhost:8000/api/health` -> `200`, `curl -I http://localhost:5173` -> `200 OK`, після перевірки стек зупинено через `docker compose down`.

## [2026-03-11 16:42] Task 11: acceptance verification
- Оновлено `backend/tests/test_app_boot.py`, щоб regression test використовував alias-based поля `Settings`, як і production config contract.
- Повторно прогнано повний verification набір: `./.venv/bin/pytest backend/tests` -> `37 passed`, `npm run test` -> `3 passed`, `npm run build` -> успішно.
- Зафіксовано, що виділеного e2e test suite у проєкті ще немає; поточна acceptance verification спирається на backend unit/integration coverage, frontend app tests і Docker smoke checks з Task 10.

## [2026-03-11 16:42] Task 12: фінальна документація
- Оновлено `README.md` блоками `Current Status` і `Latest Verification`, щоб поточний стан MVP і перевірки були видимі без читання плану.
- `AGENTS.md` не змінювався: нових repo-specific workflow patterns понад уже зафіксовані не з’явилося.
- План реалізації перенесено до `docs/plans/completed/20260311-copart-pwa-mvp.md`.

## [2026-03-11 16:54] Fix CORS preflight for login flow
- Додано backend CORS-конфіг через `BACKEND_CORS_ORIGINS` у `backend/src/cartrap/config.py` і підключено `CORSMiddleware` в `backend/src/cartrap/app.py`.
- Додано regression tests для env parsing і `OPTIONS /api/auth/login` preflight у `backend/tests/test_config.py` та `backend/tests/test_app_boot.py`.
- Оновлено `.env.example` і `README.md`, щоб локальні frontend origins для `5173`/`4173` були дозволені за замовчуванням і явно документовані.

## [2026-03-11 17:08] Fix Copart manual search URL builder
- Оновлено `backend/src/cartrap/modules/search/schemas.py`: manual search тепер будує Copart `lotSearchResults` URL замість застарілого `/search` endpoint.
- Додано логування search failures у `backend/src/cartrap/modules/search/service.py`, щоб у backend logs було видно проблемний `source_url`.
- Оновлено `backend/tests/search/test_search_api.py` під новий URL contract і додано перевірку `SearchRequest.to_url()`.
- Додано завершений hotfix-план `docs/plans/completed/20260311-copart-search-hotfix.md`.

## [2026-03-11 17:18] Harden Copart search parser diagnostics
- Розширено `backend/src/cartrap/modules/copart_provider/parser.py`: search parser тепер підтримує вкладені JSON payload-и на кшталт `__NEXT_DATA__`, `__NUXT_DATA__`, `__PRELOADED_STATE__`, `__INITIAL_STATE__`.
- Додано окреме розпізнавання anti-bot/challenge HTML від Copart і warning-лог із title/script ids, якщо payload у відповіді не знайдено.
- Додано parser fixtures і тести `backend/tests/fixtures/copart/search_results_next_data.html`, `backend/tests/copart/test_search_parser.py` для nested JSON і challenge-page сценарію.

## [2026-03-11 17:34] Add watchlist flow by lot number
- Розширено `POST /api/watchlist`: endpoint тепер приймає `lot_url` або `lot_number` через `backend/src/cartrap/modules/watchlist/schemas.py` і нормалізує номер лота в стандартний Copart URL.
- Оновлено `backend/tests/watchlist/test_watchlist_api.py` новими сценаріями для `lot_number` input і валідації порожнього payload.
- Додано frontend flow “Add by Lot Number” у `frontend/src/features/watchlist/WatchlistPanel.tsx`, інтегровано в `frontend/src/App.tsx` і `frontend/src/lib/api.ts`.
- Розширено `frontend/tests/app.test.tsx` перевіркою додавання в watchlist по lot number.
- Оновлено `.gitignore`, щоб `frontend/src/lib/*.ts` не блокувалися загальним Python-правилом `lib/`.

## [2026-03-11 17:47] Harden Copart lot parser diagnostics
- Розширено `backend/src/cartrap/modules/copart_provider/parser.py`: lot parser тепер підтримує вкладені JSON payload-и з `__NEXT_DATA__`, `__NUXT_DATA__`, `__PRELOADED_STATE__`, `__INITIAL_STATE__`.
- Додано окреме розпізнавання anti-bot/challenge HTML для lot pages і warning-лог із title/script ids, якщо payload у відповіді не знайдено.
- Додано `backend/tests/fixtures/copart/lot_page_next_data.html` і розширено `backend/tests/copart/test_parser_lot_page.py` сценаріями nested JSON та challenge page.

## [2026-03-11 17:55] Expose watchlist lot-fetch failure reason
- Додано `logger.exception(...)` у `backend/src/cartrap/modules/watchlist/service.py`, щоб `POST /api/watchlist` не ховав першопричину lot fetch/parse збою.
- `502` від watchlist тепер містить detail із повідомленням винятку Copart provider/parser.
- Оновлено `backend/tests/watchlist/test_watchlist_api.py` під новий error contract.

## [2026-03-11 18:04] Run browser-like Copart request experiment
- Оновлено `backend/src/cartrap/modules/copart_provider/client.py`: додано browser-like headers, homepage warmup request, `Referer` на target fetch і optional HTTP/2, якщо в runtime доступний `h2`.
- Додано ізольовані тести `backend/tests/copart/test_http_client.py` на session warmup, header profile і graceful continuation після warmup failure.
- Додано завершений план `docs/plans/completed/20260311-copart-browser-headers-experiment.md` для цього експерименту.

## [2026-03-12 14:31] Refactor Copart integration to JSON API
- Замінено HTML scraping в `backend/src/cartrap/modules/copart_provider/` на POST запити до Copart JSON API (`mmember.copart.com/srch/?services=bidIncrementsBySiteV2`) з env-configured headers і cookies.
- `fetch_lot()` тепер працює через lookup по `lot_number` через той самий JSON endpoint; HTML parser layer, fixtures і `beautifulsoup4` dependency видалені.
- Оновлено search contract у backend/frontend: `make` / `model` / `year_from` / `year_to` замість попереднього `query` / `location`, з новим JSON request builder.
- Додано нові тести `backend/tests/copart/test_http_client.py`, `backend/tests/copart/test_api_normalizer.py`, оновлено `backend/tests/search/test_search_api.py`, `backend/tests/watchlist/test_watchlist_api.py`, `backend/tests/test_config.py`, `frontend/tests/app.test.tsx`.
- Оновлено `.env.example`, `README.md` і додано завершений план `docs/plans/completed/20260312-copart-json-api-provider.md`.
