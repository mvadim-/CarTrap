# Repository Guidelines

# Role & Workflow Prompt
- Працюєш як Solution Architect / асистент розробника. Спілкування, планування й мислення — українською; усі термінальні команди виконуються англійською.
- Якщо тобі щось не зрозуміло то дай мені знати роби на свій розсуд.
- Перед стартом перевіряй останній блок у `ChangeLog.md`, щоби знати контекст.
- Кожен цикл змін → окремий запис у `ChangeLog.md` (формат `## [YYYY-MM-DD HH:MM] ...` + перелік файлів/ключових пунктів).
- Будь-які зміни коду чи конфігурацій фіксуй у `ChangeLog.md`.
- Після кожного завершеного циклу змін для багфикса, рефакторингу або нової фічі обов'язково роби окремий `git commit` з коротким імперативним повідомленням.
- Після кожного завершеного циклу змін у фінальній відповіді обов'язково давай короткі інструкції для production deploy, прив'язані до сервісів, яких торкнулися зміни.
- Мапінг production deploy такий: `backend`, `worker`, `frontend` деплояться на AWS; `copart-gateway` і `iaai-gateway` деплояться на NAS.
- Якщо зміни торкаються shared Python image, `backend/Dockerfile`, спільних backend-модулів для gateway flow або будь-якого коду, який виконується і на AWS, і на gateway, у фінальній відповіді треба явно сказати, що потрібен деплой і на AWS, і на NAS.
- Для AWS-частини за замовчуванням орієнтуйся на `docs/private/aws-server-admin.md`: `ssh ubuntu@<aws-host>`, `cd /opt/cartrap`, `git pull --ff-only`, `docker compose build backend frontend worker`, `docker compose up -d`, `docker compose ps`, `curl http://127.0.0.1:8000/api/health`, `curl -I https://cartrapapp.pp.ua`.
- Для NAS-частини давай команди, прив'язані до змінених gateway service names: `copart-gateway` і/або `iaai-gateway`; мінімальний шаблон: зайти на NAS host, перейти в `/opt/cartrap`, `git pull --ff-only`, `docker compose build <service>`, `docker compose up -d <service>`, `docker compose ps`, перевірити логи відповідного gateway.


## Project Structure & Module Organization
This repository is currently a minimal baseline: the root contains [`LICENSE`](/Users/mvadym/Documents/Dev/CarTrap/LICENSE), [`.gitignore`](/Users/mvadym/Documents/Dev/CarTrap/.gitignore), and this guide. The ignore rules are Python-focused, so new application code should follow a conventional layout as the project grows:

- `src/` for runtime code
- `tests/` for automated tests
- `docs/` for design notes and plans
- `assets/` for static project resources

Keep modules small and organized by feature. Prefer names like `src/cartrap/<feature>.py` and `tests/test_<feature>.py`.

## Build, Test, and Development Commands
No build or test tooling is committed yet. When adding it, keep the entry points simple and document them in the repository root. Preferred Python defaults:

- `python -m venv .venv` to create a local virtual environment
- `source .venv/bin/activate` to activate it
- `pytest` to run the test suite
- `ruff check .` to run linting
- `ruff format .` to apply formatting

If you introduce a task runner such as `make`, `tox`, or `uv`, keep command names short and predictable.

## Coding Style & Naming Conventions
Use 4-space indentation and standard Python naming:

- `snake_case` for files, functions, and variables
- `PascalCase` for classes
- `UPPER_SNAKE_CASE` for constants

Prefer type hints on public functions. Keep functions focused and avoid large multi-purpose modules. Use Ruff for linting and formatting if you add tooling.

## Testing Guidelines
Place tests in `tests/` and mirror the source layout. Name files `test_<module>.py` and test functions `test_<behavior>()`. Add tests with each feature or bug fix. Favor fast, isolated unit tests first; add integration coverage only where behavior crosses module boundaries.

## Commit & Pull Request Guidelines
The current history starts with `Initial commit`, so no strict convention exists yet. Use short, imperative commit subjects such as `Add vehicle lookup service` or `Fix test fixture cleanup`.

For pull requests, include:

- a clear summary of the change
- linked issue or task reference when available
- test evidence (`pytest`, lint output, or both)
- screenshots only for UI-facing changes

## Security & Configuration Tips
Do not commit local environments, secrets, or generated artifacts. `.gitignore` already excludes common Python caches, virtual environments, coverage outputs, and `.env` files; keep sensitive configuration in local-only files.
