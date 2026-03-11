# Copart PWA MVP

## Overview
- Побудувати PWA-додаток поверх `copart.com` з власним Python-бекендом, MongoDB та запуском у Docker.
- Реалізувати закритий доступ через `invite flow`, де користувачів створює лише адміністратор.
- Дати користувачу змогу вручну шукати лоти Copart, додавати лоти до watchlist і отримувати web push при зміні стану аукціону.
- Закласти архітектурну основу для майбутнього додавання `saved_searches` і моніторингу появи нових лотів за критеріями.

## Context (from discovery)
- files/components involved:
  - Поточний репозиторій майже порожній: [`AGENTS.md`](/Users/mvadym/Documents/Dev/CarTrap/AGENTS.md), [`LICENSE`](/Users/mvadym/Documents/Dev/CarTrap/LICENSE), [`.gitignore`](/Users/mvadym/Documents/Dev/CarTrap/.gitignore)
  - Нові області коду очікуються в `src/`, `tests/`, `docs/`, `frontend/` або еквівалентній структурі для web-клієнта
- related patterns found:
  - У проєкті ще немає прикладного коду, тому структура і конвенції задаються цим планом
  - `AGENTS.md` вимагає окремого запису в `ChangeLog.md` на кожен цикл змін
- dependencies identified:
  - Python backend (`FastAPI`, `Pydantic`, `PyMongo/Motor`)
  - PWA frontend (`React + Vite`)
  - MongoDB
  - Docker Compose
  - HTML scraping stack (`httpx`, `selectolax` або `lxml/BeautifulSoup`)
  - Web Push (`pywebpush` або сумісна бібліотека)

## Development Approach
- **testing approach**: Regular (код спочатку, потім тести) для швидкого старту greenfield MVP
- Використовувати модульний моноліт з окремими контейнерами `frontend`, `backend`, `worker`, `mongodb`
- Тримати всі інтеграції з `copart.com` виключно в модулі `copart_provider`
- **CRITICAL: every task MUST include new/updated tests** for code changes in that task
  - unit тести потрібні для нових і змінених модулів
  - integration тести потрібні для API і MongoDB інтеграцій
  - parsing/change-detection сценарії мають бути покриті фікстурами
- **CRITICAL: all tests must pass before starting next task**
- **CRITICAL: update this plan file when scope changes during implementation**
- Після кожного завершеного кроку оновлювати `ChangeLog.md`
- Зберігати межі модулів жорсткими, щоб парсер Copart не просочувався у бізнес-логіку

## Testing Strategy
- **unit tests**:
  - парсинг сторінок Copart і нормалізація лота
  - auth utilities: password hashing, JWT, invite token checks
  - domain logic: adaptive polling, change detection, permission guards
- **integration tests**:
  - API endpoints для auth, admin invites, watchlist, search, push subscriptions
  - перевірка роботи з MongoDB через test container або окрему test database в Docker Compose
- **e2e tests**:
  - login/invite acceptance flow
  - ручний пошук і додавання лота до watchlist
  - підписка на push у PWA
- Зберігати HTML/JSON фікстури Copart у `tests/fixtures/` для стабільних parser tests

## Progress Tracking
- Позначати виконані пункти відразу через `[x]`
- Додавати нові знайдені задачі з префіксом `➕`
- Фіксувати блокери з префіксом `⚠️`
- Не переходити до наступної задачі, доки її код і тести не завершені
- Синхронізувати цей файл із фактичним прогресом реалізації

## What Goes Where
- **Implementation Steps** (`[ ]` checkboxes): код, тести, конфігурація Docker, документація проєкту
- **Post-Completion** (без чекбоксів): ручна перевірка на реальному акаунті Copart, production secrets, домен і HTTPS для push у production

## Implementation Steps

### Task 1: Initialize repository structure and developer tooling

**Files:**
- Create: `README.md`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `backend/pyproject.toml`
- Create: `backend/src/cartrap/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`

- [x] створити базову структуру директорій для `backend`, `frontend`, `docs`, `tests` і локальної конфігурації
- [x] описати в `README.md` цілі MVP, сервіси Docker і базові команди запуску
- [x] додати `docker-compose.yml` для `frontend`, `backend`, `worker`, `mongodb`
- [x] налаштувати базові backend/frontend маніфести та змінні середовища в `.env.example`
- [x] write tests for backend bootstrap/import smoke case and frontend config validation where practical
- [x] run tests - must pass before next task

### Task 2: Create backend app skeleton and shared infrastructure

**Files:**
- Create: `backend/src/cartrap/main.py`
- Create: `backend/src/cartrap/config.py`
- Create: `backend/src/cartrap/api/router.py`
- Create: `backend/src/cartrap/db/mongo.py`
- Create: `backend/src/cartrap/core/logging.py`
- Create: `backend/tests/test_app_boot.py`
- Create: `backend/tests/test_config.py`

- [x] створити FastAPI application factory і кореневий router
- [x] додати typed config layer для env variables і підключення до MongoDB
- [x] винести спільні логування, healthcheck і базову обробку помилок
- [x] підготувати спільну інфраструктуру для використання і `backend`, і `worker`
- [x] write tests for app bootstrap and config parsing success cases
- [x] write tests for config validation and startup edge cases
- [x] run tests - must pass before next task

### Task 3: Implement auth, roles, and invite-based onboarding

**Files:**
- Create: `backend/src/cartrap/modules/auth/models.py`
- Create: `backend/src/cartrap/modules/auth/schemas.py`
- Create: `backend/src/cartrap/modules/auth/repository.py`
- Create: `backend/src/cartrap/modules/auth/service.py`
- Create: `backend/src/cartrap/modules/auth/router.py`
- Create: `backend/src/cartrap/modules/admin/router.py`
- Create: `backend/tests/auth/test_invites.py`
- Create: `backend/tests/auth/test_login.py`
- Create: `backend/tests/auth/test_rbac.py`

- [x] реалізувати моделі `users` і `invites` з ролями `admin` та `user`
- [x] додати invite creation/revoke endpoints, доступні лише адміністратору
- [x] реалізувати accept invite flow, password hashing і login/refresh flow
- [x] додати role guards для admin-only API
- [x] write tests for invite lifecycle and login success scenarios
- [x] write tests for invalid/expired invite, bad credentials, and RBAC denial cases
- [x] run tests - must pass before next task

### Task 4: Build Copart provider and normalization layer

**Files:**
- Create: `backend/src/cartrap/modules/copart_provider/client.py`
- Create: `backend/src/cartrap/modules/copart_provider/parser.py`
- Create: `backend/src/cartrap/modules/copart_provider/models.py`
- Create: `backend/src/cartrap/modules/copart_provider/normalizer.py`
- Create: `backend/tests/copart/test_parser_lot_page.py`
- Create: `backend/tests/copart/test_search_parser.py`
- Create: `backend/tests/fixtures/copart/`

- [ ] реалізувати HTTP client для отримання сторінок Copart і базову обробку помилок/timeout
- [ ] реалізувати parser для сторінки лота з виділенням `lot_number`, статусу, sale date, current bid та інших ключових полів
- [ ] реалізувати parser для manual search results і нормалізацію в доменні моделі
- [ ] ізолювати raw scraping logic від решти системи через чіткий provider interface
- [ ] write tests for lot-page parsing and normalization success cases using fixtures
- [ ] write tests for malformed/missing-field fixtures and provider failure cases
- [ ] run tests - must pass before next task

### Task 5: Add watchlist domain and lot snapshot history

**Files:**
- Create: `backend/src/cartrap/modules/watchlist/models.py`
- Create: `backend/src/cartrap/modules/watchlist/schemas.py`
- Create: `backend/src/cartrap/modules/watchlist/repository.py`
- Create: `backend/src/cartrap/modules/watchlist/service.py`
- Create: `backend/src/cartrap/modules/watchlist/router.py`
- Create: `backend/tests/watchlist/test_watchlist_api.py`
- Create: `backend/tests/watchlist/test_snapshot_storage.py`

- [ ] реалізувати колекції `tracked_lots` і `lot_snapshots`
- [ ] додати API для додавання, видалення і перегляду watchlist користувача
- [ ] зберігати початковий snapshot при першому додаванні валідного лота
- [ ] оновлювати `tracked_lot` останнім відомим станом без втрати історії в `lot_snapshots`
- [ ] write tests for watchlist CRUD and initial snapshot success scenarios
- [ ] write tests for duplicate lot, invalid lot source, and ownership edge cases
- [ ] run tests - must pass before next task

### Task 6: Add manual search API and watchlist integration from results

**Files:**
- Create: `backend/src/cartrap/modules/search/schemas.py`
- Create: `backend/src/cartrap/modules/search/service.py`
- Create: `backend/src/cartrap/modules/search/router.py`
- Modify: `backend/src/cartrap/modules/watchlist/service.py`
- Create: `backend/tests/search/test_search_api.py`

- [ ] реалізувати search endpoint, який приймає фільтри і повертає нормалізовані результати Copart
- [ ] забезпечити єдиний формат lot summary для search results і watchlist
- [ ] додати сценарій “add to watchlist” з результатів пошуку без дублювання доменної логіки
- [ ] підготувати контракти API так, щоб пізніше додати `saved_searches` без ломування клієнта
- [ ] write tests for search endpoint success cases and add-from-search flow
- [ ] write tests for invalid filters, empty results, and downstream scraper failure cases
- [ ] run tests - must pass before next task

### Task 7: Implement monitoring worker and adaptive polling

**Files:**
- Create: `backend/src/cartrap/worker/main.py`
- Create: `backend/src/cartrap/modules/monitoring/service.py`
- Create: `backend/src/cartrap/modules/monitoring/polling_policy.py`
- Create: `backend/src/cartrap/modules/monitoring/change_detection.py`
- Create: `backend/tests/monitoring/test_polling_policy.py`
- Create: `backend/tests/monitoring/test_change_detection.py`

- [ ] реалізувати worker entrypoint і scheduler loop для періодичних перевірок активних лотів
- [ ] додати adaptive polling policy: повільний режим за замовчуванням і частіший polling перед аукціоном
- [ ] реалізувати compare logic між попереднім і новим snapshot для визначення значущих змін
- [ ] зберігати результати перевірок так, щоб помилки scraping не перетирали валідний останній стан
- [ ] write tests for polling policy and significant-change detection success cases
- [ ] write tests for retry/backoff, parse failure, and no-op change scenarios
- [ ] run tests - must pass before next task

### Task 8: Add Web Push subscriptions and notification delivery

**Files:**
- Create: `backend/src/cartrap/modules/notifications/models.py`
- Create: `backend/src/cartrap/modules/notifications/service.py`
- Create: `backend/src/cartrap/modules/notifications/router.py`
- Create: `backend/tests/notifications/test_push_subscriptions.py`
- Create: `backend/tests/notifications/test_push_delivery.py`

- [ ] реалізувати збереження `push_subscriptions` для браузерів користувача
- [ ] додати API для subscribe/unsubscribe на backend
- [ ] інтегрувати worker change events з доставкою Web Push через VAPID keys
- [ ] обробити невалідні або прострочені subscriptions без падіння job-процесу
- [ ] write tests for subscription CRUD and delivery success cases
- [ ] write tests for invalid subscription cleanup and push provider failure cases
- [ ] run tests - must pass before next task

### Task 9: Build PWA frontend for auth, search, watchlist, and admin invite flow

**Files:**
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/router.tsx`
- Create: `frontend/src/features/auth/`
- Create: `frontend/src/features/admin/`
- Create: `frontend/src/features/search/`
- Create: `frontend/src/features/watchlist/`
- Create: `frontend/src/features/push/`
- Create: `frontend/public/manifest.webmanifest`
- Create: `frontend/src/sw.ts`
- Create: `frontend/tests/`

- [ ] реалізувати PWA shell, routing і auth state management
- [ ] створити UI для invite acceptance, login і role-aware navigation
- [ ] створити admin UI для генерації та відкликання інвайтів
- [ ] створити manual search UI, список результатів і додавання лота у watchlist
- [ ] реалізувати watchlist UI і client-side flow підписки на push
- [ ] write tests for frontend success scenarios including route guards and core user flows
- [ ] write tests for auth errors, empty states, and push permission denial cases
- [ ] run tests - must pass before next task

### Task 10: Harden Docker workflow, docs, and delivery checks

**Files:**
- Modify: `README.md`
- Modify: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `backend/tests/integration/test_dockerized_api.py`
- Modify: `docs/plans/20260311-copart-pwa-mvp.md`

- [ ] додати production-like Dockerfiles для `backend`, `worker` і `frontend`
- [ ] перевірити коректний запуск усього стеку через `docker compose up`
- [ ] задокументувати змінні середовища, локальний запуск і базові operational notes
- [ ] синхронізувати план-файл з фактичним scope та знайденими відхиленнями
- [ ] write tests for dockerized backend smoke flow and critical integration path
- [ ] write tests for startup failure scenarios caused by missing config
- [ ] run tests - must pass before next task

### Task 11: Verify acceptance criteria
- [ ] verify all requirements from Overview are implemented
- [ ] verify edge cases are handled
- [ ] run full test suite: `docker compose run --rm backend pytest && docker compose run --rm frontend npm test`
- [ ] run e2e tests if project has them: `docker compose run --rm frontend npm run test:e2e`
- [ ] verify test coverage meets project standard

### Task 12: [Final] Update documentation
- [ ] update README.md if needed
- [ ] update AGENTS.md if new patterns discovered
- [ ] update ChangeLog.md with final implementation cycle notes
- [ ] move this plan to `docs/plans/completed/`

## Technical Details
- Базові MongoDB колекції:
  - `users`
  - `invites`
  - `tracked_lots`
  - `lot_snapshots`
  - `push_subscriptions`
  - `saved_searches` як зарезервований напрям для наступної ітерації
- Ролі:
  - `admin`: створює і відкликає інвайти, керує доступом
  - `user`: виконує пошук, керує watchlist, підписується на push
- Базові backend модулі:
  - `auth`
  - `admin`
  - `copart_provider`
  - `watchlist`
  - `search`
  - `monitoring`
  - `notifications`
  - `shared`
- Основний data flow:
  - `invite -> accept -> user`
  - `search -> lot summary -> add to watchlist -> initial snapshot`
  - `worker polling -> snapshot compare -> notification event -> web push`
- Правила моніторингу:
  - стандартний polling рідкий
  - перед стартом аукціону polling частішає
  - parse failure не перетирає останній валідний стан
  - push відправляється лише на значущі зміни

## Post-Completion
- Перевірити стабільність scraping на реальних сторінках Copart з різними типами лотів
- Налаштувати production secrets для JWT, VAPID, MongoDB, Copart-related headers/cookies якщо знадобляться
- Додати HTTPS домен для коректної роботи PWA installability і Web Push у production
- Спланувати другу фазу: `saved_searches`, diff нових лотів за критеріями, push по нових збігах
