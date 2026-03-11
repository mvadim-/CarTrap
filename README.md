# CarTrap

CarTrap is a Docker-based PWA and Python backend for tracking Copart lots, managing invite-only access, and delivering browser push notifications when tracked auction data changes.

## MVP Scope
- Invite-based onboarding with `admin` and `user` roles
- Manual Copart search from the app
- Watchlist management for tracked lots
- Adaptive polling before auction start
- Web Push notifications for significant lot changes

## Repository Layout
- `backend/` - FastAPI application, worker, shared Python code, tests
- `frontend/` - PWA client and frontend test setup
- `docs/plans/` - implementation plans and progress tracking

## Local Development
1. Copy `.env.example` to `.env`.
2. Create a local virtual environment with `python3 -m venv .venv`.
3. Activate it with `source .venv/bin/activate`.
4. Install backend dependencies with `pip install -e ./backend[dev]`.
5. Start the stack with `docker compose up --build`.
6. Backend will be available on `http://localhost:8000`.
7. Frontend will be available on `http://localhost:5173`.
8. MongoDB will be available on `mongodb://localhost:27017`.

## Services
- `mongodb` - primary database
- `backend` - API container
- `worker` - background jobs container
- `frontend` - Vite-based PWA container

## Initial Commands
- Backend tests: `source .venv/bin/activate && pytest backend/tests`
- Frontend tests: `npm --prefix frontend run test`
- Full stack: `docker compose up --build`
