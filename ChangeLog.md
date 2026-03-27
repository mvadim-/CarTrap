# Change Log

## [2026-03-27 17:55] Make mobile dashboard headers less bulky and safer
- Оновлено `frontend/src/styles.css`: mobile `dashboard-header` став компактнішим за padding, radius і typography, а `Menu` button більше не виглядає як великий окремий блок у шапці.
- Ті самі стилі перебудували mobile headers для `Saved Searches` і `Tracked Lots`: текстовий блок тепер має повну ширину, action buttons йдуть окремим compact row під ним, тому lede не зжимається і кнопки не вилазять за межі панелей.
- Додатково ущільнено mobile chips для `All / New / Needs attention`, щоб вони лишалися в одному рядку всередині контейнера без overflow.

## [2026-03-27 17:49] Normalize dashboard button shape and sizing
- Оновлено `frontend/src/styles.css`: для основних CTA, ghost buttons і filter chips введено спільні control tokens (`--control-height`, `--control-radius`), вирівняно мінімальну висоту, padding і округлення, щоб кнопки в dashboard більше не виглядали як суміш круглих, овальних і різновисоких елементів.
- Окремо на mobile прибрано зайве full-width розтягування `Menu` button у header, щоб він залишався тим самим rounded-rectangle control, що й інші дії на екрані.

## [2026-03-27 17:45] Tighten mobile saved-search spacing and add watchlist lede
- Оновлено `frontend/src/features/{search/SearchPanel.tsx,watchlist/WatchlistPanel.tsx}`: `Saved Searches` у collapsed state тепер не залишає зайвий порожній блок під action buttons, а `Tracked Lots` отримав explanatory lede під заголовком для візуальної симетрії з inbox секцією.
- Оновлено `frontend/src/styles.css`: mobile toolbar для `All / New / Needs attention` переведено в один рядок з компактнішими chip proportions, а collapsed search panel тепер має зменшений bottom padding.

## [2026-03-27 17:40] Relax mobile header action stacking after Playwright review
- Оновлено `frontend/src/styles.css`: прибрано агресивне mobile-правило, яке розтягувало `.panel-header__actions` у колонку на всю ширину; action buttons для `Saved Searches` і `Tracked Lots` тепер лишаються компактною inline-group на мобільному, без ламання композиції секцій.
- Verification: Playwright mobile check проти `https://cartrapapp.pp.ua` підтвердив проблему на проді, після чого локальний frontend було перевірено в mobile viewport; `cd frontend && npm test -- app.test.tsx` -> `53 passed`, `cd frontend && npm run build` -> успішно.

## [2026-03-27 17:27] Add collapsible Saved Searches and Tracked Lots on mobile
- Оновлено `frontend/src/{App.tsx,styles.css}`: додано mobile-layout detection для dashboard і стилі для panel header actions / collapse toggles, щоб мобільні секції можна було згортати без впливу на desktop layout.
- Оновлено `frontend/src/features/{search/SearchPanel.tsx,watchlist/WatchlistPanel.tsx}`: `Saved Searches` і `Tracked Lots` тепер мають mobile-only toggle-кнопки з `aria-expanded` / `aria-controls`, а їхній вміст можна сховати або повернути назад без втрати внутрішнього стану панелей.
- Оновлено `frontend/tests/app.test.tsx`: додано regression coverage для mobile viewport, що обидві секції коректно collapse/expand.

## [2026-03-25 17:30] Tighten IAAI bootstrap hardening plan after review
- Переглянуто `docs/plans/20260325-iaai-gateway-bootstrap-hardening.md` проти поточного `iaai_provider`, `iaai_gateway` і `provider_connections` stack.
- Додано в план два пропущені напрями: end-to-end correlation між AWS backend і NAS gateway для step-level діагностики та явне рішення щодо використання `client_ip` у IAAI replay flow.
- Розширено task scope файлами `backend/src/cartrap/modules/iaai_gateway/schemas.py` і `backend/src/cartrap/modules/provider_connections/router.py`, а також тестовою стратегією для correlation-id propagation і `client_ip` behavior.

## [2026-03-25 17:19] Add follow-up plan for IAAI gateway bootstrap hardening
- Додано `docs/plans/20260325-iaai-gateway-bootstrap-hardening.md`: окремий follow-up план під production blocker після успішного ввімкнення `iaai-gateway`.
- Зафіксовано поточний стан: `AWS backend -> iaai-gateway` transport уже працює, а незакритий ризик зводиться до Imperva/browser replay після `GET /Identity/Account/Login`.
- План розбиває роботу на step-level diagnostics, Imperva preflight replay, browser-like login/callback hardening, post-bootstrap lifecycle verification і rollout docs.

## [2026-03-25 16:31] Add iaai-gateway Docker Compose service
- Оновлено `docker-compose.yml`: додано окремий `iaai-gateway` service під profile `gateway`, який використовує той самий backend image, але стартує з `APP_MODULE=cartrap.iaai_gateway_app:app` і слухає `IAAI_GATEWAY_PORT` (за замовчуванням `8020`).
- Це синхронізує локальний/NAS deployment із уже доданим IAAI gateway code path і дозволяє піднімати `copart-gateway` та `iaai-gateway` незалежно, не змішуючи їх у одному контейнері.

## [2026-03-25 16:27] Add dedicated NAS IAAI gateway path
- Оновлено `backend/src/cartrap/config.py`, `backend/src/cartrap/modules/iaai_provider/client.py` і додано `backend/src/cartrap/modules/iaai_gateway/{schemas.py,service.py,router.py}` разом із `backend/src/cartrap/iaai_gateway_app.py`: backend тепер має окремий additive `IAAI_GATEWAY_*` transport mode, а для NAS з’явився окремий IAAI gateway app з proxy `search/lot-details` і connector `bootstrap/verify/execute` flow, щоб винести IAAI egress з AWS backend та не чіпати існуючий Copart gateway docker.
- Додано regression coverage в `backend/tests/iaai/{test_gateway_client_config.py,test_gateway_router.py,test_gateway_connector_flow.py}`: перевірено config switch, bearer-auth gateway routing, encrypted session bundle round-trip і mapping `invalid_credentials` / `auth_invalid` / `upstream_rejected` для IAAI connector flow.
- Оновлено `.env.example`, `README.md` і `docs/plans/20260325-iaai-multi-auction-support.md`: додано нові `IAAI_GATEWAY_*` / `IAAI_CONNECTOR_ENCRYPTION_KEY` env keys, окремий `cartrap.iaai_gateway_app:app` entrypoint для NAS deploy і зафіксовано рішення вести IAAI через dedicated gateway через Imperva/WAF блокування AWS direct bootstrap.

## [2026-03-25 16:14] Make watchlist lot-key index rollout safe for legacy Mongo rows
- Оновлено `backend/src/cartrap/modules/watchlist/repository.py`: перед створенням unique індексу `owner_user_id + lot_key` backend тепер backfill-ить legacy `tracked_lots` поля `provider`, `auction_label`, `provider_lot_id`, `lot_key`, а сам індекс створює як partial для string-valued `lot_key`, щоб старі записи з `null` більше не валили `/api/watchlist`.
- Додано `backend/tests/watchlist/test_repository.py`: regression coverage перевіряє прод-сценарій із кількома legacy rows `lot_key = null` для одного owner, а також toleration для зовсім зламаних legacy документів без `lot_number/provider_lot_id`.

## [2026-03-25 16:08] Complete IAAI multi-auction implementation
- Оновлено backend multi-auction domain і provider stack: додано `backend/src/cartrap/modules/auction_domain/models.py`, `backend/src/cartrap/modules/iaai_provider/{client.py,errors.py,models.py,normalizer.py,service.py}`, розширено `backend/src/cartrap/config.py`, `backend/src/cartrap/modules/provider_connections/{models.py,schemas.py,service.py,router.py}`, `backend/src/cartrap/modules/search/{schemas.py,repository.py,router.py,service.py}`, `backend/src/cartrap/modules/watchlist/{schemas.py,repository.py,router.py,service.py}` і `backend/src/cartrap/modules/monitoring/service.py`, щоб CarTrap підтримував Copart + IAAI через спільні `provider/provider_lot_id/lot_key` contracts, mixed-provider search merge, provider-aware watchlist identity й provider-level diagnostics.
- Оновлено frontend multi-provider UX у `frontend/src/{App.tsx,types.ts,lib/api.ts}`, `frontend/src/features/search/{ManualSearchScreen.tsx,SearchPanel.tsx,SearchResultsModal.tsx}`, `frontend/src/features/watchlist/WatchlistPanel.tsx`, `frontend/src/features/dashboard/AccountMenuSheet.tsx`, `frontend/src/features/integrations/{CopartConnectionCard.tsx,ProviderConnectionCard.tsx}`: додано IAAI connector, provider selection у manual search, auction badges/source pills, provider-aware add-to-watchlist flows і generalized blocking copy для Copart/IAAI.
- Додано/розширено тестове покриття в `backend/tests/auction_domain/test_models.py`, `backend/tests/iaai/{test_http_client.py,test_normalizer.py}`, `backend/tests/provider_connections/test_iaai_router.py`, `frontend/tests/app.test.tsx`; оновлено `docs/backend-api.md`, `docs/database-schema.md` і `docs/plans/20260325-iaai-multi-auction-support.md` під нові provider-aware API/schema contracts і фінальний статус плану.
- Verification: `./.venv/bin/pytest backend/tests/provider_connections/test_router.py backend/tests/provider_connections/test_iaai_router.py backend/tests/search/test_search_api.py backend/tests/watchlist/test_watchlist_api.py backend/tests/monitoring/test_change_detection.py backend/tests/test_worker_main.py backend/tests/auction_domain/test_models.py backend/tests/iaai/test_normalizer.py backend/tests/iaai/test_http_client.py -q`, `npm --prefix frontend run test -- --run tests/app.test.tsx`, `npm --prefix frontend run build`.

## [2026-03-25 15:12] Tighten IAAI plan around catalog and provider-aware add flows
- Переперевірено план `docs/plans/20260325-iaai-multi-auction-support.md` проти поточних `search/catalog`, `ManualSearchScreen`, `AddFromSearchRequest` і watchlist contracts; додано явні пункти про те, що каталог і manual-search UX зараз Copart-only на рівні даних, а не лише копірайту.
- Доповнено план окремими задачами для provider-aware search catalog strategy, еволюції saved-search `connection_diagnostic` / `external_url` у multi-provider contract, а також для зміни `/search/watchlist` і `/watchlist` payload-ів з `lot_url` на provider-aware identifiers, щоб IAAI add-from-search не блокувався через відсутність підтвердженого deep link.

## [2026-03-25 14:26] Plan IAAI multi-auction integration
- Проаналізовано `Temp/Login-flow-iaai` разом із поточними `provider_connections`, search, watchlist і frontend surfaces; зафіксовано, що IAAI flow базується на OIDC/PKCE, bearer + refresh token, mobile headers і inventory-centric identifiers (`id`, `stockNumber`, `itemId`), а не на Copart-style session bundle only.
- Створено план `docs/plans/20260325-iaai-multi-auction-support.md`: описано рекомендовану multi-auction архітектуру, normalization contract для `provider` / `provider_lot_id` / `lot_key`, refactor saved-search/watchlist uniqueness away from plain `lot_number`, додавання IAAI connector у PWA settings і відображення auction source у saved-search/watchlist rows.

## [2026-03-24 17:35] Implement per-user Copart connector end-to-end
- Оновлено backend для user-scoped Copart session bundles: додано модуль `provider_connections`, нові `/api/provider-connections` endpoints, gateway bootstrap/verify/execute contract, шифрування bundle через `COPART_CONNECTOR_ENCRYPTION_KEY`, а також інтеграцію search/watchlist/worker flows з `connection_missing` і `reconnect_required` без деградації глобального `live_sync`.
- Оновлено frontend connector UX у `frontend/src/{App.tsx,lib/api.ts,types.ts,styles.css}`, `frontend/src/features/{dashboard/AccountMenuSheet.tsx,integrations/CopartConnectionCard.tsx,search/{ManualSearchScreen.tsx,SearchPanel.tsx,SearchResultsModal.tsx},watchlist/WatchlistPanel.tsx}` і `frontend/tests/app.test.tsx`: додано connect/reconnect/disconnect surface, account-level reconnect notice, resource-level diagnostics і guarded live actions для saved searches/watchlist.
- Оновлено документацію й execution artifacts: синхронізовано `README.md`, `docs/backend-api.md`, план `docs/plans/completed/20260324-copart-per-user-connector-v1.md`; verification: `./.venv/bin/pytest backend/tests/provider_connections/test_repository.py backend/tests/provider_connections/test_router.py backend/tests/copart/test_http_client.py backend/tests/copart/test_gateway_router.py backend/tests/copart/test_gateway_connector_flow.py backend/tests/search/test_search_api.py backend/tests/watchlist/test_watchlist_api.py backend/tests/monitoring/test_change_detection.py backend/tests/test_worker_main.py backend/tests/test_config.py` -> `79 passed`, `npm --prefix frontend run test -- app.test.tsx` -> `49 passed`, `npm --prefix frontend run build` -> успішно.

## [2026-03-21 17:25] Fix watchlist ordering to follow auction date instead of update time
- Оновлено `backend/src/cartrap/modules/watchlist/{repository.py,service.py}` і `backend/tests/watchlist/test_watchlist_api.py`: watchlist більше не сортується за `has_unseen_update/latest_change_at`; items тепер стабільно впорядковуються за найближчим `sale_date` угору, а regression test перевіряє, що unseen update не підкидає пізніший аукціон на верх списку.
- Оновлено `frontend/src/App.tsx` і `frontend/tests/app.test.tsx`: додано єдине локальне сортування watchlist по `sale_date`, яке застосовується і після reload, і після add-to-watchlist flows, щоб UI не показував тимчасово неправильний порядок під час refresh/add.

## [2026-03-19 16:24] Add completed-state affordance after search result is tracked
- Оновлено `frontend/src/{App.tsx,styles.css}` і `frontend/src/features/search/{SearchPanel.tsx,SearchResultsModal.tsx}`: add-to-watchlist CTA у results rows тепер переходить з `+` у completed-state `✓`, блокує повторне додавання для вже tracked lot URLs і показує success-повідомлення в модалці після успішного add.
- Оновлено `frontend/tests/app.test.tsx`: додано assertion на disabled completed-state button і success message після додавання лота з search results.

## [2026-03-19 16:16] Add explicit lot-open link and plus affordance in search rows
- Оновлено `frontend/src/features/search/SearchResultsModal.tsx` і `frontend/src/styles.css`: у results rows назва лоту тепер відкриває Copart lot page в новій вкладці, а add-to-watchlist CTA змінено зі стрілки на `+`, щоб дія читалась як додавання, а не навігація.
- Оновлено `frontend/tests/app.test.tsx`: додано assertion на зовнішнє lot-link посилання в search results.

## [2026-03-19 16:08] Format search odometer from Copart reading fields and soften list emphasis
- Оновлено `backend/src/cartrap/modules/copart_provider/normalizer.py` і `backend/tests/copart/test_api_normalizer.py`: search-result odometer тепер формується з `odometer_reading_received` та `odometer_brand_calculated` / `odometer_reading_desc`, щоб у list results приходили значення на кшталт `347 N`, а не порожнє `N/A`.
- Оновлено `frontend/src/styles.css`: зменшено візуальну вагу назви лоту і countdown/timer у rows search results, щоб mobile list був ближчий до референсу й не виглядав надмірно жирним.

## [2026-03-19 15:51] Force stable lot thumbnail ratio in results rows
- Оновлено `frontend/src/styles.css`: thumbnail у search-result rows тепер має явні width/height і `object-fit: cover`, щоб на реальному мобільному девайсі не ламався в портретну геометрію через intrinsic image ratio.
- Оновлено `backend/src/cartrap/modules/copart_provider/normalizer.py`: parse odometer для search docs розширено додатковими варіантами ключів навколо `odometer_reading_received`, щоб не втрачати значення через дрібні відмінності payload shape.

## [2026-03-19 15:39] Tighten results modal mobile fit and restore odometer from search payload
- Оновлено `frontend/src/features/search/SearchResultsModal.tsx` і `frontend/src/styles.css`: saved-search results modal тепер стабільно входить у mobile fullscreen на вузьких екранах навіть якщо `pointer: coarse` не спрацював, а lot rows і topbar ущільнено під реальний `390px` viewport після prod smoke-check.
- Оновлено `backend/src/cartrap/modules/copart_provider/normalizer.py` і `backend/tests/copart/test_api_normalizer.py`: search-result odometer тепер також читається з ключа `odometer_reading_received`, який приходить у продакшен search docs.
- Оновлено `frontend/tests/app.test.tsx`: додано regression test для fullscreen saved-search results на вузькому viewport без coarse-pointer detection.

## [2026-03-19 12:15] Restyle search-result lot rows to match reference mobile list
- Оновлено `frontend/src/features/search/SearchResultsModal.tsx`, `frontend/src/styles.css` і `frontend/src/types.ts`: список лотів у search results перебудовано з card-layout у щільний mobile-first list pattern зі скріншота; рядок тепер має thumbnail зліва, title/lot/location/odo по центру, bid-or-live/timer/buy-now сигнал справа і chevron-style add-to-watchlist CTA без змін верхнього chrome модалки.
- Оновлено `backend/src/cartrap/modules/copart_provider/{models.py,normalizer.py}`, `backend/tests/copart/test_api_normalizer.py` і `backend/tests/search/test_search_api.py`: search-result payload розширено полями `odometer`, `buy_now_price` і `raw_status`, щоб новий list layout міг показувати ту саму ключову інформацію по лоту, що й reference.
- Оновлено `frontend/tests/app.test.tsx`: assertions синхронізовано з новим search-results row contract.

## [2026-03-19 11:38] Add mobile pull-to-refresh for dashboard data
- Оновлено `frontend/src/App.tsx`, `frontend/src/features/dashboard/DashboardShell.tsx` і `frontend/src/styles.css`: додано mobile-only `pull to refresh` для dashboard через touch gesture від верхнього краю, з resistance/threshold логікою, top indicator, safe reset стану та перевикористанням існуючого dashboard reload flow без впливу на desktop.
- Оновлено `frontend/tests/app.test.tsx`: додано сценарій для мобільного `pull to refresh`, лічильники повторного завантаження dashboard resources і винесено стабільний helper для login-submit у jsdom, щоб verification не залежав від browser validation поведінки.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `27 passed`; `npm run build --prefix frontend` -> успішно.

## [2026-03-18 15:49] Apply premium finish and close dashboard polish implementation
- Оновлено `frontend/src/features/{dashboard/DashboardShell.tsx,search/SearchPanel.tsx,watchlist/WatchlistPanel.tsx,admin/AdminInvitesPanel.tsx,admin/AdminSearchCatalogPanel.tsx,push/PushSettingsModal.tsx}` та `frontend/src/styles.css`: dashboard surfaces, badges, pills, support cards і settings modal зведено до більш єдиної premium visual language без зміни runtime contract.
- Оновлено planning artifacts: `docs/plans/20260318-dashboard-density-urgency-premium-polish.md` синхронізовано з фактичним execution, зафіксовано блокер ручного headed smoke-check через недоступний локальний API (`127.0.0.1:8000`), після чого план перенесено в `docs/plans/completed/20260318-dashboard-density-urgency-premium-polish.md`.
- Verification: `npm run test --prefix frontend` -> `26 passed`; `npm run build --prefix frontend` -> успішно.

## [2026-03-18 15:43] Make watchlist urgency the dominant signal
- Оновлено `frontend/src/features/watchlist/WatchlistPanel.tsx`, `frontend/src/features/shared/LotThumbnail.tsx` і `frontend/src/styles.css`: sale timing винесено в головний top-row сигнал, watchlist cards отримали urgency-tier surfaces (`today/soon/live`), тихіші `Show details` / `Remove`, компактніший intake row, менші KPI boxes і щільніший thumbnail/gallery affordance.
- Оновлено `frontend/tests/app.test.tsx`: додано окремий сценарій для `Auction live`, зберігши попереднє покриття `Sale soon`, updated cards і disclosure flow.
- Оновлено `docs/plans/20260318-dashboard-density-urgency-premium-polish.md`: `Task 3` позначено виконаним після зеленого test pass.
- Verification: `npm run test --prefix frontend` -> `26 passed`.

## [2026-03-18 15:41] Compact search workflow and align modal density
- Оновлено `frontend/src/features/search/{SearchPanel.tsx,SearchResultsModal.tsx,SearchFiltersModal.tsx}` і `frontend/src/styles.css`: форма пошуку стала щільнішою, `Filters` отримав явний active-count badge, saved-search cards зібрано в компактніший action/meta layout, а filters/results modal toolbar/footer приведено до того ж density rhythm.
- Оновлено `frontend/tests/app.test.tsx`: додано assertion на доступну назву `Filters (6 active)` після застосування modal filters, не змінюючи решту saved-search/search contracts.
- Оновлено `docs/plans/20260318-dashboard-density-urgency-premium-polish.md`: `Task 2` позначено виконаним після зеленого test pass.
- Verification: `npm run test --prefix frontend` -> `25 passed`.

## [2026-03-18 15:38] Tighten dashboard chrome and top-level density
- Оновлено `frontend/src/features/dashboard/DashboardShell.tsx`, `frontend/src/App.tsx` і `frontend/src/styles.css`: hero/user card стали щільнішими, support-панелі винесено в тихіший нижній lane, а глобальні spacing/button/input tokens піджато для більш операційного first screen.
- Оновлено `frontend/tests/app.test.tsx`: додано top-level assertion-и на `User summary` та порядок main/support panels після логіну.
- Оновлено `docs/plans/20260318-dashboard-density-urgency-premium-polish.md`: `Task 1` позначено виконаним після зеленого test pass.
- Verification: `npm run test --prefix frontend` -> `25 passed`.

## [2026-03-18 15:33] Tighten polish plan around filters modal, watchlist intake, and support surfaces
- Оновлено `docs/plans/20260318-dashboard-density-urgency-premium-polish.md`: план розширено явним покриттям для `SearchFiltersModal`, compacting `Add by Lot Number` intake row у watchlist, а також consistency-pass для admin/settings surfaces, щоб second-pass polish не лишив візуально чужі ділянки в dashboard.
- Planning scope став менш двозначним перед наступною імплементацією.

## [2026-03-18 15:30] Add follow-up dashboard polish plan for density, urgency, and premium finish
- Додано `docs/plans/20260318-dashboard-density-urgency-premium-polish.md`: оформлено follow-up implementation plan на наступний visual/UX pass після щойно реалізованого search/watchlist refresh, з окремими задачами для density polish, urgency-first watchlist і premium visual finish.
- Цей цикл обмежено planning/documentation scope без runtime-змін.

## [2026-03-18 15:01] Implement search/watchlist UI hierarchy refresh
- Оновлено `frontend/src/{App.tsx,styles.css}`: `Search` і `Watchlist` піднято як primary workflows у dashboard grid, введено сильніший visual hierarchy для карток, кнопок, summary bars і responsive stacking без зміни backend contract.
- Оновлено `frontend/src/features/search/{SearchPanel.tsx,SearchResultsModal.tsx}`: manual search тепер має один домінантний action flow, compact criteria summary bar, а saved-search cards отримали явні primary/secondary actions з кращою scanability.
- Оновлено `frontend/src/features/{watchlist/WatchlistPanel.tsx,shared/LotThumbnail.tsx}`: tracked lot cards стали compact-first, додано disclosure для другорядних деталей, urgency badges (`Auction live` / `Sale soon` / `Today`), тихіші destructive actions і більший thumbnail contract для watchlist.
- Оновлено `frontend/tests/app.test.tsx` під новий DOM/UI contract, додано покриття для details toggle та near-auction urgency state.
- Оновлено planning artifacts: `docs/plans/completed/20260318-search-watchlist-ui-ux-refresh.md` синхронізовано з фактичним execution і перенесено в completed.
- Verification: `npm run test --prefix frontend` -> `24 passed`; `npm run build --prefix frontend` -> успішно.

## [2026-03-18 14:53] Tighten UI-UX refresh plan around watchlist urgency and shared thumbnail scope
- Оновлено `docs/plans/completed/20260318-search-watchlist-ui-ux-refresh.md`: у план додано явне покриття для `frontend/src/features/shared/LotThumbnail.tsx`, зафіксовано потребу визначити source of truth для watchlist urgency tiers і розширено manual verification під near-auction сценарії.
- План став менш двозначним для реалізації compact watchlist card без drift між frontend urgency UX і backend near-auction логікою.

## [2026-03-18 14:49] Add implementation plan for search/watchlist UI-UX refresh
- Додано `docs/plans/completed/20260318-search-watchlist-ui-ux-refresh.md`: зафіксовано discovery-контекст, рекомендований hierarchy-first підхід і покроковий implementation plan для оновлення `Search`, `Watchlist`, visual system, responsive/accessibility polish та verification.
- Цикл змін обмежено planning/documentation scope без змін runtime-коду.

## [2026-03-18 14:27] Add auction reminder pushes and switch near-auction window config to minutes
- Оновлено `backend/src/cartrap/modules/{monitoring/service.py,notifications/service.py,watchlist/service.py}`: worker тепер надсилає одноразові watchlist push-нагадування за 60 хв, 15 хв і в момент старту аукціону, з persisted marker-ами в `tracked_lots`, щоб reminder-и не дублювалися між poll cycles та коректно скидалися при зміні `sale_date`.
- Оновлено `backend/src/cartrap/{config.py,worker/main.py}` і `backend/src/cartrap/modules/monitoring/polling_policy.py`: near-auction window переведено з `WATCHLIST_NEAR_AUCTION_WINDOW_HOURS` на `WATCHLIST_NEAR_AUCTION_WINDOW_MINUTES` із хвилинним контрактом по всьому runtime.
- Оновлено `backend/tests/{monitoring/test_change_detection.py,monitoring/test_polling_policy.py,notifications/test_push_delivery.py,test_config.py}`, `README.md`, `.env`, `.env.example` і `docs/database-schema.md` під нові reminder flows та minute-based config.

## [2026-03-17 16:02] Tighten lot-change push copy for minimal informative text
- Оновлено `backend/src/cartrap/modules/notifications/service.py`: title lot-change push тепер має більш компактний формат `<title> (<lot_number>)`, а body скорочено до мінімалістичного diff без зайвого повтору валюти, наприклад `Status: Upcoming -> Live; Bid: 1,000 -> 1,800 USD`.
- Оновлено `backend/tests/notifications/test_push_delivery.py` під новий copy contract.

## [2026-03-17 15:58] Prioritize updated watchlist lots and enrich lot-change push copy
- Оновлено `backend/src/cartrap/modules/{watchlist/schemas.py,watchlist/repository.py,watchlist/service.py,monitoring/service.py,notifications/service.py}`: watchlist items тепер мають `has_unseen_update`/`latest_change*` metadata, `GET /watchlist` повертає лоти з непрочитаними оновленнями першими та очищає marker після перегляду, а lot-change push notification тепер починається з назви лота й містить значення змін (`Status`, `Current bid`, `Sale date` тощо).
- Оновлено `frontend/src/{types.ts,styles.css}` і `frontend/src/features/watchlist/WatchlistPanel.tsx`: card з оновленням тепер має виразний accent state, `Updated` badge і change summary callout з деталями diff прямо в списку.
- Оновлено `backend/tests/{watchlist/test_snapshot_storage.py,watchlist/test_watchlist_api.py,monitoring/test_change_detection.py,notifications/test_push_delivery.py}`, `frontend/tests/app.test.tsx` і `docs/backend-api.md` під новий watchlist/push contract.

## [2026-03-17 15:25] Move saved-search and watchlist refresh cadence to env config
- Оновлено `backend/src/cartrap/{config.py,app.py,worker/main.py}`: додано env-driven settings для періодичності polling saved searches і watchlist lots, а runtime створення сервісів тепер підхоплює ці значення з `.env`.
- Оновлено `backend/src/cartrap/modules/{search/service.py,search/router.py,admin/router.py,monitoring/service.py,monitoring/polling_policy.py}`: прибрано жорстко зашиті інтервали, saved-search polling і adaptive watchlist polling тепер працюють через конфігуровані значення.
- Оновлено `.env`, `.env.example`, `README.md` і backend-тести (`backend/tests/test_config.py`, `backend/tests/monitoring/test_polling_policy.py`, `backend/tests/search/test_saved_search_monitoring.py`) під новий env contract.
- Verification: `./.venv/bin/pytest backend/tests/test_config.py` -> `4 passed`, `./.venv/bin/pytest backend/tests/monitoring/test_polling_policy.py` -> `3 passed`, `./.venv/bin/pytest backend/tests/search/test_saved_search_monitoring.py` -> `7 passed`, `./.venv/bin/pytest backend/tests/monitoring/test_change_detection.py` -> `5 passed`, `./.venv/bin/pytest backend/tests/test_worker_main.py` -> `3 passed`, `./.venv/bin/pytest backend/tests/test_app_boot.py` -> `4 passed` (усюди лишився лише `urllib3` warning про локальний LibreSSL).

## [2026-03-17 14:58] Restrict push diagnostics visibility to admin accounts
- Оновлено `frontend/src/{App.tsx}` і `frontend/src/features/push/PushSettingsModal.tsx`: test push, retry diagnostics і розширений diagnostics block (`browser support`, `secure context`, `server config`, `current device`) тепер відображаються лише для `admin` акаунтів, тоді як звичайні користувачі бачать тільки власний push management (`permission`, `subscriptions`, `enable/revoke`).
- Оновлено `frontend/tests/app.test.tsx`: додано окремий сценарій для non-admin user, який перевіряє, що admin-only push diagnostics не рендеряться в settings modal.

## [2026-03-17 14:50] Implement PWA UX polish for search, watchlist, push, and admin flows
- Оновлено `frontend/src/{App.tsx,styles.css,types.ts}` і додано `frontend/src/features/shared/AsyncStatus.tsx`: введено shared async-status primitives, granular bootstrap/action pending states, panel-level retry для partial load failures, browser offline tracking і окреме UX-розділення між device offline та backend live-sync degraded mode.
- Оновлено `frontend/src/features/search/{SearchPanel.tsx,SearchResultsModal.tsx}` і `frontend/src/features/watchlist/WatchlistPanel.tsx`: manual search, saved-search cache flow і watchlist mutations тепер мають явні loading/success/error states, disabled/busy semantics, кращу metadata clarity (`freshness`, `last checked`, `last synced`) і non-blocking refresh UX із збереженням уже завантажених даних.
- Оновлено `frontend/src/features/push/PushSettingsModal.tsx` та `frontend/src/features/admin/{AdminInvitesPanel.tsx,AdminSearchCatalogPanel.tsx}`: додано push diagnostics (`support`, `secure context`, `permission`, `server config`, `current device`), `Send Test Push`, покращений subscription list, copy-invite affordance, expiry visibility, catalog refresh feedback і support-friendly success/error messaging.
- Оновлено `frontend/src/features/dashboard/DashboardShell.tsx`: dashboard тепер показує окремий offline banner для браузера/девайса, компактний bootstrap progress і зберігає live-sync degraded banner як окремий сценарій.
- Оновлено `frontend/tests/app.test.tsx`: додано покриття для partial bootstrap retry, push test diagnostics, browser-offline messaging та оновлено assertions під новий UX contract.
- Оновлено `docs/plans/completed/20260317-pwa-ux-polish-flows.md`: усі tasks позначено виконаними, план перенесено в `docs/plans/completed/`.
- Verification: `npm run test --prefix frontend` -> `21 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-17 12:11] Add 6-week product roadmap document
- Додано `output/doc/cartrap-6-week-roadmap.docx` з 6-тижневим roadmap для CarTrap, що спирається на поточний стан репозиторію: завершений MVP, cached saved-search flow, NAS-backed `copart-gateway` split, degraded/offline UX і наявні deployment constraints.
- У roadmap окремо винесено milestones, тижневий план `Week 1-6`, явні dependencies і key risks, з фокусом на production hardening, observability, automated regression safety, release automation і beta rollout замість великого net-new feature scope.
- Структуру документа перевірено через зворотне читання `.docx`; візуальний render-to-image check не виконано, бо в середовищі відсутні `soffice` і `pdftoppm`.

## [2026-03-16 18:42] Add plan for cached saved-search run flow
- Додано `docs/plans/20260316-saved-search-cache-run-search.md` з планом переходу saved searches на Mongo-backed results cache: seed cache під час `Save Search`, cached `Run Search`, `Refresh Live` всередині modal і `NEW` badge для лотів, що з’явилися після останнього перегляду.
- У плані окремо розписано backend cache persistence, worker diff logic для `new_lot_numbers`, нові API endpoints для `view`/`refresh-live`, frontend modal/list UX і обов’язкове тестове покриття для backend та frontend flows.

## [2026-03-16 17:39] Add push delivery diagnostics and worker logging bootstrap
- Оновлено `backend/src/cartrap/modules/notifications/service.py`: додано явні structured logs для push delivery path, включно з warning при відсутньому sender, логами успішної доставки, причиною `PushDeliveryError`, а також повідомленням про автоматичне видалення subscription після unrecoverable failure.
- Оновлено `backend/src/cartrap/worker/main.py`: worker тепер викликає `configure_logging(settings.log_level)` на старті, тож результати polling cycle і push delivery failures більше не губляться в порожніх `docker compose logs worker`.

## [2026-03-16 17:14] Add private Synology NAS gateway administration runbook
- Додано приватний `docs/private/nas-synology-gateway-admin.md` з окремим runbook для Synology DS723+ gateway deployment: NIC.UA DNS піддомен `copart-gw`, DSM Reverse Proxy/Let's Encrypt, `Container Manager`, стандартні deploy/update команди для `docker compose --profile gateway` і щоденні health/log checks.
- У runbook окремо задокументовано продакшн-мережеву специфіку поточного setup: співіснування з `currex.pp.ua` на тих самих `80/443`, внутрішній gateway порт `8010`, заборону прямого публічного expose `8010`, а також troubleshooting для hairpin NAT, `405` на `HEAD /health`, gateway degraded mode і rotation для `COPART_GATEWAY_TOKEN` / `COPART_API_*`.

## [2026-03-16 13:27] Close NAS gateway split implementation plan
- Оновлено `docs/plans/completed/20260316-nas-copart-gateway-split.md`: фінальні Task 7/8 checkboxes позначено виконаними після повного backend/frontend verification, а сам план перенесено з `docs/plans/` у `docs/plans/completed/`.
- Verification closure для цього циклу спирається на вже прогнані команди: `./.venv/bin/pytest backend/tests` -> `124 passed`, `npm run test --prefix frontend` -> `16 passed`, `npm run build --prefix frontend` -> успішно, `docker compose --profile gateway config` -> успішно.

## [2026-03-16 13:24] Document split deployment and add compose gateway profile
- Оновлено `README.md`, `backend/README.md` і `.env.example`: задокументовано split deployment model (`AWS backend + worker + Mongo` та окремий `NAS copart-gateway`), required gateway env vars, bearer auth, gzip/keep-alive expectations, відсутність direct fallback і локальний запуск `uvicorn cartrap.gateway_app:app`.
- Оновлено `docker-compose.yml`: додано optional service `copart-gateway` через profile `gateway`, який перевикористовує той самий backend image і запускається через `APP_MODULE=cartrap.gateway_app:app`.
- Verification: `docker compose --profile gateway config` -> успішно; compose-конфіг валідно рендериться з новим `copart-gateway` service.

## [2026-03-16 13:24] Add frontend degraded-mode banner and live-sync refresh flow
- Оновлено `frontend/src/{App.tsx,types.ts}` і `frontend/src/lib/api.ts`: frontend тепер читає `/api/system/status`, тримає окремий `liveSyncStatus`, оновлює його на bootstrap і після live Copart actions (`search`, `add to watchlist`, `add from search`, `catalog refresh`), а HTTP client дістає `detail` з backend JSON errors замість показу сирого JSON рядка.
- Оновлено `frontend/src/features/dashboard/DashboardShell.tsx` і `frontend/src/styles.css`: додано помітний degraded/offline banner з останнім sync/failure контекстом; cached Mongo-backed data продовжує рендеритись, а UI не блокується повністю.
- Оновлено `frontend/tests/app.test.tsx`: додано покриття для banner render/recovery path і user-visible degraded-mode messaging, коли manual search або додавання lot у watchlist падають через live sync outage.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `16 passed`; `npm run test --prefix frontend` -> `16 passed`; `npm run build --prefix frontend` -> успішно.

## [2026-03-16 13:14] Persist backend live-sync status and close gateway routing groundwork
- Додано `backend/src/cartrap/modules/system_status/{repository.py,service.py}` і розширено `backend/src/cartrap/api/system.py`: з’явився Mongo-backed shared live-sync status (`/api/system/status`), який відділяє `status=ok` від `live_sync.status=available|degraded`, повертає останні success/failure timestamps/sources і вміє трактувати застарілий failure marker як `stale`.
- Оновлено `backend/src/cartrap/modules/{search/service.py,monitoring/service.py}` та `backend/src/cartrap/worker/main.py`: manual search, catalog refresh, saved-search polling, watchlist polling і worker-level transient exceptions тепер записують shared live-sync state в Mongo, замість покладатися на in-memory стан окремого процесу.
- Додано `backend/tests/{test_system_status.py,test_worker_main.py}` і `backend/tests/copart/test_gateway_backed_services.py`: покрито `/api/system/status`, stale degraded marker, worker transient handling і реальні `SearchService` / `WatchlistService` / `MonitoringService` / `SearchCatalogRefreshJob` сценарії поверх `CopartProvider` + gateway transport + raw gateway JSON.
- Verification: `./.venv/bin/pytest backend/tests/test_system_status.py backend/tests/test_worker_main.py backend/tests/test_app_boot.py` -> `12 passed`; `./.venv/bin/pytest backend/tests/copart/test_gateway_backed_services.py backend/tests/copart/test_gateway_client_config.py backend/tests/search/test_search_api.py backend/tests/watchlist/test_watchlist_api.py backend/tests/monitoring/test_change_detection.py backend/tests/search/test_saved_search_monitoring.py` -> `54 passed`; `./.venv/bin/pytest backend/tests` -> `124 passed` (залишився лише `urllib3` warning про локальний LibreSSL).

## [2026-03-16 13:06] Wire gateway search-count path and add degradation regressions
- Оновлено `backend/src/cartrap/modules/copart_provider/{client.py,service.py}` і `backend/src/cartrap/modules/copart_gateway/service.py`: додано окремий `search_count_with_metadata()` transport path, тож AWS-side saved-search polling тепер може використовувати dedicated gateway endpoint `/v1/search-count`, а не загальний `/v1/search`.
- Розширено backend regression coverage в `backend/tests/{copart/test_gateway_client_config.py,search/test_search_api.py,search/test_saved_search_monitoring.py,watchlist/test_watchlist_api.py,monitoring/test_change_detection.py}`: перевірено dedicated `/v1/search-count` routing, відсутність direct fallback при `CopartGatewayUnavailableError`, і те, що search/watchlist/monitoring polling деградує у контрольований failure state без крашу worker-side flows.
- Verification: `./.venv/bin/pytest backend/tests/copart/test_http_client.py backend/tests/copart/test_gateway_client_config.py backend/tests/copart/test_gateway_router.py backend/tests/search/test_search_api.py backend/tests/search/test_saved_search_monitoring.py backend/tests/watchlist/test_watchlist_api.py backend/tests/monitoring/test_change_detection.py backend/tests/test_config.py backend/tests/test_app_boot.py backend/tests/test_import_smoke.py` -> `75 passed` (залишився лише `urllib3` warning про локальний LibreSSL).

## [2026-03-16 13:00] Add NAS gateway app skeleton and raw Copart proxy routes
- Додано `backend/src/cartrap/{gateway_app.py}` і `backend/src/cartrap/modules/copart_gateway/{schemas.py,service.py,router.py}`: з’явився окремий FastAPI entrypoint для NAS `copart-gateway` з bearer-protected endpoint-ами `POST /v1/search`, `POST /v1/search-count`, `POST /v1/lot-details`, `GET /v1/search-keywords`, raw JSON passthrough, підтримкою `If-None-Match`/`ETag` і явним mapping для `upstream_rejected`, `unavailable`, `malformed_response`.
- Оновлено `backend/src/cartrap/config.py`, `backend/tests/copart/test_gateway_client_config.py` і `backend/src/cartrap/modules/copart_provider/{client.py,errors.py}`: `COPART_GATEWAY_TOKEN` тепер може існувати без `COPART_GATEWAY_BASE_URL` для NAS runtime, при цьому AWS-side gateway mode вмикається лише за наявності `base_url`; transport foundation з попереднього кроку лишається сумісною.
- Оновлено `backend/Dockerfile`: той самий image тепер можна запускати з різними app entrypoint через `APP_MODULE` (`cartrap.main:app` або `cartrap.gateway_app:app`) без окремого Dockerfile для NAS.
- Додано `backend/tests/copart/test_gateway_router.py` і прогнано verification: `./.venv/bin/pytest backend/tests/copart/test_http_client.py backend/tests/copart/test_gateway_client_config.py backend/tests/copart/test_gateway_router.py backend/tests/test_config.py` -> `31 passed`; `./.venv/bin/pytest backend/tests/test_app_boot.py backend/tests/test_import_smoke.py backend/tests/auth/test_login.py backend/tests/auth/test_invites.py backend/tests/auth/test_rbac.py backend/tests/search/test_search_api.py backend/tests/search/test_saved_search_monitoring.py backend/tests/watchlist/test_watchlist_api.py backend/tests/monitoring/test_change_detection.py` -> `46 passed` (залишився лише `urllib3` warning про локальний LibreSSL).

## [2026-03-16 12:28] Implement gateway-ready Copart transport foundation
- Оновлено `backend/src/cartrap/config.py`: додано gateway-related settings (`COPART_GATEWAY_BASE_URL`, `COPART_GATEWAY_TOKEN`, `COPART_GATEWAY_ENABLE_GZIP`) і transport/keep-alive tuning (`COPART_HTTP_*`), валідацію зв’язки `base_url/token`, а також сумісність `Settings(...)` з repo-тестами, які передають alias-поля через lowercase kwargs.
- Оновлено `backend/src/cartrap/modules/copart_provider/client.py` і додано `backend/src/cartrap/modules/copart_provider/errors.py`: `CopartHttpClient` перетворено на transport-aware facade з `DirectCopartTransport` і `GatewayCopartTransport`, shared `httpx.Client` pool для reusable keep-alive, gateway path constants і явне error mapping для unavailable/upstream_rejected/malformed-response сценаріїв.
- Додано `backend/tests/copart/test_gateway_client_config.py` і прогнано backend verification: `./.venv/bin/pytest backend/tests/copart/test_http_client.py backend/tests/copart/test_gateway_client_config.py backend/tests/test_config.py` -> `21 passed`; `./.venv/bin/pytest backend/tests/search/test_search_api.py backend/tests/search/test_saved_search_monitoring.py backend/tests/watchlist/test_watchlist_api.py backend/tests/monitoring/test_change_detection.py backend/tests/search/test_catalog_builder.py backend/tests/test_app_boot.py` -> `45 passed`; `./.venv/bin/pytest backend/tests/auth/test_login.py backend/tests/auth/test_invites.py backend/tests/auth/test_rbac.py backend/tests/notifications/test_push_subscriptions.py` -> `12 passed` (в усіх прогонах лишився лише `urllib3` warning про локальний LibreSSL).

## [2026-03-13 18:24] Show tracked lot auction start time in local browser timezone
- Оновлено `frontend/src/features/watchlist/WatchlistPanel.tsx`: поле `Sale` у `Tracked Lots` тепер показує не лише дату, а локальний `date + time` старту аукціону через browser `Intl.DateTimeFormat`, використовуючи вже наявний `sale_date` timestamp.
- Оновлено `frontend/tests/app.test.tsx`: додано regression check, що tracked lot card рендерить локальний час старту аукціону для lot із заповненим `sale_date`.

## [2026-03-13 18:14] Add ETag-based conditional polling for lot details and saved searches
- Оновлено `backend/src/cartrap/modules/copart_provider/{client.py,models.py,service.py}`: додано conditional fetch через `If-None-Match` для `search` і `lot_details`, з підтримкою `304 Not Modified` та поверненням актуального `ETag`.
- Оновлено `backend/src/cartrap/modules/{watchlist/service.py,monitoring/service.py,search/{repository.py,service.py}}`: `tracked_lots` тепер кешують `detail_etag`, `saved_searches` кешують `search_etag`, а worker-side polling використовує `ETag`, щоб не обробляти важкий payload, коли Copart повертає `304`.
- Оновлено `backend/tests/{copart/test_http_client.py,monitoring/test_change_detection.py,search/test_saved_search_monitoring.py,test_search_api.py,notifications/test_push_delivery.py,notifications/test_push_subscriptions.py}`: додано покриття для `If-None-Match`, `304` flow і збереження/оновлення `ETag`; verification: `./.venv/bin/pytest backend/tests/copart/test_http_client.py backend/tests/monitoring/test_change_detection.py backend/tests/search/test_saved_search_monitoring.py backend/tests/search/test_search_api.py backend/tests/notifications/test_push_delivery.py backend/tests/notifications/test_push_subscriptions.py` -> `40 passed` (є лише `urllib3` warning про локальний LibreSSL), `npm run test --prefix frontend -- app.test.tsx` -> `13 passed`.

## [2026-03-13 18:03] Add saved-search match-growth push notifications
- Оновлено `backend/src/cartrap/modules/search/{repository.py,service.py}` і `backend/src/cartrap/worker/main.py`: для `saved_searches` додано `last_checked_at`, фоновий due-poll раз на 15 хвилин і lightweight refresh тільки по `numFound`, без завантаження всіх search result pages.
- Оновлено `backend/src/cartrap/modules/notifications/service.py`: додано окремий push payload для росту `Matches` у saved searches з текстом `З'явилось <n> нових лотів для пошуку машини <search>`, який відправляється лише коли новий `result_count` більший за збережений.
- Додано `backend/tests/search/test_saved_search_monitoring.py` і розширено `backend/tests/search/test_search_api.py`: покрито increase/decrease/recent-check flows для saved-search polling і перевірку, що нові `saved_searches` отримують `last_checked_at`; verification: `./.venv/bin/pytest backend/tests/search/test_saved_search_monitoring.py backend/tests/search/test_search_api.py backend/tests/notifications/test_push_delivery.py backend/tests/notifications/test_push_subscriptions.py` -> `29 passed` (є лише `urllib3` warning про локальний LibreSSL), `npm run test --prefix frontend -- app.test.tsx` -> `13 passed`.

## [2026-03-13 17:39] Move push notifications UI into user settings modal
- Оновлено `frontend/src/{App.tsx,styles.css}` і `frontend/src/features/{dashboard/DashboardShell.tsx,push/PushSettingsModal.tsx}`: окрема hero-панель `Browser Notifications` прибрана, hero повернуто до двоколонного layout, а весь push UX перенесено в modal `Settings`, який відкривається з кнопки `Settings` на `User` panel.
- Видалено `frontend/src/features/push/PushPanel.tsx`: старий inline panel більше не рендериться, тому не ламає dashboard layout після розширення push functionality.
- Оновлено `frontend/tests/app.test.tsx`: push subscription flow тепер проходить через відкриття settings modal; verification: `npm run test --prefix frontend -- app.test.tsx` -> `13 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-13 17:31] Add manual test-push endpoint for current user subscriptions
- Оновлено `backend/src/cartrap/modules/notifications/{schemas.py,service.py,router.py}` і `docs/backend-api.md`: додано `POST /api/notifications/test`, який відправляє test push на всі subscriptions поточного користувача через той самий delivery path, що й worker notifications.
- Оновлено `backend/tests/notifications/test_push_subscriptions.py`: додано route-level тест, який перевіряє доставку test push на subscription поточного користувача з очікуваним payload `title/body/test`.
- Verification: `./.venv/bin/pytest backend/tests/notifications/test_push_subscriptions.py backend/tests/notifications/test_push_delivery.py` -> `9 passed` (є лише `urllib3` warning про локальний LibreSSL), `npm run test --prefix frontend -- app.test.tsx` -> `13 passed`.

## [2026-03-13 16:24] Fix browser push subscription flow behind Enable Push button
- Оновлено `backend/src/cartrap/{config.py}` і `backend/src/cartrap/modules/notifications/{router.py,schemas.py,service.py}`: додано `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY` у settings та новий `GET /api/notifications/subscription-config`, щоб frontend міг отримати public VAPID key або явну причину, чому push не сконфігурований; placeholder `replace-me` більше не вважається валідною конфігурацією.
- Оновлено `frontend/src/{App.tsx,lib/api.ts,main.tsx,types.ts}`: прибрано `fakeSubscription`, кнопка `Enable Push On This Device` тепер створює реальну browser subscription через `serviceWorker` + `PushManager`, працює й у локальній dev-сесії та показує користувачу зрозумілу помилку для HTTPS/permission/VAPID проблем.
- Оновлено `backend/tests/notifications/test_push_subscriptions.py`, `frontend/tests/app.test.tsx` і `docs/backend-api.md`: додано покриття для нового subscription-config endpoint і фронтенд-flow реальної push subscription; verification: `./.venv/bin/pytest backend/tests/notifications/test_push_subscriptions.py` -> `4 passed`, `npm run test --prefix frontend -- app.test.tsx` -> `13 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-13 16:41] Add real backend Web Push delivery via pywebpush
- Оновлено `backend/src/cartrap/modules/notifications/service.py`, `backend/src/cartrap/{app.py,worker/main.py,config.py}` і `backend/pyproject.toml`: інтегровано реальний `WebPushSender` через `pywebpush`, додано `VAPID_SUBJECT`, централізовану валідацію VAPID-конфігурації, а worker тепер створює `NotificationService` і реально відправляє push під час polling.
- Оновлено `.env.example`, `README.md`, `.gitignore` і `docs/backend-api.md`: задокументовано повний набір `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT`, точну послідовність генерації `applicationServerKey` через `py-vapid` і додано ignore для `*.pem`, щоб приватні ключі не комітилися в repo.
- Розширено `backend/tests/notifications/{test_push_subscriptions.py,test_push_delivery.py}`: додано перевірки для повної VAPID-конфігурації, transient vs unrecoverable delivery failures і серіалізації payload у `pywebpush`; verification: `./.venv/bin/pytest backend/tests/notifications/test_push_subscriptions.py backend/tests/notifications/test_push_delivery.py` -> `8 passed` (є лише `urllib3` warning про локальний LibreSSL), `npm run test --prefix frontend -- app.test.tsx` -> `13 passed`, `npm run build --prefix frontend` -> успішно.

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

## [2026-03-12 14:42] Add frontend token refresh on 401
- Оновлено `frontend/src/lib/api.ts`: захищені API запити тепер один раз пробують `/api/auth/refresh` після `401`, зберігають нові токени і повторюють початковий запит.
- Оновлено `frontend/src/lib/session.ts`, `frontend/src/app/useSession.ts`, `frontend/src/App.tsx`, щоб refreshed tokens синхронізувалися в React state, а невдалий refresh робив logout і redirect на login.
- Розширено `frontend/tests/app.test.tsx` сценарієм із протухлим `access_token`, який refresh-иться без втрати сесії.
- Додано завершений план `docs/plans/completed/20260312-frontend-session-refresh.md`.

## [2026-03-12 15:00] Use dedicated Copart lot details endpoint
- Оновлено `backend/src/cartrap/modules/copart_provider/client.py`: додано окремий `lot_details()` для `/lots-api/v1/lot-details?services=bidIncrementsBySiteV2`.
- `backend/src/cartrap/modules/copart_provider/service.py` більше не робить single-lot lookup через search endpoint; `fetch_lot()` працює напряму через `lotDetails`.
- Додано `extract_lot_details()` і `normalize_lot_details_payload()` у `backend/src/cartrap/modules/copart_provider/normalizer.py`.
- Оновлено `backend/src/cartrap/config.py`, `.env.example`, `backend/tests/test_config.py`, `backend/tests/copart/test_http_client.py`, `backend/tests/copart/test_api_normalizer.py` і `README.md`.
- Додано завершений план `docs/plans/completed/20260312-copart-lot-details-endpoint.md`.

## [2026-03-12 16:40] Generate static Copart make-model catalog
- Додано `backend/src/cartrap/modules/search/catalog_builder.py` з helpers для парсингу Copart `keywords`, канонізації make-alias-ів і побудови статичного каталогу `make -> models`.
- Додано генератор `scripts/generate_copart_make_model_catalog.py`, який валідує make/model відповідності через офіційний NHTSA vPIC API і пише готовий JSON-каталог.
- Згенеровано `backend/src/cartrap/modules/search/data/copart_make_model_catalog.json` та додано `backend/src/cartrap/modules/search/data/copart_make_model_overrides.json` для ручних винятків на кшталт `MODEL 3 -> tesla`.
- Додано тести `backend/tests/search/test_catalog_builder.py`, оновлено `README.md` і підготовлено базу для майбутнього переведення Manual Copart Search на локальний довідник make/model.

## [2026-03-12 17:40] Serve search catalog from backend and wire dropdown UI
- Додано Mongo-backed search catalog cache через `backend/src/cartrap/modules/search/repository.py` і startup seed у `backend/src/cartrap/app.py`; каталог тепер віддається через `GET /api/search/catalog`.
- Розширено Copart client/provider для `GET /mcs/v2/public/data/search/keywords` та додано admin-only refresh endpoint `POST /api/admin/search-catalog/refresh` у `backend/src/cartrap/modules/admin/router.py`.
- Оновлено `backend/src/cartrap/modules/search/service.py` і `backend/src/cartrap/modules/search/schemas.py`: search тепер може використовувати catalog-derived `make_filter` / `model_filter`, а catalog refresh працює через live Copart keywords + NHTSA matching.
- Перероблено frontend search UX у `frontend/src/features/search/SearchPanel.tsx`: `Make` і `Model` стали dropdown-ами з backend catalog; додано `frontend/src/features/admin/AdminSearchCatalogPanel.tsx` з кнопкою примусового refresh.
- Оновлено `frontend/src/App.tsx`, `frontend/src/lib/api.ts`, `frontend/src/types.ts`, `frontend/tests/app.test.tsx`, `backend/tests/search/test_search_api.py`, `backend/tests/copart/test_http_client.py`, `backend/tests/test_config.py` і `README.md`.

## [2026-03-12 17:45] Plan modal search results, saved searches, and lot thumbnails
- Додано план `docs/plans/20260312-manual-search-modal-saved-searches.md` для трьох пов’язаних UI/API змін: modal results у `Manual Copart Search`, user-scoped saved searches і thumbnail для `Tracked Lots`.
- Зафіксовано рекомендований напрям: `saved searches` зберігаються в backend/Mongo, modal робиться як окремий reusable UI layer, thumbnail проходить через Copart normalizer -> watchlist/search responses -> frontend cards.
- У плані одразу розкладено backend/frontend файли, regression tests (`pytest`, `npm run test`, `npm run build`) і acceptance verification для цього циклу змін.

## [2026-03-12 18:04] Implement modal search results, saved searches, and lot thumbnails
- Розширено backend search/watchlist contract: додано persisted `saved_searches` у `backend/src/cartrap/modules/search/*`, user-scoped save/list endpoints `/api/search/saved`, per-user duplicate isolation, а також `thumbnail_url` у Copart/search/watchlist моделі та серіалізацію.
- Оновлено frontend UX у `frontend/src/App.tsx`, `frontend/src/features/search/SearchPanel.tsx`, новому `frontend/src/features/search/SearchResultsModal.tsx`, `frontend/src/features/watchlist/WatchlistPanel.tsx`, `frontend/src/lib/api.ts`, `frontend/src/types.ts`, `frontend/src/styles.css`: search results тепер відкриваються в modal, saved searches рендеряться списком із `Run Search`, tracked lots показують thumbnail.
- Розширено regression coverage: `backend/tests/search/test_search_api.py`, `backend/tests/watchlist/test_watchlist_api.py`, `backend/tests/watchlist/test_snapshot_storage.py`, `backend/tests/copart/test_api_normalizer.py`, `frontend/tests/app.test.tsx`.
- Оновлено `README.md`, plan completion у `docs/plans/completed/20260312-manual-search-modal-saved-searches.md` і прогнано verification: `./.venv/bin/pytest backend/tests` -> `60 passed`, `npm run test --prefix frontend` -> `6 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-12 18:10] Fix service worker registration and thumbnail URL normalization
- Оновлено `frontend/src/main.tsx`: service worker тепер реєструється лише в production і через `frontend/public/sw.js`, а не через Vite source path `/src/sw.ts`, що прибирає browser `SecurityError` / unsupported MIME type у dev mode.
- Додано `frontend/src/features/shared/LotThumbnail.tsx` і fallback rendering у `frontend/src/features/search/SearchResultsModal.tsx` та `frontend/src/features/watchlist/WatchlistPanel.tsx`, щоб биті thumbnail URL не лишали поламаний `<img>`.
- Розширено `backend/src/cartrap/modules/copart_provider/normalizer.py`, щоб relative (`/content/...`) і protocol-relative (`//img...`) thumbnail URLs нормалізувалися в абсолютні Copart/CDN адреси; додано regression test у `backend/tests/copart/test_api_normalizer.py`.
- Прогнано verification: `./.venv/bin/pytest backend/tests/copart/test_api_normalizer.py` -> `6 passed`, `npm run test --prefix frontend` -> `6 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-12 18:12] Use Copart lot_thumbnail_image_path for search thumbnails
- Уточнено `backend/src/cartrap/modules/copart_provider/normalizer.py`: search thumbnail тепер пріоритетно береться з реального Copart поля `lot_thumbnail_image_path`, а не лише з узагальнених image keys.
- Оновлено regression fixtures у `backend/tests/copart/test_api_normalizer.py`, щоб вони перевіряли саме `lot_thumbnail_image_path`, включно з relative-path сценарієм.
- Повторно прогнано релевантні перевірки: `./.venv/bin/pytest backend/tests/copart/test_api_normalizer.py backend/tests/search/test_search_api.py` -> `18 passed`, `npm run test --prefix frontend -- app.test.tsx` -> `6 passed`.

## [2026-03-12 18:19] Fix scheme-less Copart CDN thumbnail URLs
- Оновлено `backend/src/cartrap/modules/copart_provider/normalizer.py`: thumbnail path виду `cs.copart.com/...` без схеми тепер автоматично нормалізується в `https://cs.copart.com/...`, щоб `Pydantic HttpUrl` не падав з `url_parsing`.
- Розширено `backend/tests/copart/test_api_normalizer.py` окремим regression scenario для scheme-less `lot_thumbnail_image_path` із Copart CDN.
- Повторно прогнано релевантні перевірки: `./.venv/bin/pytest backend/tests/copart/test_api_normalizer.py backend/tests/search/test_search_api.py` -> `18 passed`.

## [2026-03-12 18:31] Add tracked-lot gallery from Copart lotImages
- Розширено `backend/src/cartrap/modules/copart_provider/models.py` і `backend/src/cartrap/modules/copart_provider/normalizer.py`: `CopartLotSnapshot` тепер містить `image_urls`, а `normalize_lot_details_payload()` збирає gallery з `lotImages` і бере thumbnail з першого фото в списку.
- Оновлено watchlist contract у `backend/src/cartrap/modules/watchlist/service.py` та `backend/src/cartrap/modules/watchlist/schemas.py`: `tracked_lot` тепер серіалізує `image_urls` разом із `thumbnail_url`, а gallery зберігається в `tracked_lots`.
- Додано frontend gallery modal у `frontend/src/features/watchlist/LotGalleryModal.tsx`, інтегровано clickable thumbnail через `frontend/src/features/shared/LotThumbnail.tsx` і `frontend/src/features/watchlist/WatchlistPanel.tsx`.
- Розширено regression coverage в `backend/tests/copart/test_api_normalizer.py`, `backend/tests/watchlist/test_watchlist_api.py`, `backend/tests/watchlist/test_snapshot_storage.py`, `frontend/tests/app.test.tsx`.
- Оновлено `README.md` і прогнано verification: `./.venv/bin/pytest backend/tests/copart/test_api_normalizer.py backend/tests/watchlist/test_watchlist_api.py backend/tests/watchlist/test_snapshot_storage.py` -> `14 passed`, `npm run test --prefix frontend` -> `7 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-12 18:40] Harden lotImages extraction for tracked-lot thumbnails
- Оновлено `backend/src/cartrap/modules/copart_provider/normalizer.py`: `extract_lot_details()` тепер підтягує `lotImages` не лише з `lotDetails`, а й з root-level / `data` payload, якщо Copart повертає gallery окремо.
- Додано stricter image-like path detection і support для nested keys на кшталт `highResUrl`, щоб `lotImages` краще парсилися в реальних Copart lot-details response без `thumbnail_url: null`.
- Розширено `backend/tests/copart/test_api_normalizer.py` сценаріями для root-level `lotImages` і scheme-less gallery URLs; повторно прогнано `./.venv/bin/pytest backend/tests/copart/test_api_normalizer.py backend/tests/watchlist/test_watchlist_api.py backend/tests/watchlist/test_snapshot_storage.py` -> `16 passed`.

## [2026-03-12 18:43] Backfill media for legacy tracked lots
- Перевірено реальний payload із `Lot_Response.json`: `lotImages` приходить на top-level response і містить валідні `url`/`thumbnailUrl`, тож `thumbnail_url: null` для tracked lot був ознакою застарілого документа в Mongo, а не нового lot-details contract.
- Оновлено `backend/src/cartrap/modules/watchlist/service.py`: `GET /api/watchlist` тепер робить lazy media backfill для legacy items без `thumbnail_url`/`image_urls`, підтягує актуальний snapshot із Copart і зберігає media поля назад у `tracked_lots`.
- Оновлено `backend/src/cartrap/modules/monitoring/service.py`, щоб background polling також синхронізував `thumbnail_url` і `image_urls`, а не лише bid/status state.
- Додано regression coverage в `backend/tests/watchlist/test_watchlist_api.py` і `backend/tests/monitoring/test_change_detection.py`; прогнано `./.venv/bin/pytest backend/tests/copart/test_api_normalizer.py backend/tests/watchlist/test_watchlist_api.py backend/tests/watchlist/test_snapshot_storage.py backend/tests/monitoring/test_change_detection.py` -> `20 passed`.

## [2026-03-12 18:55] Polish watchlist and responsive card layout
- Перероблено `frontend/src/features/watchlist/WatchlistPanel.tsx`: tracked-lot card тепер має окремі зони `media / body / actions`, статус винесено в pill, метадані й bid не злипаються з кнопкою `Remove`.
- Оновлено `frontend/src/styles.css`: додано стабільний відступ між watchlist form і списком, card surface styling для `result-card`, кращий mobile stack для watchlist actions/meta та загальний cleanup заголовків/label spacing у panel forms.
- Прогнано frontend verification: `npm run test --prefix frontend` -> `7 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-12 19:05] Add saved-search delete, result counts, and full search pagination
- Оновлено backend search flow у `backend/src/cartrap/modules/copart_provider/{models.py,normalizer.py,service.py}` та `backend/src/cartrap/modules/search/{schemas.py,service.py,repository.py,router.py}`: `/api/search` тепер читає `numFound`, проходить усі `pageNumber` по 20 лотів на сторінку, повертає `total_results`, а saved searches зберігають `result_count` і підтримують `DELETE /api/search/saved/{id}`.
- Оновлено frontend contract/UX у `frontend/src/{types.ts,lib/api.ts,App.tsx}`, `frontend/src/features/search/{SearchPanel.tsx,SearchResultsModal.tsx}`, `frontend/src/styles.css`: у saved search row відображається кількість знайдених лотів, з’явилась кнопка `Delete`, modal показує загальний count поточного пошуку.
- Розширено regression coverage в `backend/tests/search/test_search_api.py`, `backend/tests/copart/test_api_normalizer.py`, `frontend/tests/app.test.tsx` під `numFound`, multi-page fetch, saved-search count і delete flow.

## [2026-03-12 19:18] Fix LAN-access frontend API host and backend CORS
- Оновлено `frontend/src/lib/api.ts`: якщо `VITE_API_BASE_URL` не заданий, frontend більше не хардкодить `localhost`, а будує API base URL як `http://<current-host>:8000/api`, тож відкриття через `192.168.x.x:5173` використовує той самий LAN host для backend.
- Оновлено `backend/src/cartrap/{config.py,app.py}`: у non-production backend дозволяє CORS для private LAN IPv4 origins через `allow_origin_regex`, не обмежуючись лише `localhost`/`127.0.0.1`.
- Розширено документацію й тести в `README.md`, `backend/tests/test_app_boot.py`, `backend/tests/test_config.py` під LAN-origin preflight і новий default API-host behavior.

## [2026-03-12 19:24] Remove localhost API default from frontend container build
- Оновлено `docker-compose.yml` і `frontend/Dockerfile`: containerized frontend більше не вшиває `VITE_API_BASE_URL=http://localhost:8000/api` за замовчуванням, щоб LAN access міг використовувати runtime-derived `http://<current-host>:8000/api`.
- Уточнено `README.md`, що для авто-визначення API host `VITE_API_BASE_URL` треба лишати порожнім, а не задавати `localhost`.

## [2026-03-13 12:36] Add backend API and MongoDB documentation
- Додано `docs/backend-api.md` з актуальним описом backend endpoint-ів: auth, admin, search, watchlist, notifications, auth model, основні request/response payload-и та error semantics.
- Додано `docs/database-schema.md` з описом MongoDB-колекцій, ключових полів, зв’язків між документами, індексів і приміток по тому, що зараз не зберігається в БД.
- Документацію зібрано на основі фактичних router/schema/repository/service модулів у `backend/src/cartrap/modules/*`, без зміни runtime-коду.

## [2026-03-13 12:44] Add external Copart URL button to saved searches
- Оновлено `backend/src/cartrap/modules/search/{schemas.py,service.py}`: saved search response тепер містить `external_url`, який генерується з критеріїв через Copart `lotSearchResults`, а для `lot_number`-based search веде напряму на сторінку лота.
- Оновлено `frontend/src/{types.ts}` та `frontend/src/features/search/SearchPanel.tsx`: у рядку saved search додано кнопку-лінк `Open URL`, що відкриває пошук у зовнішньому браузері.
- Розширено покриття в `backend/tests/search/test_search_api.py` і `frontend/tests/app.test.tsx` для перевірки generated URL та рендеру нового зовнішнього лінка.

## [2026-03-13 12:49] Align saved-search external URL with Copart web filters
- Уточнено `backend/src/cartrap/modules/search/schemas.py`: `external_url` для saved searches тепер будується з `displayStr`, `qId` і `searchCriteria.filter` (`YEAR` / `MAKE` / `MODL`) у форматі, ближчому до реального Copart `vehicleFinder` URL, а не як порожній free-form filter.
- Оновлено `backend/tests/search/test_search_api.py` і `frontend/tests/app.test.tsx`, щоб перевіряти новий URL contract із `qId` та заповненим `searchCriteria.filter`.

## [2026-03-13 12:52] Normalize saved-search external link button styling
- Оновлено `frontend/src/styles.css`: `.ghost-button` тепер задає layout/padding/radius/text-decoration самостійно, щоб `Open URL` як `<a>` виглядав так само, як інші action buttons у `Saved Searches`.

## [2026-03-13 13:06] Add pre-search filter modal for drive train and primary damage
- Оновлено `backend/src/cartrap/modules/search/{schemas.py,service.py}`: manual search і saved searches тепер підтримують додаткові поля `drive_type` та `primary_damage`, які мапляться в Copart `filter[]` як structured filters для `Drive train` і `Primary damage`.
- Додано frontend filter UX у `frontend/src/features/search/{SearchPanel.tsx,SearchFiltersModal.tsx,searchFilters.ts}` та оновлено `frontend/src/{App.tsx,lib/api.ts,types.ts,styles.css}`: кнопка `Filters` відкриває modal до `Search Lots`, можна застосувати/очистити фільтри, а активні значення показуються під формою й у saved searches.
- Розширено покриття в `backend/tests/search/test_search_api.py` і `frontend/tests/app.test.tsx` для перевірки нового `filter[]` payload і modal-based apply flow.

## [2026-03-13 13:11] Include drive filter in saved-search external Copart URL
- Уточнено `backend/src/cartrap/modules/search/schemas.py`: `external_url` для saved searches тепер додає `searchCriteria.filter.DRIV` із канонічним Copart значенням, якщо обрано `Drive train`, щоб зовнішній `lotSearchResults` URL відповідав web-format payload.
- Оновлено `backend/tests/search/test_search_api.py` і `frontend/tests/app.test.tsx` для перевірки `DRIV` у generated external URL.

## [2026-03-13 13:42] Add more search filters from saved mobile Copart API tree
- Переглянуто збережені mobile API dumps у `Temp/mmember.copart.com`, зокрема `srch/index*.html`, `mcs/v2/public/data/search/keywords` і `api/v2/reference-data/sale-highlights`, та виділено додаткові фільтри, які реально присутні в Copart payload/facets: `title_group_code`, `fuel_type_desc`, `lot_condition_code`, `odometer_reading_received`.
- Оновлено `backend/src/cartrap/modules/search/{schemas.py,service.py}`: manual search і saved searches тепер підтримують `title_type`, `fuel_type`, `lot_condition`, `odometer_range`; критерії мапляться в Copart `filter[]`, серіалізуються в saved searches і додаються в generated external Copart URL разом із `primary_damage`.
- Оновлено frontend UX у `frontend/src/{App.tsx,types.ts,lib/api.ts,styles.css}` та `frontend/src/features/search/{SearchPanel.tsx,SearchFiltersModal.tsx,searchFilters.ts}`: modal `Filters` тепер дозволяє вибирати `Title type`, `Fuel type`, `Sale highlight`, `Odometer`, а активні значення відображаються під формою й у списку saved searches.
- Розширено regression coverage в `backend/tests/search/test_search_api.py` і `frontend/tests/app.test.tsx`; verification: `./.venv/bin/pytest backend/tests/search/test_search_api.py` -> `17 passed`, `npm run test --prefix frontend -- app.test.tsx` -> `10 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-13 14:00] Add typed make/model filtering for search panel dropdowns
- Оновлено `frontend/src/features/search/SearchPanel.tsx`: для `Make` і `Model` додано поля `Find make` / `Find model`, які в реальному часі фільтрують відповідні dropdown-и без ручного скролу по всьому каталогу.
- Для make використано prefix-match по початку назви (`F` -> `FORD`, `FIAT`), а для model реалізовано word-prefix search по токенах, щоб `MAC` знаходив `MUSTANG MACH-E`, а не лише збіги з початку всього рядка.
- Розширено frontend regression coverage в `frontend/tests/app.test.tsx` окремим сценарієм live-фільтрації списків і перевірено, що існуючі search/save flows не зламалися; verification: `npm run test --prefix frontend -- app.test.tsx` -> `11 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-13 14:09] Merge make/model search into single searchable selectors
- Перероблено `frontend/src/features/search/SearchPanel.tsx`: окремі поля `Find make` / `Find model` прибрано, а `Make` і `Model` тепер працюють як один searchable control кожне: ввід відбувається прямо в поле, а нижче відкривається live-filtered dropdown з відповідними варіантами.
- Збережено попередню логіку матчингу: для make це prefix-search по початку назви, для model це word-prefix search по токенах, тож `MAC` і далі знаходить `MUSTANG MACH-E`; додано стилі dropdown-а в `frontend/src/styles.css`.
- Оновлено frontend regression coverage в `frontend/tests/app.test.tsx` під нову взаємодію з single-field selectors; verification: `npm run test --prefix frontend -- app.test.tsx` -> `11 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-13 14:17] Reduce width of year inputs in search panel
- Оновлено `frontend/src/features/search/SearchPanel.tsx`: поля `Year From` і `Year To` отримали локальний class, `inputMode="numeric"` і `maxLength={4}`, щоб краще відповідати фактичному формату значення.
- Оновлено `frontend/src/styles.css`: для `.search-grid__year-field` додано вузьку ширину, щоб year inputs не розтягувалися як повноширинні поля в search panel.
- Verification: `npm run build --prefix frontend` -> успішно.

## [2026-03-13 14:20] Keep year inputs paired in one row
- Оновлено `frontend/src/features/search/SearchPanel.tsx`: `Year From` і `Year To` згруповано в окремий `search-grid__year-group`, щоб ці два поля рендерилися як зв’язана пара.
- Оновлено `frontend/src/styles.css`: для `search-grid__year-group` додано внутрішню двоколонну grid-розкладку, тож year inputs залишаються поруч один біля одного навіть коли основна search-grid переходить у вузький layout.
- Verification: `npm run build --prefix frontend` -> успішно.

## [2026-03-13 14:31] Add implementation plan for tracked lot detail tiles
- Додано `docs/plans/20260313-enhance-tracked-lots-tiles-with-lot-details.md` з end-to-end планом для розширення `Tracked Lots` полями `Odometer`, `Primary damage`, `Estimated retail value`, `Has Key`, `Drivetrain`, `Highlights`, `Vin`.
- У плані зафіксовано рекомендований підхід: нормалізувати Copart lot-details на backend, декодувати `encryptedVIN` через логіку з `vin_decoder.py`, розширити watchlist API/persistence і лише потім оновити frontend tiles та regression-тести.

## [2026-03-13 14:35] Auto-review tracked lot details implementation plan
- Проведено auto review `docs/plans/20260313-enhance-tracked-lots-tiles-with-lot-details.md` і уточнено два ризики реалізації: крихкий імпорт `vin_decoder.py` з кореня repo та неоднозначний критерій backfill для nullable detail-полів.
- Оновлено план: VIN decoder тепер явно винесено в backend-safe importable helper, а backfill для legacy tracked lots має спиратися на відсутність ключів у документі, а не на прості `None`-перевірки.

## [2026-03-13 15:14] Enrich tracked lot tiles with decoded VIN and lot details
- Оновлено `backend/src/cartrap/modules/copart_provider/{models.py,normalizer.py,vin.py}` і `vin_decoder.py`: `CopartLotSnapshot` тепер містить `odometer`, `primary_damage`, `estimated_retail_value`, `has_key`, `drivetrain`, `highlights`, `vin`; lot-details normalizer витягує ці поля з Copart payload і декодує `encryptedVIN` через shared backend helper.
- Оновлено `backend/src/cartrap/modules/watchlist/{schemas.py,service.py}` та `backend/src/cartrap/modules/monitoring/service.py`: нові detail-поля зберігаються в `tracked_lots`, повертаються з `/api/watchlist`, lazy backfill працює для legacy документів за відсутніми ключами, а background polling синхронізує detail state разом із media/status/bid.
- Оновлено `frontend/src/{types.ts,styles.css}` і `frontend/src/features/watchlist/WatchlistPanel.tsx`: `Tracked Lots` card тепер показує `Odometer`, `Primary damage`, `Estimated retail value`, `Has Key`, `Drivetrain`, `Highlights`, `Vin` з fallback `—` для відсутніх значень і читабельним responsive details-grid.
- Розширено покриття в `backend/tests/copart/test_api_normalizer.py`, `backend/tests/watchlist/test_watchlist_api.py`, `backend/tests/watchlist/test_snapshot_storage.py`, `backend/tests/monitoring/test_change_detection.py`, `frontend/tests/app.test.tsx`; verification: `./.venv/bin/pytest backend/tests/copart/test_api_normalizer.py backend/tests/watchlist/test_watchlist_api.py backend/tests/watchlist/test_snapshot_storage.py backend/tests/monitoring/test_change_detection.py` -> `23 passed`, `npm run test --prefix frontend -- app.test.tsx` -> `12 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-13 15:18] Fix Copart key mapping for retail value and key status
- Уточнено `backend/src/cartrap/modules/copart_provider/normalizer.py`: `estimated_retail_value` тепер у першу чергу читається з `estRetailValue`, а `has_key` з `keys`, збережено fallback на попередні aliases для сумісності.
- Оновлено `backend/tests/copart/test_api_normalizer.py` під фактичні Copart lot-details keys `estRetailValue` і `keys`.

## [2026-03-13 15:25] Compact tracked lot tile layout
- Оновлено `frontend/src/features/watchlist/WatchlistPanel.tsx`: detail-поля в `Tracked Lots` тепер рендеряться як щільніші рядки `label: value` через компактний `dl`, без втрати полів `Odometer`, `Primary damage`, `Retail`, `Has Key`, `Drivetrain`, `Highlights`, `Vin`.
- Оновлено `frontend/src/styles.css`: зменшено thumb, padding і вертикальні відступи в `watchlist-card`, details-grid переведено в компактніший 3-column layout на desktop і 2-column на mobile/tablet.
- Оновлено `frontend/tests/app.test.tsx` під новий compact markup; verification: `npm run test --prefix frontend -- app.test.tsx` -> `12 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-13 15:29] Make tracked lot number open Copart lot page
- Оновлено `frontend/src/features/watchlist/WatchlistPanel.tsx`: номер лоту в `Tracked Lots` тепер рендериться як зовнішній лінк на Copart lot URL і відкривається в новій вкладці.
- Оновлено `frontend/src/styles.css`: додано стилізацію для `watchlist-card__lot-link`, щоб лінк залишався компактним і читабельним всередині card.
- Оновлено `frontend/tests/app.test.tsx` перевіркою `href` і `target` для лінка на Copart; verification: `npm run test --prefix frontend -- app.test.tsx` -> `12 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-13 15:41] Unify tracked lot parameter styling and top summary layout
- Оновлено `frontend/src/features/watchlist/WatchlistPanel.tsx`: верхні параметри `Lot / Bid / Sale` винесено в окремий summary `dl` над нижнім details-grid, а всі параметри в tile тепер використовують один і той самий label/value layout.
- Оновлено `frontend/src/styles.css`: уніфіковано шрифти й кольори для всіх параметрів у `Tracked Lots`, summary і details використовують спільні стилі; верхній блок лишається над нижньою таблицею і на mobile переходить у одноколонний layout.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `12 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-13 15:47] Align dashboard typography and move Browser Notifications beside user panel
- Оновлено `frontend/src/features/dashboard/DashboardShell.tsx` і `frontend/src/App.tsx`: hero отримав праву `sidebar`-колонку, де `Browser Notifications` тепер стоїть поруч із user-card замість нижньої частини dashboard-grid.
- Оновлено `frontend/src/features/push/PushPanel.tsx` і `frontend/src/styles.css`: для informational блоків введено shared `detail-label/detail-value` типографіку, яку використано в user-card, push panel і `Tracked Lots`, щоб шрифти й кольори параметрів були узгоджені по всьому dashboard.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `12 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-13 15:58] Extend shared parameter styling to Manual Copart Search and fix hero layout
- Оновлено `frontend/src/features/search/SearchPanel.tsx`: `Manual Copart Search` тепер має compact summary-блок у shared style (`Make`, `Model`, `Years`, `Filters`) одразу під формою, замість окремого рядка `Active filters`.
- Оновлено `frontend/src/features/dashboard/DashboardShell.tsx` і `frontend/src/styles.css`: hero перебудовано в три окремі колонки `intro / user / browser notifications`, щоб `Browser Notifications` був реально поруч із user-card, а не стеком під ним.
- Оновлено `frontend/tests/app.test.tsx` під новий summary markup; verification: `npm run test --prefix frontend -- app.test.tsx` -> `12 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-13 16:06] Apply shared detail layout to Saved Searches and balance search form spacing
- Оновлено `frontend/src/features/search/SearchPanel.tsx`: `Saved Searches` тепер рендеряться через той самий shared label/value layout (`Make`, `Model`, `Years`, `Filters`, `Matches`), що й інші informational блоки dashboard.
- Оновлено `frontend/src/styles.css`: для search form додано явний нижній відступ під `Search Lots`, а saved-search details отримали власний compact detail-grid з тим самим шрифтовим контрактом.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `12 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-18 16:31] Align lot preview aspect ratios with Copart image sizes
- Оновлено `frontend/src/styles.css`: search/watchlist thumbnail-и `LotThumbnail` переведено з квадратного контейнера на `4 / 3` aspect ratio, що відповідає Copart preview `144x108` і прибирає некоректне відображення прев’ю.
- Оновлено gallery styles для lot photos: hero image та thumbnail strip тепер також використовують `4 / 3`, що відповідає lot image size `960x720` і стабілізує відображення в modal.

## [2026-03-18 16:24] Remove prefilled login credentials and add admin email link
- Оновлено `frontend/src/features/auth/LoginScreen.tsx`: поля `Email` і `Password` на login screen тепер стартують порожніми замість predefined `admin@example.com` / `AdminPass123`.
- Оновлено текст invite hint на login screen: слово `administrator` тепер є `mailto:`-посиланням на `vpm2000@gmail.com` з підготовленими subject/body для запиту invite link.

## [2026-03-16 12:04] Add implementation plan for NAS-backed Copart gateway split
- Додано `docs/plans/20260316-nas-copart-gateway-split.md` з покроковим планом розділення інтеграції Copart: AWS лишається primary backend + Mongo, а локальний NAS стає окремим `copart-gateway`, який виконує сирі Copart-запити з локальної IP.
- У плані зафіксовано рекомендовану архітектуру без fallback на direct Copart mode: backend деградує в `offline/live-sync unavailable` режим, worker пропускає sync cycles без падіння process, frontend показує banner про доступність лише локально збережених даних.
- Окремо винесено rollout-частину для NAS deployment: TLS, bearer auth, IP allowlist, gzip compression, health endpoint і зовнішні кроки з DNS/router/firewall.

## [2026-03-16 12:09] Refine NAS gateway split plan after technical review
- Оновлено `docs/plans/20260316-nas-copart-gateway-split.md` після review: додано покриття для `saved_search` polling у worker, явну вимогу до shared persisted `live_sync` status між web app і worker, а також окремий акцент на reusable HTTP client/keep-alive між AWS і NAS.
- Скориговано frontend scope в degraded mode: замість широкого disable live actions перша ітерація фокусується на banner + зрозумілих повідомленнях про live-sync недоступність при збереженні Mongo-backed даних у UI.

## [2026-03-16 12:13] Add private AWS server administration runbook
- Оновлено `.gitignore`: каталог `docs/private/` додано до ignore, щоб приватна ops-документація не потрапляла в git.
- Додано `docs/private/aws-server-admin.md` з детальним runbook для AWS/Lightsail сервера: SSH та робочі шляхи, перевірка стану stack, перегляд логів Docker/Caddy, оновлення Docker Engine, тягнення останніх source changes, rebuild/restart compose stack, базові health checks, cleanup і recovery notes.

## [2026-03-16 13:05] Install external write skill from oberskills
- Оновлено `ChangeLog.md`: зафіксовано встановлення зовнішнього skill `write` із репозиторію `ryanthedev/oberskills`.
- Під час інсталяції виявлено, що `skills/write` у вихідному репозиторії не містить `SKILL.md`, тому штатний `skill-installer` не міг встановити його напряму.
- У `~/.codex/skills/write` створено Codex-сумісний wrapper `SKILL.md` і підтягнуто вихідні reference-файли `elements-of-style.md` та `references/ai-writing-patterns.md`.

## [2026-03-16 18:56] Add saved-search results cache persistence primitives
- Оновлено `backend/src/cartrap/modules/search/{models.py,repository.py,schemas.py,service.py}`: додано окрему Mongo collection для cached saved-search results, ownership-scoped repository methods, atomic `view-and-clear` flow для `NEW`, а також backend response shape для cached modal і list metadata (`cached_result_count`, `new_count`, `last_synced_at`).
- Додано `backend/tests/search/test_saved_search_cache_repository.py` з покриттям upsert/read/list/view/delete flow для cache-документів і schema/serialization contract для майбутнього cached modal response.
- Оновлено `docs/plans/20260316-saved-search-cache-run-search.md`: Task 1 позначено завершеним після успішної верифікації.
- Verification: `./.venv/bin/pytest backend/tests/search/test_saved_search_cache_repository.py` -> `4 passed`, `./.venv/bin/pytest backend/tests/search/test_search_api.py` -> `18 passed`, `./.venv/bin/pytest backend/tests/search/test_saved_search_monitoring.py` -> `5 passed`.

## [2026-03-16 19:01] Seed saved-search cache on save and add cached view endpoints
- Оновлено `backend/src/cartrap/modules/search/{router.py,schemas.py,service.py}`: `SavedSearchCreateRequest` тепер приймає `seed_results`, save flow seed-ить Mongo cache без додаткового live Copart request, а нові endpoint-и `POST /api/search/saved/{id}/view` і `POST /api/search/saved/{id}/refresh-live` повертають cached modal payload та оновлюють persisted seen/cache state.
- Уточнено `backend/src/cartrap/modules/search/repository.py`: `view` path тепер atomically очищає `new_lot_numbers`, але повертає pre-clear snapshot, щоб modal міг показати lot-level `NEW`, поки list metadata вже скинута.
- Розширено `backend/tests/search/test_search_api.py` новими API сценаріями для cache seed, cached view, refresh-live і owner/not-found access control; `backend/tests/search/test_saved_search_cache_repository.py` синхронізовано з pre-clear semantics.
- Оновлено `docs/plans/20260316-saved-search-cache-run-search.md`: Task 2 позначено завершеним після повторної backend verification.
- Verification: `./.venv/bin/pytest backend/tests/search/test_saved_search_cache_repository.py` -> `4 passed`, `./.venv/bin/pytest backend/tests/search/test_search_api.py` -> `22 passed`, `./.venv/bin/pytest backend/tests/search/test_saved_search_monitoring.py` -> `5 passed`.

## [2026-03-16 19:07] Move saved-search worker polling to cache diff semantics
- Оновлено `backend/src/cartrap/modules/search/service.py`: worker polling тепер використовує cheap `etag/result_count` check лише як gate, робить full search при change або відсутньому cache, дифить `lot_number` проти попереднього cached result set, зберігає union unseen `new_lot_numbers` і рахує push `new_matches` лише з truly-new lot numbers поточного циклу.
- Оновлено `backend/tests/search/test_saved_search_monitoring.py`: додано покриття для changed cache with new lots, changed cache without truly new lots, legacy cache backfill when upstream reports `not_modified`, і збережено сценарії skip/failure для polling loop.
- Оновлено `docs/plans/20260316-saved-search-cache-run-search.md`: Task 3 позначено завершеним після backend verification.
- Verification: `./.venv/bin/pytest backend/tests/search/test_saved_search_monitoring.py` -> `6 passed`, `./.venv/bin/pytest backend/tests/search/test_search_api.py` -> `22 passed`, `./.venv/bin/pytest backend/tests/search/test_saved_search_cache_repository.py` -> `4 passed`.

## [2026-03-16 19:14] Switch saved-search UI to cached modal flow
- Оновлено `frontend/src/{types.ts,lib/api.ts,App.tsx}`: додано типи й API client для cached saved-search `view` / `refresh-live`, `Save Search` тепер передає `seed_results`, а App синхронізує list metadata з backend responses замість повторного live `/search`.
- Оновлено `frontend/src/features/search/{SearchPanel.tsx,SearchResultsModal.tsx}` і `frontend/src/styles.css`: `Run Search` відкриває cached modal, saved-search cards показують `new_count` / `last_synced_at`, lot-level `NEW` badge очищається після view, а всередині modal з’явився `Refresh Live`, який лишає cached results видимими навіть при помилці refresh.
- Оновлено `frontend/tests/app.test.tsx`: додано regression scenarios для cache-seeded save flow, cached rerun без generic live search, `NEW` clearing semantics і modal `Refresh Live`; на тестовому mock API введено cached saved-search endpoints.
- Оновлено `docs/plans/20260316-saved-search-cache-run-search.md`: Task 4 позначено завершеним після frontend verification.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `18 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-16 19:15] Complete saved-search cache rollout verification
- Оновлено `docs/plans/completed/20260316-saved-search-cache-run-search.md`: Task 5/6 позначено завершеними, додано примітку що `README.md`/`backend/README.md` не змінювались у цьому циклі, і план перенесено в `docs/plans/completed/`.
- Проведено повний regression прогін після backend/frontend реалізації cached saved-search flow.
- Verification: `./.venv/bin/pytest backend/tests` -> `133 passed`, `npm run test --prefix frontend` -> `18 passed`, `npm run build --prefix frontend` -> успішно.

## [2026-03-17 14:31] Add implementation plan for PWA UX polish across search, watchlist, push, and admin flows
- Додано `docs/plans/20260317-pwa-ux-polish-flows.md` з покроковим планом доробки UX для вже реалізованих flows: saved-search metadata, refresh/error states, watchlist clarity, push diagnostics, admin support tooling.
- У плані зафіксовано рекомендований підхід через shared async feedback primitives замість великого редизайну, з окремим акцентом на mobile/PWA usage, loading indicators, progress bars, disabled/pending semantics і degraded-mode messaging.
- Окремо додано перелік практичних usability improvements beyond spinner/progress bar: cached-data preservation during refresh, clearer stale/live status copy, current-device push diagnostics, test-push UX, copy affordances для довгих URL/endpoint-ів і safer admin feedback.
## [2026-03-17 14:37] Tighten PWA UX polish plan with missing failure-state coverage
- Оновлено `docs/plans/20260317-pwa-ux-polish-flows.md` після повторної перевірки: додано явне покриття для manual search / save-search pending states, partial bootstrap failures з panel-level retry, а також browser offline/online UX як окремий сценарій від backend live-sync degraded mode.
- Уточнено testing/manual verification секції: тепер план вимагає перевіряти часткові фейли завантаження dashboard, throttled search/save flows, offline-to-online recovery і reduced-motion-safe loading animations.

## [2026-03-20 15:45] Fix auction reminder polling when reminder thresholds are crossed between regular checks
- Оновлено `backend/src/cartrap/modules/monitoring/service.py`: `poll_due_lots()` тепер форсує poll не лише за звичайним polling cadence, а й коли між `last_checked_at` та поточним часом був перетин pending reminder threshold (`60m`, `15m`, `auction start`), щоб time-based push-нагадування не залежали від точного вирівнювання worker loop.
- Оновлено `backend/tests/monitoring/test_change_detection.py`: додано regression-покриття для двох проблемних сценаріїв: перетин `60m` threshold до настання стандартного poll interval і start reminder одразу після недавньої pre-start перевірки.
- Verification: `./.venv/bin/pytest backend/tests/monitoring/test_change_detection.py backend/tests/notifications/test_push_delivery.py backend/tests/monitoring/test_polling_policy.py` -> `17 passed` (є лише `urllib3` warning про локальний LibreSSL).

## [2026-03-18 15:25] Refresh PWA data in place after backend push updates
- Оновлено `backend/src/cartrap/modules/notifications/service.py` і тести `backend/tests/notifications/{test_push_delivery.py,test_push_subscriptions.py}`: push payload тепер містить `notification_type` і `refresh_targets`, щоб frontend міг адресно оновлювати потрібні секції dashboard після серверних змін.
- Оновлено `frontend/public/sw.js`: service worker після отримання push не тільки показує notification, а й розсилає `cartrap:push-received` у всі відкриті вкладки PWA; додано fallback-логіку для deriving `refresh_targets` і focus/open app по кліку на notification.
- Оновлено `frontend/src/App.tsx` і `frontend/tests/app.test.tsx`: додано listener на service-worker messages, batched background refresh `watchlist/savedSearches/liveSync/...` без `window.location.reload()`, плюс regression-тест на оновлення watchlist після push.
- Verification: `./.venv/bin/pytest backend/tests/notifications/test_push_delivery.py backend/tests/notifications/test_push_subscriptions.py` -> `10 passed`; `npm run test --prefix frontend -- app.test.tsx` -> `25 passed`; `npm run build --prefix frontend` -> успішно.

## [2026-03-18 15:57] Generate favicon and PWA icon set for CarTrap
- Додано `frontend/public/icons/{cartrap-icon.svg,cartrap-icon-maskable.svg,icon-192.png,icon-512.png,icon-maskable-192.png,icon-maskable-512.png}` та root-level site icons `frontend/public/{favicon.ico,favicon-16x16.png,favicon-32x32.png,apple-touch-icon.png}`: зібрано повний набір для браузерного favicon, iOS home screen і PWA install flow.
- Оновлено `frontend/public/manifest.webmanifest`: додано `id`, `scope` і секцію `icons` з `any` та `maskable` assets, щоб installable PWA використовувала коректні іконки на Android/desktop.
- Оновлено `frontend/index.html`: підключено `favicon.ico`, SVG/PNG favicon-и, `apple-touch-icon`, `manifest` і базові theme/app meta-теги для браузерів та мобільного web app mode.
- Додано `scripts/generate_frontend_icons.py`: локальний generator через headless Chrome, який дозволяє перевипускати PNG/ICO з SVG source assets без сторонніх npm/python бібліотек.
- Verification: `python3 scripts/generate_frontend_icons.py` -> успішно; `npm run build --prefix frontend` -> успішно.

## [2026-03-18 16:15] Fix favicon/PWA icon rasterization and transparency
- Оновлено `scripts/generate_frontend_icons.py`: замість прямого browser screenshot сирого SVG generator тепер створює тимчасову HTML-сторінку, рендерить SVG у `canvas` і лише потім знімає PNG, що прибрало кроп, білий фон і неправильне кадрування на малих розмірах.
- Перегенеровано `frontend/public/{favicon.ico,favicon-16x16.png,favicon-32x32.png,apple-touch-icon.png}` та `frontend/public/icons/{icon-192.png,icon-512.png,icon-maskable-192.png,icon-maskable-512.png}`: assets тепер мають коректний full-frame render і alpha transparency (`RGBA`) замість попередніх обрізаних кадрів.
- Verification: `python3 scripts/generate_frontend_icons.py` -> успішно; `npm run build --prefix frontend` -> успішно.

## [2026-03-18 16:17] Refine CarTrap monogram from ambiguous mark to clear C+t
- Оновлено `frontend/public/icons/{cartrap-icon.svg,cartrap-icon-maskable.svg}`: внутрішній помаранчевий знак перемальовано з двозначної форми в просту й чітку `t` з окремою вертикаллю та перекладиною, щоб монограма стабільно читалась як `C + t` на favicon і PWA розмірах.
- Перегенеровано `frontend/public/{favicon.ico,favicon-16x16.png,favicon-32x32.png,apple-touch-icon.png}` та `frontend/public/icons/{icon-192.png,icon-512.png,icon-maskable-192.png,icon-maskable-512.png}` під оновлений знак.
- Verification: `python3 scripts/generate_frontend_icons.py` -> успішно; `npm run build --prefix frontend` -> успішно.

## [2026-03-19 13:14] Add implementation plan for saved-search inbox mobile refresh
- Додано `docs/plans/20260319-saved-search-inbox-mobile-refresh.md` з frontend-only планом редизайну dashboard під mobile saved-search-first usage: компактний header, сендвіч-меню для account actions і secondary full-screen flow для `New Search`.
- У плані зафіксовано обраний UX-напрямок `Saved-first inbox`: `Saved Searches` стають першим екраном, `Open Results` замінюється на tappable title block, quick filters `All / New / Needs refresh` працюють поверх існуючих saved-search metadata без backend contract changes.
- Окремо винесено вимоги до role-aware поведінки: admin system status ховається в account menu, а device-offline/degraded messaging лишається тільки як глобальний actionable state; для кожного task додано явні test expectations і фінальну build/test verification.

## [2026-03-19 13:18] Tighten saved-search inbox plan after self-review
- Оновлено `docs/plans/20260319-saved-search-inbox-mobile-refresh.md` після технічного self-review: додано explicit coordination з `App.tsx` для вимкнення pull-to-refresh під час full-screen `New Search`, щоб новий mobile flow не конфліктував з існуючим touch gesture.
- Уточнено UX-правила, які раніше лишались неявними: `Needs refresh` тепер зафіксований як deterministic UI heuristic (`last_synced_at` відсутній або старший за 24 години), а порожній inbox повинен показувати явний CTA до `New Search`.
- Скориговано role-aware degraded-state scope: dashboard-level live-sync banner більше не вважається частиною цільового UX, натомість admin бачить system status лише в account menu, а non-admin отримує пояснення через offline/error states на рівні конкретних дій.

## [2026-03-19 13:41] Implement saved-search inbox mobile refresh
- Оновлено `frontend/src/{App.tsx,styles.css}` і додано `frontend/src/features/dashboard/AccountMenuSheet.tsx`: hero shell замінено на compact header з hamburger account menu, admin-only system status перенесено в sheet, а dashboard-level degraded live-sync banner прибрано при збереженні глобального offline messaging та pull-to-refresh suppression під час full-screen `New Search`.
- Додано `frontend/src/features/search/ManualSearchScreen.tsx` і суттєво перероблено `frontend/src/features/search/SearchPanel.tsx`: dashboard тепер saved-search-first, підтримує quick filters `All / New / Needs refresh`, tappable title block замість `Open Results`, overflow menu для `Refresh Live / Open URL / Delete`, sticky `New Search` CTA та повернення в inbox після save/cancel.
- Оновлено `frontend/tests/app.test.tsx`: suite переведено на новий mobile flow, додано покриття для account menu, inbox filters/order, overflow actions, title-block open, full-screen manual-search flow і блокування pull-to-refresh під час composer.
- Оновлено `docs/plans/20260319-saved-search-inbox-mobile-refresh.md`: усі task-и позначені виконаними перед переміщенням у `docs/plans/completed/`.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `29 passed`; `npm run test --prefix frontend` -> `29 passed`; `npm run build --prefix frontend` -> успішно.

## [2026-03-19 14:10] Fix mobile header and overlay behavior after saved-search inbox rollout
- Оновлено `frontend/src/features/dashboard/DashboardShell.tsx` і `frontend/src/styles.css`: header зведено в одну компактну поверхню без окремого `USER` pill/block, а кнопка меню інтегрована прямо в header, щоб верхній екран не витрачав висоту на порожню account card.
- Додано `frontend/src/features/shared/useBodyScrollLock.ts` і оновлено `frontend/src/features/search/{ManualSearchScreen.tsx,SearchResultsModal.tsx,SearchPanel.tsx}`: full-screen `New Search` тепер реально локує background scroll, а saved-search results на mobile відкриваються як full-screen surface замість нижнього sheet; scroll lock став reference-counted, щоб вкладені overlays не лишали `body` у заблокованому стані.
- Оновлено `frontend/tests/app.test.tsx`: додано regression coverage для mobile fullscreen saved-search results, body-scroll lock/unlock під час `New Search`, і перевірку що dashboard більше не рендерить окремий `USER` label на верхньому екрані.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `30 passed`; `npm run test --prefix frontend` -> `30 passed`; `npm run build --prefix frontend` -> успішно.

## [2026-03-19 14:19] Fix push settings modal layout on iPhone-sized screens
- Оновлено `frontend/src/features/push/PushSettingsModal.tsx`: settings modal тепер автоматично переходить у mobile full-screen режим на touch-екранах до 900px, використовує body scroll lock і зберігає desktop modal layout без змін.
- Оновлено `frontend/src/styles.css`: додано mobile-специфічну поведінку для `settings-modal` та окремі стилі `push-subscription-card`, щоб довгі `user_agent`/endpoint значення переносились усередині картки й `Revoke` не ламав ширину layout на iPhone.
- Оновлено `frontend/tests/app.test.tsx`: додано regression coverage для mobile settings modal, full-screen class/scroll lock і рендерингу довгої device subscription картки після enable push.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `31 passed`; `npm run build --prefix frontend` -> успішно.

## [2026-03-19 14:28] Compact saved-search fullscreen modal chrome on mobile scroll
- Оновлено `frontend/src/features/search/SearchResultsModal.tsx`: fullscreen results modal тепер рендериться через portal у `document.body`, скидає внутрішній scroll при відкритті й на mobile схлопує title/meta/status chrome після початку scroll, залишаючи зверху лише action menu.
- Оновлено `frontend/src/styles.css`: додано окремий layout для `search-results-modal` з `chrome/body` секціями та mobile collapsed state, щоб results list отримував більше корисної висоти під час scroll без втрати `Refresh Live / Close`.
- Оновлено `frontend/tests/app.test.tsx`: додано regression coverage для fullscreen results modal поза `.app-shell`, collapse/un-collapse header chrome при scroll і тестовий stub `window.scrollTo`, щоб suite залишався чистим у JSDOM.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `32 passed`; `npm run build --prefix frontend` -> успішно.

## [2026-03-19 14:37] Harden mobile overlays and input ergonomics across frontend
- Оновлено `frontend/src/features/search/{ManualSearchScreen.tsx,SearchFiltersModal.tsx}` і додано `frontend/src/features/shared/mobileFullscreen.ts`: mobile overlays тепер визначають coarse-pointer fullscreen mode через shared helper, а `New Search` і `Search Filters` рендеряться через portal у `document.body`, щоб fixed layout не ламався після scroll всередині pull-to-refresh shell.
- Оновлено `frontend/src/features/watchlist/{LotGalleryModal.tsx,WatchlistPanel.tsx}` та `frontend/src/styles.css`: gallery modal також винесено в portal і переведено в mobile fullscreen surface, filter/gallery mobile layouts отримали safe-area-friendly fullscreen стилі, а lot-number input тепер відкриває numeric keyboard без autocorrect noise.
- Оновлено `frontend/src/features/auth/{LoginScreen.tsx,InviteAcceptScreen.tsx}` і `frontend/src/features/search/ManualSearchScreen.tsx`: додано auth autocomplete hints (`email`, `current-password`, `new-password`), вимкнено небажаний mobile autocorrect/spellcheck для make/model search inputs і підсилено numeric year fields через `pattern="[0-9]*"`.
- Оновлено `frontend/tests/app.test.tsx`: додано regression coverage для portal rendering manual-search / filters / gallery overlays у mobile режимі після scroll основного dashboard.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `35 passed`; `npm run build --prefix frontend` -> успішно.

## [2026-03-19 14:42] Fix production-discovered mobile overlay drift for account and settings
- Після live mobile перевірки production `https://cartrapapp.pp.ua/` під user session підтверджено системний drift overlays після dashboard scroll: `Account menu`, `Search filters` і `Gallery` рендерились усередині прокрученого shell замість незалежного mobile surface.
- Оновлено `frontend/src/features/dashboard/AccountMenuSheet.tsx` і `frontend/src/features/push/PushSettingsModal.tsx`: обидва overlays тепер використовують `createPortal(..., document.body)` і `useBodyScrollLock`, тож більше не плавають усередині `app-shell` після mobile scroll.
- Оновлено `frontend/tests/app.test.tsx`: додано regression coverage для mobile account menu та push settings after-scroll portal rendering поза `.app-shell`, щоб production-симптом не повернувся.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `37 passed`; `npm run build --prefix frontend` -> успішно.

## [2026-03-19 15:03] Smooth saved-search mobile header collapse with scroll-linked motion
- Оновлено `frontend/src/features/search/SearchResultsModal.tsx`: замість threshold-based toggle saved-search fullscreen modal тепер використовує scroll-linked collapse offset для mobile intro chrome, тому title/meta/status блок схлопується пропорційно scroll gesture, а не ривком після одного порогу.
- Оновлено `frontend/src/styles.css`: додано окремі `topbar/collapsible` стилі для `search-results-modal`, де верхній action menu лишається pinned, а intro chrome плавно зсувається й згасає в темпі scroll, ближче до поведінки native large-title surfaces.
- Оновлено `frontend/tests/app.test.tsx`: regression тепер перевіряє реальне зменшення/відновлення висоти mobile collapsible chrome під час scroll, а не лише наявність CSS toggle class.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `37 passed`; `npm run build --prefix frontend` -> успішно.

## [2026-03-19 15:12] Remove saved-search mobile scroll jank from React scroll-loop updates
- Оновлено `frontend/src/features/search/SearchResultsModal.tsx`: scroll-linked collapse для mobile saved-search modal більше не проходить через `setState` на кожен `scroll` event; inline `height` і CSS progress var тепер оновлюються напряму через `requestAnimationFrame`, щоб зняти re-render pressure і повернути smooth inertial scroll на iPhone.
- Verification: `npm run test --prefix frontend -- app.test.tsx`; `npm run build --prefix frontend`.

## [2026-03-20 18:59] Add fallback dashboard auto-refresh and hidden-tab attention blinking
- Оновлено `frontend/src/App.tsx`: push лишився fast-path сигналом, але dashboard тепер також сам перечитує `watchlist`, `savedSearches` і `liveSync` кожні 60 секунд, а також одразу після `window.focus` / `visibilitychange`, щоб вже відкрита вкладка підтягувала зміни навіть коли browser push не спрацював.
- Для background refresh додано silent-loading режим і локальний diff попереднього/нового стану; якщо під час прихованої вкладки знаходяться нові зміни у watchlist або saved searches, `document.title` починає блимати між базовим заголовком і повідомленням про оновлення, доки користувач не повернеться у вкладку.
- Оновлено `frontend/tests/app.test.tsx`: додано regression coverage для fallback refresh по `focus` і для hidden-tab polling + blinking title behavior.
- Verification: `npm run test --prefix frontend -- app.test.tsx` -> `40 passed`; `npm run test --prefix frontend` -> `40 passed`; `npm run build --prefix frontend` -> успішно.

## [2026-03-21 17:51] Add implementation plan for operational reliability spine
- Додано `docs/plans/20260321-operational-reliability-spine.md`: зафіксовано рекомендований напрямок `Reliability Spine` для поточного стеку `frontend + backend + worker + NAS gateway` без queue-first rewrite.
- У плані розкладено етапи для shared freshness/degradation contract, explicit refresh execution primitives, separation of cached read-path vs live refresh-path, priority scheduling для near-auction lots, frontend reliability UX і structured observability/diagnostics.
- Для кожного етапу вказано конкретні модулі й тестові набори (`system_status`, `search`, `watchlist`, `monitoring`, `worker`, `App.tsx`, `app.test.tsx`), а також фінальні verification commands для backend/frontend regression.

## [2026-03-21 17:56] Tighten reliability plan to avoid contract and notification regressions
- Оновлено `docs/plans/20260321-operational-reliability-spine.md`: додано additive compatibility bridge для backend/frontend контрактів, щоб `live_sync` і поточні поля `saved search/watchlist` не ламались між Task 1 і Task 5.
- Розширено scope плану на `notifications`, `frontend/public/sw.js`, `copart_gateway` і `copart_provider client`: зафіксовано вимоги до push/reminder dedupe, `refresh_targets` compatibility та gateway-level observability/timeout taxonomy.
- Додано окремі вимоги для legacy watchlist backfill під час розділення `read-path` і `refresh-path`, щоб існуючі incomplete tracked-lot records не втратили media/detail enrichment після reliability refactor.

## [2026-03-21 18:06] Complete Task 1 additive freshness contract bridge
- Додано `backend/src/cartrap/modules/system_status/schemas.py` і оновлено `backend/src/cartrap/modules/system_status/service.py`: виділено спільний `freshness` envelope (`status`, `last_synced_at`, `stale_after`, `degraded_reason`, `retryable`) та helper для additive-serializing без зміни поточного `live_sync` контракту.
- Оновлено `backend/src/cartrap/api/system.py`, `backend/src/cartrap/modules/search/{router.py,schemas.py,service.py}` і `backend/src/cartrap/modules/watchlist/{router.py,schemas.py,service.py}`: `/system/status` тепер повертає `freshness_policies`, а saved-search/watchlist responses отримали explicit `freshness` metadata поверх legacy полів `last_synced_at` / `last_checked_at`.
- Оновлено `frontend/src/{types.ts,lib/api.ts}` і `frontend/tests/app.test.tsx`: frontend API-шар тепер нормалізує новий або legacy payload у спільний shape, а integration suite працює з additive `freshness`/`freshness_policies` без регресії degraded-mode поведінки.
- Оновлено `backend/tests/{test_system_status.py,search/test_search_api.py,watchlist/test_watchlist_api.py}` і `docs/plans/20260321-operational-reliability-spine.md`: додано explicit coverage для live/cached/degraded envelope transitions, позначено Task 1 виконаним і синхронізовано фактичний scope змін.
- Verification: `./.venv/bin/pytest backend/tests/test_system_status.py backend/tests/search/test_search_api.py backend/tests/watchlist/test_watchlist_api.py` -> `39 passed`; `npm --prefix frontend run test -- app.test.tsx` -> `40 passed`; `npm --prefix frontend run build` -> успішно.

## [2026-03-21 18:15] Complete Task 2 refresh runtime primitives and push dedupe
- Додано `backend/src/cartrap/modules/monitoring/job_runtime.py` і оновлено `backend/src/cartrap/modules/{monitoring/service.py,search/service.py,notifications/{models.py,repository.py,service.py}}` та `backend/src/cartrap/worker/main.py`: polling flows тепер проходять через shared `job_runtime` з `execution_key`, lease TTL, attempt counting, retryable backoff і explicit `jobs` outcomes у результатах worker cycle.
- Saved-search і watchlist polling тепер пропускають ресурси з активним lock/backoff замість неявного дублювання виконання; при failure job runtime фіксує `retryable_failure`, а при `not_modified/refreshed` закриває цикл явним `succeeded` outcome.
- Додано per-endpoint notification receipts у `push_delivery_receipts`: повторні `lot_change` і `auction_reminder` delivery для того самого domain event більше не ресендяться при duplicate execution/retry, але transient failures не блокують майбутню повторну спробу.
- Оновлено `backend/tests/{test_worker_main.py,search/test_saved_search_monitoring.py,monitoring/test_change_detection.py,notifications/test_push_delivery.py}` і `docs/plans/20260321-operational-reliability-spine.md`: додано покриття для lock/backoff lifecycle, skip semantics, retryable failures і push/reminder dedupe, а Task 2 позначено виконаним.
- Verification: `./.venv/bin/pytest backend/tests/test_worker_main.py backend/tests/search/test_saved_search_monitoring.py backend/tests/monitoring/test_change_detection.py backend/tests/notifications/test_push_delivery.py` -> `28 passed`; `PYTHONPYCACHEPREFIX=/tmp/python-cache python3 -m compileall backend/src/cartrap/modules/monitoring backend/src/cartrap/modules/search backend/src/cartrap/modules/notifications backend/src/cartrap/worker` -> успішно.

## [2026-03-21 18:21] Complete Task 3 cached read-path and explicit refresh-path split
- Оновлено `backend/src/cartrap/modules/search/{service.py,schemas.py,repository.py}` і `backend/src/cartrap/modules/system_status/schemas.py`: saved searches тепер серіалізують окремий persisted `refresh_state`, а `refresh-live` / worker failure paths зберігають retryable/non-retryable refresh metadata без втрати cached read access.
- Оновлено `backend/src/cartrap/modules/watchlist/{service.py,router.py,schemas.py,repository.py}` та `backend/src/cartrap/modules/monitoring/service.py`: `GET /watchlist` більше не робить hidden upstream backfill, legacy incomplete lots лише ставлять `repair_pending`, background polling бере їх у repair через `repair_requested_at`, а explicit `POST /watchlist/{id}/refresh-live` став окремим refresh-path для manual repair/update.
- Додано cached-vs-refresh regression coverage в `backend/tests/{search/test_search_api.py,search/test_saved_search_monitoring.py,watchlist/test_watchlist_api.py,watchlist/test_snapshot_storage.py,monitoring/test_change_detection.py}`: перевірено retryable refresh failure metadata, cached reads після gateway failure, watchlist read без live fetch, explicit refresh repair і background repair для legacy items.
- Оновлено `docs/plans/20260321-operational-reliability-spine.md`: Task 3 позначено виконаним і синхронізовано фактичний scope файлів після refactor read-path vs refresh-path.
- Verification: `./.venv/bin/pytest backend/tests/search/test_search_api.py backend/tests/watchlist/test_watchlist_api.py backend/tests/watchlist/test_snapshot_storage.py backend/tests/search/test_saved_search_monitoring.py backend/tests/monitoring/test_change_detection.py` -> `54 passed`; `PYTHONPYCACHEPREFIX=/tmp/python-cache python3 -m compileall backend/src/cartrap/modules/search backend/src/cartrap/modules/watchlist backend/src/cartrap/modules/monitoring` -> успішно.

## [2026-03-21 18:39] Sync Task 4 plan state and complete Task 5 reliability UX in the PWA
- Оновлено `docs/plans/20260321-operational-reliability-spine.md`: Task 4 синхронізовано з уже реалізованим backend state (`priority_class`, adaptive near-auction freshness, persisted refresh outcomes), а Task 5 позначено виконаним після фактичної frontend інтеграції.
- Оновлено `frontend/src/{types.ts,lib/api.ts,App.tsx}`: додано shared `refresh_state`/diagnostics типи, legacy-safe нормалізацію payloads, explicit `refreshWatchlistLotLive()` API та app-level diagnostics summary для admin/support surface.
- Оновлено `frontend/src/features/search/{SearchPanel.tsx,SearchResultsModal.tsx}` і `frontend/src/features/watchlist/WatchlistPanel.tsx`: saved searches і tracked lots тепер показують локальні стани `Live/Cached/Refreshing/Degraded/Outdated`, manual refresh flow явно відображає in-flight/success/failure/cached fallback, а watchlist отримав explicit `Refresh Live`.
- Оновлено `frontend/src/features/dashboard/AccountMenuSheet.tsx`, `frontend/public/sw.js` і `frontend/src/styles.css`: admin sheet тепер показує compact refresh backlog summary, service-worker bridge приймає старий і новий shape `refresh_targets`, а UI отримав reliability pills/callouts без зміни глобального `live_sync` banner semantics.
- Оновлено `frontend/tests/app.test.tsx`: додано coverage для per-resource reliability rendering, saved-search/watchlist refresh failure persistence, admin diagnostics і object-shaped push refresh targets compatibility.
- Verification: `npm --prefix frontend run test -- app.test.tsx` -> `45 passed`; `npm --prefix frontend run build` -> успішно.

## [2026-03-21 18:53] Complete Task 6 structured observability and finish reliability plan acceptance
- Оновлено `backend/src/cartrap/{core/logging.py,worker/main.py}` і `backend/src/cartrap/modules/{system_status/service.py,search/service.py,monitoring/service.py,copart_gateway/service.py,copart_provider/client.py}`: додано structured JSON logging з `event`/`correlation_id`, refresh/request/worker/gateway event families, timeout/upstream failure classification і safe formatter-конфігурацію без зламу pytest capture handlers.
- Оновлено `README.md` і `docs/backend-api.md`: задокументовано reliability contract (`freshness`, `refresh_state`, `freshness_policies`), explicit `refresh-live` endpoints і operator-facing structured log families/diagnostics semantics.
- Оновлено `backend/tests/{test_worker_main.py,copart/test_gateway_client_config.py,copart/test_gateway_router.py,copart/test_gateway_backed_services.py,copart/test_http_client.py,search/test_saved_search_cache_repository.py}` та `frontend/tests/app.test.tsx`: додано/підправлено coverage для structured logs, direct-vs-gateway test isolation, gateway-backed due polling, instance-based cache serialization і stabilized saved-search refresh failure assertion.
- Оновлено `docs/plans/20260321-operational-reliability-spine.md`: Task 6, Task 7 і Task 8 позначено виконаними після повної acceptance verification.
- Verification: `./.venv/bin/pytest backend/tests` -> `155 passed`; `npm --prefix frontend run test` -> `45 passed`; `npm --prefix frontend run build` -> успішно.

## [2026-03-21 19:09] Unify resource sync messaging into one reliability block
- Перевірено production `https://cartrapapp.pp.ua/#/login`: saved-search cards, search results modal і watchlist cards дублювали sync-state через окремі `Last synced`/`Last checked` meta rows поруч із reliability pill та `Last successful sync` copy.
- Додано `frontend/src/features/shared/resourceReliability.ts` і оновлено `frontend/src/features/search/{SearchPanel.tsx,SearchResultsModal.tsx}` та `frontend/src/features/watchlist/WatchlistPanel.tsx`: sync-state тепер формується через shared helper і показується тільки в одному compact reliability block; дубльовані `Last synced`/`Last checked` рядки з cards/modals прибрано.
- Оновлено `frontend/tests/app.test.tsx`: додано regression expectations, що saved-search/watchlist surfaces більше не рендерять окремі `Last synced`/`Last checked` labels поруч із reliability block, але зберігають зрозумілий unified `Synced ...` copy.
- Verification: `npm --prefix frontend run test -- app.test.tsx` -> `45 passed`; `npm --prefix frontend run build` -> успішно.

## [2026-03-24 16:30] Add implementation plan for per-user Copart connector V1
- Додано `docs/plans/20260324-copart-per-user-connector-v1.md`: зафіксовано V1-дизайн для `per-user` Copart connector без зберігання пароля після bootstrap, з user-scoped encrypted session bundle, `reconnect_required` state та split відповідальністю між `frontend`, `AWS backend` і `NAS copart-gateway`.
- У плані описано discovery-контекст із поточної архітектури `copart_provider`/`copart_gateway`, висновки з Charles login flow (`SessionID`, Imperva cookies, `x-d-token`, challenge side effects) і конкретні implementation tasks для `provider_connections` domain, gateway bootstrap/execute flow, frontend account UX, worker integration та observability redaction.
- Також зафіксовано testing strategy, acceptance verification і post-completion manual checks для production rollout та secret management на NAS.

## [2026-03-24 16:38] Tighten per-user Copart connector plan after design review
- Оновлено `docs/plans/20260324-copart-per-user-connector-v1.md`: додано `Task 0` для feasibility gate `login -> challenge -> lot-details`, щоб не заходити в повний domain/UI rollout без підтвердження, що Copart native flow стабільно відтворюється server-side.
- План доповнено вимогами до `bundle_version` / compare-and-swap semantics, policy `one active connection per (user, provider)`, явними additive contract changes для `connection_missing` / `reconnect_required` у saved-search/watchlist payloads та config-deliverables для gateway encryption/profile settings.
- Також додано rollout/acceptance пункти для legacy users без конектора, suppression duplicate connector-state noise і post-completion вимогу ротувати Copart credentials/cookies/tokens, які використовувались під час Charles discovery.

## [2026-03-24 18:29] Fix connector bootstrap failure after successful Copart login
- Оновлено `backend/src/cartrap/modules/copart_provider/client.py` і `backend/src/cartrap/config.py`: connector bootstrap тепер seed-ить стартовий `x-d-token` із конфіга в login request і session bundle fallback, `verify` за замовчуванням переведено на реальний `me-info` path, `identity_path` вимкнено за замовчуванням, а mobile connector defaults синхронізовано ближче до реального native profile (`COPART` / `ios` / `en-US` / `6.7.2`).
- Оновлено `backend/src/cartrap/modules/provider_connections/service.py`: `CopartChallengeError` більше не провалюється в неочікуваний `500`; backend повертає керований `502 Bad Gateway` із явним bootstrap/challenge detail.
- Оновлено `backend/tests/{copart/test_http_client.py,provider_connections/test_router.py}`: додано regression coverage для bootstrap без `x-d-token` у login response headers та для router mapping challenge failure -> `502`.
- Verification: `./.venv/bin/pytest backend/tests/copart/test_http_client.py backend/tests/provider_connections/test_router.py backend/tests/test_config.py` -> `16 passed` (є лише `urllib3` `LibreSSL` warning у локальному Python runtime).

## [2026-03-24 18:41] Surface invalid connector encryption key after successful bootstrap
- Оновлено `backend/src/cartrap/modules/copart_gateway/service.py`: `Fernet(...)` build для `COPART_CONNECTOR_ENCRYPTION_KEY` тепер обгорнуто в явний `CopartConfigurationError`, щоб bootstrap не падав безіменним `500` після успішних `login` і `me-info`.
- Оновлено `backend/tests/copart/test_gateway_connector_flow.py`: додано regression coverage для невалідного `COPART_CONNECTOR_ENCRYPTION_KEY`, яка перевіряє, що gateway повертає керований `500` з detail `COPART_CONNECTOR_ENCRYPTION_KEY is invalid.`.
- Verification: `./.venv/bin/pytest backend/tests/copart/test_gateway_connector_flow.py` -> `3 passed`.

## [2026-03-24 18:56] Align connector login bootstrap with native Copart profile and upstream rejection mapping
- Оновлено `backend/src/cartrap/modules/copart_provider/{client.py,errors.py}` і `backend/src/cartrap/config.py`: connector bootstrap тепер шле ближчий до Charles native login shape (`keepSession`, `anonymousCrmId`, `loginLocationInfo`, `ins-sess`, `Accept-Language`, mobile `User-Agent`), генерує UUID-подібні `deviceid/ins-sess` і відокремлює `403` login profile rejection від реального `401 invalid credentials` через новий `CopartLoginRejectedError`.
- Оновлено `backend/src/cartrap/modules/{copart_gateway/router.py,provider_connections/service.py}`: `Copart` bootstrap `403` тепер прокидається як `502 upstream_rejected` / `Copart rejected connector bootstrap request.`, а не як помилковий `401 Copart credentials were rejected.`.
- Оновлено `backend/tests/{copart/test_http_client.py,copart/test_gateway_connector_flow.py,provider_connections/test_router.py}`: додано regression coverage для native-style bootstrap payload/headers, direct `403 -> CopartLoginRejectedError`, gateway `upstream_rejected` mapping і backend `502` router mapping.

## [2026-03-24 19:09] Forward external client IP through Copart connector bootstrap
- Оновлено `backend/src/cartrap/modules/{provider_connections/router.py,provider_connections/service.py,copart_gateway/{schemas.py,service.py,router.py},copart_provider/client.py}`: connect/reconnect flow тепер витягує зовнішній IP із `CF-Connecting-IP` / `X-Forwarded-For` / `X-Real-IP` на AWS, прокидає його через gateway bootstrap і підставляє в Copart login як `ip_address` header та `loginLocationInfo.ip`.
- Це зберігає поточний frontend API без змін форми, але дає Copart реальніший login context замість порожнього `ip_address`, що було одним із головних кандидатів на `403 Forbidden` з native login replay.
- Оновлено `backend/tests/{copart/test_http_client.py,copart/test_gateway_connector_flow.py,provider_connections/test_router.py}`: додано regression coverage для прокидування `client_ip` у gateway payload, direct bootstrap headers/body і extraction з proxy headers у connect router.
- Verification: `./.venv/bin/pytest backend/tests/copart/test_http_client.py backend/tests/copart/test_gateway_connector_flow.py backend/tests/provider_connections/test_router.py backend/tests/test_config.py` -> `23 passed` (є лише `urllib3` `LibreSSL` warning у локальному Python runtime).

## [2026-03-25 17:58] Harden IAAI gateway bootstrap with Imperva replay and step diagnostics
- Оновлено `backend/src/cartrap/modules/iaai_provider/{client.py,errors.py}` і `backend/src/cartrap/config.py`: IAAI bootstrap тепер має explicit step taxonomy (`oidc_metadata`, `authorize`, `login_page`, `imperva_preflight`, `login_submit`, `authorize_callback`, `token_exchange`), реплеїть captured Imperva `/A-would-they-here-beathe-and-should-mis-fore-Cas` GET+POST flow, зберігає anti-bot cookies у session bundle, жорсткіше валідовує bundle completeness перед execute і вирівнює mobile header defaults ближче до native iOS профілю (`IAA-Buyer-App-iOS`, `295`).
- Оновлено `backend/src/cartrap/modules/iaai_gateway/{router.py,schemas.py,service.py}` і `backend/src/cartrap/modules/provider_connections/service.py`: AWS тепер прокидає correlation id у `iaai-gateway`, NAS логує той самий trace id і повертає safe diagnostics (`x-iaai-correlation-id`, `x-iaai-bootstrap-step`, `x-iaai-failure-class`, `x-iaai-upstream-status`), а provider-connections мапить їх у керований backend error без витоку секретів.
- `client_ip` для IAAI bootstrap свідомо не використовується в upstream replay: IAAI все одно бачить NAS egress IP, тому synthetic forwarding не дає реалістичнішого browser/mobile context і лише розмиває діагностику.
- Оновлено `backend/tests/{iaai/test_http_client.py,iaai/test_gateway_client_config.py,iaai/test_gateway_connector_flow.py,provider_connections/test_iaai_router.py}` та `README.md`, `docs/plans/{20260325-iaai-multi-auction-support.md,20260325-iaai-gateway-bootstrap-hardening.md}`: додано regression coverage для Imperva preflight carry-over, callback follow-up, gateway diagnostics propagation, stale/incomplete bundle rejection і синхронізовано операторську документацію/план hardening.
- Verification: `./.venv/bin/pytest backend/tests/iaai/test_http_client.py backend/tests/iaai/test_gateway_router.py backend/tests/iaai/test_gateway_client_config.py backend/tests/iaai/test_gateway_connector_flow.py backend/tests/provider_connections/test_iaai_router.py` -> `19 passed` (є лише `urllib3` `LibreSSL` warning у локальному Python runtime).

## [2026-03-25 18:01] Archive completed IAAI gateway hardening plan
- Переміщено `docs/plans/20260325-iaai-gateway-bootstrap-hardening.md` у `docs/plans/completed/20260325-iaai-gateway-bootstrap-hardening.md` після фактичного завершення всіх задач і verification.
- Поточний активний planning context залишився в `docs/plans/20260325-iaai-multi-auction-support.md`, а hardening-план зафіксовано як completed artifact для подальшого rollout/smoke-test follow-up.

## [2026-03-25 18:10] Add NAS-oriented IAAI Imperva diagnostics and script-token fallback
- Оновлено `backend/src/cartrap/modules/iaai_provider/client.py`: додано safe bootstrap telemetry `iaai_client.bootstrap.state` з cookie names, set-cookie names, response status/content-type/body-length без витоку cookie values; `imperva_preflight` тепер логуватиме точніший `hint`, а також має fallback на випадок, коли Imperva token не потрапив у cookie jar, але присутній у body script response.
- Оновлено `backend/src/cartrap/modules/iaai_gateway/service.py` і `backend/src/cartrap/modules/provider_connections/service.py`: gateway/AWS failure logs тепер включають `hint`, `step` і `failure_class`, щоб з production NAS логів було видно не лише факт падіння, а й sanitized причину на кшталт `missing_reese84_cookie_after_script_get`.
- Оновлено `backend/tests/iaai/test_http_client.py`: додано regression coverage для fallback `script body -> Imperva token` і синхронізовано expectation для нового diagnostic hint.
- Verification: `./.venv/bin/pytest backend/tests/iaai/test_http_client.py backend/tests/iaai/test_gateway_connector_flow.py backend/tests/provider_connections/test_iaai_router.py` -> `13 passed` (є лише `urllib3` `LibreSSL` warning у локальному Python runtime).

## [2026-03-25 18:10] Add browser-assisted IAAI bootstrap fallback for NAS gateway
- Оновлено `backend/src/cartrap/modules/iaai_provider/client.py`: якщо `httpx` bootstrap зупиняється на `imperva_preflight` з `missing_reese84_cookie_after_script_get` або `missing_imperva_post_state`, gateway тепер може перейти в Playwright/Chromium fallback, пройти реальний browser login flow, зібрати cookies із browser context і завершити token exchange без зміни AWS-side contract.
- Оновлено `backend/src/cartrap/config.py`, `backend/pyproject.toml` і `backend/Dockerfile`: додано runtime knobs `IAAI_BROWSER_BOOTSTRAP_*`, runtime dependency `playwright` і інсталяцію Chromium у backend/gateway image, щоб NAS `iaai-gateway` мав все необхідне для browser-assisted bootstrap.
- Оновлено `backend/tests/iaai/test_http_client.py` і `README.md`: додано regression coverage, що при imperva-cookie blocker client переключається на browser bootstrap path, та задокументовано новий NAS fallback/runtime expectations.
- Verification: `./.venv/bin/pytest backend/tests/iaai/test_http_client.py backend/tests/iaai/test_gateway_connector_flow.py backend/tests/provider_connections/test_iaai_router.py` -> `14 passed` (є лише `urllib3` `LibreSSL` warning у локальному Python runtime).
## [2026-03-25 18:33] Tolerate alternative IAAI lot-details payload shapes from connector flow
- Оновлено `backend/src/cartrap/modules/iaai_provider/normalizer.py`: `normalize_lot_details_payload()` і image extraction більше не вимагають тільки top-level `inventoryResult`; тепер підтримуються direct inventory payloads і типові nested wrappers (`data`, `result`, `payload`, `inventory`, `inventoryDetails`) з authenticated `GetInventoryDetails` responses.
- Оновлено `backend/tests/iaai/test_normalizer.py`: додано regression coverage для direct inventory-root shape і nested `data` wrapper, щоб watchlist/add-by-stock-number flow не ламався на `200 OK` payload без явного `inventoryResult`.
## [2026-03-25 18:40] Make IAAI lot-details payload discovery recursive across unknown wrappers
- Оновлено `backend/src/cartrap/modules/iaai_provider/normalizer.py`: `resolve_inventory_result()` більше не покладається на фіксований перелік wrapper keys; тепер payload discovery рекурсивно проходить кілька рівнів dict/list envelope-ів і знаходить inventory payload навіть у capitalized або нетипових wrapper structures.
- Оновлено `backend/tests/iaai/test_normalizer.py`: додано regression coverage для глибоко вкладеного `Data -> InventoryDetails -> Result` shape, щоб backend не ламався на продових варіантах `GetInventoryDetails` envelope.
## [2026-03-25 18:57] Resolve IAAI stock numbers to inventory ids before lot-details fetch
- Оновлено `backend/src/cartrap/modules/iaai_provider/service.py`: `fetch_lot_conditional()` більше не ріже market suffix із `inventoryId` (`45107325~US`) і, коли digit-only reference виявляється `stockNumber`, робить fallback lookup через `mobilesearch` (`fullSearch`) для резолву `stockNumber -> inventoryId`, а вже потім повторює `GetInventoryDetails`.
- Додано `backend/tests/iaai/test_service.py`: regression coverage для збереження `inventoryId` suffix і retry-path `stockNumber -> search lookup -> GetInventoryDetails(inventoryId)`, що відтворює зафіксований у `Temp/Login-flow-iaai` mapping `44610371 -> 45107325~US`.
## [2026-03-25 19:21] Map real IAAI lot-details trace shape into watchlist snapshot fields
- Оновлено `backend/src/cartrap/modules/iaai_provider/normalizer.py`: `normalize_lot_details_payload()` тепер підтримує реальний `GetInventoryDetails` shape з `Temp/Login-flow-iaai`, де `vehicleInformation`, `vehicleDescription` і `saleInformation` приходять списками `key/label/value`, `attributes.Id` є справжнім `inventoryId`, а дати мають mobile-format `3/26/2026 5:00:00 PM +00:00`.
- Також оновлено image/VIN/detail extraction для IAAI: thumbnail і gallery тепер беруться з `imageInformation.images.{ThumbnailImages,StandardImages}` або `imageDimensions.keys[*].k`, збережено backward-compatible `baseUrl + key` path для старих тестових payloadів, а snapshot наповнюється `title`, `odometer`, `primary_damage`, `estimated_retail_value`, `has_key`, `drivetrain`, `vin`, `sale_date` і branch metadata.
- Оновлено `backend/tests/iaai/test_normalizer.py`: додано regression coverage на payload shape з live trace (`Id=...~US`, row-lists, imageInformation, slash-format datetime), щоб watchlist cards більше не створювались із порожніми IAAI detail fields після успішного add-by-stock-number.
- Verification: `./.venv/bin/pytest backend/tests/iaai/test_normalizer.py backend/tests/iaai/test_service.py backend/tests/iaai/test_gateway_connector_flow.py backend/tests/provider_connections/test_iaai_router.py` -> `15 passed` (є лише `urllib3` `LibreSSL` warning у локальному Python runtime).
## [2026-03-25 19:36] Resolve IAAI item-id style references before retrying lot-details
- Оновлено `backend/src/cartrap/modules/iaai_provider/service.py`: fallback після `GetInventoryDetails` без `inventoryResult` більше не припускає, що digit-only reference завжди є `stockNumber`; lookup через `mobilesearch` тепер матчить `stockNumber`, `itemId`, `salvageId`, `inventoryId` та `id` без market suffix, а потім повторює `lot-details` з resolved `inventoryId`.
- Оновлено `backend/tests/iaai/test_service.py`: додано regression coverage для production-like кейсу `62993275 -> 45107325~US`, де початковий reference є `itemId`, а не `stockNumber`, тому watchlist refresh/add має доходити до другого `GetInventoryDetails` замість падіння після одного `search`.
- Verification: `./.venv/bin/pytest backend/tests/iaai/test_service.py backend/tests/iaai/test_normalizer.py backend/tests/iaai/test_gateway_connector_flow.py backend/tests/provider_connections/test_iaai_router.py` -> `16 passed` (є лише `urllib3` `LibreSSL` warning у локальному Python runtime).

## [2026-03-27 13:22] Fix IAAI search payload mapping and result titles
- Оновлено `backend/src/cartrap/modules/search/schemas.py`: `SearchRequest.to_iaai_payload()` більше не шле внутрішній `{keyword, filters}` shape в `mobilesearch/search`; тепер формується native IAAI payload із `searches[]`, `facets`, `longRanges`, `AuctionDateTime` sort і timestamp fields, а також є fallback на витяг `make/model` із `make_filter` / `model_filter` для mixed-provider saved-search criteria.
- Оновлено `backend/src/cartrap/modules/iaai_provider/normalizer.py`: IAAI search result normalizer тепер підтримує і flat `vehicles[]`, і authenticated `results[].data` payload shapes, а `title` будується з `year/make/model/series`, щоб API більше не показував `CLEAR-*` / `SALVAGE-*` замість реальної машини.
- Оновлено `backend/tests/{search/test_search_api.py,iaai/test_normalizer.py}`: додано regression coverage для native IAAI search payload builder, fallback parsing catalog filters і auth-style search response normalization з vehicle title `2025 FORD MUSTANG MACH-E GT`.
- Verification: `./.venv/bin/pytest backend/tests/search/test_search_api.py backend/tests/iaai/test_normalizer.py` -> `32 passed` (є лише `urllib3` `LibreSSL` warning у локальному Python runtime).

## [2026-03-27 13:39] Fix multi-provider total result aggregation
- Оновлено `backend/src/cartrap/modules/search/service.py`: multi-provider `total_results` більше не рахується через `max(...)`; тепер backend сумує `num_found` по кожному успішному provider, тому одночасний пошук по Copart + IAAI повертає повний count замість фактично лише більшого з двох значень.
- У тому ж сервісі синхронізовано single-provider error detail у `fetch_result_count()`, щоб background poll зберігав provider-specific повідомлення на кшталт `Failed to fetch search results from Copart.` замість generic тексту.
- Оновлено `backend/tests/search/test_search_api.py`: додано regression coverage для multi-provider search, яка перевіряє `120 + 35 -> total_results=155`.
- Verification: `./.venv/bin/pytest backend/tests/search/test_search_api.py backend/tests/search/test_saved_search_monitoring.py` -> `34 passed` (є лише `urllib3` `LibreSSL` warning у локальному Python runtime).

## [2026-03-27 13:39] Speed up backend Docker rebuilds with stable dependency layers
- Оновлено `backend/Dockerfile`: dependency install і `playwright install --with-deps chromium` винесені в окремий шар, який залежить лише від `backend/{pyproject.toml,setup.py,README.md}`, а application install тепер окремо копіює тільки `backend/src` і ставиться через `pip install --no-deps /app/backend`.
- Додано `docker/dockerfile` BuildKit syntax і `--mount=type=cache,target=/root/.cache/pip`, щоб повторні білди не качали Python dependencies з нуля, а зміни в коді більше не інвалідовували дорогий Chromium layer.
- Очікуваний ефект: при зміні лише backend source має перевиконуватись фінальний lightweight install layer, тоді як кроки `pip install` залежностей і `python -m playwright install --with-deps chromium` мають братись із cache.
- Verification: docker build локально не проганяв; зміна обмежена `Dockerfile` layer ordering і BuildKit cache semantics.

## [2026-03-27 13:57] Move provider connectors into Settings and collapse connected forms
- Оновлено `frontend/src/features/{dashboard/AccountMenuSheet.tsx,push/PushSettingsModal.tsx,integrations/ProviderConnectionCard.tsx}`: картки Copart/IAAI перенесено з account menu у `Settings`, а для `connected` стану форма логіну більше не показується, лишаються статусні деталі та `Disconnect`; після disconnect картка повертається до connect-режиму з полями вводу.
- Оновлено `frontend/src/{App.tsx,styles.css}` і `frontend/src/features/{dashboard/DashboardShell.tsx,search/SearchPanel.tsx}`: синхронізовано нові пропси/settings layout, нейтральні стилі для connector cards і всі user-facing підказки, де reconnect раніше відсилав у Account.
- Оновлено `frontend/tests/app.test.tsx`: додано regression coverage, що конектори більше не рендеряться в account menu, у `Settings` для активного Copart-конектора ховається connect-форма, а після `Disconnect` вона з’являється назад.
- Verification: `cd frontend && npm test && npm run build` -> `51 passed`, production build успішний.

## [2026-03-27 14:05] Collapse expiring IAAI sessions in connector settings
- Оновлено `frontend/src/features/integrations/ProviderConnectionCard.tsx`: compact connector state тепер застосовується не лише до `connected`, а й до `expiring`, бо така сесія ще придатна для live actions і не повинна показувати login form до явного `Disconnect`.
- Оновлено `frontend/tests/app.test.tsx`: додано regression coverage для IAAI-конектора зі статусом `expiring`, щоб у `Settings` лишалися тільки статус, метадані та `Disconnect`.

## [2026-03-27 14:35] Rewrite UI copy in more user-friendly language
- Оновлено `frontend/src/features/{shared/resourceReliability.ts,search/{SearchPanel.tsx,SearchResultsModal.tsx,ManualSearchScreen.tsx},watchlist/WatchlistPanel.tsx,integrations/ProviderConnectionCard.tsx,push/PushSettingsModal.tsx,dashboard/{AccountMenuSheet.tsx,DashboardShell.tsx},auth/LoginScreen.tsx,admin/AdminSearchCatalogPanel.tsx}` і `frontend/src/App.tsx`: прибрано внутрішній технічний жаргон (`priority_class`, `cached`, `degraded`, `refresh diagnostics`, `reconnect required`, `live sync` тощо) з user-facing copy, замінено на простіші пояснення й дружніші назви кнопок/статусів.
- Окремо замаплено внутрішні urgency values на зрозумілі підписи в saved searches: `auction_imminent -> Sale coming up`, `recently_changed -> Recent changes`, `normal -> Normal`, `cold -> Low`, `manual -> Just updated`, а лейбл `Priority` замінено на `Update urgency`.
- Додатково дочищено copy у `Settings`/connections: `connector` замінено на `account`, push permission status тепер відображається як `Allowed/Blocked/Not chosen yet`, а non-admin/admin notification labels синхронізовано з більш людяними текстами.
- Оновлено `frontend/tests/app.test.tsx` під новий copy-pass, щоб regression suite перевіряв фінальні user-facing тексти замість старого технічного wording.
- Verification: `cd frontend && npm test && npm run build` -> `52 passed`, production build успішний.
