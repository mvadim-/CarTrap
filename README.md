# CarTrap

CarTrap is a Docker-based PWA and Python backend for tracking Copart lots, managing invite-only access, and delivering browser push notifications when tracked auction data changes.

## MVP Scope
- Invite-based onboarding with `admin` and `user` roles
- Manual Copart search from the app via Copart JSON API, with modal result review
- Backend-served Copart make/model catalog with admin-triggered refresh
- Saved manual searches with one-click rerun from the dashboard
- Watchlist management for tracked lots, including Copart thumbnails and lot photo gallery modal
- Adaptive polling before auction start
- Web Push notifications for significant lot changes
- Auction reminder push notifications at 60 minutes, 15 minutes, and auction start

## Repository Layout
- `backend/` - FastAPI application, worker, shared Python code, tests
- `frontend/` - PWA client and frontend test setup
- `docs/plans/` - implementation plans and progress tracking

## Deployment Model
- `backend` on AWS remains the primary API for auth, Mongo-backed state, worker polling, notifications, and frontend traffic.
- `copart-gateway` on NAS is a narrow raw-JSON proxy to Copart. AWS calls NAS over HTTP(S) with bearer auth and keep-alive.
- AWS does not fall back to direct Copart access. If NAS sync is degraded, the app serves cached Mongo-backed data and `/api/system/status` exposes `live_sync.status=degraded`.
- Saved searches and watchlist items expose additive `freshness` and `refresh_state` metadata so the PWA can distinguish `Live`, `Cached`, `Refreshing/repair pending`, and `Outdated` states per resource instead of relying on one global banner.

## Reliability Model
- Ordinary dashboard reads are cache-backed. `GET /api/search/saved` and `GET /api/watchlist` return the latest persisted snapshot even when live upstream refresh fails.
- Explicit live refreshes now run through dedicated endpoints: `POST /api/search/saved/{saved_search_id}/refresh-live` and `POST /api/watchlist/{tracked_lot_id}/refresh-live`.
- `/api/system/status` remains the global backend/gateway health surface and now also returns `freshness_policies` so the frontend can interpret stale windows without hardcoded thresholds.
- Worker refresh execution uses per-resource runtime metadata with lease/backoff semantics to avoid duplicate concurrent refreshes and to preserve single-delivery push/reminder behavior.
- Structured JSON logs are emitted across request, refresh, worker, and gateway flows with `event` + `correlation_id`, which makes it practical to separate upstream NAS failures from primary-backend logic failures.

## Local Development
1. Copy `.env.example` to `.env`.
2. Create a local virtual environment with `python3 -m venv .venv`.
3. Activate it with `source .venv/bin/activate`.
4. Install backend dependencies with `pip install -e ./backend[dev]`.
5. Start the stack with `docker compose up --build`.
6. Backend will be available on `http://localhost:8000`.
7. Frontend will be available on `http://localhost:5173` from Vite during local dev, or `http://localhost:4173` from the containerized static build.
8. MongoDB will be available on `mongodb://localhost:27017`.
9. If `VITE_API_BASE_URL` is not set, frontend targets `http://<current-host>:8000/api`, so opening the UI via LAN IP also uses the same LAN host for API calls.
10. If frontend is opened from another origin in production, add it to `BACKEND_CORS_ORIGINS` in `.env`.
11. Configure Copart API headers in `.env`: `COPART_API_DEVICE_NAME`, `COPART_API_D_TOKEN`, `COPART_API_COOKIE`, and optionally override `COPART_API_BASE_URL`, `COPART_API_SEARCH_PATH`, `COPART_API_SITECODE`.
12. `COPART_HTTP_TIMEOUT_SECONDS`, `COPART_HTTP_CONNECT_TIMEOUT_SECONDS`, `COPART_HTTP_KEEPALIVE_EXPIRY_SECONDS`, `COPART_HTTP_MAX_CONNECTIONS`, and `COPART_HTTP_MAX_KEEPALIVE_CONNECTIONS` tune reusable HTTP clients for both direct Copart access and NAS gateway transport.
13. `SAVED_SEARCH_POLL_INTERVAL_MINUTES` controls how often the worker refreshes cached results for saved searches.
14. `WATCHLIST_DEFAULT_POLL_INTERVAL_MINUTES`, `WATCHLIST_NEAR_AUCTION_POLL_INTERVAL_MINUTES`, and `WATCHLIST_NEAR_AUCTION_WINDOW_MINUTES` control tracked-lot polling cadence, including the faster near-auction mode.
15. On the primary backend, set `COPART_GATEWAY_BASE_URL` and `COPART_GATEWAY_TOKEN` to route all live Copart traffic through NAS. Leave `COPART_GATEWAY_BASE_URL` empty on the NAS gateway itself.
16. If you use direct lot lookup, `COPART_API_LOT_DETAILS_PATH` defaults to `/lots-api/v1/lot-details?services=bidIncrementsBySiteV2`.
17. If you use backend-driven catalog refresh, `COPART_API_SEARCH_KEYWORDS_PATH` defaults to `/mcs/v2/public/data/search/keywords`.
18. For browser push registration and delivery, configure `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, and `VAPID_SUBJECT` in `.env`.

## NAS Gateway

Runtime expectations:

- `COPART_GATEWAY_TOKEN` is required on both AWS and NAS.
- `COPART_GATEWAY_BASE_URL` is required only on AWS primary backend.
- NAS gateway returns raw Copart JSON with standard HTTP `ETag`/`304` behavior and should rely on normal HTTP compression (`gzip`) instead of custom payload wrappers.
- For production rollout, put the NAS gateway behind HTTPS and restrict inbound traffic to the AWS static IP or another explicit allowlist.
- Gateway and client logs now classify failures separately for `timeout`, transport failure, upstream rejection, malformed response, and gateway unavailability so operator review can tell whether the issue is inside NAS proxying or deeper in Copart/upstream traffic.

Local gateway run:

```bash
source .venv/bin/activate
uvicorn cartrap.gateway_app:app --reload --host 0.0.0.0 --port 8010
```

Docker Compose gateway profile:

```bash
docker compose --profile gateway up --build copart-gateway
```

## VAPID Keys

Generate VAPID keys with the installed `py-vapid` CLI:

```bash
source .venv/bin/activate
mkdir -p backend/keys
cd backend/keys
vapid --gen
vapid --applicationServerKey --private-key private_key.pem
```

Set the printed `Application Server Key` value as `VAPID_PUBLIC_KEY`, point `VAPID_PRIVATE_KEY` to `backend/keys/private_key.pem`, and use a contact URI such as `mailto:admin@example.com` for `VAPID_SUBJECT`.

## Services
- `mongodb` - primary database
- `backend` - API container
- `worker` - background jobs container
- `copart-gateway` - optional NAS-style raw Copart proxy container, enabled with `docker compose --profile gateway`
- `frontend` - static PWA served by nginx after a Vite production build

## Initial Commands
- Backend tests: `source .venv/bin/activate && pytest backend/tests`
- Frontend tests: `npm --prefix frontend run test`
- Frontend production build: `npm --prefix frontend run build`
- Full stack: `docker compose up --build`
- Rebuild static Copart make/model catalog: `python3 scripts/generate_copart_make_model_catalog.py --keywords /path/to/keywords`

## Docker Notes
- `backend` and `worker` share the same Python image build and differ only by command.
- `copart-gateway` reuses the same backend image and switches entrypoint via `APP_MODULE=cartrap.gateway_app:app`.
- `frontend` is built with Vite and served from nginx on port `4173`.
- `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` seed the first admin user on API startup.
- `BACKEND_CORS_ORIGINS` controls which browser origins may call the API; local defaults cover `localhost` and `127.0.0.1` on ports `5173` and `4173`, while non-production backend also accepts private LAN IPv4 origins via regex.
- `VITE_API_BASE_URL` can override the frontend API target; leave it empty to let the frontend derive `http://<current-host>:8000/api` automatically.
- Copart integration now uses the JSON API on `mmember.copart.com`; HTML scraping and page parsing are no longer used.
- `COPART_GATEWAY_ENABLE_GZIP=true` tells AWS-side gateway transport to advertise `Accept-Encoding: gzip`; actual compression should be terminated by the NAS gateway/reverse proxy layer.
- Static make/model catalog generation lives in `scripts/generate_copart_make_model_catalog.py`, with manual fixes in `backend/src/cartrap/modules/search/data/copart_make_model_overrides.json`.
- At runtime, the current make/model catalog is served from Mongo through `/api/search/catalog`, and admins can force a refresh via `/api/admin/search-catalog/refresh`.
- Structured operator log families include `search.execute.*`, `saved_search.refresh.*`, `saved_search.poll.*`, `watchlist.refresh.*`, `worker.poll_cycle.*`, `live_sync.*`, `copart_gateway.proxy.*`, and `copart_client.request.*`.

## Current Status
- MVP backend flows are implemented: invite auth, roles, Copart API integration, watchlist, search, monitoring, and push subscription management.
- MVP frontend flows are implemented: login, invite acceptance, admin invite creation, backend-backed manual search catalog, modal search results, saved-search rerun, watchlist thumbnails with gallery modal, client-side push registration UX, and degraded/offline live-sync messaging backed by `/api/system/status`.
- Docker images for `backend`, `worker`, and `frontend` are buildable and the compose stack passes a basic smoke check.

## Latest Verification
- `./.venv/bin/pytest backend/tests`
- `npm --prefix frontend run test`
- `npm --prefix frontend run build`
- `docker compose build backend frontend worker`
- `docker compose up -d`
- `curl http://localhost:8000/api/health`
- `curl -I http://localhost:5173`
