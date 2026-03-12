# CarTrap

CarTrap is a Docker-based PWA and Python backend for tracking Copart lots, managing invite-only access, and delivering browser push notifications when tracked auction data changes.

## MVP Scope
- Invite-based onboarding with `admin` and `user` roles
- Manual Copart search from the app via Copart JSON API
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
7. Frontend will be available on `http://localhost:5173` from Vite during local dev, or `http://localhost:4173` from the containerized static build.
8. MongoDB will be available on `mongodb://localhost:27017`.
9. If frontend is opened from another origin, add it to `BACKEND_CORS_ORIGINS` in `.env`.
10. Configure Copart API headers in `.env`: `COPART_API_DEVICE_NAME`, `COPART_API_D_TOKEN`, `COPART_API_COOKIE`, and optionally override `COPART_API_BASE_URL`, `COPART_API_SEARCH_PATH`, `COPART_API_SITECODE`.
11. If you use direct lot lookup, `COPART_API_LOT_DETAILS_PATH` defaults to `/lots-api/v1/lot-details?services=bidIncrementsBySiteV2`.

## Services
- `mongodb` - primary database
- `backend` - API container
- `worker` - background jobs container
- `frontend` - static PWA served by nginx after a Vite production build

## Initial Commands
- Backend tests: `source .venv/bin/activate && pytest backend/tests`
- Frontend tests: `npm --prefix frontend run test`
- Frontend production build: `npm --prefix frontend run build`
- Full stack: `docker compose up --build`
- Rebuild static Copart make/model catalog: `python3 scripts/generate_copart_make_model_catalog.py --keywords /path/to/keywords`

## Docker Notes
- `backend` and `worker` share the same Python image build and differ only by command.
- `frontend` is built with Vite and served from nginx on port `4173`.
- `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` seed the first admin user on API startup.
- `BACKEND_CORS_ORIGINS` controls which browser origins may call the API; local defaults cover `localhost` and `127.0.0.1` on ports `5173` and `4173`.
- Copart integration now uses the JSON API on `mmember.copart.com`; HTML scraping and page parsing are no longer used.
- Static make/model catalog generation lives in `scripts/generate_copart_make_model_catalog.py`, with manual fixes in `backend/src/cartrap/modules/search/data/copart_make_model_overrides.json`.

## Current Status
- MVP backend flows are implemented: invite auth, roles, Copart API integration, watchlist, search, monitoring, and push subscription management.
- MVP frontend flows are implemented: login, invite acceptance, admin invite creation, manual search, watchlist, and client-side push registration UX.
- Docker images for `backend`, `worker`, and `frontend` are buildable and the compose stack passes a basic smoke check.

## Latest Verification
- `./.venv/bin/pytest backend/tests`
- `npm --prefix frontend run test`
- `npm --prefix frontend run build`
- `docker compose build backend frontend worker`
- `docker compose up -d`
- `curl http://localhost:8000/api/health`
- `curl -I http://localhost:5173`
