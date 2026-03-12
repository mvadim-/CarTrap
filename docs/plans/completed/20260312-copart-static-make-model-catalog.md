# 2026-03-12 Copart Static Make-Model Catalog

## Goal
- Побудувати статичний `make -> models` каталог для майбутнього оновлення `Manual Copart Search`.
- Взяти за джерело Copart `keywords` payload, але не покладатися лише на нього, бо він не містить явного foreign key між виробником і моделлю.
- Підготувати артефакт, який можна перевипускати вручну через скрипт і коригувати локальними overrides.

## Decisions
- Використати `111/mcs/v2/public/data/search/keywords` лише як джерело Copart keyword-ів.
- Валідувати make/model відповідності через офіційний NHTSA vPIC API (`GetModelsForMake`).
- Зводити alias-и виробників (`TOYO`/`TOYOTA`, `HOND`/`HONDA`) в один canonical make.
- Зберігати окремий файл ручних overrides для очевидних, але двозначних моделей.
- Не комітити raw network captures з `111/`; комітити лише похідний JSON-каталог і генератор.

## Deliverables
- `backend/src/cartrap/modules/search/catalog_builder.py`
- `scripts/generate_copart_make_model_catalog.py`
- `backend/src/cartrap/modules/search/data/copart_make_model_catalog.json`
- `backend/src/cartrap/modules/search/data/copart_make_model_overrides.json`
- `backend/tests/search/test_catalog_builder.py`

## Validation
- `./.venv/bin/pytest backend/tests/search`
- ручна перевірка generated summary та кількох make/model прикладів (`Ford`, `Toyota`, `Honda`, `Tesla`)

## Outcome
- Згенеровано статичний каталог із 369 canonical makes, 547 model keywords, 231 assign-нутими моделями і 315 `unassigned_models`.
- Каталог уже придатний як база для dropdown-ів `Make` / `Model`.
- Ручні винятки винесені в окремий JSON overrides-файл, тож каталог можна розвивати без зміни коду генератора.
