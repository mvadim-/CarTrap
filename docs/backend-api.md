# Backend API Reference

This document describes the current HTTP API exposed by the FastAPI backend.

## Overview

- Base URL: `/api`
- Auth scheme: `Authorization: Bearer <access_token>`
- Content type: `application/json`
- Public endpoints:
  - `GET /health`
  - `POST /auth/login`
  - `POST /auth/refresh`
  - `POST /auth/invites/accept`
- Authenticated user endpoints:
  - `search/*`
  - `watchlist/*`
  - `notifications/*`
- Admin-only endpoints:
  - `admin/*`

## Authentication and Roles

- `access_token` and `refresh_token` are stateless JWTs signed with different secrets.
- `access_token` is required for all protected endpoints.
- `refresh_token` is used only by `POST /auth/refresh`.
- Roles:
  - `admin`: can create/revoke invites and refresh the search catalog.
  - `user`: can use search, watchlist, and notification endpoints.

## Common Error Semantics

| Status | Meaning |
| --- | --- |
| `400` | Invalid input or malformed request in downstream logic |
| `401` | Missing/invalid token or invalid credentials |
| `403` | Authenticated but admin role is required |
| `404` | Requested entity was not found |
| `409` | Conflict, duplicate resource, or invalid state transition |
| `410` | Expired invite |
| `422` | FastAPI/Pydantic validation error |
| `502` | Upstream Copart failure or failed catalog refresh |
| `503` | Search catalog is unavailable |

## Endpoint Summary

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | public | Healthcheck |
| `POST` | `/auth/login` | public | Login by email/password |
| `POST` | `/auth/refresh` | public | Refresh access token |
| `POST` | `/auth/invites/accept` | public | Accept invite and create user |
| `POST` | `/admin/invites` | admin | Create invite |
| `DELETE` | `/admin/invites/{invite_id}` | admin | Revoke pending invite |
| `POST` | `/admin/search-catalog/refresh` | admin | Refresh Mongo-backed search catalog |
| `POST` | `/search` | user/admin | Manual Copart search |
| `GET` | `/search/saved` | user/admin | List saved searches |
| `POST` | `/search/saved` | user/admin | Save current search |
| `DELETE` | `/search/saved/{saved_search_id}` | user/admin | Delete saved search |
| `GET` | `/search/catalog` | user/admin | Read make/model/year catalog |
| `POST` | `/search/watchlist` | user/admin | Add search result to watchlist |
| `GET` | `/watchlist` | user/admin | List tracked lots |
| `POST` | `/watchlist` | user/admin | Add tracked lot by URL or lot number |
| `DELETE` | `/watchlist/{tracked_lot_id}` | user/admin | Remove tracked lot |
| `GET` | `/notifications/subscriptions` | user/admin | List push subscriptions |
| `POST` | `/notifications/subscriptions` | user/admin | Create/update push subscription |
| `DELETE` | `/notifications/subscriptions?endpoint=...` | user/admin | Remove push subscription |

## Detailed Endpoints

### System

#### `GET /api/health`

Returns backend health metadata.

Response:

```json
{
  "status": "ok",
  "service": "CarTrap API",
  "environment": "development"
}
```

### Auth

#### `POST /api/auth/login`

Request:

```json
{
  "email": "admin@example.com",
  "password": "AdminPass123"
}
```

Response:

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer"
}
```

#### `POST /api/auth/refresh`

Request:

```json
{
  "refresh_token": "<jwt>"
}
```

Response is the same `TokenPairResponse` as login.

#### `POST /api/auth/invites/accept`

Creates a regular user account from an invite token.

Request:

```json
{
  "token": "<invite-token>",
  "password": "UserPass123"
}
```

Response:

```json
{
  "user": {
    "id": "mongo-object-id",
    "email": "buyer@example.com",
    "role": "user",
    "status": "active"
  }
}
```

### Admin

#### `POST /api/admin/invites`

Creates a new pending invite.

Request:

```json
{
  "email": "buyer@example.com"
}
```

Response:

```json
{
  "id": "mongo-object-id",
  "email": "buyer@example.com",
  "status": "pending",
  "token": "<invite-token>",
  "expires_at": "2026-03-16T10:00:00Z"
}
```

#### `DELETE /api/admin/invites/{invite_id}`

Revokes a pending invite. Returns the invite payload after the state change.

#### `POST /api/admin/search-catalog/refresh`

Rebuilds the Copart make/model/year catalog and stores it in MongoDB.

Response shape:

- `generated_at`
- `updated_at`
- `summary`
- `years`
- `makes[]`
- `manual_override_count`

### Search

#### `POST /api/search`

Runs manual Copart search and fetches all result pages based on `numFound`.

Accepted request fields:

| Field | Type | Notes |
| --- | --- | --- |
| `make` | `string` | Optional if `make_filter` is used |
| `model` | `string` | Optional if `model_filter` is used |
| `make_filter` | `string` | Catalog-derived Copart filter query |
| `model_filter` | `string` | Catalog-derived Copart filter query |
| `year_from` | `integer` | `1900..2100` |
| `year_to` | `integer` | `1900..2100`, must be `>= year_from` |
| `lot_number` | `string` | Digits are normalized before search |

At least one of `make`, `model`, `make_filter`, `model_filter`, `lot_number` must be present.

Response:

```json
{
  "results": [
    {
      "lot_number": "12345678",
      "title": "2025 FORD MUSTANG MACH-E PREMIUM",
      "url": "https://www.copart.com/lot/12345678",
      "thumbnail_url": "https://img.copart.com/12345678.jpg",
      "location": "CA - SACRAMENTO",
      "sale_date": "2026-03-20T17:00:00Z",
      "current_bid": 4200.0,
      "currency": "USD",
      "status": "live"
    }
  ],
  "total_results": 42,
  "source_request": {
    "MISC": ["..."],
    "sort": ["..."],
    "filter": [],
    "localFilters": [],
    "latlngFacets": false,
    "pageNumber": 1,
    "userStartUtcDatetime": "2026-03-13T00:00:00Z"
  }
}
```

#### `GET /api/search/saved`

Lists saved searches for the current user.

Response:

```json
{
  "items": [
    {
      "id": "mongo-object-id",
      "label": "FORD MUSTANG MACH-E 2025-2027",
      "criteria": {
        "make": "FORD",
        "model": "MUSTANG MACH-E",
        "make_filter": null,
        "model_filter": null,
        "year_from": 2025,
        "year_to": 2027,
        "lot_number": null
      },
      "result_count": 42,
      "created_at": "2026-03-13T10:00:00Z"
    }
  ]
}
```

#### `POST /api/search/saved`

Stores a user-scoped saved search.

Accepted request fields:

- all fields from `POST /api/search`
- `label` optional custom title
- `result_count` optional snapshot of the last known number of matches

Response:

```json
{
  "saved_search": {
    "id": "mongo-object-id",
    "label": "FORD MUSTANG MACH-E 2025-2027",
    "criteria": {
      "make": "FORD",
      "model": "MUSTANG MACH-E"
    },
    "result_count": 42,
    "created_at": "2026-03-13T10:00:00Z"
  }
}
```

#### `DELETE /api/search/saved/{saved_search_id}`

Deletes a saved search belonging to the current user.

- Success response: `204 No Content`

#### `GET /api/search/catalog`

Returns current Mongo-backed search catalog.

Response fields:

- `generated_at`
- `updated_at`
- `summary.make_count`
- `summary.model_count`
- `summary.assigned_model_count`
- `summary.exact_match_count`
- `summary.fuzzy_match_count`
- `summary.unassigned_model_count`
- `summary.year_count`
- `years[]`
- `makes[].slug`
- `makes[].name`
- `makes[].aliases[]`
- `makes[].search_filter`
- `makes[].models[].slug`
- `makes[].models[].name`
- `makes[].models[].search_filter`
- `manual_override_count`

#### `POST /api/search/watchlist`

Adds a lot from search results to the watchlist.

Request:

```json
{
  "lot_url": "https://www.copart.com/lot/12345678"
}
```

Response shape is identical to `POST /api/watchlist`.

### Watchlist

#### `GET /api/watchlist`

Lists current user tracked lots.

Response:

```json
{
  "items": [
    {
      "id": "mongo-object-id",
      "lot_number": "12345678",
      "url": "https://www.copart.com/lot/12345678",
      "title": "2025 FORD MUSTANG MACH-E PREMIUM",
      "thumbnail_url": "https://img.copart.com/12345678.jpg",
      "image_urls": ["https://img.copart.com/12345678.jpg"],
      "status": "live",
      "raw_status": "Live",
      "current_bid": 4200.0,
      "buy_now_price": null,
      "currency": "USD",
      "sale_date": "2026-03-20T17:00:00Z",
      "last_checked_at": "2026-03-13T10:00:00Z",
      "created_at": "2026-03-13T10:00:00Z"
    }
  ]
}
```

#### `POST /api/watchlist`

Adds a lot either by direct Copart URL or by raw lot number.

Request variants:

```json
{
  "lot_url": "https://www.copart.com/lot/12345678"
}
```

```json
{
  "lot_number": "12345678"
}
```

Response:

```json
{
  "tracked_lot": {
    "id": "mongo-object-id",
    "lot_number": "12345678",
    "url": "https://www.copart.com/lot/12345678",
    "title": "2025 FORD MUSTANG MACH-E PREMIUM",
    "thumbnail_url": "https://img.copart.com/12345678.jpg",
    "image_urls": ["https://img.copart.com/12345678.jpg"],
    "status": "upcoming",
    "raw_status": "Upcoming",
    "current_bid": 0.0,
    "buy_now_price": null,
    "currency": "USD",
    "sale_date": null,
    "last_checked_at": "2026-03-13T10:00:00Z",
    "created_at": "2026-03-13T10:00:00Z"
  },
  "initial_snapshot": {
    "id": "mongo-object-id",
    "tracked_lot_id": "mongo-object-id",
    "lot_number": "12345678",
    "status": "upcoming",
    "raw_status": "Upcoming",
    "current_bid": 0.0,
    "buy_now_price": null,
    "currency": "USD",
    "sale_date": null,
    "detected_at": "2026-03-13T10:00:00Z"
  }
}
```

#### `DELETE /api/watchlist/{tracked_lot_id}`

Deletes tracked lot and all related snapshots.

- Success response: `204 No Content`

### Notifications

#### `GET /api/notifications/subscriptions`

Lists push subscriptions for current user.

Response:

```json
{
  "items": [
    {
      "id": "mongo-object-id",
      "endpoint": "https://push.example/subscription-id",
      "user_agent": "Mozilla/5.0 ...",
      "created_at": "2026-03-13T10:00:00Z",
      "updated_at": "2026-03-13T10:05:00Z"
    }
  ]
}
```

#### `POST /api/notifications/subscriptions`

Creates or updates push subscription by endpoint.

Request:

```json
{
  "subscription": {
    "endpoint": "https://push.example/subscription-id",
    "expirationTime": null,
    "keys": {
      "p256dh": "<key>",
      "auth": "<key>"
    }
  },
  "user_agent": "Mozilla/5.0 ..."
}
```

Response:

```json
{
  "id": "mongo-object-id",
  "endpoint": "https://push.example/subscription-id",
  "user_agent": "Mozilla/5.0 ...",
  "created_at": "2026-03-13T10:00:00Z",
  "updated_at": "2026-03-13T10:05:00Z"
}
```

#### `DELETE /api/notifications/subscriptions?endpoint=...`

Deletes subscription by exact endpoint string.

- Success response: `204 No Content`

## Notes on Internal Behavior

- Search calls Copart JSON API and transparently loads all pages using `pageNumber`.
- `saved_searches.result_count` is a snapshot of the last known count passed from the client, not a live computed counter.
- Watchlist `GET` may backfill missing media for legacy documents.
- Notification delivery exists as backend service logic, but there is no public endpoint for sending arbitrary pushes.
