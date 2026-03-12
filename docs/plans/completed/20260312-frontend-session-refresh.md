# Frontend Session Refresh

## Goal
- Прибрати спорадичні `401 Unauthorized` у PWA, коли access token протухає під час активної сесії.

## Scope
- Додати refresh-on-401 у frontend API client
- Синхронізувати оновлені токени назад у session state
- Робити явний logout і redirect на login, якщо refresh не вдається

## Verification
- `npm --prefix frontend run test -- --run tests/app.test.tsx`
- `npm --prefix frontend run build`

## Outcome
- Захищені API запити автоматично пробують `/api/auth/refresh` один раз після `401`
- Нові токени зберігаються в `localStorage` і в React session state
- Якщо refresh не вдається, користувач повертається на login з явним повідомленням про завершення сесії
