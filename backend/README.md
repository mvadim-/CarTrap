# CarTrap Backend

FastAPI backend package for the CarTrap split deployment:

- `cartrap.main:app` is the primary AWS-hosted API that serves auth, Mongo-backed app state, watchlist/search APIs, and worker-triggered flows.
- `cartrap.gateway_app:app` is the NAS-hosted `copart-gateway` that proxies raw Copart JSON over bearer-authenticated HTTP.

## Local Commands

Primary backend:

```bash
uvicorn cartrap.main:app --reload --host 0.0.0.0 --port 8000
```

Gateway app:

```bash
uvicorn cartrap.gateway_app:app --reload --host 0.0.0.0 --port 8010
```

Worker:

```bash
python -m cartrap.worker.main
```

## Split Runtime Notes

- AWS backend should set `COPART_GATEWAY_BASE_URL` and `COPART_GATEWAY_TOKEN` so all live Copart traffic goes through NAS.
- NAS `copart-gateway` only needs direct Copart credentials plus `COPART_GATEWAY_TOKEN`; it should leave `COPART_GATEWAY_BASE_URL` empty.
- There is no AWS-side direct fallback to Copart when gateway sync fails.
- `/api/system/status` on the primary backend exposes the persisted `live_sync` state consumed by the frontend offline banner.
