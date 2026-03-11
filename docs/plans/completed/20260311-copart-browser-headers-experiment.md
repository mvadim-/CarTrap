# Copart Browser-Like Request Experiment

## Goal
- Перевірити гіпотезу, що Copart server-side anti-bot може послабитися при більш browser-like HTTP profile.

## Scope
- Розширити `CopartHttpClient` browser-like headers.
- Додати warmup request на homepage для отримання стартових cookies/session context.
- Додати isolation tests без live мережі.

## Verification
- `./.venv/bin/pytest backend/tests/copart/test_http_client.py`

## Outcome
- Client тепер робить session warmup на `https://www.copart.com/`
- Target request іде з `Referer: https://www.copart.com/`
- Додано browser-like header набір і optional HTTP/2, якщо в runtime доступний пакет `h2`
- Експеримент не гарантує обхід Imperva; це лише контрольна перевірка гіпотези
